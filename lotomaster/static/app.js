const API = '/api/v1';
const state = {
  catalog: [], game: 'lotofacil', page: 'overview', mode: 'fixed',
  generated: [], closureTickets: [], simulatorText: '', simulatorTickets: [], simulatorBonus: {}, simpleSimulation: null, historySimulation: null, statId: 'frequency', statsPayload: null,
  resultCache: null, resultsHistory: null, lastContests: {}, repeatedDraw: null, repeatedTickets: [],
  closureData: null, repeatedData: null, myGames: [], myGamesFiltered: [], myGameFilters: {}, myGamesError: '',
};
let renderVersion = 0;
let combinationCountRequest = 0;
const pageNames = {
  overview: 'Visão geral', generator: 'Gerador de jogos', simulator: 'Conferir jogos',
  results: 'Resultados', statistics: 'Tabelas e estatísticas', assistant: 'Assistente analítico', tools: 'Outras ferramentas',
};
const months = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
let aiAnalysisController = null;
let historyNumberSearchController = null;
let historyNumberSearchVersion = 0;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function spec() { return state.catalog.find(item => item.key === state.game) || state.catalog[0]; }
function probabilityEvent(item, probability) {
  return item.key === 'diadesorte'
    ? 'Acertar as 7 dezenas sorteadas e o Mês da Sorte'
    : probability.event;
}
function padNum(n, digits=(spec()?.digits || 2)) { return String(n).padStart(digits, '0'); }
function balls(nums, special=false, digits=(spec()?.digits || 2)) {
  if (!Array.isArray(nums) || !nums.length) return '<span class="small-note">Sem dezenas</span>';
  return nums.map(n => `<span class="ball ${special ? 'ball-special' : ''}">${esc(padNum(n,digits))}</span>`).join('');
}
function money(value) {
  const n = Number(value || 0);
  return n ? n.toLocaleString('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:2}) : '—';
}
async function api(path, options={}) {
  const method=(options.method||'GET').toUpperCase();
  try {
    const response = await fetch(`${API}${path}`, {headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) throw new Error(payload?.detail || payload || `Erro HTTP ${response.status}`);
    return payload;
  } catch(error) {
    if (method==='GET' && error?.name!=='AbortError' && window.lotomasterCaixaFallback && !error.recovered) {
      try {
        const recovered=await window.lotomasterCaixaFallback(path);
        if (recovered!==undefined) return recovered;
      } catch(fallbackError) {
        throw new Error(`${error.message} · Consulta da CAIXA via Worker também falhou: ${fallbackError.message}`);
      }
    }
    throw error;
  }
}
function setNotice(message, type='notice') {
  const main = $('#main-content');
  if (!main) return;
  const existing = $('.notice.dynamic-notice', main);
  if (existing) existing.remove();
  if (message) main.insertAdjacentHTML('afterbegin', `<div class="notice ${type==='warning'?'notice-warning':''} dynamic-notice"><span>ⓘ</span><span>${esc(message)}</span></div>`);
}
function toast(message) {
  const el = $('#toast'); el.textContent = message; el.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(()=>el.classList.remove('show'),3200);
}
function renderGameNav() {
  $('#game-nav').innerHTML = state.catalog.map(item => `
    <button class="nav-item game-item ${item.key===state.game?'active':''}" data-game="${esc(item.key)}">
      <span class="nav-icon">${esc(item.name.slice(0,1))}</span>${esc(item.name)}
    </button>`).join('');
  $('#game-picker').innerHTML = state.catalog.map(item => `<option value="${esc(item.key)}" ${item.key===state.game?'selected':''}>${esc(item.name)}</option>`).join('');
}
function pageHeader(eyebrow, title, subtitle, actions='') {
  return `<div class="page-heading"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="heading-actions">${actions}</div></div>`;
}
function resultCard(draw, item=spec()) {
  if (!draw) return `<div class="card result-card"><div class="card-head"><h2 class="card-title">Último resultado · ${esc(item.name)}</h2><span class="pill pill-muted">Sem dados</span></div><div class="empty-state">Ainda não há resultado em cache.</div></div>`;
  const extras = [];
  if (draw.second_numbers?.length) extras.push(`<div class="result-extras">2º sorteio: ${balls(draw.second_numbers,false,item.digits)}</div>`);
  if (draw.trevos?.length) extras.push(`<div class="result-extras">Trevos da Sorte: ${balls(draw.trevos,true,2)}</div>`);
  if (draw.month?.name) extras.push(`<div class="result-extras">Mês da Sorte: <b>${esc(draw.month.name)}</b></div>`);
  if (draw.team) extras.push(`<div class="result-extras">Time do Coração: <b>${esc(draw.team)}</b></div>`);
  const awardCount = (draw.winners_by_tier||[]).reduce((sum,row)=>sum+Number(row.winners||0),0);
  return `<div class="card result-card">
    <div class="card-head"><div><h2 class="card-title">${esc(item.name)} · concurso ${esc(draw.contest)}</h2><div class="result-meta">${esc(draw.draw_date||'Data não informada')} · ${esc(draw.source||'Origem não informada')}</div></div><span class="pill ${draw.accumulated?'pill-warm':'pill-muted'}">${draw.accumulated?'Acumulado':'Apurado'}</span></div>
    <div class="ball-row">${balls(draw.numbers,false,item.digits)}</div>
    ${extras.join('')}
    <div class="result-kpis"><span>Prêmio estimado<b>${esc(money(draw.estimated_prize))}</b></span><span>Próximo acumulado<b>${esc(money(draw.next_prize))}</b></span><span>Ganhadores em faixas<b>${esc(awardCount.toLocaleString('pt-BR'))}</b></span></div>
    ${draw.warning?`<div class="small-note" style="color:#ffe0b0;margin-top:9px">${esc(draw.warning)} · exibindo cache disponível.</div>`:''}
  </div>`;
}
function drawMini(draw, item) {
  const extras = draw.trevos?.length ? ` <span class="small-note">+ ${esc(draw.trevos.map(n=>padNum(n)).join(' · '))}</span>` : '';
  return `<div class="draw-row"><div class="draw-row-main"><div class="draw-title">${esc(item.name)} · concurso ${esc(draw.contest)}</div><div class="draw-caption">${esc(draw.draw_date||'')}</div></div><div class="draw-balls">${balls(draw.numbers)}${extras}</div></div>`;
}
function loading(text='Carregando...') { $('#main-content').innerHTML = `<div class="loading-block"><span class="spinner"></span>${esc(text)}</div>`; }
function errorBlock(message) { return `<div class="error-box">${esc(message)}<div class="small-note">Se houver resultados no cache local, eles continuarão disponíveis. Tente atualizar em alguns instantes.</div></div>`; }

async function render() {
  const version=++renderVersion;
  if (!state.catalog.length) return;
  $('#page-crumb').textContent = pageNames[state.page];
  $$('.section-nav .nav-item').forEach(btn => btn.classList.toggle('active',btn.dataset.page===state.page));
  renderGameNav();
  $('#game-picker').value = state.game;
  if (state.page==='overview') return renderOverview(version);
  if (state.page==='generator') return renderGenerator();
  if (state.page==='simulator') return renderSimulator();
  if (state.page==='results') return renderResults();
  if (state.page==='statistics') return renderStatistics();
  if (state.page==='assistant') return renderAssistant();
  if (state.page==='tools') return renderTools();
}

async function renderOverview(version=renderVersion) {
  loading('Consultando resultados oficiais...');
  const promises = state.catalog.map(item => api(`/${item.key}/latest`).then(data=>({item,data})).catch(error=>({item,error})));
  const rows = await Promise.all(promises);
  rows.forEach(row=>{if(row.data)state.lastContests[row.item.key]=Number(row.data.contest);});
  if (version!==renderVersion || state.page!=='overview') return;
  const active = rows.find(row=>row.item.key===state.game);
  const successful = rows.filter(row=>row.data);
  const cards = successful.map(row=>`<div class="card"><div class="card-head"><div><h3 class="card-title">${esc(row.item.name)}</h3><div class="card-subtitle">Concurso ${esc(row.data.contest)} · ${esc(row.data.draw_date||'')}${row.data.warning?` · ${esc(row.data.warning)} · cache possivelmente desatualizado`:''}</div></div><span class="pill ${row.data.accumulated?'pill-warm':''}">${row.data.accumulated?'Acumulado':'Resultado'}</span></div><div class="ball-row">${balls(row.data.numbers,false,row.item.digits)}${row.data.trevos?.length?balls(row.data.trevos,true,2):''}</div><button class="button button-quiet" data-game="${esc(row.item.key)}" data-page="results">Ver histórico</button></div>`).join('');
  const failed = rows.filter(row=>row.error);
  $('#main-content').innerHTML = `${pageHeader('Painel de concursos','Resultados e estatísticas','Consulte os últimos concursos oficiais e abra as ferramentas disponíveis para cada modalidade.',`<button class="button button-primary" data-page="generator">✦ Gerar jogos</button>`)}
    <div class="grid grid-2" style="margin-bottom:16px">${active?.data?resultCard(active.data,active.item):`<div class="card">${errorBlock(active?.error?.message||'Resultado indisponível.')}</div>`}
      <div class="grid" style="align-content:start"><div class="grid grid-2"><div class="card kpi"><div class="kpi-top"><span>Modalidades disponíveis</span><span class="kpi-icon">▦</span></div><div class="kpi-value">${state.catalog.length}</div><div class="kpi-foot">Loterias oficiais da CAIXA</div></div><div class="card kpi"><div class="kpi-top"><span>Fonte de resultados</span><span class="kpi-icon">↻</span></div><div class="kpi-value" style="font-size:16px">CAIXA</div><div class="kpi-foot">API oficial via Worker; cache local</div></div></div>
      <div class="card"><div class="card-head"><div><h2 class="card-title">Atalhos da modalidade</h2><div class="card-subtitle">Ferramentas correspondentes às páginas públicas da referência</div></div></div><div class="form-actions"><button class="button" data-page="generator">Gerador</button><button class="button" data-page="simulator">Conferir jogos</button><button class="button" data-page="results">Resultados</button><button class="button" data-page="statistics">Estatísticas</button></div></div></div>
    </div><div class="card"><div class="card-head"><div><h2 class="card-title">Resultados recentes por modalidade</h2><div class="card-subtitle">Consulta via Worker e cache; resultados podem estar desatualizados.</div></div><span class="pill">${successful.length} de ${state.catalog.length} disponíveis</span></div><div class="grid grid-3">${cards||'<div class="empty-state">Nenhum resultado retornado.</div>'}</div>${failed.length?`<div class="small-note" style="margin-top:12px">Temporariamente indisponíveis: ${failed.map(row=>esc(row.item.name)).join(', ')}.</div>`:''}</div>
    <div class="notice"><span>ⓘ</span><span><strong>Como interpretar:</strong> frequência, atraso e padrões são descrições de sorteios passados. Cada novo concurso é aleatório e independente; essas métricas não aumentam a probabilidade de um jogo ser sorteado.</span></div>`;
}

function pickGrid(item) {
  const selected = new Set();
  const excluded = new Set();
  return `<div class="card"><div class="card-head"><div><h2 class="card-title">Fixar ou remover dezenas</h2><div class="card-subtitle">Toque nas dezenas e use o modo escolhido. Sem seleção, o jogo é aleatório.</div></div><div class="pick-mode"><button type="button" data-mode="fixed" class="${state.mode==='fixed'?'active':''}">● Fixar</button><button type="button" data-mode="excluded" class="${state.mode==='excluded'?'active':''}">× Remover</button></div></div><div class="legend"><span><i class="fixed"></i>Fixa</span><span><i class="removed"></i>Removida</span><span>Disponíveis ${item.range.minimum}–${item.range.maximum}</span></div><div class="number-grid" id="number-grid">${Array.from({length:item.range.maximum-item.range.minimum+1},(_,i)=>i+item.range.minimum).map(n=>`<button type="button" class="number-cell" data-number="${n}" aria-pressed="false">${esc(padNum(n,item.digits))}</button>`).join('')}</div></div>`;
}
function superSeteGrid() {
  return `<div class="card"><div class="card-head"><div><h2 class="card-title">Seleção por coluna</h2><div class="card-subtitle">Marque os dígitos fixos ou excluídos em cada coluna; por padrão é sorteado um dígito por coluna.</div></div><div class="pick-mode"><button type="button" data-mode="fixed" class="${state.mode==='fixed'?'active':''}">● Fixar</button><button type="button" data-mode="excluded" class="${state.mode==='excluded'?'active':''}">× Remover</button></div></div><div class="col-grid">${Array.from({length:7},(_,i)=>`<div class="col-box"><strong>COLUNA ${i+1}</strong><div class="col-digits">${Array.from({length:10},(_,n)=>`<button type="button" data-column="${i+1}" data-digit="${n}">${n}</button>`).join('')}</div><label class="small-note">Opções <select data-column-pick="${i+1}" aria-label="Quantidade de opções na coluna ${i+1}">${Array.from({length:10},(_,j)=>`<option value="${j+1}" ${j===0?'selected':''}>${j+1}</option>`).join('')}</select></label></div>`).join('')}</div></div>`;
}
function bonusFields(item) {
  if (!item.bonus) return '';
  if (item.bonus.type==='month') return `<div class="field"><label for="bonus-month">Mês da Sorte</label><select id="bonus-month"><option value="">Aleatório</option>${months.map((m,i)=>`<option value="${i+1}">${m}</option>`).join('')}</select></div>`;
  if (item.bonus.type==='team') return `<div class="field"><label for="bonus-team">Time do Coração</label><input id="bonus-team" placeholder="Informe o time para testar" maxlength="80"><span class="field-help">Informe o Time do Coração para gerar um jogo completo e poder conferi-lo.</span></div>`;
  if (item.bonus.type==='trevos') return `<div class="field"><label for="trevo-count">Quantidade de trevos</label><select id="trevo-count">${Array.from({length:5},(_,index)=>index+2).map(count=>`<option value="${count}" ${count===2?'selected':''}>${count} trevos</option>`).join('')}</select><span class="field-help">A +Milionária aceita apostas de 6–12 dezenas e 2–6 trevos; cada bilhete múltiplo equivale a várias apostas simples.</span></div>`;
  return '';
}
function filtersFields() {
  const fields=[['sum','Soma'],['even','Pares'],['repeat','Repetidas do último'],['prime','Primos'],['fibonacci','Fibonacci'],['sequence','Maior sequência consecutiva'],['jumps','Saltos']];
  const controls=fields.map(([key,label])=>`<div class="field"><label for="filter-${key}-min">Mínimo ${label}</label><input id="filter-${key}-min" type="number" min="${key==='sequence'?1:0}" placeholder="Sem limite"></div><div class="field"><label for="filter-${key}-max">Máximo ${label}</label><input id="filter-${key}-max" type="number" min="${key==='sequence'?1:0}" placeholder="Sem limite"></div>`).join('');
  const grid=spec().key==='lotofacil'?['line','column'].map(key=>`<div class="field"><label for="filter-${key}-min">Mínimo por ${key==='line'?'linha':'coluna'} (em cada uma das 5)</label><input id="filter-${key}-min" type="number" min="0" max="5" placeholder="Sem limite"></div><div class="field"><label for="filter-${key}-max">Máximo por ${key==='line'?'linha':'coluna'} (em cada uma das 5)</label><input id="filter-${key}-max" type="number" min="0" max="5" placeholder="Sem limite"></div>`).join(''):'';
  const quadrants=spec().key==='lotomania'?['q1','q2','q3','q4'].map((key,index)=>`<div class="field"><label for="filter-${key}-min">Mínimo Q${index+1} (0–25)</label><input id="filter-${key}-min" type="number" min="0" max="25" placeholder="Sem limite"></div><div class="field"><label for="filter-${key}-max">Máximo Q${index+1} (0–25)</label><input id="filter-${key}-max" type="number" min="0" max="25" placeholder="Sem limite"></div>`).join('')+'<div class="field-help">Lotomania: cada quadrante é um bloco 5×5 da grade 10×10 — Q1 topo esquerdo, Q2 topo direito, Q3 inferior esquerdo e Q4 inferior direito. Filtro estrutural, sem valor preditivo.</div>':'';
  return `<div class="card"><div class="card-head"><div><h2 class="card-title">Filtros e regras</h2><div class="card-subtitle">Critérios próprios: primos e Fibonacci positivos (zero não conta); sequência é o maior grupo consecutivo; saltos são pares vizinhos em ordem cuja diferença é maior que 1. Na Lotofácil, contagens de linha/coluna são aplicadas a cada linha/coluna da grade 5×5. Não foi demonstrada equivalência à MazuSoft.</div></div></div><div class="form-grid">${controls}${grid}${quadrants}</div><div class="field" style="margin-top:12px"><label for="generator-weights">Pesos manuais opcionais</label><input id="generator-weights" placeholder="Ex.: 1:2, 5:3"><span class="field-help">Formato dezena:peso, separados por vírgula; peso positivo. Dezenas não informadas usam peso 1. Altera a seleção, não a chance no sorteio; não equivale aos pesos da MazuSoft.</span></div><div class="field" style="margin-top:12px"><label><input id="generator-pareto" type="checkbox"> Aplicar filtro Pareto histórico (80%)</label><span class="field-help">Restringe a seleção às dezenas que acumulam 80% das aparições nos até 1.000 concursos mais recentes do cache local desta modalidade. Ordem: frequência decrescente, desempate por dezena crescente. É uma descrição retrospectiva, não uma previsão; precisa haver histórico no cache.</span></div></div>`;
}
function generatorParetoField() {
  return `<div class="card"><div class="field"><label><input id="generator-pareto" type="checkbox"> Aplicar filtro Pareto histórico (80%)</label><span class="field-help">Restringe a seleção às dezenas que acumulam 80% das aparições nos até 1.000 concursos mais recentes do cache local desta modalidade. Ordem: frequência decrescente, desempate por dezena crescente. É uma descrição retrospectiva, não uma previsão; precisa haver histórico no cache.</span></div></div>`;
}
async function renderGenerator() {
  const item=spec();
  const pickOptions = item.key==='lotomania' || item.key==='timemania' || item.key==='supersete' ? [item.pick_size] : Array.from({length:item.max_pick-item.min_pick+1},(_,i)=>i+item.min_pick);
  $('#main-content').innerHTML = `${pageHeader('Ferramentas · '+item.name,'Gerador de jogos',`Monte jogos para ${item.name} com dezenas fixas, removidas e filtros opcionais.`)}
    <div class="notice"><span>✦</span><span>O gerador é aleatório. Frequências e filtros servem para organizar seus jogos, não para prever o resultado nem melhorar a probabilidade matemática.</span></div>
    ${item.key==='supersete'?superSeteGrid():pickGrid(item)}
    <form id="generate-form" class="card" style="margin-top:15px"><div class="card-head"><div><h2 class="card-title">Configuração do gerador</h2><div class="card-subtitle">${esc(item.name)} · ${item.draw_size} dezenas sorteadas por concurso</div></div></div><div class="form-grid"><div class="field"><label for="game-count">Quantidade de jogos</label><input id="game-count" type="number" min="1" max="100" value="1"></div>${pickOptions.length>1?`<div class="field"><label for="pick-count">Dezenas no jogo</label><select id="pick-count">${pickOptions.map(n=>`<option value="${n}" ${n===item.pick_size?'selected':''}>${n} dezenas</option>`).join('')}</select></div>`:''}${bonusFields(item)}</div><div class="form-actions"><button class="button button-primary" type="submit">✦ Gerar combinação</button><button class="button" type="button" data-page="tools">Abrir calculadora</button></div><div id="generated-output" style="margin-top:14px"></div></form>
    ${item.key==='supersete'?generatorParetoField():filtersFields()}`;
}
function parseNumberLines(raw) {
  return raw.split(/\n+/).map(line=>line.trim()).filter(Boolean).map(line=>line.split(/[\s,;|]+/).filter(Boolean).map(Number)).filter(row=>row.every(Number.isFinite));
}
function parseStrictNumberLines(raw) {
  const lines=raw.split(/\n+/).map(line=>line.trim()).filter(Boolean);
  const rows=[];
  for (const line of lines) {
    const parts=line.split(/[\s,;|]+/).filter(Boolean);
    if (!parts.length || parts.some(part=>!/^\d+$/.test(part) || !Number.isSafeInteger(Number(part)))) return null;
    rows.push(parts.map(Number));
  }
  return rows;
}
const MY_GAMES_LIMIT=500;
const MY_GAMES_SERIALIZED_CHAR_LIMIT=1_500_000;
function myGamesStorageKey(game) { return `lotomaster.myGames.v1.${game}`; }
function readMyGames(game) {
  const store=globalThis.localStorage;
  if (!store) throw new Error('O armazenamento local deste navegador não está disponível.');
  const raw=store.getItem(myGamesStorageKey(game));
  if (!raw) return [];
  const items=JSON.parse(raw);
  const itemSpec=state.catalog.find(row=>row.key===game);
  if (!Array.isArray(items)||items.length>MY_GAMES_LIMIT||!itemSpec) throw new Error('Os dados de Meus Jogos estão inválidos; nada foi alterado.');
  const ids=new Set();
  for(const ticket of items) {
    if(!ticket||ticket.game!==game||typeof ticket.id!=='string'||!ticket.id||ids.has(ticket.id)||!Array.isArray(ticket.numbers)||!Number.isSafeInteger(ticket.ticket_number)) throw new Error('Os dados de Meus Jogos estão inválidos; nada foi alterado.');
    ids.add(ticket.id);
    const numbers=ticket.numbers;
    if(game==='supersete'?numbers.length!==7:numbers.length<itemSpec.min_pick||numbers.length>maxSimulationPicks(itemSpec)) throw new Error('Há um bilhete local com quantidade inválida; nada foi alterado.');
    if(numbers.some(number=>!Number.isSafeInteger(number)||(game==='supersete'?number<0||number>9:number<itemSpec.range.minimum||number>itemSpec.range.maximum))||(game!=='supersete'&&new Set(numbers).size!==numbers.length)) throw new Error('Há dezenas inválidas em Meus Jogos; nada foi alterado.');
    const bonus=ticket.bonus||{};
    if(itemSpec.bonus?.type==='month'&&bonus.month!==undefined&&(!Number.isInteger(bonus.month)||bonus.month<1||bonus.month>12)) throw new Error('Há um Mês da Sorte inválido em Meus Jogos; nada foi alterado.');
    if(itemSpec.bonus?.type==='team'&&bonus.team!==undefined&&(typeof bonus.team!=='string'||bonus.team.length>80)) throw new Error('Há um Time do Coração inválido em Meus Jogos; nada foi alterado.');
    if(itemSpec.bonus?.type==='trevos'&&(!Array.isArray(bonus.trevos)||bonus.trevos.length<2||bonus.trevos.length>6||new Set(bonus.trevos).size!==bonus.trevos.length||bonus.trevos.some(number=>!Number.isInteger(number)||number<1||number>6))) throw new Error('Há trevos inválidos em Meus Jogos; nada foi alterado.');
  }
  return items;
}
function writeMyGames(game, items) {
  if (!Array.isArray(items)||items.length>MY_GAMES_LIMIT) throw new Error(`Meus Jogos permite até ${MY_GAMES_LIMIT} bilhetes por modalidade.`);
  const serialized=JSON.stringify(items);
  if (serialized.length>MY_GAMES_SERIALIZED_CHAR_LIMIT) throw new Error('O texto dos bilhetes excede o limite local de 1.500.000 caracteres; remova alguns bilhetes e tente novamente.');
  const store=globalThis.localStorage;
  if (!store) throw new Error('O armazenamento local deste navegador não está disponível.');
  store.setItem(myGamesStorageKey(game),serialized);
}
function parseImportBonus(item) {
  if (item.bonus?.type==='month') {
    const value=$('#import-month')?.value||'';
    if (!value) return {};
    const month=Number(value);
    if (!Number.isInteger(month)||month<1||month>12) throw new Error('Escolha um Mês da Sorte válido.');
    return {month};
  }
  if (item.bonus?.type==='team') {
    const team=$('#import-team')?.value.trim()||'';
    if (team.length>80) throw new Error('O Time do Coração deve ter até 80 caracteres.');
    return team?{team}:{};
  }
  if (item.bonus?.type==='trevos') {
    const rows=parseStrictNumberLines($('#import-trevos')?.value||'');
    if (!rows||rows.length!==1||rows[0].length<2||rows[0].length>6||new Set(rows[0]).size!==rows[0].length||rows[0].some(n=>n<1||n>6)) throw new Error('A +Milionária exige de 2 a 6 trevos distintos entre 1 e 6.');
    return {trevos:rows[0]};
  }
  return {};
}
function validateImportedTickets(raw, item, bonus={}) {
  const rawLines=String(raw||'').split(/\n+/).map(line=>line.trim()).filter(Boolean);
  const rows=parseStrictNumberLines(String(raw||''));
  if (!rows||!rawLines.length||rows.length!==rawLines.length) throw new Error('Há uma ou mais linhas inválidas. Informe apenas inteiros; nenhum bilhete foi importado.');
  if (rows.length>MY_GAMES_LIMIT) throw new Error(`Importe no máximo ${MY_GAMES_LIMIT} bilhetes por vez.`);
  const maxPicks=maxSimulationPicks(item);
  const tickets=rows.map((numbers,index)=>{
    if (item.key==='supersete'?numbers.length!==7:numbers.length<item.min_pick||numbers.length>maxPicks) throw new Error(`Linha ${index+1}: ${item.key==='supersete'?'informe exatamente 7 dígitos':`informe de ${item.min_pick} a ${maxPicks} dezenas`}.`);
    if (item.key!=='supersete'&&new Set(numbers).size!==numbers.length) throw new Error(`Linha ${index+1}: não repita dezenas.`);
    if (numbers.some(n=>item.key==='supersete'?n<0||n>9:n<item.range.minimum||n>item.range.maximum)) throw new Error(`Linha ${index+1}: há ${item.key==='supersete'?'dígitos fora de 0–9':`dezenas fora de ${item.range.minimum}–${item.range.maximum}`}.`);
    const ticket={game:item.key,numbers:[...numbers],ticket_number:index+1,bonus:{...bonus},source:'import'};
    if (item.key==='supersete') ticket.columns=numbers.map(n=>[n]);
    return ticket;
  });
  return tickets;
}
function readNumberList(raw, item, label) {
  const rows=parseStrictNumberLines(String(raw||''));
  if (!rows||rows.length!==1) throw new Error(`${label}: informe uma linha de dezenas inteiras distintas.`);
  const values=rows[0];
  if (item.key!=='supersete'&&new Set(values).size!==values.length) throw new Error(`${label}: não repita dezenas.`);
  if (values.some(n=>item.key==='supersete'?n<0||n>9:n<item.range.minimum||n>item.range.maximum)) throw new Error(`${label}: há valores fora do intervalo da modalidade.`);
  return values;
}
function parseMyGamesFilters(item) {
  const value=(id,min,max)=>{
    const raw=$(`#${id}`)?.value.trim()||'';
    if (!raw) return null;
    if (!/^\d+$/.test(raw)||!Number.isSafeInteger(Number(raw))||Number(raw)<min||Number(raw)>max) throw new Error(`${id.replaceAll('-',' ')} deve ser inteiro entre ${min} e ${max}.`);
    return Number(raw);
  };
  const filters={sumMin:value('my-filter-sum-min',0,100000),sumMax:value('my-filter-sum-max',0,100000),evenMin:value('my-filter-even-min',0,100),evenMax:value('my-filter-even-max',0,100)};
  filters.include=($('#my-filter-include')?.value.trim())?readNumberList($('#my-filter-include').value,item,'Incluir'):[];
  filters.exclude=($('#my-filter-exclude')?.value.trim())?readNumberList($('#my-filter-exclude').value,item,'Excluir'):[];
  if (filters.include.some(number=>filters.exclude.includes(number))) throw new Error('Uma dezena não pode estar simultaneamente incluída e excluída.');
  const minRepeated=value('my-filter-repeat-min',0,100), maxRepeated=value('my-filter-repeat-max',0,100);
  filters.repeatMin=minRepeated; filters.repeatMax=maxRepeated;
  const repeatFilter=minRepeated!==null||maxRepeated!==null;
  if (repeatFilter) {
    const contest=value('my-filter-reference-contest',1,10_000_000);
    const drawRaw=$('#my-filter-reference-draw')?.value.trim()||'';
    if (contest===null||!drawRaw) throw new Error('Para filtrar repetidas, informe o concurso e as dezenas de referência. Esse dado fica somente neste navegador e não é verificado pela CAIXA.');
    filters.referenceContest=contest; filters.referenceDraw=readNumberList(drawRaw,item,'Concurso de referência');
  }
  if (filters.sumMin!==null&&filters.sumMax!==null&&filters.sumMin>filters.sumMax) throw new Error('Soma mínima não pode superar a máxima.');
  if (filters.evenMin!==null&&filters.evenMax!==null&&filters.evenMin>filters.evenMax) throw new Error('Mínimo de pares não pode superar o máximo.');
  if (minRepeated!==null&&maxRepeated!==null&&minRepeated>maxRepeated) throw new Error('Mínimo de repetidas não pode superar o máximo.');
  return filters;
}
function filterMyGames(items, filters) {
  return items.filter(ticket=>{
    const numbers=ticket.numbers||[], sum=numbers.reduce((total,n)=>total+n,0), even=numbers.filter(n=>n%2===0).length;
    const repeats=filters.referenceDraw?numbers.filter(n=>filters.referenceDraw.includes(n)).length:null;
    return (filters.sumMin===null||sum>=filters.sumMin)&&(filters.sumMax===null||sum<=filters.sumMax)
      &&(filters.evenMin===null||even>=filters.evenMin)&&(filters.evenMax===null||even<=filters.evenMax)
      &&filters.include.every(number=>numbers.includes(number))&&!filters.exclude.some(number=>numbers.includes(number))
      &&(filters.repeatMin===null||repeats>=filters.repeatMin)&&(filters.repeatMax===null||repeats<=filters.repeatMax);
  });
}
function lotomaniaQuadrantCounts(numbers) {
  const counts={Q1:0,Q2:0,Q3:0,Q4:0};
  for (const number of numbers||[]) {
    const row=Math.floor(Number(number)/10), column=Number(number)%10;
    const quadrant=(row<5?1:3)+(column<5?0:1);
    counts[`Q${quadrant}`]++;
  }
  return counts;
}
function maxSimulationPicks(item) { return item.key==='lotofacil'?23:item.max_pick; }
function ticketsWithBonus(tickets, bonus, replaceBonus=false) {
  return tickets.map(ticket=>({...ticket,bonus:replaceBonus?{...bonus}:{...(ticket.bonus||{})}}));
}
function commonTicketBonus(tickets) {
  if (!tickets.length) return {};
  const first=JSON.stringify(tickets[0].bonus||{});
  return tickets.every(ticket=>JSON.stringify(ticket.bonus||{})===first)?{...(tickets[0].bonus||{})}:{};
}
function historyBonusFields(item) {
  const override='<div class="field"><label><input id="batch-bonus-override" type="checkbox"> Substituir bônus individualmente preservados pelo valor abaixo</label><span class="field-help">Desmarcado, cada jogo mantém seu próprio bônus; marque para aplicar conscientemente o mesmo valor ao lote.</span></div>';
  if (item.bonus?.type==='month') return `${override}<div class="field"><label for="batch-month">Mês da Sorte (substituição do lote)</label><select id="batch-month"><option value="">Não informado</option>${months.map((month,index)=>`<option value="${index+1}">${month}</option>`).join('')}</select></div>`;
  if (item.bonus?.type==='team') return `${override}<div class="field"><label for="batch-team">Time do Coração (substituição do lote)</label><input id="batch-team" maxlength="80" placeholder="Informe o time"></div>`;
  if (item.bonus?.type==='trevos') return `${override}<div class="field"><label for="batch-trevos">Trevos da Sorte (substituição do lote)</label><input id="batch-trevos" placeholder="Ex.: 2, 5"><span class="field-help">Informe de 2 a 6 trevos distintos entre 1 e 6.</span></div>`;
  return '';
}
async function renderSimulator() {
  const item=spec();
  const example=item.key==='supersete'?'3 0 6 6 0 5 4':item.key==='lotofacil'?'01 03 04 06 07 08 09 10 11 13 15 17 19 22 25':Array.from({length:item.pick_size},(_,i)=>padNum(item.range.minimum+i)).join(' ');
  const bonusInput=item.bonus?.type==='month'?`<div class="field"><label for="sim-month">Mês da Sorte (substituição)</label><select id="sim-month"><option value="">Não informado</option>${months.map((m,i)=>`<option value="${i+1}" ${Number(state.simulatorBonus?.month)===i+1?'selected':''}>${m}</option>`).join('')}</select></div>`:item.bonus?.type==='team'?`<div class="field"><label for="sim-team">Time do Coração (substituição)</label><input id="sim-team" placeholder="Nome do time" value="${esc(state.simulatorBonus?.team||'')}"></div>`:item.bonus?.type==='trevos'?`<div class="field"><label for="sim-trevos">Trevos marcados (substituição)</label><input id="sim-trevos" placeholder="Ex.: 2, 5" value="${esc((state.simulatorBonus?.trevos||[]).join(', '))}"></div>`:'';
  const bonusOverride=item.bonus?'<div class="field"><label><input id="sim-bonus-override" type="checkbox"> Substituir os bônus originais por este valor em todos os jogos</label><span class="field-help">Desmarcado: preserva bônus individuais. Marque para substituir explicitamente.</span></div>':'';
  $('#main-content').innerHTML = `${pageHeader('Conferência · '+item.name,'Simulador de jogos',`Compare um ou mais jogos com o resultado consultado mais recente de ${item.name}.`)}
    <div class="grid grid-2"><form id="simulate-form" class="card"><div class="card-head"><div><h2 class="card-title">Seus jogos</h2><div class="card-subtitle">Um jogo por linha; separe as dezenas com espaço, vírgula ou ponto e vírgula.</div></div></div><div class="field"><label for="sim-numbers">Dezenas selecionadas</label><textarea id="sim-numbers" placeholder="${esc(example)}">${esc(state.simulatorText||'')}</textarea><span class="field-help">${item.key==='supersete'?'Informe 7 dígitos em ordem de coluna.':'Você pode colar vários jogos, um por linha.'}</span></div><div class="form-grid" style="margin-top:10px">${bonusOverride}${bonusInput}</div><div class="form-actions"><button class="button button-primary" type="submit">✓ Conferir com o último resultado</button><button class="button" type="button" data-page="results">Abrir histórico</button></div></form><div class="card"><div class="card-head"><div><h2 class="card-title">Como funciona</h2><div class="card-subtitle">Conferência contra o concurso consultado</div></div></div><div class="metric-list"><div class="draw-row"><div class="draw-row-main"><div class="draw-title">1 · Insira seu jogo</div><div class="draw-caption">Use dezenas do intervalo mostrado pela modalidade.</div></div></div><div class="draw-row"><div class="draw-row-main"><div class="draw-title">2 · Compare acertos</div><div class="draw-caption">O sistema informa a quantidade e faixas de acerto.</div></div></div><div class="draw-row"><div class="draw-row-main"><div class="draw-title">3 · Confira na CAIXA</div><div class="draw-caption">A confirmação final de prêmios deve ser feita no portal oficial.</div></div></div></div><div id="sim-result" style="margin-top:14px"></div></div></div>
    <form id="history-batch-form" class="card history-batch-card"><div class="card-head"><div><h2 class="card-title">Conferência histórica em lote</h2><div class="card-subtitle">Compare estes jogos com os concursos de um intervalo numérico.</div></div><span id="batch-status" class="pill pill-muted">Não iniciado</span></div><div class="field"><label for="batch-numbers">Jogos (um por linha)</label><textarea id="batch-numbers" placeholder="${esc(example)}" required></textarea><span class="field-help">Os jogos são usados somente nesta solicitação; não são salvos. Toda linha preenchida precisa ser válida.${item.key==='lotofacil'?' A conferência aceita de 15 a 23 dezenas; o gerador de apostas permanece limitado a 20.':''}</span></div><div class="form-grid" style="margin-top:12px"><div class="field"><label for="batch-from">Concurso inicial</label><input id="batch-from" type="number" min="1" step="1" required></div><div class="field"><label for="batch-to">Concurso final</label><input id="batch-to" type="number" min="1" step="1" required></div>${historyBonusFields(item)}</div><div class="form-actions"><button class="button button-primary" type="submit">Conferir intervalo</button></div><div class="small-note">Os dados obtidos pelo cliente são enviados ao servidor para conferência, sem verificação de origem oficial pelo endpoint. Confirme qualquer premiação diretamente na CAIXA.</div><div id="batch-result" style="margin-top:14px"></div></form>`;
  const contestField=document.createElement('div');
  contestField.className='field';
  contestField.innerHTML='<label for="sim-contest">Concurso (deixe vazio para usar o último)</label><input id="sim-contest" type="number" min="1" step="1" placeholder="Último resultado">';
  $('#simulate-form').insertBefore(contestField,$('#simulate-form .form-actions'));
  $('#simulate-form .card-subtitle').textContent='Compare um ou mais jogos com o último resultado ou informe um concurso específico.';
  $('#simulate-form button[type="submit"]').textContent='✓ Conferir concurso selecionado';
  $('#history-batch-form .form-actions').insertAdjacentHTML('afterbegin','<button type="button" class="button" data-action="fill-all-contests">Preencher todos os concursos disponíveis</button>');
}

async function loadHistoryRange(game, first, last, progress) {
  const byContest=new Map(); let before=last+1; let pages=0;
  while (true) {
    if (pages>=100) throw new Error('O intervalo excede o limite de 10.000 concursos desta consulta. Reduza o período.');
    const page=await api(`/${game}/history?limit=${Math.min(100,last-first+1)}&before=${encodeURIComponent(before)}`);
    (page.items||[]).forEach(draw=>{const c=Number(draw.contest);if(c>=first&&c<=last)byContest.set(c,draw);});
    pages++;
    const next=page.next_before;
    if (next===null||next===undefined||Number(next)<=first) break;
    if (!Number.isInteger(Number(next))||Number(next)>=before) throw new Error('O cursor do histórico retornou um valor inválido.');
    before=Number(next);
    if (progress) progress.textContent=`Histórico consultado: ${byContest.size} de ${last-first+1} concursos localizados…`;
  }
  const draws=[...byContest.values()].sort((a,b)=>Number(a.contest)-Number(b.contest));
  if (!draws.length) throw new Error('Nenhum concurso disponível nesse intervalo.');
  return draws;
}

async function simulateHistoryInChunks(game, tickets, draws, progress) {
  const byContest=new Map(), summary={};
  const drawChunkSize=5000;
  for (let drawStart=0;drawStart<draws.length;drawStart+=drawChunkSize) {
    const drawChunk=draws.slice(drawStart,drawStart+drawChunkSize);
    const ticketChunkSize=Math.max(1,Math.min(500,Math.floor(100000/drawChunk.length)));
    for (let ticketStart=0;ticketStart<tickets.length;ticketStart+=ticketChunkSize) {
      if (progress) progress.textContent=`Conferindo ${Math.min(drawStart+drawChunk.length,draws.length)} de ${draws.length} concursos · jogos ${ticketStart+1}–${Math.min(ticketStart+ticketChunkSize,tickets.length)}…`;
      const response=await api(`/${game}/simulate/history`,{method:'POST',body:JSON.stringify({tickets:tickets.slice(ticketStart,ticketStart+ticketChunkSize),draws:drawChunk})});
      if (!Array.isArray(response.draws)||!response.summary) throw new Error('A resposta do serviço não corresponde ao contrato esperado (draws e summary).');
      for (const [category,count] of Object.entries(response.summary)) summary[category]=(summary[category]||0)+Number(count);
      for (const draw of response.draws) {
        const contest=Number(draw.contest), existing=byContest.get(contest)||{...draw,results:[]};
        existing.results.push(...(Array.isArray(draw.results)?draw.results:[]));
        byContest.set(contest,existing);
      }
    }
  }
  return {draws:[...byContest.values()].sort((a,b)=>Number(a.contest)-Number(b.contest)),summary,evaluated_contests:draws.length,evaluated_tickets:tickets.length};
}

function csvField(value) {
  let text=String(value??'');
  if (/^\s*[=+\-@]/.test(text)) text=`'${text}`;
  return `"${text.replaceAll('"','""')}"`;
}
function downloadCsv(filename, rows) {
  const blob=new Blob(['\uFEFF'+rows.map(row=>row.map(csvField).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob), link=document.createElement('a');
  link.href=url; link.download=filename; link.style.display='none'; document.body.appendChild(link); link.click(); link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function awardDisplay(result) {
  if (result?.award_counts && typeof result.award_counts==='object') {
    const entries=Object.entries(result.award_counts).filter(([,count])=>Number(count)>0);
    const awards=entries.length?entries.map(([label,count])=>`${label}: ${count}`).join(' · '):'Sem faixa de premiação';
    return result.subbets_total===undefined?awards:`${awards} · Subapostas com prêmio: ${Number(result.winning_subbets||0).toLocaleString('pt-BR')} de ${Number(result.subbets_total).toLocaleString('pt-BR')}`;
  }
  return typeof result?.award==='string'?result.award:result?.award?JSON.stringify(result.award):'';
}
function downloadSimpleSimulation() {
  const bundle=state.simpleSimulation; if (!bundle) return;
  const {response,tickets,game}=bundle, draw=response.draw||{};
  const rows=[['Modalidade','Concurso','Data','Dezenas sorteadas','Jogo','Dezenas do jogo','Acertos principais','Acertos 2º sorteio','Acertos de trevos','Mês acertado','Time acertado','Faixa']];
  (response.results||[]).forEach((result,index)=>{
    const ticket=tickets.find(row=>Number(row.ticket_number)===Number(result.ticket_number))||tickets[index]||{};
    rows.push([game,response.contest,response.draw_date,(draw.numbers||[]).join(' '),result.ticket_number,(ticket.numbers||[]).join(' '),result.main_hits??result.hits,result.second_hits,result.trevo_hits,result.month_hit?'sim':'não',result.team_hit?'sim':'não',awardDisplay(result)]);
  });
  downloadCsv(`lotomaster-${game}-conferencia-${response.contest||'resultado'}.csv`,rows);
}
function downloadHistorySimulation() {
  const bundle=state.historySimulation; if (!bundle) return;
  const {response,officialDraws,tickets,game}=bundle;
  const drawMap=new Map(officialDraws.map(draw=>[Number(draw.contest),draw]));
  const ticketMap=new Map(tickets.map(ticket=>[Number(ticket.ticket_number),ticket]));
  const rows=[['Modalidade','Concurso','Data','Dezenas sorteadas','Jogo','Dezenas do jogo','Acertos principais','Acertos 2º sorteio','Acertos de trevos','Mês acertado','Time acertado','Faixa','Origem']];
  for (const draw of response.draws||[]) for (const result of draw.results||[]) {
    const official=drawMap.get(Number(draw.contest))||{}, ticket=ticketMap.get(Number(result.ticket_number))||{};
    rows.push([game,draw.contest,draw.draw_date,(official.numbers||[]).join(' '),result.ticket_number,(ticket.numbers||[]).join(' '),result.main_hits??result.hits,result.second_hits,result.trevo_hits,result.month_hit?'sim':'não',result.team_hit?'sim':'não',awardDisplay(result),'Histórico obtido pelo cliente; origem não autenticada pelo servidor']);
  }
  downloadCsv(`lotomaster-${game}-conferencia-historica.csv`,rows);
}
function renderHistorySimulation() {
  const bundle=state.historySimulation, out=$('#batch-result'); if (!bundle||!out) return;
  const {response,officialDraws,game,first,last}=bundle;
  const order=$('#history-sort')?.value||'contest';
  const draws=[...response.draws];
  const hitScore=draw=>Math.max(0,...(draw.results||[]).map(result=>Number(result.main_hits??result.hits??0)));
  draws.sort(order==='hits'?(a,b)=>hitScore(b)-hitScore(a)||Number(a.contest)-Number(b.contest):(a,b)=>Number(a.contest)-Number(b.contest));
  const summary=Object.entries(response.summary||{}).map(([category,count])=>`<div class="mini-stat"><small>${esc(category)}</small><b>${esc(Number(count).toLocaleString('pt-BR'))}</b></div>`).join('');
  const rows=draws.map(draw=>`<tr><td class="table-number">${esc(draw.contest)}</td><td>${(draw.results||[]).map((result,index)=>{const details=[];if(result.second_hits!==undefined)details.push(`2º sorteio: ${esc(result.second_hits)} acertos`);if(result.month_hit!==undefined)details.push(`Mês da Sorte: ${result.month_hit?'acertou':'não acertou'}`);if(result.team_hit!==undefined)details.push(`Time do Coração: ${result.team_hit?'acertou':'não acertou'}`);if(result.trevo_hits!==undefined)details.push(`Trevos: ${esc(result.trevo_hits)} acerto(s)`);const awards=awardDisplay(result);return `Jogo ${esc(result.ticket_number??index+1)}: ${esc(result.main_hits??result.hits??result.acertos??'—')} acertos${details.length?` · ${details.join(' · ')}`:''}${awards?` · Faixas: ${esc(awards)}`:''}`;}).join('<br>')}</td></tr>`).join('');
  const expected=last-first+1, missing=expected-officialDraws.length;
  out.innerHTML=`<div class="stats-highlight"><div class="mini-stat"><small>Concursos solicitados</small><b>${esc(expected.toLocaleString('pt-BR'))}</b></div><div class="mini-stat"><small>Jogos avaliados</small><b>${esc(response.evaluated_tickets??bundle.tickets.length)}</b></div><div class="mini-stat"><small>Concursos recebidos</small><b>${esc(officialDraws.length.toLocaleString('pt-BR'))}</b></div></div><h3 class="card-title">Totais por categoria</h3><div class="stats-highlight">${summary||'<span class="small-note">Sem totais informados.</span>'}</div><div class="form-actions"><label for="history-sort">Ordenar conferência</label><select id="history-sort"><option value="contest" ${order==='contest'?'selected':''}>Por concurso (crescente)</option><option value="hits" ${order==='hits'?'selected':''}>Por maior número de acertos</option></select><button type="button" class="button" data-action="download-history-report">Baixar relatório CSV</button></div><h3 class="card-title">Acertos por concurso</h3>${rows?`<div class="table-wrap"><table><thead><tr><th>Concurso</th><th>Resultados dos jogos</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<div class="empty-state">Nenhum resultado retornado.</div>'}<div class="small-note">${missing>0?`Aviso: o intervalo solicita ${expected} concursos (${first}–${last}), mas foram recebidos ${officialDraws.length}; há ${missing} lacuna(s) ou indisponibilidade no histórico.`:''} O relatório CSV é gerado no seu dispositivo; nada é salvo pelo servidor. Os dados históricos obtidos pelo cliente não foram verificados quanto à origem oficial pelo servidor. A conferência não confirma premiação: confirme na CAIXA.</div>`;
}

async function fillAllAvailableContestRange() {
  const item=spec(), button=$('[data-action="fill-all-contests"]'), status=$('#batch-status');
  if (button) button.disabled=true;
  try {
    const latest=await api(`/${item.key}/latest`), contest=Number(latest.contest);
    if (!Number.isSafeInteger(contest)||contest<1||contest>10000) throw new Error('O histórico completo desta modalidade ultrapassa o limite local de 10.000 concursos. Escolha um intervalo menor.');
    $('#batch-from').value='1'; $('#batch-to').value=String(contest);
    if (status) status.textContent=`1–${contest} preenchido`;
    toast(`Intervalo preenchido: concurso 1 até ${contest}. Pressione “Conferir intervalo” para iniciar.`);
  } catch(error) {
    if ($('#batch-result')) $('#batch-result').innerHTML=errorBlock(error.message);
  } finally { if (button?.isConnected) button.disabled=false; }
}

async function handleHistoryBatch(event) {
  event.preventDefault(); const item=spec(); const version=renderVersion;
  const out=$('#batch-result'), status=$('#batch-status'), button=event.submitter || event.target.querySelector('button[type="submit"]');
  const invalid=message=>{status.textContent='Inválida';out.innerHTML=`<div class="error-box">${esc(message)}</div>`;};
  const first=Number($('#batch-from').value), last=Number($('#batch-to').value);
  const rawLines=$('#batch-numbers').value.split(/\n+/).map(line=>line.trim()).filter(Boolean);
  const parsed=parseNumberLines($('#batch-numbers').value);
  if (!Number.isInteger(first)||first<1||!Number.isInteger(last)||last<first) {invalid('Informe um intervalo de concursos válido.');return;}
  if (last-first+1>10000) {invalid('O intervalo máximo desta consulta é de 10.000 concursos.');return;}
  if (!rawLines.length) {invalid('Informe ao menos um jogo válido.');return;}
  if (parsed.length!==rawLines.length||rawLines.some(line=>line.split(/[\s,;|]+/).filter(Boolean).some(value=>!/^\d+$/.test(value)))) {invalid('Há uma ou mais linhas com conteúdo inválido. Informe apenas números inteiros; nenhum jogo será omitido.');return;}
  if (parsed.length>500||(last-first+1)*parsed.length>100000) {invalid('O limite é de 500 jogos e 100.000 comparações por consulta. Reduza o lote ou o intervalo.');return;}
  const maxPicks=maxSimulationPicks(item);
  for (let index=0;index<parsed.length;index++) {
    const numbers=parsed[index];
    if (item.key==='supersete'?numbers.length!==7:numbers.length<item.min_pick||numbers.length>maxPicks) {invalid(`Jogo na linha ${index+1}: ${item.key==='supersete'?'informe exatamente 7 dígitos':`informe de ${item.min_pick} a ${maxPicks} dezenas`}.`);return;}
    if (new Set(numbers).size!==numbers.length && item.key!=='supersete') {invalid(`Jogo na linha ${index+1}: não repita dezenas.`);return;}
    if (numbers.some(n=>item.key==='supersete'?n<0||n>9:n<item.range.minimum||n>item.range.maximum)) {invalid(`Jogo na linha ${index+1}: há ${item.key==='supersete'?'dígitos fora de 0–9':`dezenas fora de ${item.range.minimum}–${item.range.maximum}`}.`);return;}
  }
  const bonus={};
  const batchOverride=$('#batch-bonus-override')?.checked===true;
  if (batchOverride&&item.bonus?.type==='month') {const month=$('#batch-month').value;if(!month){invalid('Escolha o mês para substituir os bônus do lote.');return;}bonus.month=Number(month);}
  if (batchOverride&&item.bonus?.type==='team') {const team=$('#batch-team').value.trim();if(!team){invalid('Informe o time para substituir os bônus do lote.');return;}bonus.team=team;}
  if (batchOverride&&item.bonus?.type==='trevos') {
    const rawTrevos=$('#batch-trevos').value.trim(); const trevoLines=rawTrevos.split(/\n+/).map(line=>line.trim()).filter(Boolean); const parsedTrevos=rawTrevos?parseNumberLines(rawTrevos):[]; const trevos=parsedTrevos.flat();
    if (!rawTrevos||parsedTrevos.length!==trevoLines.length) {invalid('A lista de trevos contém uma linha inválida. Informe de 2 a 6 trevos distintos entre 1 e 6.');return;}
    if (trevos.length<2||trevos.length>6||new Set(trevos).size!==trevos.length||trevos.some(n=>!Number.isInteger(n)||n<1||n>6)) {invalid('Informe de 2 a 6 trevos distintos entre 1 e 6.');return;}
    bonus.trevos=trevos;
  }
  const batchPreloaded=state.simulatorTickets.length&&$('#batch-numbers').value===state.simulatorText;
  const baseTickets=parsed.map((numbers,index)=>batchPreloaded?{...state.simulatorTickets[index],numbers,ticket_number:index+1}:{numbers,ticket_number:index+1,...(item.key==='supersete'?{columns:numbers.map(n=>[n])}:{})});
  const tickets=ticketsWithBonus(baseTickets,bonus,batchOverride);
  if (item.key==='maismilionaria'&&tickets.some(ticket=>{const trevos=ticket.bonus?.trevos;return !Array.isArray(trevos)||trevos.length<2||trevos.length>6||new Set(trevos).size!==trevos.length||trevos.some(n=>!Number.isInteger(n)||n<1||n>6);})) {invalid('A +Milionária exige de 2 a 6 trevos distintos por jogo. Informe os trevos e marque a substituição do lote quando os jogos não tiverem bônus preservados.');return;}
  button.disabled=true; status.textContent='Buscando'; out.innerHTML='<div class="loading-block"><span class="spinner"></span>Carregando concursos oficiais…</div>';
  try {
    const draws=await loadHistoryRange(item.key,first,last,out);
    if (version!==renderVersion||state.page!=='simulator'||state.game!==item.key) return;
    status.textContent='Conferindo'; out.innerHTML='<div class="loading-block"><span class="spinner"></span>Comparando jogos e concursos…</div>';
    const response=await simulateHistoryInChunks(item.key,tickets,draws,out);
    if (version!==renderVersion||state.page!=='simulator'||state.game!==item.key) return;
    status.textContent='Concluída';
    state.historySimulation={response,officialDraws:draws,tickets,game:item.key,first,last};
    renderHistorySimulation();
  } catch(error) { if (version===renderVersion) {status.textContent='Falha';out.innerHTML=errorBlock(error.message);} }
  finally { if (button?.isConnected) button.disabled=false; }
}
async function renderResults() {
  const item=spec(); const version=renderVersion;
  if (!state.resultsHistory||state.resultsHistory.game!==item.key) state.resultsHistory={game:item.key,limit:100,cursors:[null],index:0,page:null,requestId:0,isLoading:false};
  const history=state.resultsHistory;
  $('#main-content').innerHTML = `${pageHeader('Histórico · '+item.name,'Resultados dos sorteios',`Consulte o histórico oficial de ${item.name} em páginas; concursos indisponíveis são sinalizados.`,`<a class="button" href="${API}/${item.key}/export.csv?limit=100">↓ Exportar CSV recente</a><a class="button" href="${API}/${item.key}/export.txt?limit=100">↓ Exportar TXT recente</a><a class="button" href="${API}/${item.key}/export.xlsx?limit=100">↓ Exportar Excel recente</a>`)}<div class="card"><div class="card-head"><div><h2 class="card-title">Histórico de concursos</h2><div class="card-subtitle">Navegação do mais recente ao mais antigo · dados públicos consultados sob demanda</div></div><span id="history-count" class="pill">Consultando…</span></div><div class="form-actions" aria-label="Navegação do histórico"><label for="results-page-size">Concursos por página</label><select id="results-page-size"><option value="30" ${history.limit===30?'selected':''}>30</option><option value="50" ${history.limit===50?'selected':''}>50</option><option value="100" ${history.limit===100?'selected':''}>100</option></select><button class="button" type="button" data-action="results-latest">Mais recentes</button><button class="button" type="button" data-action="results-newer">Página mais recente</button><button class="button" type="button" data-action="results-older">Página mais antiga</button></div><div id="history-range" class="small-note" role="status"></div><div id="history-table"><div class="loading-block"><span class="spinner"></span>Buscando concursos...</div></div><div class="small-note">Exportar histórico recente baixa até 100 concursos. A conferência final de prêmios deve ser feita no portal oficial da CAIXA.</div></div>`;
  await loadResultsHistoryPage(version,history.index);
}
function historyItemsNewestFirst(items) {
  return [...(Array.isArray(items)?items:[])].sort((a,b)=>Number(b.contest)-Number(a.contest));
}
function resultsHistoryNavigation(history,page) {
  return {latest:history.index>0,newer:history.index>0,older:page?.next_before!==null&&page?.next_before!==undefined};
}
function renderResultsHistoryPage(item,history,page) {
  const items=historyItemsNewestFirst(page.items);
  const missing=Array.isArray(page.missing_contests)?page.missing_contests:[];
  const provenance=page.provenance||{};
  const sourceLabel=provenance.latest_lookup==='server_fetch'?'consulta via Worker':provenance.latest_lookup==='server_cache'?'cache do servidor':'origem da consulta não identificada';
  const freshnessWarning=page.warning||(provenance.recently_checked===true?'':'A atualização do último concurso não foi verificada; os dados podem estar desatualizados.');
  $('#history-count').textContent=`${items.length} concursos nesta página`;
  $('#history-range').textContent=items.length?`Concursos ${page.from_contest}–${page.to_contest} · ${items.length} encontrado(s)${missing.length?` · ${missing.length} indisponível(is)`:''}`:'Nenhum concurso disponível nesta página.';
  const nav=resultsHistoryNavigation(history,page);
  $('[data-action="results-latest"]').disabled=!nav.latest;
  $('[data-action="results-newer"]').disabled=!nav.newer;
  $('[data-action="results-older"]').disabled=!nav.older||history.isLoading;
  const rows=items.map(draw=>`<tr><td class="table-number">${esc(draw.contest)}</td><td>${esc(draw.draw_date||'')}</td><td>${balls(draw.numbers,false,item.digits)} ${draw.second_numbers?.length?`<div class="small-note">2º sorteio: ${balls(draw.second_numbers,false,item.digits)}</div>`:''}</td><td>${draw.trevos?.length?balls(draw.trevos,true,2):draw.month?.name?esc(draw.month.name):draw.team?esc(draw.team):'—'}</td><td>${draw.accumulated?'<span class="pill pill-warm">Acumulado</span>':'—'}</td><td>${esc(money(draw.estimated_prize))}</td></tr>`).join('');
  const gapNotice=missing.length?`<div class="notice notice-warning"><span>ⓘ</span><span>Não foi possível obter ${missing.length} concurso(s) desta página: ${missing.map(esc).join(', ')}. Tente novamente mais tarde; a ausência não é preenchida com dados inventados.</span></div>`:'';
  const freshnessNotice=freshnessWarning?`<div class="notice notice-warning"><span>ⓘ</span><span>${esc(freshnessWarning)} · exibindo os dados disponíveis; confirme os resultados na CAIXA.</span></div>`:'';
  const provenanceNote=`<div class="small-note">Proveniência: ${esc(sourceLabel)}; autenticidade não verificada independentemente pelo servidor.</div>`;
  $('#history-table').innerHTML=`${freshnessNotice}${gapNotice}${provenanceNote}${rows?`<div class="table-wrap"><table><thead><tr><th>Concurso</th><th>Data</th><th>Dezenas sorteadas</th><th>Complemento</th><th>Status</th><th>Próximo prêmio</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<div class="empty-state">Não foram retornados concursos.</div>'}`;
}
async function loadResultsHistoryPage(version,index) {
  const item=spec(),history=state.resultsHistory;
  if (!history||history.game!==item.key) return;
  const cursor=history.cursors[index];
  if (cursor===undefined) return;
  const requestId=++history.requestId; history.isLoading=true;
  const target=$('#history-table'); if (target) target.innerHTML='<div class="loading-block"><span class="spinner"></span>Buscando concursos desta página...</div>';
  const buttons=$$('[data-action^="results-"]'); buttons.forEach(button=>button.disabled=true);
  try {
    const query=`/${item.key}/history?limit=${history.limit}${cursor===null?'':`&before=${encodeURIComponent(cursor)}`}`;
    const page=await api(query);
    if (version!==renderVersion||state.page!=='results'||state.game!==item.key||state.resultsHistory!==history||history.requestId!==requestId) return;
    history.index=index; history.page=page; history.isLoading=false;
    renderResultsHistoryPage(item,history,page);
  } catch(error) {
    if (version!==renderVersion||state.resultsHistory!==history||history.requestId!==requestId) return;
    history.isLoading=false;
    if ($('#history-table')) $('#history-table').innerHTML=errorBlock(error.message);
    if ($('#history-count')) $('#history-count').textContent='Sem conexão';
    $$('[data-action^="results-"]').forEach(button=>button.disabled=false);
  }
}
function navigateResultsHistory(action) {
  const history=state.resultsHistory;
  if (!history||!history.page||history.isLoading) return;
  if (action==='results-latest') {
    history.cursors=[null];
    loadResultsHistoryPage(renderVersion,0);
    return;
  }
  if (action==='results-newer') {
    if (history.index>0) loadResultsHistoryPage(renderVersion,history.index-1);
    return;
  }
  if (action==='results-older') {
    const next=history.page.next_before;
    if (next===null||next===undefined) return;
    const cursor=Number(next);
    if (!Number.isSafeInteger(cursor)||cursor<1) {toast('O cursor do histórico retornou um valor inválido.');return;}
    let nextIndex=history.index+1;
    if (nextIndex>=history.cursors.length) history.cursors.push(cursor);
    else history.cursors[nextIndex]=cursor;
    loadResultsHistoryPage(renderVersion,nextIndex);
  }
}
function renderValue(value) {
  if (Array.isArray(value)) return value.map(v=>typeof v==='object'?esc(JSON.stringify(v)):esc(v)).join(' · ') || '—';
  if (value && typeof value==='object') return esc(JSON.stringify(value));
  if (typeof value==='number') return esc(value.toLocaleString('pt-BR'));
  return esc(value ?? '—');
}
function statTable(data) {
  if (!data) return '<div class="empty-state">Selecione uma tabela.</div>';
  const rows=data.rows;
  if (Array.isArray(rows)&&rows.length) {
    const columns=Object.keys(rows[0]);
    return `<div class="table-wrap"><table><thead><tr>${columns.map(c=>`<th>${esc(c.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${columns.map(col=>`<td>${renderValue(row[col])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  const values=data.data||{};
  const entries=Object.entries(values);
  if (!entries.length) return `<div class="empty-state">${esc(data.title||'Sem dados disponíveis.')}</div>`;
  return `<div class="grid grid-3">${entries.map(([key,value])=>`<div class="mini-stat"><small>${esc(key.replaceAll('_',' '))}</small><b>${renderValue(value)}</b></div>`).join('')}</div>`;
}
async function renderStatistics() {
  const item=spec();
  const options=item.statistics.map(stat=>`<option value="${esc(stat.id)}" ${stat.id===state.statId?'selected':''}>${esc(stat.label)}</option>`).join('');
  $('#main-content').innerHTML=`${pageHeader('Análise histórica · '+item.name,'Tabelas e estatísticas',`Explore as categorias públicas de análise para ${item.name}.`)}<div class="notice"><span>ⓘ</span><span>Estas métricas são descritivas. Frequência e atraso no passado não tornam uma dezena mais provável no próximo sorteio.</span></div><div class="card"><div class="card-head"><div><h2 class="card-title">Análises da modalidade</h2><div class="card-subtitle">Amostra histórica de até 50 concursos</div></div><span id="stats-count" class="pill">—</span></div><div class="stat-selector"><label class="field-label" for="stat-picker">Tabela</label><select id="stat-picker">${options}</select><button class="button button-primary" id="load-stat">Carregar análise</button></div><div id="stats-highlights"></div><div id="stats-table"><div class="loading-block"><span class="spinner"></span>Calculando estatísticas...</div></div><div class="small-note" style="margin-top:12px">As páginas públicas não especificam todas as fórmulas proprietárias. As análises desta implementação são recálculos descritivos transparentes do histórico consultado.</div></div>`;
  $('#stat-picker').addEventListener('change',e=>state.statId=e.target.value);
  $('#load-stat').addEventListener('click',loadSelectedStat);
  await loadSelectedStat();
}
async function loadSelectedStat() {
  const item=spec(); const version=renderVersion; const container=$('#stats-table');
  if (!container) return;
  container.innerHTML='<div class="loading-block"><span class="spinner"></span>Calculando...</div>';
  try {
    const data=await api(`/${item.key}/statistics?limit=50`);
    if (version!==renderVersion || state.page!=='statistics' || state.game!==item.key) return;
    state.statsPayload=data;
    $('#stats-count').textContent=`${data.draws_analyzed} concursos`;
    setNotice([data.warning, data.partial?'Amostra parcial: nem todos os concursos solicitados estão disponíveis.':''].filter(Boolean).join(' '), 'warning');
    const repeatAvailable=data.tables?.repeats?.data?.latest_comparison_available!==false;
    $('#stats-highlights').innerHTML=`<div class="stats-highlight"><div class="mini-stat"><small>Números analisados</small><b>${esc(data.draws_analyzed)}</b></div><div class="mini-stat"><small>Concurso mais recente</small><b>${esc(data.latest_contest||'—')}</b></div><div class="mini-stat"><small>Repetidas do anterior</small><b>${esc(repeatAvailable?data.repeated_from_previous:'Indisponível')}</b></div><div class="mini-stat"><small>Soma mais recente</small><b>${esc(data.sum?.latest??'—')}</b></div></div>`;
    const id=$('#stat-picker').value; state.statId=id;
    const table=data.tables?.[id];
    container.innerHTML=table?`<h3 class="card-title" style="margin:0 0 12px">${esc(table.title)}</h3>${statTable(table)}`:'<div class="empty-state">Esta tabela ainda não possui cálculo separado. Consulte a análise geral.</div>';
  } catch(error) { container.innerHTML=errorBlock(error.message); }
}
async function renderAssistant() {
  const item=spec(); const version=renderVersion;
  $('#main-content').innerHTML=`${pageHeader('Análise exploratória · '+item.name,'Assistente analítico',`Conecte sua API pessoal para analisar resultados públicos e, se quiser, gerar uma combinação experimental.`)}${window.LotoMasterAI.configMarkup()}<div class="notice notice-warning"><span>ⓘ</span><span>A análise é retrospectiva e não prevê resultados. Concursos futuros só podem ser lidos depois de publicados pela CAIXA; a página verifica atualizações enquanto permanece aberta. O gerador uniforme permanece inalterado.</span></div><form id="ai-analysis-form" class="card"><div class="card-head"><div><h2 class="card-title">Ler resultados oficiais e analisar</h2><div class="card-subtitle">Para calcular estatísticas, o recorte passa pelo backend Lotomaster; após consentimento, ele também é enviado diretamente ao provedor escolhido.</div></div><span id="assistant-status" class="pill pill-muted">Aguardando</span></div><div class="ai-analysis-controls"><div class="field"><label for="ai-history-mode">Período histórico</label><select id="ai-history-mode"><option value="all" selected>Até os 500 concursos mais recentes</option><option value="300">Últimos 300 concursos</option><option value="50">Últimos 50 concursos</option></select></div><button class="button button-primary" type="submit">Analisar com minha IA</button></div><label class="ai-consent"><input id="ai-consent" type="checkbox"><span>Autorizo enviar ao provedor escolhido os resultados públicos da CAIXA e as estatísticas deste recorte para a análise solicitada.</span></label><label class="ai-partial"><input id="ai-allow-partial" type="checkbox"><span>Se alguns concursos estiverem indisponíveis, aceito uma análise parcial claramente identificada.</span></label><div class="small-note ai-progress" id="ai-progress">O recorte é carregado em páginas de até 100 concursos, com limite de 500 por análise. Se houver concursos anteriores, eles ficarão de fora.</div><div id="assistant-content"><div class="empty-state">Configure uma API, marque o consentimento e solicite uma análise.</div></div></form><div class="card" style="margin-top:16px"><div class="card-head"><div><h2 class="card-title">Gerador uniforme (baseline)</h2><div class="card-subtitle">Esta combinação é aleatória e independente da análise histórica; cada jogo legal conserva suas chances teóricas.</div></div></div>${item.key==='timemania'?'<div class="field"><label for="assistant-team">Time do Coração</label><input id="assistant-team" maxlength="100" required placeholder="Informe seu time"></div>':''}<div class="form-actions"><button class="button button-primary" data-action="assistant-generate">Montar combinação aleatória</button></div><div id="assistant-ticket"></div></div>`;
  if (version!==renderVersion || state.page!=='assistant') return;
  window.LotoMasterAI.bindConfigControls();
  $('#ai-consent')?.addEventListener('change', event=>{if(!event.currentTarget.checked)aiAnalysisController?.abort();});
}

function validateAssistantHistoryPage(page, pageLimit, seenDraws, seenMissing) {
  if (!page || typeof page!=='object' || !Array.isArray(page.items)) throw new Error('O histórico retornou uma página inválida.');
  const expected=Number(page.expected_count);
  if (!Number.isSafeInteger(expected)||expected<0||expected>pageLimit) throw new Error('O histórico retornou metadados de página inválidos.');
  const hasFrom=page.from_contest!==null&&page.from_contest!==undefined;
  const hasTo=page.to_contest!==null&&page.to_contest!==undefined;
  if (hasFrom!==hasTo) throw new Error('O histórico retornou limites de concursos incompletos.');
  let from=null, to=null;
  if (hasFrom) {
    from=Number(page.from_contest); to=Number(page.to_contest);
    if (!Number.isSafeInteger(from)||!Number.isSafeInteger(to)||from<1||to<from||to-from+1!==expected) throw new Error('O intervalo de concursos da página não corresponde à quantidade informada.');
  }
  const rows=[], localDraws=new Set();
  for (const draw of page.items) {
    const contest=Number(draw?.contest);
    if (!Number.isSafeInteger(contest)||contest<1||(hasFrom&&(contest<from||contest>to))) throw new Error('O histórico retornou um concurso fora do intervalo esperado.');
    if (localDraws.has(contest)||seenDraws.has(contest)) throw new Error(`O histórico retornou o concurso ${contest} mais de uma vez.`);
    localDraws.add(contest); rows.push(draw);
  }
  const reported=page.missing_contests??[];
  if (!Array.isArray(reported)) throw new Error('A lista de concursos indisponíveis é inválida.');
  const missing=new Set();
  for (const value of reported) {
    const contest=Number(value);
    if (!Number.isSafeInteger(contest)||contest<1||(hasFrom&&(contest<from||contest>to))) throw new Error('A lista de concursos indisponíveis contém um número inválido.');
    if (missing.has(contest)||localDraws.has(contest)||seenDraws.has(contest)||seenMissing.has(contest)) throw new Error(`Os metadados do concurso ${contest} são inconsistentes.`);
    missing.add(contest);
  }
  if (expected<rows.length+missing.size) throw new Error('A página informa menos concursos esperados do que os itens recebidos.');
  if (hasFrom) {
    for (let contest=from;contest<=to;contest++) if (!localDraws.has(contest)) missing.add(contest);
  }
  const unreported=Math.max(0,expected-rows.length-missing.size);
  return {expected,rows,missing,unreported};
}

async function fetchAssistantHistory(item, mode, progress, signal) {
  const isRecentMode=mode!=='all';
  const limit=isRecentMode?Number(mode):500;
  if (!Number.isSafeInteger(limit)||![50,300,500].includes(limit)) throw new Error('Selecione 50, 300 ou até 500 concursos.');
  const byContest=new Map(); const missing=new Set(); let unreported=0; let before=null; let expectedCount=0; let pages=0; let hasMore=true; let warning=null; let recentlyChecked=true;
  const pageBudget=Math.ceil(limit/100);
  while (hasMore && expectedCount<limit && pages<pageBudget) {
    const pageLimit=Math.min(100,limit-expectedCount);
    const cursor=before===null?'':`&before=${encodeURIComponent(before)}`;
    const page=await api(`/${item.key}/history?limit=${pageLimit}${cursor}`,{signal});
    if (page.warning) warning=page.warning;
    if (pages===0 && page.provenance?.recently_checked!==true) {
      recentlyChecked=false;
      warning ||= 'Atualização do último concurso não foi verificada nesta consulta; o histórico pode estar desatualizado.';
    }
    const checked=validateAssistantHistoryPage(page,pageLimit,new Set(byContest.keys()),missing);
    checked.rows.forEach(draw=>byContest.set(Number(draw.contest),draw));
    checked.missing.forEach(contest=>missing.add(contest));
    unreported+=checked.unreported; expectedCount+=checked.expected; pages++;
    hasMore=page.next_before!==null&&page.next_before!==undefined;
    if (hasMore&&checked.expected===0) throw new Error('O cursor do histórico avançou sem concursos esperados.');
    if (hasMore) {
      const next=Number(page.next_before);
      if (!Number.isSafeInteger(next)||next<1||(before!==null&&next>=before)) throw new Error('O cursor do histórico retornou um valor inválido.');
      before=next;
    }
    progress.textContent=`Carregando recorte da CAIXA: ${byContest.size} concursos recebidos · ${missing.size} indisponível(is)`;
  }
  if (hasMore&&expectedCount<limit) throw new Error('O recorte excedeu o limite de 500 concursos desta análise.');
  const draws=[...byContest.values()].sort((a,b)=>Number(b.contest)-Number(a.contest));
  const missingCount=Math.max(missing.size+unreported,expectedCount-draws.length,0);
  const includesFirst=draws.some(draw=>Number(draw.contest)===1);
  const complete=missingCount===0&&draws.length===expectedCount;
  const archiveComplete=complete&&includesFirst&&!warning&&recentlyChecked;
  const periodLabel=isRecentMode
    ? (hasMore?`Últimos ${expectedCount} concursos numerados`:`Histórico desde o concurso 1 · ${expectedCount} concursos`)
    : (hasMore?`Recorte dos até ${limit} concursos mais recentes · histórico anterior não incluído`:`Histórico desde o concurso 1 · ${expectedCount} concursos`);
  return {draws,warning,missingCount,complete,archiveComplete,expectedCount,periodLabel,recentlyChecked};
}
function renderAssistantAnalysis(result, item, draws, completeness, stats, probability) {
  const content=$('#assistant-content');
  const observations=(result.observations||[]).map(text=>`<li>${esc(text)}</li>`).join('');
  const candidate=result.candidate_numbers;
  const candidateHtml=candidate?`<div class="ai-ticket"><div class="generated-ticket-head"><b>Sugestão experimental da IA · ${esc(item.name)}</b><span class="pill pill-warm">Sem vantagem demonstrada</span></div><div class="ball-row">${balls(candidate,false,item.digits)}</div><div class="small-note">${esc(result.candidate_note||'Combinação exploratória, não é previsão nem altera a probabilidade teórica.')} ${item.bonus?.type==='team'?'Escolha também o Time do Coração na conferência.':item.bonus?.type==='month'?'Escolha também o Mês da Sorte na conferência.':item.bonus?.type==='trevos'?'Escolha também os trevos na conferência.':''}</div><div class="form-actions"><button type="button" class="button" data-action="ai-use-candidate" data-numbers="${esc(JSON.stringify(candidate))}">Conferir esta sugestão</button></div></div>`:'<div class="small-note">A resposta não forneceu uma combinação válida conforme as regras oficiais; nenhuma combinação foi exibida.</div>';
  const probabilityHtml=probability?`<div class="card" style="margin-top:12px"><h3 class="card-title">Probabilidades calculadas pelo motor combinatório</h3><div class="stats-highlight"><div class="mini-stat"><small>${esc(probability.event)}</small><b>Aprox. 1 em ${esc(Number(probability.one_in).toLocaleString('pt-BR'))}</b><small>${esc(Number(probability.percent).toExponential(3))}%</small>${renderExactOutcomes(probability)}</div>${probability.any_prize?`<div class="mini-stat"><small>Qualquer categoria de prêmio</small><b>Aprox. 1 em ${esc(Number(probability.any_prize.one_in).toLocaleString('pt-BR'))}</b><small>${esc(Number(probability.any_prize.percent).toExponential(3))}%</small>${renderExactOutcomes(probability.any_prize)}</div>`:''}</div><div class="small-note">Contagem combinatória teórica do jogo-base da modalidade; o histórico não altera estas chances. A IA apenas recebe estes valores calculados, não os estima.</div></div>`:'';
  const scope=completeness.complete?completeness.periodLabel:`análise parcial · ${completeness.missingCount} concurso(s) indisponível(is)`;
  content.innerHTML=`${completeness.warning?`<div class="notice notice-warning">${esc(completeness.warning)} · o histórico pode estar desatualizado.</div>`:""}<div class="stats-highlight"><div class="mini-stat"><small>Concursos recebidos</small><b>${esc(draws.length.toLocaleString('pt-BR'))}</b></div><div class="mini-stat"><small>Mais recente</small><b>${esc(stats.latest_contest||'—')}</b></div><div class="mini-stat"><small>Escopo</small><b>${esc(scope)}</b></div></div>${probabilityHtml}<h3 class="card-title">Leitura da IA</h3><p class="ai-output">${esc(result.analysis||'O provedor não apresentou um resumo interpretável.')}</p>${observations?`<h3 class="card-title" style="margin-top:14px">Observações do modelo</h3><ul class="ai-observations">${observations}</ul>`:''}${candidateHtml}<div class="notice"><span>ⓘ</span><span>Frequência, atraso, vizinhança e áreas quentes/frias são descrições do histórico, não probabilidades ou previsões. Mesmo uma anomalia aparente não demonstra manipulação nem vantagem futura. ${esc(stats.disclaimer||'')}</span></div>`;
}

async function runPersonalAIAnalysis(event) {
  event.preventDefault();
  const config=window.LotoMasterAI.getConfig();
  const item=spec(); const version=renderVersion;
  const status=$('#assistant-status'); const output=$('#assistant-content'); const progress=$('#ai-progress');
  if (!config?.key) { output.innerHTML=errorBlock('Salve primeiro sua própria configuração de API.'); return; }
  if (!$('#ai-consent')?.checked) { output.innerHTML=errorBlock('Marque o consentimento para enviar os resultados públicos ao provedor escolhido.'); return; }
  const controller=new AbortController(); aiAnalysisController=controller; let providerStarted=false;
  const requireConsent=()=>{if(controller.signal.aborted||!$('#ai-consent')?.checked){controller.abort();const error=new Error('O consentimento foi retirado; análise cancelada.');error.name='AbortError';throw error;}};
  const mode=$('#ai-history-mode').value;
  const allowPartial=$('#ai-allow-partial').checked;
  const submit=event.submitter;
  if (submit) submit.disabled=true;
  status.textContent='Carregando';
  output.innerHTML='<div class="loading-block"><span class="spinner"></span>Buscando resultados oficiais da CAIXA...</div>';
  try {
    const completeness=await fetchAssistantHistory(item,mode,progress,controller.signal);
    requireConsent();
    if (version!==renderVersion || state.page!=='assistant' || state.game!==item.key) return;
    if (!completeness.draws.length) throw new Error('Não há concursos disponíveis para esta análise.');
    if (!completeness.complete && !allowPartial) throw new Error(`Não foi possível obter ${completeness.missingCount} concurso(s). Marque a opção de análise parcial se desejar continuar; a IA não será chamada sem essa escolha.`);
    status.textContent='Calculando';
    progress.textContent=`Calculando estatísticas descritivas de ${completeness.draws.length.toLocaleString('pt-BR')} concursos; a seguir os dados serão enviados ao provedor selecionado.`;
    const drawsForStats=completeness.draws.map(({game,contest,numbers,second_numbers,trevos,ordered_numbers,month,team,special_draw})=>({game,contest,numbers,second_numbers,trevos,ordered_numbers,month,team,special_draw}));
    const stats=await api(`/${item.key}/statistics/from-draws`,{method:'POST',body:JSON.stringify({draws:drawsForStats}),signal:controller.signal});
    requireConsent();
    if (version!==renderVersion || state.page!=='assistant' || state.game!==item.key) return;
    const probability=await api(`/${item.key}/probability`,{signal:controller.signal});
    requireConsent();
    if (version!==renderVersion || state.page!=='assistant' || state.game!==item.key) return;
    status.textContent=`${config.model}`;
    progress.textContent=`Enviando diretamente a ${config.model} em ${config.provider}; nenhum segredo passa pelo backend do site.`;
    requireConsent(); providerStarted=true;
    const result=await window.LotoMasterAI.analyze(config,item,stats,completeness.draws,completeness,probability,controller.signal);
    if (version!==renderVersion || state.page!=='assistant' || state.game!==item.key) return;
    renderAssistantAnalysis(result,item,completeness.draws,completeness,stats,probability);
    status.textContent='Concluída';
    progress.textContent=`Fonte: histórico consultado via Worker e/ou cache; não verificado independentemente. ${completeness.warning?"Último concurso pode estar desatualizado. ":""}${completeness.draws.length.toLocaleString('pt-BR')} concursos enviados; janela ${completeness.draws.at(-1)?.contest||'—'}–${completeness.draws[0]?.contest||'—'}.`;
  } catch(error) {
    if (version!==renderVersion) return;
    if (error?.name==='AbortError') {
      status.textContent='Cancelada';
      const detail=providerStarted?'A autorização foi retirada e a solicitação foi interrompida; uma chamada já iniciada ainda pode ter sido recebida pelo provedor.':'A autorização foi retirada antes do envio ao provedor; a análise foi interrompida.';
      output.innerHTML=`<div class="notice notice-warning"><span>ⓘ</span><span>${esc(detail)}</span></div>`;
    } else {
      status.textContent='Não concluída';
      output.innerHTML=errorBlock(error.message);
    }
  } finally {
    if (aiAnalysisController===controller) aiAnalysisController=null;
    if (submit && submit.isConnected) submit.disabled=false;
  }
}

function savePersonalAIConfig() {
  try {
    const config=window.LotoMasterAI.saveFromForm();
    $('#ai-config-status').textContent=`Configurada · ${config.model}`;
    $('#ai-config-status').classList.remove('pill-muted');
    $('#ai-key').value='';
    toast(config.persistent?'Configuração guardada neste dispositivo':'Configuração guardada nesta aba');
  } catch(error) { toast(error.message); }
}

async function testPersonalAIConfig() {
  const button=$('[data-action="ai-test"]');
  try {
    const config=window.LotoMasterAI.saveFromForm();
    if (button) button.disabled=true;
    const status=$('#ai-config-status'); status.textContent='Testando';
    const result=await window.LotoMasterAI.testConnection(config);
    status.textContent=result.textReceived?`Conectada · ${config.model}`:`API respondeu · sem texto`;
    status.classList.remove('pill-muted');
    toast(result.textReceived?'API conectada e retornou texto; nenhum histórico foi enviado':'API alcançada, mas sem texto; análise generativa ainda não confirmada. Nenhum histórico foi enviado.');
    $('#ai-key').value='';
  } catch(error) {
    const status=$('#ai-config-status'); if(status) status.textContent='Falha na conexão';
    toast(error.message);
  } finally { if(button) button.disabled=false; }
}
async function generateAssistantTicket() {
  const item=spec(); const target=$('#assistant-ticket');
  if (!target) return;
  target.innerHTML='<div class="loading-block"><span class="spinner"></span>Gerando combinação aleatória...</div>';
  try {
    const payload={count:1};
    if (item.key==='timemania') {
      const team=$('#assistant-team')?.value?.trim() || '';
      if (!team || team.length>100) throw new Error('Informe o Time do Coração (até 100 caracteres).');
      payload.bonus={team};
    }
    const data=await api(`/${item.key}/generate`,{method:'POST',body:JSON.stringify(payload)});
    const ticket=data.items[0];
    target.innerHTML=`<div class="generated-ticket"><div class="generated-ticket-head"><b>Jogo aleatório</b><span class="pill">Sem ponderação histórica</span></div>${item.key==='supersete'?`<div class="col-grid">${ticket.columns.map((values,index)=>`<div class="col-box"><strong>COLUNA ${index+1}</strong>${balls(values)}</div>`).join('')}</div>`:`<div class="ball-row">${balls(ticket.numbers,false,item.digits)}</div>`}${ticket.bonus?.team?`<div class="ticket-stats">Time do Coração: ${esc(ticket.bonus.team)}</div>`:''}<div class="ticket-stats">${esc(probabilityEvent(item,ticket.probability))}: 1 em ${esc(Number(ticket.probability.one_in).toLocaleString('pt-BR'))}</div><div class="small-note">${esc(data.disclaimer)}</div></div>`;
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
function invalidateHistoryNumberSearch(message='Resultado anterior desatualizado; pesquise novamente.') {
  historyNumberSearchVersion++;
  if (historyNumberSearchController) historyNumberSearchController.abort();
  historyNumberSearchController=null;
  const target=$('#history-number-search-result');
  if (target && target.innerHTML) target.innerHTML=`<div class="small-note">${esc(message)}</div>`;
  const status=$('#history-number-search-status'), progress=$('#history-number-search-progress'), button=$('#history-number-search-form button[type="submit"]');
  if (status) status.textContent='Não iniciada';
  if (progress) progress.textContent='';
  if (button) button.disabled=false;
}
function renderHistoryNumberSearchResult(response, completeness) {
  const missing=Number(completeness.missingCount||0);
  const scope=completeness.complete?esc(completeness.periodLabel):`Amostra parcial: ${esc(missing.toLocaleString('pt-BR'))} concurso(s) ausente(s) ou indisponível(is); não representa necessariamente todo o histórico.`;
  const matches=Array.isArray(response.matching_draws)?response.matching_draws:[];
  const mode=response.match_mode||'contains_all';
  const criterion=response.match_description||({contains_all:'Concursos contendo todas as dezenas selecionadas',exact:'Combinação exata',excludes_all:'Concursos que não contêm nenhuma das dezenas selecionadas'}[mode]||'Pesquisa histórica');
  const rows=matches.slice(0,100).map(draw=>`<div class="draw-row"><div class="draw-row-main"><div class="draw-title">Lotofácil · concurso ${esc(draw.contest)}</div><div class="draw-caption">${esc(draw.draw_date||'Data não informada')}</div></div><div class="draw-balls">${balls(draw.numbers,false,2)}</div></div>`).join('');
  return `<div class="stats-highlight"><div class="mini-stat"><small>Concursos examinados</small><b>${esc(Number(response.examined_count||0).toLocaleString('pt-BR'))}</b></div><div class="mini-stat"><small>Correspondências</small><b>${esc(Number(response.match_count||0).toLocaleString('pt-BR'))}</b></div><div class="mini-stat"><small>Escopo</small><b>${scope}</b></div></div><h3 class="card-title">${esc(criterion)}</h3>${rows||'<div class="empty-state">Nenhum concurso correspondente nesta amostra.</div>'}${matches.length>100?`<div class="small-note">Exibindo 100 de ${esc(matches.length)} resultados encontrados.</div>`:''}<div class="small-note">${esc(response.disclaimer||'Os dados enviados pelo navegador têm origem não verificada pelo servidor. A coocorrência histórica não é previsão de sorteios futuros.')}</div>`;
}
async function runHistoryNumberSearch(event) {
  event.preventDefault();
  const version=++historyNumberSearchVersion, item=spec();
  const output=$('#history-number-search-result'), status=$('#history-number-search-status'), button=event.submitter||$('#history-number-search-form button[type="submit"]');
  const invalid=message=>{status.textContent='Entrada inválida';output.innerHTML=`<div class="error-box">${esc(message)}</div>`;};
  const raw=$('#history-number-search-numbers').value.trim();
  const parts=raw?raw.split(/[\s,;|]+/):[];
  if (!parts.length||parts.some(part=>!/^[0-9]+$/.test(part)||!Number.isSafeInteger(Number(part)))) {invalid('Informe de 1 a 15 dezenas inteiras, separadas por espaço, vírgula ou ponto e vírgula.');return;}
  const numbers=parts.map(Number);
  if(numbers.length>15||numbers.some(n=>n<1||n>25)||new Set(numbers).size!==numbers.length){invalid('Use de 1 a 15 dezenas distintas, cada uma entre 1 e 25.');return;}
  const matchMode=$('#history-number-search-criterion').value;
  if(!['contains_all','exact','excludes_all'].includes(matchMode)){invalid('Selecione um critério de pesquisa válido.');return;}
  if(matchMode==='exact'&&numbers.length!==15){invalid('A combinação exata da Lotofácil exige exatamente 15 dezenas.');return;}
  const mode=$('#history-number-search-mode').value;
  if(!['50','300','all'].includes(mode)){invalid('Selecione uma janela válida.');return;}
  const controller=new AbortController(); historyNumberSearchController=controller;
  if(button)button.disabled=true;
  status.textContent='Carregando histórico';
  output.innerHTML='<div class="loading-block"><span class="spinner"></span>Carregando concursos históricos…</div>';
  const progress={set textContent(value){if(version===historyNumberSearchVersion&&$('#history-number-search-progress'))$('#history-number-search-progress').textContent=value;}};
  try {
    const completeness=await fetchAssistantHistory(item,mode,progress,controller.signal);
    if(version!==historyNumberSearchVersion||controller.signal.aborted||state.page!=='tools'||state.game!=='lotofacil')return;
    if(!completeness.draws.length)throw new Error('Nenhum concurso disponível para examinar.');
    status.textContent='Pesquisando';
    const response=await api('/lotofacil/history-number-search',{method:'POST',body:JSON.stringify({numbers,draws:completeness.draws,match_mode:matchMode}),signal:controller.signal});
    if(version!==historyNumberSearchVersion||controller.signal.aborted||state.page!=='tools'||state.game!=='lotofacil')return;
    if(!Array.isArray(response.matching_draws)||!Number.isSafeInteger(Number(response.examined_count))||!Number.isSafeInteger(Number(response.match_count)))throw new Error('Resposta de pesquisa incompatível com o contrato esperado.');
    output.innerHTML=renderHistoryNumberSearchResult(response,completeness);
    status.textContent='Concluída';
    if($('#history-number-search-progress'))$('#history-number-search-progress').textContent=`Examinados ${completeness.draws.length.toLocaleString('pt-BR')} concursos${completeness.missingCount?` · ${completeness.missingCount.toLocaleString('pt-BR')} ausente(s)`:''}.`;
  } catch(error) {
    if(version!==historyNumberSearchVersion||error?.name==='AbortError')return;
    status.textContent='Falha'; output.innerHTML=errorBlock(error.message);
  } finally {
    if(historyNumberSearchController===controller) {
      historyNumberSearchController=null;
      if(button?.isConnected)button.disabled=false;
    }
  }
}

function myGamesListHtml(item) {
  if(state.myGamesError) return `<div class="error-box">${esc(state.myGamesError)}</div>`;
  const all=state.myGames||[], shown=state.myGamesFiltered||all;
  const rows=shown.slice(0,100).map(ticket=>{
    const numbers=item.key==='supersete'?(ticket.numbers||[]).join(' '):(ticket.numbers||[]).map(n=>padNum(n,item.digits)).join(' ');
    const bonus=ticket.bonus?.trevos?.length?` · trevos ${ticket.bonus.trevos.join(' ')}`:ticket.bonus?.month?` · mês ${ticket.bonus.month}`:ticket.bonus?.team?` · ${ticket.bonus.team}`:'';
    return `<div class="draw-row"><div class="draw-row-main"><div class="draw-title">Jogo ${esc(ticket.ticket_number)}${esc(bonus)}</div><div class="draw-caption">${esc(numbers)}</div></div><div class="form-actions"><button type="button" class="button" data-action="my-game-use" data-game-id="${esc(ticket.id)}">Abrir no conferidor</button><button type="button" class="button" data-action="my-game-remove" data-game-id="${esc(ticket.id)}">Remover</button></div></div>`;
  }).join('');
  return `<div class="card-head"><div><h3 class="card-title">${esc(shown.length)} exibidos de ${esc(all.length)} jogos salvos</h3><div class="card-subtitle">A filtragem só altera esta lista visual. Os bilhetes originais ficam intactos no localStorage deste navegador.</div></div></div>${rows||'<div class="empty-state">Nenhum jogo corresponde aos filtros, ou ainda não há jogos importados.</div>'}${shown.length>100?'<div class="small-note">Exibindo 100 itens. Os filtros foram aplicados à lista completa.</div>':''}<div class="small-note">Os jogos não são enviados ao servidor até você abrir um jogo no conferidor e enviar uma solicitação.</div>`;
}
function myGamesSection(item) {
  return `<section class="card" id="my-games-section" style="margin-top:16px"><div class="card-head"><div><h2 class="card-title">Meus Jogos · somente neste navegador</h2><div class="card-subtitle">Importe, filtre e gerencie bilhetes localmente; nada é enviado por salvar ou filtrar.</div></div><span class="pill">Até ${MY_GAMES_LIMIT} por modalidade</span></div><form id="my-games-filter-form"><div class="form-grid"><div class="field"><label for="my-filter-sum-min">Soma mínima</label><input id="my-filter-sum-min" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="my-filter-sum-max">Soma máxima</label><input id="my-filter-sum-max" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="my-filter-even-min">Pares mínimos</label><input id="my-filter-even-min" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="my-filter-even-max">Pares máximos</label><input id="my-filter-even-max" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="my-filter-include">Incluir todas estas dezenas (opcional)</label><input id="my-filter-include" placeholder="Ex.: 01 05"></div><div class="field"><label for="my-filter-exclude">Excluir jogos com estas dezenas</label><input id="my-filter-exclude" placeholder="Ex.: 10 20"></div><div class="field"><label for="my-filter-repeat-min">Repetidas mínimas</label><input id="my-filter-repeat-min" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="my-filter-repeat-max">Repetidas máximas</label><input id="my-filter-repeat-max" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="my-filter-reference-contest">Concurso de referência (para repetidas)</label><input id="my-filter-reference-contest" type="number" min="1" step="1" placeholder="Informe o concurso"></div><div class="field"><label for="my-filter-reference-draw">Dezenas do concurso de referência</label><input id="my-filter-reference-draw" placeholder="Informe junto ao concurso"></div></div><div class="form-actions"><button type="submit" class="button button-primary">Aplicar filtros localmente</button><button type="button" class="button" data-action="my-games-clear-filters">Limpar filtros</button></div><div id="my-games-filter-status" class="small-note" role="status"></div></form><div id="my-games-list" style="margin-top:12px">${myGamesListHtml(item)}</div></section>`;
}
function updateMyGamesList() {
  const item=spec(), target=$('#my-games-list');
  if(target) target.innerHTML=myGamesListHtml(item);
}
async function handleImportGames(event) {
  event.preventDefault();
  const item=spec(), status=$('#import-status');
  try {
    const bonus=parseImportBonus(item), imported=validateImportedTickets($('#import-text').value,item,bonus);
    const existing=readMyGames(item.key);
    if(existing.length+imported.length>MY_GAMES_LIMIT) throw new Error(`Meus Jogos permite até ${MY_GAMES_LIMIT} bilhetes por modalidade; nada foi salvo.`);
    const timestamp=new Date().toISOString();
    const additions=imported.map((ticket,index)=>({...ticket,id:`g${Date.now()}-${Math.random().toString(36).slice(2)}-${index}`,ticket_number:existing.length+index+1,saved_at:timestamp}));
    const updated=[...existing,...additions];
    writeMyGames(item.key,updated);
    state.myGames=updated; state.myGamesFiltered=updated; state.myGamesError='';
    if(status) status.textContent=`${additions.length} jogo(s) validados e salvos apenas neste navegador.`;
    updateMyGamesList(); toast(`${additions.length} jogo(s) salvos em Meus Jogos`);
  } catch(error) {
    if(status) status.textContent=`Importação não concluída: ${error.message}`;
  }
}
function prepareImportForSimulator() {
  const item=spec();
  try {
    const bonus=parseImportBonus(item), tickets=validateImportedTickets($('#import-text').value,item,bonus);
    state.simulatorTickets=tickets.map((ticket,index)=>({...ticket,ticket_number:index+1}));
    state.simulatorText=state.simulatorTickets.map(ticket=>item.key==='supersete'?ticket.numbers.join(' '):ticket.numbers.map(n=>padNum(n,item.digits)).join(' ')).join('\n');
    state.simulatorBonus=commonTicketBonus(state.simulatorTickets); state.page='simulator'; render();
  } catch(error) { if($('#import-status'))$('#import-status').textContent=`Importação não concluída: ${error.message}`; }
}
function applyMyGamesFilters(event) {
  event.preventDefault();
  const status=$('#my-games-filter-status');
  try {
    const filters=parseMyGamesFilters(spec());
    state.myGameFilters=filters; state.myGamesFiltered=filterMyGames(state.myGames||[],filters);
    if(status) status.textContent=`Filtros aplicados somente à lista local: ${state.myGamesFiltered.length} de ${(state.myGames||[]).length} jogos.`;
    updateMyGamesList();
  } catch(error) { if(status)status.textContent=`Filtros não aplicados: ${error.message}`; }
}
function clearMyGamesFilters() {
  const form=$('#my-games-filter-form'); form?.reset();
  state.myGameFilters={}; state.myGamesFiltered=state.myGames||[];
  if($('#my-games-filter-status'))$('#my-games-filter-status').textContent='Filtros limpos; todos os jogos locais são exibidos.';
  updateMyGamesList();
}
function removeMyGame(id) {
  const item=spec(), updated=(state.myGames||[]).filter(ticket=>ticket.id!==id);
  try { writeMyGames(item.key,updated); state.myGames=updated; state.myGamesFiltered=filterMyGames(updated,state.myGameFilters||{}); state.myGamesError=''; updateMyGamesList(); }
  catch(error) { toast(`Não foi possível atualizar o armazenamento local: ${error.message}`); }
}
function useMyGame(id) {
  const item=spec(), ticket=(state.myGames||[]).find(entry=>entry.id===id);
  if(!ticket) {toast('Jogo local não encontrado.');return;}
  state.simulatorTickets=[{...ticket,numbers:[...ticket.numbers],bonus:{...(ticket.bonus||{})},columns:ticket.columns?.map(column=>[...column])}];
  state.simulatorText=item.key==='supersete'?ticket.numbers.join(' '):ticket.numbers.map(n=>padNum(n,item.digits)).join(' ');
  state.simulatorBonus=commonTicketBonus(state.simulatorTickets); state.page='simulator'; render();
}
function changeClosureView(type, view) {
  if(!['all','approved'].includes(view)) return;
  const response=type==='closure'?state.closureData:state.repeatedData;
  if(!response) return;
  if(type==='closure') state.closureView=view; else state.repeatedView=view;
  const entries=response.items||[];
  const visible=view==='approved'?entries.filter(entry=>entry.approved):entries;
  const offset=Number(response.offset||0);
  const tickets=visible.map(entry=>({numbers:entry.numbers,ticket_number:offset+entries.indexOf(entry)+1,bonus:{}}));
  if(type==='closure') state.closureTickets=tickets; else state.repeatedTickets=tickets;
  const target=type==='closure'?$('#closure-output'):$('#repeated-output');
  if(target) target.innerHTML=closureOutputHtml(type,response,spec());
}

async function renderTools() {
  const item=spec(); const version=renderVersion;
  state.myGameFilters={}; state.closureData=null; state.repeatedData=null;
  state.closureRequest=null; state.repeatedRequest=null; state.closureTickets=[]; state.repeatedTickets=[];
  let tools=[];
  try { tools=(await api(`/${item.key}/tools`)).tools; } catch(_) {}
  if (version!==renderVersion || state.page!=='tools' || state.game!==item.key) return;
  try { state.myGames=readMyGames(item.key); state.myGamesFiltered=state.myGames; state.myGamesError=''; }
  catch(error) { state.myGames=[]; state.myGamesFiltered=[]; state.myGamesError=error.message; }
  const toolCards=tools.map(tool=>`<div class="card tool-card"><div><div class="tool-icon">${tool.id==='probability'?'∑':tool.id==='export'?'↓':tool.id==='closures'?'▧':'⌘'}</div><h3 class="card-title" style="margin-top:10px">${esc(tool.name)}</h3><p>${tool.available?'Disponível nesta versão.':esc(tool.note||'')}</p>${tool.id==='quadrants'&&tool.available?'<button type="button" class="button button-primary" data-page="generator" style="margin-top:10px">Abrir gerador por quadrantes</button>':''}</div><span class="pill ${tool.available?'':'pill-muted'}">${tool.available?'Disponível':'Em desenvolvimento'}</span></div>`).join('');
  $('#main-content').innerHTML=`${pageHeader('Recursos · '+item.name,'Ferramentas adicionais',`Recursos públicos de apoio a jogos e consultas de ${item.name}.`)}<div class="grid grid-3">${toolCards}</div><div class="grid grid-2" style="margin-top:16px"><form class="card" id="probability-form"><div class="card-head"><div><h2 class="card-title">Calculadora de probabilidades</h2><div class="card-subtitle">Combinações teóricas para a quantidade de dezenas escolhida</div></div></div><div class="form-grid"><div class="field"><label for="prob-picks">Dezenas selecionadas</label><input id="prob-picks" type="number" min="${item.min_pick}" max="${item.max_pick}" value="${item.pick_size}"></div>${item.bonus?.type==='trevos'?'<div class="field"><label for="prob-trevos">Trevos selecionados</label><select id="prob-trevos">'+Array.from({length:5},(_,i)=>`<option value="${i+2}">${i+2}</option>`).join('')+'</select></div>':''}</div><div class="form-actions"><button class="button button-primary" type="submit">Calcular</button></div><div id="prob-result" style="margin-top:12px"></div></form><form class="card" id="import-form"><div class="card-head"><div><h2 class="card-title">Importar jogos por texto</h2><div class="card-subtitle">Valida todas as linhas antes de salvar; linhas inválidas não são omitidas.</div></div></div><div class="field"><label for="import-text">Jogos (um por linha)</label><textarea id="import-text" placeholder="01 05 12 ..."></textarea></div><div class="form-grid" style="margin-top:10px">${item.bonus?.type==='month'?`<div class="field"><label for="import-month">Mês da Sorte (opcional)</label><select id="import-month"><option value="">Não informado</option>${months.map((month,index)=>`<option value="${index+1}">${month}</option>`).join('')}</select></div>`:''}${item.bonus?.type==='team'?'<div class="field"><label for="import-team">Time do Coração (opcional)</label><input id="import-team" maxlength="80" placeholder="Nome do time"></div>':''}${item.bonus?.type==='trevos'?'<div class="field"><label for="import-trevos">Trevos da Sorte (obrigatório)</label><input id="import-trevos" placeholder="Ex.: 2 5"><span class="field-help">Informe de 2 a 6 trevos distintos entre 1 e 6.</span></div>':''}</div><div class="form-actions"><button type="submit" class="button button-primary">Validar e salvar em Meus Jogos</button><button type="button" class="button" data-action="import-prepare-simulator">Usar no conferidor sem salvar</button></div><div id="import-status" class="small-note" role="status"></div></form></div>${myGamesSection(item)}<div class="notice notice-warning"><span>ⓘ</span><span>Desdobramentos exaustivos não replicam fechamentos proprietários nem garantem premiação. A inspeção de recursos públicos é parcial e não garante paridade com áreas ou funções não públicas da referência.</span></div>`;
  if (item.key==='supersete') {
    $('#prob-picks')?.closest('.field')?.remove();
    $('#probability-form .form-grid')?.insertAdjacentHTML('beforeend',Array.from({length:7},(_,index)=>`<div class="field"><label for="prob-column-${index+1}">Opções na coluna ${index+1}</label><select id="prob-column-${index+1}">${Array.from({length:10},(_,value)=>`<option value="${value+1}">${value+1} dígito(s)</option>`).join('')}</select></div>`).join(''));
  }
  $('#prob-result')?.setAttribute('role','status');
  $('#prob-result')?.setAttribute('aria-live','polite');
  if (tools.find(tool=>tool.id==='closures')?.available) {
    $('#main-content').insertAdjacentHTML('beforeend', `<form class="card" id="closure-form" style="margin-top:16px"><div class="card-head"><div><h2 class="card-title">Desdobramento exaustivo paginado</h2><div class="card-subtitle">Percorra o conjunto completo em páginas de até 1.000 combinações. Cada jogo recebe diagnóstico dos filtros; nada é salvo nem enviado automaticamente.</div></div></div><div class="field"><label for="closure-pool">Conjunto de dezenas</label><textarea id="closure-pool" placeholder="Ex.: 01 02 03 04 05 06 07" required></textarea></div><div class="form-grid" style="margin-top:10px"><div class="field"><label for="closure-fixed">Dezenas fixas (opcional)</label><input id="closure-fixed" placeholder="Ex.: 01 02"></div><div class="field"><label for="closure-picks">Dezenas por jogo</label><input id="closure-picks" type="number" min="${item.min_pick}" max="${item.max_pick}" step="1" value="${item.pick_size}" required></div></div>${closureFilterFields(item,'closure')}<div class="form-actions"><button class="button button-primary" type="submit">Gerar primeira página</button></div><div id="closure-output" style="margin-top:12px"></div></form>`);
    $('#closure-form').addEventListener('submit',handleClosure);
  }
  if (item.key==='lotofacil') {
    $('#main-content').insertAdjacentHTML('beforeend', `<form class="card" id="history-number-search-form" style="margin-top:16px"><div class="card-head"><div><h2 class="card-title">Pesquisa histórica por dezenas · Lotofácil</h2><div class="card-subtitle">Defina como as dezenas informadas devem corresponder a cada concurso.</div></div><span id="history-number-search-status" class="pill pill-muted">Não iniciada</span></div><div class="form-grid"><div class="field"><label for="history-number-search-numbers">Dezenas (1–15, entre 1 e 25)</label><input id="history-number-search-numbers" maxlength="60" placeholder="Ex.: 01 04 12"><span class="field-help">Dezenas distintas. “Combinação exata” exige as 15 dezenas de um resultado. Editar uma entrada invalida resultados anteriores.</span></div><div class="field"><label for="history-number-search-criterion">Critério</label><select id="history-number-search-criterion"><option value="contains_all">Contém todas as dezenas informadas</option><option value="exact">Combinação exata de 15 dezenas</option><option value="excludes_all">Não contém nenhuma das dezenas informadas</option></select></div><div class="field"><label for="history-number-search-mode">Janela do histórico</label><select id="history-number-search-mode"><option value="50">Últimos 50 concursos</option><option value="300">Últimos 300 concursos</option><option value="all">Todo histórico disponível (máximo 5.000)</option></select></div></div><div class="form-actions"><button type="submit" class="button button-primary">Pesquisar concursos</button></div><div id="history-number-search-progress" class="small-note" role="status"></div><div id="history-number-search-result" style="margin-top:12px"></div><div class="small-note">A janela “todo” pode ser incompleta: lacunas e concursos ausentes são informados e não serão apresentados como histórico completo. Os dados vêm do carregador histórico do navegador e sua origem não é verificada pelo servidor. Isso não é previsão, nem altera a probabilidade de sorteios futuros; a consulta não salva jogos nem estudos.</div></form>`);
    $('#history-number-search-form').addEventListener('submit',runHistoryNumberSearch);
    ['#history-number-search-numbers','#history-number-search-mode','#history-number-search-criterion'].forEach(selector=>$(selector).addEventListener('input',()=>invalidateHistoryNumberSearch()));
    ['#history-number-search-mode','#history-number-search-criterion'].forEach(selector=>$(selector).addEventListener('change',()=>invalidateHistoryNumberSearch()));
    $('#main-content').insertAdjacentHTML('beforeend', `<form class="card" id="repeated-form" style="margin-top:16px"><div class="card-head"><div><h2 class="card-title">Desdobramento de repetidas · Lotofácil</h2><div class="card-subtitle" id="repeated-previous">Consultando o último resultado…</div></div><span class="pill pill-muted">Entrada explícita · não salva</span></div><div id="repeated-picker" class="field-help">Carregando dezenas do último concurso…</div>${closureFilterFields(item,'repeated')}<div class="form-actions"><button type="submit" class="button button-primary" id="repeated-submit" disabled>Gerar página e diagnósticos</button></div><div id="repeated-output" style="margin-top:12px"></div><div class="small-note">Escolha de 6 a 12 dezenas que ocorreram no resultado anterior. Cada jogo inclui todas as dezenas selecionadas e completa 15 dezenas entre as ausentes. Para filtro de repetidas, a referência exibida é explicitamente informada; critérios locais não são previsão nem garantia de prêmio.</div></form>`);
    loadRepeatedPrevious(version,item.key);
    $('#repeated-form').addEventListener('submit',handleRepeatedClosure);
    $('#main-content').insertAdjacentHTML('beforeend', `<form class="card" id="combination-count-form" style="margin-top:16px"><div class="card-head"><div><h2 class="card-title">Contar combinações com fixas e removidas</h2><div class="card-subtitle">Lotofácil: conta as combinações sem gerar ou salvar jogos.</div></div></div><div class="form-grid"><div class="field"><label for="combination-picks">Dezenas por jogo</label><input id="combination-picks" type="number" min="15" max="20" step="1" value="15" required></div><div class="field"><label for="combination-fixed">Quantidade de fixas</label><input id="combination-fixed" type="number" min="0" max="20" step="1" value="0" required></div><div class="field"><label for="combination-removed">Quantidade removida</label><input id="combination-removed" type="number" min="0" max="10" step="1" value="0" required></div></div><div class="form-actions"><button type="submit" class="button button-primary">Contar combinações</button></div><div id="combination-count-result" role="status" aria-live="polite" style="margin-top:12px"></div><div class="small-note">Esta é uma contagem, não uma probabilidade de prêmio. Fixar ou remover dezenas não garante que as escolhas estarão corretas no sorteio.</div></form>`);
    $('#combination-count-form').addEventListener('submit',calculateCombinationCount);
    ['#combination-picks','#combination-fixed','#combination-removed'].forEach(selector=>$(selector).addEventListener('input',markCombinationCountStale));
  }
  $('#probability-form').addEventListener('submit',calculateProbability);
    $('#import-form').addEventListener('submit',handleImportGames);
    $('#my-games-filter-form').addEventListener('submit',applyMyGamesFilters);
}
async function calculateCombinationCount(event) {
  event.preventDefault();
  const version=renderVersion, request=++combinationCountRequest, target=$('#combination-count-result');
  try {
    const raw=[$('#combination-picks').value,$('#combination-fixed').value,$('#combination-removed').value];
    if (raw.some(value=>!/^\d+$/.test(value))) throw new Error('Informe quantidades inteiras não negativas.');
    const [picks,fixed,removed]=raw.map(Number);
    if (picks<15||picks>20||fixed>picks||removed>25-picks) throw new Error('Use de 15 a 20 dezenas, fixas até o tamanho do jogo e removidas deixando dezenas suficientes.');
    target.innerHTML='<span class="spinner"></span> Contando combinações…';
    const result=await api(`/lotofacil/combination-count?pick_count=${picks}&fixed_count=${fixed}&removed_count=${removed}`);
    if (version!==renderVersion||request!==combinationCountRequest||state.page!=='tools'||state.game!=='lotofacil') return;
    if (!/^\d+$/.test(String(result.combination_count))) throw new Error('A contagem retornada é inválida.');
    const count=BigInt(result.combination_count).toLocaleString('pt-BR');
    target.innerHTML=`<div class="mini-stat"><small>Combinações possíveis</small><b>${esc(count)}</b><small>${esc(result.formula_expression||'')}</small></div><p class="small-note">${esc(result.disclaimer||'Contagem, não chance de prêmio.')}</p>`;
  } catch(error) { if (version===renderVersion&&request===combinationCountRequest&&state.page==='tools'&&state.game==='lotofacil') target.innerHTML=errorBlock(error.message); }
}
function markCombinationCountStale() {
  combinationCountRequest++;
  const target=$('#combination-count-result');
  if (target) target.innerHTML='<div class="small-note" role="status">Entradas alteradas: resultado anterior desatualizado. Calcule novamente para atualizar.</div>';
}
async function loadRepeatedPrevious(version, game) {
  try {
    const draw=await api('/lotofacil/latest');
    if (version!==renderVersion||state.page!=='tools'||state.game!==game) return;
    if (!draw||!Number.isInteger(Number(draw.contest))||!Array.isArray(draw.numbers)||draw.numbers.length!==15||new Set(draw.numbers).size!==15) throw new Error('O último resultado não contém 15 dezenas válidas.');
    state.repeatedDraw=draw; state.repeatedTickets=[];
    $('#repeated-previous').textContent=`Resultado anterior · concurso ${draw.contest}`;
    if($('#repeated-reference-contest')) $('#repeated-reference-contest').value=String(draw.contest);
    $('#repeated-picker').innerHTML=draw.numbers.slice().sort((a,b)=>a-b).map(n=>`<label style="display:inline-flex;align-items:center;gap:5px;margin:6px 10px 0 0"><input type="checkbox" name="repeated-number" value="${n}">${padNum(n,2)}</label>`).join('')+'<div class="field-help">Selecione exatamente de 6 a 12 dezenas.</div>';
    $('#repeated-submit').disabled=false;
  } catch(error) { if(version===renderVersion&&state.page==='tools'&&state.game===game) $('#repeated-output').innerHTML=errorBlock(error.message); }
}
function closureFilterFields(item, prefix) {
  const keys=[['sum','Soma'],['even','Pares'],['repeat','Repetidas do concurso de referência'],['prime','Primos'],['fibonacci','Fibonacci'],['sequence','Maior sequência'],['jumps','Saltos']];
  if(item.key==='lotofacil') keys.push(['line','Mínimo/máximo por linha (cada uma das 5)'],['column','Mínimo/máximo por coluna (cada uma das 5)']);
  if(item.key==='lotomania') for(let q=1;q<=4;q++) keys.push([`q${q}`,`Contagem Q${q}`]);
  const inputs=keys.map(([key,label])=>`<div class="field"><label for="${prefix}-filter-${key}-min">Mínimo ${esc(label)}</label><input id="${prefix}-filter-${key}-min" type="number" placeholder="Sem limite"></div><div class="field"><label for="${prefix}-filter-${key}-max">Máximo ${esc(label)}</label><input id="${prefix}-filter-${key}-max" type="number" placeholder="Sem limite"></div>`).join('');
  const reference=keys.some(([key])=>key==='repeat')?`<div class="field"><label for="${prefix}-reference-contest">Concurso de referência (obrigatório para repetidas)</label><input id="${prefix}-reference-contest" type="number" min="1" step="1" placeholder="Informe o concurso"><span class="field-help">Repetidas serão calculadas contra este concurso específico, nunca contra um resultado implícito.</span></div>`:'';
  return `<div class="card" style="margin-top:12px"><div class="card-head"><div><h3 class="card-title">Filtros e diagnósticos</h3><div class="card-subtitle">Cada combinação mostrará todos os motivos locais de aprovação ou reprovação.</div></div></div><div class="form-grid">${inputs}${reference}<div class="field"><label for="${prefix}-page-size">Combinações por página</label><select id="${prefix}-page-size"><option value="100">100</option><option value="250">250</option><option value="500">500</option><option value="1000" selected>1.000</option></select></div></div></div>`;
}
function readClosureRequest(prefix) {
  const filters={};
  const keyMap={sum:'sum',even:'even',repeat:'repeated',prime:'prime',fibonacci:'fibonacci',sequence:'sequence',jumps:'jumps',line:'line',column:'column',q1:'q1',q2:'q2',q3:'q3',q4:'q4'};
  for(const [uiKey,apiKey] of Object.entries(keyMap)) for(const bound of ['min','max']) {
    const value=$(`#${prefix}-filter-${uiKey}-${bound}`)?.value.trim()||'';
    if(value) {
      if(!/^\d+$/.test(value)||!Number.isSafeInteger(Number(value))) throw new Error(`O filtro ${bound} ${uiKey} deve ser um inteiro não negativo.`);
      filters[`${bound}_${apiKey}`]=Number(value);
    }
  }
  const repeatFilter=filters.min_repeated!==undefined||filters.max_repeated!==undefined;
  const referenceText=$(`#${prefix}-reference-contest`)?.value.trim()||'';
  if(repeatFilter&&(!/^\d+$/.test(referenceText)||!Number.isSafeInteger(Number(referenceText))||Number(referenceText)<1)) throw new Error('Filtros de repetidas exigem um número de concurso de referência explícito.');
  const pageSize=Number($(`#${prefix}-page-size`)?.value||1000);
  if(![100,250,500,1000].includes(pageSize)) throw new Error('Selecione um tamanho de página válido.');
  return {filters,reference_contest:repeatFilter?Number(referenceText):null,page_size:pageSize};
}
function closureGamesText(items,item) { return items.map(entry=>entry.numbers.map(n=>padNum(n,item.digits)).join(' ')).join('\n'); }
function closureOutputHtml(type,response,item) {
  const view=type==='closure'?(state.closureView||'all'):(state.repeatedView||'all');
  const items=Array.isArray(response.items)?response.items:(response.games||[]).map(numbers=>({numbers,approved:true,reasons:[]}));
  const visible=view==='approved'?items.filter(entry=>entry.approved):items;
  const offset=Number(response.offset||0), pageSize=Number(response.page_size||items.length||1);
  const pageNumber=Math.floor(offset/pageSize)+1;
  const diagnostics=items.map((entry,index)=>`<tr><td>${esc(offset+index+1)}</td><td>${esc(entry.numbers.map(n=>padNum(n,item.digits)).join(' '))}</td><td>${entry.approved?'Aprovado':'Reprovado'}</td><td>${entry.reasons?.length?esc(entry.reasons.join(' · ')):'Todos os filtros atendidos'}</td></tr>`).join('');
  const nav=`<div class="form-actions"><button type="button" class="button" data-action="${type}-prev" ${offset<=0?'disabled':''}>Página anterior</button><span class="small-note">Página ${esc(pageNumber)} · ${esc(offset+1)}–${esc(offset+items.length)} de ${esc(response.candidate_count??response.game_count)} combinações</span><button type="button" class="button" data-action="${type}-next" ${response.next_offset===null?'disabled':''}>Próxima página</button></div>`;
  const viewControl=`<div class="form-actions"><label for="${type}-view">Exibir</label><select id="${type}-view"><option value="all" ${view==='all'?'selected':''}>Todos</option><option value="approved" ${view==='approved'?'selected':''}>Somente aprovados</option></select><span class="pill">${visible.length} exibidos · ${Number(response.approved_count||0)} aprovados nesta página</span></div>`;
  const send=visible.length&&visible.length<=500?`<div class="form-actions"><button type="button" class="button button-primary" data-action="test-${type}">Preparar conferência dos jogos exibidos</button></div>`:`<div class="small-note">${visible.length?`O conferidor aceita até 500 jogos por envio; reduza o tamanho da página ou use “Somente aprovados”.`:'Nenhum jogo corresponde à seleção de exibição.'} Nenhum jogo foi enviado.</div>`;
  const reference=response.reference_contest?` · referência do concurso ${esc(response.reference_contest)}`:'';
  return `<div class="stats-highlight"><div class="mini-stat"><small>Combinações no fechamento</small><b>${esc(Number(response.candidate_count??response.game_count).toLocaleString('pt-BR'))}</b></div><div class="mini-stat"><small>Candidatas nesta página</small><b>${esc(items.length)}</b></div><div class="mini-stat"><small>Aprovadas nesta página</small><b>${esc(Number(response.approved_count||0))}</b></div></div><p class="small-note">${esc(response.coverage||response.disclaimer||'Enumeração local, sem garantia de prêmio.')}${reference}</p>${nav}${viewControl}${visible.length?`<div class="field"><label for="${type}-games">Jogos exibidos (copie para guardar)</label><textarea id="${type}-games" rows="8" readonly>${esc(closureGamesText(visible,item))}</textarea></div>`:''}${send}<details class="small-note"><summary>Diagnóstico completo de cada combinação (${items.length})</summary><div class="table-wrap"><table><thead><tr><th>#</th><th>Jogo</th><th>Status</th><th>Motivos</th></tr></thead><tbody>${diagnostics}</tbody></table></div></details>`;
}
async function loadClosurePage(offset) {
  const item=spec(), version=renderVersion, target=$('#closure-output');
  if(!state.closureRequest) return;
  target.innerHTML='<div class="loading-block"><span class="spinner"></span>Calculando página e diagnósticos…</div>';
  try {
    const response=await api(`/${item.key}/closures/exhaustive`,{method:'POST',body:JSON.stringify({...state.closureRequest,offset})});
    if(version!==renderVersion||state.page!=='tools'||state.game!==item.key) return;
    if(!Array.isArray(response.items)||response.items.length!==response.returned_count||!Number.isSafeInteger(response.next_offset===null?0:Number(response.next_offset))) throw new Error('Resposta de página incompatível com o contrato esperado.');
    state.closureData=response;
    const entries=state.closureView==='approved'?response.items.filter(entry=>entry.approved):response.items;
  state.closureTickets=entries.map(entry=>({numbers:entry.numbers,ticket_number:Number(response.offset||0)+(response.items||[]).indexOf(entry)+1,bonus:{}}));
    target.innerHTML=closureOutputHtml('closure',response,item);
  } catch(error) { if(version===renderVersion&&state.page==='tools'&&state.game===item.key) target.innerHTML=errorBlock(error.message); }
}
async function loadRepeatedClosurePage(offset) {
  const item=spec(), version=renderVersion, output=$('#repeated-output');
  if(!state.repeatedRequest||!state.repeatedDraw) return;
  output.innerHTML='<div class="loading-block"><span class="spinner"></span>Calculando página e diagnósticos…</div>';
  try {
    const response=await api('/lotofacil/closures/repeated',{method:'POST',body:JSON.stringify({...state.repeatedRequest,previous_draw:state.repeatedDraw.numbers,offset})});
    if(version!==renderVersion||state.page!=='tools'||state.game!=='lotofacil') return;
    if(!Array.isArray(response.items)||response.items.length!==response.returned_count) throw new Error('Resposta do fechamento de repetidas inválida.');
    state.repeatedData=response;
    const entries=state.repeatedView==='approved'?response.items.filter(entry=>entry.approved):response.items;
  state.repeatedTickets=entries.map(entry=>({numbers:entry.numbers,ticket_number:Number(response.offset||0)+(response.items||[]).indexOf(entry)+1,bonus:{}}));
    output.innerHTML=closureOutputHtml('repeated',response,item);
  } catch(error) { if(version===renderVersion&&state.page==='tools'&&state.game==='lotofacil') output.innerHTML=errorBlock(error.message); }
}
async function handleRepeatedClosure(event) {
  event.preventDefault(); const version=renderVersion, game=state.game, previous=state.repeatedDraw;
  const output=$('#repeated-output');
  if(game!=='lotofacil'||!previous) {output.innerHTML=errorBlock('Resultado anterior indisponível.');return;}
  const repeated=$$('[name="repeated-number"]:checked').map(el=>Number(el.value));
  if(repeated.length<6||repeated.length>12||new Set(repeated).size!==repeated.length||repeated.some(n=>!previous.numbers.includes(n))) {output.innerHTML=errorBlock('Selecione de 6 a 12 dezenas distintas do resultado anterior; nenhum pedido foi enviado.');return;}
  try {
    const filters=readClosureRequest('repeated');
    state.repeatedRequest={repeated,filters:filters.filters,reference_contest:filters.reference_contest,page_size:filters.page_size};
    state.repeatedView='all';
    if(version!==renderVersion||state.page!=='tools'||state.game!==game)return;
    await loadRepeatedClosurePage(0);
  } catch(error) { if(version===renderVersion&&state.page==='tools'&&state.game===game) output.innerHTML=errorBlock(error.message); }
}
async function handleClosure(event) {
  event.preventDefault();
  const item=spec(), version=renderVersion, target=$('#closure-output');
  const parse=raw=>{const text=raw.trim(); if (!text) return []; const parts=text.split(/[\s,;|]+/); if (parts.some(part=>!/^[0-9]+$/.test(part))) throw new Error('Use apenas dezenas inteiras separadas por espaços ou vírgulas.'); return parts.map(Number);};
  try {
    const filters=readClosureRequest('closure');
    const pool=parse($('#closure-pool').value), fixed=parse($('#closure-fixed').value), pick_count=Number($('#closure-picks').value);
    state.closureRequest={pool,fixed,pick_count,filters:filters.filters,reference_contest:filters.reference_contest,page_size:filters.page_size};
    state.closureView='all';
    if(version!==renderVersion||state.page!=='tools'||state.game!==item.key)return;
    await loadClosurePage(0);
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
function renderProbabilityTiers(tiers, awardTiersOverlap=false) {
  if (!Array.isArray(tiers) || !tiers.length) return '';
  const rows=tiers.map(tier=>{
    const probability=Number(tier.probability), denominator=Number(tier.one_in)||Math.round(1/probability);
    const label=tier.label||`${esc(tier.hits)} ${Number(tier.hits)===1?'acerto':'acertos'}`;
    if (!Number.isFinite(probability)||probability<=0||probability>1||!Number.isFinite(denominator)) return '';
    return `<div class="draw-row"><div class="draw-title">${esc(label)}</div><div>Aprox. 1 em ${esc(denominator.toLocaleString('pt-BR'))} · ${esc((probability*100).toExponential(3))}%${renderExactOutcomes(tier)}</div></div>`;
  }).filter(Boolean).join('');
  const overlapping=awardTiersOverlap||tiers.some(tier=>tier.overlaps_main_prizes||tier.may_overlap);
  const note=overlapping?'Probabilidade de presença do evento no bilhete; faixas dos dois sorteios da Dupla Sena, bônus e subapostas da +Milionária podem se sobrepor. Não some linhas nem as interprete como quantidade de prêmios.':'Probabilidade de presença de cada evento no bilhete; as faixas exatas de acertos são mutuamente exclusivas.';
  return rows?`<div class="card" style="margin-top:12px"><h3 class="card-title">Probabilidade teórica por faixa</h3><div class="small-note">${note}</div>${rows}</div>`:'';
}
function renderExactOutcomes(outcome) {
  if (outcome?.favorable_outcomes===undefined||outcome?.total_outcomes===undefined) return '';
  return `<details class="small-note" style="margin-top:4px;overflow-wrap:anywhere"><summary>Ver contagem inteira exata</summary><div>${esc(outcome.favorable_outcomes)} resultados favoráveis / ${esc(outcome.total_outcomes)} resultados possíveis</div></details>`;
}
function renderHitDistribution(distribution, hitUnit='acertos') {
  if (!Array.isArray(distribution)||!distribution.length) return '';
  const rows=distribution.map(row=>{
    const hits=Number(row.hits),probability=Number(row.probability),denominator=Number(row.one_in)||Math.round(1/probability);
    if (!Number.isInteger(hits)||hits<0||!Number.isFinite(probability)||probability<=0||probability>1||!Number.isFinite(denominator)) return '';
    return `<div class="draw-row"><div class="draw-title">${esc(hits)} ${esc(hitUnit)}</div><div>Aprox. 1 em ${esc(denominator.toLocaleString('pt-BR'))} · ${esc((probability*100).toExponential(3))}%${renderExactOutcomes(row)}</div></div>`;
  }).filter(Boolean).join('');
  return rows?`<details class="card" style="margin-top:12px"><summary class="card-title">Ver a distribuição completa de acertos</summary><div class="small-note" style="margin-top:8px">Probabilidade exata de cada quantidade de acertos, sob o modelo combinatório informado.</div>${rows}</details>`:'';
}
async function calculateProbability(event) {
  event.preventDefault(); const item=spec(); const version=renderVersion;
  const picks=$('#prob-picks')?.value||''; const trevos=$('#prob-trevos')?.value||2;
  const target=$('#prob-result'); target.innerHTML='<span class="spinner"></span> Calculando probabilidades combinatórias…';
  try {
    const query=[];
    if (picks) query.push(`pick_count=${encodeURIComponent(picks)}`);
    if ($('#prob-trevos')) query.push(`trevo_count=${encodeURIComponent(trevos)}`);
    if (item.key==='supersete') for (let column=1;column<=7;column++) query.push(`column_picks=${encodeURIComponent($(`#prob-column-${column}`)?.value||1)}`);
    const data=await api(`/${item.key}/probability${query.length?'?'+query.join('&'):''}`);
    if (version!==renderVersion || state.page!=='tools' || state.game!==item.key) return;
    const any=data.any_prize?`<div class="mini-stat"><small>Qualquer faixa de prêmio</small><b>1 em ${esc(Number(data.any_prize.one_in).toLocaleString('pt-BR'))}</b><small>${esc(Number(data.any_prize.percent).toExponential(3))}% · eventos contabilizados sem dupla contagem</small>${renderExactOutcomes(data.any_prize)}</div>`:'';
    target.innerHTML=`<div class="stats-highlight"><div class="mini-stat"><small>${esc(probabilityEvent(item,data))}</small><b>Aprox. 1 em ${esc(Number(data.one_in).toLocaleString('pt-BR'))}</b></div><div class="mini-stat"><small>Percentual teórico</small><b>${esc(Number(data.percent).toExponential(3))}%</b></div>${any}</div><div class="small-note">${esc(data.method)} Sorteios são aleatórios e independentes. ${esc(data.probability_scope||'Probabilidades combinatórias teóricas, não previsões.')} As razões “1 em N” são arredondadas para apresentação; abra a contagem inteira para ver a fração exata.</div>${renderProbabilityTiers(data.prize_tiers,data.award_tiers_overlap)}${renderHitDistribution(data.hit_distribution,data.hit_unit||'acertos')}`;
    if (data.ticket_subbets!==undefined) target.insertAdjacentHTML('beforeend',`<div class="small-note">O bilhete múltiplo equivale a ${esc(Number(data.ticket_subbets).toLocaleString('pt-BR'))} subapostas simples distintas.</div>`);
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
async function handleGenerate(event) {
  event.preventDefault(); const item=spec(); const version=renderVersion;
  const payload={count:Number($('#game-count').value||1),filters:{},pareto:$('#generator-pareto')?.checked===true};
  if (item.key!=='supersete') {
    for (const key of ['sum','even','repeat','prime','fibonacci','sequence','jumps','line','column','q1','q2','q3','q4']) {
      const min=$(`#filter-${key}-min`), max=$(`#filter-${key}-max`);
      const apiKey=key==='repeat'?'repeated':key;
      if (min?.value) payload.filters[`min_${apiKey}`]=min.value;
      if (max?.value) payload.filters[`max_${apiKey}`]=max.value;
    }
    const weightText=$('#generator-weights')?.value.trim();
    if (weightText) {
      const weights={};
      for (const part of weightText.split(',')) {
        const match=part.trim().match(/^(\d+)\s*:\s*(\d+(?:\.\d+)?)$/);
        if (!match || Object.hasOwn(weights,String(Number(match?.[1])))) { $('#generated-output').innerHTML=errorBlock('Informe pesos únicos no formato dezena:peso, separados por vírgula. Use ponto para decimais.'); return; }
        weights[String(Number(match[1]))]=Number(match[2]);
      }
      payload.weights=weights;
    }
  }
  if ($('#pick-count')) payload.pick_count=Number($('#pick-count').value);
  if (item.key==='supersete') {
    payload.columns={};
    for(let col=1;col<=7;col++) {
      const fixed=$$(`[data-column="${col}"].on-fixed`).map(el=>Number(el.dataset.digit));
      const excluded=$$(`[data-column="${col}"].on-excluded`).map(el=>Number(el.dataset.digit));
      payload.columns[String(col)]={fixed,excluded,pick_count:Number($(`[data-column-pick="${col}"]`).value||1)};
    }
  } else {
    payload.fixed=$$('.number-cell.is-fixed').map(el=>Number(el.dataset.number));
    payload.excluded=$$('.number-cell.is-excluded').map(el=>Number(el.dataset.number));
  }
  if (item.bonus?.type==='month') payload.bonus={month:$('#bonus-month').value||null};
  if (item.bonus?.type==='team') payload.bonus={team:$('#bonus-team').value||''};
  if (item.bonus?.type==='trevos') payload.bonus={trevo_count:Number($('#trevo-count').value||2)};
  const target=$('#generated-output'); target.innerHTML='<div class="loading-block"><span class="spinner"></span>Montando jogos...</div>';
  try {
    const response=await api(`/${item.key}/generate`,{method:'POST',body:JSON.stringify(payload)});
    if (version!==renderVersion || state.page!=='generator' || state.game!==item.key) return;
    state.generated=response.items; state.simulatorTickets=[];
    target.innerHTML=response.items.map(ticket=>`<div class="generated-ticket"><div class="generated-ticket-head"><b>Jogo ${esc(ticket.ticket_number)}</b><span class="pill">${payload.pareto?'Aleatório · Pareto histórico':payload.weights?'Ponderado':'Aleatório'}</span></div>${item.key==='supersete'?`<div class="col-grid">${ticket.columns.map((values,i)=>`<div class="col-box"><strong>COLUNA ${i+1}</strong>${balls(values)}</div>`).join('')}</div>`:`<div class="ball-row">${balls(ticket.numbers)}</div>`}${ticket.bonus?.month?`<div class="ticket-stats">Mês da Sorte: ${esc(months[Number(ticket.bonus.month)-1]||ticket.bonus.month)}</div>`:''}${ticket.bonus?.team?`<div class="ticket-stats">Time do Coração: ${esc(ticket.bonus.team)}</div>`:''}${ticket.bonus?.trevos?`<div class="ticket-stats">Trevos: ${balls(ticket.bonus.trevos,true)}</div>`:''}<div class="ticket-stats"><span>Soma: ${esc(ticket.sum??'—')}</span><span>Pares: ${esc(ticket.even_count)}</span><span>Ímpares: ${esc(ticket.odd_count)}</span><span>Repetidas do último: ${esc(ticket.repeated_from_latest)}</span><span>${esc(probabilityEvent(item,ticket.probability))}: 1 em ${esc(Number(ticket.probability.one_in).toLocaleString('pt-BR'))}</span></div></div>`).join('')+`<div class="form-actions"><button class="button button-primary" data-action="test-generated">Conferir estes jogos</button><a class="button" href="${API}/${item.key}/export.csv?limit=100">↓ Exportar histórico</a></div><div class="small-note">${esc(response.disclaimer)}</div>`;
    if (response.pareto) target.innerHTML+=`<div class="small-note">Pareto local: ${esc(response.pareto.draws_analyzed)} concursos até o concurso ${esc(response.pareto.latest_contest??'—')}; ${esc(response.pareto.total_appearances)} aparições observadas, conjunto selecionado ${esc((response.pareto.selected_numbers||[]).map(n=>padNum(n,item.digits)).join(' '))}. ${esc(response.pareto.scope||'Regra retrospectiva de 80%; não prevê resultados.')}</div>`;
    if (item.key==='maismilionaria') $$('.generated-ticket',target).forEach((element,index)=>{const count=response.items[index].probability.ticket_subbets;element.insertAdjacentHTML('beforeend',`<div class="ticket-stats">Subapostas distintas neste bilhete: ${esc(Number(count).toLocaleString('pt-BR'))}</div>`);});
    if (item.key==='lotomania') $$('.generated-ticket',target).forEach((element,index)=>{const counts=lotomaniaQuadrantCounts(response.items[index].numbers);element.insertAdjacentHTML('beforeend',`<div class="ticket-stats quadrant-counts"><span>Q1: ${counts.Q1}</span><span>Q2: ${counts.Q2}</span><span>Q3: ${counts.Q3}</span><span>Q4: ${counts.Q4}</span></div>`);});
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
async function handleSimulate(event) {
  event.preventDefault(); const item=spec(); const version=renderVersion;
  const typed=$('#sim-numbers').value;
  let tickets;
  const preloaded=state.simulatorTickets.length && typed===state.simulatorText;
  const bonus={};
  if (preloaded) {
    tickets=state.simulatorTickets;
  } else {
    const parsed=parseStrictNumberLines(typed);
    if (!parsed) { $('#sim-result').innerHTML='<div class="error-box">Há uma ou mais linhas com conteúdo inválido. Informe apenas números inteiros; nenhum jogo será omitido.</div>'; return; }
    if (!parsed.length) { $('#sim-result').innerHTML=errorBlock('Digite ao menos um jogo.'); return; }
    if (item.bonus?.type==='month'&&$('#sim-month').value) bonus.month=Number($('#sim-month').value);
    if (item.bonus?.type==='team'&&$('#sim-team').value) bonus.team=$('#sim-team').value.trim();
    if (item.bonus?.type==='trevos'&&$('#sim-trevos').value) {
      const trevos=parseStrictNumberLines($('#sim-trevos').value);
      if (!trevos || trevos.length!==1||trevos[0].length<2||trevos[0].length>6||new Set(trevos[0]).size!==trevos[0].length||trevos[0].some(n=>n<1||n>6)) { $('#sim-result').innerHTML='<div class="error-box">Informe de 2 a 6 trevos distintos entre 1 e 6 em uma linha.</div>'; return; }
      bonus.trevos=trevos[0];
    }
    tickets=parsed.map((numbers,index)=>({numbers,ticket_number:index+1,bonus:{...bonus}}));
    if (item.key==='supersete') tickets.forEach(ticket=>ticket.columns=ticket.numbers.map(n=>[n]));
  }
  if (preloaded && $('#sim-bonus-override')?.checked) {
    if (item.bonus?.type==='month'&&$('#sim-month').value) bonus.month=Number($('#sim-month').value);
    if (item.bonus?.type==='team'&&$('#sim-team').value.trim()) bonus.team=$('#sim-team').value.trim();
    if (item.bonus?.type==='trevos'&&$('#sim-trevos').value) {
      const trevos=parseStrictNumberLines($('#sim-trevos').value);
      if (!trevos||trevos.length!==1||trevos[0].length<2||trevos[0].length>6||new Set(trevos[0]).size!==trevos[0].length||trevos[0].some(n=>n<1||n>6)) {$('#sim-result').innerHTML='<div class="error-box">Informe de 2 a 6 trevos distintos entre 1 e 6.</div>';return;}
      bonus.trevos=trevos[0];
    }
    if (!Object.keys(bonus).length) {$('#sim-result').innerHTML='<div class="error-box">Informe um bônus válido para substituir os bônus originais.</div>';return;}
    tickets=ticketsWithBonus(tickets,bonus,true);
  }
  if (item.key==='maismilionaria'&&tickets.some(ticket=>{const trevos=ticket.bonus?.trevos;return !Array.isArray(trevos)||trevos.length<2||trevos.length>6||new Set(trevos).size!==trevos.length||trevos.some(n=>!Number.isInteger(n)||n<1||n>6);})) {$('#sim-result').innerHTML=errorBlock('A +Milionária exige de 2 a 6 trevos distintos por jogo. Informe os trevos antes de conferir.');return;}
  const maxPicks=maxSimulationPicks(item);
  for (let index=0;index<tickets.length;index++) {
    const numbers=tickets[index].numbers||[];
    if (item.key==='supersete'?numbers.length!==7:numbers.length<item.min_pick||numbers.length>maxPicks) {$('#sim-result').innerHTML=`<div class="error-box">Jogo na linha ${index+1}: ${item.key==='supersete'?'informe exatamente 7 dígitos':`informe de ${item.min_pick} a ${maxPicks} dezenas`}.</div>`;return;}
    if (item.key!=='supersete'&&new Set(numbers).size!==numbers.length) {$('#sim-result').innerHTML=`<div class="error-box">Jogo na linha ${index+1}: não repita dezenas.</div>`;return;}
    if (numbers.some(number=>item.key==='supersete'?number<0||number>9:number<item.range.minimum||number>item.range.maximum)) {$('#sim-result').innerHTML=`<div class="error-box">Jogo na linha ${index+1}: há ${item.key==='supersete'?'dígitos fora de 0–9':`dezenas fora de ${item.range.minimum}–${item.range.maximum}`}.</div>`;return;}
  }
  const target=$('#sim-result'); target.innerHTML='<div class="loading-block"><span class="spinner"></span>Conferindo...</div>';
  try {
    const contestText=$('#sim-contest')?.value.trim()||'';
    if (contestText&&(!/^\d+$/.test(contestText)||!Number.isSafeInteger(Number(contestText))||Number(contestText)<1)) {target.innerHTML=errorBlock('Informe um número de concurso inteiro e positivo, ou deixe o campo vazio para usar o último.');return;}
    const request={tickets};
    if (contestText) request.contest=Number(contestText);
    else request.draw=await api(`/${item.key}/latest`);
    const response=await api(`/${item.key}/simulate`,{method:'POST',body:JSON.stringify(request)});
    if (version!==renderVersion || state.page!=='simulator' || state.game!==item.key) return;
    const clientOrigin=response.draw_origin==='client_submitted';
    const draw=response.draw||{};
    const provenanceText=response.provenance?.description||(clientOrigin?'Dados enviados pelo navegador; o servidor não verificou sua origem.':'Origem do resultado não verificada independentemente.');
    const drawWarning=draw.warning||response.warning||response.provenance?.warning;
    state.simpleSimulation={response,tickets,game:item.key};
    target.innerHTML=`<div class="card" style="box-shadow:none;padding:12px;border-color:#dfe9de"><div class="card-head"><div><h3 class="card-title">Resultado do concurso ${esc(response.contest)}</h3><div class="card-subtitle">${esc(response.draw_date||'')}</div></div><span class="pill">${clientOrigin?'Dados enviados pelo navegador':'Origem não verificada'}</span></div><div class="small-note">${esc(provenanceText)} ${esc(draw.source?`Fonte informada pelo navegador: ${draw.source}.`:"")}</div>${drawWarning?`<div class="notice notice-warning">${esc(drawWarning)} · o concurso pode estar desatualizado; confirme na CAIXA.</div>`:""}<div class="ball-row">${balls(draw.numbers)}${draw.second_numbers?.length?balls(draw.second_numbers):''}${draw.trevos?.length?balls(draw.trevos,true):''}</div>${response.results.map(result=>{const awards=awardDisplay(result);return `<div class="draw-row"><div class="draw-title">Jogo ${esc(result.ticket_number)}</div><div>${result.main_hits!==undefined?`<b>${esc(result.main_hits)} acertos</b>`:`<b>${esc(result.hits)} colunas</b>`}${result.second_hits!==undefined?` · 2º sorteio ${esc(result.second_hits)}`:''} ${awards?`<span class="pill pill-warm">${esc(awards)}</span>`:'<span class="pill pill-muted">Sem faixa de premiação</span>'}${result.month_hit?'<span class="pill">Mês da Sorte</span>':''}${result.team_hit?'<span class="pill">Time do Coração</span>':''}${result.trevo_hits?`<span class="pill">${esc(result.trevo_hits)} trevos</span>`:''}</div></div>`}).join('')}<div class="form-actions"><button type="button" class="button" data-action="download-simple-report">Baixar relatório CSV</button></div><div class="small-note">O relatório é gerado no seu dispositivo; nada é salvo pelo servidor. A conferência é informativa; confirme premiações no portal oficial da CAIXA.</div></div>`;
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
function handleClick(event) {
  const pageButton=event.target.closest('[data-page]');
  const gameButton=event.target.closest('[data-game]');
  const modeButton=event.target.closest('[data-mode]');
  const numberButton=event.target.closest('.number-cell');
  const columnButton=event.target.closest('[data-column][data-digit]');
  const aiButton=event.target.closest('[data-action]');
  if (aiButton?.dataset.action==='ai-test') { testPersonalAIConfig(); return; }
  if (aiButton?.dataset.action==='ai-clear') { window.LotoMasterAI.clearConfig(); toast('Chave removida deste navegador'); render(); return; }
  if (aiButton?.dataset.action==='ai-use-candidate') {
    try {
      const item=spec(); const numbers=JSON.parse(aiButton.dataset.numbers);
      state.simulatorText=numbers.map(n=>padNum(n,item.digits)).join(' ');
      state.simulatorTickets=[]; state.simulatorBonus={}; state.page='simulator'; render();
    } catch(_) { toast('Não foi possível abrir essa combinação.'); }
    return;
  }
  if (pageButton) { if(state.page==='tools'&&state.game==='lotofacil')invalidateHistoryNumberSearch('Pesquisa cancelada ao sair da tela.'); state.page=pageButton.dataset.page; if (gameButton) { if(state.page==='tools'&&state.game==='lotofacil')invalidateHistoryNumberSearch('Pesquisa cancelada ao trocar de modalidade.'); state.game=gameButton.dataset.game; state.generated=[]; state.simulatorTickets=[]; state.simulatorText=''; state.simulatorBonus={}; } $('#sidebar').classList.remove('open'); render(); return; }
  if (gameButton) { if(state.page==='tools'&&state.game==='lotofacil')invalidateHistoryNumberSearch('Pesquisa cancelada ao trocar de modalidade.'); state.game=gameButton.dataset.game; state.page='overview'; state.generated=[]; state.simulatorTickets=[]; state.simulatorText=''; state.simulatorBonus={}; render(); return; }
  if (modeButton) { state.mode=modeButton.dataset.mode; $$('.pick-mode button').forEach(btn=>btn.classList.toggle('active',btn===modeButton)); return; }
  if (numberButton) {
    const wasFixed=numberButton.classList.contains('is-fixed'); const wasExcluded=numberButton.classList.contains('is-excluded');
    numberButton.classList.remove('is-fixed','is-excluded');
    if (state.mode==='fixed'&&!wasFixed) numberButton.classList.add('is-fixed');
    if (state.mode==='excluded'&&!wasExcluded) numberButton.classList.add('is-excluded');
    return;
  }
  if (columnButton) {
    const className=state.mode==='fixed'?'on-fixed':'on-excluded';
    const other=state.mode==='fixed'?'on-excluded':'on-fixed';
    const on=columnButton.classList.contains(className);
    columnButton.classList.remove('on-fixed','on-excluded');
    if (!on) columnButton.classList.add(className);
    else columnButton.classList.remove(other);
    columnButton.classList.toggle('on',!on);
    return;
  }
  if (event.target.closest('[data-action="assistant-generate"]')) { generateAssistantTicket(); return; }
  if (aiButton?.dataset.action==='import-prepare-simulator') { prepareImportForSimulator(); return; }
  if (aiButton?.dataset.action==='my-games-clear-filters') { clearMyGamesFilters(); return; }
  if (aiButton?.dataset.action==='my-game-remove') { removeMyGame(aiButton.dataset.gameId); return; }
  if (aiButton?.dataset.action==='my-game-use') { useMyGame(aiButton.dataset.gameId); return; }
  if (aiButton?.dataset.action==='download-simple-report') { downloadSimpleSimulation(); return; }
  if (aiButton?.dataset.action==='download-history-report') { downloadHistorySimulation(); return; }
  if (['results-latest','results-newer','results-older'].includes(aiButton?.dataset.action)) { navigateResultsHistory(aiButton.dataset.action); return; }
  if (aiButton?.dataset.action==='fill-all-contests') { fillAllAvailableContestRange(); return; }
  if (aiButton?.dataset.action==='closure-prev') { loadClosurePage(Math.max(0,Number(state.closureData?.offset||0)-Number(state.closureData?.page_size||0))); return; }
  if (aiButton?.dataset.action==='closure-next') { if(state.closureData?.next_offset!==null)loadClosurePage(Number(state.closureData?.next_offset)); return; }
  if (aiButton?.dataset.action==='repeated-prev') { loadRepeatedClosurePage(Math.max(0,Number(state.repeatedData?.offset||0)-Number(state.repeatedData?.page_size||0))); return; }
  if (aiButton?.dataset.action==='repeated-next') { if(state.repeatedData?.next_offset!==null)loadRepeatedClosurePage(Number(state.repeatedData?.next_offset)); return; }
  if (event.target.closest('[data-action="test-repeated"]')) {
    if (state.game!=='lotofacil'||state.repeatedTickets.length>500) {toast('O conferidor aceita até 500 jogos; nenhum jogo foi encaminhado.');return;}
    const item=spec(); state.simulatorTickets=state.repeatedTickets.map(ticket=>({...ticket}));
    state.simulatorText=state.simulatorTickets.map(ticket=>ticket.numbers.map(n=>padNum(n,item.digits)).join(' ')).join('\n');
    state.simulatorBonus={}; state.page='simulator'; render(); return;
  }
  if (event.target.closest('[data-action="test-closure"]')) {
    if(state.closureTickets.length>500) {toast('O conferidor aceita até 500 jogos; reduza a página ou filtre os aprovados. Nenhum jogo foi encaminhado.');return;}
    const item=spec();
    state.simulatorTickets=state.closureTickets.map(ticket=>({...ticket}));
    state.simulatorText=state.simulatorTickets.map(ticket=>ticket.numbers.map(n=>padNum(n,item.digits)).join(' ')).join('\n');
    state.simulatorBonus={}; state.page='simulator'; render(); return;
  }
  if (event.target.closest('[data-action="test-generated"]')) {
    const item=spec();
    state.simulatorText=state.generated.map(ticket=>item.key==='supersete'?ticket.numbers.join(' '):ticket.numbers.map(n=>padNum(n,item.digits)).join(' ')).join('\n');
    state.simulatorTickets=state.generated.map(ticket=>({numbers:ticket.numbers,columns:ticket.columns,bonus:ticket.bonus||{},ticket_number:ticket.ticket_number}));
    state.simulatorBonus=commonTicketBonus(state.generated);
    state.page='simulator'; render(); return;
  }
}
function handleChange(event) {
  if (event.target.id==='history-sort') renderHistorySimulation();
  if (event.target.id==='closure-view') changeClosureView('closure',event.target.value);
  if (event.target.id==='repeated-view') changeClosureView('repeated',event.target.value);
  if (event.target.id==='results-page-size') {
    const limit=Number(event.target.value), history=state.resultsHistory;
    if (![30,50,100].includes(limit)||!history||history.game!==state.game) return;
    history.limit=limit; history.cursors=[null]; history.index=0; history.page=null;
    loadResultsHistoryPage(renderVersion,0);
  }
}
async function handleSubmit(event) {
  if (event.target.id==='ai-config-form') { event.preventDefault(); savePersonalAIConfig(); return; }
  if (event.target.id==='ai-analysis-form') return runPersonalAIAnalysis(event);
  if (event.target.id==='generate-form') return handleGenerate(event);
  if (event.target.id==='simulate-form') return handleSimulate(event);
  if (event.target.id==='history-batch-form') return handleHistoryBatch(event);
}
async function init() {
  $('#main-content').innerHTML='<div class="loading-block"><span class="spinner"></span>Carregando modalidades...</div>';
  try {
    const data=await api('/lotteries'); state.catalog=data.items;
    renderGameNav();
    $('#game-picker').addEventListener('change',e=>{if(state.page==='tools'&&state.game==='lotofacil')invalidateHistoryNumberSearch('Pesquisa cancelada ao trocar de modalidade.');state.game=e.target.value;state.page='overview';state.generated=[];state.simulatorTickets=[];state.simulatorText='';state.simulatorBonus={};render();});
    $('#refresh-button').addEventListener('click',()=>refreshLiveData(true));
    $('#menu-toggle').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
    $('#main-content').addEventListener('click',handleClick);
    $('#main-content').addEventListener('change',handleChange);
    $('#main-content').addEventListener('submit',handleSubmit);
    $('#game-nav').addEventListener('click',event=>{const target=event.target.closest('[data-game]');if(target){if(state.page==='tools'&&state.game==='lotofacil')invalidateHistoryNumberSearch('Pesquisa cancelada ao trocar de modalidade.');state.game=target.dataset.game;state.page='overview';state.generated=[];state.simulatorTickets=[];state.simulatorText='';state.simulatorBonus={};render();}});
    $$('.section-nav [data-page]').forEach(button=>button.addEventListener('click',()=>{if(state.page==='tools'&&state.game==='lotofacil')invalidateHistoryNumberSearch('Pesquisa cancelada ao sair da tela.');state.page=button.dataset.page;render();}));
    await render();
    state.lastRefreshAt=Date.now();
    window.setInterval(()=>refreshLiveData(false),5*60*1000);
    document.addEventListener('visibilitychange',()=>{
      if (!document.hidden && Date.now()-(state.lastRefreshAt||0)>=5*60*1000) refreshLiveData(false);
    });
  } catch(error) { $('#main-content').innerHTML=errorBlock(`Não foi possível inicializar a Lotomaster: ${error.message}`); }
}
async function refreshLiveData(force) {
  if (!state.catalog.length || document.hidden) return;
  const page=state.page;
  const latest=await Promise.all(state.catalog.map(item=>api(`/${item.key}/latest`).then(draw=>({item,draw})).catch(()=>null)));
  state.lastRefreshAt=Date.now();
  if ($('#sync-status')) $('#sync-status').textContent=`Conferido ${new Date(state.lastRefreshAt).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}`;
  let changed=false;
  latest.filter(Boolean).forEach(({item,draw})=>{
    const current=Number(draw.contest);
    if (state.lastContests[item.key]!==undefined && state.lastContests[item.key]!==current) changed=true;
    state.lastContests[item.key]=current;
  });
  if (force || (changed && ['overview','results','statistics'].includes(page))) await render();
  if (changed && page==='assistant' && !force && $('#ai-progress')) $('#ai-progress').textContent='Novo concurso detectado pela atualização automática. Reexecute a análise para incluir esse resultado.';
}
window.addEventListener('DOMContentLoaded',init);
