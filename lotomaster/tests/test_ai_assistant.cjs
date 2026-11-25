'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const appSource = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const aiSource = fs.readFileSync(path.join(__dirname, '../static/ai-assistant.js'), 'utf8');

function loadAi(fetchImpl = async () => { throw new Error('fetch inesperado'); }, timerApi = {}) {
  const storage = {getItem: () => null, setItem() {}, removeItem() {}};
  const context = vm.createContext({
    window: {},
    document: {querySelector: () => null},
    sessionStorage: storage,
    localStorage: storage,
    URL,
    AbortController,
    setTimeout: timerApi.setTimeout || setTimeout,
    clearTimeout: timerApi.clearTimeout || clearTimeout,
    fetch: fetchImpl,
  });
  vm.runInContext(aiSource, context);
  return context;
}

function loadApp(fetchImpl, elements = {}) {
  const context = vm.createContext({
    window: {addEventListener() {}},
    document: {querySelector: selector => elements[selector] || null},
    fetch: fetchImpl,
    AbortController,
  });
  vm.runInContext(appSource, context);
  return context;
}

function jsonResponse(payload) {
  return {
    ok: true,
    status: 200,
    headers: {get: () => 'application/json'},
    json: async () => payload,
  };
}

test('validação de combinação exige inteiros JSON reais e permite dígitos repetidos no Super Sete', async () => {
  const superSpec = {key: 'supersete', pick_size: 7, range: {minimum: 0, maximum: 9}};
  const candidateResult = async (numbers, spec) => {
    const context = loadAi(async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({output_text: JSON.stringify({analysis: 'ok', observations: [], candidate_numbers: numbers, candidate_note: 'teste'})}),
    }));
    return context.window.LotoMasterAI.analyze(
      {provider: 'openai-responses', endpoint: 'https://api.openai.com/v1/responses', model: 'local-test', key: 'test-only'},
      spec,
      {frequency: []},
      [],
      {complete: true, archiveComplete: true, missingCount: 0},
      null,
    ).then(result => result.candidate_numbers);
  };
  assert.deepEqual(JSON.parse(JSON.stringify(await candidateResult([0, 0, 1, 2, 3, 4, 9], superSpec))), [0, 0, 1, 2, 3, 4, 9]);
  for (const invalid of [null, false, '0', '', 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    const candidate = [0, 1, 2, 3, 4, 5, 6];
    candidate[0] = invalid;
    assert.equal(await candidateResult(candidate, superSpec), null);
  }
  const megaSpec = {key: 'megasena', pick_size: 6, range: {minimum: 1, maximum: 60}};
  assert.equal(await candidateResult(['1', 2, 3, 4, 5, 6], megaSpec), null);
});

test('recorte recente completo aceita cursor para concursos anteriores e distingue o arquivo integral', async () => {
  const calls = [];
  const context = loadApp(async url => {
    calls.push(String(url));
    return jsonResponse({
      items: Array.from({length: 50}, (_, index) => ({contest: 5000-index, numbers: [1, 2, 3, 4, 5, 6]})),
      expected_count: 50,
      from_contest: 4951,
      to_contest: 5000,
      missing_contests: [],
      next_before: 4951,
    });
  });
  context.item = {key: 'megasena'};
  context.progress = {textContent: ''};
  const result = await vm.runInContext('fetchAssistantHistory(item, "50", progress)', context);
  assert.equal(calls.length, 1);
  assert.match(calls[0], /\/api\/v1\/megasena\/history\?limit=50$/);
  assert.equal(result.complete, true);
  assert.equal(result.archiveComplete, false);
  assert.equal(result.missingCount, 0);
  assert.equal(result.expectedCount, 50);
  assert.equal(result.draws.length, 50);
  assert.equal(result.periodLabel, 'Últimos 50 concursos numerados');
});

test('contagem esperada impede rotular como completo um histórico com itens ausentes sem IDs informados', async () => {
  const context = loadApp(async () => jsonResponse({
    items: [{contest: 40, numbers: [1, 2, 3, 4, 5, 6]}],
    expected_count: 50,
    missing_contests: [],
    next_before: null,
  }));
  context.item = {key: 'megasena'};
  context.progress = {textContent: ''};
  const result = await vm.runInContext('fetchAssistantHistory(item, "50", progress)', context);
  assert.equal(result.complete, false);
  assert.equal(result.missingCount, 49);
  assert.equal(result.expectedCount, 50);
  assert.equal(result.draws.length, 1);
});

