#!/usr/bin/env python3
"""Recolhe a FPL clássica (fantasy.premierleague.com) para o modo "Clássica".

Uso: python scripts/fetch_classica.py
     FPL_ENTRY_ID=1234567 python scripts/fetch_classica.py   (com a tua equipa)

Escreve `site/data/classica.json` na **mesma forma** que o data.json do Draft,
para o motor de projeção do site funcionar sem alterações. O que muda são as
regras do jogo: orçamento, preços, capitão a dobrar, máximo 3 por clube,
transferências com custo e chips.

Só usa a stdlib e as funções partilhadas do fetch_data.py.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as fd

BASE = "https://fantasy.premierleague.com/api"
OUT = os.path.join(fd.OUT_DIR, "classica.json")
POS_SIGLA = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD", 5: "MNG"}

# Campos que só existem na clássica e que o modo precisa.
CAMPOS_CLASSICA = ("now_cost", "cost_change_event", "cost_change_start",
                   "selected_by_percent", "transfers_in_event", "transfers_out_event",
                   "ep_next", "penalties_order", "direct_freekicks_order",
                   "corners_and_indirect_freekicks_order")


def get(caminho):
    req = urllib.request.Request(BASE + caminho,
                                 headers={"User-Agent": "Mozilla/5.0 fpl-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def achatar_pontuacao(scoring):
    """{"goals_scored": {"GKP": 10}} -> {"goals_scored_GKP": 10}, como no Draft."""
    plano = {}
    for chave, valor in (scoring or {}).items():
        if isinstance(valor, dict):
            for pos, v in valor.items():
                plano[f"{chave}_{pos}"] = v
        else:
            plano[chave] = valor
    plano.setdefault("concede_limit", 2)
    plano.setdefault("saves_limit", 3)
    plano.setdefault("long_play_limit", 60)
    return plano


def calendario_por_clube(fixtures, desde):
    """Fixtures da API clássica -> {team_id: [{event, opponent, is_home, difficulty}]}.

    A clássica dá o calendário todo num pedido, com a dificuldade já calculada
    para cada lado — não é preciso o truque dos 20 pedidos do Draft."""
    saida = {}
    for j in sorted(fixtures, key=lambda x: (x.get("event") or 99, x.get("id", 0))):
        ev = j.get("event")
        if not ev or ev < desde or j.get("finished"):
            continue
        for casa in (True, False):
            eq = j["team_h"] if casa else j["team_a"]
            adv = j["team_a"] if casa else j["team_h"]
            dif = j.get("team_h_difficulty" if casa else "team_a_difficulty") or 3
            lista = saida.setdefault(str(eq), [])
            if len(lista) < 10:
                lista.append({"event": ev, "opponent": adv, "is_home": casa,
                              "difficulty": dif})
    return saida


def bola_parada_da_api(players):
    """Na clássica os cargos vêm preenchidos — não é preciso o ficheiro curado."""
    saida = {}
    for p in players:
        cargos = {}
        if p.get("penalties_order"):
            cargos["pen"] = p["penalties_order"]
        if p.get("direct_freekicks_order"):
            cargos["fk"] = p["direct_freekicks_order"]
        if p.get("corners_and_indirect_freekicks_order"):
            cargos["cantos"] = p["corners_and_indirect_freekicks_order"]
        if cargos:
            cargos["confianca"] = "alta"  # vem da fonte oficial
            saida[str(p["id"])] = cargos
    fd.registar("Bola parada (API clássica)", True, f"{len(saida)} jogadores com cargo")
    return saida


def fetch_jornadas(atual, anterior, fixtures):
    """Minutos e pontos por jornada, como no Draft (o formato é o mesmo).

    `equipas` guarda só quem já **terminou** o jogo dessa jornada: sem isso,
    um jogador cuja equipa joga na segunda-feira apareceria com 0 minutos no
    sábado e a projeção dele afundava sem razão."""
    if not atual:
        return {}
    por_evento = {}
    for j in fixtures:
        ev = j.get("event")
        if ev:
            por_evento.setdefault(ev, []).append(j)
    cache = (anterior or {}).get("jornadas") or {}
    saida = {}
    for ev in range(1, int(atual) + 1):
        chave = str(ev)
        guardada = cache.get(chave)
        # Uma jornada dada como terminada mas sem equipas registadas vem de uma
        # versão anterior com um erro: vale a pena voltar a pedi-la.
        if guardada and guardada.get("finalizada") and guardada.get("equipas"):
            saida[chave] = guardada
            continue
        try:
            live = get(f"/event/{ev}/live/")
        except Exception as exc:
            fd.registar(f"Jornada {ev}", False, exc)
            if guardada:
                saida[chave] = guardada
            continue
        stats = {}
        for eid, dados in fd._elementos_live(live):
            s = (dados or {}).get("stats") or dados or {}
            minutos, pontos = s.get("minutes") or 0, s.get("total_points") or 0
            if minutos or pontos:
                stats[str(eid)] = [minutos, pontos]
        jogos = por_evento.get(ev, [])
        # "Jogado" (90 minutos feitos) conta os minutos logo; "finalizada"
        # espera pela confirmação dos bónus antes de ir para cache.
        jogado = lambda j: j.get("finished") or j.get("finished_provisional")
        equipas = sorted({t for j in jogos if jogado(j)
                          for t in (j.get("team_h"), j.get("team_a")) if t})
        saida[chave] = {
            "finalizada": bool(jogos) and all(j.get("finished") for j in jogos),
            "equipas": equipas,
            "stats": stats,
        }
    if saida:
        fd.registar("Jornadas disputadas", True, f"{len(saida)} jornadas")
    return saida


def fetch_minha_equipa(entry_id, evento):
    """Plantel, dinheiro e chips — só com FPL_ENTRY_ID definido.

    As escolhas de uma jornada só existem depois do deadline; antes disso a API
    devolve 404 e ficamos apenas com os dados gerais da equipa."""
    if not entry_id:
        fd.registar("Equipa clássica", True, "sem FPL_ENTRY_ID: só análise geral")
        return None
    try:
        entry = get(f"/entry/{entry_id}/")
    except Exception as exc:
        fd.registar("Equipa clássica", False, exc)
        return None

    dados = {
        "id": entry.get("id"),
        "nome": entry.get("name"),
        "gestor": f'{entry.get("player_first_name", "")} {entry.get("player_last_name", "")}'.strip(),
        "pontos": entry.get("summary_overall_points"),
        "classificacao": entry.get("summary_overall_rank"),
        "valor": None, "banco": None, "transferencias_livres": None,
        "picks": [], "capitao": None, "vice": None, "chips_usados": [],
    }
    try:
        hist = get(f"/entry/{entry_id}/history/")
        dados["chips_usados"] = [{"chip": c.get("name"), "jornada": c.get("event")}
                                 for c in hist.get("chips", [])]
    except Exception:
        pass

    for ev in range(int(evento or 1), 0, -1):  # a última jornada com escolhas
        try:
            picks = get(f"/entry/{entry_id}/event/{ev}/picks/")
        except Exception:
            continue
        h = picks.get("entry_history") or {}
        dados.update({
            "jornada_picks": ev,
            "valor": (h.get("value") or 0) / 10,
            "banco": (h.get("bank") or 0) / 10,
            "picks": [{"id": p["element"], "posicao": p["position"],
                       "multiplicador": p["multiplier"]} for p in picks.get("picks", [])],
            "capitao": next((p["element"] for p in picks.get("picks", []) if p.get("is_captain")), None),
            "vice": next((p["element"] for p in picks.get("picks", []) if p.get("is_vice_captain")), None),
            "chip_ativo": picks.get("active_chip"),
        })
        break
    fd.registar("Equipa clássica", True,
                f'{dados["nome"] or entry_id}: {len(dados["picks"])} jogadores')
    return dados


def main():
    entry_id = os.environ.get("FPL_ENTRY_ID", "").strip() or None
    anterior = fd.load_anterior(OUT)

    bootstrap = get("/bootstrap-static/")
    fixtures = get("/fixtures/")
    fd.registar("API da FPL clássica", True,
                f'{len(bootstrap["elements"])} jogadores, {len(fixtures)} jogos')

    eventos = bootstrap["events"]
    atual = next((e["id"] for e in eventos if e.get("is_current")), None)
    proximo = next((e for e in eventos if e.get("is_next")), None) or \
        next((e for e in eventos if not e.get("finished")), None)
    game = {"current_event": atual, "next_event": proximo and proximo["id"]}

    nomes_clubes = {t["id"]: t["name"] for t in bootstrap["teams"]}
    campos = fd.PLAYER_FIELDS + CAMPOS_CLASSICA
    players = []
    for el in bootstrap["elements"]:
        if el.get("element_type", 0) > 4:
            continue  # "managers" não entram no modelo
        p = {k: el.get(k) for k in campos}
        p["owner"] = None
        p["news_new"] = False
        players.append(p)

    minha = fetch_minha_equipa(entry_id, atual or (proximo and proximo["id"]))
    meus_ids = {x["id"] for x in (minha or {}).get("picks", [])}
    if meus_ids:
        for p in players:
            if p["id"] in meus_ids:
                p["owner"] = minha["id"]

    feeds = fd.fetch_feeds_clubes()
    noticias = fd.fetch_noticias_mercado()
    meus = [p for p in players if p["owner"] is not None]
    clubes = sorted({(p["team"], nomes_clubes[p["team"]]) for p in meus}, key=lambda c: c[1])

    dados = {
        "modo": "classica",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "league_id": "classica",
        "game": game,
        "next_event": proximo and {
            "id": proximo["id"], "name": proximo["name"],
            "deadline_time": proximo["deadline_time"],
        },
        "league": {"name": "Fantasy Premier League", "scoring": "classic"},
        "entries": [{"id": minha["id"], "entry_id": minha["id"], "entry_name": minha["nome"],
                     "manager": minha["gestor"], "waiver_pick": None}] if minha else [],
        "standings": [],
        "diagnostico": fd.DIAGNOSTICO,
        "regras": {
            "scoring": achatar_pontuacao(bootstrap.get("game_config", {}).get("scoring")),
            "squad": {
                "size": bootstrap["game_settings"].get("squad_squadsize", 15),
                "play": bootstrap["game_settings"].get("squad_squadplay", 11),
                "min_play_GKP": 1, "max_play_GKP": 1,
                "min_play_DEF": 3, "max_play_DEF": 5,
                "min_play_MID": 2, "max_play_MID": 5,
                "min_play_FWD": 1, "max_play_FWD": 3,
                "team_limit": bootstrap["game_settings"].get("squad_team_limit", 3),
                "total_spend": bootstrap["game_settings"].get("squad_total_spend", 1000),
                "sell_on_fee": bootstrap["game_settings"].get("transfers_sell_on_fee", 0.5),
            },
        },
        "classica": {
            "equipa": minha,
            "chips": [{"nome": c.get("name"), "inicio": c.get("start_event"),
                       "fim": c.get("stop_event")} for c in bootstrap.get("chips", [])],
            "custo_transferencia": 4,
        },
        "teams": {str(t["id"]): {"name": t["name"], "short_name": t["short_name"]}
                  for t in bootstrap["teams"]},
        "players": players,
        "fixtures": calendario_por_clube(fixtures, (proximo and proximo["id"]) or 1),
        "jornadas": fetch_jornadas(atual, anterior, fixtures),
        "historico": fd.snapshot_historico(players, anterior, game),
        "preepoca": fd.fetch_preepoca(nomes_clubes, players),
        "bolaparada": bola_parada_da_api(bootstrap["elements"]),
        "ffs": fd.fetch_ffs(players, nomes_clubes),
        "transferencias": fd.extrair_transferencias(
            {**feeds, "Transfer Centre": noticias}, players, nomes_clubes),
        "conferencias": {"equipa": minha and minha["nome"],
                         "clubes": fd.fetch_conferencias(clubes, meus, feeds)},
        "mercado": {"noticias": noticias, "transacoes": []},
    }

    os.makedirs(fd.OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {OUT} ({os.path.getsize(OUT)} bytes, {len(players)} jogadores"
          f'{", com a tua equipa" if minha and minha["picks"] else ""})')


if __name__ == "__main__":
    main()
