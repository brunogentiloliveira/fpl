import json, sys, urllib.request
BASE = "https://draft.premierleague.com/api"
out = sys.argv[1]
def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
b = get("/bootstrap-static")
json.dump(b, open(out + "/bootstrap.json", "w", encoding="utf-8"))
e = b["elements"][0]
print("bootstrap: chaves de topo", list(b.keys()))
print("elements[0]:", len(e), "campos")
print(sorted(e.keys()))
h = next(x for x in b["elements"] if x["web_name"] == "Haaland")
print("Haaland:", {k: h[k] for k in sorted(h) if k not in ("first_name","second_name","news","news_added","code")})
l = get("/event/10/live")
json.dump(l, open(out + "/live10.json", "w", encoding="utf-8"))
print("live: chaves de topo", list(l.keys()))
els = l["elements"]
k0 = next(iter(els)) if isinstance(els, dict) else 0
print("live element exemplo:", json.dumps(els[k0] if isinstance(els, dict) else els[0])[:900])
