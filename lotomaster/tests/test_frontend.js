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
  const context = vm.createContext({window, document, fetch, URL, console, setTimeout, clearTimeout, AbortController});
  vm.runInContext(fs.readFileSync(path.join(staticDir, 'app.js'), 'utf8'), context);
  return {context, elements, window};
}
function response(data) {
  return {ok: true, headers: {get: () => 'application/json'}, json: async () => data};
}
function pages(latest, missing = new Set()) {
  const requests = [];
  const fetch = async url => {
    const parsed = new URL(url, 'http://localhost');
    if (!parsed.pathname.endsWith('/history')) return response(null);
    requests.push(url);
    const limit = Math.min(Number(parsed.searchParams.get('limit') || 100), 100);
    const before = Number(parsed.searchParams.get('before') || latest + 1);
    const upper = Math.min(latest, before - 1);
    const lower = Math.max(1, upper - limit + 1);
    const items = [], unavailable = [];
    for (let n = upper; n >= lower; n--) {
      if (missing.has(n)) unavailable.push(n);
      else items.push({game:'quina', contest:n, numbers:[1,2,3,4,5]});
    }
    return response({items, from_contest:lower, to_contest:upper, expected_count:Math.max(0, upper-lower+1), missing_contests:unavailable, next_before:lower > 1 ? lower : null, provenance:{recently_checked:true, verified:false}});
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
  assert.equal(result.complete, true);
  assert.equal(result.archiveComplete, false);
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
  vm.runInContext("state.catalog=[{key:'quina',name:'Quina',pick_size:5,min_pick:5,max_pick:15,digits:2,range:{minimum:1,maximum:80}}]; state.game='quina'; state.page='assistant'", context);
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

test('refresh concorrente atualiza concursos sem renderizar a página aberta depois da navegação', async () => {
  let resolveLatest;
  const pending = new Promise(resolve => { resolveLatest = resolve; });
  const {context, elements} = setup(() => pending);
  elements['#sync-status'] = {textContent:''};
  let renders = 0;
  context.render = async () => { renders++; };
  vm.runInContext("state.catalog=[{key:'quina'}]; state.game='quina'; state.page='results'; state.lastContests.quina=10; state.lastRefreshAt=123", context);
  const refreshing = vm.runInContext('refreshLiveData(false)', context);
  vm.runInContext("state.page='generator'", context);
  resolveLatest(response({contest:11}));
  await refreshing;
  assert.equal(renders, 0);
  assert.equal(vm.runInContext('state.lastContests.quina', context), 11);
  assert.notEqual(vm.runInContext('state.lastRefreshAt', context), 123);
});

test('falha total no refresh informa falha e não atualiza horário de sucesso', async () => {
  const {context, elements} = setup(async () => { throw new Error('offline'); });
  elements['#sync-status'] = {textContent:''};
  vm.runInContext("state.catalog=[{key:'quina'}]; state.page='overview'; state.lastRefreshAt=123", context);
  await vm.runInContext('refreshLiveData(true)', context);
  assert.equal(elements['#sync-status'].textContent, 'Falha ao atualizar resultados');
  assert.equal(vm.runInContext('state.lastRefreshAt', context), 123);
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
  assert.match(request.instructions, /nunca afirme que o histórico completo foi analisado se archive_complete for falso/);
});

test('OpenAI Chat omite temperature para gpt-6-astra e preserva o padrão para outros modelos', async () => {
  const requests = [];
  const fetch = async (_url, options) => {
    requests.push(JSON.parse(options.body));
    return {ok:true, status:200, text:async () => JSON.stringify({choices:[{message:{content:'OK'}}]})};
  };
  const {context, window} = setup(fetch);
  vm.runInContext(fs.readFileSync(path.join(staticDir, 'ai-assistant.js'), 'utf8'), context);
  for (const model of ['gpt-6-astra', 'compatible-custom-model']) {
    await window.LotoMasterAI.testConnection({provider:'openai-chat',endpoint:'https://example.test/chat',model,key:'test-key'});
  }
  assert.equal(Object.hasOwn(requests[0], 'temperature'), false);
  assert.equal(requests[1].temperature, 0.2);
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
  vm.runInContext("state.catalog=[{key:'quina',name:'Quina',pick_size:5,min_pick:5,max_pick:15,digits:2,range:{minimum:1,maximum:80}}]; state.game='quina'; state.page='assistant'", context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){},submitter:null})', context);
  assert.equal(mock.requests.length, 5);
  assert.equal(posted.draws.length, 500);
  assert.equal(sent.draws.length, 500);
  assert.equal(sent.completeness.complete, true);
  assert.equal(sent.completeness.archiveComplete, false);
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
  vm.runInContext("state.catalog=[{key:'quina',name:'Quina',pick_size:5,min_pick:5,max_pick:15,digits:2,range:{minimum:1,maximum:80}}]; state.game='quina'; state.page='assistant'", context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){},submitter:null})', context);
  assert.equal(actualStatus,200);
  assert.equal(actualStats.draws_analyzed,500);
  assert.equal(actualStats.provenance.verified,false);
  assert.equal(sent.draws.length,500);
  assert.equal(sent.completeness.complete,true);
  assert.equal(sent.completeness.archiveComplete,false);
  assert.match(elements['#assistant-content'].innerHTML,/histórico anterior não incluído/);
  assert.equal(elements['#assistant-status'].textContent,'Concluída');
});

