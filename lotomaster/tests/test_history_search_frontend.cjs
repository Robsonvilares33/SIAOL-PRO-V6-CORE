'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
function harness(values={},fetchImpl=async()=>{throw new Error('unexpected network')}) {
  const elements=Object.fromEntries(Object.entries(values).map(([id,value])=>[id,{value,innerHTML:'',textContent:'',isConnected:true,disabled:false}]));
  for(const id of ['#history-number-search-result','#history-number-search-status','#history-number-search-progress','#history-number-search-form'])elements[id]||={value:'',innerHTML:'',textContent:'',isConnected:true,disabled:false,addEventListener(){}};
  elements['#history-number-search-criterion']||={value:'contains_all',innerHTML:'',textContent:'',isConnected:true,disabled:false,addEventListener(){}};
  elements['#history-number-search-form'].querySelector=()=>({disabled:false,isConnected:true});
  const calls=[];
  const context=vm.createContext({window:{addEventListener(){}},document:{querySelector:selector=>elements[selector]||null},AbortController,fetch:async(url,options={})=>{calls.push({url,options});return fetchImpl(url,options);}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8'),context);
  vm.runInContext("state.catalog=[{key:'lotofacil',digits:2,range:{minimum:1,maximum:25}}];state.game='lotofacil';state.page='tools';",context);
  return {context,elements,calls};
}
const json=payload=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>payload});
test('pesquisa usa histórico parcial, informa lacuna e envia concursos carregados',async()=>{
  const draw={game:'lotofacil',contest:2,draw_date:'02/01/2026',numbers:Array.from({length:15},(_,i)=>i+1)};
  const {context,elements,calls}=harness({'#history-number-search-numbers':'1 2 3','#history-number-search-mode':'all'},async(url,options)=>url.includes('/history?')?json({items:[draw],expected_count:2,from_contest:1,to_contest:2,missing_contests:[1],next_before:null}):json({numbers:[1,2,3],match_mode:'contains_all',matching_draws:[draw],match_count:1,examined_count:1,disclaimer:'Origem não verificada; não é previsão.'}));
  await vm.runInContext('runHistoryNumberSearch({preventDefault(){},submitter:null})',context);
  assert.equal(calls.length,2);
  assert.match(calls[0].url,/\/lotofacil\/history\?limit=100/);
  assert.deepEqual(JSON.parse(calls[1].options.body),{numbers:[1,2,3],draws:[draw],match_mode:'contains_all'});
  assert.match(elements['#history-number-search-result'].innerHTML,/Amostra parcial/);
  assert.match(elements['#history-number-search-result'].innerHTML,/1 concurso\(s\) ausente/);
  assert.match(elements['#history-number-search-result'].innerHTML,/Origem não verificada; não é previsão/);
  assert.equal(elements['#history-number-search-status'].textContent,'Concluída');
});
test('entrada inválida rejeitada sem chamadas de rede',async()=>{
  for(const raw of ['', '1 1','0','26','1 x','1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16','1.5']){
    const {context,elements,calls}=harness({'#history-number-search-numbers':raw,'#history-number-search-mode':'50'});
    await vm.runInContext('runHistoryNumberSearch({preventDefault(){}})',context);
    assert.equal(calls.length,0,`requests for ${raw}`);
    assert.match(elements['#history-number-search-result'].innerHTML,/error-box/);
  }
});
test('combinação exata com menos de 15 dezenas é rejeitada antes da rede',async()=>{
  const {context,elements,calls}=harness({'#history-number-search-numbers':'1 2','#history-number-search-mode':'50'});
  elements['#history-number-search-criterion'].value='exact';
  await vm.runInContext('runHistoryNumberSearch({preventDefault(){},submitter:null})',context);
  assert.equal(calls.length,0);
  assert.match(elements['#history-number-search-result'].innerHTML,/exige exatamente 15 dezenas/);
});
test('busca exata envia o critério escolhido ao backend e identifica o resultado',async()=>{
  const draw={game:'lotofacil',contest:2,draw_date:'02/01/2026',numbers:Array.from({length:15},(_,i)=>i+1)};
  const values={'#history-number-search-numbers':Array.from({length:15},(_,i)=>i+1).join(' '),'#history-number-search-mode':'50'};
  const {context,elements,calls}=harness(values,async(url,options)=>url.includes('/history?')?json({items:[draw],expected_count:1,from_contest:2,to_contest:2,missing_contests:[],next_before:null}):json({numbers:draw.numbers,match_mode:'exact',match_description:'combinação exata',matching_draws:[draw],match_count:1,examined_count:1,disclaimer:'Dados históricos.'}));
  elements['#history-number-search-criterion'].value='exact';
  await vm.runInContext('runHistoryNumberSearch({preventDefault(){},submitter:null})',context);
  assert.equal(JSON.parse(calls[1].options.body).match_mode,'exact');
  assert.match(elements['#history-number-search-result'].innerHTML,/combinação exata/);
});
test('valores hostis nos resultados são escapados e a edição invalida a pesquisa sem fetch',()=>{
  const {context,elements,calls}=harness({'#history-number-search-numbers':'1','#history-number-search-mode':'50'});
  context.response={matching_draws:[{contest:'<img src=x onerror=alert(1)>',draw_date:'<SCRIPT>x</SCRIPT>',numbers:[1,2,3]}],match_count:1,examined_count:1,disclaimer:'<b>unsafe</b>'};
  context.complete={complete:false,missingCount:1,periodLabel:'x'};
  const html=vm.runInContext('renderHistoryNumberSearchResult(response,complete)',context);
  assert.doesNotMatch(html,/<img|<script>|<b>unsafe/i);
  assert.match(html,/&lt;img/);
  assert.match(html,/&lt;SCRIPT&gt;/);
  elements['#history-number-search-result'].innerHTML='resultado antigo';
  vm.runInContext("historyNumberSearchController={abort(){globalThis.wasAborted=true}};invalidateHistoryNumberSearch()",context);
  assert.match(elements['#history-number-search-result'].innerHTML,/desatualizado/);
  assert.equal(calls.length,0);
});
test('aviso de probabilidade cobre Dupla Sena e +Milionária',()=>{
  const {context}=harness();
  context.tiers=[{label:'faixa',probability:.1,one_in:10}];
  const html=vm.runInContext('renderProbabilityTiers(tiers,true)',context);
  assert.match(html,/dois sorteios da Dupla Sena/);
  assert.match(html,/bônus e subapostas da \+Milionária/);
});


test('o submit delegado não repete a pesquisa já tratada no formulário',async()=>{
  const {context,calls}=harness({'#history-number-search-numbers':'1','#history-number-search-mode':'50'});
  await vm.runInContext("handleSubmit({target:{id:'history-number-search-form'},preventDefault(){}})",context);
  assert.equal(calls.length,0);
});

test('editar limpa estado e progresso anteriores e desbloqueia o botão',()=>{
  const {context,elements}=harness({'#history-number-search-numbers':'1','#history-number-search-mode':'50'});
  const button={disabled:true,isConnected:true};
  elements['#history-number-search-form button[type="submit"]']=button;
  elements['#history-number-search-status'].textContent='Concluída';
  elements['#history-number-search-progress'].textContent='Examinados 50 concursos';
  vm.runInContext('invalidateHistoryNumberSearch()',context);
  assert.equal(elements['#history-number-search-status'].textContent,'Não iniciada');
  assert.equal(elements['#history-number-search-progress'].textContent,'');
  assert.equal(button.disabled,false);
});
