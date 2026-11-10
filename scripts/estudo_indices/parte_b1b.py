# -*- coding: utf-8 -*-
"""Teste 1: cada índice, medido ANTES da jornada t, prevê os pontos da jornada t?
E acrescenta alguma coisa à ordem que o modelo já dá?"""
import json, sys, io, random, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, sys.argv[2])
from comum import *
api, S = sys.argv[1], sys.argv[2]
b, live = carregar(api)
XMIN = float(sys.argv[3]) if len(sys.argv) > 3 else 0
linhas = [r for r in json.load(open(S + "/linhas.json", encoding="utf-8")) if r["conhecido"] and r["t"] >= 4 and r["xmin"] >= XMIN]
INDICES = ["total_points", "ppg", "form", "minutes", "starts", "goals_scored", "assists", "clean_sheets",
           "saves", "bonus", "bps", "influence", "creativity", "threat", "ict_index",
           "expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded",
           "clearances_blocks_interceptions", "recoveries", "tackles", "defensive_contribution"]
cache = {}
def idx(pid, t):
    if (pid, t) not in cache:
        cache[(pid, t)] = acumulado(live, pid, t - 1)
    return cache[(pid, t)]
for r in linhas:
    r["ix"] = idx(r["id"], r["t"])

def medidas(rows, k):
    """(ρ com os pontos, ρ parcial dado o modelo), média pesada por (jornada)."""
    por_t = collections.defaultdict(list)
    for r in rows: por_t[r["t"]].append(r)
    s1 = s2 = n1 = n2 = 0
    for t, rs in por_t.items():
        if len(rs) < 8: continue
        a = [r["pred"] if k == "pred" else r["ix"][k] for r in rs]
        y = [r["real"] for r in rs]
        c = [r["pred"] for r in rs]
        rho = spearman(a, y)
        if rho is not None: s1 += rho * len(rs); n1 += len(rs)
        if k != "pred":
            rp = spearman_parcial(a, y, c)
            if rp is not None: s2 += rp * len(rs); n2 += len(rs)
    return (s1 / n1 if n1 else None, s2 / n2 if n2 else None)

random.seed(11)
B = 300
print(f"[só quem o modelo espera com {XMIN:.0f}+ minutos] Jornadas previstas: 4 a 10. ρ = acerto na ordem (−1 a 1). 'além do modelo' = o que o índice ainda")
print("ordena depois de descontado o que o modelo já diz; entre [] o IC95 (reamostragem por jogador).")
for pos in (1, 2, 3, 4):
    rows = [r for r in linhas if r["pos"] == pos]
    por_jog = collections.defaultdict(list)
    for r in rows: por_jog[r["id"]].append(r)
    ids = list(por_jog)
    amostras = [[x for _ in ids for x in por_jog[random.choice(ids)]] for _ in range(B)]
    base = medidas(rows, "pred")[0]
    print(f"\n=== {POS[pos]} — {len(rows)} previsões de {len(ids)} jogadores — MODELO: ρ = {base:.3f} ===")
    print("índice".ljust(20) + "ρ sozinho   além do modelo [IC95]")
    res = []
    for k in INDICES:
        if k == "saves" and pos != 1: continue
        rho, rp = medidas(rows, k)
        if rho is None: continue
        bs = sorted(x for x in (medidas(a, k)[1] for a in amostras) if x is not None)
        lo, hi = (bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs)) - 1]) if len(bs) > 20 else (None, None)
        res.append((rp if rp is not None else 0, k, rho, rp, lo, hi))
    for _, k, rho, rp, lo, hi in sorted(res, reverse=True):
        marca = "  <-- fora do ruído" if lo is not None and (lo > 0 or hi < 0) else ""
        print(f"{ABR[k].ljust(20)}{rho:+.3f}      {rp:+.3f} [{lo:+.3f}, {hi:+.3f}]{marca}")
