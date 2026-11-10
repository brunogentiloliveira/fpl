import json, sys, time, urllib.request
BASE = "https://draft.premierleague.com/api"
out = sys.argv[1]
def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
b = json.load(open(out + "/bootstrap.json", encoding="utf-8"))
print("element_stats (o que a página deixa ordenar):")
for s in b["element_stats"]:
    print("  ", s)
ev = b["events"]
print("current", ev["current"], "| jornadas acabadas:", [e["id"] for e in ev["data"] if e["finished"]])
for e in ev["data"]:
    if not e["finished"]:
        continue
    l = get(f"/event/{e['id']}/live")
    json.dump(l, open(f"{out}/live{e['id']}.json", "w", encoding="utf-8"))
    els = l["elements"]
    n = sum(1 for v in els.values() if v["stats"]["minutes"] > 0)
    print(f"  J{e['id']}: {len(els)} jogadores, {n} com minutos, {len(l['fixtures'])} jogos")
    time.sleep(0.4)
