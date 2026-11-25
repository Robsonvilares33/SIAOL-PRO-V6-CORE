'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function frontend(values = {}, bonus = null, fetchImpl = null) {
  const elements = Object.fromEntries(Object.entries(values).map(([id, value]) => [id, value&&typeof value==='object'?{...value}:{value, innerHTML: ''}]));
  elements['#sim-result'] = {innerHTML: ''};
  elements['#toast'] = {textContent:'',classList:{add(){},remove(){}}};
  const records = new Map();
  const localStorage = {getItem:key=>records.has(key)?records.get(key):null,setItem:(key,value)=>records.set(key,String(value)),removeItem:key=>records.delete(key)};
  let requests = 0;
  const context = vm.createContext({
    window: {addEventListener() {}},
    document: {querySelector: selector => elements[selector] || null, querySelectorAll: () => []},
    localStorage,
    TextEncoder,
    setTimeout:()=>1,
    clearTimeout:()=>{},
    fetch: async (...args) => { requests++; if (fetchImpl) return fetchImpl(...args); throw new Error('a rede não deve ser chamada neste teste'); },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8'), context);
  context.lotteryBonus = bonus;
  vm.runInContext("state.catalog=[{key:'lotofacil', bonus:lotteryBonus, min_pick:15, max_pick:20, pick_size:15, digits:2, range:{minimum:1, maximum:25}}]; state.game='lotofacil'; state.page='simulator';", context);
  return {context, elements, localStorage, requests: () => requests};
}

test('converte jogos válidos mantendo linhas e dezenas', () => {
  const {context} = frontend();
  context.input = '01 02 03\n4,5;6\n\n07 | 08 09';
  const result = vm.runInContext('parseStrictNumberLines(input)', context);
  assert.deepEqual(JSON.parse(JSON.stringify(result)), [[1,2,3],[4,5,6],[7,8,9]]);
});

test('rejeita uma linha inválida em vez de descartá-la', async () => {
  for (const invalid of ['abc', '1 2 x', '1e2', '1.5', '-1', ',,,', '9007199254740992']) {
    const {context, elements, requests} = frontend({'#sim-numbers': `01 02 03\n${invalid}`});
    await vm.runInContext('handleSimulate({preventDefault(){}})', context);
    assert.match(elements['#sim-result'].innerHTML, /nenhum jogo será omitido/);
    assert.equal(requests(), 0);
  }
});

test('rejeita trevos inválidos antes de chamar a API', async () => {
  const {context, elements, requests} = frontend({'#sim-numbers':'01 02 03', '#sim-trevos':'2, x'}, {type:'trevos'});
  await vm.runInContext('handleSimulate({preventDefault(){}})', context);
  assert.match(elements['#sim-result'].innerHTML, /2 a 6 trevos distintos/);
  assert.equal(requests(), 0);
});

test('preserva mês e colunas de cada jogo quando não há substituição explícita', () => {
  const {context} = frontend();
  const games=[
    {numbers:[1,2],columns:[[1],[2]],ticket_number:1,bonus:{month:3}},
    {numbers:[3,4],columns:[[3],[4]],ticket_number:2,bonus:{month:11}},
  ];
  context.games=games;
  const result=vm.runInContext('ticketsWithBonus(games, {}, false)', context, {timeout:1000});
  assert.deepEqual(JSON.parse(JSON.stringify(result)), games);
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(commonTicketBonus(games))', context)), {});
});

test('sobrescreve bônus heterogêneos somente quando o usuário opta', () => {
  const {context} = frontend();
  const games=[{numbers:[1],bonus:{team:'Azul'}},{numbers:[2],bonus:{team:'Verde'}}];
  context.games=games;
  const kept=vm.runInContext('ticketsWithBonus(games, {team:"Vermelho"}, false)', context);
  const replaced=vm.runInContext('ticketsWithBonus(games, {team:"Vermelho"}, true)', context);
  assert.deepEqual(JSON.parse(JSON.stringify(kept.map(t=>t.bonus))), [{team:'Azul'},{team:'Verde'}]);
  assert.deepEqual(JSON.parse(JSON.stringify(replaced.map(t=>t.bonus))), [{team:'Vermelho'},{team:'Vermelho'}]);
});

test('preserva trevos diferentes por jogo, sem alterar dezenas nem colunas', () => {
  const {context} = frontend();
  const games=[
    {numbers:[1,2],columns:[[1],[2]],bonus:{trevos:[1,2]}},
    {numbers:[3,4],columns:[[3],[4]],bonus:{trevos:[4,6]}},
  ];
  context.games=games;
  const output=vm.runInContext('ticketsWithBonus(games, {}, false)', context);
  assert.deepEqual(JSON.parse(JSON.stringify(output.map(t=>t.bonus.trevos))), [[1,2],[4,6]]);
  assert.deepEqual(JSON.parse(JSON.stringify(output.map(t=>t.columns))), [[[1],[2]],[[3],[4]]]);
  const overridden=vm.runInContext('ticketsWithBonus(games, {trevos:[2,5]}, true)', context);
  assert.deepEqual(JSON.parse(JSON.stringify(overridden.map(t=>t.bonus.trevos))), [[2,5],[2,5]]);
  assert.deepEqual(JSON.parse(JSON.stringify(overridden.map(t=>t.numbers))), [[1,2],[3,4]]);
});

test('não altera bonus individual se o mesmo bônus já é comum', () => {
  const {context} = frontend();
  const games=[{bonus:{month:7}},{bonus:{month:7}}]; context.games=games;
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(commonTicketBonus(games))', context)), {month:7});
});

test('integra fechamento de repetidas Lotofácil com resultado explícito e contrato esperado', () => {
  const source=fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
  assert.match(source, /async function loadRepeatedPrevious\(version, game\)/);
  assert.match(source, /api\('\/lotofacil\/latest'\)/);
  assert.match(source, /api\('\/lotofacil\/closures\/repeated',\{method:'POST',body:JSON\.stringify\(\{\.\.\.state\.repeatedRequest,previous_draw:state\.repeatedDraw\.numbers,offset\}\)\}\)/);
  assert.match(source, /Selecione de 6 a 12 dezenas distintas do resultado anterior/);
  assert.match(source, /response\.items\.length!==response\.returned_count/);
  assert.match(source, /state\.page!=='tools'\|\|state\.game!==game/);
});

test('repetidas acima do limite não encaminham lote parcial ao conferidor', () => {
  const source=fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
  assert.match(source, /visible\.length<=500/);
  assert.match(source, /O conferidor aceita até 500 jogos por envio/);
  assert.match(source, /state\.repeatedTickets\.length>500/);
  assert.match(source, /Preparar conferência dos jogos exibidos/);
});

test('mantém intactos os fluxos legados de fechamento exaustivo e de bônus preservados', () => {
  const source=fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
  assert.match(source, /async function handleClosure\(event\)/);
  assert.match(source, /\/closures\/exhaustive/);
  assert.match(source, /state\.closureTickets=entries\.map/);
  assert.match(source, /function ticketsWithBonus\(tickets, bonus, replaceBonus=false\)/);
  assert.match(source, /if \(preloaded && \$\('#sim-bonus-override'\)\?\.checked\)/);
});

test('importação só salva depois de validar todas as linhas e não chama a API', async () => {
  const values={'#import-text':`${Array.from({length:15},(_,i)=>i+1).join(' ')}\n1 2 x`,'#import-status':{textContent:''},'#my-games-list':{innerHTML:''}};
  const {context,elements,localStorage,requests}=frontend(values);
  vm.runInContext("state.catalog=[{key:'lotofacil',min_pick:15,max_pick:20,pick_size:15,digits:2,range:{minimum:1,maximum:25}}];state.game='lotofacil';",context);
  await vm.runInContext('handleImportGames({preventDefault(){}})',context);
  assert.match(elements['#import-status'].textContent,/nenhum bilhete foi importado/);
  assert.equal(localStorage.getItem('lotomaster.myGames.v1.lotofacil'),null);
  assert.equal(requests(),0);
});

test('importação válida persiste somente localmente em Meus Jogos', async () => {
  const values={'#import-text':Array.from({length:15},(_,i)=>i+1).join(' '),'#import-status':{textContent:''},'#my-games-list':{innerHTML:''}};
  const {context,elements,localStorage,requests}=frontend(values);
  vm.runInContext("state.catalog=[{key:'lotofacil',min_pick:15,max_pick:20,pick_size:15,digits:2,range:{minimum:1,maximum:25}}];state.game='lotofacil';",context);
  await vm.runInContext('handleImportGames({preventDefault(){}})',context);
  const saved=JSON.parse(localStorage.getItem('lotomaster.myGames.v1.lotofacil'));
  assert.equal(saved.length,1);
  assert.equal(saved[0].game,'lotofacil');
  assert.deepEqual(saved[0].numbers,Array.from({length:15},(_,i)=>i+1));
  assert.match(elements['#import-status'].textContent,/apenas neste navegador/);
  assert.equal(requests(),0);
});

test('filtros de Meus Jogos não alteram o armazenamento nem enviam pedidos', () => {
  const values={'#my-filter-sum-min': '250','#my-filter-sum-max':'','#my-filter-even-min':'','#my-filter-even-max':'','#my-filter-include':'','#my-filter-exclude':'','#my-filter-repeat-min':'','#my-filter-repeat-max':'','#my-filter-reference-contest':'','#my-filter-reference-draw':'','#my-games-filter-status':{textContent:''},'#my-games-list':{innerHTML:''}};
  const {context,elements,localStorage,requests}=frontend(values);
  vm.runInContext("state.catalog=[{key:'lotofacil',min_pick:15,max_pick:20,pick_size:15,digits:2,range:{minimum:1,maximum:25}}];state.game='lotofacil';",context);
  const numbers1=Array.from({length:15},(_,i)=>i+1),numbers2=Array.from({length:15},(_,i)=>i+11);
  const saved=[{id:'one',game:'lotofacil',numbers:numbers1,ticket_number:1,bonus:{}},{id:'two',game:'lotofacil',numbers:numbers2,ticket_number:2,bonus:{}}];
  localStorage.setItem('lotomaster.myGames.v1.lotofacil',JSON.stringify(saved));
  const before=localStorage.getItem('lotomaster.myGames.v1.lotofacil');
  vm.runInContext('state.myGames=readMyGames("lotofacil");state.myGamesFiltered=state.myGames;',context);
  vm.runInContext('applyMyGamesFilters({preventDefault(){}})',context);
  assert.equal(vm.runInContext('state.myGamesFiltered.length',context),1);
  assert.equal(vm.runInContext('state.myGamesFiltered[0].id',context),'two');
  assert.equal(localStorage.getItem('lotomaster.myGames.v1.lotofacil'),before);
  assert.match(elements['#my-games-filter-status'].textContent,/1 de 2 jogos/);
  assert.equal(requests(),0);
});

test('remoção e abertura de Meus Jogos só alteram estado e armazenamento locais', () => {
  const {context,localStorage,requests}=frontend({'#my-games-list':{innerHTML:''}});
  vm.runInContext("state.catalog=[{key:'lotofacil',min_pick:15,max_pick:20,pick_size:15,digits:2,range:{minimum:1,maximum:25}}];state.game='lotofacil';",context);
  const tickets=[1,2].map((id,index)=>({id:String(id),game:'lotofacil',numbers:Array.from({length:15},(_,i)=>i+index+1),ticket_number:id,bonus:{}}));
  localStorage.setItem('lotomaster.myGames.v1.lotofacil',JSON.stringify(tickets));
  vm.runInContext('state.myGames=readMyGames("lotofacil");state.myGamesFiltered=state.myGames;removeMyGame("1")',context);
  assert.deepEqual(JSON.parse(localStorage.getItem('lotomaster.myGames.v1.lotofacil')).map(ticket=>ticket.id),['2']);
  context.render=()=>{};
  vm.runInContext('useMyGame("2")',context);
  assert.equal(vm.runInContext('state.page',context),'simulator');
  assert.equal(vm.runInContext('state.simulatorTickets.length',context),1);
  assert.equal(vm.runInContext('state.simulatorTickets[0].ticket_number',context),2);
  assert.equal(requests(),0);
});

test('modo Somente aprovados mantém o número original e prepara apenas os jogos exibidos', () => {
  const {context,elements,requests}=frontend({'#closure-output':{innerHTML:''}});
  vm.runInContext("state.catalog=[{key:'megasena',min_pick:6,max_pick:20,pick_size:6,digits:2,range:{minimum:1,maximum:60}}];state.game='megasena';state.closureData={offset:10,page_size:3,candidate_count:20,approved_count:1,next_offset:13,coverage:'local',items:[{numbers:[1,2,3,4,5,6],approved:false,reasons:['Soma baixa']},{numbers:[1,2,3,4,5,7],approved:true,reasons:[]},{numbers:[1,2,3,4,5,8],approved:false,reasons:['Pares']} ]};",context);
  vm.runInContext("changeClosureView('closure','approved')",context);
  assert.equal(vm.runInContext('state.closureTickets.length',context),1);
  assert.equal(vm.runInContext('state.closureTickets[0].ticket_number',context),12);
  assert.match(elements['#closure-output'].innerHTML,/Somente aprovados/);
  assert.match(elements['#closure-output'].innerHTML,/Jogos exibidos/);
  assert.equal(requests(),0);
});

test('navegação de fechamento envia somente o offset solicitado', async () => {
  const calls=[];
  const response={offset:3,page_size:3,candidate_count:10,game_count:10,returned_count:1,approved_count:1,next_offset:null,coverage:'Enumeração local.',items:[{numbers:[1,2,3,4,5,7],approved:true,reasons:[]}],games:[[1,2,3,4,5,7]]};
  const {context,elements}=frontend({'#closure-output':{innerHTML:''}},null,async(url,options={})=>{calls.push({url,options});return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>response};});
  vm.runInContext("state.catalog=[{key:'megasena',min_pick:6,max_pick:20,pick_size:6,digits:2,range:{minimum:1,maximum:60}}];state.game='megasena';state.page='tools';state.closureRequest={pool:[1,2,3,4,5,6,7],fixed:[],pick_count:6,page_size:3,filters:{}};",context);
  await vm.runInContext('loadClosurePage(3)',context);
  assert.equal(calls.length,1);
  assert.equal(calls[0].url,'/api/v1/megasena/closures/exhaustive');
  assert.equal(JSON.parse(calls[0].options.body).offset,3);
  assert.match(elements['#closure-output'].innerHTML,/Página 2/);
});

