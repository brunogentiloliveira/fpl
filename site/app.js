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

/**
 * Já não está na Premier League.
 *
 * A FPL demora a mudar o `status` de quem sai — o Watkins tinha transferência
 * confirmada para o Al Hilal e continuava como "a", o que o fazia aparecer nas
 * sugestões (e ainda com piso de minutos por a transferência ser cara). O
 * Transfermarkt lista Entradas e Saídas por clube, e quem está nas saídas sem
 * estar nas entradas foi-se mesmo embora.
 */
function saiuDaLiga(p) {
  return Object.prototype.hasOwnProperty.call(D.saiu_da_liga || {}, String(p.id));
}

/** Fora de jogo por qualquer razão: lesão, castigo, ou já não estar na liga. */
function indisponivel(p) {
  return STATUS_FORA.has(p.status) || saiuDaLiga(p);
}

function estadoDe(p) {
  if (saiuDaLiga(p)) return { rotulo: "Saiu da liga", sev: "bad" };
  const e = ESTADOS[p.status] || { rotulo: p.status, sev: "" };
  if (p.status === "d" && p.chance_of_playing_next_round != null) {
    return { rotulo: "Dúvida " + p.chance_of_playing_next_round + "%", sev: "warn" };
  }
  return e;
}

/* ---------- Cabeçalho ---------- */

