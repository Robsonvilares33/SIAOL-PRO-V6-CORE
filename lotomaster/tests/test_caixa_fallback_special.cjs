'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function normalizeIndicator(indicator) {
  const raw = {
    numero: 3088,
    dataApuracao: '19/11/2026',
    listaDezenas: ['10', '21', '24', '28', '34', '44'],
    dezenasSorteadasOrdemSorteio: ['34', '44', '21', '10', '28', '24'],
    indicadorConcursoEspecial: indicator,
    tipoJogo: 'MEGA_SENA',
  };
  const context = vm.createContext({
    window: {},
    localStorage: { getItem: () => null, setItem() {} },
    AbortController, URLSearchParams, setTimeout, clearTimeout,
    fetch: async () => ({ ok: true, json: async () => raw }),
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
