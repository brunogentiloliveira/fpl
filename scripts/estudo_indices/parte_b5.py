# -*- coding: utf-8 -*-
"""Teste 5: (a) os candidatos com o intervalo reamostrado por CLUBE; (b) escolha entre livres."""
import json, sys, io, random, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, sys.argv[2])
from comum import *
import feats
api, S = sys.argv[1], sys.argv[2]
linhas = [r for r in json.load(open(S + "/linhas.json", encoding="utf-8")) if r["t"] >= 4]
feats.construir(api, linhas)
def val(r, k): return r["x"].get(k) if k in feats.NOMES else r["ix"].get(k)
def nome(k): return feats.NOMES.get(k) or ABR.get(k, k)
def parcial(rows, k):
    por_t = collections.defaultdict(list)
    for r in rows:
        if val(r, k) is not None: por_t[r["t"]].append(r)
    s = n = 0
    for rs in por_t.values():
        if len(rs) < 8: continue
        rp = spearman_parcial([val(r, k) for r in rs], [r["real"] for r in rs], [r["pred"] for r in rs])
        if rp is not None: s += rp * len(rs); n += len(rs)
    return s / n if n else None
CAND = {1: ["total_points", "ppg", "sel", "dval"],
        2: ["clean_sheets", "total_points", "eq_cs", "tin", "dval", "bal", "ict_index", "bps"],
        3: ["adv_xg", "adv_ppj", "val", "infl90"], 4: ["expected_assists", "bal"]}
random.seed(21)
print("(a) Além do modelo, entre titulares esperados — intervalo por jogador e por CLUBE (20 clubes)")
for pos in (1, 2, 3, 4):
    rows = [r for r in linhas if r["pos"] == pos and r["conhecido"] and r["xmin"] >= 60]
    por_clube = collections.defaultdict(list)
    for r in rows: por_clube[r["team"]].append(r)
    clubes = list(por_clube)
    am = [[x for _ in clubes for x in por_clube[random.choice(clubes)]] for _ in range(400)]
    for k in CAND[pos]:
        rp = parcial(rows, k)
        bs = sorted(x for x in (parcial(a, k) for a in am) if x is not None)
        lo, hi = bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs)) - 1]
        print(f"  {POS[pos]:<4}{nome(k):<36}{rp:+.3f}  por clube [{lo:+.3f}, {hi:+.3f}]{'  <-- fora do ruído' if lo > 0 or hi < 0 else ''}")

print()
print("(b) Escolha entre livres, jornada a jornada (4 a 10): os 5 melhores de cada posição entre quem")
print("    estaria livre (fora dos 14/35/35/21 com mais pontos até aí). Pontos reais nessa jornada, por jogador.")
POOL = {1: 14, 2: 35, 3: 35, 4: 21}
def z_por_t(rows, k):
    out = {}
    for t in set(r["t"] for r in rows):
        base = [r for r in rows if r["t"] == t and r["xmin"] >= 30 and val(r, k) is not None]
        vs = [val(r, k) for r in base]
        m = sum(vs) / len(vs); sd = (sum((v - m) ** 2 for v in vs) / len(vs)) ** 0.5 or 1.0
        for r in rows:
            if r["t"] == t:
                v = val(r, k)
                out[(r["id"], t)] = ((v - m) / sd) * (r["xmin"] / 90) if (v is not None and r["xmin"] >= 30) else 0.0
    return out
for pos, ks in ((1, ["total_points", "sel"]), (2, ["clean_sheets", "total_points", "tin", "dval"]),
                (3, ["adv_xg", "total_points"]), (4, ["total_points", "bal"])):
    rows = [r for r in linhas if r["pos"] == pos]
    ts = sorted(set(r["t"] for r in rows))
    livres = {}
    for t in ts:
        rs = sorted((r for r in rows if r["t"] == t), key=lambda r: -r["ix"]["total_points"])
        livres[t] = rs[POOL[pos]:]
    def picks(score):
        tot = []
        for t in ts:
            esc = sorted(livres[t], key=lambda r: -score(r))[:5]
            tot.append(sum(r["real"] for r in esc) / 5)
        return tot
    base = picks(lambda r: r["pred"])
    media_pool = sum(sum(r["real"] for r in livres[t]) / len(livres[t]) for t in ts) / len(ts)
    teto = sum(sum(sorted((r["real"] for r in livres[t]), reverse=True)[:5]) / 5 for t in ts) / len(ts)
    print(f"  {POS[pos]}: só o modelo {sum(base)/len(base):.2f}   (média dos livres {media_pool:.2f}, teto {teto:.2f})")
    for k in ks:
        A = z_por_t(rows, k)
        novo = {}
        for t in ts:
            tr = [r for r in rows if r["t"] != t and r["conhecido"]]
            saa = sum(A[(r["id"], r["t"])] ** 2 for r in tr)
            c = sum(A[(r["id"], r["t"])] * (r["real"] - r["pred"]) for r in tr) / saa if saa else 0.0
            for r in rows:
                if r["t"] == t: novo[(r["id"], t)] = r["pred"] + c * A[(r["id"], t)]
        com = picks(lambda r: novo[(r["id"], r["t"])])
        so = picks(lambda r: val(r, k) if val(r, k) is not None else -1e9)
        d = [x - y for x, y in zip(com, base)]
        print(f"      modelo + {nome(k):<30} {sum(com)/len(com):.2f}  (melhor em {sum(1 for v in d if v > 0)} jornadas, pior em {sum(1 for v in d if v < 0)}, igual em {sum(1 for v in d if v == 0)})"
              f"   | só o índice: {sum(so)/len(so):.2f}")
