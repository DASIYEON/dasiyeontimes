#!/usr/bin/env python3
"""다시연 타임즈 정적 페이지 생성 스크립트 (정적 기사 생성 V3)

Supabase articles 테이블에서 발행 기사를 읽어
  1) index.html          — 히어로·최신기사·섹션이 미리 채워진 홈
  2) articles/{id}.html  — 기사별 정적 페이지 (기사별 OG태그·canonical·JSON-LD 포함)
를 templates/ 의 템플릿으로부터 생성한다.

운영 원칙 (공통 운영규칙 §15 연계):
  - 정본(콘텐츠)은 Supabase, 정본(마크업)은 templates/. 생성된 HTML은 파생물이다.
  - index.html 과 articles/*.html 은 직접 수정하지 않는다. 디자인 수정은 templates/에서.
  - 발행 목록에 없는 articles/*.html 은 삭제한다 (기사 삭제·비공개 반영).

GitHub Actions에서 sitemap/RSS 생성과 함께 실행된다.
"""
import json, urllib.request, urllib.parse, datetime, html, re, os, glob, sys

SITE = "https://dasiyeontimes.kr"
SUPABASE_URL = "https://lguvdtesdetteasnniif.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxndXZkdGVzZGV0dGVhc25uaWlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAwNzk1MjUsImV4cCI6MjA5NTY1NTUyNX0.SBUdAzeAwwJ-v2CVYBPdIvTyXLePWZuthNTmWdRjwig"
DEFAULT_OG_IMAGE = f"{SITE}/images/og-image.png"
CATS = ["마음", "경영", "AI", "컬럼"]
GENERATED_MARK = "<!-- 이 파일은 scripts/generate_static.py 가 생성한 파생 파일입니다. 직접 수정하지 마세요 — 수정은 templates/ 에서. -->\n"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def fetch_articles():
    q = "select=*&status=eq." + urllib.parse.quote("발행") + "&order=id.desc&limit=100"
    url = f"{SUPABASE_URL}/rest/v1/articles?{q}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fmt_date(v):
    if not v:
        return ""
    s = str(v)
    if re.match(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$", s):
        return s.replace("-", ".")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return s


def date_iso(a):
    for key in ("published_at", "created_at", "date", "date_str", "updated_at"):
        v = a.get(key)
        if v:
            m = re.match(r"(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})", str(v))
            if m:
                y, mo, d = m.groups()
                try:
                    return datetime.date(int(y), int(mo), int(d)).isoformat()
                except ValueError:
                    pass
    return datetime.date.today().isoformat()


def norm(a):
    return {
        "id": a.get("id"),
        "title": a.get("title") or "제목 없음",
        "summary": a.get("summary") or "",
        "body": a.get("body") or "<p>본문 내용이 없습니다.</p>",
        "category": a.get("category") or "컬럼",
        "image": a.get("image") or "",
        "author": a.get("author") or "최형규",
        "date_str": a.get("date_str") or fmt_date(a.get("created_at") or a.get("date")),
        "date_iso": date_iso(a),
    }


def art_url(a):
    return f"{SITE}/articles/{a['id']}.html"


def art_href(a):
    return f"articles/{a['id']}.html"


def load_template(name):
    with open(os.path.join("templates", name), encoding="utf-8") as f:
        return f.read()


# ---------- index.html ----------

def hero_html(top):
    img = (f'<img src="{esc(top["image"])}" alt="" fetchpriority="high" decoding="async">'
           if top["image"] else '<div class="hero-fallback"></div>')
    return (f'<a href="{art_href(top)}" style="position:absolute;inset:0;z-index:3" '
            f'aria-label="{esc(top["title"])}"></a>'
            f'{img}<div class="hero-copy"><span class="tag">{esc(top["category"])}</span>'
            f'<h1>{esc(top["title"])}</h1><p>{esc(top["summary"])}</p>'
            f'<div class="meta">{esc(top["author"])} · {esc(top["date_str"])}</div></div>')


def latest_html(arts):
    out = []
    for a in arts[:5]:
        thumb = (f'<img src="{esc(a["image"])}" alt="" loading="lazy" decoding="async">'
                 if a["image"] else "")
        out.append(
            f'<article class="latest-item" onclick="location.href=\'{art_href(a)}\'">'
            f'<div class="latest-thumb">{thumb}</div><div>'
            f'<div class="latest-title">{esc(a["title"])}</div>'
            f'<div class="latest-meta"><span>{esc(a["date_str"])}</span>'
            f'<span class="latest-cat">{esc(a["category"])}</span></div></div></article>')
    return "".join(out)


def sections_html(arts):
    out = []
    for cat in CATS:
        arr = [a for a in arts if a["category"] == cat][:2]
        more = f'category.html?cat={urllib.parse.quote(cat)}'
        if cat == "컬럼":
            cards = "".join(
                f'<article class="column-card" onclick="location.href=\'{art_href(a)}\'">'
                f'<span class="tag">{cat}</span><h3>{esc(a["title"])}</h3><p>{esc(a["summary"])}</p>'
                f'<div class="meta">{esc(a["author"])} · {esc(a["date_str"])}</div></article>'
                for a in arr)
            out.append(f'<section class="section"><div class="section-head"><h2>대표 칼럼</h2>'
                       f'<a href="{more}">더보기 →</a></div>'
                       f'<div class="column-cards">{cards}</div></section>')
        else:
            cards = "".join(
                f'<article class="card" onclick="location.href=\'{art_href(a)}\'">'
                f'<div class="card-img">'
                + (f'<img src="{esc(a["image"])}" alt="" loading="lazy" decoding="async">' if a["image"] else "")
                + f'</div><div class="card-body"><span class="tag">{cat}</span>'
                f'<h3>{esc(a["title"])}</h3><p>{esc(a["summary"])}</p>'
                f'<div class="meta">{esc(a["author"])} · {esc(a["date_str"])}</div></div></article>'
                for a in arr)
            out.append(f'<section class="section"><div class="section-head"><h2>{cat}</h2>'
                       f'<a href="{more}">더보기 →</a></div>'
                       f'<div class="cards">{cards}</div></section>')
    return "".join(out)


def build_index(arts):
    tpl = load_template("index.template.html")
    top = arts[0]
    preload = (f'<link rel="preload" as="image" href="{esc(top["image"])}" fetchpriority="high">'
               if top["image"] else "")
    return (GENERATED_MARK + tpl
            .replace("{{PRELOAD}}", preload)
            .replace("{{TOP_ID}}", esc(top["id"]))
            .replace("{{HERO}}", hero_html(top))
            .replace("{{LATEST}}", latest_html(arts))
            .replace("{{SECTIONS}}", sections_html(arts)))


# ---------- articles/{id}.html ----------

def related_html(arts, self_id):
    rel = [a for a in arts if a["id"] != self_id][:5]
    return "".join(
        f'<article class="related-item" onclick="location.href=\'/{art_href(a)}\'">'
        f'<span class="tag">{esc(a["category"])}</span><h3>{esc(a["title"])}</h3>'
        f'<div class="meta"><span>{esc(a["author"])}</span><span>{esc(a["date_str"])}</span></div></article>'
        for a in rel)


def build_article(a, arts):
    tpl = load_template("article.template.html")
    url = art_url(a)
    og_image = a["image"] or DEFAULT_OG_IMAGE
    hero_fig = (f'<img src="{esc(a["image"])}" alt="{esc(a["title"])}" fetchpriority="high" decoding="async">'
                if a["image"] else '<div class="article-fallback"></div>')
    preload = (f'<link rel="preload" as="image" href="{esc(a["image"])}" fetchpriority="high">'
               if a["image"] else "")
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": a["title"],
        "description": a["summary"],
        "image": [og_image],
        "datePublished": a["date_iso"],
        "author": {"@type": "Person", "name": a["author"]},
        "publisher": {"@type": "NewsMediaOrganization", "name": "다시연 타임즈",
                      "logo": {"@type": "ImageObject", "url": DEFAULT_OG_IMAGE}},
        "mainEntityOfPage": url,
    }, ensure_ascii=False).replace("</", "<\\/")
    return (GENERATED_MARK + tpl
            .replace("{{TITLE_ESC}}", esc(a["title"]))
            .replace("{{SUMMARY_ESC}}", esc(a["summary"]))
            .replace("{{AUTHOR_ESC}}", esc(a["author"]))
            .replace("{{CATEGORY_ESC}}", esc(a["category"]))
            .replace("{{CAT_URLENC}}", urllib.parse.quote(a["category"]))
            .replace("{{DATE_STR}}", esc(a["date_str"]))
            .replace("{{DATE_ISO}}", a["date_iso"])
            .replace("{{URL}}", url)
            .replace("{{OG_IMAGE}}", esc(og_image))
            .replace("{{PRELOAD}}", preload)
            .replace("{{HERO_FIGURE}}", hero_fig)
            .replace("{{BODY}}", a["body"])
            .replace("{{RELATED}}", related_html(arts, a["id"]))
            .replace("{{JSONLD}}", jsonld))


def main():
    raw = fetch_articles()
    arts = [norm(a) for a in raw if a.get("id") is not None]
    if not arts:
        print("발행 기사 0건 — 안전을 위해 아무것도 변경하지 않고 종료합니다.")
        sys.exit(0)
    print(f"발행 기사 {len(arts)}건 확인")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(build_index(arts))
    print("index.html 생성 완료")

    os.makedirs("articles", exist_ok=True)
    valid = set()
    for a in arts:
        path = f"articles/{a['id']}.html"
        valid.add(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_article(a, arts))
    print(f"articles/ 정적 페이지 {len(arts)}건 생성 완료")

    removed = 0
    for path in glob.glob("articles/*.html"):
        if path not in valid:
            os.remove(path)
            removed += 1
    if removed:
        print(f"발행 목록에 없는 정적 페이지 {removed}건 삭제 (기사 삭제/비공개 반영)")


if __name__ == "__main__":
    main()
