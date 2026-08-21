#!/usr/bin/env python3
"""Recolhe dados da API do FPL Draft e gera site/data/data.json.

Uso: LEAGUE_ID=12258 python scripts/fetch_data.py
Só usa a stdlib. A API é pública e não requer autenticação.
"""
import json
import os
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

BASE = "https://draft.premierleague.com/api"
SKY_RSS = "https://www.skysports.com/rss/12691"  # Sky Sports Transfer Centre

# Feeds por clube do Sky Sports (ids confirmados por sondagem em 2026-08-21).
# Chave = "name" do clube no bootstrap-static.
SKY_CLUBES = {
    "Arsenal": 11670, "Aston Villa": 11677, "Bournemouth": 11743,
    "Brentford": 11748, "Brighton": 11741, "Chelsea": 11668,
    "Coventry City": 11710, "Crystal Palace": 11706, "Everton": 11671,
    "Fulham": 11681, "Hull City": 11714, "Ipswich Town": 11707,
    "Leeds": 11715, "Liverpool": 11669, "Man City": 11679,
    "Man Utd": 11667, "Newcastle": 11678, "Nott'm Forest": 11727,
    "Spurs": 11675, "Sunderland": 11695,
}

# Um item é tratado como conferência/antevisão (e não notícia solta) se bater aqui.
CONF_PADROES = (
    "says", "said", "confirms", "confident", "expects", "insists", "admits",
    "reveals", "latest:", "team news", "press conference", "injury", "injured",
    "ruled out", "doubt", "fitness", "return", "available", "boss", "line-up",
    "lineup", "starting", "suspended", "ban", "back in", "sidelined", "fit",
)
# Ruído promocional/editorial que não interessa para escalar a equipa.
CONF_RUIDO = (
    "super 6", "sky bet", "free bet", "odds", "win £", "quiz", "papers:",
    "predictions", "transfer centre live", "watch:", "highlights", "podcast",
)
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "data")

PLAYER_FIELDS = (
    "id", "web_name", "first_name", "second_name", "team", "element_type",
    "draft_rank", "total_points", "status", "news", "news_added",
    "chance_of_playing_next_round", "form", "points_per_game",
    "minutes", "starts",
    # estatísticas da época anterior, para as projeções
    "goals_scored", "assists", "clean_sheets", "saves", "bonus",
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "defensive_contribution",
)

# Valores de transferência nos títulos/resumos das notícias (ex.: "£85m deal").
RE_VALOR = re.compile(
    r"(?P<moeda>[£€$])\s?(?P<valor>\d+(?:[.,]\d+)?)\s?(?P<mult>m\b|million|bn\b|billion)", re.I)
# Negócio fechado (mesmo que a notícia também fale de conversas/interesse).
RE_FECHADO = re.compile(
    r"\b(completes?d?|has joined|joins|joined|sealed?|medical"
    r"|agreed? (?:a )?(?:[£€$]?[\d.,]+m? )?deal|signs?\b[^.]{0,60}\bdeal)\b", re.I)
# Ainda em aberto: só rumor, não mexe na projeção.
RE_ABERTO = re.compile(
    r"\b(reject\w*|seek\w*|want\w*|target\w*|interest\w*|talks|bid|eye\w*"
    r"|approach\w*|enquir\w*|consider\w*|linked|monitor\w*)\b", re.I)


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def rss_data_para_iso(pubdate):
    """'Fri, 21 Aug 2026 07:56:00 BST' -> ISO UTC (parsedate não conhece BST)."""
    if not pubdate:
        return None
    txt = pubdate.replace(" BST", " +0100").replace(" GMT", " +0000")
    try:
        return parsedate_to_datetime(txt).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def sem_acentos(txt):
    return "".join(c for c in unicodedata.normalize("NFD", txt)
                   if unicodedata.category(c) != "Mn")


def ler_rss(url, limite=20):
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    itens = []
    for item in root.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        if not titulo:
            continue
        itens.append({
            "titulo": titulo,
            "link": (item.findtext("link") or "").strip(),
            "data": rss_data_para_iso(item.findtext("pubDate")),
            "resumo": " ".join((item.findtext("description") or "").split())[:220],
        })
        if len(itens) >= limite:
            break
    return itens


def fetch_noticias_mercado():
    """Feed de transferências da Sky. Nunca deve partir a recolha principal."""
    try:
        itens = ler_rss(SKY_RSS)
    except Exception as exc:
        print(f"Aviso: RSS da Sky falhou ({exc}); a seguir sem notícias externas.",
              file=sys.stderr)
        return []
    for it in itens:
        baixa = it["titulo"].lower()
        it["rumor"] = baixa.startswith("papers") or "rumour" in baixa
    return itens


def _rx_nomes(nomes):
    partes = [re.escape(sem_acentos(n).lower()) for n in nomes if len(n) >= 4]
    return re.compile(r"\b(" + "|".join(partes) + r")\b") if partes else None


def padrao_nome(p):
    """Regex do nome de um jogador (sem acentos, fronteiras de palavra)."""
    nomes = {p["web_name"]}
    if p.get("second_name"):
        nomes.update(p["second_name"].split())
    return _rx_nomes(nomes)


