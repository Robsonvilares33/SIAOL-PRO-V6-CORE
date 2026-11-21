'use strict';
// Testes isolados, sem rede, credenciais ou serviços externos: node --test lotomaster/tests/test_frontend.js
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const staticDir = path.join(__dirname, '..', 'static');
function setup(fetch) {
  const elements = {};
  const document = {querySelector: selector => elements[selector] || null, querySelectorAll: () => []};
  const window = {addEventListener() {}, LotoMasterAI: {}};
  const context = vm.createContext({window, document, fetch, URL, console, setTimeout, clearTimeout});
  vm.runInContext(fs.readFileSync(path.join(staticDir, 'app.js'), 'utf8'), context);
  return {context, elements, window};
}
function response(data) {
  return {ok: true, headers: {get: () => 'application/json'}, json: async () => data};
}
function pages(latest, missing = new Set()) {
  const requests = [];
  const fetch = async url => {
    requests.push(url);
    const parsed = new URL(url, 'http://localhost');
    const before = Number(parsed.searchParams.get('before') || latest + 1);
    const upper = Math.min(latest, before - 1);
    const lower = Math.max(1, upper - 99);
    const items = [], unavailable = [];
    for (let n = upper; n >= lower; n--) {
      if (missing.has(n)) unavailable.push(n);
      else items.push({game:'quina', contest:n, numbers:[1,2,3,4,5]});
    }
    return response({items, missing_contests:unavailable, next_before:lower > 1 ? lower : null, provenance:{recently_checked:true, verified:false}});
  };
  return {fetch, requests};
}
async function history(latest, missing) {
  const mock = pages(latest, missing);
  const env = setup(mock.fetch);
  env.context.progress = {textContent:''};
  const result = await vm.runInContext("fetchAssistantHistory({key:'quina'}, 'all', progress)", env.context);
  return {result, ...mock, ...env};
}
test('histórico maior que 500 termina com recorte explícito e sem ultrapassar o limite', async () => {
  const {result, requests, context} = await history(7000);
  assert.equal(requests.length, 5);
  assert.equal(result.draws.length, 500);
  assert.equal(result.draws[0].contest, 7000);
  assert.equal(result.draws.at(-1).contest, 6501);
  assert.equal(result.complete, false);
  assert.match(result.periodLabel, /histórico anterior não incluído/);
  context.result = result;
  context.resultAI = {analysis:'ok', observations:[], candidate_numbers:null};
  context.stats = {};
  context.draws = result.draws;
  context.item = {name:'Quina'};
  const out = {innerHTML:''}; context.document.querySelector = () => out;
  vm.runInContext('renderAssistantAnalysis(resultAI,item,draws,result,stats)', context);
  assert.match(out.innerHTML, /histórico anterior não incluído/);
  assert.doesNotMatch(out.innerHTML, /0 concurso\(s\) indisponível/);
});
test('limites de 500 e inferiores são completos somente sem lacunas', async () => {
  for (const latest of [1, 499, 500]) {
    const {result} = await history(latest);
    assert.equal(result.draws.length, latest);
    assert.equal(result.complete, true);
    assert.match(result.periodLabel, /desde o concurso 1/);
  }
});
test('lacunas no recorte são identificadas tanto abaixo quanto acima do limite', async () => {
  for (const latest of [100, 7000]) {
    const {result} = await history(latest, new Set([latest - 1]));
    assert.equal(result.missingCount, 1);
    assert.equal(result.complete, false);
    assert.equal(result.draws.length, Math.min(latest, 500) - 1);
  }
});
test('não envia estatísticas ou dados à IA sem aceite das lacunas', async () => {
  const mock = pages(7000, new Set([6999]));
  const {context, elements, window} = setup(mock.fetch);
  Object.assign(elements, {
    '#assistant-status': {textContent:''}, '#assistant-content': {innerHTML:''}, '#ai-progress': {textContent:''},
    '#ai-consent': {checked:true}, '#ai-history-mode': {value:'all'}, '#ai-allow-partial': {checked:false},
  });
  window.LotoMasterAI.getConfig = () => ({key:'fake',model:'fake',provider:'fake'});
  window.LotoMasterAI.analyze = () => { throw new Error('IA não deveria ser chamada'); };
  vm.runInContext("state.catalog=[{key:'quina'}]; state.game='quina'; state.page='assistant'", context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){},submitter:null})', context);
  assert.equal(mock.requests.length, 5);
  assert.match(elements['#assistant-content'].innerHTML, /Marque a opção de análise parcial/);
  assert.equal(elements['#assistant-status'].textContent, 'Não concluída');
});
test('probabilidade do Dia de Sorte descreve evento conjunto também em jogos gerados', () => {
  const {context} = setup(async () => { throw Error('sem rede'); });
  assert.equal(vm.runInContext("probabilityEvent({key:'diadesorte'},{event:'7 dezenas + Mês da Sorte'})", context), 'Acertar as 7 dezenas sorteadas e o Mês da Sorte');
  assert.equal(vm.runInContext("probabilityEvent({key:'quina'},{event:'5 acertos'})", context), '5 acertos');
  const source = fs.readFileSync(path.join(staticDir, 'app.js'), 'utf8');
  assert.equal((source.match(/probabilityEvent\(item,(?:ticket\.probability|data)\)/g) || []).length, 3);
});
test('payload para a IA informa recorte limitado e proíbe alegar completude', async () => {
  let request;
  const {context, window} = setup(async (url, options) => {
    request = JSON.parse(options.body);
    return {ok:true, text:async () => JSON.stringify({output_text:'{"analysis":"ok"}'})};
  });
  vm.runInContext(fs.readFileSync(path.join(staticDir, 'ai-assistant.js'), 'utf8'), context);
  await window.LotoMasterAI.analyze(
    {key:'fake', endpoint:'https://example.test', provider:'openai-responses', model:'fake'},
    {key:'quina',name:'Quina',pick_size:5,range:{minimum:1,maximum:80}}, {},
    [{contest:7000,numbers:[1,2,3,4,5]}],
    {complete:false,missingCount:0,periodLabel:'Recorte dos até 500 concursos mais recentes · histórico anterior não incluído'}
  );
  const payload = JSON.parse(request.input.split('Dados JSON:\n')[1]);
  assert.equal(payload.archive_complete, false);
  assert.match(payload.period_label, /histórico anterior não incluído/);
  assert.match(request.instructions, /nunca afirme que o histórico é completo/);
});

