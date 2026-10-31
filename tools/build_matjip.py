#!/usr/bin/env python3
"""맛집 게시판 글을 검색용 정적 페이지(/matjip/)로 만든다.

데이터 출처 (위에서부터 먼저 되는 것 사용)
 1) 환경변수 MATJIP_DATA_URL : JSON을 돌려주는 주소 (예: Firebase Realtime DB .json 주소)
 2) data/matjip.json         : 저장소 안의 JSON 파일

글이 하나도 없어도 오류로 멈추지 않고, 실행 기록에 [진단] 줄을 남긴다.
"""
import datetime
import html
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

SITE = "https://dyeo880-sys.github.io"
SITE_NAME = "Radiola 웹 라디오"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "matjip"
LOCAL = ROOT / "data" / "matjip.json"
DATA_URL = os.environ.get("MATJIP_DATA_URL", "").strip()
TODAY = datetime.date.today().isoformat()

REGION_ALIAS = {
    "경상북도": "경북", "경상남도": "경남", "전라북도": "전북", "전라남도": "전남",
    "충청북도": "충북", "충청남도": "충남", "강원특별자치도": "강원", "강원도": "강원",
    "제주특별자치도": "제주", "제주도": "제주",
}

KEYS = {
    "title": ["title", "name", "store", "shop", "제목", "가게", "상호"],
    "region": ["region", "area", "city", "지역"],
    "body": ["content", "body", "desc", "description", "text", "내용", "설명"],
    "address": ["address", "addr", "주소"],
    "phone": ["phone", "tel", "전화", "연락처"],
    "menu": ["menu", "메뉴"],
    "hours": ["hours", "영업시간"],
    "date": ["date", "createdAt", "created", "time", "작성일"],
}


def log(msg):
    print(msg, flush=True)