def padroes_nome_split(p):
    """(principal, secundário): o web_name vale mais do que um apelido solto.

    Apelidos compostos (ex.: "Martínez Romero") geram falsos positivos, por isso
    só se usa o secundário quando nenhum jogador bate pelo nome principal."""
    principal = _rx_nomes({p["web_name"]})
    outros = set(p["second_name"].split()) if p.get("second_name") else set()
    outros.discard(p["web_name"])
    return principal, _rx_nomes(outros)


def fetch_feeds_clubes():
    """Lê uma vez o feed Sky de cada clube: {nome_clube: [itens]}."""
    feeds = {}
    for nome, rid in SKY_CLUBES.items():
        try:
            feeds[nome] = ler_rss(f"https://www.skysports.com/rss/{rid}", limite=25)
        except Exception as exc:
            print(f"Aviso: feed de {nome} falhou ({exc}).", file=sys.stderr)
            feeds[nome] = []
    return feeds


def extrair_transferencias(feeds, players, nomes_clubes):
    """Valores de transferência detetados nas notícias, por jogador.

    Uma transferência cara é sinal de que o jogador vai ser titular, por isso
    guarda-se o maior valor confirmado (rumores ficam marcados à parte)."""
    padroes = [(p,) + padroes_nome_split(p) for p in players]
    achados = {}

    for nome_clube, itens in feeds.items():
        for it in itens:
            texto = sem_acentos(f'{it["titulo"]} {it["resumo"]}').lower()
            m = RE_VALOR.search(texto)
            if not m:
                continue
            valor = float(m.group("valor").replace(",", "."))
            if m.group("mult").lower().startswith(("bn", "billion")):
                valor *= 1000
            if valor < 1 or valor > 500:  # ignora ruído (audiências, receitas)
                continue
            # Classificar pelo título: é escrito com precisão, o resumo mistura
            # o negócio fechado com as negociações à volta.
            titulo = sem_acentos(it["titulo"]).lower()
            confirmada = bool(RE_FECHADO.search(titulo)) and not RE_ABERTO.search(titulo)
            if not confirmada and not RE_ABERTO.search(texto):
                continue

            # O web_name manda; apelidos soltos só se ninguém bater pelo principal.
            candidatos = [p for p, pr, _ in padroes if pr and pr.search(texto)]
            if not candidatos:
                candidatos = [p for p, _, sec in padroes if sec and sec.search(texto)]
            if not candidatos or len(candidatos) > 3:  # ambíguo demais
                continue
            for p in candidatos:
                ant = achados.get(p["id"])
                melhor = (confirmada, valor)
                if ant is None or melhor > (ant["confirmada"], ant["valor"]):
                    achados[p["id"]] = {
                        "valor": round(valor, 1),
                        "moeda": m.group("moeda"),
                        "confirmada": confirmada,
                        "titulo": it["titulo"],
                        "link": it["link"],
                        "data": it["data"],
                        "fonte": nome_clube,
                    }
    return {str(k): v for k, v in achados.items()}


def fetch_fixtures(bootstrap, desde_evento):
    """Próximos jogos por clube, com dificuldade (1-5).

    A dificuldade só existe em /element-summary, que é por jogador mas devolve
    o calendário do clube — basta um jogador por equipa (20 pedidos)."""
    representante = {}
    for el in bootstrap["elements"]:
        representante.setdefault(el["team"], el["id"])

    saida = {}
    for team_id, el_id in representante.items():
        try:
            jogos = get(f"/element-summary/{el_id}")["fixtures"]
        except Exception as exc:
            print(f"Aviso: calendário da equipa {team_id} falhou ({exc}).", file=sys.stderr)
            continue
        saida[str(team_id)] = [
            {
                "event": j["event"],
                "opponent": j["opponent"],
                "is_home": j["is_home"],
                "difficulty": j["difficulty"],
            }
            for j in jogos
            if j.get("event") and j["event"] >= desde_evento and not j.get("finished")
        ][:10]
    return saida


def fetch_conferencias(clubes, meus, feeds):
    """Antevisões/conferências dos clubes onde tenho jogadores.

    `clubes`: [(team_id, nome)]. Cruza cada item com os nomes do meu plantel
    para assinalar quem é mencionado."""
    saida = []
    for team_id, nome in clubes:
        # Só cruzar com os meus jogadores deste clube: evita falsos positivos
        # (apelidos comuns) em notícias que mencionam outras equipas.
        alvos = [(p["id"], padrao_nome(p)) for p in meus if p["team"] == team_id]
        alvos = [(pid, rx) for pid, rx in alvos if rx]
        itens = feeds.get(nome, [])

        filtrados = []
        for it in itens:
            texto = sem_acentos(f'{it["titulo"]} {it["resumo"]}').lower()
            if any(r in texto for r in CONF_RUIDO):
                continue
            item = dict(it)  # os feeds são partilhados com as transferências
            item["conferencia"] = any(k in texto for k in CONF_PADROES)
            item["mencoes"] = [pid for pid, rx in alvos if rx.search(texto)]
            filtrados.append(item)
        # Data mais recente primeiro; depois menções e conferências ao topo.
        filtrados.sort(key=lambda i: i["data"] or "", reverse=True)
        filtrados.sort(key=lambda i: (not i["mencoes"], not i["conferencia"]))
        saida.append({"team_id": team_id, "nome": nome, "itens": filtrados[:8]})
    return saida


