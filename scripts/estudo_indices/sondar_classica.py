import json, sys, io, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "https://fantasy.premierleague.com/api"
out = sys.argv[1]
def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
b = get("/bootstrap-static/")
json.dump(b, open(out + "/classica_bootstrap.json", "w", encoding="utf-8"))
d = json.load(open(out + "/bootstrap.json", encoding="utf-8"))
campos_draft = set(d["elements"][0].keys())
e = b["elements"][0]
novos = sorted(k for k in e if k not in campos_draft)
print("classica: ", len(b["elements"]), "jogadores;", len(e), "campos; que o Draft não tem:", len(novos))
h = next(x for x in b["elements"] if x["web_name"] == "Haaland")
print({k: h[k] for k in novos})
s = get(f"/element-summary/{h['id']}/")
print("element-summary: chaves", list(s.keys()), "| history:", len(s["history"]), "jornadas")
print("history[-1]:", s["history"][-1])
cd = {x["code"] for x in d["elements"]}
cc = {x["code"] for x in b["elements"]}
print("codes: draft", len(cd), "classica", len(cc), "em comum", len(cd & cc))