test('lacuna em recorte recente impede o envio sem autorização de análise parcial', async () => {
  const calls = [];
  let providerCalls = 0;
  const elements = {
    '#ai-consent': {checked: true},
    '#ai-history-mode': {value: '50'},
    '#ai-allow-partial': {checked: false},
    '#assistant-status': {textContent: ''},
    '#assistant-content': {innerHTML: ''},
    '#ai-progress': {textContent: ''},
  };
  const context = loadApp(async (url, options = {}) => {
    calls.push({url: String(url), options});
    return jsonResponse({
      items: [{game: 'megasena', contest: 40, numbers: [1, 2, 3, 4, 5, 6]}],
      expected_count: 50,
      missing_contests: [39],
      next_before: null,
    });
  }, elements);
  context.window.LotoMasterAI = {
    getConfig: () => ({key: 'test-only', model: 'local-test', provider: 'mock'}),
    analyze: async () => { providerCalls++; return {}; },
  };
  vm.runInContext("state.catalog=[{key:'megasena',name:'Mega-Sena',pick_size:6,min_pick:6,max_pick:20,digits:2,range:{minimum:1,maximum:60}}];state.game='megasena';state.page='assistant';", context);
  await vm.runInContext('runPersonalAIAnalysis({preventDefault(){}})', context);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/history\?limit=50$/);
  assert.equal(providerCalls, 0);
  assert.match(elements['#assistant-content'].innerHTML, /Marque a opção de análise parcial/);
  assert.equal(elements['#assistant-status'].textContent, 'Não concluída');
});

test('retirada do consentimento durante o carregamento bloqueia cálculo e envio ao provedor', async () => {
  const calls = [];
  let releasePage;
  const pagePromise = new Promise(resolve => { releasePage = resolve; });
  let providerCalls = 0;
  const elements = {
    '#ai-consent': {checked: true},
    '#ai-history-mode': {value: '50'},
    '#ai-allow-partial': {checked: false},
    '#assistant-status': {textContent: ''},
    '#assistant-content': {innerHTML: ''},
    '#ai-progress': {textContent: ''},
  };
  const context = loadApp(async (url, options = {}) => {
    calls.push({url: String(url), options});
    return pagePromise;
  }, elements);
  context.window.LotoMasterAI = {
    getConfig: () => ({key: 'test-only', model: 'local-test', provider: 'mock'}),
    analyze: async () => { providerCalls++; return {}; },
  };
  vm.runInContext("state.catalog=[{key:'megasena',name:'Mega-Sena',pick_size:6,min_pick:6,max_pick:20,digits:2,range:{minimum:1,maximum:60}}];state.game='megasena';state.page='assistant';", context);
  const running = vm.runInContext('runPersonalAIAnalysis({preventDefault(){}})', context);
  assert.equal(calls.length, 1);
  assert.ok(calls[0].options.signal instanceof AbortSignal);
  elements['#ai-consent'].checked = false;
  releasePage(jsonResponse({items:[{contest:40,numbers:[1,2,3,4,5,6]}],expected_count:1,missing_contests:[],next_before:null}));
  await running;
  assert.equal(calls.length, 1);
  assert.equal(providerCalls, 0);
  assert.equal(elements['#assistant-status'].textContent, 'Cancelada');
  assert.match(elements['#assistant-content'].innerHTML, /antes do envio ao provedor/);
});

test('modelo recebe a contagem combinatória exata e o escopo correto sem chamadas externas reais', async () => {
  let request;
  const context = loadAi(async (url, options) => {
    request = {url: String(url), options};
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({
        output_text: JSON.stringify({analysis: 'Odds pré-calculadas recebidas.', observations: [], candidate_numbers: [1, 2, 3, 4, 5, 6], candidate_note: 'Experimental.'}),
      }),
    };
  });
  const probability = {
    event: '6 acertos',
    one_in: 50063860,
    percent: 0.00000199745,
    favorable_outcomes: '1',
    total_outcomes: '50063860',
    any_prize: {one_in: 50063860, percent: 0.00000199745, favorable_outcomes: '1', total_outcomes: '50063860'},
  };
  const stats = {frequency: [], gaps: [], parity_distribution: [], sum: {}, layout: {}, pairs: [], triples: [], disclaimer: 'Descritivo.'};
  const completeness = {complete: true, archiveComplete: false, missingCount: 0, periodLabel: 'Recorte dos últimos 50 concursos'};
  const draws = [{contest: 40, numbers: [1, 2, 3, 4, 5, 6]}];
  const spec = {key: 'megasena', name: 'Mega-Sena', pick_size: 6, range: {minimum: 1, maximum: 60}};
  const config = {provider: 'openai-responses', endpoint: 'https://api.openai.com/v1/responses', model: 'local-test', key: 'test-only'};
  const result = await context.window.LotoMasterAI.analyze(config, spec, stats, draws, completeness, probability);
  assert.equal(result.analysis, 'Odds pré-calculadas recebidas.');
  assert.equal(request.url, config.endpoint);
  const body = JSON.parse(request.options.body);
  const json = body.input.slice(body.input.indexOf('Dados JSON:') + 'Dados JSON:\n'.length);
  const payload = JSON.parse(json);
  assert.equal(payload.archive_complete, false);
  assert.equal(payload.selected_window_complete, true);
  assert.equal(payload.selected_scope, 'Recorte dos últimos 50 concursos');
  assert.deepEqual(JSON.parse(JSON.stringify(payload.theoretical_probability)), probability);
  assert.match(body.instructions, /contagens inteiras pré-calculadas/);
});