function initCabecalho() {
  document.title = D.league.name + (ehClassica() ? " · FPL" : " · FPL Draft");
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

// Saída do clube: a API usa u/n tanto para quem saiu como para outros
// indisponíveis, por isso é o texto da notícia que distingue.
const FRASES_SAIDA = ["has joined", "has returned", "on loan"];

function saiuDoClube(p) {
  const news = (p.news || "").toLowerCase();
  return FRASES_SAIDA.some((f) => news.includes(f));
}

const GRUPOS_BOLETIM = ["Do teu plantel", "De outros gestores", "Livres"];

/** Quem o Scout dá como fora sem a API ainda ter notícia dele. */
function soNoScout(p) {
  const f = ffsDe(p);
  return !!(f && f.estado === "fora" && !(p.news && p.news.trim()));
}

/** O boletim junta as notícias da API com o que só o Scout sabe. */
function noticiasBoletim() {
  return comNoticias().concat(D.players.filter(soNoScout));
}

/** Primeiro os meus, depois os de outros gestores, por fim os livres. */
function pesoDono(p, eu) {
  if (eu && p.owner === eu.entry_id) return 0;
  return p.owner != null ? 1 : 2;
}

/** Scout > fora > dúvida > saída do clube > resto. */
function pesoGravidade(p) {
  const f = ffsDe(p);
  if (f && f.estado === "fora") return -1;
  if (saiuDoClube(p)) return 2;
  if (indisponivel(p)) return 0;
  if (p.status === "d") return 1;
  return 3;
}

/** Ordem do boletim: quem exige ação primeiro (o ticker fica cronológico). */
function ordenarBoletim(noticias) {
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  return noticias.slice().sort((a, b) =>
    pesoDono(a, eu) - pesoDono(b, eu) ||
    pesoGravidade(a) - pesoGravidade(b) ||
    (b.news_added || "").localeCompare(a.news_added || ""));
}

function initBoletim(noticias) {
  if (noticias.length === 0) { $("nota-boletim").hidden = false; return; }
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  const contagens = noticias.reduce((c, p) => {
    c[pesoDono(p, eu)] = (c[pesoDono(p, eu)] || 0) + 1;
    return c;
  }, {});
  let grupoAtual = null;

  const ul = $("lista-boletim");
  ul.innerHTML = noticias.map((p) => {
    let cabecalho = "";
    const grupo = pesoDono(p, eu);
    if (grupo !== grupoAtual) {
      grupoAtual = grupo;
      cabecalho = '<li class="grupo">' + GRUPOS_BOLETIM[grupo] +
        " (" + contagens[grupo] + ")</li>";
    }
    const est = estadoDe(p);
    const dono = nomeDono(p.owner);
    const ffs = ffsDe(p);
    const scoutFora = !!(ffs && ffs.estado === "fora");
    const artigo = (D.ffs || {}).artigo;
    const quando = p.news_added || (scoutFora && artigo ? artigo.data : null);
    const data = quando ? fmtDataHora.format(new Date(quando)) : "";
    const sev = scoutFora ? "bad" : est.sev;
    return cabecalho + '<li class="' + sev + '">' +
      '<div class="linha1">' +
        '<span class="nome">' + esc(p.web_name) + "</span>" +
        '<span class="clube">' + nomeClube(p.team) + " · " + (POSICOES[p.element_type] || "?") + "</span>" +
        (scoutFora ? '<span class="estado bad">Fora (Scout)</span>' : "") +
        (p.news ? '<span class="estado ' + est.sev + '">' + esc(est.rotulo) + "</span>" : "") +
        '<span class="data">' + data + "</span>" +
      "</div>" +
      (p.news ? '<p class="news">' + esc(p.news) + "</p>" : "") +
      (scoutFora
        ? '<p class="news fonte-scout">Fantasy Football Scout: “' + esc(ffs.frase) + "”" +
          (p.news ? "" : " — a API oficial ainda não tem notícia dele.") + "</p>"
        : "") +
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

/* ---------- Equipas (cartão por gestor) ---------- */

function initEquipas() {
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  const rankPor = Object.fromEntries(D.standings.map((s) => [s.league_entry, s.rank]));
  const ordenadas = D.entries.slice().sort((a, b) =>
    (rankPor[a.id] ?? a.waiver_pick ?? 99) - (rankPor[b.id] ?? b.waiver_pick ?? 99));

  $("cartoes-equipas").innerHTML = ordenadas.map((e) => {
    const plantel = D.players.filter((p) => p.owner === e.entry_id);
    const fora = plantel.filter(indisponivel).length;
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
  if (ordem === "preco") {
    filtrados.sort((a, b) => (b.now_cost || 0) - (a.now_cost || 0));
  } else if (ordem === "proj") {
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
        '<span class="sub">' + nomeClube(p.team) +
          (p.draft_rank ? " · #" + p.draft_rank : "") + "</span></td>" +
      "<td>" + (POSICOES[p.element_type] || "?") + "</td>" +
      '<td class="num">' + p.total_points + "</td>" +
      '<td class="num forte">' + projecao(p).ppj.toFixed(1) + "</td>" +
      "<td>" + (ehClassica()
        ? (p.now_cost ? precoDe(p).toFixed(1) + "M" +
            '<span class="sub">' + (p.selected_by_percent || "0") + "% têm</span>" : "—")
        : (dono ? esc(dono) : '<span class="sub">Livre</span>')) + "</td>" +
    "</tr>";
  }).join("");
  $("contagem-jogadores").textContent =
    filtrados.length + " jogador" + (filtrados.length === 1 ? "" : "es") +
    (mostrar.length < filtrados.length ? " (a mostrar " + mostrar.length + ")" : "");
  $("mostrar-mais").hidden = mostrar.length >= filtrados.length;
}

/** A clássica não tem donos nem draft rank, mas tem preços. */
function adaptarJogadoresAoModo() {
  if (!ehClassica()) return;
  const cabecalho = document.querySelector("#tabela-jogadores thead th:last-child");
  if (cabecalho) cabecalho.textContent = "Preço";
  const soLivres = $("so-livres");
  if (soLivres && soLivres.parentElement) soLivres.parentElement.hidden = true;
  const ordenar = $("ordenar");
  if (ordenar) {
    ordenar.querySelector('option[value="rank"]').remove();
    ordenar.insertAdjacentHTML("beforeend",
      '<option value="preco">Ordenar por preço</option>');
    ordenar.value = "proj";
  }
}

function initJogadores() {
  adaptarJogadoresAoModo();
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

/**
 * O número que o outro gestor olha primeiro: os pontos da época passada. Vem do
 * histórico congelado — `total_points` do bootstrap passa a contar a época a
 * decorrer assim que ela arranca.
 */
function pontosEpocaPassada(p) {
  return historicoDe(p).total_points || 0;
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
      const j = js[ev];
      const eq = j.equipas || [];
      // Conta quando o jogo DESTE jogador já se realizou. A jornada inteira só
      // fica "finalizada" depois dos bónus, mas os minutos já são definitivos.
      const jogado = eq.length ? eq.includes(p.team) : !!j.finalizada;
      const s = j.stats[String(p.id)] || [];
      // BPS e expected só existem em jornadas recolhidas a partir de 2026-08-23;
      // nas anteriores ficam indefinidos, e quem os usa tem de contar com isso.
      return {
        event: ev, minutos: s[0] || 0, pontos: s[1] || 0, finalizada: jogado,
        bps: s[2], xg: s[3], xa: s[4], xgc: s[5],
      };
    });
}

/* --- Pontos esperados a partir das estatísticas subjacentes --- */

// Valores de recurso, caso a liga não publique a tabela (nunca aconteceu).
const LIMITES_XI_OMISSAO = { 1: [1, 1], 2: [3, 5], 3: [2, 5], 4: [1, 3] };

/* --- Pontuação: vem da própria liga, não de valores escritos à mão --- */

const POS_SIGLA = { 1: "GKP", 2: "DEF", 3: "MID", 4: "FWD" };

function regra(chave, omissao) {
  const v = ((D.regras || {}).scoring || {})[chave];
  return v === undefined || v === null ? omissao : v;
}

/** Valor de um acontecimento para a posição do jogador (ex.: golo de GR vale 10). */
function regraPos(prefixo, pos, omissao) {
  return regra(prefixo + "_" + (POS_SIGLA[pos] || "MID"), omissao);
}

/** Limites de formação do onze, tal como a liga os define. */
function limitesXI() {
  const sq = (D.regras || {}).squad || {};
  const lim = {};
  [1, 2, 3, 4].forEach((pos) => {
    const s = POS_SIGLA[pos];
    lim[pos] = [
      sq["min_play_" + s] ?? LIMITES_XI_OMISSAO[pos][0],
      sq["max_play_" + s] ?? LIMITES_XI_OMISSAO[pos][1],
    ];
  });
  return lim;
}

/**
 * Penalização esperada por golos sofridos (GR e DEF perdem 1 ponto por cada 2).
 *
 * Com os golos sofridos a seguir uma Poisson de média λ, o número de castigos é
 * ⌊X/2⌋, cuja média tem forma fechada: (λ − P(X ímpar)) / 2, com
 * P(X ímpar) = (1 − e^(−2λ)) / 2. É o contrapeso da baliza a zero, que o modelo
 * já premiava sem nunca castigar o lado de lá.
 */
function castigoGolosSofridos(pos, xgc90) {
  const porCada = regraPos("goals_conceded", pos, 0);
  if (!porCada || xgc90 <= 0) return 0;
  const limite = regra("concede_limit", 2);
  const impar = (1 - Math.exp(-2 * xgc90)) / 2;
  const castigos = limite === 2 ? (xgc90 - impar) / 2 : xgc90 / limite;
  return castigos * porCada;
}
/** P(X >= k) com X ~ Poisson(media). */
function probPoissonAtinge(media, k) {
  let acumulado = 0;
  let termo = Math.exp(-media);
  for (let i = 0; i < k; i += 1) {
    acumulado += termo;
    termo *= media / (i + 1);
  }
  return Math.max(0, Math.min(1, 1 - acumulado));
}

/**
 * Contribuição defensiva: a liga dá 2 pontos a quem chega ao limiar de ações
 * defensivas **naquele jogo** (10 para defesas, 12 para médios e avançados).
 *
 * Sendo um limiar por jogo e não um total, a média não chega: usa-se a mesma
 * Poisson da baliza a zero para estimar com que frequência é atingido. Vale
 * 0.67 pts/90 a um defesa médio (15% dos pontos dele) e chega a 1.6 nos mais
 * defensivos — o maior fator que o modelo ignorava.
 *
 * Aproximação assumida: as ações defensivas são provavelmente mais dispersas
 * do que uma Poisson, o que subestima quem está longe do limiar e sobrestima
 * quem está muito acima. Com as jornadas agora guardadas uma a uma, isto passa
 * a ser verificável ao fim de algumas.
 */
function pontosContribuicaoDefensiva(pos, dc90) {
  const pontos = regraPos("defensive_contribution", pos, 0);
  const limiar = regraPos("defensive_contribution_limit", pos, 0);
  if (!pontos || !limiar || dc90 <= 0) return 0;
  return probPoissonAtinge(dc90, limiar) * pontos;
}

// Peso do modelo de xG/xA contra a taxa de pontos que o jogador fez mesmo.
// As estatísticas subjacentes preveem melhor o futuro; os pontos reais apanham
// o que o modelo não tem (penáltis defendidos fora de época, sequências de bónus,
// o que quer que a Poisson das defensivas não capte).
//
// **Medido** (Fase 2, 2026-09-01): 397 pares época→época seguinte com 900+
// minutos dos dois lados, validação repetida em 200 divisões. O ótimo está em
// 0.7–0.8 e o antigo 0.5 ficava 1.5% pior; num subconjunto limpo (só épocas em
// que a contribuição defensiva já existia) dá o mesmo. Por posição o modelo
// esperado ganha em defesas, médios e avançados. Fica em 0.7, o extremo
// conservador do ótimo: guarda 30% para o que o modelo não vê.
const PESO_ESPERADO = 0.7;

function num(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Pontos por 90 minutos estimados a partir do que o jogador gera, não do que
 * marcou: golos esperados, assistências esperadas, probabilidade de baliza a
 * zero, defesas, bónus e cartões.
 *
 * Nota sobre penáltis e bolas paradas: os campos de cargo (`penalties_order`,
 * `direct_freekicks_order`, cantos) vêm vazios nesta API para todos os
 * jogadores, por isso não há como dar um bónus explícito a quem os marca. Mas o
 * valor que geram já está aqui: um penálti vale ~0.79 de xG e os cantos e
 * livres alimentam o xA de quem os bate.
 */
// Fator que alinha a média do modelo esperado com a dos pontos realmente feitos.
// Nenhum modelo apanha tudo, por isso o nível fica ao lado; isto alinha-o com a
// média realizada sem mexer na ordenação. Desceu para perto de 1 quando as
// contribuições defensivas entraram — eram a maior parcela em falta.
let calibEsperado = 1;

function calibrarEsperado() {
  let real = 0;
  let esperado = 0;
  D.players.forEach((p) => {
    const h = historicoDe(p);
    if (!h || !h.minutes || h.minutes < MIN_PRIOR) return;
    const c = componentesPP90(p, h, true);
    if (!c) return;
    real += (h.total_points / h.minutes) * 90;
    esperado += c.total;
  });
  calibEsperado = esperado > 0 ? real / esperado : 1;
}

function componentesPP90(p, hist, semCalibrar) {
  const min = hist.minutes || 0;
  if (min < 90) return null; // amostra curta demais para uma taxa por 90
  const por90 = (v) => (num(v) / min) * 90;
  const pos = p.element_type;

  const golos = por90(hist.expected_goals) * regraPos("goals_scored", pos, 4);
  const assist = por90(hist.expected_assists) * regra("assists", 3);
  // Poisson: probabilidade de a equipa não sofrer, dado o xG concedido por 90.
  const xgc90 = por90(hist.expected_goals_conceded);
  const baliza = Math.exp(-xgc90) * regraPos("clean_sheets", pos, 0);
  // ... e o reverso, que faltava: cada 2 golos sofridos tiram 1 ponto a GR e DEF.
  const sofridos = castigoGolosSofridos(pos, xgc90);
  const defesas = pos === 1
    ? (por90(hist.saves) / regra("saves_limit", 3)) * regra("saves", 1) +
      por90(hist.penalties_saved) * regra("penalties_saved", 5)
    : 0;
  const defensivas = pontosContribuicaoDefensiva(
    pos, por90(hist.defensive_contribution));
  const bonus = por90(hist.bonus);
  const cartoes = por90(hist.yellow_cards) * regra("yellow_cards", -1) +
    por90(hist.red_cards) * regra("red_cards", -3) +
    por90(hist.penalties_missed) * regra("penalties_missed", -2);
  const autoGolos = por90(hist.own_goals) * regra("own_goals", -2);

  const presenca = regra("long_play", 2);
  const total = presenca + golos + assist + baliza + sofridos + defesas +
    defensivas + bonus + cartoes + autoGolos;
  const k = semCalibrar ? 1 : calibEsperado;
  return {
    total: Math.max(0, total) * k,
    presenca: presenca * k,
    golos: golos * k,
    assist: assist * k,
    baliza: baliza * k,
    sofridos: sofridos * k,
    defesas: defesas * k,
    defensivas: defensivas * k,
    bonus: bonus * k,
    penalizacoes: (cartoes + autoGolos) * k,
  };
}

/* --- Bola parada: penáltis, livres e cantos --- */

// Um penálti vale ~0.79 de golo e as equipas ganham ~0.12 por jogo.
const PEN_GOLOS_90 = 0.095;
const QUOTA_PEN = { 1: 1, 2: 0.2, 3: 0.05 };      // 2.º e 3.º batem de vez em quando
const FK_GOLOS_90 = { 1: 0.02, 2: 0.01 };          // golos de livre direto são raros
const CANTOS_XA90 = { 1: 0.05, 2: 0.02, 3: 0.01 }; // valem sobretudo em assistências

function bolaParadaDe(p) {
  return (D.bolaparada || {})[p.id] || null;
}

/**
 * Quanto do cargo é que o histórico ainda não reflete.
 *
 * Se um jogador já batia os penáltis no ano passado, o xG dele já os inclui e
 * somar outra vez seria contar a dobrar. O acréscimo vale a sério para quem tem
 * pouca amostra ou mudou de clube — aí o histórico não diz nada sobre o cargo.
 */
function pesoBolaParada(p, hist) {
  const bp = bolaParadaDe(p);
  if (!bp) return 0;
  const confianca = bp.confianca === "alta" ? 1 : 0.5;
  const tr = (D.transferencias || {})[p.id];
  if (tr && tr.confirmada) return confianca;
  return confianca * (MIN_PRIOR / ((hist.minutes || 0) + MIN_PRIOR));
}

/** Pontos por 90 que o cargo de bola parada acrescenta. */
function pontosBolaParada(p, hist) {
  const bp = bolaParadaDe(p);
  if (!bp) return 0;
  const golos90 = PEN_GOLOS_90 * (QUOTA_PEN[bp.pen] || 0) + (FK_GOLOS_90[bp.fk] || 0);
  const assist90 = CANTOS_XA90[bp.cantos] || 0;
  return (golos90 * regraPos("goals_scored", p.element_type, 4) +
    assist90 * regra("assists", 3)) *
    pesoBolaParada(p, hist);
}

/** Etiqueta curta dos cargos: P1 penáltis, LL livres, C cantos. */
function etiquetaBolaParada(p) {
  const bp = bolaParadaDe(p);
  if (!bp) return "";
  const partes = [];
  if (bp.pen) partes.push("P" + bp.pen);
  if (bp.fk) partes.push("LL" + bp.fk);
  if (bp.cantos) partes.push("C" + bp.cantos);
  return partes.join(" ");
}

/** Taxa de pontos por 90 usada como base: mistura o esperado com o realizado. */
function taxaBase(p, hist) {
  const min = hist.minutes || 0;
  const realizada = min > 0 ? (hist.total_points / min) * 90 : null;
  const comp = componentesPP90(p, hist);
  if (comp === null) return realizada;
  if (realizada === null) return comp.total;
  return PESO_ESPERADO * comp.total + (1 - PESO_ESPERADO) * realizada;
}

function construirPriors() {
  calibrarEsperado();
  priorsPos = {};
  [1, 2, 3, 4].forEach((pos) => {
    priorsPos[pos] = D.players
      .filter((p) => p.element_type === pos && historicoDe(p).minutes >= MIN_PRIOR)
      .map((p) => {
        const h = historicoDe(p);
        return {
          rank: p.draft_rank ?? 1e9,
          pp90: taxaBase(p, h),
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

/** Team news do Fantasy Football Scout (chega antes da API oficial). */
function ffsDe(p) {
  return ((D.ffs || {}).jogadores || {})[p.id] || null;
}

/**
 * Como o jogador apareceu no último ensaio de pré-época do clube.
 *
 * Já não tem secção própria no site (a pedido do utilizador): serve só de
 * entrada para o modelo e para justificar sugestões, e deixa de contar
 * sozinha assim que houver jornadas disputadas.
 */
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

/* --- Janela do calendário --- */

// Com 3 jornadas, a diferença entre o melhor e o pior calendário chega a 10%,
// o suficiente para o sorteio inverter diferenças de qualidade entre jogadores
// — e as decisões de waiver são, na prática, permanentes. Com 10 jornadas cai
// para 2.4% e deixa de dizer nada. 5 é o equilíbrio.
const JANELA_OMISSAO = 5;
const JANELAS = [3, 5, 8];
const DECAIMENTO = 0.85; // a próxima jornada pesa mais do que a última da janela

function janelaAtual() {
  const guardada = Number(lerGuardado("janela") || 0);
  return JANELAS.includes(guardada) ? guardada : JANELA_OMISSAO;
}

function definirJanela(n) {
  try {
    localStorage.setItem("janela", JSON.stringify(n));
  } catch (err) {
    /* sem localStorage: fica só nesta sessão */
  }
}

function fatorDificuldade(d) {
  return 1 + (3 - d) * 0.06; // adversário fácil (1) 1.12 … difícil (5) 0.88
}

/** Jogos das próximas `janela` **jornadas** (não os próximos `janela` jogos). */
function jogosNaJanela(jogos, janela, primeiraJornada) {
  if (!jogos.length) return [];
  const primeiro = primeiraJornada != null
    ? primeiraJornada : Math.min(...jogos.map((j) => j.event));
  return jogos.filter((j) => j.event >= primeiro && j.event < primeiro + janela);
}

/**
 * Média ponderada da dificuldade das próximas jornadas, ~1.0.
 *
 * É uma taxa e não um total: assim o número não cresce com a janela e continua
 * comparável aos pts/jornada.
 *
 * **Agrupa por jornada, não por jogo.** A versão anterior fazia a média sobre a
 * lista de jogos, e o comentário dizia que as duplas contavam duas vezes e as
 * jornadas em branco puxavam para baixo — não fazia nem uma coisa nem outra:
 * uma dupla entrava como dois valores numa média (peso nenhum a mais) e uma
 * jornada em branco simplesmente não aparecia na lista. Agora cada jornada
 * contribui com a **soma** dos seus jogos, portanto uma dupla vale perto do
 * dobro e uma em branco vale zero.
 */
function fatorCalendario(jogos, janela, primeiraJornada) {
  if (!jogos.length) return 1;
  const n = janela || janelaAtual();
  const porJornada = new Map();
  jogos.forEach((j, i) => {
    // Sem `event` cada jogo conta como a sua própria jornada: colapsá-los
    // todos num só seria uma falha silenciosa, com o fator a disparar.
    const ev = j.event == null ? -1000 + i : j.event;
    porJornada.set(ev, (porJornada.get(ev) || 0) + fatorDificuldade(j.difficulty));
  });
  // A janela ancora na **próxima jornada da liga**, não no primeiro jogo deste
  // jogador. Ancorar no jogo dele tornava invisível uma jornada em branco já a
  // seguir: a janela dele começava mais tarde e ninguém pagava por isso.
  const comEvento = [...porJornada.keys()].filter((e) => e > -1000);
  const primeiro = comEvento.length && primeiraJornada != null
    ? primeiraJornada : Math.min(...porJornada.keys());
  let soma = 0;
  let pesos = 0;
  for (let i = 0; i < n; i += 1) {
    const peso = Math.pow(DECAIMENTO, i);
    soma += (porJornada.get(primeiro + i) || 0) * peso; // sem jogo = 0
    pesos += peso;
  }
  return pesos > 0 ? soma / pesos : 1;
}

// Cinco amarelos valem um jogo de castigo, dez valem dois. A contagem é desta
// época e vem da API. Não modelo a data-limite a partir da qual o primeiro
// patamar deixa de contar — precisaria dela da API, e não vem.
const AMARELOS_CASTIGO = 5;

/**
 * Probabilidade de falhar uma jornada por acumulação de amarelos.
 *
 * Só conta quando está **a um cartão** do castigo: aí, a probabilidade de o
 * apanhar no próximo jogo é a taxa de amarelos dele aplicada aos minutos que
 * se espera que jogue. Com dois ou mais cartões em falta a probabilidade cai
 * muito e exigiria uma conta em dois passos que não se justifica.
 */
function riscoSuspensao(p, xmin) {
  const amarelos = num(p.yellow_cards);
  const minutos = num(p.minutes);
  if (!amarelos || minutos < 90) return 0;
  if (AMARELOS_CASTIGO - (amarelos % AMARELOS_CASTIGO) !== 1) return 0;
  // Teto de 50%: com poucos minutos a taxa dispara e deixa de ser credível.
  return Math.min(0.5, (amarelos / minutos) * xmin);
}

// Estatísticas que fazem sentido somar entre épocas — as que o modelo de pontos
// esperados lê. Ficam de fora minutos e titularidades, que são o denominador.
const CAMPOS_COMBINAVEIS = [
  "total_points", "expected_goals", "expected_assists", "expected_goals_conceded",
  "saves", "penalties_saved", "bonus", "yellow_cards", "red_cards",
  "penalties_missed", "own_goals", "defensive_contribution",
];

/**
 * Época passada e época a decorrer no mesmo objeto, para o modelo de pontos
 * esperados poder olhar para as duas.
 *
 * Cada estatística fica com as contagens desta época mais uma pseudo-contagem
 * da taxa da época passada, que vale MIN_PRIOR minutos. É a mesma fórmula que
 * já se usava só para os pontos, alargada a tudo o resto: com um jogo esta
 * época pesa 90/990 (~9%), ao fim de dez jornadas passa de metade.
 *
 * Sem isto, um avançado com quatro jogos, 1.9 de xG e zero golos continuava a
 * ser julgado pelo que fez em maio — o contrário da premissa do modelo.
 */
function historicoCombinado(p, hist) {
  const minEpoca = num(p.minutes);
  // Sem retrato congelado, `hist` já é esta época: combinar seria contá-la duas vezes.
  if (minEpoca <= 0 || !(D.historico || {})[p.id]) return hist;
  const minHist = hist.minutes || 0;
  const saida = { minutes: minEpoca + MIN_PRIOR, starts: hist.starts };
  CAMPOS_COMBINAVEIS.forEach((campo) => {
    const taxaHist = minHist > 0 ? num(hist[campo]) / minHist : 0;
    saida[campo] = num(p[campo]) + taxaHist * MIN_PRIOR;
  });
  return saida;
}

function projecao(p, ignorarAusencia) {
  const prior = priorDe(p);
  const hist = historicoDe(p);
  // Taxa combinada (esperado + realizado) sobre as duas épocas.
  const combinado = historicoCombinado(p, hist);
  const taxa = taxaBase(p, combinado);
  // O encolhimento para o prior da posição usa os minutos REAIS das duas
  // épocas, não os sintéticos do combinado — senão um estreante com 200
  // minutos ficava com o prior subvalorizado.
  const minTotal = (hist.minutes || 0) + num(p.minutes);
  const base = taxa === null ? prior.pp90
    : (taxa * minTotal + prior.pp90 * MIN_PRIOR) / (minTotal + MIN_PRIOR);
  const extraBP = pontosBolaParada(p, { ...hist, minutes: minTotal });
  const pp90 = base + extraBP;
  let xminHist = hist.minutes > 0 ? Math.min(90, hist.minutes / JOGOS_EPOCA) : prior.minJogo;

  // Jogos já disputados nesta época: a realidade manda mais do que o histórico.
  const uso = utilizacao(p).filter((u) => u.finalizada);
  const jogosObs = uso.length;
  // Quanto se confia no que já se viu em campo. n/(n+2): um jogo já vale um
  // terço (antes valia um quinto, e a média da época passada continuava a
  // mandar mesmo contra a evidência direta); nunca chega a 1, porque o
  // historial mantém sempre alguma palavra.
  const peso = jogosObs / (jogosObs + 2);
  const ultimos = uso.slice(-3);

  // Os pontos desta época já entram pelo `combinado`, com todas as outras
  // estatísticas; aqui só restam os minutos.
  let xmin = xminHist;
  if (jogosObs > 0) {
    const mediaRecente = ultimos.reduce((s, u) => s + u.minutos, 0) / ultimos.length;
    xmin = peso * mediaRecente + (1 - peso) * xminHist;
  }

  const tr = (D.transferencias || {})[p.id];
  let bump = null;
  // O piso da transferência é uma suposição: assim que houver jogos, vale o que
  // se viu. Exige **valor publicado**: o sinal é "custou caro, logo vai jogar".
  // A fonte oficial confirma mudanças sem dizer o preço, e sem preço não há
  // sinal nenhum — `pisoTransferencia(0)` devolveria 50 minutos a um reforço
  // de plantel qualquer. A confirmação sozinha continua a valer para a
  // pré-época (o onze do clube antigo não diz nada de quem mudou).
  if (tr && tr.confirmada && tr.valor > 0 && jogosObs < 3 && !indisponivel(p)) {
    const piso = pisoTransferencia(tr.valor);
    if (piso > xmin) { bump = Math.round(piso - xmin); xmin = piso; }
  }

  // O último ensaio de pré-época é o melhor indício de quem o treinador lança
  // enquanto não há jogos a sério. Perde peso à medida que eles aparecem, em
  // vez de desaparecer de repente: basta uma jornada para o cortar a direito
  // e um titular confirmado em campo ficava a valer menos do que quem ainda
  // não jogou.
  const pe = preEpocaDe(p);
  if (pe && !indisponivel(p)) {
    const forca = (pe.confianca === "alta" ? 1 : 0.5) * (1 - peso);
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
  // O Scout costuma saber da conferência de imprensa antes de a API atualizar.
  const ffs = ffsDe(p);
  if (ignorarAusencia) {
    // Projeção "se estivesse apto", para comparar com o valor de agora.
  } else if (indisponivel(p) || (ffs && ffs.estado === "fora")) {
    xmin = 0;
  } else if (p.status === "d" && p.chance_of_playing_next_round != null) {
    xmin *= p.chance_of_playing_next_round / 100;
  }
  // Acumulação de amarelos: entra depois do estado clínico, porque a taxa de
  // cartões aplica-se aos minutos que ele de facto espera jogar.
  if (!ignorarAusencia) xmin *= 1 - riscoSuspensao(p, xmin);
  xmin = Math.max(0, Math.min(90, xmin));

  const ppj = (pp90 * xmin) / 90;

  const janela = janelaAtual();
  const proxima = (D.next_event || {}).id;
  const jogos = jogosNaJanela((D.fixtures || {})[String(p.team)] || [], janela, proxima);
  const calFator = fatorCalendario(jogos, janela, proxima);
  const ppjCal = ppj * calFator;
  const naoUsado = jogosObs >= 2 && ultimos.every((u) => u.minutos === 0) &&
    !indisponivel(p);
  return { pp90, xmin, ppj, ppjCal, calFator, jogos, tr, bump, ultimos, jogosObs, naoUsado, pe, ffs,
    componentes: componentesPP90(p, hist), extraBP, bp: bolaParadaDe(p) };
}

/** "+3%" / "-4%": quanto o calendário mexe na projeção deste jogador. */
function sinalPct(fator) {
  const pct = Math.round((fator - 1) * 100);
  return pct === 0 ? "=" : (pct > 0 ? "+" : "") + pct + "%";
}

function explicarCalendario(pr) {
  if (pr.jogos.length === 0) return "sem jogos conhecidos no horizonte";
  const adv = pr.jogos.map((j) => (D.teams[String(j.opponent)] || {}).short_name +
    " (" + j.difficulty + ")").join(", ");
  return "Próximas " + pr.jogos.length + ": " + adv +
    " — o calendário mexe " + sinalPct(pr.calFator) + " na projeção";
}

/** Amplitude real do calendário nesta janela, para calibrar expectativas. */
function amplitudeCalendario() {
  const fatores = Object.keys(D.fixtures || {}).map((tid) =>
    fatorCalendario((D.fixtures[tid] || []).slice(0, janelaAtual())));
  if (fatores.length === 0) return null;
  return { min: Math.min(...fatores), max: Math.max(...fatores) };
}

/** Texto da decomposição dos pontos por 90, para tooltip. */
function decomporPP90(c, extra) {
  const partes = [
    "presença " + c.presenca.toFixed(1),
    "golos esperados " + c.golos.toFixed(1),
    "assistências esperadas " + c.assist.toFixed(1),
  ];
  if (c.baliza >= 0.05) partes.push("baliza a zero " + c.baliza.toFixed(1));
  if (c.defesas >= 0.05) partes.push("defesas " + c.defesas.toFixed(1));
  if (c.defensivas >= 0.05) {
    partes.push("contribuição defensiva " + c.defensivas.toFixed(1));
  }
  if (c.bonus >= 0.05) partes.push("bónus " + c.bonus.toFixed(1));
  if (c.sofridos <= -0.05) partes.push("golos sofridos " + c.sofridos.toFixed(1));
  if (c.penalizacoes <= -0.05) partes.push("cartões " + c.penalizacoes.toFixed(1));
  const txt = partes.join(" · ") + " = " + c.total.toFixed(1) + " pts/90 esperados";
  return extra >= 0.05 ? txt + " (+" + extra.toFixed(2) + " de bola parada)" : txt;
}

function linhaProjecao(p, pr) {
  const est = estadoDe(p);
  const badges =
    (pr.tr ? '<span class="estado ' + (pr.tr.confirmada ? "ok" : "warn") + '">' +
      esc(pr.tr.moeda) + pr.tr.valor + "M" + (pr.tr.confirmada ? "" : "?") +
      (pr.bump ? " +" + pr.bump + "min" : "") + "</span>" : "") +
    (est.sev ? ' <span class="estado ' + est.sev + '">' + esc(est.rotulo) + "</span>" : "");
  const visiveis = pr.jogos.slice(0, 4);
  const jogos = visiveis.map((j) =>
    '<span class="fx d' + j.difficulty + '">' +
      (D.teams[String(j.opponent)] || {}).short_name +
      (j.is_home ? "" : " (F)") + "</span>").join(" ") +
    (pr.jogos.length > visiveis.length
      ? ' <span class="fx d3">+' + (pr.jogos.length - visiveis.length) + "</span>" : "");
  const recentes = minutosRecentes(pr);
  const cargos = etiquetaBolaParada(p);
  const badgeBP = cargos
    ? ' <span class="estado ok" title="Bola parada: P penáltis, LL livres, C cantos (número = ordem)">' +
      cargos + "</span>" : "";
  return "<tr>" +
    "<td>" + esc(p.web_name) + badges + badgeBP +
      (pr.naoUsado ? ' <span class="estado bad">sem jogar</span>' : "") +
      '<span class="sub">' + nomeClube(p.team) + " · " + (POSICOES[p.element_type] || "?") +
      (recentes ? " · jogou " + recentes : "") +
      (jogos ? " · " + jogos : "") + "</span></td>" +
    '<td class="num"' + (pr.componentes
      ? ' title="' + esc(decomporPP90(pr.componentes, pr.extraBP)) + '"' : "") + ">" +
      pr.pp90.toFixed(1) + "</td>" +
    '<td class="num">' + Math.round(pr.xmin) + "</td>" +
    '<td class="num forte">' + pr.ppj.toFixed(1) + "</td>" +
    '<td class="num" title="' + esc(explicarCalendario(pr)) + '">' +
      pr.ppjCal.toFixed(1) + '<span class="fator">' + sinalPct(pr.calFator) + "</span></td>" +
  "</tr>";
}

function tabelaProjecao(linhas) {
  return '<table class="tabela tabela-proj">' +
    "<thead><tr><th>Jogador</th><th class=\"num\">Pts/90</th><th class=\"num\">Min</th>" +
    "<th class=\"num\">Pts/J</th><th class=\"num\" title=\"Pts por jornada ajustados à dificuldade das próximas ' + janelaAtual() + ' jornadas\">Calend.</th></tr></thead>" +
    "<tbody>" + linhas + "</tbody></table>";
}

function desenharLivres() {
  const pos = $("proj-pos").value;
  const livres = D.players
    .filter((p) => p.owner == null && !indisponivel(p))
    .filter((p) => !pos || String(p.element_type) === pos)
    .map((p) => ({ p, pr: projecao(p) }))
    // Ordenados pela taxa já ajustada ao calendário: é o que muda com a janela.
    .sort((a, b) => b.pr.ppjCal - a.pr.ppjCal)
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

/* --- Próximos jogos dos meus jogadores --- */

const fmtDiaHora = new Intl.DateTimeFormat("pt-PT", {
  timeZone: "Europe/Lisbon", weekday: "short", day: "numeric", month: "short",
});
const fmtHora = new Intl.DateTimeFormat("pt-PT", {
  timeZone: "Europe/Lisbon", hour: "2-digit", minute: "2-digit",
});

/**
 * Agrupa os próximos jogos por partida: cada uma com a data, a hora e os meus
 * jogadores que entram nela.
 */
function proximosJogos(meusX, limite) {
  const partidas = new Map();
  meusX.forEach((x) => {
    (x.pr.jogos || []).forEach((j) => {
      if (!j.kickoff) return;
      const casa = j.is_home ? x.p.team : j.opponent;
      const fora = j.is_home ? j.opponent : x.p.team;
      const chave = j.event + ":" + casa + "-" + fora;
      if (!partidas.has(chave)) {
        partidas.set(chave, {
          evento: j.event, kickoff: new Date(j.kickoff),
          casa, fora, dificuldade: j.difficulty, jogadores: [],
        });
      }
      const partida = partidas.get(chave);
      if (!partida.jogadores.some((y) => y.p.id === x.p.id)) {
        partida.jogadores.push(x);
      }
    });
  });

  return [...partidas.values()]
    .filter((m) => m.kickoff >= new Date(Date.now() - 2 * 36e5)) // ainda a decorrer conta
    .sort((a, b) => a.kickoff - b.kickoff)
    .slice(0, limite || 12);
}

function desenharProximosJogos(meusX) {
  const alvo = $("proximos-jogos");
  if (!alvo) return;
  const partidas = proximosJogos(meusX, 12);
  if (partidas.length === 0) {
    alvo.innerHTML = '<p class="nota">Sem jogos agendados para os teus jogadores.</p>';
    $("proximos-resumo").textContent = "";
    return;
  }

  const primeira = partidas[0];
  const horas = Math.round((primeira.kickoff - Date.now()) / 36e5);
  $("proximos-resumo").textContent = horas <= 0
    ? "a decorrer"
    : horas < 48
      ? "o próximo é daqui a " + horas + (horas === 1 ? " hora" : " horas")
      : "o próximo é " + fmtDiaHora.format(primeira.kickoff);

  let diaAtual = "";
  alvo.innerHTML = partidas.map((m) => {
    const dia = fmtDiaHora.format(m.kickoff);
    const cabecalho = dia !== diaAtual ? (diaAtual = dia, '<h4 class="dia">' + dia + "</h4>") : "";
    const jogadores = m.jogadores
      .sort((a, b) => b.pr.ppj - a.pr.ppj)
      .map((x) => {
        const est = estadoDe(x.p);
        const ffs = ffsDe(x.p);
        const fora = indisponivel(x.p) || (ffs && ffs.estado === "fora");
        return '<span class="chip">' +
          '<span class="chip-nome">' + esc(x.p.web_name) + "</span>" +
          '<span class="chip-info">' + (POSICOES[x.p.element_type] || "?") + " · " +
            x.pr.ppj.toFixed(1) + " pts</span>" +
          (fora ? '<span class="estado bad">fora</span>'
                : est.sev === "warn" ? '<span class="estado warn">dúvida</span>' : "") +
        "</span>";
      }).join("");

    return cabecalho +
      '<div class="jogo">' +
        '<div class="jogo-linha">' +
          '<span class="hora">' + fmtHora.format(m.kickoff) + "</span>" +
          '<span class="equipas">' + nomeClube(m.casa) + " – " + nomeClube(m.fora) + "</span>" +
          '<span class="fx d' + m.dificuldade + '">dif. ' + m.dificuldade + "</span>" +
          '<span class="gw">GW' + m.evento + "</span>" +
        "</div>" +
        '<div class="linha-campo jogo-jogadores">' + jogadores + "</div>" +
      "</div>";
  }).join("");
}

/* ---------- Sugestões da jornada ---------- */

// Formações válidas: lidas de settings.squad da liga (1 GR, 3-5 DEF, 2-5 MED, 1-3 AV).
const GANHO_MIN_LIVRE = 0.4;  // pts/jornada abaixo disto não vale o waiver
const GANHO_MIN_TROCA = 0.25; // ambos os lados têm de ganhar pelo menos isto

/** Melhor onze possível de um plantel, por projeção. */
function melhorXI(plantel) {
  const LIMITES_XI = limitesXI();
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
    if (xi.length >= (((D.regras || {}).squad || {}).play || 11)) break;
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
  return projecao(p, true).ppj;
}

function sugestoesLivres(meusX) {
  const livresX = comProjecao(D.players.filter((p) => p.owner == null && !indisponivel(p)));
  const pares = [];
  meusX.forEach((meu) => {
    livresX
      .filter((l) => l.p.element_type === meu.p.element_type)
      .forEach((livre) => {
        const ganho = livre.pr.ppj - meu.pr.ppj;
        if (ganho >= GANHO_MIN_LIVRE) {
          pares.push({ meu, livre, ganho, ganhoCal: livre.pr.ppjCal - meu.pr.ppjCal });
        }
      });
  });
  // O ganho puro (qualidade) já filtrou acima; a ordem segue o calendário escolhido.
  pares.sort((a, b) => b.ganhoCal - a.ganhoCal);

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

// Até quantos jogadores de cada lado. O plantel tem de ficar sempre com 15
// (2 GR / 5 DEF / 5 MED / 3 AV), por isso uma troca é sempre N-por-N e com o
// **mesmo conjunto de posições** dos dois lados — dar 2 e receber 1 é ilegal.
// Medido: 378 combinações a 1, 9 126 a 2 e 109 626 a 3, ~325 ms ao todo.
const MAX_TROCA = 3;
// Quanto é que uma troca maior tem de ganhar a mais para valer a pena propô-la:
// mais jogadores é mais atrito e mais risco, e sem isto o 3-por-3 aparecia
// sempre a repetir o 1-por-1 com dois enchimentos à volta.
const MARGEM_TAMANHO = 0.15;
// O adoçante tem de ser real. Sem isto saíam propostas a dizer "ele recebe
// mais do que dá" com 9.9 contra 9.9 — quatro centésimas não convencem
// ninguém a perder pontos no onze. Exige-se valor entregue a mais **e** que
// ele seja proporcional ao que se lhe está a pedir: quem perde 2 pts/jornada
// no onze não aceita por meio ponto de plantel.
const ADOCANTE_MIN = 0.4;
const ADOCANTE_QUOTA = 0.5;

/** Todas as combinações de `n` elementos. */
function combinacoes(lista, n) {
  if (n === 1) return lista.map((x) => [x]);
  const saida = [];
  const passo = (inicio, atual) => {
    if (atual.length === n) { saida.push(atual.slice()); return; }
    for (let i = inicio; i < lista.length; i += 1) {
      atual.push(lista[i]);
      passo(i + 1, atual);
      atual.pop();
    }
  };
  passo(0, []);
  return saida;
}

/** Posições de um grupo, ordenadas: só trocam grupos com a mesma assinatura. */
function assinaturaPosicoes(grupo) {
  return grupo.map((x) => x.p.element_type).sort().join("-");
}

function somaPpj(grupo) {
  return grupo.reduce((t, x) => t + x.pr.ppj, 0);
}

/**
 * Trocas propostas a cada gestor, de 1-por-1 até 3-por-3.
 *
 * **Porque é que passar de 1-por-1 muda o jogo**: com a mesma régua dos dois
 * lados, uma troca 1-por-1 da mesma posição é praticamente soma zero — por
 * isso o "ambos ganham" quase nunca disparava e quase tudo caía no cartaz. O
 * que quebra a simetria é o **banco**: no Draft só o onze pontua, e um bom
 * jogador parado no meu banco vale-me zero à margem mas pode valer muito no
 * onze dele. Daí que um 2-por-2 possa ser genuinamente bom para os dois.
 *
 * Dois tipos ficam:
 *  - `ambos`  — os dois onzes sobem. É o caso honesto.
 *  - `adocante` — o meu onze sobe e ele **recebe mais valor bruto do que dá**,
 *    mesmo que o onze dele não melhore. É a troca que se fecha juntando
 *    qualidade a mais do meu lado; fica marcada como tal, porque quem ganha
 *    sou eu.
 */
function sugestoesTrocas(meusX, euEntry) {
  const meuValor = valorXI(meusX);
  const meuXI = new Set(melhorXI(meusX).map((x) => x.p.id));
  const propostas = [];

  D.entries.filter((e) => e.id !== euEntry.id).forEach((outro) => {
    const delesX = comProjecao(D.players.filter((p) => p.owner === outro.entry_id));
    if (delesX.length === 0) return;
    const delesValor = valorXI(delesX);
    let melhorMenor = 0; // melhor ganho já conseguido com menos jogadores

    for (let n = 1; n <= MAX_TROCA; n += 1) {
      const porAssinatura = {};
      combinacoes(delesX, n).forEach((g) => {
        const chave = assinaturaPosicoes(g);
        (porAssinatura[chave] = porAssinatura[chave] || []).push(g);
      });

      const desteN = [];
      combinacoes(meusX, n).forEach((saem) => {
        const alternativas = porAssinatura[assinaturaPosicoes(saem)];
        if (!alternativas) return;
        const idsSaem = new Set(saem.map((x) => x.p.id));
        const meuBase = meusX.filter((x) => !idsSaem.has(x.p.id));
        const dou = somaPpj(saem);

        alternativas.forEach((entram) => {
          const ganhoMeu = valorXI(meuBase.concat(entram)) - meuValor;
          if (ganhoMeu < GANHO_MIN_TROCA) return;
          // Um negócio mais pequeno já consegue isto: não vale o atrito.
          if (ganhoMeu < melhorMenor + MARGEM_TAMANHO) return;

          const idsEntram = new Set(entram.map((x) => x.p.id));
          const delesNovo = delesX.filter((x) => !idsEntram.has(x.p.id)).concat(saem);
          const ganhoDeles = valorXI(delesNovo) - delesValor;
          const recebo = somaPpj(entram);
          const entregue = dou - recebo;            // valor de plantel que lhe dou a mais
          const pedido = Math.max(0, -ganhoDeles);  // o que ele perde no onze
          const tipo = ganhoDeles >= GANHO_MIN_TROCA ? "ambos"
            : (entregue >= ADOCANTE_MIN && entregue >= pedido * ADOCANTE_QUOTA)
              ? "adocante" : null;
          if (!tipo) return;
          desteN.push({
            outro, saem, entram, ganhoMeu, ganhoDeles, tipo, n,
            dou, recebo, entregue, pedido,
            // Quem sai sem fazer falta ao onze é o que adoça o negócio.
            adocantes: saem.filter((x) => !meuXI.has(x.p.id)),
          });
        });
      });

      desteN.forEach((pr) => { melhorMenor = Math.max(melhorMenor, pr.ganhoMeu); });
      propostas.push(...desteN);
    }
  });

  // Win-win primeiro; dentro de cada tipo, o que me dá mais.
  propostas.sort((a, b) => b.ganhoMeu - a.ganhoMeu);
  propostas.sort((a, b) => (a.tipo === "ambos" ? 0 : 1) - (b.tipo === "ambos" ? 0 : 1));

  // Cada jogador entra ou sai uma vez só, senão saem cinco variantes do mesmo.
  const usados = new Set();
  const escolhidas = [];
  for (const pr of propostas) {
    const envolvidos = pr.saem.concat(pr.entram).map((x) => x.p.id);
    if (envolvidos.some((id) => usados.has(id))) continue;
    envolvidos.forEach((id) => usados.add(id));
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
  const adv = pr.jogos.slice(0, 5)
    .map((j) => (D.teams[String(j.opponent)] || {}).short_name).join(", ");
  if (media <= 2.4) return "calendário fácil (" + adv + ")";
  if (media >= 3.6) return "calendário difícil (" + adv + ")";
  return "calendário equilibrado (" + adv + ")";
}

function minutosRecentes(pr) {
  if (!pr.ultimos || pr.ultimos.length === 0) return null;
  return pr.ultimos.map((u) => u.minutos + "'").join(", ");
}

/**
 * Porque é que este jogador sai, dita a verdade sobre a alternativa.
 *
 * A frase-tampão antiga dizia sempre "rende X pts por 90 min, abaixo da
 * alternativa" — e chegou a aparecer com o Ødegaard a 4.9 contra um Scott a
 * 4.4, ou seja a afirmar o contrário dos números que estavam ao lado. Quando o
 * rendimento por 90 é parecido, o motivo real são quase sempre os **minutos**,
 * e é isso que tem de estar escrito.
 */
function porqueSai(x, entra) {
  const est = estadoDe(x.p);
  if (indisponivel(x.p)) {
    return "está " + est.rotulo.toLowerCase() + " e não pontua";
  }
  if (x.pr.ffs && x.pr.ffs.estado === "fora") {
    return "está fora desta jornada segundo o team news do Fantasy Football Scout";
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
  if (citaPreEpoca(x.pr) && x.pr.pe.estado !== "titular") {
    return PE_TEXTO[x.pr.pe.estado];
  }
  if (x.pr.xmin < 55) {
    return "só deve jogar cerca de " + Math.round(x.pr.xmin) + " min por jornada";
  }
  if (entra) {
    const dPp90 = entra.pr.pp90 - x.pr.pp90;
    const dMin = entra.pr.xmin - x.pr.xmin;
    // Rendimento parecido (menos de 0.3 pts/90 de diferença) e minutos a
    // separá-los: é a situação mais comum, e a que a frase antiga escondia.
    if (Math.abs(dPp90) < 0.3 && dMin >= 5) {
      return "rende o mesmo por 90 minutos (" + x.pr.pp90.toFixed(1) + " contra " +
        entra.pr.pp90.toFixed(1) + "), mas espera-se que jogue menos: " +
        Math.round(x.pr.xmin) + " min por jornada contra " + Math.round(entra.pr.xmin);
    }
    if (dPp90 > 0) {
      return "rende " + x.pr.pp90.toFixed(1) + " pts por 90 min, contra " +
        entra.pr.pp90.toFixed(1) + " da alternativa";
    }
    if (dMin >= 5) {
      return "rende mais por 90 minutos (" + x.pr.pp90.toFixed(1) + " contra " +
        entra.pr.pp90.toFixed(1) + "), mas deve jogar menos: " +
        Math.round(x.pr.xmin) + " min contra " + Math.round(entra.pr.xmin);
    }
  }
  return "rende " + x.pr.pp90.toFixed(1) + " pts por 90 min";
}

/** A pré-época pesa cada vez menos; passados 3 jogos deixa de valer a pena cita-la. */
function citaPreEpoca(pr) {
  return !!pr.pe && pr.jogosObs < 3;
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
  const jogouMesmo = x.pr.ultimos && x.pr.ultimos.some((u) => u.minutos > 0);
  if (recentes && jogouMesmo) {
    partes.push("já jogou " + recentes + " nas últimas jornadas");
  } else if (citaPreEpoca(x.pr) && x.pr.pe.estado === "titular") {
    partes.push(PE_TEXTO.titular);
  } else if (x.pr.tr && x.pr.tr.confirmada) {
    partes.push("custou " + x.pr.tr.moeda + x.pr.tr.valor + "M, por isso deve ser titular");
  } else if (x.pr.xmin >= 70) {
    partes.push("é titular certo (~" + Math.round(x.pr.xmin) + " min por jogo)");
  } else {
    partes.push("deve jogar cerca de " + Math.round(x.pr.xmin) + " min por jogo");
  }
  const bp = bolaParadaDe(x.p);
  if (bp && bp.pen === 1) partes.push("bate os penáltis da equipa");
  else if (bp && (bp.fk === 1 || bp.cantos === 1)) partes.push("é ele que bate as bolas paradas");
  partes.push("vale " + x.pr.pp90.toFixed(1) + " pts por 90 min");
  const cal = calendario(x.pr);
  if (cal) partes.push(cal);
  return partes.join(", ");
}

/* --- Utilização real nas jornadas já disputadas --- */

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

/**
 * Com a jornada a meio, uns jogadores já têm mais um jogo de informação do que
 * outros — e é aí que as sugestões são menos de fiar. Diz quantas equipas já
 * jogaram em vez de deixar isso escondido no modelo.
 */
function avisoJornadaACorrer() {
  const alvo = $("sug-jornada");
  if (!alvo) return;
  const eventos = Object.keys(D.jornadas || {}).map(Number).sort((a, b) => a - b);
  const ev = eventos[eventos.length - 1];
  const j = ev ? D.jornadas[ev] : null;
  const jogaram = j && !j.finalizada ? (j.equipas || []).length : 0;
  const total = (D.teams || []).length || 20;
  alvo.hidden = !jogaram || jogaram >= total;
  if (alvo.hidden) return;
  alvo.textContent = "Jornada " + ev + " a decorrer: " + jogaram + " de " + total +
    " equipas já jogaram. Quem já entrou em campo tem mais um jogo de informação " +
    "do que os outros, por isso as sugestões só ficam comparáveis no fim da jornada.";
}

function initSugestoes() {
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  if (!eu) { $("sug-contexto").textContent = "Não encontrei a tua equipa na liga."; return; }
  const meusX = comProjecao(D.players.filter((p) => p.owner === eu.entry_id));
  desenharOnze(meusX);
  desenharProximosJogos(meusX);
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
  // A fila de waivers e os movimentos da liga são do Draft; na clássica não
  // existem, e a frase antiga falava deles nos dois modos.
  partes.push("és o #" + (eu.waiver_pick ?? "?") + " na fila de waivers");
  const movs = (D.mercado && D.mercado.transacoes ? D.mercado.transacoes : [])
    .filter((t) => t.result === "a").length;
  if (movs) partes.push(movs + " movimentos recentes na liga");
  $("sug-contexto").textContent = partes.join(" · ") + ".";

  avisoJornadaACorrer();

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
      const explicacao = "<strong>" + esc(s.meu.p.web_name) + "</strong> " +
        porqueSai(s.meu, s.livre) +
        ". <strong>" + esc(s.livre.p.web_name) + "</strong> " + porqueEntra(s.livre) +
        ". A troca vale mais <strong>" + s.ganho.toFixed(1) +
        " pontos por jornada</strong> (" + s.ganhoCal.toFixed(1) +
        " com o calendário das próximas " + janelaAtual() + ").";
      return "<li>" +
        '<div class="troca-linha"><span class="sai">Sai</span> ' + etiquetaJogador(s.meu) + "</div>" +
        '<div class="troca-linha"><span class="entra">Entra</span> ' + etiquetaJogador(s.livre) + "</div>" +
        '<p class="porque">' + explicacao + "</p>" + aviso +
      "</li>";
    }).join("");
  }

  // --- Trocas ---
  // Só existem no Draft; na clássica seriam 119 mil combinações para nada.
  const trocas = ehClassica() ? [] : sugestoesTrocas(meusX, eu);
  if (trocas.length === 0) {
    $("nota-sug-trocas").hidden = false;
  } else {
    $("sug-trocas").innerHTML = trocas.map((t) => {
      const lista = (grupo) => grupo.map(etiquetaJogador).join("");
      // "A, B e C", não "A e B e C".
      const nomes = (grupo) => {
        const n = grupo.map((x) => "<strong>" + esc(x.p.web_name) + "</strong>");
        return n.length <= 1 ? (n[0] || "")
          : n.slice(0, -1).join(", ") + " e " + n[n.length - 1];
      };

      // Numa troca de um só, o motivo do jogador é o que interessa; em várias,
      // o que interessa é o balanço e quem é que lá vai a adoçar.
      const ganhas = t.n === 1
        ? "Ganhas porque " + nomes(t.entram) + " " + porqueEntra(t.entram[0]) +
          ", enquanto " + nomes(t.saem) + " " + porqueSai(t.saem[0], t.entram[0]) +
          " — o teu onze sobe <strong>" + t.ganhoMeu.toFixed(1) + " pontos por jornada</strong>."
        : "O teu onze sobe <strong>" + t.ganhoMeu.toFixed(1) + " pontos por jornada</strong>: " +
          "entram " + nomes(t.entram) + " e saem " + nomes(t.saem) + "." +
          (t.adocantes.length
            ? " " + nomes(t.adocantes) + (t.adocantes.length === 1 ? " não entra" : " não entram") +
              " no teu onze, por isso " + (t.adocantes.length === 1 ? "vai" : "vão") +
              " no negócio sem te custar pontos."
            : "");

      const cartazMeu = t.saem.reduce((v, x) => v + pontosEpocaPassada(x.p), 0);
      const cartazDele = t.entram.reduce((v, x) => v + pontosEpocaPassada(x.p), 0);
      const aceita = t.tipo === "ambos"
        ? " Ele também tem interesse: o onze dele sobe " + t.ganhoDeles.toFixed(1) +
          " pontos, porque " + nomes(t.saem) + " encaixa melhor no plantel dele."
        : " Ele recebe mais do que dá — <strong>" + t.dou.toFixed(1) + "</strong> contra " +
          t.recebo.toFixed(1) + " pts/jornada em valor de plantel" +
          (cartazMeu > cartazDele
            ? ", e ainda os nomes maiores (" + cartazMeu + " contra " + cartazDele +
              " pontos na época passada)"
            : "") +
          ". O onze dele não melhora (" + t.ganhoDeles.toFixed(1) + "), por isso é a ti que " +
          "esta troca serve: o argumento é a qualidade a mais que lhe dás.";

      // Um jogador que não pode jogar ocupa uma das 15 vagas e não pontua: o
      // onze melhora na mesma, mas ficas com menos cobertura. Uma dúvida de
      // 75% não conta — esses jogam quase sempre; só abaixo de metade.
      const problemas = t.entram.filter((x) => indisponivel(x.p) ||
        (x.p.status === "d" && (x.p.chance_of_playing_next_round ?? 100) <= 50));
      const alerta = problemas.length
        ? '<p class="aviso-sug">⚠ ' + problemas.map((x) => esc(x.p.web_name) + " (" +
            estadoDe(x.p).rotulo.toLowerCase() + ")").join(", ") +
          (problemas.length === 1 ? " entra" : " entram") + " sem poder jogar: ocupa" +
          (problemas.length === 1 ? "" : "m") + " vaga no plantel e não pontua" +
          (problemas.length === 1 ? "" : "m") + ".</p>"
        : "";

      return '<li class="' + t.tipo + '">' + alerta +
        '<p class="alvo">Propor a <strong>' + esc(t.outro.entry_name) + "</strong> (" +
          esc(t.outro.manager) + ")" +
          (t.n > 1 ? ' <span class="estado warn">' + t.n + "-por-" + t.n + "</span>" : "") +
        "</p>" +
        '<div class="troca-linha"><span class="sai">Dás</span> ' + lista(t.saem) + "</div>" +
        '<div class="troca-linha"><span class="entra">Recebes</span> ' + lista(t.entram) + "</div>" +
        '<p class="porque">' + ganhas + aceita + "</p>" +
      "</li>";
    }).join("");
  }
}

/** Estado da última recolha e aviso quando os dados já não servem. */
function initDiagnostico() {
  const fontes = D.diagnostico || [];
  if (fontes.length) {
    $("estado-fontes").innerHTML = "Fontes: " + fontes.map((f) =>
      '<span class="fonte ' + (f.ok ? "ok" : "falhou") + '" title="' + esc(f.detalhe) + '">' +
      (f.ok ? "✓ " : "✗ ") + esc(f.fonte) + "</span>").join(" · ");
  }

  const gerado = new Date(D.generated_at);
  const horas = (Date.now() - gerado) / 36e5;
  const deadline = D.next_event ? new Date(D.next_event.deadline_time) : null;
  // Recolha feita antes de um deadline que já passou: as escolhas mudaram desde então.
  const passouDeadline = deadline && Date.now() > deadline && gerado < deadline;
  if (!passouDeadline && horas < 12) return;

  $("aviso-velho").innerHTML = passouDeadline
    ? "⚠ Estes dados foram recolhidos antes do deadline da " + esc(D.next_event.name) +
      ", que já passou. Corre o <strong>atualizar.cmd</strong> para veres a jornada atual."
    : "⚠ Dados com " + Math.round(horas) + " horas. Corre o <strong>atualizar.cmd</strong> " +
      "para atualizar lesões, notícias e escolhas da liga.";
  $("aviso-velho").hidden = false;
}

/* ---------- Precisão do modelo ---------- */

// O site é estático e não escreve ficheiros, e o modelo vive aqui no browser:
// por isso é o próprio browser que guarda o que projetou, antes de a jornada
// ser jogada. Sem isto não há como saber se o modelo acerta.
const CHAVE_PROJ = "proj";

function chaveProjecoes(evento) {
  return CHAVE_PROJ + ":" + D.league_id + ":" + evento;
}

function lerGuardado(chave) {
  try {
    const txt = localStorage.getItem(chave);
    return txt ? JSON.parse(txt) : null;
  } catch (err) {
    return null; // localStorage pode estar bloqueado; a app segue sem histórico
  }
}

/** Congela as projeções da jornada por disputar, uma só vez. */
function guardarProjecoes() {
  const ev = D.next_event && D.next_event.id;
  if (!ev) return;
  const jornada = (D.jornadas || {})[String(ev)];
  if (jornada && jornada.finalizada) return; // já foi jogada
  const chave = chaveProjecoes(ev);
  if (lerGuardado(chave)) return;

  const valores = {};
  D.players.filter((p) => p.owner != null).forEach((p) => {
    valores[p.id] = Math.round(projecao(p).ppj * 100) / 100;
  });
  try {
    localStorage.setItem(chave, JSON.stringify({
      gravado: new Date().toISOString(),
      evento: ev,
      valores,
    }));
  } catch (err) {
    /* sem espaço ou bloqueado: não é crítico */
  }
}

/** Compara o que foi projetado com o que aconteceu, jornada a jornada. */
function avaliarPrecisao() {
  const linhas = [];
  Object.keys(D.jornadas || {}).map(Number).sort((a, b) => a - b).forEach((ev) => {
    const jornada = D.jornadas[String(ev)];
    if (!jornada.finalizada) return;
    const guardado = lerGuardado(chaveProjecoes(ev));
    if (!guardado) return;

    const casos = [];
    Object.entries(guardado.valores).forEach(([id, projetado]) => {
      const p = jogadoresPorId[Number(id)];
      if (!p) return;
      const equipas = jornada.equipas || [];
      if (equipas.length && !equipas.includes(p.team)) return; // jornada em branco
      const real = (jornada.stats[id] || [0, 0])[1];
      casos.push({ p, projetado, real, erro: real - projetado });
    });
    if (casos.length === 0) return;

    const erroAbs = casos.reduce((s, c) => s + Math.abs(c.erro), 0) / casos.length;
    const vies = casos.reduce((s, c) => s + c.erro, 0) / casos.length;
    linhas.push({ evento: ev, casos, erroAbs, vies });
  });
  return linhas;
}

function desenharPrecisao() {
  const linhas = avaliarPrecisao();
  if (linhas.length === 0) { $("nota-precisao").hidden = false; return; }

  const total = linhas.reduce((s, l) => s + l.erroAbs * l.casos.length, 0) /
    linhas.reduce((s, l) => s + l.casos.length, 0);
  $("precisao-resumo").textContent = "erro médio de " + total.toFixed(1) + " pts por jogador";

  const ultima = linhas[linhas.length - 1];
  const ordenados = ultima.casos.slice().sort((a, b) => b.erro - a.erro);
  const destaque = (c) => "<li><strong>" + esc(c.p.web_name) + "</strong> (" +
    nomeClube(c.p.team) + "): projetado " + c.projetado.toFixed(1) + ", fez " + c.real +
    " (" + sinal(c.erro) + ")</li>";

  $("precisao-corpo").innerHTML =
    '<table class="tabela tabela-proj"><thead><tr><th>Jornada</th>' +
      '<th class="num">Jogadores</th><th class="num">Erro médio</th><th class="num">Viés</th>' +
      "</tr></thead><tbody>" +
      linhas.map((l) => "<tr><td>GW" + l.evento + "</td>" +
        '<td class="num">' + l.casos.length + "</td>" +
        '<td class="num forte">' + l.erroAbs.toFixed(1) + "</td>" +
        '<td class="num">' + sinal(l.vies) + "</td></tr>").join("") +
    "</tbody></table>" +
    '<p class="nota">Viés positivo significa que o modelo ficou aquém do que aconteceu; ' +
      "negativo, que foi otimista.</p>" +
    '<h4 class="sub-titulo">Maiores desvios na GW' + ultima.evento + "</h4>" +
    '<ul class="detalhe-troca">' +
      ordenados.slice(0, 3).map(destaque).join("") +
      ordenados.slice(-3).reverse().map(destaque).join("") +
    "</ul>";
}

/* ---------- Modo de jogo: Draft ou FPL clássica ---------- */

const MODOS = { draft: "data/data.json", classica: "data/classica.json" };

function modoAtual() {
  const m = lerGuardado("modo");
  return MODOS[m] ? m : "draft";
}

function aplicarModo(modo) {
  document.body.dataset.modo = modo;
  document.querySelectorAll("[data-modo]").forEach((el) => {
    el.hidden = el.dataset.modo !== modo;
  });
  $("modo-draft").setAttribute("aria-pressed", String(modo === "draft"));
  $("modo-classica").setAttribute("aria-pressed", String(modo === "classica"));
}

function initSeletorModo() {
  const trocar = (modo) => {
    if (modo === modoAtual()) return;
    try {
      localStorage.setItem("modo", JSON.stringify(modo));
    } catch (err) { /* segue sem guardar */ }
    location.reload();
  };
  $("modo-draft").addEventListener("click", () => trocar("draft"));
  $("modo-classica").addEventListener("click", () => trocar("classica"));
}

/* --- Mini-liga da FPL clássica --- */

function ligaClassica() {
  return ((D.classica || {}).liga) || null;
}

function initLigaClassica() {
  const liga = ligaClassica();
  if (!liga) return;
  const eu = (minhaEquipaClassica() || {}).id;
  $("titulo-liga").textContent = liga.nome;

  $("tabela-liga").querySelector("tbody").innerHTML = liga.participantes.map((p) =>
    '<tr class="' + (p.entry === eu ? "eu" : "") + '">' +
      '<td class="num">' + (p.rank ?? "–") + "</td>" +
      "<td>" + esc(p.nome) + (p.entry === eu ? " ★" : "") +
        '<span class="sub">' + esc(p.gestor) +
        (p.capitao && jogadoresPorId[p.capitao]
          ? " · capitão: " + esc(jogadoresPorId[p.capitao].web_name) : "") + "</span></td>" +
      '<td class="num">' + (p.jornada ?? "–") + "</td>" +
      '<td class="num forte">' + (p.total ?? 0) + "</td>" +
    "</tr>").join("");
  $("nota-liga").hidden = true;
}

/** Quantas equipas da liga têm cada jogador. */
function posseNaLiga() {
  const liga = ligaClassica();
  const conta = {};
  if (!liga) return conta;
  liga.participantes.forEach((p) => {
    (p.picks || []).forEach((id) => { conta[id] = (conta[id] || 0) + 1; });
  });
  return conta;
}

/**
 * Numa mini-liga o que conta é a diferença para os outros, não os pontos
 * absolutos: um jogador que todos têm nunca te faz ganhar terreno, e um que
 * só tu tens é onde a liga se decide — para os dois lados.
 */
function initEquipasClassica() {
  const liga = ligaClassica();
  if (!liga) return;
  const eu = (minhaEquipaClassica() || {}).id;
  const posse = posseNaLiga();
  const total = liga.participantes.length;
  const meu = liga.participantes.find((p) => p.entry === eu);

  let destaque = "";
  if (meu) {
    const comProj = (ids) => ids.map((id) => jogadoresPorId[id]).filter(Boolean)
      .map((p) => ({ p, pr: projecao(p) }))
      .sort((a, b) => b.pr.ppjCal - a.pr.ppjCal);
    const soMeus = comProj(meu.picks.filter((id) => posse[id] === 1));
    const emFalta = comProj(Object.keys(posse).map(Number)
      .filter((id) => posse[id] === total - 1 && !meu.picks.includes(id)));

    const lista = (arr) => arr.slice(0, 8).map((x) =>
      esc(x.p.web_name) + " (" + nomeClube(x.p.team) + " · " +
      x.pr.ppjCal.toFixed(1) + ")").join(" · ") || "nenhum";

    destaque =
      '<div class="veredicto ' + (emFalta.length ? "warn" : "ok") + '">' +
        "<p><strong>Só tu tens (" + soMeus.length + "):</strong> " + lista(soMeus) +
        ". É aqui que ganhas ou perdes a liga.</p>" +
        (emFalta.length
          ? "<p><strong>Todos os outros têm e tu não (" + emFalta.length + "):</strong> " +
            lista(emFalta) + ". Cada ponto que fizerem é terreno perdido para todos ao mesmo " +
            "tempo — é o risco mais caro numa liga pequena.</p>"
          : "") +
      "</div>";
  }

  $("cartoes-equipas").innerHTML = destaque + liga.participantes.map((p) => {
    const plantel = (p.picks || []).map((id) => jogadoresPorId[id]).filter(Boolean);
    const titulares = new Set(p.titulares || []);
    const porPos = { 1: [], 2: [], 3: [], 4: [] };
    plantel.forEach((j) => porPos[j.element_type].push(j));
    const corpo = [1, 2, 3, 4].map((pos) => {
      if (porPos[pos].length === 0) return "";
      const linhas = porPos[pos]
        .sort((a, b) => projecao(b).ppjCal - projecao(a).ppjCal)
        .map((j) => {
          const n = posse[j.id] || 0;
          const partilha = n === total ? "toda a liga" : n === 1 ? "só ele" : n + " equipas";
          return '<li><div class="linha">' +
            '<span class="nome">' + esc(j.web_name) + (j.id === p.capitao ? " (C)" : "") + "</span>" +
            '<span class="clube">' + nomeClube(j.team) +
              (titulares.size && !titulares.has(j.id) ? " · banco" : "") + "</span>" +
            '<span class="pts">' + partilha + "</span></div></li>";
        }).join("");
      return '<section class="grupo-pos"><h3>' + POS_NOMES[pos] + " (" + porPos[pos].length +
        ')</h3><ul class="lista-jog">' + linhas + "</ul></section>";
    }).join("");

    return "<details class=\"cartao\"" + (p.entry === eu ? " open" : "") + ">" +
      "<summary>" +
        '<span class="nome">' + esc(p.nome) + (p.entry === eu ? " ★" : "") + "</span>" +
        '<span class="clube">' + esc(p.gestor) + " · " + (p.total ?? 0) + " pts</span>" +
        '<span class="badges"><span class="estado ok">' + (p.rank ?? "–") + "º</span></span>" +
      "</summary>" +
      '<div class="corpo">' + (corpo || '<p class="nota">Sem escolhas nesta jornada.</p>') +
      "</div></details>";
  }).join("");
}

/* ---------- Sugestões da FPL clássica ---------- */

function ehClassica() {
  return (D.modo || "draft") === "classica";
}

function precoDe(p) {
  return (p.now_cost || 0) / 10;
}

/* --- O plantel que a API não publica --- */

// A FPL só torna a equipa pública depois do deadline: até lá as escolhas
// devolvidas são as da jornada anterior, sem as transferências nem o wildcard
// desta. Sugerir capitão e trocas sobre um plantel que já não existe não ajuda
// ninguém, e não há forma de o ir buscar sem sessão iniciada — mas o utilizador
// sabe qual é. Isto deixa-o dizê-lo, e passa a ser essa a base de tudo.
let meuPlantel = null; // { ids, banco, jornada } ou null

function chavePlantel() {
  return "plantel:" + ((((D.classica || {}).equipa) || {}).id || "0");
}

/** Lê o plantel indicado à mão, descartando-o quando a API já o alcançou. */
function lerPlantelManual() {
  let g = null;
  try { g = JSON.parse(localStorage.getItem(chavePlantel()) || "null"); } catch (e) { g = null; }
  if (!g || !Array.isArray(g.ids) || !g.ids.length) return null;
  // Assim que a FPL publica a jornada para a qual isto foi escrito, a fonte
  // oficial passa a saber mais do que a memória: o manual deixa de valer.
  const oficial = (((D.classica || {}).equipa) || {}).jornada_picks;
  if (oficial && g.jornada && oficial >= g.jornada) {
    try { localStorage.removeItem(chavePlantel()); } catch (e) { /* nada a fazer */ }
    return null;
  }
  return g;
}

function guardarPlantelManual() {
  try {
    if (meuPlantel && meuPlantel.ids.length) {
      localStorage.setItem(chavePlantel(), JSON.stringify(meuPlantel));
    } else {
      localStorage.removeItem(chavePlantel());
    }
  } catch (e) { /* modo privado: vale só nesta sessão */ }
}

/**
 * Um plantel só substitui o oficial quando está completo e legal — a meio
 * daria sugestões de transferência sobre posições por preencher.
 */
function validarPlantel(ids) {
  const jogadores = (ids || []).map((id) => jogadoresPorId[id]).filter(Boolean);
  const conta = { 1: 0, 2: 0, 3: 0, 4: 0 };
  const clubes = {};
  jogadores.forEach((p) => {
    conta[p.element_type] += 1;
    clubes[p.team] = (clubes[p.team] || 0) + 1;
  });
  const aMais = [1, 2, 3, 4].filter((pos) => conta[pos] > NO_PLANTEL[pos])
    .map((pos) => conta[pos] + " " + POSICOES[pos] + " (só cabem " + NO_PLANTEL[pos] + ")");
  const clubeCheio = Object.keys(clubes)
    .filter((t) => clubes[t] > (((D.regras || {}).squad || {}).team_limit || 3))
    .map((t) => clubes[t] + " do " + nomeClube(Number(t)));
  if (aMais.length || clubeCheio.length) {
    return { ok: false, erro: "Tens " + aMais.concat(clubeCheio).join(" e ") + "." };
  }
  const falta = [1, 2, 3, 4].filter((pos) => conta[pos] < NO_PLANTEL[pos])
    .map((pos) => (NO_PLANTEL[pos] - conta[pos]) + " " + POSICOES[pos]);
  return { ok: falta.length === 0, falta: falta, conta: conta };
}

function minhaEquipaClassica() {
  const eq = ((D.classica || {}).equipa) || null;
  if (!eq || !meuPlantel || !validarPlantel(meuPlantel.ids).ok) return eq;
  return Object.assign({}, eq, {
    picks: meuPlantel.ids.map((id, i) => ({ id: id, posicao: i + 1, multiplicador: 1 })),
    banco: meuPlantel.banco != null ? meuPlantel.banco : eq.banco,
    valor: meuPlantel.ids.reduce((t, id) => t + precoDe(jogadoresPorId[id] || {}), 0),
    // O capitão da jornada passada não diz nada do plantel novo, e mantê-lo
    // seria dar por feita uma escolha que ainda está por fazer.
    capitao: null,
    vice: null,
    jornada_picks: meuPlantel.jornada,
    manual: true,
  });
}

/**
 * O resto do site descobre os meus jogadores por `owner` — é assim nos dois
 * modos. Reescrever o dono é o que faz o onze, os próximos jogos, a utilização
 * e as sugestões seguirem o plantel indicado, sem cada um ter de saber dele.
 */
function aplicarPlantelManual() {
  if (!ehClassica()) return;
  const eq = ((D.classica || {}).equipa) || null;
  if (!eq) return;
  const usar = meuPlantel && validarPlantel(meuPlantel.ids).ok;
  const meus = new Set(usar ? meuPlantel.ids : ((eq.picks || []).map((x) => x.id)));
  D.players.forEach((p) => { p.owner = meus.has(p.id) ? eq.id : null; });
}

/** Os meus, já com projeção, seja o plantel o da FPL ou o indicado por mim. */
function meusDaClassica() {
  const equipa = minhaEquipaClassica();
  const ids = new Set((((equipa || {}).picks) || []).map((x) => x.id));
  return comProjecao(D.players.filter((p) => ids.has(p.id)));
}

function desenharMeuPlantel() {
  const alvo = $("meu-lista");
  if (!alvo) return;
  const ids = (meuPlantel && meuPlantel.ids) || [];
  const jogadores = ids.map((id) => jogadoresPorId[id]).filter(Boolean);
  const val = validarPlantel(ids);

  alvo.innerHTML = jogadores.length === 0
    ? '<span class="sub">Sem jogadores: valem as escolhas que a FPL publica.</span>'
    : jogadores
      .slice()
      .sort((a, b) => a.element_type - b.element_type || precoDe(b) - precoDe(a))
      .map((p) => '<span class="chip">' +
        '<span class="chip-nome">' + esc(p.web_name) + "</span>" +
        '<span class="chip-info">' + (POSICOES[p.element_type] || "?") + " · " +
          nomeClube(p.team) + " · " + precoDe(p).toFixed(1) + "M</span>" +
        '<button type="button" class="tirar" data-id="' + p.id +
          '" aria-label="Tirar ' + esc(p.web_name) + '">×</button>' +
      "</span>").join("");

  const custo = jogadores.reduce((t, p) => t + precoDe(p), 0);
  const estado = $("meu-estado");
  if (estado) {
    estado.textContent = ids.length === 0
      ? ""
      : ids.length + "/" + NO_PLANTEL_TOTAL + (val.ok ? " · a valer" : "");
  }
  const falta = $("meu-falta");
  if (falta) {
    falta.textContent = ids.length === 0
      ? ""
      : val.erro
        ? val.erro
        : val.ok
          ? "Plantel completo (" + custo.toFixed(1) +
            "M): o capitão, as transferências e os chips acima já são sobre estes 15."
          : "Faltam " + val.falta.join(", ") + ". Enquanto não estiver completo, as " +
            "sugestões continuam a usar o plantel que a FPL publica.";
    falta.className = "nota" + (val.erro ? " aviso-sug" : "");
  }
}

function initMeuPlantel() {
  const form = $("form-meu");
  if (!form) return;
  const procura = $("meu-procura");
  const banco = $("meu-banco");
  const bloco = $("bloco-meu-plantel");
  $("meu-sugestoes").innerHTML = D.players.filter((p) => p.now_cost)
    .map((p) => '<option value="' + esc(p.web_name) + " · " + nomeClube(p.team) + '">')
    .join("");

  // Só se abre sozinho quando há mesmo um problema a resolver: o plantel
  // publicado é de uma jornada anterior e ainda não foi corrigido.
  const eq = ((D.classica || {}).equipa) || {};
  const proxima = (D.next_event || {}).id;
  if (bloco && !meuPlantel && eq.jornada_picks && proxima && eq.jornada_picks < proxima) {
    bloco.open = true;
  }
  if (banco && meuPlantel && meuPlantel.banco != null) banco.value = meuPlantel.banco;

  const garantir = () => {
    if (!meuPlantel) {
      meuPlantel = { ids: [], banco: null, jornada: (D.next_event || {}).id || 0 };
    }
    return meuPlantel;
  };
  const redesenhar = () => {
    guardarPlantelManual();
    aplicarPlantelManual();
    desenharMeuPlantel();
    initSugestoes();
    desenharClassica();
  };

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const alvo = semAcentos(procura.value.split("·")[0].trim());
    if (!alvo) return;
    const achado = D.players.find((p) => semAcentos(p.web_name) === alvo && p.now_cost) ||
      D.players.find((p) => semAcentos(p.web_name).indexOf(alvo) >= 0 && p.now_cost);
    if (achado && !garantir().ids.includes(achado.id)) meuPlantel.ids.push(achado.id);
    procura.value = "";
    redesenhar();
  });
  $("meu-lista").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-id]");
    if (!b || !meuPlantel) return;
    meuPlantel.ids = meuPlantel.ids.filter((id) => id !== Number(b.dataset.id));
    if (!meuPlantel.ids.length) meuPlantel = null;
    redesenhar();
  });
  $("meu-copiar").addEventListener("click", () => {
    // Corrigir duas ou três posições é mais rápido do que escrever quinze.
    garantir().ids = ((((D.classica || {}).equipa) || {}).picks || []).map((x) => x.id);
    redesenhar();
  });
  $("meu-repor").addEventListener("click", () => {
    meuPlantel = null;
    if (banco) banco.value = "";
    redesenhar();
  });
  if (banco) {
    banco.addEventListener("change", () => {
      const v = parseFloat(banco.value);
      garantir().banco = isNaN(v) ? null : v;
      redesenhar();
    });
  }
  desenharMeuPlantel();
}

/** Capitão: o dobro dos pontos de um jogador é o maior salto da jornada. */
function desenharCapitao(meusX) {
  const equipa = minhaEquipaClassica();
  const universo = meusX.length
    ? meusX
    : comProjecao(D.players.filter((p) => !indisponivel(p)));
  const candidatos = universo.slice().sort((a, b) => b.pr.ppjCal - a.pr.ppjCal).slice(0, 5);
  if (candidatos.length === 0) return;

  const melhor = candidatos[0];
  $("cap-resumo").textContent = meusX.length
    ? "do teu plantel" : "de toda a Premier League (sem a tua equipa carregada)";

  $("cap-lista").innerHTML =
    '<div class="veredicto ok"><p>Capitão sugerido: <strong>' + esc(melhor.p.web_name) +
      "</strong> (" + nomeClube(melhor.p.team) + ") — projeta " + melhor.pr.ppjCal.toFixed(1) +
      " pts, <strong>" + (melhor.pr.ppjCal * 2).toFixed(1) + " com a braçadeira</strong>. " +
      esc(porqueEntra(melhor)) + ".</p></div>" +
    '<table class="tabela tabela-proj"><thead><tr><th>Candidato</th>' +
      '<th class="num">Pts/J</th><th class="num">Como capitão</th>' +
      '<th class="num">Ganho</th></tr></thead><tbody>' +
      candidatos.map((x) => "<tr><td>" + esc(x.p.web_name) +
        '<span class="sub">' + nomeClube(x.p.team) + " · " +
          (POSICOES[x.p.element_type] || "?") +
          (equipa && equipa.capitao === x.p.id ? " · capitão atual" : "") + "</span></td>" +
        '<td class="num">' + x.pr.ppjCal.toFixed(1) + "</td>" +
        '<td class="num forte">' + (x.pr.ppjCal * 2).toFixed(1) + "</td>" +
        '<td class="num">' + sinal(x.pr.ppjCal) + "</td></tr>").join("") +
    "</tbody></table>";
}

/**
 * Transferências: só compensam se pagarem o que custam.
 *
 * A troca tem de caber no dinheiro disponível, respeitar o limite de jogadores
 * por clube e, se gastar mais do que as transferências livres, render mais do
 * que os 4 pontos da penalização.
 */
/**
 * As melhores trocas possíveis, emparelhadas guloso (cada jogador entra ou sai
 * uma vez só). Respeita o orçamento, a posição e o máximo por clube. Serve as
 * sugestões de transferência e a decisão do wildcard, que é a mesma pergunta
 * feita em bloco.
 */
function melhoresTransferencias(meusX, maximo) {
  const equipa = minhaEquipaClassica();
  if (!equipa || meusX.length === 0) return [];
  const limiteClube = ((D.regras || {}).squad || {}).team_limit || 3;
  const banco = equipa.banco || 0;
  const porClube = {};
  meusX.forEach((x) => { porClube[x.p.team] = (porClube[x.p.team] || 0) + 1; });

  const candidatos = comProjecao(D.players.filter((p) =>
    !meusX.some((x) => x.p.id === p.id) && !indisponivel(p) && p.now_cost));

  const ideias = [];
  meusX.forEach((meu) => {
    const orcamento = banco + precoDe(meu.p);
    candidatos
      .filter((c) => c.p.element_type === meu.p.element_type)
      .filter((c) => precoDe(c.p) <= orcamento + 1e-9)
      .filter((c) => c.p.team === meu.p.team || (porClube[c.p.team] || 0) < limiteClube)
      .forEach((c) => {
        const ganho = c.pr.ppjCal - meu.pr.ppjCal;
        if (ganho > 0.2) {
          ideias.push({ meu, entra: c, ganho, sobra: orcamento - precoDe(c.p) });
        }
      });
  });
  ideias.sort((a, b) => b.ganho - a.ganho);

  const usados = new Set();
  const escolhidas = [];
  ideias.forEach((i) => {
    if (usados.has(i.meu.p.id) || usados.has(i.entra.p.id) ||
        escolhidas.length >= maximo) return;
    usados.add(i.meu.p.id);
    usados.add(i.entra.p.id);
    escolhidas.push(i);
  });
  return escolhidas;
}

/**
 * Vale a pena gastar o wildcard nesta jornada?
 *
 * O wildcard não vale pelo plantel ideal que permite montar — esse está sempre
 * à frente do teu, porque o modelo tem opiniões e o plantel real tem história.
 * Vale pelos **−4 que evita**: com uma transferência livre por jornada, fazer N
 * mudanças de uma vez custa 4×(N−1) pontos. É isso que se mede aqui.
 *
 * Só contam as trocas que se pagariam a si próprias mesmo com a penalização
 * (ganho × janela ≥ 4): as outras não seriam feitas de qualquer maneira, e
 * incluí-las inflacionaria o caso a favor do chip.
 */
function analiseWildcard(meusX) {
  const equipa = minhaEquipaClassica();
  const custo = (D.classica || {}).custo_transferencia || 4;
  if (!equipa || meusX.length === 0) return null;

  const livres = equipa.transferencias_livres != null ? equipa.transferencias_livres : 1;
  const janela = janelaAtual();
  const trocas = melhoresTransferencias(meusX, 10);
  const valem = trocas.filter((t) => t.ganho * janela >= custo);
  // O ganho conta-se **no onze**, não na soma das trocas: quatro das saídas
  // costumam ser do banco, e trocar quem não joga não dá pontos nenhuns.
  const depois = meusX.filter((x) => !valem.some((t) => t.meu.p.id === x.p.id))
    .concat(valem.map((t) => t.entra));
  const ganho = valorXI(depois) - valorXI(meusX);
  const penalizacao = Math.max(0, valem.length - livres) * custo;

  // Três condições: muitas mudanças a precisar de ser feitas, uma fatura de
  // penalizações que justifique queimar o chip, e um ganho no onze que a pague
  // dentro da janela (senão está-se a gastar o chip por causa do banco).
  const usar = valem.length >= 4 && penalizacao >= 2 * custo &&
    ganho * janela >= penalizacao;
  return { trocas: valem, quantas: valem.length, ganho, penalizacao, livres, janela, usar };
}

function desenharTransferencias(meusX) {
  const equipa = minhaEquipaClassica();
  const squad = (D.regras || {}).squad || {};
  const limiteClube = squad.team_limit || 3;
  const custo = (D.classica || {}).custo_transferencia || 4;

  if (!equipa || meusX.length === 0) {
    // Sem a equipa carregada: mostrar quem rende mais por milhão gasto.
    const valor = comProjecao(D.players.filter((p) => !indisponivel(p) && p.now_cost))
      .map((x) => ({ x, racio: x.pr.ppjCal / precoDe(x.p) }))
      .sort((a, b) => b.racio - a.racio)
      .slice(0, 12);
    $("tr-resumo").textContent = "sem a tua equipa: melhor relação pontos/preço";
    $("tr-lista").innerHTML =
      '<p class="nota">Define <code>FPL_ENTRY_ID</code> para veres sugestões para o teu ' +
        "plantel, com orçamento, limite de 3 por clube e o custo de −" + custo + " pontos.</p>" +
      '<table class="tabela tabela-proj"><thead><tr><th>Jogador</th><th class="num">Preço</th>' +
        '<th class="num">Pts/J</th><th class="num">Pts por milhão</th></tr></thead><tbody>' +
        valor.map(({ x, racio }) => "<tr><td>" + esc(x.p.web_name) +
          '<span class="sub">' + nomeClube(x.p.team) + " · " +
            (POSICOES[x.p.element_type] || "?") + "</span></td>" +
          '<td class="num">' + precoDe(x.p).toFixed(1) + "M</td>" +
          '<td class="num">' + x.pr.ppjCal.toFixed(1) + "</td>" +
          '<td class="num forte">' + racio.toFixed(2) + "</td></tr>").join("") +
      "</tbody></table>";
    return;
  }

  const banco = equipa.banco || 0;
  const livres = equipa.transferencias_livres != null ? equipa.transferencias_livres : 1;
  const escolhidas = melhoresTransferencias(meusX, 5);

  $("tr-resumo").textContent = banco.toFixed(1) + "M no banco · " + livres +
    " transferência" + (livres === 1 ? "" : "s") + " livre" + (livres === 1 ? "" : "s");

  if (escolhidas.length === 0) {
    $("tr-lista").innerHTML = '<p class="nota">Nenhuma transferência melhora o plantel ' +
      "o suficiente para valer a pena.</p>";
    return;
  }

  $("tr-lista").innerHTML = escolhidas.map((i, idx) => {
    const paga = idx < livres || i.ganho * 3 > custo; // 3 jornadas para pagar o hit
    const nota = idx < livres
      ? "Cabe nas transferências livres."
      : paga
        ? "Custa −" + custo + " pts, mas recupera-os em cerca de " +
          Math.ceil(custo / Math.max(i.ganho, 0.1)) + " jornadas."
        : "Não compensa pagar −" + custo + " pts por este ganho.";
    return '<li class="' + (paga ? "" : "cartaz") + '">' +
      '<div class="troca-linha"><span class="sai">Sai</span> ' + etiquetaJogador(i.meu) +
        ' <span class="clube">' + precoDe(i.meu.p).toFixed(1) + "M</span></div>" +
      '<div class="troca-linha"><span class="entra">Entra</span> ' + etiquetaJogador(i.entra) +
        ' <span class="clube">' + precoDe(i.entra.p).toFixed(1) + "M</span></div>" +
      '<p class="porque"><strong>' + esc(i.entra.p.web_name) + "</strong> " +
        esc(porqueEntra(i.entra)) + ". Ganhas <strong>" + i.ganho.toFixed(1) +
        " pts por jornada</strong> e sobram " + i.sobra.toFixed(1) + "M. " + nota + "</p>" +
    "</li>";
  }).join("");
  $("tr-lista").innerHTML = '<ul class="sugestoes">' + $("tr-lista").innerHTML + "</ul>";
}

/** Chips: quanto valeria usá-los nesta jornada. */
/**
 * Jornadas futuras em que os meus clubes jogam duas vezes ou nenhuma.
 *
 * **A jornada a decorrer fica de fora de propósito**: as fixtures só guardam
 * os jogos por disputar, por isso a meio de uma jornada os clubes que já
 * jogaram parecem estar em branco. Foi o que a GW2 mostrou — 18 "em branco"
 * que eram 18 jogos já realizados.
 */
function jornadasEspeciais(meusX) {
  const fx = D.fixtures || {};
  const atual = (D.game || {}).current_event || 0;
  const meusClubes = [...new Set(meusX.map((x) => x.p.team))];
  const porEvento = {};
  Object.keys(fx).forEach((tid) => {
    (fx[tid] || []).forEach((j) => {
      if (!j.event || j.event <= atual) return;
      const ev = (porEvento[j.event] = porEvento[j.event] || {});
      ev[tid] = (ev[tid] || 0) + 1;
    });
  });
  return Object.keys(porEvento).map(Number).sort((a, b) => a - b).map((ev) => {
    const conta = porEvento[ev];
    return {
      evento: ev,
      semJogo: meusClubes.filter((t) => !conta[String(t)]),
      duplas: meusClubes.filter((t) => (conta[String(t)] || 0) > 1),
    };
  });
}

/* --- Planeador do wildcard --- */

let wcFixos = [];

function desenharPlaneadorWC() {
  const meusX = meusDaClassica();
  const alvo = $("wc-plantel");
  if (!alvo) return;
  const fixos = wcFixos.map((id) => jogadoresPorId[id]).filter(Boolean);
  const comProj = comProjecao(fixos);

  $("wc-fixos").innerHTML = comProj.length === 0
    ? '<span class="sub">Sem escolhas tuas: o plantel abaixo é o que o modelo faria de raiz.</span>'
    : comProj.map((x) => '<span class="chip">' +
        '<span class="chip-nome">' + esc(x.p.web_name) + "</span>" +
        '<span class="chip-info">' + nomeClube(x.p.team) + " · " +
          precoDe(x.p).toFixed(1) + "M</span>" +
        '<button type="button" class="tirar" data-id="' + x.p.id +
          '" aria-label="Tirar ' + esc(x.p.web_name) + '">×</button>' +
      "</span>").join("");

  const melhor = melhorPlantelPossivel(comProj);
  $("wc-erro").hidden = !(melhor && melhor.erro);
  if (melhor && melhor.erro) {
    $("wc-erro").textContent = melhor.erro;
    alvo.innerHTML = "";
    $("wc-resumo").textContent = "";
    return;
  }
  if (!melhor) {
    alvo.innerHTML = '<p class="nota">Não consigo montar um plantel legal com essas escolhas.</p>';
    return;
  }

  const meus = new Set(meusX.map((x) => x.p.id));
  const mudam = melhor.escolhidos.filter((x) => !meus.has(x.p.id)).length;
  const agora = meusX.length ? valorXI(meusX) : 0;
  const sobe = melhor.pontos - agora;
  $("wc-resumo").textContent = melhor.formacao + " · " + melhor.custo.toFixed(1) + "M de " +
    (((D.regras || {}).squad || {}).total_spend / 10 || 100).toFixed(1) + "M";

  const chip = (x, novo) => '<span class="chip' + (novo ? " chip-novo" : "") + '">' +
    '<span class="chip-nome">' + esc(x.p.web_name) + "</span>" +
    '<span class="chip-info">' + nomeClube(x.p.team) + " · " +
      precoDe(x.p).toFixed(1) + "M · " + x.pr.ppjCal.toFixed(1) + "</span></span>";

  // Insistir em jogadores caros pode empurrar um deles para o banco: aí o
  // dinheiro fica parado, e isso não se vê olhando só para o onze.
  const noXI = new Set(melhor.xi.map((x) => x.p.id));
  const presosNoBanco = comProj.filter((x) => !noXI.has(x.p.id));
  const aviso = presosNoBanco.length
    ? '<p class="aviso-sug">⚠ ' +
      presosNoBanco.map((x) => esc(x.p.web_name) + " (" + precoDe(x.p).toFixed(1) + "M)")
        .join(", ") +
      (presosNoBanco.length === 1 ? " fica" : " ficam") + " no banco: com estas escolhas não " +
      "sobra orçamento para " + (presosNoBanco.length === 1 ? "o pôr" : "os pôr") +
      " no onze, e no banco não pontuam.</p>"
    : "";

  alvo.innerHTML = aviso +
    '<p class="veredicto ' + (sobe > 0 ? "ok" : "") + '">' +
      "Onze projeta <strong>" + melhor.pontos.toFixed(1) + " pts/jornada</strong>" +
      (meusX.length
        ? " — <strong>" + sinal(sobe) + "</strong> face ao teu de agora (" +
          agora.toFixed(1) + "). São <strong>" + mudam + "</strong> jogadores diferentes."
        : ".") +
      " Sobram " + (((D.regras || {}).squad || {}).total_spend / 10 - melhor.custo).toFixed(1) +
      "M." + "</p>" +
    '<div class="linha-campo">' + melhor.xi.map((x) => chip(x, !meus.has(x.p.id))).join("") +
    "</div>" +
    '<p class="nota"><strong>Suplentes:</strong> ' +
      melhor.banco.sort((a, b) => b.pr.ppjCal - a.pr.ppjCal)
        .map((x) => esc(x.p.web_name) + " (" + precoDe(x.p).toFixed(1) + "M)").join(" · ") +
    "</p>";
}

function initPlaneadorWC() {
  const form = $("form-wc");
  if (!form) return;
  const procura = $("wc-procura");
  // Sugestões por nome, para não ser preciso acertar na escrita exata.
  $("wc-sugestoes").innerHTML = D.players
    .filter((p) => p.now_cost && !indisponivel(p))
    .map((p) => '<option value="' + esc(p.web_name) + " · " + nomeClube(p.team) + '">')
    .join("");

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const alvo = semAcentos(procura.value.split("·")[0].trim());
    if (!alvo) return;
    const achado = D.players.find((p) => semAcentos(p.web_name) === alvo && p.now_cost) ||
      D.players.find((p) => semAcentos(p.web_name).indexOf(alvo) >= 0 && p.now_cost);
    if (achado && !wcFixos.includes(achado.id)) wcFixos.push(achado.id);
    procura.value = "";
    desenharPlaneadorWC();
  });
  $("wc-limpar").addEventListener("click", () => {
    wcFixos = [];
    desenharPlaneadorWC();
  });
  $("wc-fixos").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-id]");
    if (!b) return;
    wcFixos = wcFixos.filter((id) => id !== Number(b.dataset.id));
    desenharPlaneadorWC();
  });
  desenharPlaneadorWC();
}

function desenharChips(meusX) {
  const equipa = minhaEquipaClassica();
  const custoChip = (D.classica || {}).custo_transferencia || 4;
  const chips = (D.classica || {}).chips || [];
  const usados = new Set((equipa && equipa.chips_usados || []).map((c) => c.chip));
  const ev = D.next_event && D.next_event.id;
  const disponiveis = chips.filter((c) =>
    !usados.has(c.nome) && (!ev || (c.inicio <= ev && ev <= c.fim)));

  const xi = meusX.length ? melhorXI(meusX) : [];
  const banco = meusX.filter((x) => !xi.includes(x));
  const capitao = xi.slice().sort((a, b) => b.pr.ppjCal - a.pr.ppjCal)[0];
  const valorBanco = banco.reduce((s, x) => s + x.pr.ppjCal, 0);

  const especiais = jornadasEspeciais(meusX);
  const comDuplas = especiais.filter((e) => e.duplas.length);
  const ultimaConhecida = especiais.length ? especiais[especiais.length - 1].evento : "?";

  const explicar = (nome) => {
    if (nome === "bboost") {
      if (!meusX.length) return "Soma os pontos do banco. Guarda para uma jornada dupla.";
      const proxima = especiais[0];
      const bancoParado = proxima
        ? banco.filter((x) => proxima.semJogo.includes(x.p.team)).length : 0;
      if (comDuplas.length) {
        return "<strong>Aponta à jornada " + comDuplas[0].evento + "</strong>, em que " +
          comDuplas[0].duplas.length + " dos teus clubes jogam duas vezes — é aí que o " +
          "banco rende a dobrar. Hoje ele projeta " + valorBanco.toFixed(1) + " pts.";
      }
      return "<strong>Guarda-o.</strong> O teu banco projeta " + valorBanco.toFixed(1) +
        " pts" + (bancoParado ? " e " + bancoParado + " suplentes nem jogam na próxima" : "") +
        ". Não há jornadas duplas no calendário conhecido (até à " + ultimaConhecida +
        "), e é numa dupla que este chip vale o dobro.";
    }
    if (nome === "3xc") {
      if (!capitao) {
        return "Triplica o capitão: guarda para quem tenha jornada dupla e bom calendário.";
      }
      const dupla = comDuplas.find((e) => e.duplas.includes(capitao.p.team));
      if (dupla) {
        return "<strong>Aponta à jornada " + dupla.evento + "</strong>: o " +
          esc(capitao.p.web_name) + " joga duas vezes, que é exatamente onde este chip " +
          "vale o triplo do normal.";
      }
      const prox = (capitao.pr.jogos || [])[0];
      const facil = prox && prox.difficulty <= 2;
      return "<strong>" + (facil ? "Podes usá-lo já" : "Guarda-o") + ".</strong> O melhor " +
        "capitão é o " + esc(capitao.p.web_name) + ", que renderia mais " +
        capitao.pr.ppjCal.toFixed(1) + " pts do que com a braçadeira normal (" +
        (capitao.pr.ppjCal * 3).toFixed(1) + " no total)" +
        (prox ? ", contra o " + nomeClube(prox.opponent) + " (dificuldade " +
          prox.difficulty + ")" : "") +
        (facil ? "." : ". Sem jornada dupla à vista, vale mais esperar por uma.");
    }
    if (nome === "wildcard") {
      const w = analiseWildcard(meusX);
      if (!w) {
        return "Refaz o plantel sem custo. Usa quando tiveres várias transferências " +
          "necessárias ao mesmo tempo.";
      }
      const conta = w.quantas + " troca" + (w.quantas === 1 ? "" : "s") +
        " compensam nas próximas " + w.janela + " jornadas" +
        (w.quantas ? " (" + w.trocas.slice(0, 3).map((t) =>
          esc(t.meu.p.web_name) + "→" + esc(t.entra.p.web_name)).join(", ") +
          (w.quantas > 3 ? ", …" : "") + ")" : "");
      if (w.usar) {
        // Com as escolhas públicas atrasadas, a API ainda não diz que chips
        // foram gastos — mandar "usa" seria mandar usar de novo.
        return (plantelDesatualizado(equipa)
          ? "<strong>Se ainda não o usaste, é esta a jornada.</strong>"
          : "<strong>Usa nesta jornada.</strong>") + " " + conta + ", e o teu onze sobe " +
          w.ganho.toFixed(1) + " pts por jornada. Feitas à mão custariam −" + w.penalizacao +
          " pts de penalização (tens " + w.livres + " transferência" +
          (w.livres === 1 ? "" : "s") + " livre" + (w.livres === 1 ? "" : "s") +
          "); o wildcard faz as mesmas de graça. Conta com a projeção estar certa, " +
          "e o chip só se usa uma vez.";
      }
      if (w.quantas === 0) {
        return "<strong>Guarda-o.</strong> Nenhuma troca compensa a penalização de −" +
          custoChip + " pts agora, portanto não há nada que o wildcard resolva.";
      }
      const porque = w.quantas >= 4 && w.ganho * w.janela < w.penalizacao
        ? " As trocas que faltam são quase todas de banco, e o banco não pontua."
        : "";
      return "<strong>Guarda-o.</strong> Só " + conta + " — dá para as fazer com as " +
        "transferências livres" + (w.penalizacao ? " e −" + w.penalizacao + " pts" : "") +
        "." + porque + " O wildcard vale a pena quando forem quatro ou mais ao mesmo " +
        "tempo e o onze subir o suficiente para pagar as penalizações, ou quando uma " +
        "vaga de lesões te obrigar.";
    }
    if (nome === "freehit") {
      const pior = especiais.slice().sort((a, b) => b.semJogo.length - a.semJogo.length)[0];
      if (pior && pior.semJogo.length >= 4) {
        return "<strong>Guarda-o para a jornada " + pior.evento + "</strong>: " +
          pior.semJogo.length + " dos teus clubes não jogam (" +
          pior.semJogo.map(nomeClube).join(", ") + "), e sem chip ficavas a fazer " +
          "substituições a perder.";
      }
      if (comDuplas.length) {
        return "<strong>Guarda-o.</strong> A jornada " + comDuplas[0].evento +
          " tem duplas — um plantel montado só para ela pode render muito.";
      }
      const parados = pior ? pior.semJogo.length : 0;
      return "<strong>Guarda-o.</strong> Serve para uma jornada em que metade do teu plantel " +
        "não joga, e até à " + ultimaConhecida + " isso não acontece: " +
        (parados === 0
          ? "todos os teus clubes têm jogo em todas as jornadas conhecidas."
          : "no pior caso ficam " + parados + (parados === 1 ? " clube teu parado" : " clubes teus parados") +
            " (jornada " + pior.evento + "), o que se resolve com o banco.");
    }
    return "";
  };

  // A FPL só revela os chips gastos depois do deadline: enquanto as escolhas
  // públicas forem de uma jornada anterior, esta lista pode incluir um chip
  // que já foi usado.
  const nota = plantelDesatualizado(equipa)
    ? '<p class="nota">A FPL só revela os chips usados depois do deadline, por isso esta ' +
      "lista pode incluir algum que já tenhas gasto na jornada a seguir.</p>"
    : "";
  $("chips-lista").innerHTML = nota + (disponiveis.length === 0
    ? '<p class="nota">Sem chips disponíveis nesta janela.</p>'
    : '<ul class="sugestoes">' + disponiveis.map((c) =>
        "<li><p class=\"alvo\"><strong>" + nomeChip(c.nome) + "</strong> " +
          "(jornadas " + c.inicio + " a " + c.fim + ")</p>" +
          '<p class="porque">' + explicar(c.nome) + "</p></li>").join("") + "</ul>");
}

/* --- Melhor plantel possível dentro do orçamento (modo clássico) --- */

/**
 * Escolhe 15 jogadores dentro do orçamento, com 2 GR / 5 DEF / 5 MED / 3 AV e
 * no máximo 3 por clube, a maximizar os pontos do onze.
 *
 * O banco não pontua, por isso a estratégia é a que toda a gente usa: banco
 * barato para libertar dinheiro, e o dinheiro todo no onze. Para cada formação
 * válida começa-se pelo plantel mais barato e vai-se fazendo a melhoria que dá
 * mais pontos por milhão gasto, até o dinheiro acabar.
 */
const NO_PLANTEL = { 1: 2, 2: 5, 3: 5, 4: 3 };
const NO_PLANTEL_TOTAL = 15;

/**
 * O plantel de 15 que mais pontos projeta dentro do orçamento.
 *
 * `fixos` são jogadores que têm de lá estar — é o que permite planear um
 * wildcard à volta de quem queres ter. Ocupam vaga, contam para o limite de 3
 * por clube e para o orçamento, e o resto é construído em volta deles.
 */
function melhorPlantelPossivel(fixos) {
  const squad = (D.regras || {}).squad || {};
  const orcamento = (squad.total_spend || 1000) / 10;
  const limiteClube = squad.team_limit || 3;
  const lim = limitesXI();
  const presos = (fixos || []).slice();
  const idsPresos = new Set(presos.map((x) => x.p.id));

  const aptos = comProjecao(D.players.filter((p) =>
    p.now_cost && !indisponivel(p) && projecao(p).ppj > 0));
  const porPos = { 1: [], 2: [], 3: [], 4: [] };
  aptos.forEach((x) => { if (!idsPresos.has(x.p.id)) porPos[x.p.element_type].push(x); });
  [1, 2, 3, 4].forEach((pos) => porPos[pos].sort((a, b) => b.pr.ppjCal - a.pr.ppjCal));

  // Os fixos podem já não deixar plantel legal: posições a mais, clube a mais
  // ou dinheiro a menos. Melhor dizer porquê do que devolver um plantel errado.
  const contaFixos = { 1: 0, 2: 0, 3: 0, 4: 0 };
  const clubesFixos = {};
  presos.forEach((x) => {
    contaFixos[x.p.element_type] += 1;
    clubesFixos[x.p.team] = (clubesFixos[x.p.team] || 0) + 1;
  });
  const posCheia = [1, 2, 3, 4].find((pos) => contaFixos[pos] > NO_PLANTEL[pos]);
  if (posCheia) {
    return { erro: "Escolheste " + contaFixos[posCheia] + " " +
      (POSICOES[posCheia] || "?") + " e o plantel só leva " + NO_PLANTEL[posCheia] + "." };
  }
  const clubeCheio = Object.keys(clubesFixos).find((t) => clubesFixos[t] > limiteClube);
  if (clubeCheio) {
    return { erro: "Escolheste " + clubesFixos[clubeCheio] + " jogadores do " +
      nomeClube(Number(clubeCheio)) + " e o máximo é " + limiteClube + "." };
  }
  const custoFixos = presos.reduce((t, x) => t + precoDe(x.p), 0);
  if (custoFixos > orcamento + 1e-9) {
    return { erro: "Os jogadores escolhidos custam " + custoFixos.toFixed(1) +
      "M e o orçamento é " + orcamento.toFixed(1) + "M." };
  }
  if ([1, 2, 3, 4].some((pos) => porPos[pos].length + contaFixos[pos] < NO_PLANTEL[pos])) {
    return null;
  }

  let melhor = null;

  for (let def = lim[2][0]; def <= lim[2][1]; def += 1) {
    for (let med = lim[3][0]; med <= lim[3][1]; med += 1) {
      const av = 10 - def - med;
      if (av < lim[4][0] || av > lim[4][1]) continue;
      const noXI = { 1: 1, 2: def, 3: med, 4: av };

      // Base: os fixos primeiro, depois os mais baratos que cumprem as regras.
      const escolhidos = presos.slice();
      const clubes = {};
      presos.forEach((x) => { clubes[x.p.team] = (clubes[x.p.team] || 0) + 1; });
      const cabe = (x) => (clubes[x.p.team] || 0) < limiteClube;
      let ok = true;
      [1, 2, 3, 4].forEach((pos) => {
        const baratos = porPos[pos].slice().sort((a, b) => a.p.now_cost - b.p.now_cost);
        let postos = contaFixos[pos];
        for (const x of baratos) {
          if (postos >= NO_PLANTEL[pos]) break;
          if (!cabe(x)) continue;
          escolhidos.push(x);
          clubes[x.p.team] = (clubes[x.p.team] || 0) + 1;
          postos += 1;
        }
        if (postos < NO_PLANTEL[pos]) ok = false;
      });
      if (!ok) continue;

      let custo = escolhidos.reduce((s, x) => s + precoDe(x.p), 0);

      // Melhorias: a que render mais pontos por milhão, enquanto houver dinheiro.
      for (let passo = 0; passo < 60; passo += 1) {
        let melhorTroca = null;
        escolhidos.forEach((atual, i) => {
          if (idsPresos.has(atual.p.id)) return; // escolhido por ti: não se troca
          const pos = atual.p.element_type;
          const naPos = escolhidos.filter((x) => x.p.element_type === pos)
            .sort((a, b) => b.pr.ppjCal - a.pr.ppjCal);
          const titular = naPos.indexOf(atual) < noXI[pos];
          porPos[pos].forEach((cand) => {
            if (escolhidos.some((x) => x.p.id === cand.p.id)) return;
            const dCusto = precoDe(cand.p) - precoDe(atual.p);
            if (custo + dCusto > orcamento + 1e-9) return;
            const mesmoClube = cand.p.team === atual.p.team;
            if (!mesmoClube && (clubes[cand.p.team] || 0) >= limiteClube) return;
            // Um suplente só interessa se for barato; o valor está no onze.
            const dPontos = (cand.pr.ppjCal - atual.pr.ppjCal) * (titular ? 1 : 0.15);
            if (dPontos <= 0) return;
            const ganho = dPontos / Math.max(dCusto, 0.1);
            if (!melhorTroca || ganho > melhorTroca.ganho) {
              melhorTroca = { i, atual, cand, dCusto, ganho };
            }
          });
        });
        if (!melhorTroca) break;
        clubes[melhorTroca.atual.p.team] -= 1;
        clubes[melhorTroca.cand.p.team] = (clubes[melhorTroca.cand.p.team] || 0) + 1;
        escolhidos[melhorTroca.i] = melhorTroca.cand;
        custo += melhorTroca.dCusto;
      }

      const xi = melhorXI(escolhidos);
      const pontos = xi.reduce((s, x) => s + x.pr.ppjCal, 0);
      if (!melhor || pontos > melhor.pontos) {
        const banco = escolhidos.filter((x) => !xi.includes(x));
        melhor = { formacao: def + "-" + med + "-" + av, xi, banco, custo, pontos, escolhidos };
      }
    }
  }
  return melhor;
}

function chipsPorPosicao(lista) {
  const porPos = { 1: [], 2: [], 3: [], 4: [] };
  lista.forEach((x) => porPos[x.p.element_type].push(x));
  [1, 2, 3, 4].forEach((pos) => porPos[pos].sort((a, b) => b.pr.ppjCal - a.pr.ppjCal));
  return [1, 2, 3, 4].map((pos) =>
    '<div class="linha-campo">' + porPos[pos].map((x) =>
      '<span class="chip"><span class="chip-nome">' + esc(x.p.web_name) + "</span>" +
      '<span class="chip-info">' + nomeClube(x.p.team) + " · " + precoDe(x.p).toFixed(1) + "M</span>" +
      '<span class="chip-info">' + x.pr.ppjCal.toFixed(1) + " pts</span></span>").join("") +
    "</div>").join("");
}

function desenharMelhorPlantel() {
  const alvo = $("plantel-otimo");
  if (!alvo) return;
  const melhor = melhorPlantelPossivel();
  if (!melhor) { alvo.innerHTML = '<p class="nota">Sem dados suficientes.</p>'; return; }

  const orcamento = ((D.regras.squad || {}).total_spend || 1000) / 10;
  const capitao = melhor.xi.slice().sort((a, b) => b.pr.ppjCal - a.pr.ppjCal)[0];
  const clubes = {};
  melhor.escolhidos.forEach((x) => { clubes[x.p.team] = (clubes[x.p.team] || 0) + 1; });
  const maisUsados = Object.entries(clubes).filter(([, n]) => n >= 2)
    .map(([t, n]) => n + "× " + (D.teams[t] || {}).short_name).join(", ");

  $("otimo-resumo").textContent = melhor.formacao + " · " + melhor.custo.toFixed(1) + "M de " +
    orcamento.toFixed(1) + "M · ≈ " + melhor.pontos.toFixed(1) + " pts nesta jornada";

  alvo.innerHTML =
    '<div class="veredicto ok"><p>Capitão: <strong>' + esc(capitao.p.web_name) + "</strong> (" +
      nomeClube(capitao.p.team) + ") — " + (capitao.pr.ppjCal * 2).toFixed(1) +
      " pts com a braçadeira. Sobram <strong>" + (orcamento - melhor.custo).toFixed(1) +
      "M</strong> no banco." + (maisUsados ? " Concentração: " + maisUsados + "." : "") + "</p></div>" +
    '<div class="campo">' + chipsPorPosicao(melhor.xi) + "</div>" +
    '<p class="nota"><strong>Suplentes:</strong> ' + melhor.banco
      .sort((a, b) => b.pr.ppjCal - a.pr.ppjCal)
      .map((x) => esc(x.p.web_name) + " (" + (POSICOES[x.p.element_type] || "?") + " · " +
        precoDe(x.p).toFixed(1) + "M)").join(" · ") + "</p>";
}

/** Onde estou: mini-liga, classificação geral e orçamento. */
function contextoClassica(equipa) {
  const ev = D.next_event ? D.next_event.name : "próxima jornada";
  $("sug-titulo").textContent = "Sugestões para a " + ev;
  if (!equipa) {
    $("sug-contexto").textContent =
      "Sem FPL_ENTRY_ID: as sugestões são gerais, não para o teu plantel.";
    return;
  }
  const partes = [esc(equipa.nome) + " · " + equipa.pontos + " pts"];
  if (equipa.classificacao) {
    partes.push(equipa.classificacao.toLocaleString("pt-PT") + "º no geral");
  }
  const liga = ligaClassica();
  const eu = liga && (liga.participantes || []).find((x) => x.entry === equipa.id);
  if (eu && liga) {
    const lider = liga.participantes.reduce((a, b) => (a.total >= b.total ? a : b));
    const dif = lider.total - eu.total;
    partes.push(eu.rank + "º em " + liga.participantes.length + " na " + esc(liga.nome) +
      (dif > 0 ? " (a " + dif + " do líder)" : " — és o líder"));
  }
  $("sug-contexto").textContent = partes.join(" · ") + ".";
}

/**
 * O plantel mostrado pode já não ser o teu.
 *
 * A FPL **não publica a equipa antes do deadline**: `/entry/{id}/event/{ev}/picks/`
 * dá 404 para a jornada que ainda não fechou, e até os chips usados vêm a
 * vazio. O que se mostra é sempre o plantel da última jornada com escolhas
 * públicas — se entretanto fizeste transferências, ou gastaste o wildcard,
 * nada disso aparece aqui até o deadline passar.
 *
 * Isto não se corrige com código (a API pública não o dá); corrige-se dizendo-o.
 */
/** As escolhas públicas são anteriores à próxima jornada? */
function plantelDesatualizado(equipa) {
  const proxima = (D.next_event || {}).id;
  return !!(equipa && equipa.jornada_picks && proxima && equipa.jornada_picks < proxima);
}

function avisoPlantelDesatualizado(equipa) {
  const alvo = $("aviso-plantel");
  if (!alvo) return;
  const proxima = (D.next_event || {}).id;
  const daJornada = equipa && equipa.jornada_picks;
  // Indicado à mão: já é o plantel certo, mas convém dizer de onde veio — os
  // números que se seguem dependem dele estar bem escrito.
  if (equipa && equipa.manual) {
    alvo.hidden = false;
    alvo.textContent = "As sugestões abaixo são sobre o plantel que indicaste em " +
      "“O meu plantel”, não sobre o que a FPL publica (que ainda é o da jornada " +
      (((D.classica || {}).equipa) || {}).jornada_picks + "). " +
      "Se te enganaste a escrevê-lo, corrige aí.";
    return;
  }
  alvo.hidden = !(equipa && daJornada && proxima && daJornada < proxima);
  if (alvo.hidden) return;
  const dl = (D.next_event || {}).deadline_time;
  alvo.textContent =
    "O plantel abaixo é o da jornada " + daJornada + ", a última que a FPL publica. " +
    "Transferências e chips que tenhas feito para a jornada " + proxima +
    " — o wildcard incluído — só ficam visíveis depois do deadline" +
    (dl ? " (" + fmtDataHora.format(new Date(dl)) + ")" : "") +
    ". Até lá, abre “O meu plantel” e escreve os teus 15 — as sugestões passam " +
    "a ser sobre a equipa que tens mesmo.";
}

function initClassica() {
  if (!ehClassica()) return;
  initMeuPlantel();
  initPlaneadorWC();
  desenharClassica();
}

/** A parte que depende do plantel, e por isso se refaz quando ele muda. */
function desenharClassica() {
  if (!ehClassica()) return;
  const equipa = minhaEquipaClassica();
  avisoPlantelDesatualizado(equipa);
  const meusX = meusDaClassica();
  contextoClassica(equipa);
  // O plantel ideal só interessa quando não há equipa carregada (era a versão
  // do deadline); com plantel, a decisão útil são as transferências.
  const semEquipa = meusX.length === 0;
  const blocoOtimo = $("bloco-otimo");
  if (blocoOtimo) blocoOtimo.hidden = !semEquipa;
  if (semEquipa) desenharMelhorPlantel();
  // "Livres" é vocabulário do Draft: na clássica todos se compram por um preço.
  const tituloLivres = $("titulo-livres");
  if (tituloLivres) tituloLivres.textContent = "Melhores opções do mercado";
  desenharCapitao(meusX);
  desenharTransferencias(meusX);
  desenharPlaneadorWC();
  desenharChips(meusX);
}

/* ---------- Analisador de trocas ---------- */

function contaPorPosicao(lista) {
  return lista.reduce((c, x) => {
    c[x.p.element_type] = (c[x.p.element_type] || 0) + 1;
    return c;
  }, {});
}

function resumoPosicoes(lista) {
  const c = contaPorPosicao(lista);
  return [1, 2, 3, 4].filter((pos) => c[pos])
    .map((pos) => c[pos] + " " + POSICOES[pos]).join(" + ");
}

/** Jogadores marcados numa das colunas. */
function selecionados(idContentor, universo) {
  const ids = [...document.querySelectorAll("#" + idContentor + " input:checked")]
    .map((i) => Number(i.value));
  return universo.filter((x) => ids.includes(x.p.id));
}

function linhaEscolha(x) {
  const est = estadoDe(x.p);
  const ffs = ffsDe(x.p);
  const alerta = (ffs && ffs.estado === "fora") ? "Fora (Scout)" : (est.sev ? est.rotulo : "");
  const cargos = etiquetaBolaParada(x.p);
  return '<label class="escolha"><input type="checkbox" value="' + x.p.id + '">' +
    '<span class="escolha-nome">' + esc(x.p.web_name) + "</span>" +
    (cargos ? ' <span class="estado ok" title="Bola parada: P penáltis, LL livres, C cantos">' +
      cargos + "</span>" : "") +
    '<span class="escolha-info">' + (POSICOES[x.p.element_type] || "?") + " · " +
      nomeClube(x.p.team) + " · " + x.pr.ppj.toFixed(1) + " pts/J</span>" +
    (alerta ? '<span class="estado bad">' + esc(alerta) + "</span>" : "") +
  "</label>";
}

/** Uma linha por jogador, com o motivo que o modelo usa. */
function detalheTroca(x, sentido) {
  const motivo = sentido === "dou" ? porqueSai(x) : porqueEntra(x);
  const bp = bolaParadaDe(x.p);
  const cargo = bp && bp.pen === 1 ? " Bate os penáltis da equipa"
    : bp && (bp.fk === 1 || bp.cantos === 1) ? " É ele que bate as bolas paradas da equipa"
    : bp && bp.pen === 2 ? " É o segundo na fila dos penáltis" : "";
  return "<li><strong>" + esc(x.p.web_name) + "</strong> (" +
    (POSICOES[x.p.element_type] || "?") + " · " + nomeClube(x.p.team) + ") — " + esc(motivo) +
    (cargo ? "." + cargo : "") +
    ". Projeta <strong>" + x.pr.ppj.toFixed(1) + " pts/jornada</strong>, " +
    x.pr.ppjCal.toFixed(1) + " com o calendário das próximas " + janelaAtual() + "." +
    (pontosEpocaPassada(x.p)
      ? " Fez " + pontosEpocaPassada(x.p) + " pontos na época passada." : "") +
    "</li>";
}

/** Casos que os números sozinhos não contam. */
function avisosTroca(dou, recebo) {
  const avisos = [];
  dou.forEach((x) => {
    const saudavel = ppjSaudavel(x.p);
    if (saudavel - x.pr.ppj >= 1) {
      avisos.push("Estás a dar <strong>" + esc(x.p.web_name) + "</strong> enquanto está em baixo: " +
        "recuperado projeta " + saudavel.toFixed(1) + " pts/jornada, contra os " +
        x.pr.ppj.toFixed(1) + " de agora. Só compensa se a ausência for longa.");
    }
  });
  recebo.forEach((x) => {
    const saudavel = ppjSaudavel(x.p);
    if (saudavel - x.pr.ppj >= 1) {
      avisos.push("<strong>" + esc(x.p.web_name) + "</strong> vale " + x.pr.ppj.toFixed(1) +
        " agora por estar em baixo, mas " + saudavel.toFixed(1) + " quando recuperar — pode " +
        "valer a pena se aguentares a espera.");
    }
    if (x.pr.naoUsado) {
      avisos.push("<strong>" + esc(x.p.web_name) + "</strong> não tem saído do banco nas " +
        "últimas jornadas.");
    }
  });
  return avisos;
}

function linhaTabela(rotulo, meu, dele, forte) {
  return "<tr><td>" + rotulo + "</td>" +
    '<td class="num' + (forte ? " forte" : "") + '">' + meu + "</td>" +
    '<td class="num">' + dele + "</td></tr>";
}

function sinal(v) {
  return (v >= 0 ? "+" : "") + v.toFixed(1);
}

/* --- Comparação com o mercado livre --- */

/** Livres aproveitáveis, do melhor para o pior. */
function livresDisponiveis() {
  return comProjecao(D.players.filter((p) => p.owner == null && !indisponivel(p)))
    .sort((a, b) => b.pr.ppj - a.pr.ppj);
}

/**
 * Para cada jogador que recebes, qual seria o melhor livre da mesma posição.
 *
 * É a pergunta que decide muitas trocas: se o mercado livre dá o mesmo, não
 * vale a pena gastar um jogador teu para lá chegar.
 */
function compararComLivres(recebo) {
  const livres = livresDisponiveis();
  const usados = new Set();
  return recebo.slice()
    .sort((a, b) => b.pr.ppj - a.pr.ppj)
    .map((x) => {
      const livre = livres.find((l) => l.p.element_type === x.p.element_type &&
        !usados.has(l.p.id));
      if (livre) usados.add(livre.p.id);
      return { recebe: x, livre: livre || null };
    });
}

/** Onze que terias se largasses os mesmos jogadores e fosses ao mercado livre. */
function valorComLivres(meusX, dou, pares) {
  const substitutos = pares.map((par) => par.livre).filter(Boolean);
  return valorXI(meusX.filter((x) => !dou.includes(x)).concat(substitutos));
}

function blocoAlternativa(meusX, dou, recebo, ganhoMeu, eu) {
  if (recebo.length === 0) return "";
  const pares = compararComLivres(recebo);
  const ganhoLivres = valorComLivres(meusX, dou, pares) - valorXI(meusX);
  const diferenca = ganhoMeu - ganhoLivres;

  let conselho;
  let cor;
  if (diferenca >= 0.3) {
    conselho = "A troca vale mais do que largar os mesmos jogadores e ir ao mercado livre (" +
      sinal(ganhoMeu) + " contra " + sinal(ganhoLivres) + " pts por jornada), por isso " +
      "justifica-se envolver outro gestor.";
    cor = "ok";
  } else if (diferenca > -0.3) {
    conselho = "Largar os mesmos jogadores e ir ao mercado livre dá praticamente o mesmo (" +
      sinal(ganhoLivres) + " contra " + sinal(ganhoMeu) + " pts por jornada) e não depende de " +
      "o outro gestor aceitar. A troca só compensa se quiseres garantir o jogador antes que " +
      "outro o apanhe.";
    cor = "warn";
  } else {
    conselho = "Não precisas de trocar: largar os mesmos jogadores e ir ao mercado livre dá " +
      sinal(ganhoLivres) + " pts por jornada, contra " + sinal(ganhoMeu) + " desta troca.";
    cor = "bad";
  }
  const fila = eu && eu.waiver_pick
    ? " Nota: os livres estão à vista de todos e és o #" + eu.waiver_pick +
      " na fila de waivers, por isso não são garantidos."
    : "";

  const linhas = pares.map((par) => {
    const x = par.recebe;
    const l = par.livre;
    const dif = l ? x.pr.ppj - l.pr.ppj : null;
    const marca = dif === null ? "" : dif >= 0.3 ? "ok" : dif > -0.3 ? "warn" : "bad";
    const leitura = dif === null ? "sem livre nessa posição"
      : dif >= 0.3 ? "vale a pena trocar por ele"
      : dif > -0.3 ? "equivalente ao que há de graça"
      : "o livre é melhor";
    return "<tr><td>" + esc(x.p.web_name) +
      '<span class="sub">' + (POSICOES[x.p.element_type] || "?") + " · " +
        nomeClube(x.p.team) + "</span></td>" +
      '<td class="num">' + x.pr.ppj.toFixed(1) + "</td>" +
      "<td>" + (l ? esc(l.p.web_name) + '<span class="sub">' + nomeClube(l.p.team) + "</span>" : "—") + "</td>" +
      '<td class="num">' + (l ? l.pr.ppj.toFixed(1) : "—") + "</td>" +
      '<td><span class="estado ' + marca + '">' + leitura + "</span></td></tr>";
  }).join("");

  return '<h3 class="sub-titulo">E se fosses ao mercado livre?</h3>' +
    '<div class="veredicto ' + cor + '"><p>' + conselho + fila + "</p></div>" +
    '<table class="tabela tabela-proj"><thead><tr><th>Recebes</th><th class="num">Pts/J</th>' +
      '<th>Melhor livre igual</th><th class="num">Pts/J</th><th>Leitura</th></tr></thead>' +
      "<tbody>" + linhas + "</tbody></table>";
}

function analisarTroca(eu) {
  const alvoId = Number($("troca-gestor").value);
  const outro = D.entries.find((e) => e.entry_id === alvoId);
  const meusX = comProjecao(D.players.filter((p) => p.owner === eu.entry_id));
  const delesX = comProjecao(D.players.filter((p) => p.owner === alvoId));

  const dou = selecionados("troca-meus", meusX);
  const recebo = selecionados("troca-deles", delesX);
  $("conta-dou").textContent = dou.length ? resumoPosicoes(dou) : "";
  $("conta-recebo").textContent = recebo.length ? resumoPosicoes(recebo) : "";

  if (dou.length === 0 && recebo.length === 0) {
    $("troca-resultado").innerHTML = '<p class="nota">Marca pelo menos um jogador de cada lado ' +
      "para veres a análise.</p>";
    return;
  }

  // O plantel tem de manter 2 GR, 5 DEF, 5 MED e 3 AV: as posições têm de bater certo.
  const cDou = contaPorPosicao(dou);
  const cRecebo = contaPorPosicao(recebo);
  const equilibrada = [1, 2, 3, 4].every((pos) => (cDou[pos] || 0) === (cRecebo[pos] || 0));

  const meuAntes = valorXI(meusX);
  const deleAntes = valorXI(delesX);
  const meuDepois = valorXI(meusX.filter((x) => !dou.includes(x)).concat(recebo));
  const deleDepois = valorXI(delesX.filter((x) => !recebo.includes(x)).concat(dou));
  const ganhoMeu = meuDepois - meuAntes;
  const ganhoDele = deleDepois - deleAntes;

  const somaPpj = (l) => l.reduce((t, x) => t + x.pr.ppj, 0);
  const somaCal = (l) => l.reduce((t, x) => t + x.pr.ppjCal, 0);
  const cartaz = (l) => l.reduce((t, x) => t + pontosEpocaPassada(x.p), 0);

  let veredicto;
  let cor;
  if (!equilibrada) {
    veredicto = "Esta troca não é possível como está: cada lado tem de dar e receber o mesmo " +
      "número de jogadores por posição, senão o plantel deixa de ter 2 GR, 5 DEF, 5 MED e 3 AV. " +
      "Dás " + (resumoPosicoes(dou) || "nada") + " e recebes " + (resumoPosicoes(recebo) || "nada") +
      ". Os números abaixo servem na mesma de referência.";
    cor = "bad";
  } else if (ganhoMeu >= 0.5) {
    const porqueAceita = ganhoDele >= 0.25
      ? "Ele também melhora (" + sinal(ganhoDele) + "), por isso é das raras em que os dois ganham."
      : cartaz(dou) > cartaz(recebo)
        ? "Ele perde em projeção, mas recebe os nomes com mais pontos na época passada (" +
          cartaz(dou) + " contra " + cartaz(recebo) + ") — é o número que costuma pesar na decisão."
        : "Ele perde dos dois lados, por isso é provável que recuse.";
    veredicto = "Vale a pena para ti: ganhas " + ganhoMeu.toFixed(1) +
      " pts por jornada no teu onze. " + porqueAceita;
    cor = "ok";
  } else if (ganhoMeu <= -0.5) {
    veredicto = "Recusa: perdes " + Math.abs(ganhoMeu).toFixed(1) + " pts por jornada no teu onze." +
      (ganhoDele > 0 ? " Quem ganha com isto é ele (" + sinal(ganhoDele) + ")." : "");
    cor = "bad";
  } else {
    veredicto = "Praticamente neutra para ti (" + sinal(ganhoMeu) + " pts por jornada). " +
      "Decide pelo calendário ou por quem preferes ter no plantel a médio prazo.";
    cor = "warn";
  }

  const avisos = avisosTroca(dou, recebo);
  $("troca-resultado").innerHTML =
    '<div class="veredicto ' + cor + '"><p>' + veredicto + "</p></div>" +
    '<table class="tabela tabela-proj"><thead><tr><th>Efeito</th><th class="num">Tu</th>' +
      '<th class="num">' + esc(outro.entry_name) + "</th></tr></thead><tbody>" +
      linhaTabela("Onze antes", meuAntes.toFixed(1), deleAntes.toFixed(1)) +
      linhaTabela("Onze depois", meuDepois.toFixed(1), deleDepois.toFixed(1)) +
      linhaTabela("Diferença no onze", sinal(ganhoMeu), sinal(ganhoDele), true) +
      linhaTabela("Pts/jornada que entram", somaPpj(recebo).toFixed(1), somaPpj(dou).toFixed(1)) +
      linhaTabela("Ajustado ao calendário (" + janelaAtual() + " jornadas)",
        sinal(somaCal(recebo) - somaCal(dou)), sinal(somaCal(dou) - somaCal(recebo))) +
      linhaTabela("Pontos da época passada que entram", cartaz(recebo), cartaz(dou)) +
    "</tbody></table>" +
    (dou.length ? '<h3 class="sub-titulo">Sais com</h3><ul class="detalhe-troca">' +
      dou.map((x) => detalheTroca(x, "dou")).join("") + "</ul>" : "") +
    (recebo.length ? '<h3 class="sub-titulo">Recebes</h3><ul class="detalhe-troca">' +
      recebo.map((x) => detalheTroca(x, "recebo")).join("") + "</ul>" : "") +
    (avisos.length ? '<ul class="avisos-troca">' + avisos.map((a) => "<li>" + a + "</li>").join("") +
      "</ul>" : "") +
    blocoAlternativa(meusX, dou, recebo, ganhoMeu, eu);
}

function initAnaliseTroca() {
  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  if (!eu) return;
  const sel = $("troca-gestor");
  sel.innerHTML = D.entries.filter((e) => e.id !== eu.id)
    .map((e) => '<option value="' + e.entry_id + '">' + esc(e.entry_name) + " · " +
      esc(e.manager) + "</option>").join("");

  const porPpj = (a, b) => b.pr.ppj - a.pr.ppj;
  function desenharListas() {
    const meusX = comProjecao(D.players.filter((p) => p.owner === eu.entry_id)).sort(porPpj);
    const delesX = comProjecao(D.players.filter((p) => p.owner === Number(sel.value))).sort(porPpj);
    $("troca-meus").innerHTML = meusX.map(linhaEscolha).join("");
    $("troca-deles").innerHTML = delesX.map(linhaEscolha).join("");
  }

  sel.addEventListener("change", () => { desenharListas(); analisarTroca(eu); });
  $("form-troca").addEventListener("submit", (ev) => ev.preventDefault());
  ["troca-meus", "troca-deles"].forEach((id) =>
    $(id).addEventListener("change", () => analisarTroca(eu)));

  desenharListas();
  analisarTroca(eu);
}

/** Seletor da janela: redesenha tudo o que depende do calendário. */
function initSeletorJanela() {
  const sel = $("janela");
  if (!sel) return;
  sel.value = String(janelaAtual());
  $("form-janela").addEventListener("submit", (ev) => ev.preventDefault());
  const explicar = () => {
    const amp = amplitudeCalendario();
    $("janela-nota").textContent = amp
      ? "Nesta janela o calendário mexe entre " + sinalPct(amp.min) + " e " + sinalPct(amp.max) +
        " na projeção de cada jogador — afina a ordem entre jogadores parecidos, mas não " +
        "inverte diferenças grandes (um lesionado continua a valer zero)."
      : "";
  };
  explicar();
  sel.addEventListener("change", () => {
    definirJanela(Number(sel.value));
    explicar();
    const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
    if (eu) desenharOnze(comProjecao(D.players.filter((p) => p.owner === eu.entry_id)));
    initProjecoes();
    initSugestoes();
    aplicarFiltros();
    analisarTroca(eu);
  });
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
  const ffs = ffsDe(p);
  if (ffs && ffs.estado === "fora") {
    nivel = 3;
    motivos.push("Fantasy Football Scout: “" + ffs.frase + "”");
  }
  if (indisponivel(p)) {
    nivel = 3;
    motivos.push(est.rotulo + (p.news ? " — " + p.news : ""));
  } else if (p.status === "d") {
    nivel = Math.max(nivel, 2); // não baixar se o Scout já o deu como fora
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

  // --- Fantasy Football Scout ---
  const ffs = D.ffs || { feed: [], jogadores: {} };
  if (ffs.artigo) {
    $("ffs-artigo").innerHTML = '<a href="' + esc(ffs.artigo.link) + '" target="_blank" ' +
      'rel="noopener">' + esc(ffs.artigo.titulo) + "</a>";
  }
  const ROTULO_FFS = { fora: ["Fora", "bad"], duvida: ["Dúvida", "warn"], apto: ["Apto", "ok"] };
  const meusFFS = meus.map((p) => ({ p, f: ffsDe(p) })).filter((x) => x.f)
    .sort((a, b) => (a.f.estado === "fora" ? 0 : 1) - (b.f.estado === "fora" ? 0 : 1));
  if (meusFFS.length === 0) {
    $("nota-ffs").hidden = false;
  } else {
    $("ffs-meus").innerHTML = meusFFS.map(({ p, f }) => {
      const [rotulo, cor] = ROTULO_FFS[f.estado] || ["?", ""];
      return '<li class="risco ' + cor + '">' +
        '<div class="linha">' +
          '<span class="nome">' + esc(p.web_name) + "</span>" +
          '<span class="clube">' + nomeClube(p.team) + " · " + (POSICOES[p.element_type] || "?") + "</span>" +
          '<span class="estado ' + cor + '">' + rotulo + "</span>" +
        "</div>" +
        '<ul class="motivos"><li>“' + esc(f.frase) + "”</li>" +
          (f.estado === "fora" && !STATUS_FORA.has(p.status)
            ? "<li>A API oficial ainda o dá como disponível — a projeção já o põe a zero.</li>"
            : "") +
        "</ul></li>";
    }).join("");
  }
  $("ffs-feed").innerHTML = (ffs.feed || []).slice(0, 8).map((n) => {
    const data = n.data ? fmtDataHora.format(new Date(n.data)) : "";
    return "<li><a href=\"" + esc(n.link) + '" target="_blank" rel="noopener">' +
      esc(n.titulo) + "</a> <span class=\"data\">" + data + "</span></li>";
  }).join("");

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
        ' <span class="fonte-noticia">' + (i.fonte === "pl" ? "PL" : "Sky") + "</span>" +
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

/* ---------- A jornada, equipa a equipa ---------- */

/**
 * Onde está cada gestor nesta jornada: o que já fez, quantos jogadores lhe
 * faltam e onde deve acabar.
 *
 * Só conta o **onze** — no Draft o banco não pontua —, e "já jogou" é o jogo
 * daquele jogador, não a jornada inteira: com os jogos espalhados pelo fim de
 * semana, quem joga na segunda ainda tem tudo por fazer.
 */
function estadoDaJornada() {
  const pj = D.picks_jornada || {};
  const ev = pj.evento;
  const jornada = (D.jornadas || {})[String(ev)];
  if (!ev || !jornada || !pj.equipas) return null;
  const jogaram = new Set(jornada.equipas || []);
  const stats = jornada.stats || {};

  const linhas = D.entries.map((e) => {
    const escolhas = pj.equipas[String(e.entry_id)];
    // Sem escolhas (deadline por passar) o plantel inteiro é o melhor palpite.
    const ids = escolhas ? escolhas.xi
      : D.players.filter((p) => p.owner === e.entry_id).map((p) => p.id);
    const xi = ids.map((id) => jogadoresPorId[id]).filter(Boolean);
    let feitos = 0;
    const faltam = [];
    xi.forEach((p) => {
      if (jogaram.has(p.team)) {
        feitos += (stats[String(p.id)] || [0, 0])[1];
      } else {
        faltam.push({ p, pr: projecao(p) });
      }
    });
    faltam.sort((a, b) => b.pr.ppj - a.pr.ppj);
    const porVir = faltam.reduce((t, x) => t + x.pr.ppj, 0);
    return { entrada: e, feitos, faltam, porVir, previsao: feitos + porVir,
             completo: !!escolhas };
  });
  linhas.sort((a, b) => b.previsao - a.previsao);
  return { evento: ev, linhas, comEscolhas: linhas.every((l) => l.completo) };
}

function desenharJornada() {
  const bloco = $("bloco-jornada");
  if (!bloco) return;
  const estado = estadoDaJornada();
  bloco.hidden = !estado;
  if (!estado) return;

  const eu = D.entries.find((e) => MEU_GESTOR.test(e.manager));
  const totalFaltam = estado.linhas.reduce((t, l) => t + l.faltam.length, 0);
  $("jornada-resumo").textContent = "Jornada " + estado.evento + " · " +
    (totalFaltam ? totalFaltam + " jogadores por jogar" : "todos já jogaram");
  $("jornada-legenda").textContent =
    "Só conta o onze inicial. “Agora” são os pontos já feitos; “Previsão” soma-lhes o que o " +
    "modelo espera de quem ainda não entrou em campo." +
    (estado.comEscolhas ? "" : " Alguns gestores ainda não fecharam o onze — para esses " +
      "conta o plantel todo, o que inflaciona a previsão.") +
    " As substituições automáticas não estão contadas: só são aplicadas no fim da jornada.";

  document.querySelector("#tabela-jornada tbody").innerHTML = estado.linhas.map((l) => {
    const meu = eu && l.entrada.id === eu.id;
    const quem = l.faltam.length === 0 ? ""
      : l.faltam.map((x) => '<span class="chip"><span class="chip-nome">' +
          esc(x.p.web_name) + '</span><span class="chip-info">' +
          nomeClube(x.p.team) + " · " + x.pr.ppj.toFixed(1) + "</span></span>").join("");
    // Os nomes vão por baixo da equipa, e não numa coluna própria: numa coluna
    // desapareceriam no telemóvel, que é onde isto mais se olha.
    return '<tr class="' + (meu ? "eu" : "") + '">' +
      "<td>" + esc(l.entrada.entry_name) + (meu ? " ★" : "") +
        '<span class="sub">' + esc(l.entrada.manager) + "</span>" +
        (l.faltam.length ? '<div class="linha-campo faltam">' + quem + "</div>" : "") +
      "</td>" +
      '<td class="num forte">' + l.feitos + "</td>" +
      '<td class="num">' + (l.faltam.length || "—") + "</td>" +
      '<td class="num">' + l.previsao.toFixed(1) +
        (l.porVir >= 0.05 ? '<span class="sub">+' + l.porVir.toFixed(1) + "</span>" : "") +
      "</td>" +
    "</tr>";
  }).join("");
}

/* ---------- Mercado ---------- */

function nomeJogador(id) {
  const p = jogadoresPorId[id];
  return p ? esc(p.web_name) + ' <span class="clube">(' + nomeClube(p.team) + ")</span>" : "?";
}

/* --- Mercado: o que se passou na liga, jornada a jornada --- */
const NOMES_CHIP = {
  wildcard: "Wildcard", freehit: "Free Hit", bboost: "Bench Boost",
  "3xc": "Triple Captain", manager: "Assistant Manager",
};

function nomeChip(nome) {
  return NOMES_CHIP[nome] || nome;
}


/** Movimentos do Draft agrupados por jornada, da mais recente para a mais antiga. */
function movimentosPorJornada(transacoes) {
  const porEvento = {};
  transacoes.forEach((t) => {
    const ev = t.event || 0;
    (porEvento[ev] = porEvento[ev] || []).push(t);
  });
  return Object.keys(porEvento).map(Number).sort((a, b) => b - a)
    .map((ev) => ({ evento: ev, itens: porEvento[ev] }));
}

/** Resultados da mini-liga clássica em cada jornada. */
function jornadasDaLigaClassica() {
  const liga = ligaClassica();
  if (!liga) return [];
  const eventos = new Set();
  liga.participantes.forEach((p) =>
    (p.historico || []).forEach((h) => eventos.add(h.jornada)));

  return [...eventos].sort((a, b) => b - a).map((ev) => {
    const linhas = liga.participantes.map((p) => {
      const h = (p.historico || []).find((x) => x.jornada === ev);
      return h ? { p, h } : null;
    }).filter(Boolean).sort((a, b) => b.h.pontos - a.h.pontos);
    return { evento: ev, linhas };
  });
}

function desenharMercadoClassica() {
  const alvo = $("liga-jornadas");
  if (!alvo) return;
  const jornadas = jornadasDaLigaClassica();
  const eu = (minhaEquipaClassica() || {}).id;
  if (jornadas.length === 0) {
    alvo.innerHTML = '<p class="nota">Ainda não há jornadas concluídas. Depois de cada uma, ' +
      "aparece aqui o que cada equipa fez: pontos, transferências, penalizações e chips.</p>";
    return;
  }

  alvo.innerHTML = jornadas.map(({ evento, linhas }) => {
    const melhor = linhas[0];
    return '<h3 class="sub-titulo">Gameweek ' + evento +
      ' <span class="sub-total">melhor: ' + esc(melhor.p.nome) + " com " +
      melhor.h.pontos + " pts</span></h3>" +
      '<table class="tabela tabela-proj"><thead><tr><th>Equipa</th>' +
        '<th class="num">Pontos</th><th class="num">Total</th>' +
        '<th class="num">Banco</th><th>Transferências</th></tr></thead><tbody>' +
        linhas.map(({ p, h }) => {
          const chip = (p.chips_usados || []).find((c) => c.jornada === evento);
          const trocas = h.transferencias
            ? h.transferencias + (h.custo ? " (−" + h.custo + " pts)" : "")
            : "—";
          return '<tr class="' + (p.entry === eu ? "eu" : "") + '">' +
            "<td>" + esc(p.nome) + (p.entry === eu ? " ★" : "") +
              '<span class="sub">' + esc(p.gestor) +
              (chip ? " · " + esc(nomeChip(chip.chip)) : "") + "</span></td>" +
            '<td class="num forte">' + h.pontos + "</td>" +
            '<td class="num">' + h.total + "</td>" +
            '<td class="num">' + h.banco + "</td>" +
            "<td>" + trocas + "</td></tr>";
        }).join("") +
      "</tbody></table>";
  }).join("");
}

/* ---------- Transferências concluídas ---------- */

const fmtDataCurta = new Intl.DateTimeFormat("pt-PT", {
  timeZone: "Europe/Lisbon", day: "2-digit", month: "short",
});

/** Transferências que passam a pesquisa e o filtro de valor. */
function transferenciasFiltradas() {
  const todas = ((D.mercado || {}).transferencias_feitas || []);
  const procura = semAcentos(($("transf-procura") || {}).value || "").trim();
  const todasElas = ($("transf-todas") || {}).checked;
  return todas.filter((t) => {
    // Por omissão fica o que interessa: jogadores da FPL e negócios com valor.
    // O resto são 152 empréstimos de juniores a divisões inferiores.
    if (!todasElas && !t.jogador && t.tipo !== "valor") return false;
    if (!procura) return true;
    const p = jogadoresPorId[t.jogador] || {};
    const alvo = semAcentos([p.web_name, p.first_name, p.second_name, t.nome,
      t.jogador ? nomeClube(p.team) : "", t.de, t.para, t.titulo].join(" "));
    return alvo.indexOf(procura) >= 0;
  });
}

// Letras que o NFD não decompõe, como no `sem_acentos` da recolha: sem isto
// "Nørgaard" nunca casaria com "Norgaard".
const LETRAS_SOLTAS = { "ø": "o", "đ": "d", "ł": "l", "ß": "ss",
  "æ": "ae", "œ": "oe", "þ": "th" };

/** Minúsculas e sem acentos, para a pesquisa não depender de como se escreve. */
function semAcentos(txt) {
  return (txt || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[øđłßæœþ]/g, (c) => LETRAS_SOLTAS[c]);
}

function desenharTabelaTransferencias() {
  const corpo = document.querySelector("#tabela-transf tbody");
  if (!corpo) return;
  const lista = transferenciasFiltradas();
  const todas = ((D.mercado || {}).transferencias_feitas || []);
  const comValor = todas.filter((t) => t.tipo === "valor").length;

  const visiveis = transferenciasFiltradas().length;
  $("transf-total").textContent = todas.length
    ? visiveis + " negócios · " + comValor + " com valor publicado" : "";
  $("transf-legenda").textContent = todas.length
    ? "Do mais recente para o mais antigo, desde a abertura do mercado. “Livre”, “n/d” e " +
      "“empréstimo” vêm da fonte tal e qual — não são valores em falta."
    : "";
  $("nota-transf").hidden = lista.length > 0;
  $("tabela-transf").hidden = lista.length === 0;
  const mostrar = lista.slice(0, transfLimite);
  const botao = $("transf-mais");
  if (botao) {
    botao.hidden = lista.length <= transfLimite;
    botao.textContent = "Mostrar mais (" + (lista.length - transfLimite) + ")";
  }

  const ROTULO_TIPO = { livre: "livre", nd: "n/d", emprestimo: "empréstimo" };
  corpo.innerHTML = mostrar.map((t) => {
    const p = jogadoresPorId[t.jogador];
    // Sem jogador da FPL, o nome vem da Wikipedia: ou é um reforço acabado de
    // fechar que a FPL ainda não acrescentou, ou alguém que saiu da liga.
    const nome = p ? p.web_name : (t.nome || "—");
    const sub = p
      ? (POSICOES[p.element_type] || "?") +
        (t.saiu ? ' · <span class="estado bad">saiu da liga</span>' : "")
      : '<span class="fora-fpl">fora da FPL</span>';
    const data = t.data ? fmtDataCurta.format(new Date(t.data)) : "—";
    const valor = t.tipo === "valor"
      ? '<span class="forte">' + esc(t.moeda) + t.valor.toFixed(t.valor < 10 ? 1 : 0) + "M</span>"
      : ROTULO_TIPO[t.tipo] ? '<span class="sub">' + ROTULO_TIPO[t.tipo] + "</span>" : "—";
    const rota = t.de || t.para
      ? esc(t.de || "?") + ' <span class="seta">→</span> ' + esc(t.para || "?")
      : '<span class="sub">' + esc(p ? nomeClube(p.team) : "") + "</span>";
    const noticia = t.link
      ? '<span class="fonte-noticia">' + (t.oficial ? "PL" : "Sky") + "</span> " +
        '<a href="' + esc(t.link) + '" target="_blank" rel="noopener">' +
          esc(t.titulo) + "</a>"
      : '<span class="sub">sem notícia associada</span>';
    return "<tr>" +
      '<td class="data">' + data + "</td>" +
      "<td>" + (t.link
          ? '<a href="' + esc(t.link) + '" target="_blank" rel="noopener" title="' +
            esc(t.titulo) + '">' + esc(nome) + "</a>"
          : esc(nome)) +
        '<span class="sub">' + sub + "</span></td>" +
      '<td class="rota">' + rota + "</td>" +
      '<td class="num">' + valor + "</td>" +
      '<td class="col-noticia">' + noticia + "</td>" +
    "</tr>";
  }).join("");
}

const TRANSF_POR_PAGINA = 40;
let transfLimite = TRANSF_POR_PAGINA;

function initTransferencias() {
  const form = $("form-transf");
  if (!form) return;
  form.addEventListener("input", () => {
    transfLimite = TRANSF_POR_PAGINA; // filtro novo, contagem do zero
    desenharTabelaTransferencias();
  });
  form.addEventListener("submit", (ev) => ev.preventDefault());
  const mais = $("transf-mais");
  if (mais) {
    mais.addEventListener("click", () => {
      transfLimite += TRANSF_POR_PAGINA;
      desenharTabelaTransferencias();
    });
  }
  desenharTabelaTransferencias();
}

function initMercado() {
  const m = D.mercado || { noticias: [], transacoes: [] };

  if (m.transacoes.length === 0) {
    $("nota-movimentos").hidden = false;
  } else {
    const KINDS = { w: "waiver", f: "free agency" };
    $("lista-movimentos").innerHTML = movimentosPorJornada(m.transacoes).map((grupo) =>
      '<li class="grupo">Gameweek ' + grupo.evento + " (" + grupo.itens.length + ")</li>" +
      grupo.itens.map((t) => {
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
    }).join("")).join("");
  }

  if (ehClassica()) {
    desenharMercadoClassica();
    return;   // as notícias de transferências ficam só no Draft
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
    const modo = modoAtual();
    aplicarModo(modo);
    // A versão publicada como Artifact traz os dados embutidos (é um ficheiro
    // único, sem servidor por trás); a versão local vai buscá-los ao disco.
    if (window.__DADOS__) {
      D = window.__DADOS__[modo];
      if (!D) throw new Error("sem dados para o modo " + modo);
    } else {
      const resp = await fetch(MODOS[modo], { cache: "no-store" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      D = await resp.json();
    }
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
  initDiagnostico();
  initTicker(noticias);
  initBoletim(ordenarBoletim(noticiasBoletim()));
  initSeletorModo();
  meuPlantel = lerPlantelManual();
  aplicarPlantelManual();
  if (ehClassica()) {
    initLigaClassica();
    initEquipasClassica();
  } else {
    initLiga();
    initEquipas();
  }
  initConferencias();
  initProjecoes();
  guardarProjecoes();
  desenharPrecisao();
  initSugestoes();
  if (!ehClassica()) initAnaliseTroca();
  initClassica();
  initSeletorJanela();
  desenharJornada();
  initTransferencias();
  initMercado();
  initJogadores();
  initTabs();
}

// A página de testes carrega este ficheiro e monta o seu próprio D.
if (!window.__TESTES__) main();
