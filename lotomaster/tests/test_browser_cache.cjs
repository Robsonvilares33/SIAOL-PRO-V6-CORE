// Offline regression tests: node lotomaster/tests/test_browser_cache.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const cache = new Map();
const localStorage = {getItem: k => cache.get(k) || null, setItem: (k,v) => cache.set(k,v)};
let online = true;
let missingHistorical = false;
async function fetchMock(url, opts={}) {
  if (url.startsWith('/api/')) return {ok:true, json:async()=>({draws_analyzed:1})};
  if (!online) throw new Error('offline');
  const parts = url.split('/');
  const n = Number(parts.at(-1)) || 100;
  // Force historical requests to finish out of order.
  if (n !== 100) await new Promise(resolve => setTimeout(resolve, n === 99 ? 12 : 1));
  if (missingHistorical && n === 99) throw new Error('missing');
  return {ok:true,json:async()=>({numero:n,listaDezenas:['1','2','3','4','5','6']})};
}
const window = {};
const ctx = vm.createContext({window, localStorage, fetch:fetchMock, URLSearchParams, AbortController, setTimeout, clearTimeout, console});
const staticDir = path.join(__dirname, '..', 'static');
vm.runInContext(fs.readFileSync(path.join(staticDir, 'caixa-fallback.js'), 'utf8'), ctx);
(async () => {
  const fallback = window.lotomasterCaixaFallback;
  cache.set('lotomaster:caixa:latest:megasena', JSON.stringify({game:'megasena',contest:1,numbers:[1]}));
  await assert.rejects(async () => { online=false; await fallback('/megasena/latest'); }, /offline/);
  online=true;
  const history = await fallback('/megasena/results?limit=3');
  assert.deepEqual(Array.from(history.items, x=>x.contest), [100,99,98]);
  assert.equal(JSON.parse(cache.get('lotomaster:caixa:latest:v2:megasena')).contest,100);
  online=false;
  const stale = await fallback('/megasena/latest');
  assert.equal(stale.contest, 100);
  assert.match(stale.warning, /offline/);
  assert.match(stale.source, /cache/);
  const staleHistory = await fallback('/megasena/results?limit=3');
  assert.match(staleHistory.warning, /desatualizado/);
  assert.equal(staleHistory.items[0].contest, 100);
  const stats = await fallback('/megasena/statistics?limit=3');
  assert.match(stats.warning, /desatualizado/);
  cache.delete('lotomaster:caixa:history:megasena');
  online=true; missingHistorical=true;
  const partial = await fallback('/megasena/results?limit=3');
  assert.equal(partial.partial,true);
  assert.equal(partial.expected_count,3);
  assert.equal(partial.count,2);
  assert.equal(partial.warning,null);
  const appSource=fs.readFileSync(path.join(staticDir,'app.js'),'utf8');
  // Exercise the actual simulator rendering in a minimal DOM.
  const result = {innerHTML:''};
  const input = {value:'1 2 3 4 7 8'};
  const appCtx = vm.createContext({window:{addEventListener:()=>{}},document:{querySelector:s=>({'#sim-result':result,'#sim-numbers':input}[s]),querySelectorAll:()=>[],addEventListener:()=>{}},console,setTimeout,clearTimeout});
  vm.runInContext(appSource.replace(/init\(\);\s*$/, ''), appCtx);
  vm.runInContext(`state.catalog=[{key:'megasena',name:'Mega-Sena',digits:2,pick_size:6,min_pick:6,max_pick:20,range:{minimum:1,maximum:60}}]; state.game='megasena'; state.page='simulator'; api=async (path,options)=>path.endsWith('/latest')?{game:'megasena',contest:100,numbers:[1,2,3,4,5,6],source:'cache local do navegador',warning:'offline'}:(request=>({contest:100,draw_date:'',draw:request.draw,results:[{ticket_number:1,main_hits:4,award:'4 acertos'}],provenance:{description:'Resultado fornecido pelo cliente; o servidor não verificou sua origem nem autenticidade.'}}))(JSON.parse(options.body))`,appCtx);
  await vm.runInContext('handleSimulate({preventDefault(){}})',appCtx);
  assert.match(result.innerHTML,/não verificada/i);
  assert.match(result.innerHTML,/offline/);
  assert.match(result.innerHTML,/pode estar desatualizado/);
  assert.match(result.innerHTML,/servidor não verificou/);
  assert.doesNotMatch(result.innerHTML,/>Oficial</);
  console.log('OK: browser latest, legacy cache, out-of-order history, offline warning, partial data, statistics and simulator rendering');
})().catch(error => { console.error(error); process.exitCode=1; });
