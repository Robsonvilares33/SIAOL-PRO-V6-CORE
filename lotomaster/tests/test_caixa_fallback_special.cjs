'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

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
});