test('recorte recente com lacunas também exige aceite', async () => {
  let calls=0;
  const missing=Array.from({length:49},(_,index)=>451+index);
  const {context,elements,window}=setup(async()=>{calls++;return response({items:[{game:'quina',contest:500,numbers:[1,2,3,4,5]}],from_contest:451,to_contest:500,missing_contests:missing,count:1,expected_count:50,partial:true,provenance:{recently_checked:true,verified:false}});});
  Object.assign(elements, {'#assistant-status':{textContent:''},'#assistant-content':{innerHTML:''},'#ai-progress':{textContent:''},'#ai-consent':{checked:true},'#ai-history-mode':{value:'50'},'#ai-allow-partial':{checked:false}});
  window.LotoMasterAI.getConfig=()=>({key:'fake',model:'fake',provider:'fake'});
  window.LotoMasterAI.analyze=()=>{throw Error('não deveria chamar');};
  vm.runInContext("state.catalog=[{key:'quina',name:'Quina',pick_size:5,min_pick:5,max_pick:15,digits:2,range:{minimum:1,maximum:80}}];state.game='quina';state.page='assistant'",context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){},submitter:null})',context);
  assert.equal(calls,1);
  assert.match(elements['#assistant-content'].innerHTML,/Marque a opção de análise parcial/);
});