test('filtros de repetidas no formulário exigem concurso explícito antes da API', () => {
  const {context}=frontend({'#closure-filter-repeat-min':'3','#closure-reference-contest':'','#closure-page-size':'250'});
  assert.throws(()=>vm.runInContext("readClosureRequest('closure')",context),/concurso de referência explícito/);
  vm.runInContext("document.querySelector=selector=>selector==='#closure-filter-repeat-min'?{value:'3'}:selector==='#closure-reference-contest'?{value:'42'}:selector==='#closure-page-size'?{value:'250'}:null",context);
  const request=JSON.parse(vm.runInContext("JSON.stringify(readClosureRequest('closure'))",context));
  assert.equal(request.reference_contest,42);
  assert.equal(request.page_size,250);
  assert.equal(request.filters.min_repeated,3);
});

test('exibe faixas por evento e explica que categorias exatas não são cumulativas', () => {
  const {context} = frontend();
  context.tiers=[{hits:0,label:'0 acertos',probability:1/100},{hits:15,label:'15 acertos',probability:1/50},{hits:20,label:'20 acertos',probability:1/10}];
  const html=vm.runInContext('renderProbabilityTiers(tiers)', context);
  assert.match(html, /Probabilidade teórica por faixa/);
  assert.match(html, /0 acertos/);
  assert.match(html, /15 acertos/);
  assert.match(html, /20 acertos/);
  assert.match(html, /mutuamente exclusivas/);
});

