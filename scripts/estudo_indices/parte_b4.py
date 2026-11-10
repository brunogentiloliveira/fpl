# -*- coding: utf-8 -*-
"""Teste 4: juntar um índice ao modelo melhora as previsões em jornadas que não entraram no ajuste?
previsão' = previsão + c · z(índice) · (minutos esperados/90), com c ajustado nas OUTRAS jornadas.
Uso: parte_b4.py api S "2:clean_sheets 1:total_points ..."   (posição:índice)"""
import json, sys, io, random, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, sys.argv[2])
from comum import *
import feats
api, S = sys.argv[1], sys.argv[2]
spec = [(int(a.split(":")[0]), a.split(":")[1]) for a in sys.argv[3].split()]
linhas = [r for r in json.load(open(S + "/linhas.json", encoding="utf-8")) if r["t"] >= 4]
feats.construir(api, linhas)
def val(r, k):
    return r["x"].get(k) if k in feats.NOMES else r["ix"].get(k)
def nome(k):
    return feats.NOMES.get(k) or ABR.get(k, k)
LIM = {1: (1, 1), 2: (3, 5), 3: (2, 5), 4: (1, 3)}
def onze(plantel, campo):
    por = collections.defaultdict(list)
    for r in plantel: por[r["pos"]].append(r)
    xi = []
    for p in (1, 2, 3, 4):
        por[p].sort(key=lambda r: -r[campo]); xi += por[p][:LIM[p][0]]
    resto = sorted((r for r in plantel if r not in xi), key=lambda r: -r[campo])
    cont = collections.Counter(r["pos"] for r in xi)
    for r in resto:
        if len(xi) >= 11: break
        if cont[r["pos"]] < LIM[r["pos"]][1]:
            xi.append(r); cont[r["pos"]] += 1
    return sum(r["real"] for r in xi)
def rho_medio(rows, campo):
    por_t = collections.defaultdict(list)
    for r in rows: por_t[r["t"]].append(r)
    s = n = 0
    for rs in por_t.values():
        v = spearman([r[campo] for r in rs], [r["real"] for r in rs])
        if v is not None: s += v * len(rs); n += len(rs)
    return s / n if n else float("nan")
random.seed(3)
for r in linhas: r["novo"] = r["pred"]
for pos, k in spec:
    rows = [r for r in linhas if r["pos"] == pos]
    # z dentro de (jornada, posição), entre quem se espera que jogue
    for t in set(r["t"] for r in rows):
        base = [r for r in rows if r["t"] == t and r["xmin"] >= 30 and val(r, k) is not None]
        vs = [val(r, k) for r in base]
        m = sum(vs) / len(vs); sd = (sum((v - m) ** 2 for v in vs) / len(vs)) ** 0.5 or 1.0
        for r in rows:
            if r["t"] == t:
                v = val(r, k)
                r["A"] = ((v - m) / sd) * (r["xmin"] / 90) if (v is not None and r["xmin"] >= 30) else 0.0
    cs = []
    for t in sorted(set(r["t"] for r in rows)):
        tr = [r for r in rows if r["t"] != t and r["conhecido"]]
        saa = sum(r["A"] ** 2 for r in tr)
        c = sum(r["A"] * (r["real"] - r["pred"]) for r in tr) / saa if saa else 0.0
        cs.append(c)
        for r in rows:
            if r["t"] == t: r["novo"] = r["pred"] + c * r["A"]
    av = [r for r in rows if r["conhecido"]]
    tit = [r for r in av if r["xmin"] >= 60]
    rm = lambda rs, f: (sum((r["real"] - r[f]) ** 2 for r in rs) / len(rs)) ** 0.5
    por_jog = collections.defaultdict(list)
    for r in av: por_jog[r["id"]].append(r)
    ids = list(por_jog); d1 = []; d2 = []
    for _ in range(400):
        am = [x for _ in ids for x in por_jog[random.choice(ids)]]
        d1.append(rm(am, "pred") - rm(am, "novo"))
        amt = [r for r in am if r["xmin"] >= 60]
        d2.append(rho_medio(amt, "novo") - rho_medio(amt, "pred"))
    d1.sort(); d2.sort()
    print(f"{POS[pos]} + {nome(k)}:  c = {sum(cs)/len(cs):+.2f} (por jornada de fora: {min(cs):+.2f} a {max(cs):+.2f})")
    print(f"   erro (RMSE), todos: {rm(av,'pred'):.3f} -> {rm(av,'novo'):.3f}   ganho IC95 [{d1[10]:+.3f}, {d1[389]:+.3f}]  P(pior)={sum(x<0 for x in d1)/len(d1):.2f}")
    print(f"   ordem (ρ) entre titulares esperados: {rho_medio(tit,'pred'):.3f} -> {rho_medio(tit,'novo'):.3f}   ganho IC95 [{d2[10]:+.3f}, {d2[389]:+.3f}]  P(pior)={sum(x<0 for x in d2)/len(d2):.2f}")
# o onze, com tudo junto
donos = sorted(set(r["dono"] for r in linhas if r["dono"] is not None))
a = b = o = n = 0; dif = []
for t in sorted(set(r["t"] for r in linhas)):
    for d in donos:
        pl = [r for r in linhas if r["t"] == t and r["dono"] == d]
        if len(pl) < 11: continue
        x, y = onze(pl, "pred"), onze(pl, "novo")
        a += x; b += y; o += onze(pl, "real"); n += 1; dif.append(y - x)
if n:
    dif.sort()
    mud = sum(1 for v in dif if v != 0)
    print(f"ONZE ({n} onzes dos planteis atuais): modelo {a/n:.2f} -> com o(s) índice(s) {b/n:.2f}  (teto {o/n:.1f}); "
          f"mudou o resultado em {mud} onzes, {sum(1 for v in dif if v > 0)} para melhor e {sum(1 for v in dif if v < 0)} para pior")
