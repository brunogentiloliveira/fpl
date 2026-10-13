#!/usr/bin/env node
/**
 * Precisão do modelo, medida "no passado".
 *
 * Corre o modelo do site/app.js para cada jornada já jogada só com o que se
 * sabia antes dela, e compara com os pontos reais. O "Precisão do modelo" do
 * site só vê o que o browser onde se abre guardou; isto não depende disso.
 *
 * O que se reconstrói, para não deixar o futuro entrar no passado:
 *  - jornadas: só as anteriores a t;
 *  - totais da época: minutos, pontos, xG, xA e xG sofrido somados jornada a
 *    jornada; os outros (defesas, bónus, cartões, contribuição defensiva…) não
 *    vêm por jornada e ficam proporcionais aos minutos — aproximação declarada;
 *  - estado clínico: o guardado na jornada t, só se a notícia for anterior ao
 *    jogo do clube (sem isso, quem se lesionou NO jogo contava como de fora);
 *  - Scout e escolhas da liga: de fora (são de hoje); transferências: só as
 *    anteriores ao prazo da jornada.
 *
 * Uso:  node scripts/precisao.mjs [--modo draft|classica] [--desde N] [--json ficheiro]
 *                                  [--app outro/app.js]
 *
 * --app corre outra versão do modelo (por exemplo a do último commit, tirada com
 * `git show HEAD:site/app.js > /tmp/app.js`) sobre os mesmos dados: é assim que
 * se mede um ajuste antes de o aceitar.
 *
 * O conjunto avaliado não pode depender da previsão nem do futuro. Duas
 * tentativas falharam assim: "projetados a 1.5+" tirava da avaliação quem um
 * ajuste passasse a projetar abaixo disso, e "com dono hoje" escolhia jogadores
 * pelos resultados das próprias jornadas avaliadas (os gestores apanham quem
 * marcou), o que dava +0.45 pts de viés que não era do modelo. Fica: quem já
 * tinha feito 60+ minutos num jogo antes da jornada, ou 900+ na época passada —
 * tudo coisas que se sabiam antes do jogo.
 */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const opcao = (nome, omissao) => {
  const i = args.indexOf("--" + nome);
  return i >= 0 && args[i + 1] ? args[i + 1] : omissao;
};
const MODO = opcao("modo", "draft");
const DESDE = Number(opcao("desde", "2"));
const SAIDA_JSON = opcao("json", null);
const APP = path.resolve(opcao("app", path.join(RAIZ, "site/app.js")));

// ---------- o modelo do site, carregado tal como está ----------
const armazem = {};
const ctx = vm.createContext({
  window: { __TESTES__: true }, console, Intl, Date, Math, JSON, Map, Set, Number, String,
  localStorage: { getItem: (k) => armazem[k] ?? null, setItem: (k, v) => { armazem[k] = String(v); } },
  matchMedia: () => ({ matches: false }),
  document: { getElementById: () => null, querySelectorAll: () => [], querySelector: () => null },
});
vm.runInContext(fs.readFileSync(APP, "utf8") +
  "\n;globalThis.__api = { projecao, construirPriors, limparCacheReforco, melhorXI," +
  " set D(v) { D = v; }, set jogadoresPorId(v) { jogadoresPorId = v; } };", ctx);
const api = ctx.__api;

const D0 = JSON.parse(fs.readFileSync(
  path.join(RAIZ, "site/data", MODO === "classica" ? "classica.json" : "data.json"), "utf8"));
const C0 = JSON.parse(fs.readFileSync(path.join(RAIZ, "site/data/calendario.json"), "utf8"));
const J = D0.jornadas || {};
const evs = Object.keys(J).map(Number).filter((e) => J[e].finalizada).sort((a, b) => a - b);
const num = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };

// Pontapé de saída de cada clube em cada jornada. O calendário usa os ids da
// FPL do Draft; na clássica os ids dos clubes são os mesmos (mesma ordem alfabética).
const kick = {};
Object.entries(C0.clubes || {}).forEach(([cid, c]) => (c.jogos || []).forEach((j) => {
  if (j.comp !== "PL" || j.jornada == null) return;
  const k = (kick[cid] = kick[cid] || {});
  const t = Date.parse(j.data);
  if (k[j.jornada] == null || t < k[j.jornada]) k[j.jornada] = t;
}));

const ESCALAR = ["saves", "penalties_saved", "bonus", "yellow_cards", "red_cards",
  "penalties_missed", "own_goals", "defensive_contribution", "goals_scored", "assists",
  "clean_sheets", "starts", "goals_conceded"];

