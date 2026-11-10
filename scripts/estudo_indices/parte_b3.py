# -*- coding: utf-8 -*-
"""Teste 3: os índices a mais (por 90, equipa, adversário, multidão) acrescentam ao modelo?"""
import json, sys, io, random, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, sys.argv[2])
from comum import *
import feats
api, S = sys.argv[1], sys.argv[2]
XMIN = float(sys.argv[3]) if len(sys.argv) > 3 else 60
todas = [r for r in json.load(open(S + "/linhas.json", encoding="utf-8")) if r["conhecido"] and r["t"] >= 4]
feats.construir(api, todas)
json.dump([{k: v for k, v in r.items() if k != "ix"} for r in todas], open(S + "/linhas_x.json", "w", encoding="utf-8"))

def medidas(rows, k):
    por_t = collections.defaultdict(list)
    for r in rows:
        if r["x"].get(k) is not None: por_t[r["t"]].append(r)
    s1 = s2 = n1 = n2 = 0
    for t, rs in por_t.items():
        if len(rs) < 8: continue
        a = [r["x"][k] for r in rs]; y = [r["real"] for r in rs]; c = [r["pred"] for r in rs]
        rho = spearman(a, y); rp = spearman_parcial(a, y, c)
        if rho is not None: s1 += rho * len(rs); n1 += len(rs)
        if rp is not None: s2 += rp * len(rs); n2 += len(rs)
    return (s1 / n1 if n1 else None, s2 / n2 if n2 else None, n1)

random.seed(5)
B = 300
print(f"Só quem o modelo espera com {XMIN:.0f}+ minutos; jornadas 4 a 10. (−) = menos é melhor, espera-se sinal negativo.")
nfora = ntestes = 0
for pos in (1, 2, 3, 4):
    rows = [r for r in todas if r["pos"] == pos and r["xmin"] >= XMIN]
    por_jog = collections.defaultdict(list)
    for r in rows: por_jog[r["id"]].append(r)
    ids = list(por_jog)
    amostras = [[x for _ in ids for x in por_jog[random.choice(ids)]] for _ in range(B)]
    print(f"\n=== {POS[pos]} — {len(rows)} previsões de {len(ids)} jogadores ===")
    print("índice".ljust(36) + "ρ sozinho   além do modelo [IC95]")
    res = []
    for k in feats.NOMES:
        rho, rp, n = medidas(rows, k)
        if rho is None or rp is None: continue
        bs = sorted(x for x in (medidas(a, k)[1] for a in amostras) if x is not None)
        if len(bs) < 50: continue
        lo, hi = bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs)) - 1]
        res.append((abs(rp), k, rho, rp, lo, hi))
    for _, k, rho, rp, lo, hi in sorted(res, reverse=True):
        fora = lo > 0 or hi < 0
        ntestes += 1; nfora += fora
        print(f"{feats.NOMES[k].ljust(36)}{rho:+.3f}      {rp:+.3f} [{lo:+.3f}, {hi:+.3f}]{'  <-- fora do ruído' if fora else ''}")
print(f"\n{ntestes} testes, {nfora} fora do ruído; só por acaso esperavam-se ~{ntestes*0.05:.0f}.")