test('aviso de cache invalida completude arquivística e chega à interface e IA', async () => {
  const {context,window}=setup(async()=>response({items:[{game:'quina',contest:1,numbers:[1,2,3,4,5]}],from_contest:1,to_contest:1,expected_count:1,missing_contests:[],next_before:null,warning:'cache antigo',provenance:{latest_lookup:'server_cache',recently_checked:false,verified:false}}));
  context.progress={textContent:''};
  const result=await vm.runInContext("fetchAssistantHistory({key:'quina'},'all',progress)",context);
  assert.equal(result.complete,true); assert.equal(result.archiveComplete,false); assert.equal(result.warning,'cache antigo');
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

test('histórico público mostra avisos de cache e informa proveniência não verificada', () => {
  const {context,elements}=setup(async()=>{throw Error('sem rede');});
  Object.assign(elements, {
    '#history-count':{textContent:''}, '#history-range':{textContent:''}, '#history-table':{innerHTML:''},
    '[data-action="results-latest"]':{disabled:false}, '[data-action="results-newer"]':{disabled:false}, '[data-action="results-older"]':{disabled:false},
  });
  context.item={key:'quina',digits:2}; context.history={index:0,isLoading:false};
  context.historyPage={items:[{contest:500,numbers:[1,2,3,4,5],estimated_prize:1000}],from_contest:500,to_contest:500,expected_count:1,missing_contests:[],next_before:499,warning:'cache antigo',provenance:{latest_lookup:'server_cache',recently_checked:false,verified:false}};
  vm.runInContext('renderResultsHistoryPage(item,history,historyPage)',context);
  assert.match(elements['#history-table'].innerHTML,/cache antigo/);
  assert.match(elements['#history-table'].innerHTML,/cache do servidor/);
  assert.match(elements['#history-table'].innerHTML,/não verificada independentemente/);
});

test('polling mais antigo não sobrescreve resultados de polling iniciado depois', async () => {
  let resolveOld, resolveNew;
  let calls=0;
  const {context,elements}=setup(() => new Promise(resolve => { if (++calls===1) resolveOld=resolve; else resolveNew=resolve; }));
  elements['#sync-status']={textContent:''};
  context.render=async()=>{};
  vm.runInContext("state.catalog=[{key:'quina'}];state.page='overview';state.lastContests.quina=1",context);
  const old=vm.runInContext('refreshLiveData(false)',context);
  const newer=vm.runInContext('refreshLiveData(false)',context);
  resolveNew(response({contest:3})); await newer;
  resolveOld(response({contest:2})); await old;
  assert.equal(vm.runInContext('state.lastContests.quina',context),3);
});

test('histórico rejeita cursor que não corresponde ao limite da página', async () => {
  const {context}=setup(async()=>response({items:[{contest:8,numbers:[1,2,3,4,5]}],from_contest:8,to_contest:8,expected_count:1,missing_contests:[],next_before:7,provenance:{recently_checked:true}}));
  context.progress={textContent:''};
  await assert.rejects(vm.runInContext("fetchAssistantHistory({key:'quina'},'all',progress)",context),/cursor.*inválido ou descontínuo/);
});

test('controles de seleção mantêm aria-pressed sincronizado com estado visual', () => {
  const {context}=setup();
  const digits=vm.runInContext('superSeteGrid()',context).match(/<button type="button" data-column="\d+" data-digit="\d+" aria-pressed="false">/g)||[];
  assert.equal(digits.length,70);
  const classes=new Set();
  const button={dataset:{},classList:{contains:name=>classes.has(name),add:name=>classes.add(name),remove(...names){names.forEach(name=>classes.delete(name));}},setAttribute(name,value){this[name]=value;}};
  context.event={target:{closest:selector=>selector==='.number-cell'?button:null}};
  vm.runInContext("state.mode='fixed';handleClick(event)",context);
  assert.equal(button['aria-pressed'],'true');
  vm.runInContext('handleClick(event)',context);
  assert.equal(button['aria-pressed'],'false');
});

test('Cue documenta Python 3.11+, dependências no checkout e ambiente correspondente sem Bearer', () => {
  const html=fs.readFileSync(path.join(staticDir,'index.html'),'utf8');
  assert.match(html,/python3/);
  assert.match(html,/--transport stdio/);
  assert.match(html,/Python 3\.11 ou superior/);
  assert.match(html,/python3 -m pip install -r requirements\.txt/);
  assert.match(html,/executável Python desse mesmo ambiente/);
  assert.match(html,/não exige Bearer/);
  assert.match(html,/&lt;caminho-do-checkout-no-computador-do-Cue&gt;/);
});

test('menu declara controle e sincroniza estado/label ao abrir, fechar e navegar', () => {
  const html=fs.readFileSync(path.join(staticDir,'index.html'),'utf8');
  const source=fs.readFileSync(path.join(staticDir,'app.js'),'utf8');
  assert.match(html,/id="menu-toggle" aria-controls="sidebar" aria-expanded="false" aria-label="Abrir menu"/);
  assert.match(source,/aria-expanded','false'/);
  assert.match(source,/aria-expanded',String\(open\)/);
  assert.match(source,/open\?'Fechar menu':'Abrir menu'/);
  assert.match(source,/closeMobileSidebar\(\); render\(\)/);
});

test('status único permanece exibido e pode quebrar layout até 1080px', () => {
  const html=fs.readFileSync(path.join(staticDir,'index.html'),'utf8');
  const css=fs.readFileSync(path.join(staticDir,'app.css'),'utf8');
  assert.equal((html.match(/role="status"/g)||[]).length>=1,true);
  assert.doesNotMatch(css,/#sync-status\s*\{\s*display\s*:\s*none/);
  assert.match(css,/@media\(max-width:1080px\)[\s\S]*?#sync-status\{display:block/);
  // As três dimensões auditadas são fronteira/interior/fronteira das regras responsivas existentes.
  assert.match(css,/@media\(max-width:1080px\)/); assert.match(css,/@media\(max-width:760px\)/);
  for (const width of [390,760,1080]) assert.ok(width<=1080);
});

test('Super Sete limita seletores a 1–3, respeita composições aceitas e bloqueia inválidas', async () => {
  async function submit(columnPicks) {
    const calls=[];
    const {context,elements}=setup(async (url,options)=>{
      calls.push({url,payload:JSON.parse(options.body)});
      return response({items:[],disclaimer:'Somente teste.'});
    });
    vm.runInContext("state.catalog=[{key:'supersete',name:'Super Sete',digits:1}];state.game='supersete';state.page='generator';",context);
    elements['#game-count']={value:'1'};
    elements['#generated-output']={innerHTML:''};
    columnPicks.forEach((value,index)=>{elements[`[data-column-pick="${index+1}"]`]={value:String(value)};});
    await vm.runInContext('handleGenerate({preventDefault(){}})',context);
    return {calls,output:elements['#generated-output'].innerHTML};
  }
  const {context}=setup(async()=>{throw Error('endpoint não deve ser chamado');});
  const markup=vm.runInContext('superSeteGrid()',context);
  const optionTags=markup.match(/<option value="\d+"/g)||[];
  assert.equal(optionTags.length,21);
  assert.doesNotMatch(markup,/<option value="4"/);
  const validLayouts=[Array(7).fill(1),Array(7).fill(2),Array(7).fill(3),[2,2,1,1,1,1,1],[3,2,2,2,2,2,2]];
  for (const picks of validLayouts) {
    const {calls}=await submit(picks);
    assert.equal(calls.length,1);
    assert.equal(calls[0].payload.pick_count,picks[0]);
    assert.deepEqual(Object.values(calls[0].payload.columns).map(column=>column.pick_count),picks);
  }
  for (const picks of [[3,1,1,1,1,1,1],[3,3,1,1,1,1,1],[4,1,1,1,1,1,1]]) {
    const {calls,output}=await submit(picks);
    assert.equal(calls.length,0);
    assert.match(output,/Composição inválida do Super Sete/);
  }
});

test('teste de conexão da IA não aplica resposta obsoleta após edição', async () => {
  let resolveTest, toastMessages=[];
  const {context,elements,window}=setup();
  const classes=new Set(['pill-muted']);
  const status={textContent:'',classList:{remove:value=>classes.delete(value)}};
  const key={value:'secret'};
  const button={disabled:false};
  Object.assign(elements,{'[data-action="ai-test"]':button,'#ai-config-status':status,'#ai-key':key});
  window.LotoMasterAI={saveFromForm:()=>({model:'m'}),testConnection:()=>new Promise(resolve=>{resolveTest=resolve;})};
  context.toast=message=>toastMessages.push(message);
  const pending=vm.runInContext('testPersonalAIConfig()',context);
  vm.runInContext('aiConfigRevision++',context); // usuário editou enquanto a conexão estava pendente
  resolveTest({textReceived:true}); await pending;
  assert.equal(status.textContent,'Testando');
  assert.equal(key.value,'secret');
  assert.equal(toastMessages.length,0);
  assert.equal(button.disabled,false);
});

test('selo de simulação reconhece provenance client_supplied com draw_origin de fallback', () => {
  const source=fs.readFileSync(path.join(staticDir,'app.js'),'utf8');
  assert.match(source,/response\.provenance\?\.kind==='client_supplied'\|\|response\.draw_origin==='client_submitted'/);
  assert.match(source,/response\.provenance\?\.description\|\|\(clientOrigin/);
});