function dadosAte(t) {
  const antes = evs.filter((e) => e < t);
  const players = JSON.parse(JSON.stringify(D0.players)).map((p) => {
    let min = 0, pts = 0, xg = 0, xa = 0, xgc = 0;
    antes.forEach((e) => {
      const s = J[e].stats[String(p.id)];
      if (s) { min += s[0]; pts += s[1]; xg += s[3] || 0; xa += s[4] || 0; xgc += s[5] || 0; }
    });
    const f = num(p.minutes) > 0 ? min / num(p.minutes) : 0;
    ESCALAR.forEach((c) => { if (p[c] != null) p[c] = num(p[c]) * f; });
    Object.assign(p, { minutes: min, total_points: pts, expected_goals: xg,
      expected_assists: xa, expected_goals_conceded: xgc });
    const e = (J[t].estados || {})[String(p.id)];
    const k = (kick[String(p.team)] || {})[t];
    if (e && e[2] && k != null && Date.parse(e[2]) <= k) {
      Object.assign(p, { status: e[0], chance_of_playing_next_round: e[1], news: "", news_added: e[2] });
    } else {
      Object.assign(p, { status: "a", chance_of_playing_next_round: null, news: "", news_added: null });
    }
    return p;
  });
  const jornadas = {};
  antes.forEach((e) => { jornadas[e] = J[e]; });
  const kicks = Object.values(kick).map((k) => k[t]).filter((x) => x != null);
  const prazo = (kicks.length ? Math.min(...kicks) : Date.now()) - 90 * 60e3;
  const transferencias = {};
  Object.entries(D0.transferencias || {}).forEach(([id, tr]) => {
    if (!tr.data || Date.parse(tr.data) <= prazo) transferencias[id] = tr;
  });
  return Object.assign({}, D0, { players, jornadas, transferencias,
    next_event: { id: t, name: "Gameweek " + t, deadline_time: new Date(prazo).toISOString() },
    ffs: { feed: [], artigo: null, jogadores: {} }, picks_jornada: {} });
}

// ---------- previsões ----------
const linhas = [];
const ateAgora = (id, t) => {
  const antes = evs.filter((e) => e < t);
  return antes.reduce((a, e) => a + ((J[e].stats[String(id)] || [0, 0])[1]), 0) / Math.max(1, antes.length);
};
const donoAtual = Object.fromEntries(D0.players.map((p) => [p.id, p.owner]));
for (const t of evs.filter((e) => e >= DESDE && J[e].estados)) {
  const Dt = dadosAte(t);
  api.D = Dt;
  api.jogadoresPorId = Object.fromEntries(Dt.players.map((p) => [p.id, p]));
  api.limparCacheReforco();
  api.construirPriors();
  const equipas = J[t].equipas || [];
  Dt.players.forEach((p) => {
    if (equipas.length && !equipas.includes(p.team)) return;
    const pr = api.projecao(p);
    const s = J[t].stats[String(p.id)] || [0, 0];
    const h = (Dt.historico || {})[p.id];
    const forma = ateAgora(p.id, t);
    const hist = h && h.total_points != null ? h.total_points / 38 : forma;
    const jogouAntes = evs.some((e) => e < t && ((J[e].stats[String(p.id)] || [0])[0]) >= 60);
    const conhecido = !!(jogouAntes || (h && num(h.minutes) >= 900));
    linhas.push({ t, id: p.id, nome: p.web_name, pos: p.element_type, dono: donoAtual[p.id], conhecido,
      pred: pr.ppj, xmin: pr.xmin, pp90: pr.pp90, real: s[1], min: s[0],
      hist, forma, mix: (hist + forma) / 2 });
  });
}
if (!linhas.length) {
  console.log("Sem jornadas avaliáveis (é preciso estado clínico guardado, a partir da 2).");
  process.exit(0);
}

// ---------- métricas ----------
const media = (v) => v.reduce((a, b) => a + b, 0) / (v.length || 1);
const POS = { 1: "GR", 2: "DEF", 3: "MED", 4: "AV" };
const PREVISORES = [["modelo", "pred"], ["época passada", "hist"], ["esta época", "forma"], ["mistura", "mix"]];

