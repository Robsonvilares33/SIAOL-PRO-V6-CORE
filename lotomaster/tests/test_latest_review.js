'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm'), path=require('node:path'), {spawnSync}=require('node:child_process');
const dir=path.join(__dirname,'..','static');
function bridge(data) { const r=spawnSync(process.env.PYTHON||'python3',[path.join(__dirname,'review_bridge.py')],{input:JSON.stringify(data),encoding:'utf8'}); assert.equal(r.status,0,r.stderr);return JSON.parse(r.stdout); }
function setupFallback(fetch) {
 const store=new Map(), window={};
 const ctx=vm.createContext({window,fetch,localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},URLSearchParams,AbortController,setTimeout,clearTimeout,console});
 vm.runInContext(fs.readFileSync(path.join(dir,'caixa-fallback.js'),'utf8'),ctx); return {window,store};
}
const rules={megasena:[6,1],lotofacil:[15,1],lotomania:[20,0],quina:[5,1],diadesorte:[7,1],duplasena:[6,1],timemania:[7,1],supersete:[7,0],maismilionaria:[6,1]};
function rawFor(game){const [size,min]=rules[game];const numbers=game==='supersete'?[0,0,0,0,0,0,0]:Array.from({length:size},(_,i)=>min+i);const raw={numero:1,listaDezenas:numbers};if(game==='duplasena')raw.listaDezenasSegundoSorteio=[1,2,3,4,5,6]; if(game==='maismilionaria')raw.trevosSorteados=[1,2];if(game==='diadesorte')raw.nomeTimeCoracaoMesSorte='Janeiro';if(game==='timemania')raw.nomeTimeCoracaoMesSorte='Teste FC';return raw;}
test('fallback válido nas nove modalidades e aceito pelo validador backend',async()=>{
 for(const game of Object.keys(rules)){const raw=rawFor(game);const env=setupFallback(async()=>({ok:true,json:async()=>raw}));const draw=await env.window.lotomasterCaixaFallback(`/${game}/latest`);assert.equal(bridge({action:'validate',game,draw}).valid,true,game);assert.equal(env.store.size,1);}
});
test('fallback rejeita resultados inválidos e não os grava; caches antigos também são revalidados',async()=>{
 const cases=[['megasena',{numero:1,listaDezenas:[1,1,2,3,4,99]}], ...Object.keys(rules).map(game=>[game,{...rawFor(game),listaDezenas:[999]}]),['duplasena',{...rawFor('duplasena'),listaDezenasSegundoSorteio:[1,1,2,3,4,5]}],['maismilionaria',{...rawFor('maismilionaria'),trevosSorteados:[1,1]}],['diadesorte',{...rawFor('diadesorte'),nomeTimeCoracaoMesSorte:'inexistente'}],['timemania',{...rawFor('timemania'),nomeTimeCoracaoMesSorte:'  '}],['megasena',{...rawFor('megasena'),dezenasSorteadasOrdemSorteio:[1,2,3,4,5,7]}]];
 for(const [game,raw] of cases){const env=setupFallback(async()=>({ok:true,json:async()=>raw}));await assert.rejects(env.window.lotomasterCaixaFallback(`/${game}/latest`),undefined,game);assert.equal(env.store.size,0,game);}
 const env=setupFallback(async()=>{throw Error('offline')});const bad={game:'megasena',contest:1,numbers:[1,1,2,3,4,99]};env.store.set('lotomaster:caixa:latest:v2:megasena',JSON.stringify(bad));assert.equal(bridge({action:'validate',game:'megasena',draw:bad}).valid,false);await assert.rejects(env.window.lotomasterCaixaFallback('/megasena/latest'));
});
test('fallback preserva separação no time com tabulação e quebra de linha',async()=>{
 const raw={...rawFor('timemania'),nomeTimeCoracaoMesSorte:' SÃO\t\nPAULO  FC '};
 const env=setupFallback(async()=>({ok:true,json:async()=>raw}));
 const draw=await env.window.lotomasterCaixaFallback('/timemania/latest');
 assert.equal(draw.team,'SÃO PAULO FC');
 assert.equal(bridge({action:'validate',game:'timemania',draw}).valid,true);
});
test('campos contraditórios +Milionária são rejeitados, inclusive se sem ordem',async()=>{
 const raw={numero:1,listaDezenas:[1,2,3,4,5,6,1,2],trevosSorteados:[4,5]};const env=setupFallback(async()=>({ok:true,json:async()=>raw}));await assert.rejects(env.window.lotomasterCaixaFallback('/maismilionaria/latest'),/contraditórios/);assert.equal(env.store.size,0);
 raw.trevosSorteados=[2,1];const d=await env.window.lotomasterCaixaFallback('/maismilionaria/latest');assert.equal(bridge({action:'validate',game:'maismilionaria',draw:d}).valid,true);
});
function setupApp(){const elements={'#assistant-ticket':{innerHTML:''},'#assistant-team':{value:''},'#main-content':{innerHTML:''}}; const window={addEventListener(){},LotoMasterAI:{configMarkup:()=>'',bindConfigControls(){}}};const document={querySelector:s=>elements[s],querySelectorAll:()=>[]};const ctx=vm.createContext({window,document,console,setTimeout,clearTimeout});vm.runInContext(fs.readFileSync(path.join(dir,'app.js'),'utf8'),ctx);vm.runInContext("state.catalog=[{key:'timemania',name:'Timemania',digits:2,bonus:{type:'team'}}]; state.game='timemania';state.page='assistant'",ctx);return {ctx,elements};}
test('geração do assistente pede time, valida e envia à API real',async()=>{
 const {ctx,elements}=setupApp();ctx.requests=[];ctx.bridge=bridge;vm.runInContext("api=async (route,options)=>{requests.push(JSON.parse(options.body));let r=bridge({action:'generate',payload:requests.at(-1)});if(r.status!==200)throw Error(JSON.stringify(r.body));return r.body}",ctx);
 await vm.runInContext('renderAssistant()',ctx); assert.match(elements['#main-content'].innerHTML,/id="assistant-team"/);
 await vm.runInContext('generateAssistantTicket()',ctx);assert.equal(ctx.requests.length,0);assert.match(elements['#assistant-ticket'].innerHTML,/Informe o Time/);
 elements['#assistant-team'].value='  Teste FC  ';await vm.runInContext('generateAssistantTicket()',ctx);assert.equal(ctx.requests[0].bonus.team,'Teste FC');assert.match(elements['#assistant-ticket'].innerHTML,/Teste FC/);
 elements['#assistant-team'].value='x'.repeat(101);await vm.runInContext('generateAssistantTicket()',ctx);assert.equal(ctx.requests.length,1);
});
test('histórico sem prova de consulta recente nunca se declara completo e avisa',async()=>{
 for (const provenance of [undefined,{recently_checked:false,latest_lookup:'server_cache'}]) {
  const {ctx}=setupApp();ctx.page={items:[{contest:1}],missing_contests:[],next_before:null,provenance};ctx.progress={textContent:''};vm.runInContext('api=async()=>page',ctx);
  const result=await vm.runInContext("fetchAssistantHistory({key:'megasena'},'all',progress)",ctx);assert.equal(result.complete,false);assert.match(result.warning,/desatualizado/);
  ctx.page={items:[{contest:1}],count:1,expected_count:1,partial:false,provenance};const short=await vm.runInContext("fetchAssistantHistory({key:'megasena'},'50',progress)",ctx);assert.equal(short.complete,false);assert.match(short.warning,/desatualizado/);
 }
});

