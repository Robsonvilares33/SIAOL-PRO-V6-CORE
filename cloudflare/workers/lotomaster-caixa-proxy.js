const CAIXA_BASE = 'https://servicebus2.caixa.gov.br/portaldeloterias/api';
const ALLOWED_ORIGINS = new Set([
  'https://lotomaster-public-v6.vercel.app',
  'https://lotomaster-public-v6-i5km6c5vs-robsonvilares-projects.vercel.app',
]);
const ALLOWED_GAMES = new Set([
  'megasena', 'lotofacil', 'lotomania', 'quina', 'diadesorte',
  'duplasena', 'timemania', 'supersete', 'maismilionaria',
]);

function corsHeaders(origin) {
  const headers = new Headers({
    'Content-Type': 'application/json; charset=utf-8',
    'X-Content-Type-Options': 'nosniff',
    'Vary': 'Origin',
  });
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    headers.set('Access-Control-Allow-Origin', origin);
    headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
    headers.set('Access-Control-Allow-Headers', 'Accept, Content-Type');
    headers.set('Access-Control-Max-Age', '600');
  }
  return headers;
}

function jsonReply(request, payload, status, extraHeaders = {}) {
  const origin = request.headers.get('Origin') || '';
  const headers = corsHeaders(origin);
  for (const [name, value] of Object.entries(extraHeaders)) headers.set(name, value);
  headers.set('Cache-Control', 'no-store');
  return new Response(JSON.stringify(payload), { status, headers });
}

function corsResponse(response, origin) {
  const headers = new Headers(response.headers);
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    headers.set('Access-Control-Allow-Origin', origin);
    headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
    headers.set('Access-Control-Allow-Headers', 'Accept, Content-Type');
    headers.set('Access-Control-Max-Age', '600');
    headers.set('Vary', 'Origin');
  }
  return new Response(response.body, { status: response.status, headers });
}

async function handle(request, event) {
  const origin = request.headers.get('Origin') || '';
  if (origin && !ALLOWED_ORIGINS.has(origin)) {
    return jsonReply(request, { error: 'origin_not_allowed' }, 403);
  }
  if (request.method === 'OPTIONS') {
    if (!origin || !ALLOWED_ORIGINS.has(origin)) return new Response(null, { status: 403 });
    return new Response(null, { status: 204, headers: corsHeaders(origin) });
  }
  if (request.method !== 'GET') {
    return jsonReply(request, { error: 'method_not_allowed' }, 405, { Allow: 'GET, OPTIONS' });
  }

  const url = new URL(request.url);
  if (url.search) return jsonReply(request, { error: 'query_not_allowed' }, 400);
  const parts = url.pathname.split('/').filter(Boolean);
  if (parts.length < 1 || parts.length > 2) return jsonReply(request, { error: 'not_found' }, 404);
  const [game, contest] = parts;
  if (!ALLOWED_GAMES.has(game)) return jsonReply(request, { error: 'game_not_allowed' }, 404);
  if (contest && !/^[1-9][0-9]{0,4}$/.test(contest)) {
    return jsonReply(request, { error: 'invalid_contest' }, 400);
  }

  const endpoint = `${game}${contest ? `/${contest}` : ''}`;
  const ttl = contest ? 86400 : 60;
  const cacheKey = new Request(`https://lotomaster-caixa-cache.invalid/${endpoint}`);
  try {
    const cached = await caches.default.match(cacheKey);
    if (cached) return corsResponse(cached, origin);
  } catch (_) {
    // Continue without cache if the runtime cache is unavailable.
  }

  let upstream;
  try {
    upstream = await fetch(`${CAIXA_BASE}/${endpoint}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Origin': 'https://loterias.caixa.gov.br',
        'Referer': 'https://loterias.caixa.gov.br/',
        'User-Agent': 'Mozilla/5.0 (compatible; Lotomaster/1.1; official results read-only)',
      },
    });
  } catch (_) {
    return jsonReply(request, { error: 'caixa_unreachable' }, 502);
  }
  if (!upstream.ok) {
    return jsonReply(request, { error: 'caixa_upstream_error', upstream_status: upstream.status }, 502);
  }
  const contentType = upstream.headers.get('Content-Type') || '';
  if (!contentType.toLowerCase().includes('json')) {
    return jsonReply(request, { error: 'caixa_non_json_response', upstream_status: upstream.status }, 502);
  }
  const body = await upstream.text();
  let data;
  try { data = JSON.parse(body); } catch (_) {
    return jsonReply(request, { error: 'caixa_invalid_json' }, 502);
  }
  if (!data || !data.numero) return jsonReply(request, { error: 'caixa_invalid_draw' }, 502);

  const stored = new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': `public, max-age=${ttl}`,
      'X-Content-Type-Options': 'nosniff',
    },
  });
  try { event.waitUntil(caches.default.put(cacheKey, stored.clone())); } catch (_) { /* Cache opcional */ }
  return corsResponse(stored, origin);
}

addEventListener('fetch', event => event.respondWith(handle(event.request, event)));
