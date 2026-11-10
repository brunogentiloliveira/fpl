# -*- coding: utf-8 -*-
"""Teste 2 — o método proposto, simulado no passado.
Na jornada de corte c: tiram-se os 6 melhores de cada posição (pontos até c), vê-se que índices
têm em comum (5 dos 6 no top 10% da posição) e dá-se a cada outro jogador uma nota = percentil
médio nesses índices. Depois vê-se quem pontuou mais nas jornadas c+1..10."""
import json, sys, io, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, sys.argv[2])
from comum import *
api, S = sys.argv[1], sys.argv[2]
b, live = carregar(api)
E = {e["id"]: e for e in b["elements"]}
linhas = json.load(open(S + "/linhas.json", encoding="utf-8"))
pred = {(r["id"], r["t"]): r["pred"] for r in linhas}
INDICES = ["minutes", "starts", "goals_scored", "assists", "clean_sheets", "saves", "bonus", "bps",
           "influence", "creativity", "threat", "ict_index", "expected_goals", "expected_assists",
           "expected_goal_involvements", "clearances_blocks_interceptions", "recoveries", "tackles",
           "defensive_contribution"]
POOL = {1: 14, 2: 35, 3: 35, 4: 21}   # quantos de cada posição têm dono numa liga de 7
K = 5
tot = collections.defaultdict(lambda: collections.defaultdict(list))
rhos = collections.defaultdict(lambda: collections.defaultdict(list))
comuns_vistos = collections.defaultdict(list)
for c in (4, 5, 6):
    for pos in (1, 2, 3, 4):
        pop = []
        for pid, e in E.items():
            if e["element_type"] != pos: continue
            a = acumulado(live, pid, c)
            if a["minutes"] <= 0: continue
            fut = acumulado(live, pid, 10, c + 1)["total_points"] / (10 - c)
            pop.append({"id": pid, "nome": e["web_name"], "a": a, "fut": fut,
                        "pred": pred.get((pid, c + 1), 0.0)})
        n10 = max(3, round(0.10 * len(pop)))
        pop.sort(key=lambda x: -x["a"]["total_points"])
        top6 = pop[:6]
        def lugar(x, k):
            return 1 + sum(1 for o in pop if o["a"][k] > x["a"][k])
        usar = [k for k in INDICES if not (k == "saves" and pos != 1)]
        comuns = [k for k in usar if sum(1 for x in top6 if lugar(x, k) <= n10) >= 5
                  and len(set(o["a"][k] for o in pop)) > 3]
        comuns_vistos[pos].append((c, [ABR[k] for k in comuns]))
        if not comuns: continue
        def perc(x, k):
            return 1 - (lugar(x, k) - 1) / len(pop)
        for x in pop:
            x["perfil"] = sum(perc(x, k) for k in comuns) / len(comuns)
        # candidatos: fora dos que teriam dono (os N melhores por pontos até c)
        cand = pop[POOL[pos]:]
        metodos = {"perfil dos 6 melhores": lambda x: x["perfil"],
                   "pontos até ao corte": lambda x: x["a"]["total_points"],
                   "ICT sozinho": lambda x: x["a"]["ict_index"],
                   "MODELO": lambda x: x["pred"]}
        for nome, f in metodos.items():
            esc = sorted(cand, key=lambda x: -f(x))[:K]
            tot[pos][nome].append(sum(x["fut"] for x in esc) / K)
            r = spearman([f(x) for x in cand], [x["fut"] for x in cand])
            if r is not None: rhos[pos][nome].append(r)
        tot[pos]["média dos candidatos"].append(sum(x["fut"] for x in cand) / len(cand))
        melhores = sorted(cand, key=lambda x: -x["fut"])[:K]
        tot[pos]["teto (sabendo o futuro)"].append(sum(x["fut"] for x in melhores) / K)

print("Índices em comum nos 6 melhores (5 dos 6 no top 10%), por corte:")
for pos in (1, 2, 3, 4):
    for c, ks in comuns_vistos[pos]:
        print(f"  {POS[pos]} corte J{c}: {', '.join(ks) or '(nenhum)'}")
print()
print(f"Pontos por jornada, DEPOIS do corte, dos {K} escolhidos por cada método entre os jogadores")
print("que estariam livres (fora dos 14/35/35/21 melhores de cada posição). Média dos cortes J4, J5 e J6.")
ordem = ["perfil dos 6 melhores", "pontos até ao corte", "ICT sozinho", "MODELO", "média dos candidatos", "teto (sabendo o futuro)"]
print("método".ljust(26) + "".join(POS[p].rjust(7) for p in (1, 2, 3, 4)) + "   todas")
for nome in ordem:
    vals = [sum(tot[p][nome]) / len(tot[p][nome]) if tot[p][nome] else float("nan") for p in (1, 2, 3, 4)]
    print(nome.ljust(26) + "".join(f"{v:7.2f}" for v in vals) + f"{sum(vals)/4:8.2f}")
print()
print("Acerto na ordem (ρ) entre os candidatos livres, média dos cortes:")
for nome in ordem[:4]:
    vals = [sum(rhos[p][nome]) / len(rhos[p][nome]) if rhos[p][nome] else float("nan") for p in (1, 2, 3, 4)]
    print(nome.ljust(26) + "".join(f"{v:7.3f}" for v in vals) + f"{sum(vals)/4:8.3f}")