test('recorte limitado sem lacunas prossegue com até 500 concursos', async () => {
  const mock = pages(7000);
  let posted;
  const {context, elements, window} = setup(async (url, options) => {
    if (options?.method === 'POST') {
      posted = JSON.parse(options.body);
      return response({latest_contest:7000});
    }
    return mock.fetch(url);
  });
  Object.assign(elements, {
    '#assistant-status': {textContent:''}, '#assistant-content': {innerHTML:''}, '#ai-progress': {textContent:''},
    '#ai-consent': {checked:true}, '#ai-history-mode': {value:'all'}, '#ai-allow-partial': {checked:false},
  });
  window.LotoMasterAI.getConfig = () => ({key:'fake',model:'fake',provider:'fake'});
  let sent;
  window.LotoMasterAI.analyze = async (config,item,stats,draws,completeness) => {
    sent = {draws,completeness};
    return {analysis:'ok', observations:[], candidate_numbers:null};
  };
  vm.runInContext("state.catalog=[{key:'quina',name:'Quina'}]; state.game='quina'; state.page='assistant'", context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){},submitter:null})', context);
  assert.equal(mock.requests.length, 5);
  assert.equal(posted.draws.length, 500);
  assert.equal(sent.draws.length, 500);
  assert.equal(sent.completeness.complete, false);
  assert.match(elements['#assistant-content'].innerHTML, /histórico anterior não incluído/);
  assert.equal(elements['#assistant-status'].textContent, 'Concluída');
});


