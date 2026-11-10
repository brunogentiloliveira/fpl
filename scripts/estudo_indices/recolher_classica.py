import json, sys, time, urllib.request
BASE = "https://fantasy.premierleague.com/api"
out = sys.argv[1]
b = json.load(open(out + "/classica_bootstrap.json", encoding="utf-8"))
def get(path, tentativas=3):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": "fpl-draft-dashboard"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i == tentativas - 1: raise
            time.sleep(2 + 3 * i)
CAMPOS = ["round", "value", "selected", "transfers_in", "transfers_out", "transfers_balance",
          "was_home", "opponent_team", "minutes", "total_points"]
res, falhas = {}, 0
for n, e in enumerate(b["elements"]):
    try:
        s = get(f"/element-summary/{e['id']}/")
        res[str(e["code"])] = [{k: h.get(k) for k in CAMPOS} for h in s["history"]]
    except Exception as ex:
        falhas += 1
        print("falhou", e["web_name"], ex, flush=True)
    if n % 100 == 0: print(n, "de", len(b["elements"]), flush=True)
    time.sleep(0.12)
json.dump(res, open(out + "/classica_historia.json", "w", encoding="utf-8"))
print("feito:", len(res), "jogadores,", falhas, "falhas")