test('renderiza probabilidades de qualquer acerto sem limite fixo de 20', () => {
  const {context}=frontend();
  context.distribution=[{hits:0,probability:0.1,one_in:10,favorable_outcomes:'1',total_outcomes:'10'},{hits:23,probability:0.2,one_in:5,favorable_outcomes:'2',total_outcomes:'10'}];
  const html=vm.runInContext("renderHitDistribution(distribution,'colunas acertadas')",context);
  assert.match(html,/distribuição completa de acertos/);
  assert.match(html,/23 colunas acertadas/);
  assert.match(html,/2 resultados favoráveis \/ 10 resultados possíveis/);
});

test('calculadora envia as sete escolhas do Super Sete e renderiza eventos especiais', async () => {
  const calls=[];
  const payload={event:'7 acertos em 7 colunas',one_in:5000000,percent:0.00002,method:'Contagem exata',hit_unit:'colunas acertadas',column_pick_counts:[2,1,1,1,1,1,1],any_prize:{one_in:1000,percent:0.1,favorable_outcomes:'10000',total_outcomes:'10000000'},prize_tiers:[{label:'3 acertos',hits:3,probability:0.1,one_in:10,favorable_outcomes:'1000000',total_outcomes:'10000000'}],hit_distribution:[{hits:3,probability:0.1,one_in:10,favorable_outcomes:'1000000',total_outcomes:'10000000'}],probability_scope:'Teórica.'};
  const fetchImpl=async(url,options={})=>{calls.push({url,options});return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload};};
  const values={'#prob-result':''};
  for(let column=1;column<=7;column++) values[`#prob-column-${column}`]=String(column===1?2:1);
  const {context,elements}=frontend(values,null,fetchImpl);
  vm.runInContext("state.catalog=[{key:'supersete',bonus:{type:'columns'},min_pick:7,max_pick:7,pick_size:7,digits:1,range:{minimum:0,maximum:9}}];state.game='supersete';state.page='tools';",context);
  await vm.runInContext('calculateProbability({preventDefault(){}})',context);
  assert.equal(calls.length,1);
  assert.equal((calls[0].url.match(/column_picks=/g)||[]).length,7);
  assert.match(calls[0].url,/column_picks=2/);
  assert.match(elements['#prob-result'].innerHTML,/Qualquer faixa de prêmio/);
  assert.match(elements['#prob-result'].innerHTML,/3 acertos/);
  assert.match(elements['#prob-result'].innerHTML,/contagem inteira exata/);
});

