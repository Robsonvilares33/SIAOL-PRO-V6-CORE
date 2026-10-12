/* Recuperação somente leitura: consulta a API pública da CAIXA no navegador e mantém cache local. */
(() => {
  const CAIXA = 'https://servicebus2.caixa.gov.br/portaldeloterias/api';
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
  const MONTHS = {
    janeiro: 1, fevereiro: 2, marco: 3, 'março': 3, abril: 4, maio: 5, junho: 6,
    julho: 7, agosto: 8, setembro: 9, outubro: 10, novembro: 11, dezembro: 12,
  };
  const SOURCE = 'CAIXA — consulta direta pelo navegador';
  const REQUEST_TIMEOUT_MS = 20000;
  const HISTORY_BUDGET_MS = 15000;

  function integers(values) {
    return (Array.isArray(values) ? values : []).map(value => Number.parseInt(String(value).trim(), 10)).filter(Number.isFinite);
  }
  function text(value) {
    if (value == null) return null;
    const clean = String(value).replace(/[\u0000-\u001f\u007f-\u009f]/g, '').trim();
    return clean || null;
  }
  function normalize(item, raw) {
    let numbers = integers(raw.listaDezenas || raw.dezenasSorteadasOrdemSorteio);
    const ordered = integers(raw.dezenasSorteadasOrdemSorteio);
    if (item.key !== 'supersete') numbers.sort((a, b) => a - b);
    let second = integers(raw.listaDezenasSegundoSorteio);
    if (item.key === 'duplasena' && !second.length && ordered.length >= 12) second = ordered.slice(6, 12);
    let trevos = integers(raw.trevosSorteados);
    if (item.key === 'maismilionaria' && !trevos.length && ordered.length >= 8) trevos = ordered.slice(-2);
    const special = text(raw.nomeTimeCoracaoMesSorte);
    const monthNumber = item.key === 'diadesorte' && special ? (MONTHS[special.toLocaleLowerCase('pt-BR')] || null) : null;
    const awards = (raw.listaRateioPremio || []).map(row => ({
      label: text(row.descricaoFaixa) || 'Faixa',
      winners: Number(row.numeroDeGanhadores || 0),
      prize: Number(row.valorPremio || 0),
    }));
    return {
      game: item.key, name: item.name, contest: Number(raw.numero || 0),
      draw_date: text(raw.dataApuracao), next_draw_date: text(raw.dataProximoConcurso),
      numbers, ordered_numbers: ordered.length ? ordered : numbers, second_numbers: second,
      trevos,
      month: item.key === 'diadesorte' && special ? { name: special, number: monthNumber } : null,
      team: item.key === 'timemania' ? special : null,
      special_draw: ['true', '1', 's', 'sim'].includes(String(raw.indicadorConcursoEspecial || '').trim().toLowerCase()),
      contest_type: text(raw.tipoJogo), accumulated: Boolean(raw.acumulado),
      estimated_prize: Number(raw.valorEstimadoProximoConcurso || 0),
      next_prize: Number(raw.valorAcumuladoProximoConcurso || 0),
      location: text(raw.localSorteio), winners_by_tier: awards,
      fetched_at: new Date().toISOString(), source: SOURCE,
    };
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
      writeCache(`lotomaster:caixa:latest:${item.key}`, draw);
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
      const cached = readCache(`lotomaster:caixa:latest:${item.key}`);
      if (cached) return { ...cached, source: 'cache local do navegador', warning: error.message };
      throw error;
    }
  }
  async function history(item, requestedLimit) {
    const limit = Math.max(1, Math.min(Number(requestedLimit) || 30, 300));
    const cacheKey = `lotomaster:caixa:history:${item.key}`;
    const cachedRows = readCache(cacheKey);
    const byContest = new Map((Array.isArray(cachedRows) ? cachedRows : []).map(row => [Number(row.contest), row]));
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), HISTORY_BUDGET_MS);
    let newest;
    let first = 1;
    try {
      try { newest = await fetchOfficial(item, null, controller.signal); }
      catch (error) {
        newest = readCache(`lotomaster:caixa:latest:${item.key}`);
        if (!newest) throw error;
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
    const rows = [...byContest.values()]
      .filter(row => Number(row.contest) >= first && Number(row.contest) <= Number(newest.contest))
      .sort((a, b) => Number(b.contest) - Number(a.contest))
      .slice(0, limit);
    writeCache(cacheKey, rows);
    if (!rows.length) throw new Error('Não foi possível obter concursos históricos da CAIXA.');
    return rows;
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
      const items = await history(item, query.get('limit') || 30);
      return { game: item.key, name: item.name, items, count: items.length, source: SOURCE };
    }
    const draws = await history(item, query.get('limit') || 50);
    if (route === 'statistics') return postDraws(`${item.key}/statistics/from-draws`, draws);
    return postDraws(`${item.key}/assistant/from-draws`, draws);
  }
  window.lotomasterCaixaFallback = fallback;
})();
