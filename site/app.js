"use strict";

const POSICOES = { 1: "GR", 2: "DEF", 3: "MED", 4: "AV" };
const POS_NOMES = { 1: "Guarda-redes", 2: "Defesas", 3: "Médios", 4: "Avançados" };
const STATUS_FORA = new Set(["i", "s", "u", "n"]);
const MEU_GESTOR = /gentil/i; // apelido do gestor (equipa "Buendia Porro")
const ESTADOS = {
  a: { rotulo: "Disponível", sev: "" },
  d: { rotulo: "Dúvida", sev: "warn" },
  i: { rotulo: "Lesionado", sev: "bad" },
  s: { rotulo: "Suspenso", sev: "bad" },
  u: { rotulo: "Indisponível", sev: "bad" },
  n: { rotulo: "Indisponível", sev: "bad" },
};

const fmtDataHora = new Intl.DateTimeFormat("pt-PT", {
  timeZone: "Europe/Lisbon", day: "numeric", month: "short",
  hour: "2-digit", minute: "2-digit",
});

let D = null; // dados carregados
let entradasPorId = {}; // league_entry id -> entry (standings)
let entradasPorEntryId = {}; // entry_id -> entry (owner no element-status)
let jogadoresPorId = {}; // element id -> jogador

function $(id) { return document.getElementById(id); }

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function nomeClube(teamId) {
  const t = D.teams[String(teamId)];
  return t ? t.short_name : "?";
}

function nomeDono(owner) {
  if (owner == null) return null;
  const e = entradasPorEntryId[owner];
  return e ? e.entry_name : "?";
}

function estadoDe(p) {
  const e = ESTADOS[p.status] || { rotulo: p.status, sev: "" };
  if (p.status === "d" && p.chance_of_playing_next_round != null) {
    return { rotulo: "Dúvida " + p.chance_of_playing_next_round + "%", sev: "warn" };
  }
  return e;
}

/* ---------- Cabeçalho ---------- */

function initCabecalho() {
  document.title = D.league.name + " · FPL Draft";
  $("titulo-liga").textContent = D.league.name;
  $("atualizado").textContent =
    "Atualizado: " + fmtDataHora.format(new Date(D.generated_at));

  if (!D.next_event) return;
  const alvo = new Date(D.next_event.deadline_time);
  const el = $("countdown");
  el.hidden = false;

  function tique() {
    const resta = alvo - Date.now();
    if (resta <= 0) {
      el.textContent = "Deadline da " + D.next_event.name + " já passou";
      el.classList.remove("urgente");
      return;
    }
    const s = Math.floor(resta / 1000);
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    const seg = s % 60;
    const partes = d > 0
      ? d + "d " + h + "h " + m + "m"
      : h + "h " + m + "m " + String(seg).padStart(2, "0") + "s";
    el.textContent = D.next_event.name + ": " + fmtDataHora.format(alvo) + " · falta " + partes;
    el.classList.toggle("urgente", resta < 3 * 3600 * 1000);
    setTimeout(tique, 1000);
  }
  tique();
}

/* ---------- Notícias (ticker + boletim) ---------- */

function comNoticias() {
  return D.players
    .filter((p) => p.news && p.news.trim() !== "")
    .sort((a, b) => (b.news_added || "").localeCompare(a.news_added || ""));
}

function initTicker(noticias) {
  if (noticias.length === 0) return;
  const track = $("ticker-track");
  const itens = noticias.slice(0, 20).map((p) =>
    '<span class="ticker-item"><span class="nome">' + esc(p.web_name) + "</span> " +
    '<span class="clube">(' + nomeClube(p.team) + ")</span> — " + esc(p.news) + "</span>"
  ).join("");
  const reduzido = matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Com animação, duplica o conteúdo para o desfile ser contínuo.
  track.innerHTML = reduzido ? itens : itens + itens;
  $("ticker").hidden = false;
}

function initBoletim(noticias) {
  if (noticias.length === 0) { $("nota-boletim").hidden = false; return; }
  const ul = $("lista-boletim");
  ul.innerHTML = noticias.map((p) => {
    const est = estadoDe(p);
    const dono = nomeDono(p.owner);
    const data = p.news_added ? fmtDataHora.format(new Date(p.news_added)) : "";
    return '<li class="' + est.sev + '">' +
      '<div class="linha1">' +
        '<span class="nome">' + esc(p.web_name) + "</span>" +
        '<span class="clube">' + nomeClube(p.team) + " · " + (POSICOES[p.element_type] || "?") + "</span>" +
        '<span class="estado ' + est.sev + '">' + esc(est.rotulo) + "</span>" +
        '<span class="data">' + data + "</span>" +
      "</div>" +
      '<p class="news">' + esc(p.news) + "</p>" +
      '<p class="dono">' + (dono ? "Dono: <strong>" + esc(dono) + "</strong>" : "Livre") + "</p>" +
    "</li>";
  }).join("");
}

/* ---------- A minha equipa ---------- */

function porDraftRank(a, b) {
  return (a.draft_rank ?? 1e9) - (b.draft_rank ?? 1e9);
}

function grupoPosHTML(pos, jogadores, realcarNovos) {
  if (jogadores.length === 0) return "";
  const linhas = jogadores.map((p) => {
    const est = estadoDe(p);
    const novo = realcarNovos && p.news_new && p.news;
    const marca = est.sev ? ' <span class="estado ' + est.sev + '">' + esc(est.rotulo) + "</span>" : "";
    const news = realcarNovos && p.news ? '<span class="news-mini">' + esc(p.news) + "</span>" : "";
    return '<li class="' + (novo ? "novo-boletim" : "") + '">' +
      '<div class="linha">' +
        '<span class="nome">' + esc(p.web_name) + "</span>" +
        '<span class="clube">' + nomeClube(p.team) + "</span>" + marca +
        (novo ? ' <span class="estado bad">Novo no boletim</span>' : "") +
        '<span class="pts">' + p.total_points + "</span>" +
      "</div>" + news +
    "</li>";
  }).join("");
  return '<section class="grupo-pos"><h3>' + POS_NOMES[pos] + " (" + jogadores.length + ")</h3>" +
    '<ul class="lista-jog">' + linhas + "</ul></section>";
}