def fetch_json():
    if DATA_URL:
        try:
            req = urllib.request.Request(DATA_URL, headers={"User-Agent": "matjip-builder"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8")), "URL"
        except Exception as e:  # noqa: BLE001
            log(f"[진단] 게시판 주소를 불러오지 못했습니다: {e}")
    if LOCAL.exists():
        try:
            return json.loads(LOCAL.read_text(encoding="utf-8")), "파일"
        except Exception as e:  # noqa: BLE001
            log(f"[진단] data/matjip.json 읽기 실패: {e}")
    return None, "없음"


def as_items(data):
    items = []
    if isinstance(data, dict):
        # {"posts": {...}} 같은 한 겹 감싸기도 허용
        if len(data) == 1 and isinstance(next(iter(data.values())), (dict, list)):
            inner = next(iter(data.values()))
            if isinstance(inner, list) or (
                isinstance(inner, dict) and all(isinstance(v, dict) for v in inner.values())
            ):
                data = inner
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    v = dict(v)
                    v.setdefault("_id", k)
                    items.append(v)
    if isinstance(data, list):
        for i, v in enumerate(data):
            if isinstance(v, dict):
                v = dict(v)
                v.setdefault("_id", str(i))
                items.append(v)
    return items


def pick(d, name):
    for k in KEYS[name]:
        v = d.get(k)
        if v not in (None, ""):
            if isinstance(v, (list, tuple)):
                v = ", ".join(str(x) for x in v)
            return str(v).strip()
    return ""


def norm_region(r):
    r = (r or "").strip()
    return REGION_ALIAS.get(r, r) or "기타"


def slug(text):
    s = re.sub(r"[\\/:*?\"<>|#%\s]+", "-", text).strip("-")
    return s or "etc"


def e(s):
    return html.escape(s or "", quote=True)


def short(text, n=110):
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


CSS = """
body{font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif;margin:0;color:#222;line-height:1.7;background:#fafafa}
header,main,footer{max-width:760px;margin:0 auto;padding:16px}
header a{color:#222;text-decoration:none;font-weight:700}
h1{font-size:1.5rem;margin:.6em 0}
ul{padding-left:1.2em} li{margin:.4em 0}
a{color:#0b57d0}
.card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:14px 16px;margin:12px 0}
.meta{color:#555;font-size:.95rem}
footer{color:#777;font-size:.85rem}
"""


def page(title, desc, path, body, jsonld=None):
    url = f"{SITE}{path}"
    ld = ""
    if jsonld:
        ld = '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False) + "</script>"
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:type" content="website">
<style>{CSS}</style>
{ld}
</head>
<body>
<header><a href="/">{e(SITE_NAME)}</a> · <a href="/matjip/">맛집</a></header>
<main>
{body}
</main>
<footer>© {e(SITE_NAME)}</footer>
</body>
</html>
"""


def breadcrumb(parts):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + p}
            for i, (n, p) in enumerate(parts)
        ],
    }


def write(path_url, content):
    rel = urllib.parse.unquote(path_url).strip("/")
    f = ROOT / rel / "index.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")


def main():
    data, source = fetch_json()
    items = as_items(data) if data is not None else []
    log(f"[진단] 데이터 출처={source}, 읽은 항목 {len(items)}개")

    posts = []
    for it in items:
        title = pick(it, "title")
        if not title:
            continue
        posts.append({
            "id": slug(str(it.get("_id", title))),
            "title": title,
            "region": norm_region(pick(it, "region")),
            "body": pick(it, "body"),
            "address": pick(it, "address"),
            "phone": pick(it, "phone"),
            "menu": pick(it, "menu"),
            "hours": pick(it, "hours"),
        })
    regions = sorted({p["region"] for p in posts})
    log(f"[진단] 쓸 수 있는 글 {len(posts)}개, 지역값 목록: {regions}")

    urls = []
    if not posts:
        log("[진단] 만들 글이 없어 /matjip/ 은 만들지 않습니다. (오류 아님)")
        update_sitemap([])
        return 0

    # 오래된 결과 지우기
    if OUT.exists():
        for p in sorted(OUT.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
    OUT.mkdir(exist_ok=True)

    # 글 페이지
    for p in posts:
        path = f"/matjip/p/{p['id']}/"
        rpath = f"/matjip/{urllib.parse.quote(slug(p['region']))}/"
        lines = []
        if p["address"]:
            lines.append(f"<li>주소: {e(p['address'])}</li>")
        if p["phone"]:
            lines.append(f"<li>전화: {e(p['phone'])}</li>")
        if p["hours"]:
            lines.append(f"<li>영업시간: {e(p['hours'])}</li>")
        if p["menu"]:
            lines.append(f"<li>메뉴: {e(p['menu'])}</li>")
        info = f"<ul>{''.join(lines)}</ul>" if lines else ""
        text = "".join(f"<p>{e(s)}</p>" for s in p["body"].split("\n") if s.strip())
        body = (
            f'<p class="meta"><a href="/matjip/">맛집</a> › <a href="{rpath}">{e(p["region"])}</a></p>'
            f"<h1>{e(p['region'])} {e(p['title'])}</h1>{info}{text}"
        )
        ld = {"@context": "https://schema.org", "@type": "Restaurant", "name": p["title"]}
        if p["address"]:
            ld["address"] = p["address"]
        if p["phone"]:
            ld["telephone"] = p["phone"]
        title = f"{p['region']} {p['title']} - 맛집 | {SITE_NAME}"
        desc = short(p["body"] or f"{p['region']} {p['title']} 맛집 정보")
        write(path, page(title, desc, path, body, [ld, breadcrumb([
            ("맛집", "/matjip/"), (p["region"], rpath), (p["title"], path)])]))
        urls.append(path)

    # 지역 페이지
    for r in regions:
        rpath = f"/matjip/{urllib.parse.quote(slug(r))}/"
        li = "".join(
            f'<li><a href="/matjip/p/{p["id"]}/">{e(p["title"])}</a></li>'
            for p in posts if p["region"] == r
        )
        body = f'<p class="meta"><a href="/matjip/">맛집</a> › {e(r)}</p><h1>{e(r)} 맛집 모음</h1><ul>{li}</ul>'
        write(rpath, page(f"{r} 맛집 모음 | {SITE_NAME}", f"{r} 지역 맛집 목록입니다.", rpath, body,
                          breadcrumb([("맛집", "/matjip/"), (r, rpath)])))
        urls.append(rpath)

    # 목록 페이지
    sections = ""
    for r in regions:
        rpath = f"/matjip/{urllib.parse.quote(slug(r))}/"
        li = "".join(
            f'<li><a href="/matjip/p/{p["id"]}/">{e(p["title"])}</a></li>'
            for p in posts if p["region"] == r
        )
        sections += f'<div class="card"><h2><a href="{rpath}">{e(r)}</a></h2><ul>{li}</ul></div>'
    body = f"<h1>지역별 맛집 목록</h1>{sections}"
    write("/matjip/", page(f"지역별 맛집 목록 | {SITE_NAME}", "지역별 맛집을 한곳에서 확인하세요.",
                           "/matjip/", body, breadcrumb([("맛집", "/matjip/")])))
    urls.insert(0, "/matjip/")

    update_sitemap(urls)
    log(f"완료: 글 {len(posts)}개, 페이지 {len(urls)}개")
    return 0


def update_sitemap(matjip_urls):
    sm = ROOT / "sitemap.xml"
    keep = []
    if sm.exists():
        for loc in re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8")):
            if "/matjip/" not in loc:
                keep.append(loc)
    if not keep:
        keep = [SITE + "/"]
    rows = []
    for loc in keep + [SITE + u for u in matjip_urls]:
        rows.append(f"<url><loc>{html.escape(loc)}</loc><lastmod>{TODAY}</lastmod></url>")
    sm.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows) + "\n</urlset>\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    sys.exit(main())
