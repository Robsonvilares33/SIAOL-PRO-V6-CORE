'use strict';
// Sem rede: fallback real e interface simulada; /simulate ASGI via subprocesso.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const dir = path.join(__dirname, '..', 'static');
function bridge(payload) {
  const p = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname,'simulate_bridge.py')], {input:JSON.stringify(payload),encoding:'utf8'});
  assert.equal(p.status,0,p.stderr); return JSON.parse(p.stdout);
}
async function fallback(raw) {
  const store=new Map(); const window={};
  const ctx=vm.createContext({window,fetch:async()=>({ok:true,json:async()=>raw}),localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)}, URLSearchParams,AbortController,setTimeout,clearTimeout,console});
  vm.runInContext(fs.readFileSync(path.join(dir,'caixa-fallback.js'),'utf8'),ctx);
  return window.lotomasterCaixaFallback('/maismilionaria/latest');
}
test('fallback com oito valores separados e conferidos no ASGI real',async()=>{
  for (const raw of [
    {numero:407,dezenasSorteadasOrdemSorteio:['9','22','25','26','28','50','2','3']},
    {numero:407,listaDezenas:['9','22','25','26','28','50','2','3']},
    {numero:407,listaDezenas:['9','22','25','26','28','50'],trevosSorteados:['2','3']},
  ]) {
    const draw=await fallback(raw);
    assert.deepEqual(Array.from(draw.numbers),[9,22,25,26,28,50]);
    assert.deepEqual(Array.from(draw.trevos),[2,3]);
    const response=bridge({draw,tickets:[{numbers:[9,22,1,2,3,4],bonus:{trevos:[2,4]}}]});
    assert.equal(response.status,200,JSON.stringify(response.body));
    assert.equal(response.body.results[0].award,'Faixa 10 · 2 acertos + 1 trevo');
  }
});

test('fallback rejeita números malformados em vez de convertê-los silenciosamente',async()=>{
 await assert.rejects(fallback({numero:407,listaDezenas:['1x','22','25','26','28','50'],trevosSorteados:['2','3']}),/Dezena inválida/);
});

async function batchTickets(input) {
 const fields={'#batch-from':{value:'1'},'#batch-to':{value:'1'},'#batch-numbers':{value:input},'#batch-status':{textContent:''},'#batch-result':{innerHTML:''},'#batch-bonus-override':{checked:false}};
 const submitter={disabled:false,isConnected:true};
 const document={querySelector:s=>s==='#batch-submit'?submitter:fields[s]||null,querySelectorAll:()=>[]};
 const ctx=vm.createContext({window:{addEventListener(){}},document,console,setTimeout,clearTimeout,AbortController,URLSearchParams});
 vm.runInContext(fs.readFileSync(path.join(dir,'app.js'),'utf8'),ctx);
 vm.runInContext("state.catalog=[{key:'supersete',name:'Super Sete',digits:1,pick_size:7,min_pick:7,max_pick:7,draw_size:7,range:{minimum:0,maximum:9}}];state.game='supersete';state.page='simulator';state.simulatorText='1 2 3 4 5 6 7';state.simulatorTickets=[{numbers:[1,2,3,4,5,6,7],columns:[[1,8],[2],[3],[4],[5],[6],[7]],bonus:{},ticket_number:1}]",ctx);
 ctx.loadHistoryRange=async()=>[];
 ctx.simulateHistoryInChunks=async(_game,tickets)=>{ctx.capturedTickets=JSON.parse(JSON.stringify(tickets));return {results:[]};};
 ctx.renderHistorySimulation=()=>{};
 await vm.runInContext('handleHistoryBatch({preventDefault(){},submitter:document.querySelector("#batch-submit")})',ctx);
 return ctx.capturedTickets;
}

test('checker em lote preserva detalhes Super Sete só quando os números parseados não mudam',async()=>{
 const formatted=await batchTickets('1   2 3 4 5 6 7');
 assert.deepEqual(Array.from(formatted[0].columns[0]),[1,8]);
 const changedDigit=await batchTickets('8 2 3 4 5 6 7');
 assert.deepEqual(Array.from(changedDigit[0].columns[0]),[8]);
 const changedOrder=await batchTickets('2 1 3 4 5 6 7');
 assert.deepEqual(Array.from(changedOrder[0].columns[0]),[2]);
 assert.deepEqual(Array.from(changedOrder[0].columns[1]),[1]);
});

test('jogos gerados preservam trevos individuais, edição aplica a todos e limpar é rejeitado',async()=>{
  const fields={'#sim-numbers':{value:'01 02 03 04 05 06\n07 08 09 10 11 12'},'#sim-trevos':{value:'1, 2'},'#sim-bonus-override':{checked:false},'#sim-result':{innerHTML:''}};
  const document={querySelector:s=>fields[s],querySelectorAll:()=>[]};
  const ctx=vm.createContext({window:{addEventListener(){}},document,console,setTimeout,clearTimeout});
  vm.runInContext(fs.readFileSync(path.join(dir,'app.js'),'utf8'),ctx);
  ctx.sent=[];
  vm.runInContext(`state.catalog=[{key:'maismilionaria',name:'+Milionária',digits:2,pick_size:6,min_pick:6,max_pick:6,range:{minimum:1,maximum:50},bonus:{type:'trevos'}}]; state.game='maismilionaria';state.page='simulator';
  state.simulatorText='01 02 03 04 05 06\\n07 08 09 10 11 12';
  state.simulatorBonus={trevos:[1,2]}; state.simulatorTickets=[{numbers:[1,2,3,4,5,6],bonus:{trevos:[1,2]}},{numbers:[7,8,9,10,11,12],bonus:{trevos:[3,4]}}];
  api=async (route,options)=>route.endsWith('/latest')?{game:'maismilionaria',contest:10,numbers:[1,2,3,4,5,6],trevos:[3,4]}:(sent.push(JSON.parse(options.body)), {contest:10,draw:{numbers:[1,2,3,4,5,6],trevos:[3,4]},results:[]});`,ctx);
  await vm.runInContext('handleSimulate({preventDefault(){}})',ctx);
  assert.deepEqual(Array.from(ctx.sent[0].tickets, x=>Array.from(x.bonus.trevos)),[[1,2],[3,4]]);
  fields['#sim-trevos'].value='3, 4';
  fields['#sim-bonus-override'].checked=true;
  await vm.runInContext('handleSimulate({preventDefault(){}})',ctx);
  assert.deepEqual(Array.from(ctx.sent[1].tickets, x=>Array.from(x.bonus.trevos)),[[3,4],[3,4]]);
  const unedited=bridge(ctx.sent[0]); const edited=bridge(ctx.sent[1]);
  assert.equal(unedited.status,200); assert.equal(edited.status,200);
  assert.equal(unedited.body.results[0].trevo_hits,0); assert.equal(edited.body.results[0].trevo_hits,2);
  fields['#sim-trevos'].value='';
  await vm.runInContext('handleSimulate({preventDefault(){}})',ctx);
  assert.equal(ctx.sent.length,2);
  assert.match(fields['#sim-result'].innerHTML,/Informe um bônus válido/);
  assert.match(vm.runInContext("bonusFields({bonus:{type:'trevos'}})",ctx),/2–6 trevos; cada bilhete múltiplo equivale/);
  assert.match(vm.runInContext("bonusFields({bonus:{type:'trevos'}})",ctx),/value="3"/);
});