function initMinhaEquipa() {
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager)) ||
    D.entries.find((e) => e.entry_name === "Buendia Porro");
  if (!eu) {
    $("equipa-nome").textContent = "A minha equipa";
    $("equipa-alerta").textContent = "Não encontrei a equipa nos dados da liga.";
    $("equipa-alerta").hidden = false;
    return;
  }
  $("equipa-nome").textContent = eu.entry_name + " · " + eu.manager;

  const meus = D.players.filter((p) => p.owner === eu.entry_id);
  const novos = meus.filter((p) => p.news_new && p.news);
  if (novos.length > 0) {
    $("equipa-alerta").textContent = "⚠ " + novos.length +
      (novos.length === 1 ? " jogador teu entrou" : " jogadores teus entraram") +
      " no boletim desde a última atualização.";
    $("equipa-alerta").hidden = false;
    $("equipa-alerta").classList.add("alerta");
  }
  $("plantel").innerHTML = [1, 2, 3, 4].map((pos) =>
    grupoPosHTML(pos, meus.filter((p) => p.element_type === pos).sort(porDraftRank), true)
  ).join("");

  const livres = D.players.filter((p) => p.owner == null && !STATUS_FORA.has(p.status));
  $("alvos").innerHTML = [1, 2, 3, 4].map((pos) =>
    grupoPosHTML(pos, livres.filter((p) => p.element_type === pos).sort(porDraftRank).slice(0, 10), false)
  ).join("");
}

/* ---------- Equipas (cartão por gestor) ---------- */

function initEquipas() {
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  const rankPor = Object.fromEntries(D.standings.map((s) => [s.league_entry, s.rank]));
  const ordenadas = D.entries.slice().sort((a, b) =>
    (rankPor[a.id] ?? a.waiver_pick ?? 99) - (rankPor[b.id] ?? b.waiver_pick ?? 99));

  $("cartoes-equipas").innerHTML = ordenadas.map((e) => {
    const plantel = D.players.filter((p) => p.owner === e.entry_id);
    const fora = plantel.filter((p) => STATUS_FORA.has(p.status)).length;
    const duvidas = plantel.filter((p) => p.status === "d").length;
    const sou = eu && e.id === eu.id;
    const badges =
      (fora ? '<span class="estado bad">' + fora + " fora</span>" : "") +
      (duvidas ? '<span class="estado warn">' + duvidas + (duvidas === 1 ? " dúvida" : " dúvidas") + "</span>" : "") +
      (!fora && !duvidas ? '<span class="estado ok">plantel completo</span>' : "");
    const corpo = [1, 2, 3, 4].map((pos) =>
      grupoPosHTML(pos, plantel.filter((p) => p.element_type === pos).sort(porDraftRank), true)
    ).join("");
    return '<details class="cartao"' + (sou ? " open" : "") + ">" +
      "<summary>" +
        '<span class="nome">' + esc(e.entry_name) + (sou ? " ★" : "") + "</span>" +
        '<span class="clube">' + esc(e.manager) + " · waiver #" + (e.waiver_pick ?? "?") + "</span>" +
        '<span class="badges">' + badges + "</span>" +
      "</summary>" +
      '<div class="corpo">' + (corpo || '<p class="nota">Sem plantel.</p>') + "</div>" +
    "</details>";
  }).join("");
}

/* ---------- Liga ---------- */

function initLiga() {
  const corpo = $("tabela-liga").querySelector("tbody");
  const linhas = D.standings
    .slice()
    .sort((a, b) => ((a.rank_sort ?? a.rank) ?? 99) - ((b.rank_sort ?? b.rank) ?? 99));
  const semRanks = linhas.every((s) => s.rank == null);
  $("nota-liga").hidden = !semRanks;

  corpo.innerHTML = linhas.map((s) => {
    const e = entradasPorId[s.league_entry] || {};
    return "<tr>" +
      '<td class="num">' + (s.rank ?? "–") + "</td>" +
      "<td>" + esc(e.entry_name || "?") + '<span class="sub">' + esc(e.manager || "") + "</span></td>" +
      '<td class="num">' + (s.event_total ?? "–") + "</td>" +
      '<td class="num">' + (s.total ?? 0) + "</td>" +
    "</tr>";
  }).join("");
}

/* ---------- Jogadores ---------- */

const PASSO = 100;
let filtrados = [];
let visiveis = PASSO;

function aplicarFiltros() {
  const termo = $("pesquisa").value.trim().toLowerCase();
  const pos = $("filtro-pos").value;
  const soLivres = $("so-livres").checked;

  filtrados = D.players.filter((p) => {
    if (pos && String(p.element_type) !== pos) return false;
    if (soLivres && p.owner != null) return false;
    if (termo) {
      const clube = D.teams[String(p.team)];
      const alvo = (p.web_name + " " + p.first_name + " " + p.second_name + " " +
        (clube ? clube.name + " " + clube.short_name : "")).toLowerCase();
      if (!alvo.includes(termo)) return false;
    }
    return true;
  });

  const ordem = $("ordenar").value;
  if (ordem === "proj") {
    filtrados.sort((a, b) => projecao(b).ppj - projecao(a).ppj);
  } else if (ordem === "pontos") {
    filtrados.sort((a, b) => b.total_points - a.total_points);
  } else {
    filtrados.sort((a, b) => (a.draft_rank ?? 1e9) - (b.draft_rank ?? 1e9));
  }

  visiveis = PASSO;
  desenharJogadores();
}

function desenharJogadores() {
  const corpo = $("tabela-jogadores").querySelector("tbody");
  const mostrar = filtrados.slice(0, visiveis);
  corpo.innerHTML = mostrar.map((p) => {
    const est = estadoDe(p);
    const dono = nomeDono(p.owner);
    const marca = est.sev
      ? ' <span class="estado ' + est.sev + '">' + esc(est.rotulo) + "</span>"
      : "";
    const tr = (D.transferencias || {})[p.id];
    const dinheiro = tr && tr.confirmada
      ? ' <span class="estado ok">' + esc(tr.moeda) + tr.valor + "M</span>" : "";
    return "<tr>" +
      "<td>" + esc(p.web_name) + marca + dinheiro +
        '<span class="sub">' + nomeClube(p.team) + " · #" + (p.draft_rank ?? "–") + "</span></td>" +
      "<td>" + (POSICOES[p.element_type] || "?") + "</td>" +
      '<td class="num">' + p.total_points + "</td>" +
      '<td class="num forte">' + projecao(p).ppj.toFixed(1) + "</td>" +
      "<td>" + (dono ? esc(dono) : '<span class="sub">Livre</span>') + "</td>" +
    "</tr>";
  }).join("");
  $("contagem-jogadores").textContent =
    filtrados.length + " jogador" + (filtrados.length === 1 ? "" : "es") +
    (mostrar.length < filtrados.length ? " (a mostrar " + mostrar.length + ")" : "");
  $("mostrar-mais").hidden = mostrar.length >= filtrados.length;
}

