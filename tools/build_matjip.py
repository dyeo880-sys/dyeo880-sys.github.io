#!/usr/bin/env python3
"""
라디오 맛집 게시판(Firebase /board) 글을 검색엔진이 읽을 수 있는 정적 HTML 페이지로 만듭니다.

  - /matjip/index.html            전국 맛집 모음 (지역 링크 + 최신 글)
  - /matjip/<지역>/index.html     시·도별 맛집 목록  (예: /matjip/seoul/)
  - /matjip/p/<글ID>.html         글 하나당 페이지    (가게 이름으로 검색되게)
  - /sitemap.xml                  위 페이지 전부 + 메인 주소

사용법 (저장소 맨 위 폴더에서):  python3 tools/build_matjip.py
표준 라이브러리만 씁니다. 설치할 것이 없습니다.
테스트용: python3 tools/build_matjip.py --file board.json   (인터넷 없이 파일로 시험)
"""
import html, json, os, re, shutil, sys, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

ROOT = "https://dyeo880-sys.github.io/"
DB = "https://project-4230942543796585572-default-rtdb.firebaseio.com"
SITE = "Radiola 웹 라디오"
KST = timezone(timedelta(hours=9))

REGIONS = {  # 게시판 지역값: (주소용 영문, 정식 이름)
    "서울": ("seoul", "서울특별시"), "부산": ("busan", "부산광역시"), "대구": ("daegu", "대구광역시"),
    "인천": ("incheon", "인천광역시"), "광주": ("gwangju", "광주광역시"), "대전": ("daejeon", "대전광역시"),
    "울산": ("ulsan", "울산광역시"), "세종": ("sejong", "세종특별자치시"), "경기": ("gyeonggi", "경기도"),
    "강원": ("gangwon", "강원도"), "충북": ("chungbuk", "충청북도"), "충남": ("chungnam", "충청남도"),
    "전북": ("jeonbuk", "전라북도"), "전남": ("jeonnam", "전라남도"), "경북": ("gyeongbuk", "경상북도"),
    "경남": ("gyeongnam", "경상남도"), "제주": ("jeju", "제주특별자치도"),
}
MAP_HOSTS = ("kakao.com", "naver.com", "naver.me", "google.com", "goo.gl", "kko.to", "kko.kakao.com")

e = lambda x: html.escape(str(x or ""), quote=True)
def clip(t, n):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"

def safe_map(u):
    try:
        p = urllib.parse.urlparse(u or "")
        if p.scheme == "https" and any(p.hostname and (p.hostname == h or p.hostname.endswith("." + h)) for h in MAP_HOSTS):
            return u
    except Exception:
        pass
    return ""

CSS = """
body{margin:0;background:radial-gradient(ellipse at top,#6b4a2e,#1d120b 70%);color:#f0e2c4;font:16px/1.7 "Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;padding:16px}
.w{max-width:820px;margin:0 auto;background:#3b2417;border:2px solid #2a190e;border-radius:16px;padding:20px 22px;box-shadow:0 14px 40px #000a}
a{color:#ffcf7a}h1{font-size:24px;margin:.2em 0 .4em;color:#ffcf7a}h2{font-size:18px;margin:1.4em 0 .4em;color:#ffcf7a}
.nav{font-size:14px;opacity:.9}.cta{display:inline-block;margin:10px 0;padding:10px 16px;border-radius:8px;background:#b99a5b;color:#2a1a08;font-weight:700;text-decoration:none}
.card{background:#241610;border:1px solid #b99a5b66;border-radius:10px;padding:12px 14px;margin:10px 0}
.card h3{margin:0 0 4px;font-size:17px}.meta{font-size:13px;opacity:.8}.body{margin:8px 0 0;white-space:normal}
ul.l{padding-left:18px;margin:6px 0}.foot{margin-top:22px;font-size:13px;opacity:.75}
"""