test('fluxo de 500 concursos usa endpoint ASGI real e conserva proveniência', async () => {
  const {spawnSync} = require('node:child_process');
  const mock = pages(7000);
  let actualStatus, actualStats, sent;
  const {context, elements, window} = setup(async (url, options) => {
    if (options?.method === 'POST') {
      const run = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname,'api_bridge.py')],
        {input: options.body, encoding:'utf8', maxBuffer: 5_000_000});
      assert.equal(run.status, 0, run.stderr);
      const responseBody = JSON.parse(run.stdout);
      actualStatus = responseBody.status; actualStats = responseBody.body;
      return {ok:actualStatus === 200, headers:{get:()=> 'application/json'}, json:async()=>actualStats};
    }
    return mock.fetch(url);
  });
  Object.assign(elements, {
    '#assistant-status': {textContent:''}, '#assistant-content': {innerHTML:''}, '#ai-progress': {textContent:''},
    '#ai-consent': {checked:true}, '#ai-history-mode': {value:'all'}, '#ai-allow-partial': {checked:false},
  });
  window.LotoMasterAI.getConfig = () => ({key:'fake',model:'fake',provider:'fake'});
  window.LotoMasterAI.analyze = async (_config,_item,_stats,draws,completeness) => {
    sent={draws,completeness}; return {analysis:'ok',observations:[],candidate_numbers:null};
  };
  vm.runInContext("state.catalog=[{key:'quina',name:'Quina'}]; state.game='quina'; state.page='assistant'", context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){},submitter:null})', context);
  assert.equal(actualStatus,200);
  assert.equal(actualStats.draws_analyzed,500);
  assert.equal(actualStats.provenance.verified,false);
  assert.equal(sent.draws.length,500);
  assert.equal(sent.completeness.complete,false);
  assert.match(elements['#assistant-content'].innerHTML,/histórico anterior não incluído/);
  assert.equal(elements['#assistant-status'].textContent,'Concluída');
});

test('recorte recente com lacunas também exige aceite', async () => {
  let calls=0;
  const {context,elements,window}=setup(async()=>{calls++;return response({items:[{game:'quina',contest:500,numbers:[1,2,3,4,5]}], count:1, expected_count:50, partial:true});});
  Object.assign(elements, {'#assistant-status':{textContent:''},'#assistant-content':{innerHTML:''},'#ai-progress':{textContent:''},'#ai-consent':{checked:true},'#ai-history-mode':{value:'50'},'#ai-allow-partial':{checked:false}});
  window.LotoMasterAI.getConfig=()=>({key:'fake',model:'fake',provider:'fake'});
  window.LotoMasterAI.analyze=()=>{throw Error('não deveria chamar');};
  vm.runInContext("state.catalog=[{key:'quina'}];state.game='quina';state.page='assistant'",context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){},submitter:null})',context);
  assert.equal(calls,1);
  assert.match(elements['#assistant-content'].innerHTML,/Marque a opção de análise parcial/);
});

test('aviso de cache invalida completude e chega à interface e IA', async () => {
  const {context,window}=setup(async()=>response({items:[{game:'quina',contest:1,numbers:[1,2,3,4,5]}],missing_contests:[],next_before:null,warning:'cache antigo'}));
  context.progress={textContent:''};
  const result=await vm.runInContext("fetchAssistantHistory({key:'quina'},'all',progress)",context);
  assert.equal(result.complete,false); assert.equal(result.warning,'cache antigo');
  context.result=result;context.draws=result.draws;context.item={name:'Quina'};context.stats={};context.resultAI={};
  const out={innerHTML:''};context.document.querySelector=()=>out;
  vm.runInContext('renderAssistantAnalysis(resultAI,item,draws,result,stats)',context);
  assert.match(out.innerHTML,/cache antigo/);
  let request;
  context.fetch=async (_url,options)=>{request=JSON.parse(options.body);return {ok:true,text:async()=>JSON.stringify({output_text:'{"analysis":"ok"}'})};};
  vm.runInContext(fs.readFileSync(path.join(staticDir,'ai-assistant.js'),'utf8'),context);
  await window.LotoMasterAI.analyze({key:'fake',endpoint:'https://example.test',provider:'openai-responses',model:'fake'}, {key:'quina',name:'Quina',pick_size:5,range:{minimum:1,maximum:80}}, {}, result.draws,result);
  const payload=JSON.parse(request.input.split('Dados JSON:\n')[1]);
  assert.equal(payload.archive_complete,false); assert.equal(payload.freshness_warning,'cache antigo');
  assert.match(payload.application_context.official_data_path,/sem verificação independente/);
});