function initJogadores() {
  $("pesquisa").addEventListener("input", aplicarFiltros);
  $("filtro-pos").addEventListener("change", aplicarFiltros);
  $("so-livres").addEventListener("change", aplicarFiltros);
  $("ordenar").addEventListener("change", aplicarFiltros);
  $("filtros").addEventListener("submit", (ev) => ev.preventDefault());
  $("mostrar-mais").addEventListener("click", () => {
    visiveis += PASSO;
    desenharJogadores();
  });
  aplicarFiltros();
}

/* ---------- Projeção de pontos ---------- */

const MIN_PRIOR = 900;    // minutos de "prior" no encolhimento do pts/90
const JOGOS_EPOCA = 38;
const K_VIZINHOS = 15;    // jogadores de draft rank parecido usados como prior

let priorsPos = {};       // element_type -> [{rank, pp90, minJogo}] ordenado por rank

function mediana(v) {
  if (v.length === 0) return 0;
  const s = v.slice().sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** Época anterior congelada na recolha (o bootstrap passa a ser desta época). */
function historicoDe(p) {
  const h = (D.historico || {})[p.id];
  return h || { minutes: p.minutes, starts: p.starts, total_points: p.total_points };
}

/** Jornadas já disputadas pela equipa do jogador, da mais antiga para a mais recente. */
function utilizacao(p) {
  const js = D.jornadas || {};
  return Object.keys(js)
    .map(Number)
    .sort((a, b) => a - b)
    .filter((ev) => {
      const eq = js[ev].equipas || [];
      return eq.length === 0 || eq.includes(p.team);
    })
    .map((ev) => {
      const s = js[ev].stats[String(p.id)] || [0, 0];
      return { event: ev, minutos: s[0], pontos: s[1], finalizada: !!js[ev].finalizada };
    });
}

function construirPriors() {
  priorsPos = {};
  [1, 2, 3, 4].forEach((pos) => {
    priorsPos[pos] = D.players
      .filter((p) => p.element_type === pos && historicoDe(p).minutes >= MIN_PRIOR)
      .map((p) => {
        const h = historicoDe(p);
        return {
          rank: p.draft_rank ?? 1e9,
          pp90: (h.total_points / h.minutes) * 90,
          minJogo: Math.min(90, h.minutes / JOGOS_EPOCA),
        };
      })
      .sort((a, b) => a.rank - b.rank);
  });
}

/** Referência de quem tem draft rank parecido na mesma posição. */
function priorDe(p) {
  const lista = priorsPos[p.element_type] || [];
  if (lista.length === 0) return { pp90: 3, minJogo: 45 };
  const rank = p.draft_rank ?? 1e9;
  let i = lista.findIndex((x) => x.rank >= rank);
  if (i < 0) i = lista.length - 1;
  const ini = Math.max(0, Math.min(i - Math.floor(K_VIZINHOS / 2), lista.length - K_VIZINHOS));
  const viz = lista.slice(ini, ini + K_VIZINHOS);
  return { pp90: mediana(viz.map((v) => v.pp90)), minJogo: mediana(viz.map((v) => v.minJogo)) };
}

/** Como o jogador apareceu no último ensaio de pré-época do clube. */
function preEpocaDe(p) {
  const e = (D.preepoca || {})[String(p.team)];
  if (!e) return null;
  const estado = e.titulares.includes(p.id) ? "titular"
    : e.suplentes.includes(p.id) ? "suplente"
    // Sem lista de suplentes publicada só se pode dizer que não foi titular.
    : (e.suplentes.length ? "fora" : "nao_titular");
  return { estado, jogo: e.jogo, data: e.data, fonte: e.fonte, confianca: e.confianca };
}

/** Uma transferência cara confirmada é sinal de titularidade. */
function pisoTransferencia(valor) {
  if (valor >= 50) return 75;
  if (valor >= 30) return 68;
  if (valor >= 15) return 58;
  return 50;
}

function fatorDificuldade(d) {
  return 1 + (3 - d) * 0.06; // adversário fácil (1) 1.12 … difícil (5) 0.88
}

function projecao(p) {
  const prior = priorDe(p);
  const hist = historicoDe(p);
  // Encolhimento: poucos minutos ⇒ o valor aproxima-se do prior da posição/rank.
  const pp90Hist =
    ((hist.total_points + (prior.pp90 * MIN_PRIOR) / 90) / (hist.minutes + MIN_PRIOR)) * 90;
  let xminHist = hist.minutes > 0 ? Math.min(90, hist.minutes / JOGOS_EPOCA) : prior.minJogo;

  // Jogos já disputados nesta época: a realidade manda mais do que o histórico.
  const uso = utilizacao(p).filter((u) => u.finalizada);
  const jogosObs = uso.length;
  const peso = Math.min(1, jogosObs / 5); // 5 jogos ⇒ decide sozinho
  const ultimos = uso.slice(-3);

  let pp90 = pp90Hist;
  let xmin = xminHist;
  if (jogosObs > 0) {
    const minEpoca = uso.reduce((s, u) => s + u.minutos, 0);
    const ptsEpoca = uso.reduce((s, u) => s + u.pontos, 0);
    pp90 = ((ptsEpoca + (pp90Hist * MIN_PRIOR) / 90) / (minEpoca + MIN_PRIOR)) * 90;
    const mediaRecente = ultimos.reduce((s, u) => s + u.minutos, 0) / ultimos.length;
    xmin = peso * mediaRecente + (1 - peso) * xminHist;
  }

  const tr = (D.transferencias || {})[p.id];
  let bump = null;
  // O piso da transferência é uma suposição: assim que houver jogos, vale o que se viu.
  if (tr && tr.confirmada && jogosObs < 3 && !STATUS_FORA.has(p.status)) {
    const piso = pisoTransferencia(tr.valor);
    if (piso > xmin) { bump = Math.round(piso - xmin); xmin = piso; }
  }

  // Antes da primeira jornada, o último ensaio de pré-época é o melhor indício
  // de quem o treinador vai lançar. Deixa de contar assim que houver jogos a sério.
  const pe = jogosObs === 0 ? preEpocaDe(p) : null;
  if (pe && !STATUS_FORA.has(p.status)) {
    const forca = pe.confianca === "alta" ? 1 : 0.5;
    if (pe.estado === "titular") {
      const alvo = 72;
      if (alvo > xmin) xmin += (alvo - xmin) * forca;
    } else if (pe.estado === "suplente" || pe.estado === "fora") {
      xmin -= (xmin - 30) * 0.5 * forca;
    } else if (!(tr && tr.confirmada)) {
      // Não foi titular (pode ter entrado do banco): penalização suave.
      // Quem mudou de clube não é julgado pelo onze do clube antigo.
      xmin *= 1 - 0.15 * forca;
    }
  }
  if (STATUS_FORA.has(p.status)) {
    xmin = 0;
  } else if (p.status === "d" && p.chance_of_playing_next_round != null) {
    xmin *= p.chance_of_playing_next_round / 100;
  }
  xmin = Math.max(0, Math.min(90, xmin));

  const ppj = (pp90 * xmin) / 90;
  const jogos = ((D.fixtures || {})[String(p.team)] || []).slice(0, 3);
  const prox3 = jogos.reduce((s, j) => s + ppj * fatorDificuldade(j.difficulty), 0);
  const naoUsado = jogosObs >= 2 && ultimos.every((u) => u.minutos === 0) &&
    !STATUS_FORA.has(p.status);
  return { pp90, xmin, ppj, prox3, jogos, tr, bump, ultimos, jogosObs, naoUsado, pe };
}

function linhaProjecao(p, pr) {
  const est = estadoDe(p);
  const badges =
    (pr.tr ? '<span class="estado ' + (pr.tr.confirmada ? "ok" : "warn") + '">' +
      esc(pr.tr.moeda) + pr.tr.valor + "M" + (pr.tr.confirmada ? "" : "?") +
      (pr.bump ? " +" + pr.bump + "min" : "") + "</span>" : "") +
    (est.sev ? ' <span class="estado ' + est.sev + '">' + esc(est.rotulo) + "</span>" : "");
  const jogos = pr.jogos.map((j) =>
    '<span class="fx d' + j.difficulty + '">' +
      (D.teams[String(j.opponent)] || {}).short_name +
      (j.is_home ? "" : " (F)") + "</span>").join(" ");
  const recentes = minutosRecentes(pr);
  const pe = pr.pe && pr.pe.estado === "titular"
    ? ' <span class="estado ok">XI pré-época</span>'
    : pr.pe && pr.pe.estado !== "nao_titular"
      ? ' <span class="estado warn">banco pré-época</span>' : "";
  return "<tr>" +
    "<td>" + esc(p.web_name) + badges + pe +
      (pr.naoUsado ? ' <span class="estado bad">sem jogar</span>' : "") +
      '<span class="sub">' + nomeClube(p.team) + " · " + (POSICOES[p.element_type] || "?") +
      (recentes ? " · jogou " + recentes : "") +
      (jogos ? " · " + jogos : "") + "</span></td>" +
    '<td class="num">' + pr.pp90.toFixed(1) + "</td>" +
    '<td class="num">' + Math.round(pr.xmin) + "</td>" +
    '<td class="num forte">' + pr.ppj.toFixed(1) + "</td>" +
    '<td class="num">' + pr.prox3.toFixed(1) + "</td>" +
  "</tr>";
}

function tabelaProjecao(linhas) {
  return '<table class="tabela tabela-proj">' +
    "<thead><tr><th>Jogador</th><th class=\"num\">Pts/90</th><th class=\"num\">Min</th>" +
    "<th class=\"num\">Pts/J</th><th class=\"num\">Próx. 3</th></tr></thead>" +
    "<tbody>" + linhas + "</tbody></table>";
}

function desenharLivres() {
  const pos = $("proj-pos").value;
  const livres = D.players
    .filter((p) => p.owner == null && !STATUS_FORA.has(p.status))
    .filter((p) => !pos || String(p.element_type) === pos)
    .map((p) => ({ p, pr: projecao(p) }))
    .sort((a, b) => b.pr.ppj - a.pr.ppj)
    .slice(0, 20);
  $("proj-livres").innerHTML = tabelaProjecao(
    livres.map(({ p, pr }) => linhaProjecao(p, pr)).join(""));
}

function initProjecoes() {
  construirPriors();
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  const meus = (eu ? D.players.filter((p) => p.owner === eu.entry_id) : [])
    .map((p) => ({ p, pr: projecao(p) }))
    .sort((a, b) => b.pr.ppj - a.pr.ppj);

  const total = meus.reduce((s, x) => s + x.pr.ppj, 0);
  $("proj-total").textContent = meus.length
    ? "≈ " + total.toFixed(0) + " pts/jornada (plantel todo)" : "";
  $("proj-plantel").innerHTML = tabelaProjecao(
    meus.map(({ p, pr }) => linhaProjecao(p, pr)).join(""));

  $("proj-pos").addEventListener("change", desenharLivres);
  $("filtros-proj").addEventListener("submit", (ev) => ev.preventDefault());
  desenharLivres();
}

/* ---------- Sugestões da jornada ---------- */

// Formações válidas no FPL: 1 GR, 3-5 DEF, 2-5 MED, 1-3 AV (11 titulares).
const LIMITES_XI = { 1: [1, 1], 2: [3, 5], 3: [2, 5], 4: [1, 3] };
const GANHO_MIN_LIVRE = 0.4;  // pts/jornada abaixo disto não vale o waiver
const GANHO_MIN_TROCA = 0.25; // ambos os lados têm de ganhar pelo menos isto

/** Melhor onze possível de um plantel, por projeção. */
function melhorXI(plantel) {
  const porPos = { 1: [], 2: [], 3: [], 4: [] };
  plantel.forEach((x) => porPos[x.p.element_type].push(x));
  [1, 2, 3, 4].forEach((pos) => porPos[pos].sort((a, b) => b.pr.ppj - a.pr.ppj));

  const xi = [];
  const usados = {};
  [1, 2, 3, 4].forEach((pos) => {
    const min = LIMITES_XI[pos][0];
    xi.push(...porPos[pos].slice(0, min));
    usados[pos] = Math.min(min, porPos[pos].length);
  });
  // Preencher as vagas restantes com os melhores que ainda cabem por posição.
  const resto = [];
  [1, 2, 3, 4].forEach((pos) => resto.push(...porPos[pos].slice(usados[pos])));
  resto.sort((a, b) => b.pr.ppj - a.pr.ppj);
  for (const x of resto) {
    if (xi.length >= 11) break;
    const pos = x.p.element_type;
    if (usados[pos] < LIMITES_XI[pos][1]) { xi.push(x); usados[pos] += 1; }
  }
  return xi;
}

function valorXI(plantel) {
  return melhorXI(plantel).reduce((s, x) => s + x.pr.ppj, 0);
}

function comProjecao(jogadores) {
  return jogadores.map((p) => ({ p, pr: projecao(p) }));
}

/** Projeção ignorando o estado clínico — para não trocar um titular por 2 semanas de lesão. */
function ppjSaudavel(p) {
  if (!STATUS_FORA.has(p.status) && p.status !== "d") return projecao(p).ppj;
  const copia = Object.assign({}, p, { status: "a", chance_of_playing_next_round: null });
  return projecao(copia).ppj;
}

function sugestoesLivres(meusX) {
  const livresX = comProjecao(D.players.filter((p) => p.owner == null && !STATUS_FORA.has(p.status)));
  const pares = [];
  meusX.forEach((meu) => {
    livresX
      .filter((l) => l.p.element_type === meu.p.element_type)
      .forEach((livre) => {
        const ganho = livre.pr.ppj - meu.pr.ppj;
        if (ganho >= GANHO_MIN_LIVRE) {
          pares.push({ meu, livre, ganho, ganho3: livre.pr.prox3 - meu.pr.prox3 });
        }
      });
  });
  pares.sort((a, b) => b.ganho - a.ganho);

  // Guloso: cada jogador meu sai uma vez, cada livre entra uma vez.
  const saiu = new Set();
  const entrou = new Set();
  const escolhidas = [];
  for (const par of pares) {
    if (saiu.has(par.meu.p.id) || entrou.has(par.livre.p.id)) continue;
    saiu.add(par.meu.p.id);
    entrou.add(par.livre.p.id);
    escolhidas.push(par);
    if (escolhidas.length >= 5) break;
  }
  return escolhidas;
}

function sugestoesTrocas(meusX, euEntry) {
  const meuValor = valorXI(meusX);
  const propostas = [];

  D.entries.filter((e) => e.id !== euEntry.id).forEach((outro) => {
    const delesX = comProjecao(D.players.filter((p) => p.owner === outro.entry_id));
    if (delesX.length === 0) return;
    const delesValor = valorXI(delesX);

    meusX.forEach((meu) => {
      delesX.forEach((deles) => {
        // O plantel tem de continuar com 2 GR, 5 DEF, 5 MED e 3 AV: numa troca
        // 1-por-1 os jogadores têm de ser da mesma posição.
        if (deles.p.element_type !== meu.p.element_type) return;
        const meuNovo = meusX.filter((x) => x.p.id !== meu.p.id).concat([deles]);
        const delesNovo = delesX.filter((x) => x.p.id !== deles.p.id).concat([meu]);
        const ganhoMeu = valorXI(meuNovo) - meuValor;
        if (ganhoMeu < GANHO_MIN_TROCA) return;
        const ganhoDeles = valorXI(delesNovo) - delesValor;
        if (ganhoDeles >= GANHO_MIN_TROCA) {
          // Ambos melhoram o onze: acontece quando as posições fortes diferem.
          propostas.push({ outro, meu, deles, ganhoMeu, ganhoDeles, tipo: "ambos" });
        } else if (meu.p.total_points > deles.p.total_points) {
          // Soma zero na projeção, mas ele recebe o jogador com mais cartaz
          // (pontos da época passada) — é assim que as trocas passam numa liga.
          propostas.push({ outro, meu, deles, ganhoMeu, ganhoDeles, tipo: "cartaz" });
        }
      });
    });
  });

  // Win-win primeiro; dentro de cada tipo, o que me dá mais.
  propostas.sort((a, b) => b.ganhoMeu - a.ganhoMeu);
  propostas.sort((a, b) => (a.tipo === "ambos" ? 0 : 1) - (b.tipo === "ambos" ? 0 : 1));
  const usados = new Set();
  const escolhidas = [];
  for (const pr of propostas) {
    const chave = pr.meu.p.id + "-" + pr.deles.p.id;
    if (usados.has(pr.meu.p.id) || usados.has(pr.deles.p.id) || usados.has(chave)) continue;
    usados.add(pr.meu.p.id);
    usados.add(pr.deles.p.id);
    escolhidas.push(pr);
    if (escolhidas.length >= 5) break;
  }
  return escolhidas;
}

/* --- Onze inicial --- */

function chipJogador(x) {
  const est = estadoDe(x.p);
  return '<span class="chip">' +
    '<span class="chip-nome">' + esc(x.p.web_name) + "</span>" +
    '<span class="chip-info">' + nomeClube(x.p.team) + " · " + x.pr.ppj.toFixed(1) + "</span>" +
    (est.sev ? '<span class="estado ' + est.sev + '">!</span>' : "") +
  "</span>";
}

function desenharOnze(meusX) {
  const xi = melhorXI(meusX);
  const porPos = { 1: [], 2: [], 3: [], 4: [] };
  xi.forEach((x) => porPos[x.p.element_type].push(x));
  [1, 2, 3, 4].forEach((pos) => porPos[pos].sort((a, b) => b.pr.ppj - a.pr.ppj));

  const total = xi.reduce((s, x) => s + x.pr.ppj, 0);
  $("xi-resumo").textContent = porPos[2].length + "-" + porPos[3].length + "-" +
    porPos[4].length + " · ≈ " + total.toFixed(1) + " pts nesta jornada";
  $("xi-campo").innerHTML = [1, 2, 3, 4]
    .map((pos) => '<div class="linha-campo">' + porPos[pos].map(chipJogador).join("") + "</div>")
    .join("");

  const banco = meusX.filter((x) => !xi.includes(x)).sort((a, b) => b.pr.ppj - a.pr.ppj);
  $("xi-banco").innerHTML = "<strong>Suplentes:</strong> " + banco.map((x) =>
    esc(x.p.web_name) + " (" + (POSICOES[x.p.element_type] || "?") + " · " +
    x.pr.ppj.toFixed(1) + ")").join(" · ");
}

/* --- Justificações em linguagem corrente --- */

function calendario(pr) {
  if (pr.jogos.length === 0) return null;
  const media = pr.jogos.reduce((s, j) => s + j.difficulty, 0) / pr.jogos.length;
  const adv = pr.jogos.map((j) => (D.teams[String(j.opponent)] || {}).short_name).join(", ");
  if (media <= 2.4) return "calendário fácil (" + adv + ")";
  if (media >= 3.6) return "calendário difícil (" + adv + ")";
  return "calendário equilibrado (" + adv + ")";
}

function minutosRecentes(pr) {
  if (!pr.ultimos || pr.ultimos.length === 0) return null;
  return pr.ultimos.map((u) => u.minutos + "'").join(", ");
}

function porqueSai(x) {
  const est = estadoDe(x.p);
  if (STATUS_FORA.has(x.p.status)) {
    return "está " + est.rotulo.toLowerCase() + " e não pontua";
  }
  if (x.pr.naoUsado) {
    return "não saiu do banco nos últimos " + x.pr.ultimos.length + " jogos";
  }
  if (x.p.status === "d") {
    return est.rotulo.toLowerCase() + ", o que corta os minutos esperados para " +
      Math.round(x.pr.xmin);
  }
  const recentes = minutosRecentes(x.pr);
  if (recentes && x.pr.xmin < 60) {
    return "tem jogado pouco (" + recentes + " nos últimos jogos)";
  }
  if (x.pr.pe && x.pr.pe.estado !== "titular") {
    return PE_TEXTO[x.pr.pe.estado];
  }
  if (x.pr.xmin < 55) {
    return "só deve jogar cerca de " + Math.round(x.pr.xmin) + " min por jornada";
  }
  return "rende " + x.pr.pp90.toFixed(1) + " pts por 90 min, abaixo da alternativa";
}

const PE_TEXTO = {
  titular: "foi titular no último ensaio de pré-época",
  suplente: "começou no banco no último ensaio de pré-época",
  fora: "nem foi convocado para o último ensaio de pré-época",
  nao_titular: "não foi titular no último ensaio de pré-época",
};

function porqueEntra(x) {
  const partes = [];
  const recentes = minutosRecentes(x.pr);
  if (recentes) {
    partes.push("já jogou " + recentes + " nas últimas jornadas");
  } else if (x.pr.pe && x.pr.pe.estado === "titular") {
    partes.push(PE_TEXTO.titular);
  } else if (x.pr.tr && x.pr.tr.confirmada) {
    partes.push("custou " + x.pr.tr.moeda + x.pr.tr.valor + "M, por isso deve ser titular");
  } else if (x.pr.xmin >= 70) {
    partes.push("é titular certo (~" + Math.round(x.pr.xmin) + " min por jogo)");
  } else {
    partes.push("deve jogar cerca de " + Math.round(x.pr.xmin) + " min por jogo");
  }
  partes.push("vale " + x.pr.pp90.toFixed(1) + " pts por 90 min");
  const cal = calendario(x.pr);
  if (cal) partes.push(cal);
  return partes.join(", ");
}

/* --- Utilização real nas jornadas já disputadas --- */

function desenharPreEpoca(meusX) {
  if (Object.keys(D.preepoca || {}).length === 0) { $("nota-pe").hidden = false; return; }
  const ordem = { titular: 0, suplente: 1, fora: 2, nao_titular: 2 };
  const linhas = meusX
    .map((x) => ({ x, pe: preEpocaDe(x.p) }))
    .sort((a, b) => (ordem[(a.pe || {}).estado] ?? 3) - (ordem[(b.pe || {}).estado] ?? 3));

  const titulares = linhas.filter((l) => l.pe && l.pe.estado === "titular").length;
  $("pe-resumo").textContent = titulares + " dos teus 15 foram titulares";

  $("pe-plantel").innerHTML = '<table class="tabela tabela-proj"><thead><tr>' +
    "<th>Jogador</th><th>No último ensaio</th><th>Jogo</th></tr></thead><tbody>" +
    linhas.map(({ x, pe }) => {
      if (!pe) {
        return "<tr><td>" + esc(x.p.web_name) +
          '<span class="sub">' + nomeClube(x.p.team) + "</span></td>" +
          '<td colspan="2" class="sub">sem onze publicado para este clube</td></tr>';
      }
      const cor = pe.estado === "titular" ? "ok" : pe.estado === "suplente" ? "warn" : "bad";
      const rotulo = { titular: "Titular", suplente: "Suplente",
                       fora: "Não convocado", nao_titular: "Não foi titular" }[pe.estado];
      return "<tr><td>" + esc(x.p.web_name) +
        '<span class="sub">' + nomeClube(x.p.team) + " · " +
          (POSICOES[x.p.element_type] || "?") + "</span></td>" +
        '<td><span class="estado ' + cor + '">' + rotulo + "</span>" +
          (pe.confianca !== "alta" ? ' <span class="sub">indício fraco</span>' : "") + "</td>" +
        '<td><a href="' + esc(pe.fonte) + '" target="_blank" rel="noopener">' +
          esc(pe.jogo) + "</a></td></tr>";
    }).join("") + "</tbody></table>";
}

function desenharUtilizacao(meusX) {
  const jornadas = Object.keys(D.jornadas || {});
  if (jornadas.length === 0) { $("nota-uso").hidden = false; return; }

  const linhas = meusX
    .map((x) => ({ x, uso: utilizacao(x.p) }))
    .filter((l) => l.uso.length > 0)
    .sort((a, b) => {
      const pa = a.uso.reduce((s, u) => s + u.pontos, 0);
      const pb = b.uso.reduce((s, u) => s + u.pontos, 0);
      return pb - pa;
    });
  if (linhas.length === 0) { $("nota-uso").hidden = false; return; }

  const totalPts = linhas.reduce((s, l) => s + l.uso.reduce((t, u) => t + u.pontos, 0), 0);
  $("uso-resumo").textContent = linhas[0].uso.length + " jornada" +
    (linhas[0].uso.length === 1 ? "" : "s") + " · " + totalPts + " pts do plantel";

  $("uso-plantel").innerHTML = '<table class="tabela tabela-proj"><thead><tr>' +
    '<th>Jogador</th><th>Jornadas (minutos · pontos)</th><th class="num">Pts</th>' +
    "</tr></thead><tbody>" +
    linhas.map(({ x, uso }) => {
      const pts = uso.reduce((s, u) => s + u.pontos, 0);
      const chips = uso.slice(-5).map((u) => {
        const nivel = u.minutos === 0 ? "d5" : u.minutos < 45 ? "d3" : "d1";
        return '<span class="fx ' + nivel + '">GW' + u.event + " " + u.minutos + "' · " +
          u.pontos + "</span>";
      }).join(" ");
      return "<tr><td>" + esc(x.p.web_name) +
        '<span class="sub">' + nomeClube(x.p.team) + " · " +
          (POSICOES[x.p.element_type] || "?") + "</span></td>" +
        "<td>" + chips + "</td>" +
        '<td class="num forte">' + pts + "</td></tr>";
    }).join("") + "</tbody></table>";
}

function etiquetaJogador(x) {
  const est = estadoDe(x.p);
  return esc(x.p.web_name) +
    ' <span class="clube">' + nomeClube(x.p.team) + " · " + (POSICOES[x.p.element_type] || "?") +
    " · " + x.pr.ppj.toFixed(1) + " pts/J</span>" +
    (est.sev ? ' <span class="estado ' + est.sev + '">' + esc(est.rotulo) + "</span>" : "");
}

function initSugestoes() {
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  if (!eu) { $("sug-contexto").textContent = "Não encontrei a tua equipa na liga."; return; }
  const meusX = comProjecao(D.players.filter((p) => p.owner === eu.entry_id));
  desenharOnze(meusX);
  desenharPreEpoca(meusX);
  desenharUtilizacao(meusX);

  // --- Contexto da liga ---
  const ev = D.next_event ? D.next_event.name : "próxima jornada";
  $("sug-titulo").textContent = "Sugestões para a " + ev;
  const minha = D.standings.find((s) => s.league_entry === eu.id);
  const partes = [];
  if (minha && minha.rank != null) {
    const lider = D.standings.reduce((a, b) => ((a.total ?? 0) >= (b.total ?? 0) ? a : b));
    const dif = (lider.total ?? 0) - (minha.total ?? 0);
    partes.push(minha.rank + "º lugar com " + (minha.total ?? 0) + " pts" +
      (dif > 0 ? " (a " + dif + " do líder)" : " — és o líder"));
  } else {
    partes.push("A liga ainda não tem classificação");
  }
  partes.push("és o #" + (eu.waiver_pick ?? "?") + " na fila de waivers");
  const movs = (D.mercado && D.mercado.transacoes ? D.mercado.transacoes : [])
    .filter((t) => t.result === "a").length;
  if (movs) partes.push(movs + " movimentos recentes na liga");
  $("sug-contexto").textContent = partes.join(" · ") + ".";

  // --- Waivers / free agency ---
  const livres = sugestoesLivres(meusX);
  if (livres.length === 0) {
    $("nota-sug-livres").hidden = false;
  } else {
    $("sug-livres").innerHTML = livres.map((s) => {
      const saudavel = ppjSaudavel(s.meu.p);
      const aviso = saudavel > s.livre.pr.ppj
        ? '<p class="aviso-sug">⚠ Recuperado, ' + esc(s.meu.p.web_name) + " projeta " +
          saudavel.toFixed(1) + " pts/J — só compensa se a ausência for longa.</p>"
        : "";
      const explicacao = "<strong>" + esc(s.meu.p.web_name) + "</strong> " + porqueSai(s.meu) +
        ". <strong>" + esc(s.livre.p.web_name) + "</strong> " + porqueEntra(s.livre) +
        ". A troca vale mais <strong>" + s.ganho.toFixed(1) +
        " pontos por jornada</strong> (" + s.ganho3.toFixed(1) + " nas próximas três).";
      return "<li>" +
        '<div class="troca-linha"><span class="sai">Sai</span> ' + etiquetaJogador(s.meu) + "</div>" +
        '<div class="troca-linha"><span class="entra">Entra</span> ' + etiquetaJogador(s.livre) + "</div>" +
        '<p class="porque">' + explicacao + "</p>" + aviso +
      "</li>";
    }).join("");
  }

  // --- Trocas ---
  const trocas = sugestoesTrocas(meusX, eu);
  if (trocas.length === 0) {
    $("nota-sug-trocas").hidden = false;
  } else {
    $("sug-trocas").innerHTML = trocas.map((t) => {
      const ganhas = "Ganhas porque <strong>" + esc(t.deles.p.web_name) + "</strong> " +
        porqueEntra(t.deles) + ", enquanto <strong>" + esc(t.meu.p.web_name) + "</strong> " +
        porqueSai(t.meu) + " — o teu onze sobe <strong>" + t.ganhoMeu.toFixed(1) +
        " pontos por jornada</strong>.";
      const aceita = t.tipo === "ambos"
        ? " Ele também tem interesse: o onze dele sobe " + t.ganhoDeles.toFixed(1) +
          " pontos, porque " + esc(t.meu.p.web_name) + " encaixa melhor no plantel dele."
        : " Ele pode aceitar porque recebe o nome maior: " + esc(t.meu.p.web_name) + " fez " +
          t.meu.p.total_points + " pontos na época passada e " + esc(t.deles.p.web_name) +
          " fez " + t.deles.p.total_points + " — é o número que salta à vista, mesmo que a " +
          "projeção para esta época diga o contrário.";
      return "<li class=\"" + t.tipo + "\">" +
        '<p class="alvo">Propor a <strong>' + esc(t.outro.entry_name) + "</strong> (" +
          esc(t.outro.manager) + ")</p>" +
        '<div class="troca-linha"><span class="sai">Dás</span> ' + etiquetaJogador(t.meu) + "</div>" +
        '<div class="troca-linha"><span class="entra">Recebes</span> ' + etiquetaJogador(t.deles) + "</div>" +
        '<p class="porque">' + ganhas + aceita + "</p>" +
      "</li>";
    }).join("");
  }
}

/* ---------- Conferências e risco de não jogar ---------- */

const NIVEIS = { 3: "bad", 2: "bad", 1: "warn" };

function riscoRotacao(p) {
  // Com jogos disputados, o que interessa são os minutos que ele teve mesmo.
  const uso = utilizacao(p).filter((u) => u.finalizada);
  if (uso.length >= 2) {
    const ult = uso.slice(-3);
    const media = ult.reduce((s, u) => s + u.minutos, 0) / ult.length;
    if (ult.every((u) => u.minutos === 0)) {
      return { nivel: 2, texto: "Não saiu do banco nos últimos " + ult.length + " jogos" };
    }
    const sufixo = " min nos últimos " + ult.length + " jogos";
    if (media < 45) return { nivel: 2, texto: "Média de " + Math.round(media) + sufixo };
    if (media < 70) return { nivel: 1, texto: "Média de " + Math.round(media) + sufixo };
    return null;
  }
  const h = historicoDe(p);
  if (h.minutes === 0) return { nivel: 2, texto: "Sem minutos na Premier League" };
  if (h.starts <= 12) {
    return { nivel: 2, texto: "Só " + h.starts + " titularidades em 38 na época passada" };
  }
  if (h.starts <= 21) {
    return { nivel: 1, texto: h.starts + " titularidades em 38 na época passada" };
  }
  return null;
}

function riscoJogador(p, mencionados) {
  const motivos = [];
  let nivel = 0;
  const est = estadoDe(p);
  if (STATUS_FORA.has(p.status)) {
    nivel = 3;
    motivos.push(est.rotulo + (p.news ? " — " + p.news : ""));
  } else if (p.status === "d") {
    nivel = 2;
    motivos.push(est.rotulo + (p.news ? " — " + p.news : ""));
  }
  const rot = nivel < 3 ? riscoRotacao(p) : null; // se já não joga, rotação é ruído
  if (rot) {
    nivel = Math.max(nivel, rot.nivel);
    motivos.push(rot.texto);
  }
  if (mencionados.has(p.id)) {
    nivel = Math.max(nivel, 1);
    motivos.push("Referido na antevisão do clube");
  }
  return nivel > 0 ? { nivel, motivos } : null;
}

function initConferencias() {
  const c = D.conferencias || { clubes: [] };
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  const meus = eu ? D.players.filter((p) => p.owner === eu.entry_id) : [];

  const mencionados = new Set();
  c.clubes.forEach((cl) => cl.itens.forEach((i) => i.mencoes.forEach((id) => mencionados.add(id))));

  // --- Lista de risco ---
  $("risco-legenda").textContent = Object.keys(D.jornadas || {}).length === 0
    ? "Estado clínico da API e titularidades da época passada (ainda não há jogos disputados)."
    : "Estado clínico da API e minutos realmente jogados nas jornadas já disputadas.";

  const emRisco = meus
    .map((p) => ({ p, r: riscoJogador(p, mencionados) }))
    .filter((x) => x.r)
    .sort((a, b) => b.r.nivel - a.r.nivel || a.p.element_type - b.p.element_type);

  if (emRisco.length === 0) {
    $("nota-risco").hidden = false;
  } else {
    $("lista-risco").innerHTML = emRisco.map(({ p, r }) => {
      const rotulo = r.nivel === 3 ? "Não joga" : r.nivel === 2 ? "Risco alto" : "A vigiar";
      return '<li class="risco ' + NIVEIS[r.nivel] + '">' +
        '<div class="linha">' +
          '<span class="nome">' + esc(p.web_name) + "</span>" +
          '<span class="clube">' + nomeClube(p.team) + " · " + (POSICOES[p.element_type] || "?") + "</span>" +
          '<span class="estado ' + NIVEIS[r.nivel] + '">' + rotulo + "</span>" +
        "</div>" +
        "<ul class=\"motivos\">" +
          r.motivos.map((m) => "<li>" + esc(m) + "</li>").join("") +
        "</ul>" +
      "</li>";
    }).join("");
  }

  // --- Antevisões por clube ---
  if (c.clubes.length === 0) { $("nota-conf").hidden = false; return; }
  $("conf-clubes").innerHTML = c.clubes.map((cl) => {
    const doClube = meus.filter((p) => p.team === cl.team_id).map((p) => p.web_name);
    const comMencao = cl.itens.filter((i) => i.mencoes.length > 0).length;
    const itens = cl.itens.map((i) => {
      const data = i.data ? fmtDataHora.format(new Date(i.data)) : "";
      const nomes = i.mencoes.map((id) => (jogadoresPorId[id] || {}).web_name).filter(Boolean);
      return '<li class="' + (nomes.length ? "mencao" : "") + '">' +
        '<a href="' + esc(i.link) + '" target="_blank" rel="noopener">' + esc(i.titulo) + "</a>" +
        (i.conferencia ? ' <span class="estado warn">antevisão</span>' : "") +
        (nomes.length ? ' <span class="estado bad">⚑ ' + esc(nomes.join(", ")) + "</span>" : "") +
        ' <span class="data">' + data + "</span>" +
        (i.resumo ? '<p class="resumo">' + esc(i.resumo) + "</p>" : "") +
      "</li>";
    }).join("");
    return "<details class=\"cartao\"" + (comMencao ? " open" : "") + ">" +
      "<summary>" +
        '<span class="nome">' + esc(cl.nome) + "</span>" +
        '<span class="clube">' + esc(doClube.join(", ")) + "</span>" +
        (comMencao ? '<span class="badges"><span class="estado bad">⚑ ' + comMencao + "</span></span>" : "") +
      "</summary>" +
      '<div class="corpo"><ul class="wire">' + itens + "</ul></div>" +
    "</details>";
  }).join("");
}

/* ---------- Mercado ---------- */

function nomeJogador(id) {
  const p = jogadoresPorId[id];
  return p ? esc(p.web_name) + ' <span class="clube">(' + nomeClube(p.team) + ")</span>" : "?";
}

function initMercado() {
  const m = D.mercado || { noticias: [], transacoes: [] };

  if (m.transacoes.length === 0) {
    $("nota-movimentos").hidden = false;
  } else {
    const KINDS = { w: "waiver", f: "free agency" };
    $("lista-movimentos").innerHTML = m.transacoes.map((t) => {
      const eq = entradasPorEntryId[t.entry];
      const aceite = t.result === "a";
      const data = t.added ? fmtDataHora.format(new Date(t.added)) : "";
      return '<li class="' + (aceite ? "" : "recusado") + '">' +
        '<div class="linha">' +
          '<span class="nome">' + esc(eq ? eq.entry_name : "?") + "</span>" +
          '<span class="clube">GW' + t.event + " · " + (KINDS[t.kind] || t.kind) + "</span>" +
          '<span class="estado ' + (aceite ? "ok" : "bad") + '">' +
            (aceite ? "aceite" : "recusado") + "</span>" +
          '<span class="data">' + data + "</span>" +
        "</div>" +
        '<p class="troca">Entra ' + nomeJogador(t.element_in) +
          " · sai " + nomeJogador(t.element_out) + "</p>" +
      "</li>";
    }).join("");
  }

  if (m.noticias.length === 0) {
    $("nota-wire").hidden = false;
  } else {
    $("lista-wire").innerHTML = m.noticias.map((n) => {
      const data = n.data ? fmtDataHora.format(new Date(n.data)) : "";
      return "<li>" +
        '<a href="' + esc(n.link) + '" target="_blank" rel="noopener">' + esc(n.titulo) + "</a>" +
        (n.rumor ? ' <span class="estado warn">rumor</span>' : "") +
        ' <span class="data">' + data + "</span>" +
      "</li>";
    }).join("");
  }
}

/* ---------- Separadores ---------- */

function initTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  function ativar(tab) {
    tabs.forEach((t) => {
      const ativo = t === tab;
      t.setAttribute("aria-selected", String(ativo));
      t.tabIndex = ativo ? 0 : -1;
      $(t.getAttribute("aria-controls")).hidden = !ativo;
    });
    tab.focus();
  }
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => ativar(tab));
    tab.addEventListener("keydown", (ev) => {
      const delta = { ArrowRight: 1, ArrowLeft: -1 }[ev.key];
      if (delta) {
        ev.preventDefault();
        ativar(tabs[(i + delta + tabs.length) % tabs.length]);
      }
    });
  });
}

/* ---------- Arranque ---------- */

async function main() {
  try {
    const resp = await fetch("data/data.json", { cache: "no-store" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    D = await resp.json();
  } catch (err) {
    $("atualizado").textContent =
      "Não foi possível carregar os dados. Tenta novamente mais tarde.";
    console.error(err);
    return;
  }
  entradasPorId = Object.fromEntries(D.entries.map((e) => [e.id, e]));
  entradasPorEntryId = Object.fromEntries(D.entries.map((e) => [e.entry_id, e]));
  jogadoresPorId = Object.fromEntries(D.players.map((p) => [p.id, p]));
  const noticias = comNoticias();
  initCabecalho();
  initTicker(noticias);
  initBoletim(noticias);
  initLiga();
  initMinhaEquipa();
  initEquipas();
  initConferencias();
  initProjecoes();
  initSugestoes();
  initMercado();
  initJogadores();
  initTabs();
}

main();
