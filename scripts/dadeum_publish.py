#!/usr/bin/env python3
"""다듬 기사 폴더를 다시연타임즈 Supabase publish 함수로 전송한다.

python3 scripts/dadeum_publish.py check 기사폴더
python3 scripts/dadeum_publish.py auth
python3 scripts/dadeum_publish.py draft 기사폴더
python3 scripts/dadeum_publish.py publish 기사폴더
python3 scripts/dadeum_publish.py export 기사폴더 요청.json --status 임시저장

Mac 또는 Linux에서 외부 패키지 없이 Python 3.9 이상에서 실행한다. 토큰은 PUBLISH_TOKEN 또는
터미널의 숨김 입력으로 받는다. 자동화는 표준입력으로 토큰 한 줄을 전달할 수 있다.
export는 토큰 없는 요청 본문만 만든다. Supabase 대시보드의 publish > Test에서
POST, x-publish-token 헤더, 생성된 JSON 본문을 사용한다.
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import sys
import socket
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://lguvdtesdetteasnniif.supabase.co/functions/v1/publish"
SITE = "https://dasiyeontimes.kr"
MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
CARD = re.compile(r"카드[ _-]*(\d+)\.(png|jpe?g|webp)", re.I)
COVER = re.compile(r"대표이미지\.(png|jpe?g|webp)", re.I)
MAX_IMAGE = 10 * 1024 * 1024


def normalized(s):
    return unicodedata.normalize("NFC", s)


def photo(path):
    with path.open("rb") as f:
        data = f.read(MAX_IMAGE + 1)
    if not 0 < len(data) <= MAX_IMAGE:
        raise ValueError(f"{path.name} 크기를 확인하세요 (파일당 최대 10 MiB).")
    ext = path.suffix[1:].lower()
    valid = {"png": data.startswith(b"\x89PNG\r\n\x1a\n"),
             "jpg": data.startswith(b"\xff\xd8\xff"), "jpeg": data.startswith(b"\xff\xd8\xff"),
             "webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP"}
    if not valid[ext]:
        raise ValueError(f"{path.name}의 확장자와 실제 이미지 형식이 다릅니다.")
    return {"content_type": MIME[ext], "base64": base64.b64encode(data).decode("ascii")}


def card_alts(path):
    descriptions = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, sep, description = normalized(line).partition("|")
            match = CARD.fullmatch(name.strip())
            if sep and match:
                number = int(match[1])
                if number in descriptions:
                    raise ValueError(f"카드 {number}번의 대체설명이 중복됩니다.")
                descriptions[number] = description.strip()
    return descriptions


def article_payload(folder, status, allow_missing=False):
    source = folder / "4_다듬/기사데이터_다듬.json"
    if not source.is_file():
        source = folder / "2_새봄/기사데이터.json"
    raw = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("원고 JSON은 기사 한 건을 담은 객체여야 합니다.")
    payload = {"status": status}
    for key in ("title", "body", "category", "summary", "author", "subtitle", "date_str"):
        value = raw.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"원고의 {key} 값은 문자열이어야 합니다.")
        if value.strip():
            payload[key] = value.strip()
    for key in ("title", "body", "category"):
        if key not in payload:
            raise ValueError(f"원고에 {key} 값이 필요합니다.")
    if payload["category"] not in ("마음", "경영", "AI", "컬럼"):
        raise ValueError("분야는 마음, 경영, AI, 컬럼 중 하나여야 합니다.")
    if re.search(r"<script[\s>]", payload["body"], re.I):
        raise ValueError("원고 본문에 script 태그가 있습니다.")
    if raw.get("id") or raw.get("image") or raw.get("image_url") or raw.get("cards"):
        raise ValueError("기존 기사 ID·이미지가 포함된 발행 요청 파일입니다. 원고 JSON과 빛결 원본을 사용하세요.")

    design = folder / "3_빛결"
    files = list(design.iterdir()) if design.exists() else []
    covers = [p for p in files if COVER.fullmatch(normalized(p.name))]
    if len(covers) > 1:
        raise ValueError("별도 대표이미지를 한 장으로 지정하세요.")
    if covers:
        payload["image"] = photo(covers[0])
    elif not allow_missing:
        raise ValueError("3_빛결에 별도 대표이미지가 없습니다. 예비 발행은 --allow-missing-images를 사용하세요.")

    cards = {}
    for path in files:
        match = CARD.fullmatch(normalized(path.name))
        if match:
            number = int(match[1])
            if number in cards:
                raise ValueError(f"카드 {number}번 파일이 두 개입니다.")
            cards[number] = path
    if len(cards) > 12 or sorted(cards) != list(range(1, len(cards) + 1)):
        raise ValueError("카드는 1번부터 빠짐없이 최대 12장까지 번호를 붙이세요.")
    if not cards and not allow_missing:
        raise ValueError("번호가 붙은 카드가 없습니다. 예비 발행은 --allow-missing-images를 사용하세요.")
    descriptions = card_alts(design / "카드별_대체설명.txt")
    if set(descriptions) - set(cards):
        raise ValueError("대체설명에 대응하는 카드 이미지가 빠졌습니다.")
    payload["cards"] = []
    for number, path in sorted(cards.items()):
        alt = descriptions.get(number)
        if not alt:
            raise ValueError(f"카드 {number}번의 대체설명이 필요합니다. 형식: {path.name} | 설명")
        payload["cards"].append(dict(photo(path), alt=alt))
    return payload


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(payload, token):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(ENDPOINT, data=data, method="POST",
                      headers={"Content-Type": "application/json", "x-publish-token": token})
    try:
        with build_opener(NoRedirect()).open(request, timeout=120) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        try:
            result = json.loads(exc.read(16384))
        except (ValueError, UnicodeError):
            result = {}
        return exc.code, result


def request_result(payload, token, auth=False):
    try:
        code, response = post(payload, token)
    except (OSError, ValueError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        if isinstance(reason, socket.gaierror):
            raise ValueError("DNS 조회 실패로 발행 서버에 연결하지 못했습니다. export로 요청 JSON을 만들 수 있습니다.") from exc
        raise ValueError(f"HTTP 응답 확인 실패 ({type(reason).__name__}). 창구 로그와 기사 목록을 조회한 뒤 재시도하세요.") from exc
    if not isinstance(response, dict):
        raise ValueError("응답 형식이 예상과 다릅니다. 창구 로그를 확인하세요.")
    if auth and code == 400 and response.get("error") == "title(제목)이 필요합니다.":
        return {"인증": "통과", "HTTP": code}
    if auth or code != 200 or response.get("ok") is not True:
        error = str(response.get("error", "창구 로그 확인 필요")).replace(token, "[생략]")
        raise ValueError(f"HTTP {code}: {error[:400]}. 재전송 전 창구 로그를 확인하세요.")
    article_id = str(response.get("id", ""))
    status = response.get("status")
    url = response.get("url")
    duplicate = response.get("duplicate")
    if not re.fullmatch(r"\d{1,16}", article_id) or type(duplicate) is not bool:
        raise ValueError("기사 ID 또는 중복 확인 결과가 없습니다. 기사 목록을 확인하세요.")
    if status == "발행" and url != f"{SITE}/articles/{article_id}.html":
        raise ValueError("발행 주소를 확인할 수 없습니다. 기사 목록을 확인하세요.")
    if duplicate and status == "발행":
        return {"결과": "같은 제목의 기존 발행 기사", "id": article_id, "url": url}
    if status != payload["status"] or duplicate or (status == "임시저장" and url is not None):
        raise ValueError("요청과 응답의 발행 상태가 다릅니다. 기사 목록을 확인하세요.")
    cards = response.get("cards")
    if not isinstance(cards, list) or len(cards) != len(payload["cards"]) or not all(cards):
        raise ValueError("저장 응답의 카드 수가 맞지 않습니다. 같은 기사 ID를 확인하세요.")
    if bool(payload.get("image")) != bool(response.get("image")):
        raise ValueError("저장 응답의 대표이미지를 확인하세요.")
    return {"결과": status, "id": article_id, "url": url, "대표사진": bool(response.get("image")), "카드": len(cards)}


def write_request(path, payload):
    # Publish a complete export atomically and never replace an article or an existing request.
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
            temp = Path(f.name)
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        os.link(temp, path)
    finally:
        if temp:
            temp.unlink(missing_ok=True)


@contextmanager
def article_lock(title):
    # Serialize same-title submissions by overlapping local schedules on the publishing Mac.
    import fcntl
    directory = Path(tempfile.gettempdir()) / f"dadeum-publish-{os.getuid()}"
    directory.mkdir(mode=0o700, exist_ok=True)
    digest = hashlib.sha256(normalized(title).encode("utf-8")).hexdigest()
    with (directory / digest).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("같은 제목의 업로드가 이미 실행 중입니다.") from exc
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("auth", help="빈 본문으로 인증과 네트워크 연결 확인")
    for name in ("check", "draft", "publish", "export"):
        cmd = modes.add_parser(name)
        cmd.add_argument("folder", type=Path)
        cmd.add_argument("--allow-missing-images", action="store_true", help="예비 기사에서 아직 없는 대표 또는 카드 묶음 생략")
        if name == "export":
            cmd.add_argument("output", type=Path)
            cmd.add_argument("--status", choices=["임시저장", "발행"], default="임시저장")
    args = parser.parse_args()
    payload = {}
    if args.mode != "auth":
        status = "발행" if args.mode == "publish" else getattr(args, "status", "임시저장")
        payload = article_payload(args.folder, status, args.allow_missing_images)
        summary = {"제목": payload["title"], "대표사진": bool(payload.get("image")), "카드": len(payload["cards"])}
        if args.mode == "check":
            return dict(summary, 결과="전송 전 검사 완료")
        # A corrected headline can no longer be deduplicated by the server's title check.
        record_dir = args.folder / "4_다듬"
        if any(normalized(p.stem) == "발행기록" for p in record_dir.glob("*")):
            raise ValueError("발행기록이 있는 기사입니다. 기록의 기존 기사 ID로 보완하세요.")
        if args.mode == "export":
            write_request(args.output, payload)
            return dict(summary, 결과="요청 파일 생성", 상태=status, 파일=str(args.output))
    token = os.environ.get("PUBLISH_TOKEN")
    if not token:
        token = getpass.getpass("발행 토큰: ") if sys.stdin.isatty() else sys.stdin.readline().strip()
    if not token or any(c.isspace() for c in token):
        raise ValueError("직무기술서의 발행 토큰을 입력하세요.")
    if args.mode == "auth":
        return request_result({}, token, auth=True)
    with article_lock(payload["title"]):
        return request_result(payload, token)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except (OSError, ValueError, EOFError) as exc:
        sys.exit(f"다듬 업로드: {exc}")
