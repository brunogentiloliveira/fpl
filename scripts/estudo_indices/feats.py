# -*- coding: utf-8 -*-
"""Índices a mais: por 90 minutos, da equipa, do adversário e da multidão (API clássica).
Tudo calculado só com o que se sabia antes da jornada t."""
import json, collections
from comum import *

NOMES = {
 "pts90": "Pontos por 90", "xg90": "xG por 90", "xa90": "xA por 90", "xgi90": "xGI por 90",
 "xgc90": "xG sofrido por 90 (−)", "bps90": "BPS por 90", "ict90": "ICT por 90",
 "infl90": "Influence por 90", "cria90": "Creativity por 90", "amea90": "Threat por 90",
 "dc90": "Contrib. def. por 90", "def90": "Defesas por 90",
 "eq_gf": "Equipa: golos marcados/jogo", "eq_ga": "Equipa: golos sofridos/jogo (−)",
 "eq_cs": "Equipa: balizas a zero", "eq_xg": "Equipa: xG/jogo", "eq_xgc": "Equipa: xG sofrido/jogo (−)",
 "eq_ppj": "Equipa: pontos na liga/jogo",
 "adv_xg": "Adversário: xG/jogo (−)", "adv_xgc": "Adversário: xG sofrido/jogo",
 "adv_ppj": "Adversário: pontos na liga/jogo (−)", "casa": "Joga em casa",
 "sel": "Equipas que o têm (clássica)", "bal": "Saldo de transferências da semana",
 "tin": "Transferências de entrada", "tout": "Transferências de saída (−)",
 "val": "Preço na clássica", "dval": "Subida de preço desde a J1",
}

def construir(api, linhas, n=10):
    b, live = carregar(api, n)
    E = {e["id"]: e for e in b["elements"]}
    hist = json.load(open(api + "/classica_historia.json", encoding="utf-8"))
    crowd = {}
    for e in b["elements"]:
        for h in hist.get(str(e["code"]), []):
            crowd.setdefault((e["id"], h["round"]), h)
    v1 = {}
    for (pid, r), h in crowd.items():
        if pid not in v1 or r < v1[pid][0]:
            v1[pid] = (r, h["value"])
    # equipa por jornada
    eq = collections.defaultdict(dict)   # eq[g][team] = {...}
    adv = {}                              # adv[(g, team)] = (opp, casa)
    for g in range(1, n + 1):
        l = json.load(open(f"{api}/live{g}.json", encoding="utf-8"))
        xg = collections.defaultdict(float); xgc = collections.defaultdict(float)
        for pid, s in live[g].items():
            e = E.get(pid)
            if not e: continue
            xg[e["team"]] += float(s.get("expected_goals") or 0)
            xgc[e["team"]] = max(xgc[e["team"]], float(s.get("expected_goals_conceded") or 0))
        for f in l["fixtures"]:
            h, a, hs, as_ = f["team_h"], f["team_a"], f["team_h_score"], f["team_a_score"]
            adv[(g, h)] = (a, 1); adv[(g, a)] = (h, 0)
            if hs is None or as_ is None: continue
            for tm, gf, ga in ((h, hs, as_), (a, as_, hs)):
                eq[g][tm] = {"gf": gf, "ga": ga, "cs": 1.0 if ga == 0 else 0.0, "xg": xg[tm], "xgc": xgc[tm],
                             "ppj": 3.0 if gf > ga else (1.0 if gf == ga else 0.0)}
    def media_eq(tm, t, k):
        vs = [eq[g][tm][k] for g in range(1, t) if tm in eq[g]]
        return sum(vs) / len(vs) if vs else None
    cache = {}
    for r in linhas:
        pid, t = r["id"], r["t"]
        if (pid, t) not in cache:
            cache[(pid, t)] = acumulado(live, pid, t - 1)
        a = cache[(pid, t)]
        r["ix"] = a
        m = a["minutes"]
        x = {}
        p90 = lambda v: (v / m * 90) if m >= 180 else None
        x["pts90"] = p90(a["total_points"]); x["xg90"] = p90(a["expected_goals"]); x["xa90"] = p90(a["expected_assists"])
        x["xgi90"] = p90(a["expected_goal_involvements"]); x["xgc90"] = p90(a["expected_goals_conceded"])
        x["bps90"] = p90(a["bps"]); x["ict90"] = p90(a["ict_index"]); x["infl90"] = p90(a["influence"])
        x["cria90"] = p90(a["creativity"]); x["amea90"] = p90(a["threat"]); x["dc90"] = p90(a["defensive_contribution"])
        x["def90"] = p90(a["saves"]) if r["pos"] == 1 else None
        tm = E[pid]["team"]
        for k in ("gf", "ga", "cs", "xg", "xgc", "ppj"):
            x["eq_" + k] = media_eq(tm, t, k)
        o = adv.get((t, tm))
        if o:
            x["adv_xg"] = media_eq(o[0], t, "xg"); x["adv_xgc"] = media_eq(o[0], t, "xgc")
            x["adv_ppj"] = media_eq(o[0], t, "ppj"); x["casa"] = o[1]
        h = crowd.get((pid, t))
        if h:
            x["sel"] = h["selected"]; x["bal"] = h["transfers_balance"]; x["tin"] = h["transfers_in"]
            x["tout"] = h["transfers_out"]; x["val"] = h["value"]
            x["dval"] = h["value"] - v1[pid][1] if pid in v1 else None
        r["x"] = x
        r["team"] = tm
    return b, live, E
