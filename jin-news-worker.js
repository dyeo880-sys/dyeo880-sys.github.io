// Cloudflare Worker "jin-news": 이진주방산업 소식을 한곳에 모아 JSON으로 돌려줍니다 (120초 캐시)
//  1) 이진주방산업 티스토리 블로그 새 글 (src: blog)  ← 핵심
//  2) 구글 뉴스 "이진주방산업" 기사 (src: news)       ← 보조
// 카드·API 키 필요 없음. Worker 이름은 jin-news 로 만드세요.

const BLOG_RSS = ['https://010-4273-1972.tistory.com/rss'];   // 블로그가 더 있으면 여기에 주소를 추가
const QUERY = '이진주방산업';
const MUST = '이진주방';   // 구글 뉴스에서 제목·설명에 이 글자가 있는 기사만 통과 (비슷한 이름의 다른 회사 걸러내기)
const CACHE_SECONDS = 120;
const cors = { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json; charset=utf-8' };

const decode = s => s.replace(/<!\[CDATA\[|\]\]>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').trim();
const pick = (b, tag) => { const m = b.match(new RegExp('<' + tag + '[^>]*>([\\s\\S]*?)</' + tag + '>')); return m ? decode(m[1]) : ''; };
const getXml = async u => { const r = await fetch(u, { headers: { 'User-Agent': 'Mozilla/5.0' } }); if (!r.ok) throw new Error(r.status); return r.text(); };

async function readBlog(u) {
  const xml = await getXml(u), out = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const b = m[1], title = pick(b, 'title');
    if (!title) continue;
    out.push({ id: pick(b, 'guid') || pick(b, 'link'), src: 'blog', title, link: pick(b, 'link'), source: '이진주방산업 블로그', date: pick(b, 'pubDate') });
    if (out.length >= 10) break;
  }
  return out;
}
async function readNews() {
  const xml = await getXml('https://news.google.com/rss/search?q=' + encodeURIComponent('"' + QUERY + '"') + '&hl=ko&gl=KR&ceid=KR:ko'), out = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const b = m[1], title = pick(b, 'title');
    if (!(title + ' ' + pick(b, 'description')).includes(MUST)) continue;
    out.push({ id: pick(b, 'guid') || pick(b, 'link'), src: 'news', title, link: pick(b, 'link'), source: pick(b, 'source'), date: pick(b, 'pubDate') });
    if (out.length >= 10) break;
  }
  return out;
}

export default {
  async fetch(request, env, ctx) {
    const cache = caches.default;
    const key = new Request(new URL(request.url).origin + '/news-cache');
    const hit = await cache.match(key);
    if (hit) return new Response(hit.body, { headers: cors });

    const jobs = [...BLOG_RSS.map(readBlog), readNews()];
    const res = await Promise.allSettled(jobs);
    let items = [], ok = 0;
    res.forEach(r => { if (r.status === 'fulfilled') { ok++; items = items.concat(r.value); } });
    if (!ok) return new Response(JSON.stringify({ items: [], error: 'fetch failed' }), { headers: cors });
    items.sort((a, b) => (Date.parse(b.date) || 0) - (Date.parse(a.date) || 0));

    const out = new Response(JSON.stringify({ items: items.slice(0, 20), ts: Date.now() }), { headers: { ...cors, 'Cache-Control': 'public, max-age=' + CACHE_SECONDS } });
    ctx.waitUntil(cache.put(key, out.clone()));
    return out;
  },
};
