const API = '/api/v1';
const state = {
  catalog: [], game: 'lotofacil', page: 'overview', mode: 'fixed',
  generated: [], simulatorText: '', simulatorTickets: [], simulatorBonus: {}, statId: 'frequency', statsPayload: null,
  resultCache: null, lastContests: {},
};
let renderVersion = 0;
const pageNames = {
  overview: 'Visão geral', generator: 'Gerador de jogos', simulator: 'Conferir jogos',
  results: 'Resultados', statistics: 'Tabelas e estatísticas', assistant: 'Assistente analítico', tools: 'Outras ferramentas',
};
const months = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function spec() { return state.catalog.find(item => item.key === state.game) || state.catalog[0]; }
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
    if (method==='GET' && window.lotomasterCaixaFallback && !error.recovered) {
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
    <div class="card-head"><div><h2 class="card-title">${esc(item.name)} · concurso ${esc(draw.contest)}</h2><div class="result-meta">${esc(draw.draw_date||'Data não informada')} · ${esc(draw.source||draw.location||'Portal da CAIXA')}</div></div><span class="pill ${draw.accumulated?'pill-warm':'pill-muted'}">${draw.accumulated?'Acumulado':'Apurado'}</span></div>
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
  const cards = successful.map(row=>`<div class="card"><div class="card-head"><div><h3 class="card-title">${esc(row.item.name)}</h3><div class="card-subtitle">Concurso ${esc(row.data.contest)} · ${esc(row.data.draw_date||'')}</div></div><span class="pill ${row.data.accumulated?'pill-warm':''}">${row.data.accumulated?'Acumulado':'Resultado'}</span></div><div class="ball-row">${balls(row.data.numbers,false,row.item.digits)}${row.data.trevos?.length?balls(row.data.trevos,true,2):''}</div><button class="button button-quiet" data-game="${esc(row.item.key)}" data-page="results">Ver histórico</button></div>`).join('');
  const failed = rows.filter(row=>row.error);
  $('#main-content').innerHTML = `${pageHeader('Painel de concursos','Resultados e estatísticas','Consulte os últimos concursos oficiais e abra as ferramentas disponíveis para cada modalidade.',`<button class="button button-primary" data-page="generator">✦ Gerar jogos</button>`)}
    <div class="grid grid-2" style="margin-bottom:16px">${active?.data?resultCard(active.data,active.item):`<div class="card">${errorBlock(active?.error?.message||'Resultado indisponível.')}</div>`}
      <div class="grid" style="align-content:start"><div class="grid grid-2"><div class="card kpi"><div class="kpi-top"><span>Modalidades disponíveis</span><span class="kpi-icon">▦</span></div><div class="kpi-value">${state.catalog.length}</div><div class="kpi-foot">Loterias oficiais da CAIXA</div></div><div class="card kpi"><div class="kpi-top"><span>Fonte de resultados</span><span class="kpi-icon">↻</span></div><div class="kpi-value" style="font-size:16px">CAIXA</div><div class="kpi-foot">API oficial via Worker; cache local</div></div></div>
      <div class="card"><div class="card-head"><div><h2 class="card-title">Atalhos da modalidade</h2><div class="card-subtitle">Ferramentas correspondentes às páginas públicas da referência</div></div></div><div class="form-actions"><button class="button" data-page="generator">Gerador</button><button class="button" data-page="simulator">Conferir jogos</button><button class="button" data-page="results">Resultados</button><button class="button" data-page="statistics">Estatísticas</button></div></div></div>
    </div><div class="card"><div class="card-head"><div><h2 class="card-title">Resultados recentes por modalidade</h2><div class="card-subtitle">API pública da CAIXA via Worker de leitura</div></div><span class="pill">${successful.length} de ${state.catalog.length} disponíveis</span></div><div class="grid grid-3">${cards||'<div class="empty-state">Nenhum resultado retornado.</div>'}</div>${failed.length?`<div class="small-note" style="margin-top:12px">Temporariamente indisponíveis: ${failed.map(row=>esc(row.item.name)).join(', ')}.</div>`:''}</div>
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
  if (item.bonus.type==='team') return `<div class="field"><label for="bonus-team">Time do Coração</label><input id="bonus-team" placeholder="Informe o time para testar" maxlength="80"><span class="field-help">A CAIXA informa o time sorteado no resultado.</span></div>`;
  if (item.bonus.type==='trevos') return `<div class="field"><label for="trevo-count">Quantidade de trevos</label><select id="trevo-count">${Array.from({length:5},(_,i)=>`<option value="${i+2}" ${i===0?'selected':''}>${i+2} trevos</option>`).join('')}</select></div>`;
  return '';
}
function filtersFields() {
  return `<div class="card"><div class="card-head"><div><h2 class="card-title">Filtros e regras</h2><div class="card-subtitle">Restrições opcionais para compor a combinação; não aumentam a chance do sorteio.</div></div></div><div class="form-grid"><div class="field"><label for="filter-sum-min">Soma mínima</label><input id="filter-sum-min" type="number" placeholder="Sem limite" min="0"></div><div class="field"><label for="filter-sum-max">Soma máxima</label><input id="filter-sum-max" type="number" placeholder="Sem limite" min="0"></div><div class="field"><label for="filter-even-min">Mínimo de pares</label><input id="filter-even-min" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="filter-even-max">Máximo de pares</label><input id="filter-even-max" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="filter-repeat-min">Mínimo repetidas do último</label><input id="filter-repeat-min" type="number" min="0" placeholder="Sem limite"></div><div class="field"><label for="filter-repeat-max">Máximo repetidas do último</label><input id="filter-repeat-max" type="number" min="0" placeholder="Sem limite"></div></div></div>`;
}
async function renderGenerator() {
  const item=spec();
  const pickOptions = item.key==='lotomania' || item.key==='timemania' || item.key==='supersete' || item.key==='maismilionaria' ? [item.pick_size] : Array.from({length:item.max_pick-item.min_pick+1},(_,i)=>i+item.min_pick);
  $('#main-content').innerHTML = `${pageHeader('Ferramentas · '+item.name,'Gerador de jogos',`Monte jogos para ${item.name} com dezenas fixas, removidas e filtros opcionais.`)}
    <div class="notice"><span>✦</span><span>O gerador é aleatório. Frequências e filtros servem para organizar seus jogos, não para prever o resultado nem melhorar a probabilidade matemática.</span></div>
    ${item.key==='supersete'?superSeteGrid():pickGrid(item)}
    <form id="generate-form" class="card" style="margin-top:15px"><div class="card-head"><div><h2 class="card-title">Configuração do gerador</h2><div class="card-subtitle">${esc(item.name)} · ${item.draw_size} dezenas sorteadas por concurso</div></div></div><div class="form-grid"><div class="field"><label for="game-count">Quantidade de jogos</label><input id="game-count" type="number" min="1" max="100" value="1"></div>${pickOptions.length>1?`<div class="field"><label for="pick-count">Dezenas no jogo</label><select id="pick-count">${pickOptions.map(n=>`<option value="${n}" ${n===item.pick_size?'selected':''}>${n} dezenas</option>`).join('')}</select></div>`:''}${bonusFields(item)}</div><div class="form-actions"><button class="button button-primary" type="submit">✦ Gerar combinação</button><button class="button" type="button" data-page="tools">Abrir calculadora</button></div><div id="generated-output" style="margin-top:14px"></div></form>
    ${filtersFields()}`;
}
function parseNumberLines(raw) {
  return raw.split(/\n+/).map(line=>line.trim()).filter(Boolean).map(line=>line.split(/[\s,;|]+/).filter(Boolean).map(Number)).filter(row=>row.every(Number.isFinite));
}
async function renderSimulator() {
  const item=spec();
  const example=item.key==='supersete'?'3 0 6 6 0 5 4':item.key==='lotofacil'?'01 03 04 06 07 08 09 10 11 13 15 17 19 22 25':Array.from({length:item.pick_size},(_,i)=>padNum(item.range.minimum+i)).join(' ');
  const bonusInput=item.bonus?.type==='month'?`<div class="field"><label for="sim-month">Mês da Sorte</label><select id="sim-month"><option value="">Não informado</option>${months.map((m,i)=>`<option value="${i+1}" ${Number(state.simulatorBonus?.month)===i+1?'selected':''}>${m}</option>`).join('')}</select></div>`:item.bonus?.type==='team'?`<div class="field"><label for="sim-team">Time do Coração</label><input id="sim-team" placeholder="Nome do time" value="${esc(state.simulatorBonus?.team||'')}"></div>`:item.bonus?.type==='trevos'?`<div class="field"><label for="sim-trevos">Trevos marcados</label><input id="sim-trevos" placeholder="Ex.: 2, 5" value="${esc((state.simulatorBonus?.trevos||[]).join(', '))}"></div>`:'';
  $('#main-content').innerHTML = `${pageHeader('Conferência · '+item.name,'Simulador de jogos',`Compare um ou mais jogos com o resultado oficial mais recente de ${item.name}.`)}
    <div class="grid grid-2"><form id="simulate-form" class="card"><div class="card-head"><div><h2 class="card-title">Seus jogos</h2><div class="card-subtitle">Um jogo por linha; separe as dezenas com espaço, vírgula ou ponto e vírgula.</div></div></div><div class="field"><label for="sim-numbers">Dezenas selecionadas</label><textarea id="sim-numbers" placeholder="${esc(example)}">${esc(state.simulatorText||'')}</textarea><span class="field-help">${item.key==='supersete'?'Informe 7 dígitos em ordem de coluna.':'Você pode colar vários jogos, um por linha.'}</span></div><div class="form-grid" style="margin-top:10px">${bonusInput}</div><div class="form-actions"><button class="button button-primary" type="submit">✓ Conferir com o último resultado</button><button class="button" type="button" data-page="results">Abrir histórico</button></div></form><div class="card"><div class="card-head"><div><h2 class="card-title">Como funciona</h2><div class="card-subtitle">Conferência local contra o concurso oficial consultado</div></div></div><div class="metric-list"><div class="draw-row"><div class="draw-row-main"><div class="draw-title">1 · Insira seu jogo</div><div class="draw-caption">Use dezenas do intervalo mostrado pela modalidade.</div></div></div><div class="draw-row"><div class="draw-row-main"><div class="draw-title">2 · Compare acertos</div><div class="draw-caption">O sistema informa a quantidade e faixas de acerto.</div></div></div><div class="draw-row"><div class="draw-row-main"><div class="draw-title">3 · Confira na CAIXA</div><div class="draw-caption">A confirmação final de prêmios deve ser feita no portal oficial.</div></div></div></div><div id="sim-result" style="margin-top:14px"></div></div></div>`;
}
async function renderResults() {
  const item=spec(); const version=renderVersion;
  $('#main-content').innerHTML = `${pageHeader('Histórico · '+item.name,'Resultados dos sorteios',`Concursos oficiais de ${item.name}, com ordenação do mais recente para o mais antigo.`,`<a class="button" href="${API}/${item.key}/export.csv?limit=100">↓ Exportar CSV</a><a class="button" href="${API}/${item.key}/export.txt?limit=100">↓ Exportar TXT</a>`)}<div class="card"><div class="card-head"><div><h2 class="card-title">Histórico recente</h2><div class="card-subtitle">Até 30 concursos · dados consultados e armazenados em cache local</div></div><span id="history-count" class="pill">Consultando…</span></div><div id="history-table"><div class="loading-block"><span class="spinner"></span>Buscando concursos recentes...</div></div></div>`;
  try {
    const data=await api(`/${item.key}/results?limit=30`);
    if (version!==renderVersion || state.page!=='results' || state.game!==item.key) return;
    $('#history-count').textContent=`${data.count} concursos`;
    const rows=data.items.map(draw=>`<tr><td class="table-number">${esc(draw.contest)}</td><td>${esc(draw.draw_date||'')}</td><td>${balls(draw.numbers)} ${draw.second_numbers?.length?`<div class="small-note">2º sorteio: ${draw.second_numbers.map(n=>padNum(n,item.digits)).join(' · ')}</div>`:''}</td><td>${draw.trevos?.length?balls(draw.trevos,true):draw.month?.name?esc(draw.month.name):draw.team?esc(draw.team):'—'}</td><td>${draw.accumulated?'<span class="pill pill-warm">Acumulado</span>':'—'}</td><td>${esc(money(draw.estimated_prize))}</td></tr>`).join('');
    $('#history-table').innerHTML=rows?`<div class="table-wrap"><table><thead><tr><th>Concurso</th><th>Data</th><th>Dezenas sorteadas</th><th>Complemento</th><th>Status</th><th>Próximo prêmio</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<div class="empty-state">Não foram retornados concursos.</div>';
  } catch(error) { $('#history-table').innerHTML=errorBlock(error.message); $('#history-count').textContent='Sem conexão'; }
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
    $('#stats-highlights').innerHTML=`<div class="stats-highlight"><div class="mini-stat"><small>Números analisados</small><b>${esc(data.draws_analyzed)}</b></div><div class="mini-stat"><small>Concurso mais recente</small><b>${esc(data.latest_contest||'—')}</b></div><div class="mini-stat"><small>Repetidas do anterior</small><b>${esc(data.repeated_from_previous)}</b></div><div class="mini-stat"><small>Soma mais recente</small><b>${esc(data.sum?.latest??'—')}</b></div></div>`;
    const id=$('#stat-picker').value; state.statId=id;
    const table=data.tables?.[id];
    container.innerHTML=table?`<h3 class="card-title" style="margin:0 0 12px">${esc(table.title)}</h3>${statTable(table)}`:'<div class="empty-state">Esta tabela ainda não possui cálculo separado. Consulte a análise geral.</div>';
  } catch(error) { container.innerHTML=errorBlock(error.message); }
}
async function renderAssistant() {
  const item=spec(); const version=renderVersion;
  $('#main-content').innerHTML=`${pageHeader('Análise explicável · '+item.name,'Assistente analítico',`Resumo do histórico oficial, com seleção aleatória e limites científicos explícitos.`)}<div class="notice"><span>ⓘ</span><span>O assistente descreve dados observados; frequência e atraso não predizem concursos futuros. Não há probabilidades calibradas fora da amostra para dezenas individuais.</span></div><div class="card"><div class="card-head"><div><h2 class="card-title">Leitura do histórico</h2><div class="card-subtitle">Amostra inicial de até 50 concursos; os cálculos e odds teóricas ficam separados.</div></div><span id="assistant-status" class="pill">Analisando…</span></div><div id="assistant-content"><div class="loading-block"><span class="spinner"></span>Consultando resultados oficiais e calculando estatísticas...</div></div></div><div class="card" style="margin-top:16px"><div class="card-head"><div><h2 class="card-title">Gerar combinação aleatória</h2><div class="card-subtitle">A IA não favorece dezenas históricas; cada combinação legal mantém a chance teórica definida pelas regras.</div></div></div><div class="form-actions"><button class="button button-primary" data-action="assistant-generate">Montar uma combinação aleatória</button></div><div id="assistant-ticket"></div></div>`;
  try {
    const data=await api(`/${item.key}/assistant?limit=50`);
    if (version!==renderVersion || state.page!=='assistant' || state.game!==item.key) return;
    $('#assistant-status').textContent=data.ai?.status==='available'?`Gemini · ${data.ai.model}`:'Análise explicável local';
    const top=(data.historical_summary?.most_frequent||[]).slice(0,5).map(row=>`${padNum(row.number,item.digits)} (${row.count})`).join(' · ')||'—';
    const low=(data.historical_summary?.least_frequent||[]).slice(0,5).map(row=>`${padNum(row.number,item.digits)} (${row.count})`).join(' · ')||'—';
    $('#assistant-content').innerHTML=`<div class="stats-highlight"><div class="mini-stat"><small>Concursos analisados</small><b>${esc(data.draws_analyzed)}</b></div><div class="mini-stat"><small>Concurso mais recente</small><b>${esc(data.latest_contest||'—')}</b></div><div class="mini-stat"><small>Maiores contagens observadas</small><b>${esc(top)}</b></div><div class="mini-stat"><small>Menores contagens observadas</small><b>${esc(low)}</b></div></div><p>${esc(data.commentary)}</p><div class="notice"><span>ⓘ</span><span>${esc(data.disclaimer)}</span></div>`;
  } catch(error) {
    if (version!==renderVersion) return;
    $('#assistant-status').textContent='Sem conexão';
    $('#assistant-content').innerHTML=errorBlock(error.message);
  }
}
async function generateAssistantTicket() {
  const item=spec(); const target=$('#assistant-ticket');
  if (!target) return;
  target.innerHTML='<div class="loading-block"><span class="spinner"></span>Gerando combinação aleatória...</div>';
  try {
    const data=await api(`/${item.key}/generate`,{method:'POST',body:JSON.stringify({count:1})});
    const ticket=data.items[0];
    target.innerHTML=`<div class="generated-ticket"><div class="generated-ticket-head"><b>Jogo aleatório</b><span class="pill">Sem ponderação histórica</span></div>${item.key==='supersete'?`<div class="col-grid">${ticket.columns.map((values,index)=>`<div class="col-box"><strong>COLUNA ${index+1}</strong>${balls(values)}</div>`).join('')}</div>`:`<div class="ball-row">${balls(ticket.numbers,false,item.digits)}</div>`}<div class="ticket-stats">Chance combinatória teórica por jogo: 1 em ${esc(Number(ticket.probability.one_in).toLocaleString('pt-BR'))}</div><div class="small-note">${esc(data.disclaimer)}</div></div>`;
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
async function renderTools() {
  const item=spec(); const version=renderVersion;
  let tools=[];
  try { tools=(await api(`/${item.key}/tools`)).tools; } catch(_) {}
  if (version!==renderVersion || state.page!=='tools' || state.game!==item.key) return;
  const toolCards=tools.map(tool=>`<div class="card tool-card"><div><div class="tool-icon">${tool.id==='probability'?'∑':tool.id==='export'?'↓':tool.id==='closures'?'▧':'⌘'}</div><h3 class="card-title" style="margin-top:10px">${esc(tool.name)}</h3><p>${tool.available?'Disponível nesta versão.':esc(tool.note||'')}</p></div><span class="pill ${tool.available?'':'pill-muted'}">${tool.available?'Disponível':'Em desenvolvimento'}</span></div>`).join('');
  $('#main-content').innerHTML=`${pageHeader('Recursos · '+item.name,'Ferramentas adicionais',`Recursos públicos de apoio a jogos e consultas de ${item.name}.`)}<div class="grid grid-3">${toolCards}</div><div class="grid grid-2" style="margin-top:16px"><form class="card" id="probability-form"><div class="card-head"><div><h2 class="card-title">Calculadora de probabilidades</h2><div class="card-subtitle">Combinações teóricas para a quantidade de dezenas escolhida</div></div></div><div class="form-grid"><div class="field"><label for="prob-picks">Dezenas selecionadas</label><input id="prob-picks" type="number" min="${item.min_pick}" max="${item.max_pick}" value="${item.pick_size}"></div>${item.bonus?.type==='trevos'?'<div class="field"><label for="prob-trevos">Trevos selecionados</label><select id="prob-trevos">'+Array.from({length:5},(_,i)=>`<option value="${i+2}">${i+2}</option>`).join('')+'</select></div>':''}</div><div class="form-actions"><button class="button button-primary" type="submit">Calcular</button></div><div id="prob-result" style="margin-top:12px"></div></form><form class="card" id="import-form"><div class="card-head"><div><h2 class="card-title">Importar jogos por texto</h2><div class="card-subtitle">Cole uma combinação por linha para enviar ao conferidor.</div></div></div><div class="field"><label for="import-text">Jogos</label><textarea id="import-text" placeholder="01 05 12 ..."></textarea></div><div class="form-actions"><button type="submit" class="button button-primary">Preparar conferência</button></div></form></div><div class="notice notice-warning"><span>ⓘ</span><span>Fechamentos exaustivos podem gerar milhões de combinações e não estão ativados nesta versão. As áreas Premium do site de referência não foram acessadas nem simuladas.</span></div>`;
  $('#probability-form').addEventListener('submit',calculateProbability);
    $('#import-form').addEventListener('submit',e=>{e.preventDefault();state.simulatorText=$('#import-text').value;state.simulatorTickets=[];state.simulatorBonus={};state.page='simulator';render();});
}
async function calculateProbability(event) {
  event.preventDefault(); const item=spec(); const version=renderVersion;
  const picks=$('#prob-picks').value; const trevos=$('#prob-trevos')?.value||2;
  const target=$('#prob-result'); target.innerHTML='<span class="spinner"></span>';
  try {
    const data=await api(`/${item.key}/probability?pick_count=${encodeURIComponent(picks)}&trevo_count=${encodeURIComponent(trevos)}`);
    if (version!==renderVersion || state.page!=='tools' || state.game!==item.key) return;
    target.innerHTML=`<div class="stats-highlight"><div class="mini-stat"><small>${esc(data.event)}</small><b>1 em ${esc(Number(data.one_in).toLocaleString('pt-BR'))}</b></div><div class="mini-stat"><small>Percentual teórico</small><b>${esc(Number(data.percent).toExponential(3))}%</b></div></div><div class="small-note">${esc(data.method)} Sorteios são aleatórios e independentes.</div>`;
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
async function handleGenerate(event) {
  event.preventDefault(); const item=spec(); const version=renderVersion;
  const payload={count:Number($('#game-count').value||1),filters:{
    min_sum:$('#filter-sum-min').value||null,max_sum:$('#filter-sum-max').value||null,
    min_even:$('#filter-even-min').value||null,max_even:$('#filter-even-max').value||null,
    min_repeated:$('#filter-repeat-min').value||null,max_repeated:$('#filter-repeat-max').value||null,
  }};
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
    target.innerHTML=response.items.map(ticket=>`<div class="generated-ticket"><div class="generated-ticket-head"><b>Jogo ${esc(ticket.ticket_number)}</b><span class="pill">Aleatório</span></div>${item.key==='supersete'?`<div class="col-grid">${ticket.columns.map((values,i)=>`<div class="col-box"><strong>COLUNA ${i+1}</strong>${balls(values)}</div>`).join('')}</div>`:`<div class="ball-row">${balls(ticket.numbers)}</div>`}${ticket.bonus?.month?`<div class="ticket-stats">Mês da Sorte: ${esc(months[Number(ticket.bonus.month)-1]||ticket.bonus.month)}</div>`:''}${ticket.bonus?.team?`<div class="ticket-stats">Time do Coração: ${esc(ticket.bonus.team)}</div>`:''}${ticket.bonus?.trevos?`<div class="ticket-stats">Trevos: ${balls(ticket.bonus.trevos,true)}</div>`:''}<div class="ticket-stats"><span>Soma: ${esc(ticket.sum??'—')}</span><span>Pares: ${esc(ticket.even_count)}</span><span>Ímpares: ${esc(ticket.odd_count)}</span><span>Repetidas do último: ${esc(ticket.repeated_from_latest)}</span><span>Chance teórica por jogo: 1 em ${esc(Number(ticket.probability.one_in).toLocaleString('pt-BR'))}</span></div></div>`).join('')+`<div class="form-actions"><button class="button button-primary" data-action="test-generated">Conferir estes jogos</button><a class="button" href="${API}/${item.key}/export.csv?limit=100">↓ Exportar histórico</a></div><div class="small-note">${esc(response.disclaimer)}</div>`;
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
async function handleSimulate(event) {
  event.preventDefault(); const item=spec(); const version=renderVersion;
  const typed=$('#sim-numbers').value;
  let tickets;
  if (state.simulatorTickets.length && typed===state.simulatorText) {
    tickets=state.simulatorTickets;
  } else {
    const parsed=parseNumberLines(typed);
    if (!parsed.length) { $('#sim-result').innerHTML=errorBlock('Digite ao menos um jogo.'); return; }
    const bonus={};
    if (item.bonus?.type==='month'&&$('#sim-month').value) bonus.month=Number($('#sim-month').value);
    if (item.bonus?.type==='team'&&$('#sim-team').value) bonus.team=$('#sim-team').value.trim();
    if (item.bonus?.type==='trevos'&&$('#sim-trevos').value) bonus.trevos=parseNumberLines($('#sim-trevos').value)[0]||[];
    tickets=parsed.map((numbers,index)=>({numbers,ticket_number:index+1,bonus}));
    if (item.key==='supersete') tickets.forEach(ticket=>ticket.columns=ticket.numbers.map(n=>[n]));
  }
  const target=$('#sim-result'); target.innerHTML='<div class="loading-block"><span class="spinner"></span>Conferindo...</div>';
  try {
    const draw=await api(`/${item.key}/latest`);
    const response=await api(`/${item.key}/simulate`,{method:'POST',body:JSON.stringify({tickets,draw})});
    if (version!==renderVersion || state.page!=='simulator' || state.game!==item.key) return;
    target.innerHTML=`<div class="card" style="box-shadow:none;padding:12px;border-color:#dfe9de"><div class="card-head"><div><h3 class="card-title">Resultado do concurso ${esc(response.contest)}</h3><div class="card-subtitle">${esc(response.draw_date||'')}</div></div><span class="pill">Oficial</span></div><div class="ball-row">${balls(response.draw.numbers)}${response.draw.second_numbers?.length?balls(response.draw.second_numbers):''}${response.draw.trevos?.length?balls(response.draw.trevos,true):''}</div>${response.results.map(result=>`<div class="draw-row"><div class="draw-title">Jogo ${esc(result.ticket_number)}</div><div>${result.main_hits!==undefined?`<b>${esc(result.main_hits)} acertos</b>`:`<b>${esc(result.hits)} colunas</b>`}${result.second_hits!==undefined?` · 2º sorteio ${esc(result.second_hits)}`:''} ${result.award?`<span class="pill pill-warm">${esc(typeof result.award==='string'?result.award:JSON.stringify(result.award))}</span>`:'<span class="pill pill-muted">Sem faixa de premiação</span>'}${result.month_hit?'<span class="pill">Mês da Sorte</span>':''}${result.team_hit?'<span class="pill">Time do Coração</span>':''}${result.trevo_hits?`<span class="pill">${esc(result.trevo_hits)} trevos</span>`:''}</div></div>`).join('')}<div class="small-note">A conferência é informativa; confirme premiações no portal oficial da CAIXA.</div></div>`;
  } catch(error) { target.innerHTML=errorBlock(error.message); }
}
function handleClick(event) {
  const pageButton=event.target.closest('[data-page]');
  const gameButton=event.target.closest('[data-game]');
  const modeButton=event.target.closest('[data-mode]');
  const numberButton=event.target.closest('.number-cell');
  const columnButton=event.target.closest('[data-column][data-digit]');
  if (pageButton) { state.page=pageButton.dataset.page; if (gameButton) { state.game=gameButton.dataset.game; state.generated=[]; state.simulatorTickets=[]; state.simulatorText=''; state.simulatorBonus={}; } $('#sidebar').classList.remove('open'); render(); return; }
  if (gameButton) { state.game=gameButton.dataset.game; state.page='overview'; state.generated=[]; state.simulatorTickets=[]; state.simulatorText=''; state.simulatorBonus={}; render(); return; }
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
  if (event.target.closest('[data-action="test-generated"]')) {
    const item=spec();
    state.simulatorText=state.generated.map(ticket=>item.key==='supersete'?ticket.numbers.join(' '):ticket.numbers.map(n=>padNum(n,item.digits)).join(' ')).join('\n');
    state.simulatorTickets=state.generated.map(ticket=>({numbers:ticket.numbers,columns:ticket.columns,bonus:ticket.bonus||{},ticket_number:ticket.ticket_number}));
    state.simulatorBonus=state.generated[0]?.bonus||{};
    state.page='simulator'; render(); return;
  }
}
async function handleSubmit(event) {
  if (event.target.id==='generate-form') return handleGenerate(event);
  if (event.target.id==='simulate-form') return handleSimulate(event);
}
async function init() {
  $('#main-content').innerHTML='<div class="loading-block"><span class="spinner"></span>Carregando modalidades...</div>';
  try {
    const data=await api('/lotteries'); state.catalog=data.items;
    renderGameNav();
    $('#game-picker').addEventListener('change',e=>{state.game=e.target.value;state.page='overview';state.generated=[];state.simulatorTickets=[];state.simulatorText='';state.simulatorBonus={};render();});
    $('#refresh-button').addEventListener('click',()=>refreshLiveData(true));
    $('#menu-toggle').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
    $('#main-content').addEventListener('click',handleClick);
    $('#main-content').addEventListener('submit',handleSubmit);
    $('#game-nav').addEventListener('click',event=>{const target=event.target.closest('[data-game]');if(target){state.game=target.dataset.game;state.page='overview';state.generated=[];state.simulatorTickets=[];state.simulatorText='';state.simulatorBonus={};render();}});
    $$('.section-nav [data-page]').forEach(button=>button.addEventListener('click',()=>{state.page=button.dataset.page;render();}));
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
  if (force || (changed && ['overview','results','statistics','assistant'].includes(page))) await render();
}
window.addEventListener('DOMContentLoaded',init);
