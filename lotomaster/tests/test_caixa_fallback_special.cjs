'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/caixa-fallback.js'), 'utf8');
const baseRaw = (numero, overrides = {}) => ({
  numero, dataApuracao: '19/11/2026',
  listaDezenas: ['10', '21', '24', '28', '34', '44'],
  dezenasSorteadasOrdemSorteio: ['34', '44', '21', '10', '28', '24'],
  indicadorConcursoEspecial: 1, tipoJogo: 'MEGA_SENA', ...overrides,
});

async function normalizeIndicator(indicator, overrides = {}, cached = null, failFetch = false) {
  const raw = {
    numero: 3088,
    dataApuracao: '19/11/2026',
    listaDezenas: ['10', '21', '24', '28', '34', '44'],
    dezenasSorteadasOrdemSorteio: ['34', '44', '21', '10', '28', '24'],
    indicadorConcursoEspecial: indicator,
    tipoJogo: 'MEGA_SENA',
    ...overrides,
  };
  const context = vm.createContext({
    window: {},
    localStorage: { getItem: () => cached ? JSON.stringify(cached) : null, setItem() {} },
    AbortController, URLSearchParams, setTimeout, clearTimeout,
    fetch: async () => failFetch ? { ok: false, status: 503 } : ({ ok: true, json: async () => raw }),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/caixa-fallback.js'), 'utf8'), context);
  return context.window.lotomasterCaixaFallback('/megasena/latest');
}

test('fallback CAIXA trata indicador 1 como regular e 2 como especial', async () => {
  assert.equal((await normalizeIndicator(1)).special_draw, false);
  assert.equal((await normalizeIndicator('1')).special_draw, false);
  assert.equal((await normalizeIndicator(2)).special_draw, true);
  assert.equal((await normalizeIndicator('2')).special_draw, true);
});

test('fallback rejeita prêmios não finitos na resposta oficial e no cache local', async () => {
  await assert.rejects(normalizeIndicator(1, { valorEstimadoProximoConcurso: 'Infinity' }), /Valor monetário inválido/);
  await assert.rejects(normalizeIndicator(1, {
    listaRateioPremio: [{ descricaoFaixa: 'Faixa', numeroDeGanhadores: '1', valorPremio: 'NaN' }],
  }), /Rateio de prêmios inválido/);

  const cached = {
    game: 'megasena', contest: 1, numbers: [10, 21, 24, 28, 34, 44],
    second_numbers: [], trevos: [], month: null, team: null,
    estimated_prize: null, next_prize: 0, winners_by_tier: [], special_draw: false,
  };
  await assert.rejects(normalizeIndicator(1, {}, cached, true), /HTTP 503/);
  const excessiveCached = {
    ...cached, estimated_prize: 0,
    winners_by_tier: Array.from({ length: 51 }, () => ({ winners: 0, prize: 0 })),
  };
  await assert.rejects(normalizeIndicator(1, {}, excessiveCached, true), /HTTP 503/);
});

test('rateio aceita até 50 faixas e ausente/vazio, rejeita mais de 50 e formato inválido', async () => {
  const awards = Array.from({ length: 50 }, () => ({ descricaoFaixa: 'Faixa', numeroDeGanhadores: '1', valorPremio: '2' }));
  assert.equal((await normalizeIndicator(1, { listaRateioPremio: awards })).winners_by_tier.length, 50);
  assert.deepEqual(Array.from((await normalizeIndicator(1, { listaRateioPremio: [] })).winners_by_tier), []);
  assert.deepEqual(Array.from((await normalizeIndicator(1, { listaRateioPremio: null })).winners_by_tier), []);
  assert.deepEqual(Array.from((await normalizeIndicator(1)).winners_by_tier), []);
  await assert.rejects(normalizeIndicator(1, { listaRateioPremio: [...awards, awards[0]] }), /Rateio de prêmios inválido/);
  await assert.rejects(normalizeIndicator(1, { listaRateioPremio: { length: 0 } }), /Rateio de prêmios inválido/);
});

test('rateio excessivo não é armazenado nem reutilizado como fallback', async () => {
  const cache = new Map();
  const awards = Array.from({ length: 51 }, () => ({ descricaoFaixa: 'Faixa', numeroDeGanhadores: '1', valorPremio: '2' }));
  let fail = false;
  const context = vm.createContext({
    window: {},
    localStorage: { getItem: key => cache.get(key) ?? null, setItem: (key, value) => cache.set(key, value) },
    AbortController, URLSearchParams, setTimeout, clearTimeout,
    fetch: async () => fail ? { ok: false, status: 503 } : { ok: true, json: async () => baseRaw(3088, { listaRateioPremio: awards }) },
  });
  vm.runInContext(source, context);
  const fallback = context.window.lotomasterCaixaFallback;
  await assert.rejects(fallback('/megasena/latest'), /Rateio de prêmios inválido/);
  assert.equal(cache.has('lotomaster:caixa:latest:v2:megasena'), false);
  fail = true;
  await assert.rejects(fallback('/megasena/latest'), /HTTP 503/);
});

test('histórico preserva concursos concorrentes e mantém resposta estreita', async () => {
  let releaseNarrow;
  const narrowLatest = new Promise(resolve => { releaseNarrow = resolve; });
  let latestCalls = 0;
  const cache = new Map();
  const context = vm.createContext({
    window: {},
    localStorage: { getItem: key => cache.get(key) ?? null, setItem: (key, value) => cache.set(key, value) },
    AbortController, URLSearchParams, setTimeout, clearTimeout,
    fetch: async url => {
      const contest = new URL(url).pathname.split('/').pop();
      if (contest === 'megasena') {
        latestCalls += 1;
        if (latestCalls === 1) return { ok: true, json: async () => baseRaw(100) };
        return narrowLatest;
      }
      return { ok: true, json: async () => baseRaw(Number(contest)) };
    },
  });
  vm.runInContext(source, context);
  const fallback = context.window.lotomasterCaixaFallback;
  const widePromise = fallback('/megasena/results?limit=3');
  const narrowPromise = fallback('/megasena/results?limit=1');
  const wide = await widePromise;
  assert.deepEqual(Array.from(wide.items, row => row.contest), [100, 99, 98]);
  releaseNarrow({ ok: true, json: async () => baseRaw(100) });
  const narrow = await narrowPromise;
  assert.deepEqual(Array.from(narrow.items, row => row.contest), [100]);
  assert.deepEqual(JSON.parse(cache.get('lotomaster:caixa:history:megasena')).map(row => row.contest), [100, 99, 98]);
});