def load_previous_news(out_path):
    """ids -> news_added da recolha anterior, para detetar entradas novas no boletim.

    Devolve None se não houver recolha anterior (primeira execução): nesse caso
    nada é marcado como novo, para não pintar o boletim inteiro de vermelho."""
    try:
        with open(out_path, encoding="utf-8") as f:
            prev = json.load(f)
        return {p["id"]: p.get("news_added")
                for p in prev.get("players", []) if p.get("news")}
    except (OSError, ValueError, KeyError):
        return None


def pick_next_event(events, game):
    """Evento cujo deadline conta para a contagem decrescente."""
    by_id = {ev["id"]: ev for ev in events}
    if game.get("next_event") in by_id:
        return by_id[game["next_event"]]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for ev in events:
        if not ev.get("finished") and ev.get("deadline_time", "") > now:
            return ev
    return None


def main():
    league_id = os.environ.get("LEAGUE_ID", "").strip()
    if not league_id.isdigit():
        sys.exit("Erro: define a variável de ambiente LEAGUE_ID (número da liga no URL).")

    bootstrap = get("/bootstrap-static")
    game = get("/game")
    details = get(f"/league/{league_id}/details")
    status = get(f"/league/{league_id}/element-status")
    transacoes = get(f"/draft/league/{league_id}/transactions")["transactions"]

    owners = {es["element"]: es["owner"] for es in status["element_status"]}
    out_path = os.path.join(OUT_DIR, "data.json")
    prev_news = load_previous_news(out_path)

    players = []
    for el in bootstrap["elements"]:
        p = {k: el.get(k) for k in PLAYER_FIELDS}
        p["owner"] = owners.get(el["id"])
        p["news_new"] = bool(
            prev_news is not None and p["news"]
            and (el["id"] not in prev_news or prev_news[el["id"]] != p["news_added"])
        )
        players.append(p)

    events = bootstrap["events"]["data"]
    next_ev = pick_next_event(events, game)

    # Conferências: só os clubes onde tenho jogadores (equipa detetada pelo apelido).
    apelido = os.environ.get("MEU_GESTOR", "Gentil").strip().lower()
    eu = next((e for e in details["league_entries"]
               if apelido in f'{e["player_first_name"]} {e["player_last_name"]}'.lower()), None)
    nomes_clubes = {t["id"]: t["name"] for t in bootstrap["teams"]}
    meus = [p for p in players if eu and p["owner"] == eu["entry_id"]]
    clubes = sorted({(p["team"], nomes_clubes[p["team"]]) for p in meus}, key=lambda c: c[1])
    if not eu:
        print(f"Aviso: gestor '{apelido}' não encontrado; sem conferências.", file=sys.stderr)

    feeds = fetch_feeds_clubes()
    fixtures = fetch_fixtures(bootstrap, next_ev["id"] if next_ev else 1)
    noticias_mercado = fetch_noticias_mercado()

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "league_id": int(league_id),
        "game": game,
        "next_event": next_ev and {
            "id": next_ev["id"],
            "name": next_ev["name"],
            "deadline_time": next_ev["deadline_time"],
            "waivers_time": next_ev.get("waivers_time"),
            "trades_time": next_ev.get("trades_time"),
        },
        "league": {
            "name": details["league"]["name"],
            "scoring": details["league"]["scoring"],
            "transaction_mode": details["league"]["transaction_mode"],
        },
        "entries": [
            {
                "id": e["id"],
                "entry_id": e["entry_id"],
                "entry_name": e["entry_name"],
                "manager": f'{e["player_first_name"]} {e["player_last_name"]}',
                "short_name": e["short_name"],
                "waiver_pick": e.get("waiver_pick"),
            }
            for e in details["league_entries"]
        ],
        "standings": details["standings"],
        "teams": {str(t["id"]): {"name": t["name"], "short_name": t["short_name"]}
                  for t in bootstrap["teams"]},
        "players": players,
        "fixtures": fixtures,
        "transferencias": extrair_transferencias(
            {**feeds, "Transfer Centre": noticias_mercado}, players, nomes_clubes),
        "conferencias": {
            "equipa": eu["entry_name"] if eu else None,
            "clubes": fetch_conferencias(clubes, meus, feeds),
        },
        "mercado": {
            "noticias": noticias_mercado,
            "transacoes": [
                {k: t.get(k) for k in ("added", "element_in", "element_out",
                                       "entry", "event", "kind", "result")}
                for t in sorted(transacoes, key=lambda t: t.get("added") or "",
                                reverse=True)[:40]
            ],
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {out_path} ({os.path.getsize(out_path)} bytes, "
          f"{len(players)} jogadores, {len(data['entries'])} equipas)")


if __name__ == "__main__":
    main()