test('a chamada HTTP usa um sinal composto em vez de substituir o sinal de consentimento', async () => {
  let receivedSignal;
  const context = loadAi(async (url, options) => {
    receivedSignal = options.signal;
    return {ok:true,status:200,text:async()=>JSON.stringify({output_text:'{"analysis":"ok"}'})};
  });
  const controller = new AbortController();
  const config = {provider:'openai-responses',endpoint:'https://api.openai.com/v1/responses',model:'local-test',key:'test-only'};
  const spec = {key:'megasena',name:'Mega-Sena',pick_size:6,range:{minimum:1,maximum:60}};
  await context.window.LotoMasterAI.analyze(config,spec,{},[],{complete:true,periodLabel:'teste'},null,controller.signal);
  assert.ok(receivedSignal instanceof AbortSignal);
  assert.notEqual(receivedSignal, controller.signal);
});

test('retirar o consentimento aborta a requisição composta do provedor', async () => {
  let receivedSignal;
  const context=loadAi((_url,options)=>new Promise((resolve,reject)=>{
    receivedSignal=options.signal;
    options.signal.addEventListener('abort',()=>{const error=new Error('aborted');error.name='AbortError';reject(error);},{once:true});
  }));
  const controller=new AbortController();
  const config={provider:'openai-responses',endpoint:'https://api.openai.com/v1/responses',model:'local-test',key:'test-only'};
  const spec={key:'megasena',name:'Mega-Sena',pick_size:6,range:{minimum:1,maximum:60}};
  const pending=context.window.LotoMasterAI.analyze(config,spec,{},[],{complete:true,periodLabel:'teste'},null,controller.signal);
  await new Promise(resolve=>setImmediate(resolve));
  controller.abort();
  assert.equal(receivedSignal.aborted,true);
  await assert.rejects(pending,error=>error.name==='AbortError');
});

test('timeout aborta também a leitura do corpo e informa expiração distinta', async () => {
  let expire, receivedSignal, bodyRead=false;
  const context=loadAi(async (_url,options)=>{
    receivedSignal=options.signal;
    return {ok:true,status:200,text:()=>{bodyRead=true;return new Promise(()=>{});}};
  },{
    setTimeout:(callback,delay)=>{assert.equal(delay,30_000);expire=callback;return 1;},
    clearTimeout:()=>{},
  });
  const config={provider:'openai-responses',endpoint:'https://api.openai.com/v1/responses',model:'local-test',key:'test-only'};
  const pending=context.window.LotoMasterAI.testConnection(config);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(bodyRead,true);
  expire();
  assert.equal(receivedSignal.aborted,true);
  await assert.rejects(pending,/excedeu o tempo limite de 30 segundos/);
});

test('não envia chave por endpoint HTTP loopback', async () => {
  let requests=0;
  const context=loadAi(async()=>{requests++;return {ok:true,status:200,text:async()=>'{"output_text":"OK"}'};});
  const config={provider:'openai-responses',endpoint:'http://127.0.0.1:8123/v1/responses',model:'local-test',key:'provider-secret'};
  await assert.rejects(context.window.LotoMasterAI.testConnection(config),/Use HTTPS/);
  assert.equal(requests,0);
});

test('resposta OpenAI Responses incompleta não é tratada como análise concluída', async () => {
  const context=loadAi(async()=>({
    ok:true,status:200,
    text:async()=>JSON.stringify({status:'incomplete',incomplete_details:{reason:'max_output_tokens'},output_text:'{"analysis":"texto parcial'}),
  }));
  const config={provider:'openai-responses',endpoint:'https://api.openai.com/v1/responses',model:'local-test',key:'test-only'};
  const spec={key:'megasena',name:'Mega-Sena',pick_size:6,range:{minimum:1,maximum:60}};
  await assert.rejects(context.window.LotoMasterAI.analyze(config,spec,{},[],{complete:true},null),/incompleta.*max_output_tokens/);
});


test('não envia zero repetidas à IA quando comparação com anterior não está disponível', async () => {
  let request;
  const context=loadAi(async (url,options)=>{
    request=JSON.parse(options.body);
    return {ok:true,status:200,text:async()=>JSON.stringify({output_text:'{"analysis":"ok"}'})};
  });
  const config={provider:'openai-responses',endpoint:'https://api.openai.com/v1/responses',model:'test',key:'test'};
  const spec={key:'megasena',name:'Mega-Sena',pick_size:6,range:{minimum:1,maximum:60}};
  const stats={frequency:[],repeated_from_previous:0,tables:{repeats:{data:{latest_comparison_available:false}}}};
  await context.window.LotoMasterAI.analyze(config,spec,stats,[],{complete:false},null);
  const payload=JSON.parse(request.input.split('Dados JSON:\n')[1]);
  assert.equal(payload.observed_statistics.repeated_from_previous,null);
  assert.equal(payload.observed_statistics.repeat_comparison_available,false);
});