test('paridade do fallback com backend para casos normalizados inválidos e especiais',async()=>{
 const variants=[
  ['megasena',d=>{d.numbers=[1,1,2,3,4,99]}],['megasena',d=>{d.contest=0}],
  ['megasena',d=>{d.ordered_numbers=[1,2,3,4,5,7]}],['megasena',d=>{d.trevos=[1,2]}],['megasena',d=>{d.special_draw=null}],
  ['duplasena',d=>{d.second_numbers=[1,1,2,3,4,5]}],['duplasena',d=>{d.second_numbers=[]}],
  ['maismilionaria',d=>{d.trevos=[1,7]}],['maismilionaria',d=>{d.ordered_numbers=[1,2,3,4,5,6,1,3]}],
  ['diadesorte',d=>{d.month={name:'Janeiro',number:2}}],['timemania',d=>{d.team='  '}],
  ['supersete',d=>{d.ordered_numbers=[0,0,0,0,0,0,1]}]
 ];
 for(const [game,mutate] of variants){
  const raw=rawFor(game), initial=setupFallback(async()=>({ok:true,json:async()=>raw}));const draw=JSON.parse(JSON.stringify(await initial.window.lotomasterCaixaFallback(`/${game}/latest`)));mutate(draw);
  assert.equal(bridge({action:'validate',game,draw}).valid,false,game);
  const offline=setupFallback(async()=>{throw Error('offline')});offline.store.set(`lotomaster:caixa:latest:v2:${game}`,JSON.stringify(draw));await assert.rejects(offline.window.lotomasterCaixaFallback(`/${game}/latest`),undefined,game);
 }
});
test('cache histórico inválido é descartado antes da exibição e substituído somente por resultado válido',async()=>{
 const env=setupFallback(async url=>({ok:true,json:async()=>({numero:url.endsWith('/1')?1:2,listaDezenas:[1,2,3,4,5,6]})}));
 env.store.set('lotomaster:caixa:history:megasena',JSON.stringify([{game:'megasena',contest:1,numbers:[1,1,2,3,4,99]}]));
 const data=await env.window.lotomasterCaixaFallback('/megasena/results?limit=2');assert.equal(data.count,2);assert.deepEqual(Array.from(data.items[1].numbers),[1,2,3,4,5,6]);assert.deepEqual(JSON.parse(env.store.get('lotomaster:caixa:history:megasena'))[1].numbers,[1,2,3,4,5,6]);
});
