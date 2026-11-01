<?php
// jin_news.php — "이진주방산업" 구글 뉴스 중계 (jin_rss.php, jin_ai.php 와 같은 폴더에 올리세요)
// 사용법: jin_news.php  →  {"items":[{"id","title","link","source","date"}...]}
// 사이트가 20초마다 불러도 구글에는 120초에 한 번만 요청합니다 (캐시 파일 사용).

$QUERY        = '이진주방산업';
$CACHE_SEC    = 120;
$ALLOW_ORIGIN = '*';   // 보안을 높이려면 'https://dyeo880-sys.github.io' 로 제한

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: ' . $ALLOW_ORIGIN);
header('Cache-Control: no-store');

$cf = __DIR__ . '/jin_news_cache.json';
if (is_file($cf) && time() - filemtime($cf) < $CACHE_SEC) { readfile($cf); exit; }

$url = 'https://news.google.com/rss/search?q=' . rawurlencode($QUERY) . '&hl=ko&gl=KR&ceid=KR:ko';
$xml = false;
foreach ([true, false] as $verify) {
  if (!function_exists('curl_init')) break;
  $ch = curl_init($url);
  curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 15, CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_USERAGENT => 'Mozilla/5.0', CURLOPT_SSL_VERIFYPEER => $verify]);
  $xml = curl_exec($ch); $st = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
  if ($xml !== false && $st >= 200 && $st < 300) break;
  $xml = false;
}
if ($xml === false) {   // 실패하면 낡은 캐시라도 보여줌
  if (is_file($cf)) { readfile($cf); exit; }
  echo json_encode(['items' => [], 'error' => 'fetch'], JSON_UNESCAPED_UNICODE); exit;
}

$items = [];
$x = @simplexml_load_string($xml);
if ($x && isset($x->channel->item)) {
  foreach ($x->channel->item as $it) {
    $items[] = [
      'id'     => (string)$it->guid ?: (string)$it->link,
      'title'  => trim((string)$it->title),
      'link'   => trim((string)$it->link),
      'source' => trim((string)$it->source),
      'date'   => (string)$it->pubDate,
    ];
    if (count($items) >= 10) break;
  }
}
$out = json_encode(['items' => $items, 'ts' => time()], JSON_UNESCAPED_UNICODE);
if ($items) @file_put_contents($cf, $out, LOCK_EX);
echo $out;
