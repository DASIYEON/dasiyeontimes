#!/usr/bin/env python3
"""다시연 타임즈 sitemap.xml + rss.xml 자동 생성 스크립트
Supabase articles 테이블에서 발행 기사를 읽어 검색엔진용 파일을 생성한다.
GitHub Actions에서 매일 실행되며, 변경이 있을 때만 커밋된다.
"""
import json, urllib.request, datetime, html, re

SITE = "https://dasiyeontimes.kr"
SUPABASE_URL = "https://lguvdtesdetteasnniif.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxndXZkdGVzZGV0dGVhc25uaWlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAwNzk1MjUsImV4cCI6MjA5NTY1NTUyNX0.SBUdAzeAwwJ-v2CVYBPdIvTyXLePWZuthNTmWdRjwig"

STATIC_PAGES = [
    ("", "daily", "1.0"),
    ("about.html", "monthly", "0.5"),
    ("category.html?cat=%EB%A7%88%EC%9D%8C", "daily", "0.8"),
    ("category.html?cat=%EA%B2%BD%EC%98%81", "daily", "0.8"),
    ("category.html?cat=AI", "daily", "0.8"),
    ("category.html?cat=%EC%BB%AC%EB%9F%BC", "daily", "0.8"),
    ("ethics.html", "yearly", "0.3"),
    ("privacy.html", "yearly", "0.3"),
    ("terms.html", "yearly", "0.3"),
    ("youth.html", "yearly", "0.3"),
]

def fetch_articles():
    url = f"{SUPABASE_URL}/rest/v1/articles?select=*&order=id.desc"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    published = [a for a in data if str(a.get("status", "")) == "발행"]
    return published

def art_date(a):
    for key in ("published_at", "created_at", "date", "dateStr", "updated_at"):
        v = a.get(key)
        if v:
            m = re.match(r"(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})", str(v))
            if m:
                y, mo, d = m.groups()
                try:
                    return datetime.date(int(y), int(mo), int(d))
                except ValueError:
                    pass
    return datetime.date.today()

def strip_html(s, limit=300):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]

def build_sitemap(articles):
    today = datetime.date.today().isoformat()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, freq, pri in STATIC_PAGES:
        out.append(f"  <url><loc>{SITE}/{path}</loc><lastmod>{today}</lastmod>"
                   f"<changefreq>{freq}</changefreq><priority>{pri}</priority></url>")
    for a in articles:
        loc = f"{SITE}/article.html?id={a['id']}"
        lastmod = art_date(a).isoformat()
        out.append(f"  <url><loc>{html.escape(loc)}</loc><lastmod>{lastmod}</lastmod>"
                   f"<changefreq>monthly</changefreq><priority>0.7</priority></url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"

def rfc822(d):
    dt = datetime.datetime(d.year, d.month, d.day, 9, 0, 0)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0900")

def build_rss(articles):
    now = rfc822(datetime.date.today())
    items = []
    for a in articles[:50]:
        link = f"{SITE}/article.html?id={a['id']}"
        title = html.escape(strip_html(a.get("title", ""), 200))
        desc = html.escape(strip_html(a.get("summary") or a.get("body", ""), 300))
        author = html.escape(strip_html(a.get("author", "다시연 타임즈"), 50))
        cat = html.escape(strip_html(a.get("category", ""), 20))
        items.append(
            "    <item>\n"
            f"      <title>{title}</title>\n"
            f"      <link>{html.escape(link)}</link>\n"
            f"      <guid isPermaLink=\"true\">{html.escape(link)}</guid>\n"
            f"      <description>{desc}</description>\n"
            f"      <category>{cat}</category>\n"
            f"      <dc:creator>{author}</dc:creator>\n"
            f"      <pubDate>{rfc822(art_date(a))}</pubDate>\n"
            "    </item>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>다시연 타임즈</title>\n"
        f"    <link>{SITE}/</link>\n"
        "    <description>회복과 성장의 미디어 — 마음·경영·AI·삶의 통찰을 전합니다</description>\n"
        "    <language>ko</language>\n"
        f"    <lastBuildDate>{now}</lastBuildDate>\n"
        f"    <atom:link href=\"{SITE}/rss.xml\" rel=\"self\" type=\"application/rss+xml\"/>\n"
        + "\n".join(items) + "\n"
        "  </channel>\n"
        "</rss>\n")

def main():
    articles = fetch_articles()
    print(f"발행 기사 {len(articles)}건 확인")
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(build_sitemap(articles))
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(build_rss(articles))
    print("sitemap.xml, rss.xml 생성 완료")

if __name__ == "__main__":
    main()