test('distribui dezenas nos quatro blocos 5×5 da grade 10×10', () => {
  const {context} = frontend();
  context.values = [0, 4, 5, 49, 50, 54, 55, 99];
  const counts = vm.runInContext('lotomaniaQuadrantCounts(values)', context);
  assert.deepEqual(JSON.parse(JSON.stringify(counts)), {Q1:2,Q2:2,Q3:2,Q4:2});
});

test('renderiza controles Q1–Q4 e mantém 23 como limite exclusivo de conferência Lotofácil', () => {
  const {context} = frontend();
  vm.runInContext("state.catalog=[{key:'lotomania', range:{minimum:0,maximum:99},digits:2,min_pick:50,max_pick:50,pick_size:50}];state.game='lotomania';", context);
  const html = vm.runInContext('filtersFields()', context);
  for (const id of ['filter-q1-min','filter-q1-max','filter-q2-min','filter-q2-max','filter-q3-min','filter-q3-max','filter-q4-min','filter-q4-max']) assert.match(html, new RegExp(id));
  assert.equal(vm.runInContext("maxSimulationPicks({key:'lotofacil',max_pick:20})", context), 23);
  assert.equal(vm.runInContext("maxSimulationPicks({key:'lotomania',max_pick:50})", context), 50);
});

test('aceita 23 dezenas na conferência simples da Lotofácil e envia o jogo integral', async () => {
  const calls=[];
  const jsonResponse = payload => ({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const fetchImpl = async (url, options={}) => {
    calls.push({url,options});
    if (url.endsWith('/lotofacil/latest')) return jsonResponse({game:'lotofacil',contest:1,draw_date:'01/01/2026',numbers:Array.from({length:15},(_,i)=>i+1),second_numbers:[],trevos:[]});
    return jsonResponse({draw_origin:'client_submitted',contest:1,draw_date:'01/01/2026',draw:{numbers:Array.from({length:15},(_,i)=>i+1)},results:[{ticket_number:1,main_hits:15,award:'15 acertos'}]});
  };
  const values=Array.from({length:23},(_,i)=>i+1);
  const {context,elements}=frontend({'#sim-numbers':values.join(' ')},null,fetchImpl);
  await vm.runInContext('handleSimulate({preventDefault(){}})', context);
  assert.equal(calls.length,2);
  assert.equal(JSON.parse(calls[1].options.body).tickets[0].numbers.length,23);
  assert.match(elements['#sim-result'].innerHTML,/15 acertos/);
});

test('reutiliza colunas originais do Super Sete quando a entrada digitada equivale ao jogo salvo', async () => {
  const calls=[];
  const jsonResponse=payload=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const ticket={numbers:[1,2,3,4,5,6,7],columns:[[1,8],[2],[3,4],[4],[5],[6],[7]],ticket_number:17,bonus:{}};
  const fetchImpl=async(url,options={})=>{
    calls.push({url,options});
    if(url.endsWith('/latest')) return jsonResponse({contest:1,draw_date:'01/01/2026',numbers:[0,1,2,3,4,5,6]});
    return jsonResponse({draw_origin:'client_submitted',contest:1,draw:{numbers:[0,1,2,3,4,5,6]},results:[{ticket_number:17,main_hits:2}]});
  };
  const {context}=frontend({'#sim-numbers':' 1   2 3 4 5 6 7 \n','#sim-contest':''},null,fetchImpl);
  context.preloadedTicket=ticket;
  vm.runInContext("state.catalog=[{key:'supersete',bonus:{type:'columns'},min_pick:7,max_pick:7,pick_size:7,digits:1,range:{minimum:0,maximum:9}}];state.game='supersete';state.simulatorTickets=[preloadedTicket];state.simulatorText='1 2 3 4 5 6 7';",context);
  await vm.runInContext('handleSimulate({preventDefault(){}})',context);
  const request=JSON.parse(calls.find(call=>call.url.endsWith('/supersete/simulate')).options.body);
  assert.deepEqual(request.tickets[0].columns,[[1,8],[2],[3,4],[4],[5],[6],[7]]);
  assert.equal(request.tickets[0].ticket_number,17);
});

test('rejeita 24 dezenas antes de enviar a conferência Lotofácil', async () => {
  const values=Array.from({length:24},(_,i)=>i+1);
  const {context,elements,requests}=frontend({'#sim-numbers':values.join(' ')});
  await vm.runInContext('handleSimulate({preventDefault(){}})', context);
  assert.match(elements['#sim-result'].innerHTML,/informe de 15 a 23 dezenas/);
  assert.equal(requests(),0);
});

test('aceita 23 dezenas na conferência histórica Lotofácil', async () => {
  const calls=[];
  const jsonResponse = payload => ({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const draw={game:'lotofacil',contest:1,draw_date:'01/01/2026',numbers:Array.from({length:15},(_,i)=>i+1),second_numbers:[],trevos:[]};
  const fetchImpl = async (url, options={}) => {
    calls.push({url,options});
    return url.includes('/history?')
      ? jsonResponse({items:[draw],next_before:null})
      : jsonResponse({draws:[{contest:1,results:[{ticket_number:1,main_hits:15}]}],summary:{'15 acertos':1},evaluated_tickets:1});
  };
  const values=Array.from({length:23},(_,i)=>i+1);
  const {context,elements}=frontend({'#batch-numbers':values.join(' '),'#batch-from':'1','#batch-to':'1','#batch-result':'','#batch-status':''},null,fetchImpl);
  await vm.runInContext('handleHistoryBatch({preventDefault(){},submitter:{disabled:false}})', context);
  assert.equal(calls.length,2);
  assert.equal(JSON.parse(calls[1].options.body).tickets[0].numbers.length,23);
  assert.equal(elements['#batch-status'].textContent,'Concluída');
  assert.match(elements['#batch-result'].innerHTML,/15 acertos/);
});

test('confere um concurso específico sem consultar o último resultado', async () => {
  const calls=[];
  const jsonResponse = payload => ({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const draw={game:'lotofacil',contest:42,draw_date:'01/01/2026',numbers:Array.from({length:15},(_,i)=>i+1)};
  const fetchImpl=async(url,options={})=>{calls.push({url,options});return jsonResponse({contest:42,draw_date:draw.draw_date,draw,results:[{ticket_number:1,main_hits:15,award:'15 acertos'}]});};
  const values=Array.from({length:15},(_,i)=>i+1);
  const {context,elements}=frontend({'#sim-numbers':values.join(' '),'#sim-contest':'42'},null,fetchImpl);
  await vm.runInContext('handleSimulate({preventDefault(){}})',context);
  assert.equal(calls.length,1);
  assert.match(calls[0].url,/\/lotofacil\/simulate$/);
  assert.equal(JSON.parse(calls[0].options.body).contest,42);
  assert.match(elements['#sim-result'].innerHTML,/concurso 42/);
});

test('divide conferência histórica em blocos compatíveis com o limite do endpoint', async () => {
  const calls=[];
  const jsonResponse = payload => ({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const fetchImpl=async(url,options={})=>{
    const body=JSON.parse(options.body); calls.push(body.draws.length);
    return jsonResponse({draws:body.draws.map(draw=>({contest:draw.contest,results:[{ticket_number:1,main_hits:0}]})),summary:{'0 acertos':body.draws.length}});
  };
  const {context}=frontend({},null,fetchImpl);
  context.draws=Array.from({length:5001},(_,index)=>({contest:index+1,numbers:Array.from({length:15},(__,n)=>n+1)}));
  const result=await vm.runInContext('simulateHistoryInChunks("lotofacil",[{numbers:Array.from({length:15},(_,i)=>i+1),ticket_number:1}],draws,null)',context);
  assert.deepEqual(calls,[5000,1]);
  assert.equal(result.draws.length,5001);
  assert.equal(result.summary['0 acertos'],5001);
  assert.equal(result.evaluated_tickets,1);
});

test('divide payload histórico acima de 2 MB medidos em UTF-8 e agrega respostas', async () => {
  const calls=[];
  const jsonResponse=payload=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const fetchImpl=async(url,options={})=>{
    const body=JSON.parse(options.body);
    calls.push({url,body,byteLength:new TextEncoder().encode(options.body).byteLength});
    return jsonResponse({draws:body.draws.map(draw=>({contest:draw.contest,results:[{ticket_number:1,main_hits:0}]})),summary:{'0 acertos':body.draws.length}});
  };
  const {context}=frontend({},null,fetchImpl);
  const tickets=[{numbers:Array.from({length:15},(_,index)=>index+1),ticket_number:1}];
  const draws=Array.from({length:3},(_,index)=>({contest:index+1,numbers:Array.from({length:15},(__,n)=>n+1),padding:'🚀'.repeat(180000)}));
  context.tickets=tickets;
  context.draws=draws;
  const originalBytes=Buffer.byteLength(JSON.stringify({tickets,draws}),'utf8');
  assert.ok(originalBytes>2_000_000);
  const result=await vm.runInContext('simulateHistoryInChunks("lotofacil",tickets,draws,null)',context);
  assert.equal(calls.length,3);
  assert.ok(calls.every(call=>call.url.endsWith('/lotofacil/simulate/history')&&call.byteLength<=2_000_000));
  assert.deepEqual(calls.map(call=>call.body.draws.length),[1,1,1]);
  assert.deepEqual(JSON.parse(JSON.stringify(result.draws.map(draw=>draw.contest))),[1,2,3]);
  assert.equal(result.summary['0 acertos'],3);
  assert.equal(result.evaluated_contests,3);
});

test('ordena por maior acerto e oferece exportação local do relatório histórico', () => {
  const source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  assert.match(source,/Por concurso \(crescente\)/);
  assert.match(source,/Por maior número de acertos/);
  assert.match(source,/Baixar relatório CSV/);
  assert.match(source,/function downloadHistorySimulation\(\)/);
  const {context,elements}=frontend({'#batch-result':'','#history-sort':'hits'});
  context.report={game:'lotofacil',first:1,last:2,tickets:[{ticket_number:1}],officialDraws:[{contest:1,numbers:Array.from({length:15},(_,i)=>i+1)},{contest:2,numbers:Array.from({length:15},(_,i)=>i+1)}],response:{evaluated_tickets:1,summary:{'15 acertos':1},draws:[{contest:1,results:[{ticket_number:1,main_hits:2}]},{contest:2,results:[{ticket_number:1,main_hits:5}]}]}};
  vm.runInContext('state.historySimulation=report;renderHistorySimulation()',context);
  const html=elements['#batch-result'].innerHTML;
  assert.ok(html.indexOf('<td class="table-number">2</td>')<html.indexOf('<td class="table-number">1</td>'));
});

test('ordena concursos históricos do mais recente para o mais antigo e sinaliza navegação', () => {
  const {context}=frontend();
  context.items=[{contest:21},{contest:23},{contest:22}];
  const ordered=vm.runInContext('historyItemsNewestFirst(items).map(item=>item.contest)',context);
  assert.deepEqual(JSON.parse(JSON.stringify(ordered)),[23,22,21]);
  context.history={index:0}; context.page={next_before:101};
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(resultsHistoryNavigation(history,page))',context)),{latest:false,newer:false,older:true});
  context.history.index=2; context.page.next_before=null;
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(resultsHistoryNavigation(history,page))',context)),{latest:true,newer:true,older:false});
});

test('histórico permite retry de Mais recentes e preserva cursores até a primeira página carregar', async () => {
  const jsonResponse=payload=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const calls=[];
  let attempt=0;
  const fetchImpl=async(url)=>{
    calls.push(url); attempt++;
    if(attempt<3) throw new Error('offline');
    return jsonResponse({items:[{contest:200,draw_date:'01/01/2026',numbers:[1,2,3,4,5,6],second_numbers:[],trevos:[],estimated_prize:0}],from_contest:200,to_contest:200,next_before:null,missing_contests:[],provenance:{recently_checked:true,latest_lookup:'server_fetch'}});
  };
  const latest={disabled:false},newer={disabled:false},older={disabled:false};
  const {context,elements}=frontend({
    '#history-table':{innerHTML:''},'#history-count':{textContent:''},'#history-range':{textContent:''},
    '[data-action="results-latest"]':latest,'[data-action="results-newer"]':newer,'[data-action="results-older"]':older,
  },null,fetchImpl);
  const buttons=[elements['[data-action="results-latest"]'],elements['[data-action="results-newer"]'],elements['[data-action="results-older"]']];
  context.document.querySelectorAll=selector=>selector==='[data-action^="results-"]'?buttons:[];
  const history={game:'lotofacil',limit:100,cursors:[null],index:0,page:null,requestId:0,isLoading:false};
  context.history=history;
  vm.runInContext("state.catalog=[{key:'lotofacil',digits:2,min_pick:15,max_pick:20,pick_size:15,range:{minimum:1,maximum:25}}];state.game='lotofacil';state.page='results';state.resultsHistory=history;",context);

  vm.runInContext("navigateResultsHistory('results-latest')",context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,1);
  assert.equal(history.page,null);
  assert.equal(history.isLoading,false);
  assert.equal(elements['[data-action="results-latest"]'].disabled,false);

  const olderPage={items:[],next_before:25};
  history.cursors=[null,101,51]; history.index=2; history.page=olderPage;
  vm.runInContext("navigateResultsHistory('results-latest')",context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(history.cursors,[null,101,51]);
  assert.equal(history.page,olderPage);
  assert.equal(history.isLoading,false);

  vm.runInContext("navigateResultsHistory('results-latest')",context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,3);
  assert.equal(calls[2].includes('&before='),false);
  assert.equal(history.index,0);
  assert.deepEqual(JSON.parse(JSON.stringify(history.cursors)),[null]);
  assert.equal(history.page.from_contest,200);
  assert.equal(history.isLoading,false);
});

test('fechar a sidebar móvel devolve o foco ao botão somente quando necessário', () => {
  let open=true,focusCalls=0;
  const focusedLink={};
  const outside={};
  const sidebar={classList:{contains:name=>name==='open'&&open,remove:name=>{if(name==='open')open=false;}},contains:element=>element===focusedLink};
  const toggle={focus(){focusCalls++;},setAttribute(name,value){this[name]=value;}};
  const {context,elements}=frontend({'#sidebar':sidebar,'#menu-toggle':toggle});
  const menuButton=elements['#menu-toggle'];
  context.document.activeElement=focusedLink;
  vm.runInContext('closeMobileSidebar()',context);
  assert.equal(open,false);
  assert.equal(focusCalls,1);
  assert.equal(menuButton['aria-expanded'],'false');
  assert.equal(menuButton['aria-label'],'Abrir menu');
  open=true;
  context.document.activeElement=outside;
  vm.runInContext('closeMobileSidebar()',context);
  assert.equal(open,false);
  assert.equal(focusCalls,1);

  const styles=fs.readFileSync(path.join(__dirname,'../static/app.css'),'utf8');
  assert.match(styles,/\.sidebar\{[^}]*position:fixed[^}]*visibility:hidden/);
  assert.match(styles,/\.sidebar\.open\{[^}]*visibility:visible/);
});

test('textos pequenos mantêm contraste mínimo WCAG AA nos fundos claros e escuros', () => {
  const styles=fs.readFileSync(path.join(__dirname,'../static/app.css'),'utf8');
  const color=(selector)=>{
    const match=styles.match(new RegExp(`${selector}\\{[^}]*color:(#[0-9a-f]{3,6})`,'i'));
    assert.ok(match,`não encontrou a cor de ${selector}`);
    return match[1];
  };
  const rgb=hex=>{
    let digits=hex.slice(1);
    if(digits.length===3) digits=[...digits].map(digit=>digit+digit).join('');
    return [0,2,4].map(index=>parseInt(digits.slice(index,index+2),16)/255);
  };
  const luminance=hex=>rgb(hex).map(value=>value<=0.04045?value/12.92:((value+0.055)/1.055)**2.4).reduce((sum,value,index)=>sum+value*[0.2126,0.7152,0.0722][index],0);
  const contrast=(foreground,background)=>{
    const values=[luminance(foreground),luminance(background)].sort((a,b)=>b-a);
    return (values[0]+0.05)/(values[1]+0.05);
  };
  const fieldHelp=color('\\.field-help'),smallNote=color('\\.small-note'),darkSmallNote=color('\\.result-card \\.small-note');
  assert.ok(contrast(fieldHelp,'#fff')>=4.5);
  assert.ok(contrast(smallNote,'#fff')>=4.5);
  assert.ok(contrast(smallNote,'#f5f7f4')>=4.5);
  assert.ok(contrast(darkSmallNote,'#153a2b')>=4.5);
});

test('tela de resultados consome o histórico paginado e informa lacunas', () => {
  const source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  assert.match(source,/\$\('#history-table'\)\.innerHTML=/);
  assert.match(source,/\/\$\{item\.key\}\/history\?limit=\$\{history\.limit\}/);
  assert.match(source,/page\.missing_contests/);
  assert.match(source,/results-latest/);
  assert.match(source,/results-older/);
  assert.match(source,/results-page-size/);
});


test('conta combinações da Lotofácil com fixas e removidas, sem anunciar prêmio', async () => {
  let requested;
  const response = {combination_count:'21', formula_expression:'C(7, 5)', disclaimer:'Contagem, não chance de prêmio.'};
  const {context, elements} = frontend({'#combination-picks':'15','#combination-fixed':'10','#combination-removed':'8','#combination-count-result':''}, null, async (url) => {
    requested=String(url);
    return {ok:true,headers:{get:()=> 'application/json'},json:async()=>response};
  });
  vm.runInContext("state.page='tools'", context);
  await vm.runInContext('calculateCombinationCount({preventDefault(){}})', context);
  assert.match(requested, /\/lotofacil\/combination-count\?pick_count=15&fixed_count=10&removed_count=8/);
  assert.match(elements['#combination-count-result'].innerHTML, /21/);
  assert.match(elements['#combination-count-result'].innerHTML, /C\(7, 5\)/);
  assert.match(elements['#combination-count-result'].innerHTML, /não chance de prêmio/);
});

test('rejeita entradas impossíveis e vazias antes da contagem de combinações', async () => {
  for (const [picks,fixed,removed] of [['15','16','0'],['20','0','6'],['','0','0'],['15','1.5','0']]) {
    const {context,elements,requests}=frontend({'#combination-picks':picks,'#combination-fixed':fixed,'#combination-removed':removed,'#combination-count-result':''});
    vm.runInContext("state.page='tools'", context);
    await vm.runInContext('calculateCombinationCount({preventDefault(){}})', context);
    assert.equal(requests(), 0);
    assert.match(elements['#combination-count-result'].innerHTML, /error-box/);
  }
});

test('+Milionária mostra todas as faixas com quantidades na conferência simples e no CSV', async () => {
  const jsonResponse=payload=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const award_counts={'6 acertos + 2 trevos':1,'5 acertos + 2 trevos':2};
  const {context,elements}=frontend({'#sim-numbers':Array.from({length:6},(_,i)=>i+1).join(' '),'#sim-trevos':'1 2'},null,async()=>jsonResponse({contest:12,draw_date:'23/11/2026',draw:{numbers:[1,2,3,4,5,6],trevos:[1,2]},results:[{ticket_number:1,main_hits:6,trevo_hits:2,award:'6 acertos + 2 trevos',award_counts,award_tiers_overlap:true}]}));
  vm.runInContext("state.catalog=[{key:'maismilionaria',bonus:{type:'trevos'},min_pick:6,max_pick:12,pick_size:6,digits:2,range:{minimum:1,maximum:50}}];state.game='maismilionaria';",context);
  await vm.runInContext('handleSimulate({preventDefault(){}})',context);
  const html=elements['#sim-result'].innerHTML;
  assert.match(html,/6 acertos \+ 2 trevos: 1/);
  assert.match(html,/5 acertos \+ 2 trevos: 2/);
  let csv;
  context.downloadCsv=(filename,rows)=>{csv={filename,rows:JSON.parse(JSON.stringify(rows))};};
  vm.runInContext('downloadSimpleSimulation()',context);
  assert.match(csv.filename,/maismilionaria/);
  assert.match(csv.rows[1][11],/6 acertos \+ 2 trevos: 1/);
  assert.match(csv.rows[1][11],/5 acertos \+ 2 trevos: 2/);
});

test('histórico mostra todas as faixas e preserva fallback do campo award', () => {
  const {context,elements}=frontend({'#batch-result':'','#history-sort':'contest'});
  context.report={game:'maismilionaria',first:1,last:1,tickets:[{ticket_number:1}],officialDraws:[{contest:1,numbers:[1,2,3,4,5,6]}],response:{summary:{},draws:[{contest:1,results:[{ticket_number:1,main_hits:6,award:'faixa legada',award_counts:{'6 acertos':1,'5 acertos':3}}]}]}};
  vm.runInContext('state.historySimulation=report;renderHistorySimulation()',context);
  assert.match(elements['#batch-result'].innerHTML,/6 acertos: 1/);
  assert.match(elements['#batch-result'].innerHTML,/5 acertos: 3/);
  context.legacy={award:'Faixa antiga'};
  assert.equal(vm.runInContext('awardDisplay(legacy)',context),'Faixa antiga');
});

test('probabilidade sobreposta inclui subapostas +Milionária sem somar faixas', () => {
  const {context}=frontend();
  context.tiers=[{label:'Faixa principal',probability:.1,one_in:10}];
  const html=vm.runInContext('renderProbabilityTiers(tiers,true)',context);
  assert.match(html,/subapostas da \+Milionária podem se sobrepor/);
  assert.match(html,/Não some linhas/);
  assert.match(html,/presença do evento no bilhete/);
});

test('edição de qualquer campo da contagem marca a resposta como desatualizada', () => {
  const {context,elements}=frontend({'#combination-count-result':'resultado antigo'});
  vm.runInContext('markCombinationCountStale()',context);
  assert.match(elements['#combination-count-result'].innerHTML,/resultado anterior desatualizado/);
  const source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  assert.match(source,/\['#combination-picks','#combination-fixed','#combination-removed'\]\.forEach\(selector=>\$\(selector\)\.addEventListener\('input',markCombinationCountStale\)\)/);
  assert.match(source,/request!==combinationCountRequest/);
});

test('gerador ignora resposta antiga que chega depois da solicitação mais recente', async () => {
  const pending=[];
  const fetchImpl=(url,options={})=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject}));
  const {context,elements}=frontend({'#game-count':'1','#generated-output':{innerHTML:''}},null,fetchImpl);
  vm.runInContext("state.catalog=[{key:'megasena',name:'Mega-Sena',digits:2,min_pick:6,max_pick:20,pick_size:6,range:{minimum:1,maximum:60}}];state.game='megasena';state.page='generator';",context);
  const older=vm.runInContext('handleGenerate({preventDefault(){}})',context);
  const newer=vm.runInContext('handleGenerate({preventDefault(){}})',context);
  assert.equal(pending.length,2);
  const response=ticketNumber=>({
    ok:true,status:200,headers:{get:()=> 'application/json'},
    json:async()=>({items:[{numbers:[1,2,3,4,5,ticketNumber],ticket_number:ticketNumber,sum:21,even_count:2,odd_count:4,repeated_from_latest:0,probability:{event:'6 acertos',one_in:50063860}}],disclaimer:'Teste.'}),
  });
  pending[1].resolve(response(2));
  await newer;
  pending[0].resolve(response(1));
  await older;
  assert.equal(vm.runInContext('state.generated[0].ticket_number',context),2);
  assert.match(elements['#generated-output'].innerHTML,/Jogo 2/);
  assert.doesNotMatch(elements['#generated-output'].innerHTML,/Jogo 1/);

  const staleFailure=vm.runInContext('handleGenerate({preventDefault(){}})',context);
  const current=vm.runInContext('handleGenerate({preventDefault(){}})',context);
  pending[3].resolve(response(3));
  await current;
  pending[2].reject(new Error('falha de solicitação obsoleta'));
  await staleFailure;
  assert.equal(vm.runInContext('state.generated[0].ticket_number',context),3);
  assert.match(elements['#generated-output'].innerHTML,/Jogo 3/);
  assert.doesNotMatch(elements['#generated-output'].innerHTML,/falha de solicitação obsoleta/);
});

test('gerador expõe dezenas de 6 a 12 e limites de 2 a 6 trevos', async () => {
  const {context,elements}=frontend({'#main-content':''});
  vm.runInContext("state.catalog=[{key:'maismilionaria',name:'+Milionária',range:{minimum:1,maximum:50},min_pick:6,max_pick:12,pick_size:6,draw_size:6,digits:2,bonus:{type:'trevos',minimum:2,maximum:6}}];state.game='maismilionaria';",context);
  await vm.runInContext('renderGenerator()',context);
  assert.match(elements['#main-content'].innerHTML,/<option value="12"[^>]*>12 dezenas<\/option>/);
  assert.match(elements['#main-content'].innerHTML,/Quantidade de trevos/);
  assert.equal(vm.runInContext("maxSimulationPicks({key:'maismilionaria',max_pick:12})",context),12);
});

test('conferência simples envia 12 dezenas e 6 trevos e mostra subapostas premiadas', async () => {
  const calls=[];
  const jsonResponse=payload=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const draw={contest:8,draw_date:'23/11/2026',numbers:[1,2,3,4,5,6],trevos:[1,2]};
  const response={contest:8,draw_date:draw.draw_date,draw,results:[{ticket_number:1,main_hits:6,award_counts:{'Faixa 1 · 6 acertos + 2 trevos':1},subbets_total:13860,winning_subbets:1}]};
  const numbers=Array.from({length:12},(_,index)=>index+1);
  const {context,elements}=frontend({'#sim-numbers':numbers.join(' '),'#sim-trevos':'1 2 3 4 5 6'},null,async(url,options={})=>{calls.push({url,options});return jsonResponse(url.endsWith('/latest')?draw:response);});
  vm.runInContext("state.catalog=[{key:'maismilionaria',bonus:{type:'trevos'},min_pick:6,max_pick:12,pick_size:6,digits:2,range:{minimum:1,maximum:50}}];state.game='maismilionaria';",context);
  await vm.runInContext('handleSimulate({preventDefault(){}})',context);
  const ticket=JSON.parse(calls[1].options.body).tickets[0];
  assert.equal(ticket.numbers.length,12);
  assert.equal(ticket.bonus.trevos.length,6);
  assert.match(elements['#sim-result'].innerHTML,/Subapostas com prêmio: 1 de 13\.860/);
});

test('conferência histórica envia apostas múltiplas com o bônus explicitamente substituído', async () => {
  const calls=[];
  const jsonResponse=payload=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
  const draw={game:'maismilionaria',contest:1,draw_date:'23/11/2026',numbers:[1,2,3,4,5,6],trevos:[1,2]};
  const numbers=Array.from({length:12},(_,index)=>index+1);
  const values={'#batch-numbers':numbers.join(' '),'#batch-from':'1','#batch-to':'1','#batch-result':'','#batch-status':'','#batch-bonus-override':'','#batch-trevos':'1 2 3 4 5 6'};
  const {context,elements}=frontend(values,null,async(url,options={})=>{calls.push({url,options});return url.includes('/history?')?jsonResponse({items:[draw],next_before:null}):jsonResponse({draws:[{contest:1,results:[{ticket_number:1,subbets_total:13860,winning_subbets:1,award_counts:{'Faixa 1 · 6 acertos + 2 trevos':1}}]}],summary:{'Faixa 1 · 6 acertos + 2 trevos':1}});});
  elements['#batch-bonus-override'].checked=true;
  vm.runInContext("state.catalog=[{key:'maismilionaria',bonus:{type:'trevos'},min_pick:6,max_pick:12,pick_size:6,digits:2,range:{minimum:1,maximum:50}}];state.game='maismilionaria';state.page='simulator';",context);
  await vm.runInContext('handleHistoryBatch({preventDefault(){},submitter:{disabled:false}})',context);
  const request=JSON.parse(calls.find(call=>call.url.endsWith('/simulate/history')).options.body);
  assert.equal(request.tickets[0].numbers.length,12);
  assert.equal(request.tickets[0].bonus.trevos.length,6);
  assert.match(elements['#batch-result'].innerHTML,/Subapostas com prêmio: 1 de 13\.860/);
});

test('calculadora solicita probabilidades para 12 dezenas e 6 trevos e mostra o total de subapostas', async () => {
  let requested='';
  const payload={event:'Faixa 1 · ao menos uma subaposta',one_in:100,percent:1,method:'Contagem exata',ticket_subbets:13860,any_prize:{one_in:10,percent:10,favorable_outcomes:'15',total_outcomes:'150'},prize_tiers:[{tier:1,label:'Faixa 1',hits:6,probability:.01,one_in:100,favorable_outcomes:'1',total_outcomes:'100'}],hit_distribution:[],probability_scope:'Contagem exata.'};
  const {context,elements}=frontend({'#prob-picks':'12','#prob-trevos':'6','#prob-result':''},null,async url=>{requested=String(url);return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload};});
  elements['#prob-result'].insertAdjacentHTML=(position,html)=>{elements['#prob-result'].innerHTML+=html;};
  vm.runInContext("state.catalog=[{key:'maismilionaria',bonus:{type:'trevos'},min_pick:6,max_pick:12,pick_size:6,digits:2,range:{minimum:1,maximum:50}}];state.game='maismilionaria';state.page='tools';",context);
  await vm.runInContext('calculateProbability({preventDefault(){}})',context);
  assert.match(requested,/pick_count=12/);
  assert.match(requested,/trevo_count=6/);
  assert.match(elements['#prob-result'].innerHTML,/13\.860 subapostas simples distintas/);
  assert.match(elements['#prob-result'].innerHTML,/Qualquer faixa de prêmio/);
});
