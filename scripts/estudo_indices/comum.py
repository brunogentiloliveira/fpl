# -*- coding: utf-8 -*-
"""Funções partilhadas pelo estudo dos índices."""
import json, random
POS = {1: "GR", 2: "DEF", 3: "MED", 4: "AV"}
MATCH = ["minutes", "starts", "goals_scored", "assists", "clean_sheets", "goals_conceded", "saves",
         "bonus", "bps", "influence", "creativity", "threat", "ict_index",
         "expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded",
         "clearances_blocks_interceptions", "recoveries", "tackles", "defensive_contribution", "total_points"]
ABR = {"minutes": "Minutos", "starts": "Titularidades", "ppg": "Pts por jogo", "form": "Forma",
       "goals_scored": "Golos", "assists": "Assistências", "clean_sheets": "Balizas a zero",
       "goals_conceded": "Golos sofridos", "saves": "Defesas", "bonus": "Bónus", "bps": "BPS",
       "influence": "Influence", "creativity": "Creativity", "threat": "Threat", "ict_index": "ICT",
       "expected_goals": "xG", "expected_assists": "xA", "expected_goal_involvements": "xGI",
       "expected_goals_conceded": "xG sofrido", "clearances_blocks_interceptions": "CBI",
       "recoveries": "Recuperações", "tackles": "Desarmes", "defensive_contribution": "Contrib. defensiva",
       "total_points": "Pontos (total)", "pred": "MODELO", "draft_rank": "Draft rank"}

def carregar(api, n=10):
    b = json.load(open(api + "/bootstrap.json", encoding="utf-8"))
    live = {}
    for g in range(1, n + 1):
        l = json.load(open(f"{api}/live{g}.json", encoding="utf-8"))
        live[g] = {int(k): v["stats"] for k, v in l["elements"].items()}
    return b, live

def acumulado(live, pid, ate, de=1):
    """Totais de cada índice nas jornadas de..ate (inclusive), mais PPJ e forma."""
    tot = {k: 0.0 for k in MATCH}
    jogos = 0
    pts_gw = []
    for g in range(de, ate + 1):
        s = live[g].get(pid)
        if not s:
            pts_gw.append(0); continue
        for k in MATCH:
            tot[k] += float(s.get(k) or 0)
        if s["minutes"] > 0:
            jogos += 1
        pts_gw.append(s["total_points"])
    tot["ppg"] = tot["total_points"] / jogos if jogos else 0.0
    ult = pts_gw[-4:]
    tot["form"] = sum(ult) / len(ult) if ult else 0.0
    tot["jogos"] = jogos
    return tot

def postos(v):
    ordem = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(ordem):
        j = i
        while j + 1 < len(ordem) and v[ordem[j + 1]] == v[ordem[i]]:
            j += 1
        for k in range(i, j + 1):
            r[ordem[k]] = (i + j) / 2.0
        i = j + 1
    return r

def pearson(a, b):
    n = len(a)
    if n < 3: return None
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a); db = sum((y - mb) ** 2 for y in b)
    if da <= 0 or db <= 0: return None
    return num / (da * db) ** 0.5

def spearman(a, b):
    return pearson(postos(a), postos(b))

def resid(y, x):
    """Resíduo de y regredido em x (linear, com constante)."""
    n = len(x); mx, my = sum(x) / n, sum(y) / n
    sxx = sum((v - mx) ** 2 for v in x)
    if sxx <= 0: return [v - my for v in y]
    bcoef = sum((xv - mx) * (yv - my) for xv, yv in zip(x, y)) / sxx
    return [yv - my - bcoef * (xv - mx) for xv, yv in zip(x, y)]

def spearman_parcial(a, y, c):
    """Ordem de `a` contra `y`, descontado o que `c` já explica."""
    ra, ry, rc = postos(a), postos(y), postos(c)
    return pearson(resid(ra, rc), resid(ry, rc))
