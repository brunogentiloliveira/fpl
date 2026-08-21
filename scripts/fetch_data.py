#!/usr/bin/env python3
"""Recolhe dados da API do FPL Draft e gera site/data/data.json.

Uso: LEAGUE_ID=12258 python scripts/fetch_data.py
Só usa a stdlib. A API é pública e não requer autenticação.
"""
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

BASE = "https://draft.premierleague.com/api"
SKY_RSS = "https://www.skysports.com/rss/12691"  # Sky Sports Transfer Centre
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "data")

PLAYER_FIELDS = (
    "id", "web_name", "first_name", "second_name", "team", "element_type",
    "draft_rank", "total_points", "status", "news", "news_added",
    "chance_of_playing_next_round", "form", "points_per_game",
)


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


def fetch_noticias_mercado():
    """Feed de transferências da Sky. Nunca deve partir a recolha principal."""
    try:
        req = urllib.request.Request(SKY_RSS, headers={"User-Agent": "fpl-draft-dashboard"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
        itens = []
        for item in root.iter("item"):
            titulo = (item.findtext("title") or "").strip()
            if not titulo:
                continue
            baixa = titulo.lower()
            itens.append({
                "titulo": titulo,
                "link": (item.findtext("link") or "").strip(),
                "data": rss_data_para_iso(item.findtext("pubDate")),
                "rumor": baixa.startswith("papers") or "rumour" in baixa,
            })
        return itens[:20]
    except Exception as exc:
        print(f"Aviso: RSS da Sky falhou ({exc}); a seguir sem notícias externas.",
              file=sys.stderr)
        return []


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
        "mercado": {
            "noticias": fetch_noticias_mercado(),
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