function postos(v) {
  const ord = v.map((x, i) => [x, i]).sort((a, b) => a[0] - b[0]);
  const r = new Array(v.length);
  for (let i = 0; i < ord.length;) {
    let j = i;
    while (j + 1 < ord.length && ord[j + 1][0] === ord[i][0]) j += 1;
    for (let k = i; k <= j; k += 1) r[ord[k][1]] = (i + j) / 2;
    i = j + 1;
  }
  return r;
}
function spearman(a, b) {
  const ra = postos(a), rb = postos(b);
  const ma = media(ra), mb = media(rb);
  let n = 0, da = 0, db = 0;
  ra.forEach((x, i) => { n += (x - ma) * (rb[i] - mb); da += (x - ma) ** 2; db += (rb[i] - mb) ** 2; });
  return n / Math.sqrt(da * db);
}
function metricas(rows, campo) {
  const e = rows.map((r) => r.real - r[campo]);
  return { n: rows.length, mae: media(e.map(Math.abs)), rmse: Math.sqrt(media(e.map((x) => x * x))),
    vies: media(e), rho: spearman(rows.map((r) => r[campo]), rows.map((r) => r.real)) };
}
// Reamostragem por jogador (as jornadas do mesmo jogador não são independentes).
function ic(rows, a, b, f) {
  const porJog = {};
  rows.forEach((r) => { (porJog[r.id] = porJog[r.id] || []).push(r); });
  const ids = Object.keys(porJog);
  let semente = 12345;
  const rnd = () => { semente = (semente * 1103515245 + 12345) % 2147483648; return semente / 2147483648; };
  const vals = [];
  for (let k = 0; k < 1000; k += 1) {
    const amostra = [];
    ids.forEach(() => amostra.push(...porJog[ids[Math.floor(rnd() * ids.length)]]));
    vals.push(f(amostra, a) - f(amostra, b));
  }
  vals.sort((x, y) => x - y);
  return [vals[25], vals[975], vals.filter((v) => v < 0).length / vals.length];
}
const maeDe = (rows, campo) => media(rows.map((r) => Math.abs(r.real - r[campo])));
// Viés com meia-largura do IC95. Só um viés que não cabe no ruído conta como sinal.
const sinais = [];
function viesIC(rows, rotulo) {
  const e = rows.map((r) => r.real - r.pred);
  const m = media(e);
  const sd = Math.sqrt(media(e.map((x) => (x - m) ** 2)));
  const meia = 1.96 * sd / Math.sqrt(e.length || 1);
  if (rotulo && e.length >= 30 && Math.abs(m) > meia) {
    sinais.push(`${rotulo}: viés ${m >= 0 ? "+" : ""}${m.toFixed(2)} ±${meia.toFixed(2)} (N=${e.length})`);
  }
  return `viés ${m >= 0 ? "+" : ""}${m.toFixed(2)} ±${meia.toFixed(2)}`;
}

const relevantes = linhas.filter((r) => r.conhecido);
const fmt = (x, d = 2) => (x >= 0 ? " " : "") + x.toFixed(d);
const out = [];
const L = (s = "") => out.push(s);

