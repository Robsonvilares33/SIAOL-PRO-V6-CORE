/* Recuperação somente leitura: consulta a API pública da CAIXA via Worker e mantém cache local. */
(() => {
  const CAIXA = 'https://lotomaster-caixa-proxy-test.robsonboiling.workers.dev';
  const GAMES = {
    megasena: { key: 'megasena', name: 'Mega-Sena', endpoint: 'megasena' },
    lotofacil: { key: 'lotofacil', name: 'Lotofácil', endpoint: 'lotofacil' },
    lotomania: { key: 'lotomania', name: 'Lotomania', endpoint: 'lotomania' },
    quina: { key: 'quina', name: 'Quina', endpoint: 'quina' },
    diadesorte: { key: 'diadesorte', name: 'Dia de Sorte', endpoint: 'diadesorte' },
    duplasena: { key: 'duplasena', name: 'Dupla Sena', endpoint: 'duplasena' },
    timemania: { key: 'timemania', name: 'Timemania', endpoint: 'timemania' },
    supersete: { key: 'supersete', name: 'Super Sete', endpoint: 'supersete' },
    maismilionaria: { key: 'maismilionaria', name: '+Milionária', endpoint: 'maismilionaria' },
  };
  const RULES = {megasena:[6,1,60],lotofacil:[15,1,25],lotomania:[20,0,99],quina:[5,1,80],diadesorte:[7,1,31],duplasena:[6,1,50],timemania:[7,1,80],supersete:[7,0,9],maismilionaria:[6,1,50]};
  const MONTHS = {
    janeiro: 1, fevereiro: 2, marco: 3, 'março': 3, abril: 4, maio: 5, junho: 6,
    julho: 7, agosto: 8, setembro: 9, outubro: 10, novembro: 11, dezembro: 12,
  };
  const SOURCE = 'CAIXA — API oficial via Cloudflare Worker';
  // Version the slot so an older release's historical overwrite cannot persist.
  const latestKey = item => `lotomaster:caixa:latest:v2:${item.key}`;
  const REQUEST_TIMEOUT_MS = 20000;
  const HISTORY_BUDGET_MS = 15000;

  function integers(values) {
    if (values == null) return [];
    if (!Array.isArray(values) || values.length > 20) throw new Error('Lista de dezenas inválida ou excessiva.');
    return values.map(value => {
      if (typeof value === 'number' && Number.isInteger(value)) return value;
      if (typeof value === 'string' && /^[0-9]{1,3}$/.test(value.trim())) return Number(value.trim());
      throw new Error('Dezena inválida na resposta.');
    });
  }
  function text(value) {
    if (value == null) return null;
    const clean = String(value).replace(/\s/g, ' ').replace(/[\u0000-\u001f\u007f-\u009f]/g, '').replace(/ +/g, ' ').trim();
    return clean || null;
  }
  // Mirrors validate_draw(require_game=True, require_special=True). Revalidate caches too.
  function validate(item, draw) {
    const rule = RULES[item.key];
    if (!rule || !draw || draw.game !== item.key || !Number.isInteger(draw.contest) || draw.contest < 1 || draw.contest > 1000000000) throw new Error('Concurso inválido.');
    const [size, low, high] = rule;
    function sequence(xs, n, min, max, unique=true) {
      if (!Array.isArray(xs) || xs.length !== n || xs.some(x=>!Number.isInteger(x)||x<min||x>max) || (unique && new Set(xs).size!==n)) throw new Error('Resultado inválido para a modalidade.');
    }
    sequence(draw.numbers,size,low,high,item.key!=='supersete');
    const second=draw.second_numbers, trevos=draw.trevos;
    if (item.key==='duplasena') sequence(second,6,1,50);
    else if (second != null && (!Array.isArray(second) || second.length)) throw new Error('Segundo sorteio incompatível.');
    if (item.key==='maismilionaria') sequence(trevos,2,1,6);
    else if (trevos != null && (!Array.isArray(trevos) || trevos.length)) throw new Error('Trevos incompatíveis.');
    const ordered=draw.ordered_numbers;
    const same=(a,b)=>JSON.stringify([...a].sort((x,y)=>x-y))===JSON.stringify([...b].sort((x,y)=>x-y));
    if (ordered != null && (!Array.isArray(ordered) || ordered.length)) {
      const extra = item.key==='duplasena'?second:item.key==='maismilionaria'?trevos:[];
      if (!Array.isArray(ordered) || (ordered.length!==size && ordered.length!==size+extra.length)) throw new Error('Ordem inválida.');
      sequence(ordered.slice(0,size),size,low,high,item.key!=='supersete');
      if (item.key==='supersete' ? JSON.stringify(ordered.slice(0,size))!==JSON.stringify(draw.numbers) : !same(ordered.slice(0,size),draw.numbers)) throw new Error('Ordem contraditória.');
      if (ordered.length>size) { sequence(ordered.slice(size),extra.length,1,item.key==='duplasena'?50:6); if (!same(ordered.slice(size),extra)) throw new Error('Extras contraditórios.'); }
    }
    if (item.key==='diadesorte') {
      if (!draw.month || typeof draw.month.name!=='string' || draw.month.name.length>20 || MONTHS[draw.month.name.toLowerCase()]!==draw.month.number || !Number.isInteger(draw.month.number)) throw new Error('Mês inválido.');
    } else if (draw.month != null) throw new Error('Mês incompatível.');
    if (item.key==='timemania') {
      if (typeof draw.team!=='string' || !draw.team.trim() || draw.team.length>100) throw new Error('Time inválido.');
    } else if (draw.team != null) throw new Error('Time incompatível.');
    if (![draw.estimated_prize, draw.next_prize].every(value=>typeof value==='number'&&Number.isFinite(value)&&value>=0)) throw new Error('Valor monetário inválido.');
    if (!Array.isArray(draw.winners_by_tier) || draw.winners_by_tier.some(tier=>
      !tier || !Number.isSafeInteger(tier.winners) || tier.winners<0
      || typeof tier.prize!=='number' || !Number.isFinite(tier.prize) || tier.prize<0
    )) throw new Error('Rateio de prêmios inválido.');
    if ('special_draw' in draw && typeof draw.special_draw!=='boolean') throw new Error('Indicador especial inválido.');
    return draw;
  }
  function validCached(item, draw) { try { return validate(item,draw); } catch (_) { return null; } }
  function normalize(item, raw) {
    let numbers = integers(raw.listaDezenas ?? raw.dezenasSorteadasOrdemSorteio);
    const ordered = integers(raw.dezenasSorteadasOrdemSorteio);
    // A combined eight-value +Milionária list ends with two trevos.
    const combinedTrevos = item.key === 'maismilionaria' && numbers.length === 8 ? numbers.slice(6) : [];
    if ((raw.listaDezenas == null && ['duplasena', 'maismilionaria'].includes(item.key)) || combinedTrevos.length) numbers = numbers.slice(0, 6);
    if (item.key !== 'supersete') numbers.sort((a, b) => a - b);
    let second = integers(raw.listaDezenasSegundoSorteio);
    if (item.key === 'duplasena' && !second.length && ordered.length >= 12) second = ordered.slice(6, 12);
    let trevos = integers(raw.trevosSorteados);
    if (item.key === 'maismilionaria') {
      const candidates=[combinedTrevos, ordered.length===8?ordered.slice(6):[], trevos].filter(x=>x.length);
      const canonical=x=>JSON.stringify([...x].sort((a,b)=>a-b));
      if (candidates.some(x=>canonical(x)!==canonical(candidates[0]))) throw new Error('Trevos contraditórios na resposta.');
      if (!trevos.length) trevos = ordered.length===8 ? ordered.slice(6) : combinedTrevos;
    }
    const special = text(raw.nomeTimeCoracaoMesSorte);
    const monthNumber = item.key === 'diadesorte' && special ? (MONTHS[special.toLocaleLowerCase('pt-BR')] || null) : null;
    const awards = (raw.listaRateioPremio || []).map(row => ({
      label: text(row.descricaoFaixa) || 'Faixa',
      winners: Number(row.numeroDeGanhadores || 0),
      prize: Number(row.valorPremio || 0),
    }));
    if (!(Number.isInteger(raw.numero) || (typeof raw.numero==='string' && /^[0-9]{1,10}$/.test(raw.numero)))) throw new Error('Concurso inválido.');
    return validate(item, {
      game: item.key, name: item.name, contest: Number(raw.numero || 0),
      draw_date: text(raw.dataApuracao), next_draw_date: text(raw.dataProximoConcurso),
      numbers, ordered_numbers: ordered.length ? ordered : numbers, second_numbers: second,
      trevos,
      month: item.key === 'diadesorte' && special ? { name: special, number: monthNumber } : null,
      team: item.key === 'timemania' ? special : null,
      // CAIXA uses 1 for regular contests and 2 for special contests.
      special_draw: ['true', '2', 's', 'sim'].includes(String(raw.indicadorConcursoEspecial || '').trim().toLowerCase()),
      contest_type: text(raw.tipoJogo), accumulated: Boolean(raw.acumulado),
      estimated_prize: Number(raw.valorEstimadoProximoConcurso || 0),
      next_prize: Number(raw.valorAcumuladoProximoConcurso || 0),
      location: text(raw.localSorteio), winners_by_tier: awards,
      fetched_at: new Date().toISOString(), source: SOURCE,
    });
  }
  function readCache(key) {
    try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (_) { return null; }
  }
  function writeCache(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* Cache opcional */ }
  }
  async function fetchOfficial(item, contest, parentSignal) {
    const suffix = contest == null ? '' : `/${encodeURIComponent(contest)}`;
    const controller = new AbortController();
    const abortFromParent = () => controller.abort();
    if (parentSignal?.aborted) controller.abort();
    else parentSignal?.addEventListener('abort', abortFromParent, { once: true });
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(`${CAIXA}/${item.endpoint}${suffix}`, {
        method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store',
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`API pública da CAIXA respondeu HTTP ${response.status}.`);
      const raw = await response.json();
      if (!raw || !raw.numero) throw new Error('A CAIXA não retornou um concurso válido.');
      const draw = normalize(item, raw);
      if (!draw.numbers.length) throw new Error('A resposta oficial não contém dezenas.');
      if (contest != null && draw.contest !== Number(contest)) throw new Error('O identificador do concurso retornado não corresponde à consulta.');
      // A numbered historical query must never overwrite the latest slot.
      if (contest == null) writeCache(latestKey(item), draw);
      return draw;
    } catch (error) {
      if (error?.name === 'AbortError') throw new Error('A consulta à CAIXA excedeu o limite de tempo.');
      throw error;
    } finally {
      clearTimeout(timer);
      parentSignal?.removeEventListener('abort', abortFromParent);
    }
  }
  async function latest(item) {
    try { return await fetchOfficial(item); }
    catch (error) {
      const cached = validCached(item, readCache(latestKey(item)));
      if (cached) return { ...cached, source: 'cache local do navegador', warning: error.message };
      throw error;
    }
  }
  async function history(item, requestedLimit) {
    const limit = Math.max(1, Math.min(Number(requestedLimit) || 30, 300));
    const cacheKey = `lotomaster:caixa:history:${item.key}`;
    const cachedRows = readCache(cacheKey);
    const byContest = new Map((Array.isArray(cachedRows) ? cachedRows : []).filter(row=>validCached(item,row)).map(row => [Number(row.contest), row]));
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), HISTORY_BUDGET_MS);
    let newest;
    let warning = null;
    let first = 1;
    try {
      try { newest = await fetchOfficial(item, null, controller.signal); }
      catch (error) {
        newest = validCached(item, readCache(latestKey(item)));
        if (!newest) throw error;
        warning = `Não foi possível atualizar o último concurso; exibindo cache do navegador, que pode estar desatualizado: ${error.message}`;
        newest = { ...newest, source: 'cache local do navegador', warning };
      }
      byContest.set(Number(newest.contest), newest);
      first = Math.max(1, Number(newest.contest) - limit + 1);
      const missing = [];
      for (let contest = first; contest < Number(newest.contest); contest += 1) {
        if (!byContest.has(contest)) missing.push(contest);
      }
      let next = 0;
      const workers = Array.from({ length: Math.min(4, missing.length) }, async () => {
        while (next < missing.length && !controller.signal.aborted) {
          const index = next++;
          const contest = missing[index];
          try { byContest.set(contest, await fetchOfficial(item, contest, controller.signal)); } catch (_) { /* mantém resultados parciais */ }
        }
      });
      await Promise.all(workers);
    } finally {
      clearTimeout(deadline);
    }
    const retained = [...byContest.values()]
      .sort((a, b) => Number(b.contest) - Number(a.contest));
    const rows = retained
      .filter(row => Number(row.contest) >= first && Number(row.contest) <= Number(newest.contest))
      .slice(0, limit);
    writeCache(cacheKey, retained.slice(0, 300).map(({ warning: _warning, ...row }) => row));
    if (!rows.length) throw new Error('Não foi possível obter concursos históricos da CAIXA.');
    const expected = Number(newest.contest) - first + 1;
    const partial = rows.length < expected;
    return { rows, warning, partial, expected };
  }
  async function postDraws(path, draws) {
    const response = await fetch(`/api/v1/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draws }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `Não foi possível analisar os dados (HTTP ${response.status}).`);
    return payload;
  }
  async function fallback(path) {
    const match = String(path).match(/^\/([a-z0-9-]+)\/(latest|results|statistics|assistant)(?:\?(.*))?$/i);
    if (!match) return undefined;
    const item = GAMES[match[1].replaceAll('-', '')];
    if (!item) return undefined;
    const route = match[2];
    const query = new URLSearchParams(match[3] || '');
    if (route === 'latest') return latest(item);
    if (route === 'results') {
      const { rows: items, warning, partial, expected } = await history(item, query.get('limit') || 30);
      return { game: item.key, name: item.name, items, count: items.length, source: 'CAIXA via Worker e cache do navegador', warning, partial, expected_count: expected, provenance: {latest_lookup: warning?'browser_cache':'worker_fetch', recently_checked: !warning, verified: false} };
    }
    const { rows: draws, warning, partial, expected } = await history(item, query.get('limit') || 50);
    const payload = await postDraws(`${item.key}/${route === 'statistics' ? 'statistics' : 'assistant'}/from-draws`, draws);
    return { ...payload, warning, partial, expected_count: expected };
  }
  window.lotomasterCaixaFallback = fallback;
})();
