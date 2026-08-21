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
  }).sort((a, b) => (a.draft_rank ?? 1e9) - (b.draft_rank ?? 1e9));

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
    return "<tr>" +
      '<td class="num">' + (p.draft_rank ?? "–") + "</td>" +
      "<td>" + esc(p.web_name) + marca + '<span class="sub">' + nomeClube(p.team) + "</span></td>" +
      "<td>" + (POSICOES[p.element_type] || "?") + "</td>" +
      '<td class="num">' + p.total_points + "</td>" +
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
  $("filtros").addEventListener("submit", (ev) => ev.preventDefault());
  $("mostrar-mais").addEventListener("click", () => {
    visiveis += PASSO;
    desenharJogadores();
  });
  aplicarFiltros();
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
  const noticias = comNoticias();
  initCabecalho();
  initTicker(noticias);
  initBoletim(noticias);
  initLiga();
  initMinhaEquipa();
  initEquipas();
  initJogadores();
  initTabs();
}

main();