const jornadasAval = [...new Set(linhas.map((r) => r.t))];
L(`PRECISÃO DO MODELO — ${MODO}, jornadas ${jornadasAval.join(", ")}  (gerado ${new Date().toISOString().slice(0, 16)})`);
L(`Modelo: ${path.relative(RAIZ, APP) || APP}`);
L(`Avaliados: ${relevantes.length} jogador-jornada de quem já se sabia que joga (60+ min antes, ou 900+ na época passada)`);
L();
L("1. Contra previsores ingénuos (erro em pts/jogador; viés = real − previsto)");
L("   previsor          MAE    RMSE    viés   ordem(ρ)");
PREVISORES.forEach(([nome, campo]) => {
  const m = metricas(relevantes, campo);
  L(`   ${nome.padEnd(15)} ${m.mae.toFixed(2)}  ${m.rmse.toFixed(2)}  ${fmt(m.vies)}   ${m.rho.toFixed(3)}`);
});
{
  const m = metricas(linhas, "pred"), mm = metricas(linhas, "mix");
  L(`   (todos os ${linhas.length}: modelo MAE ${m.mae.toFixed(2)} viés ${fmt(m.vies)} ρ ${m.rho.toFixed(3)}; mistura MAE ${mm.mae.toFixed(2)} ρ ${mm.rho.toFixed(3)})`);
}
PREVISORES.slice(1).forEach(([nome, campo]) => {
  const [lo, hi, pPior] = ic(relevantes, campo, "pred", maeDe);
  L(`   modelo vs ${nome}: ganho em MAE IC95 [${lo.toFixed(2)}, ${hi.toFixed(2)}], P(modelo pior)=${pPior.toFixed(2)}`);
});
L();
L("2. Calibração (média prevista contra média real, por faixa de previsão)");
const faixas = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 99]];
faixas.forEach(([a, b]) => {
  const rows = relevantes.filter((r) => r.pred >= a && r.pred < b);
  if (!rows.length) return;
  L(`   ${String(a).padStart(2)}-${b === 99 ? "+" : b}: N=${String(rows.length).padStart(4)}  previsto ${media(rows.map((r) => r.pred)).toFixed(2)}  real ${media(rows.map((r) => r.real)).toFixed(2)}  (${viesIC(rows, `projeções ${a}-${b === 99 ? "+" : b}`)})`);
});
L();
L("3. Por posição");
[1, 2, 3, 4].forEach((pos) => {
  const rows = relevantes.filter((r) => r.pos === pos);
  if (!rows.length) return;
  const m = metricas(rows, "pred");
  const mixM = metricas(rows, "mix");
  L(`   ${POS[pos].padEnd(3)} N=${String(m.n).padStart(4)}  MAE ${m.mae.toFixed(2)} (mistura ${mixM.mae.toFixed(2)})  ${viesIC(rows, POS[pos])}  ρ ${m.rho.toFixed(3)}`);
});
L();
L("4. De onde vem o erro");
const minRows = relevantes;
L(`   minutos: previsto ${media(minRows.map((r) => r.xmin)).toFixed(1)}, real ${media(minRows.map((r) => r.min)).toFixed(1)}, MAE ${media(minRows.map((r) => Math.abs(r.min - r.xmin))).toFixed(1)} min`);
[1, 2, 3, 4].forEach((pos) => {
  const rows = relevantes.filter((r) => r.pos === pos && r.min >= 60);
  if (!rows.length) return;
  const real90 = media(rows.map((r) => (r.real / r.min) * 90));
  const d = rows.map((r) => (r.real / r.min) * 90 - r.pp90);
  const dm = media(d);
  const meia = 1.96 * Math.sqrt(media(d.map((x) => (x - dm) ** 2))) / Math.sqrt(d.length);
  if (d.length >= 30 && Math.abs(dm) > meia) {
    sinais.push(`por 90 dos ${POS[pos]}: ${dm >= 0 ? "+" : ""}${dm.toFixed(2)} ±${meia.toFixed(2)} pts/90 (N=${d.length})`);
  }
  L(`   por 90 (${POS[pos]}, quem jogou 60+, N=${rows.length}): previsto ${media(rows.map((r) => r.pp90)).toFixed(2)}, real ${real90.toFixed(2)}  (real/previsto ${(real90 / media(rows.map((r) => r.pp90))).toFixed(2)}, diferença ${dm >= 0 ? "+" : ""}${dm.toFixed(2)} ±${meia.toFixed(2)})`);
});
L();
L("5. A decisão que conta: o onze (planteis atuais dos gestores, sem substituições automáticas)");
const donos = [...new Set(linhas.map((r) => r.dono).filter((d) => d != null))];
const somaXI = { modelo: 0, "época passada": 0, "esta época": 0, mistura: 0, oráculo: 0 };
let nXI = 0;
jornadasAval.forEach((t) => {
  donos.forEach((dono) => {
    const plantel = linhas.filter((r) => r.t === t && r.dono === dono);
    if (plantel.length < 11) return;
    const jog = (r) => ({ id: r.id, element_type: r.pos });
    const onze = (campo) => api.melhorXI(plantel.map((r) => ({ p: jog(r), pr: { ppj: r[campo] }, r })))
      .reduce((s, x) => s + x.r.real, 0);
    PREVISORES.forEach(([nome, campo]) => { somaXI[nome] += onze(campo); });
    somaXI["oráculo"] += onze("real");
    nXI += 1;
  });
});
if (nXI) {
  Object.entries(somaXI).forEach(([nome, s]) => {
    L(`   ${nome.padEnd(15)} ${(s / nXI).toFixed(1)} pts por onze por jornada`);
  });
  L(`   (${nXI} onzes; "oráculo" é o melhor onze possível sabendo o resultado — o teto)`);
}
L();
const ultima = Math.max(...jornadasAval);
const ult = relevantes.filter((r) => r.t === ultima).map((r) => ({ ...r, erro: r.real - r.pred }))
  .sort((a, b) => b.erro - a.erro);
L(`6. Maiores desvios na J${ultima}`);
L("   acima do previsto: " + ult.slice(0, 5).map((r) => `${r.nome} ${r.pred.toFixed(1)}→${r.real}`).join(", "));
L("   abaixo do previsto: " + ult.slice(-5).reverse().map((r) => `${r.nome} ${r.pred.toFixed(1)}→${r.real}`).join(", "));
L();
L("7. Por jornada");
jornadasAval.forEach((t) => {
  const rows = relevantes.filter((r) => r.t === t);
  const m = metricas(rows, "pred");
  L(`   J${t}: N=${m.n}  MAE ${m.mae.toFixed(2)}  viés ${fmt(m.vies)}  ρ ${m.rho.toFixed(3)}`);
});

L();
L("8. A vigiar (desvios fora do ruído: IC95 sem o zero, N≥30)");
if (sinais.length) sinais.forEach((x) => L("   • " + x));
else L("   nenhum — tudo o que sobra cabe no ruído destas jornadas");

console.log(out.join("\n"));
if (SAIDA_JSON) fs.writeFileSync(SAIDA_JSON, JSON.stringify(linhas));
