# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
api = sys.argv[1]
b = json.load(open(api + "/bootstrap.json", encoding="utf-8"))
E = b["elements"]
T = {t["id"]: t["short_name"] for t in b["teams"]}
POS = {1: "GR", 2: "DEF", 3: "MED", 4: "AV"}
f = lambda v: float(v) if v not in (None, "") else 0.0
IDX = ["minutes", "starts", "points_per_game", "form", "goals_scored", "assists", "clean_sheets",
       "saves", "bonus", "bps", "influence", "creativity", "threat", "ict_index",
       "expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded",
       "clearances_blocks_interceptions", "recoveries", "tackles", "defensive_contribution"]
ABR = {"minutes": "Min", "starts": "Tit", "points_per_game": "PPJ", "form": "Forma", "goals_scored": "Gol",
       "assists": "Ass", "clean_sheets": "BZ", "saves": "Def", "bonus": "Bón", "bps": "BPS",
       "influence": "Infl", "creativity": "Cria", "threat": "Amea", "ict_index": "ICT",
       "expected_goals": "xG", "expected_assists": "xA", "expected_goal_involvements": "xGI",
       "expected_goals_conceded": "xGC", "clearances_blocks_interceptions": "CBI",
       "recoveries": "Rec", "tackles": "Des", "defensive_contribution": "CDef"}
MENOR_MELHOR = {"expected_goals_conceded"}
for pos in (1, 2, 3, 4):
    pop = [e for e in E if e["element_type"] == pos and e["minutes"] > 0]
    top = sorted(pop, key=lambda e: -e["total_points"])[:6]
    print(f"\n=== {POS[pos]} — {len(pop)} jogadores com minutos; lugar de cada um NA POSIÇÃO, por total ===")
    def lugar(e, k):
        v = f(e[k])
        if k in MENOR_MELHOR:
            return 1 + sum(1 for o in pop if f(o[k]) < v and o["minutes"] >= 450) if e["minutes"] >= 450 else None
        return 1 + sum(1 for o in pop if f(o[k]) > v)
    cols = [k for k in IDX if not (pos != 1 and k == "saves")]
    print("jogador".ljust(14) + "pts " + " ".join(ABR[k].rjust(5) for k in cols))
    for e in top:
        print(f"{e['web_name'][:13].ljust(14)}{str(e['total_points']).rjust(3)} " +
              " ".join(str(lugar(e, k) or "-").rjust(5) for k in cols))
    n10 = max(1, round(len(pop) * 0.10))
    comuns = []
    for k in cols:
        ls = [lugar(e, k) for e in top]
        dentro = sum(1 for l in ls if l is not None and l <= n10)
        med = sorted(l for l in ls if l is not None)[len(ls) // 2 - 0] if all(l is not None for l in ls) else None
        comuns.append((dentro, k, sorted(ls)))
    print(f"-> em quantos dos 6 o índice está no top 10% da posição (top {n10}):")
    print("   " + ", ".join(f"{ABR[k]} {d}/6" for d, k, _ in sorted(comuns, key=lambda x: -x[0])))