def page(title, desc, canon, body, crumbs, lastmod=None):
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]}
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<meta property="og:locale" content="ko_KR">
<meta property="og:image" content="{ROOT}og-image.png">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>
<style>{CSS}</style>
</head>
<body>
<main class="w">
<div class="nav">{' › '.join(f'<a href="{e(u)}">{e(n)}</a>' for n, u in crumbs[:-1])}{' › ' if len(crumbs) > 1 else ''}{e(crumbs[-1][0])}</div>
{body}
<a class="cta" href="{ROOT}#boardsec">🍚 맛집 게시판에서 글 쓰기·더 보기</a>
<a class="cta" href="{ROOT}">🎵 {SITE} 듣기</a>
<p class="foot">{SITE}의 '지역별 맛집 자유게시판'에 이용자가 남긴 글입니다. 영업시간·가격 등은 방문 전에 확인하세요.</p>
</main>
</body>
</html>
"""

def fetch_board(path):
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with urllib.request.urlopen(DB + "/board.json", timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def card(p, link=True):
    where = " ".join(x for x in (p.get("g"), p.get("dn")) if x)
    head = f'<a href="/matjip/p/{e(p["id"])}.html">{e(p["s"])}</a>' if link else e(p["s"])
    bits = [x for x in (e(where), "추천: " + e(p.get("f")) if p.get("f") else "", e(p.get("c"))) if x]
    return (f'<article class="card"><h3>{head}</h3><div class="meta">{" · ".join(bits)}</div>'
            f'<p class="body"><b>{e(p["t"])}</b><br>{e(clip(p.get("b"), 140) if link else "").replace(chr(10), "<br>")}</p></article>')

def main():
    src = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else None
    try:
        raw = fetch_board(src)
    except Exception as ex:
        print("게시판을 불러오지 못해 기존 페이지를 그대로 둡니다:", ex)
        sys.exit(1)
    posts = []
    for k, v in (raw or {}).items():
        if isinstance(v, dict) and v.get("t") and v.get("s") and v.get("r") in REGIONS:
            v = dict(v); v["id"] = k; v["ts"] = int(v.get("ts") or 0); posts.append(v)
    if not posts:
        print("보여줄 글이 없어 기존 페이지를 그대로 둡니다.")
        return
    posts.sort(key=lambda p: p["ts"], reverse=True)

    out = "matjip"
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out + "/p")
    urls = [(ROOT, datetime.now(KST).strftime("%Y-%m-%d"), "weekly", "1.0")]
    day = lambda ts: datetime.fromtimestamp(ts / 1000, KST).strftime("%Y-%m-%d") if ts else datetime.now(KST).strftime("%Y-%m-%d")
    by = {}
    for p in posts:
        by.setdefault(p["r"], []).append(p)

    # 글 하나당 페이지
    for p in posts:
        slug, full = REGIONS[p["r"]]
        where = " ".join(x for x in (p.get("g"), p.get("dn")) if x) or full
        title = clip(f'{p["s"]} - {where} {p.get("f") or ""} 맛집', 44) + f" | {SITE}"
        desc = clip(f'{where} {p["s"]}. 추천 음식: {p.get("f") or "-"}. {p.get("b") or ""}', 150)
        m = safe_map(p.get("m"))
        body = (f'<h1>{e(p["s"])}</h1><div class="meta">{e(full)} {e(where)} · {e(p.get("c") or "")} · {day(p["ts"])}</div>'
                f'<h2>{e(p["t"])}</h2><p>{e(p.get("b")).replace(chr(10), "<br>")}</p>'
                f'<p><b>추천 음식</b>: {e(p.get("f"))}<br><b>주소</b>: {e(full)} {e(where)} {e(p.get("a"))}</p>'
                + (f'<p><a href="{e(m)}" target="_blank" rel="nofollow ugc noopener noreferrer">🗺 지도에서 보기</a></p>' if m else "")
                + f'<p><a href="/matjip/{slug}/">{e(full)} 맛집 더 보기</a></p>')
        crumbs = [(SITE, ROOT), ("맛집 게시판", ROOT + "matjip/"), (f"{full} 맛집", f"{ROOT}matjip/{slug}/"), (p["s"], f'{ROOT}matjip/p/{p["id"]}.html')]
        with open(f'{out}/p/{p["id"]}.html', "w", encoding="utf-8") as f:
            f.write(page(title, desc, crumbs[-1][1], body, crumbs))
        urls.append((crumbs[-1][1], day(p["ts"]), "monthly", "0.5"))

    # 지역별 목록
    for r, lst in by.items():
        slug, full = REGIONS[r]
        os.makedirs(f"{out}/{slug}", exist_ok=True)
        title = f"{full} 맛집 추천 {len(lst)}곳 - 지역별 맛집 자유게시판 | {SITE}"
        names = ", ".join(p["s"] for p in lst[:6])
        desc = clip(f"{full} 맛집 이용자 추천 {len(lst)}곳: {names} 등. 추천 음식과 주소를 확인하세요.", 150)
        body = (f"<h1>{e(full)} 맛집 추천</h1><p>{SITE} 맛집 게시판에 이용자가 올린 {e(full)} 맛집 {len(lst)}곳입니다.</p>"
                + "".join(card(p) for p in lst))
        crumbs = [(SITE, ROOT), ("맛집 게시판", ROOT + "matjip/"), (f"{full} 맛집", f"{ROOT}matjip/{slug}/")]
        with open(f"{out}/{slug}/index.html", "w", encoding="utf-8") as f:
            f.write(page(title, desc, crumbs[-1][1], body, crumbs))
        urls.append((crumbs[-1][1], day(max(p["ts"] for p in lst)), "weekly", "0.7"))

    # 전국 모음
    links = "".join(f'<li><a href="/matjip/{REGIONS[r][0]}/">{e(REGIONS[r][1])} 맛집</a> ({len(by[r])}곳)</li>'
                    for r in REGIONS if r in by)
    body = (f"<h1>지역별 맛집 자유게시판 · 전국 맛집 모음</h1><p>{SITE}을 듣는 사람들이 직접 추천한 동네 맛집입니다. 지역을 골라 보세요.</p>"
            f'<ul class="l">{links}</ul><h2>최근 올라온 맛집</h2>' + "".join(card(p) for p in posts[:20]))
    crumbs = [(SITE, ROOT), ("맛집 게시판", ROOT + "matjip/")]
    desc = clip(f"{SITE} 지역별 맛집 자유게시판 — 전국 맛집 {len(posts)}곳. 서울·부산·경북 등 지역별 이용자 추천 맛집과 추천 음식.", 150)
    with open(f"{out}/index.html", "w", encoding="utf-8") as f:
        f.write(page(f"지역별 맛집 자유게시판 · 전국 맛집 추천 | {SITE}", desc, crumbs[-1][1], body, crumbs))
    urls.append((crumbs[-1][1], day(posts[0]["ts"]), "daily", "0.8"))

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for loc, lm, cf, pr in urls:
            f.write(f"  <url><loc>{e(loc)}</loc><lastmod>{lm}</lastmod><changefreq>{cf}</changefreq><priority>{pr}</priority></url>\n")
        f.write("</urlset>\n")
    print(f"완료: 글 {len(posts)}개, 지역 {len(by)}곳, 페이지 {len(urls)}개")

if __name__ == "__main__":
    main()
