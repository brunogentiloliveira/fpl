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

function construirPriors() {
  priorsPos = {};
  [1, 2, 3, 4].forEach((pos) => {
    priorsPos[pos] = D.players
      .filter((p) => p.element_type === pos && p.minutes >= MIN_PRIOR)
      .map((p) => ({
        rank: p.draft_rank ?? 1e9,
        pp90: (p.total_points / p.minutes) * 90,
        minJogo: Math.min(90, p.minutes / JOGOS_EPOCA),
      }))
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
  // Encolhimento: poucos minutos ⇒ o valor aproxima-se do prior da posição/rank.
  const pp90 = ((p.total_points + (prior.pp90 * MIN_PRIOR) / 90) / (p.minutes + MIN_PRIOR)) * 90;

  let xmin = p.minutes > 0 ? Math.min(90, p.minutes / JOGOS_EPOCA) : prior.minJogo;
  const tr = (D.transferencias || {})[p.id];
  let bump = null;
  if (tr && tr.confirmada && !STATUS_FORA.has(p.status)) {
    const piso = pisoTransferencia(tr.valor);
    if (piso > xmin) { bump = Math.round(piso - xmin); xmin = piso; }
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
  return { pp90, xmin, ppj, prox3, jogos, tr, bump };
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
  return "<tr>" +
    "<td>" + esc(p.web_name) + badges +
      '<span class="sub">' + nomeClube(p.team) + " · " + (POSICOES[p.element_type] || "?") +
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

/* ---------- Conferências e risco de não jogar ---------- */

const NIVEIS = { 3: "bad", 2: "bad", 1: "warn" };

function riscoRotacao(p) {
  const gw = D.game.current_event; // null antes do arranque da época
  if (p.minutes === 0) {
    return { nivel: 2, texto: "Sem minutos na Premier League" };
  }
  if (gw == null) {
    // starts/minutes ainda são da época passada (38 jornadas)
    if (p.starts <= 12) {
      return { nivel: 2, texto: "Só " + p.starts + " titularidades em 38 na época passada" };
    }
    if (p.starts <= 21) {
      return { nivel: 1, texto: p.starts + " titularidades em 38 na época passada" };
    }
    return null;
  }
  if (gw < 3) return null; // amostra demasiado pequena
  const razao = p.starts / gw;
  if (razao < 0.4) return { nivel: 2, texto: "Titular em " + p.starts + " de " + gw + " jornadas" };
  if (razao < 0.7) return { nivel: 1, texto: "Titular em " + p.starts + " de " + gw + " jornadas" };
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
  $("risco-legenda").textContent = D.game.current_event == null
    ? "Estado clínico da API e titularidades da época passada (a época ainda não começou)."
    : "Estado clínico da API e titularidades desta época.";

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
  initMercado();
  initJogadores();
  initTabs();
}

main();
