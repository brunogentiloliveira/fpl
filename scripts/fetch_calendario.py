#!/usr/bin/env python3
"""Calendário completo dos 20 clubes da PL: liga, Europa e taças.

Uso: python scripts/fetch_calendario.py

A Premier League vem da API oficial, que é a única das duas fontes com a
dificuldade dos adversários. As outras provas vêm do zerozero, que é a única
que as tem. Escreve `site/data/calendario.json` e mais nada: o data.json e o
classica.json não são tocados, e o modelo de projeção não vê este ficheiro.

Só stdlib.
"""
import gzip
import html as html_mod
import io
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as fd

ZZ = "https://www.zerozero.pt"
API = "https://fantasy.premierleague.com/api"
OUT = os.path.join(fd.OUT_DIR, "calendario.json")
MAPA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zerozero.json")

# A tabela dá 40 linhas por página e vem por data DECRESCENTE: a página 1 são
# os jogos mais distantes e a 2 os mais próximos. Parar na primeira página com
# menos de 40 linhas deixaria de fora... nada, porque só a última é curta — mas
# parar antes de a pedir apagava os jogos das próximas duas semanas.
LINHAS_POR_PAGINA = 40


def _celulas(tr):
    """Texto de cada <td>, sem marcação e com as entidades já resolvidas.

    A ordem importa: tirar a marcação primeiro e só depois `html.unescape`.
    Ao contrário, um `&lt;b&gt;` escrito por extenso virava marcação a sério.
    O `split()` sem argumentos já trata o `\xa0` (nbsp, comum na tabela) como
    espaço, por isso não é preciso um `replace` à parte para ele.
    """
    fora = []
    for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S):
        limpo = html_mod.unescape(re.sub(r"<[^>]+>", " ", c))
        fora.append(" ".join(limpo.split()).strip())
    return fora


def linhas_jogos(pagina):
    """Os jogos de uma página de /equipa/<slug>/jogos.

    Filtra por número de células e por data ISO na segunda: as linhas de
    classificação têm 13 células e o cabeçalho também, por isso ler pela
    posição sem este guarda dava a data no lugar do nome — foi o que aconteceu
    na tabela de empréstimos da Wikipedia.
    """
    saida = []
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", pagina, re.S):
        cels = _celulas(tr)
        if len(cels) != 10 or not re.match(r"^\d{4}-\d{2}-\d{2}$", cels[1]):
            continue
        m_id = re.search(r'<tr[^>]*\bid="(\d+)"', tr)
        # O primeiro /equipa/ da linha é o adversário. A forma canónica leva
        # o id da equipa a seguir (`/equipa/sunderland/91`), por isso o slug
        # pára no primeiro "/" — senão o id ficava colado ("sunderland/91") —
        # e a query string do segundo link (`?epoca_id=...`) também não entra.
        m_slug = re.search(r'href="/equipa/([^"?/]+)', tr)
        saida.append({
            "id": int(m_id.group(1)) if m_id else None,
            "data": cels[1],
            "hora": cels[2] if re.match(r"^\d{1,2}:\d{2}$", cels[2]) else None,
            # Vazio é campo neutro (supertaças), não "fora".
            "casa": True if cels[3] == "(C)" else (False if cels[3] == "(F)" else None),
            "adv_slug": m_slug.group(1) if m_slug else "",
            "adv_nome": cels[5],
            "comp_bruta": cels[7],
            "ronda": cels[8],
            # Nos jogos já disputados a primeira célula é V/E/D, não "h2h".
            "jogado": cels[0] in ("V", "E", "D"),
        })
    return saida


def epoca_da_pagina(pagina):
    """(id, rótulo) da época seleccionada no <select> da própria página.

    Escrever `epoca_id=156` à mão passava a verificação dos 38 jogos por clube
    na época seguinte e devolvia um ficheiro sem um único jogo por realizar,
    com visto verde no diagnóstico.
    """
    bloco = re.search(r'<select[^>]*epoca_id.*?</select>', pagina, re.S)
    if not bloco:
        return None
    m = re.search(r'<option[^>]*value="(\d+)"[^>]*\bselected[^>]*>([^<]+)',
                  bloco.group(0))
    if not m:
        return None
    return int(m.group(1)), m.group(2).strip()


# Por subcadeia, e não por igualdade: o rótulo leva o patrocinador e o ano, e
# muda de época para época ("The Emirates FA Cup 25/26", "Community Shield
# 2025"). Hoje nenhuma das dez chaves é subcadeia de outra — reordenar a
# lista e correr os 13 casos do teste não muda um único resultado —, por
# isso a ordem não resolve nenhuma colisão real. Fica como defesa contra um
# rótulo futuro que passe a sobrepor-se (ex.: a Taça de Inglaterra troca de
# patrocinador outra vez e o novo nome passa a conter "cup" a seguir a uma
# palavra já usada por outra chave).
COMPETICOES = [
    ("premier league", "PL"),
    ("champions league", "UCL"),
    ("europa league", "UEL"),
    ("conference league", "UECL"),
    ("super cup", "SUP"),
    ("supertaça", "SUP"),
    ("community shield", "SUP"),
    ("fa cup", "FAC"),
    ("carabao", "LC"),
    ("league cup", "LC"),
]

NOMES_COMP = {"PL": "Premier League", "UCL": "Champions League",
              "UEL": "Liga Europa", "UECL": "Conference League",
              "LC": "Taça da Liga", "FAC": "Taça de Inglaterra",
              "SUP": "Supertaças", "OUT": "Outras"}


def normalizar_comp(bruta):
    txt = fd.sem_acentos((bruta or "").lower())
    for chave, sigla in COMPETICOES:
        if fd.sem_acentos(chave) in txt:
            return sigla
    return "OUT"


def ler_mapa_zerozero():
    with io.open(MAPA, encoding="utf-8") as f:
        return json.load(f)


def slugs_para_id(mapa_zz, clubes_fpl):
    """slug do zerozero -> id do clube na FPL.

    O nome não serve de chave para juntar às linhas de jogo: é no `adv_nome`
    de cada linha que o zerozero usa o nome do site em vez do da FPL —
    "Brighton & Hove Albion" em vez de "Brighton", "Manchester City" em vez
    de "Man City" — em 6 dos 20 clubes, 27% das linhas. As chaves de topo do
    zerozero.json não têm este problema (já batem 1:1 com a FPL), mas o
    `adv_nome` de cada linha vem direto do HTML e não passa por essa
    curadoria. E um recurso por tokens é pior — *city* liga o Manchester
    City ao Hull City. O slug está no HTML em todas as linhas e bate
    exactamente com o zerozero.json.
    """
    por_nome = {v["name"] if isinstance(v, dict) else v: int(k)
                for k, v in clubes_fpl.items()}
    saida = {}
    for nome, info in mapa_zz.items():
        team_id = por_nome.get(nome)
        if team_id is None:
            fd.registar("Calendário: clube sem id", False, nome)
            continue
        saida[info["caminho"].split("/equipa/", 1)[1].split("/")[0]] = team_id
    return saida


def desvios_por_data(linhas_pl, fixtures_api):
    """Minutos entre a hora do zerozero e a UTC da API, por data.

    Não se usa `ZoneInfo("Europe/Lisbon")`: rebenta nesta máquina
    (ZoneInfoNotFoundError, Python do python.org em Windows sem tzdata) — e
    seria assumir. As linhas da PL dão o par (hora local, UTC) para o mesmo
    jogo, portanto o desvio é medido a partir dos próprios dados.
    """
    por_data = {}
    for j in fixtures_api:
        if j.get("kickoff"):
            por_data.setdefault(j["data"], j["kickoff"])
    desvios = {}
    for linha in linhas_pl:
        alvo = por_data.get(linha["data"])
        if not alvo or not linha.get("hora"):
            continue
        hh, mm = (int(x) for x in linha["hora"].split(":"))
        ah, am = int(alvo[11:13]), int(alvo[14:16])
        delta = (hh * 60 + mm) - (ah * 60 + am)
        # Só 0 ou 60 são plausíveis; qualquer outra coisa é jogo diferente no
        # mesmo dia, não desvio de fuso.
        if delta in (0, 60):
            desvios[linha["data"]] = delta
    return desvios


def para_utc(data, hora, desvios):
    """(ISO em UTC, hora_incerta). Sem hora, devolve a data nua."""
    if not hora:
        return data, True
    if data in desvios:
        delta, incerta = desvios[data], False
    elif desvios:
        # A âncora mais próxima: o regime de horário só muda duas vezes por ano.
        vizinha = min(desvios, key=lambda d: abs(_dias(d) - _dias(data)))
        delta, incerta = desvios[vizinha], False
    else:
        delta, incerta = 0, True
    minutos = int(hora[:2]) * 60 + int(hora[3:5]) - delta
    dia = _dias(data) + (minutos // (24 * 60))
    minutos %= 24 * 60
    return f"{_data(dia)}T{minutos // 60:02d}:{minutos % 60:02d}:00Z", incerta


def _dias(data):
    from datetime import date
    return date(int(data[:4]), int(data[5:7]), int(data[8:10])).toordinal()


def _data(ordinal):
    from datetime import date
    return date.fromordinal(ordinal).isoformat()


def validar_pl(linhas_zz, fixtures_api, semanas_criticas=6):
    """Cruza as linhas da PL do zerozero com a API. Recusa linhas, não clubes.

    Só por (data, adversário, casa/fora) — nunca pela hora, que está noutro
    fuso. Hoje batem 760/760.
    """
    oficiais = {(j["data"], j["adv_slug"], j["casa"]) for j in fixtures_api}
    aceites, recusadas = [], []
    for linha in linhas_zz:
        chave = (linha["data"], linha["adv_slug"], linha["casa"])
        if chave in oficiais:
            aceites.append(linha)
        else:
            recusadas.append(f"{linha['data']} vs {linha['adv_slug']}")
    return aceites, recusadas


def _get_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 fpl-dashboard", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            dados = gzip.decompress(dados)
        return dados.decode("utf-8", "replace")


def jogos_do_clube(caminho, epoca_id):
    """Todas as páginas de um clube.

    A tabela vem por data DECRESCENTE, portanto a última página tem os jogos
    mais PRÓXIMOS: 34 jogos por realizar existem só na página 2, e são todos
    dos 9 clubes europeus. Parar antes de a pedir apagava a congestão das
    próximas duas semanas e deixava uma linha a começar em outubro — plausível.
    """
    todos, pagina = [], 1
    while pagina <= 4:
        url = f"{ZZ}{caminho}/jogos?epoca_id={epoca_id}&page={pagina}"
        linhas = linhas_jogos(_get_html(url))
        todos += linhas
        if len(linhas) < LINHAS_POR_PAGINA:
            break
        pagina += 1
        time.sleep(0.3)
    # O id do jogo é único e estável; (data, adversário) não distingue uma
    # remarcação de um jogo novo.
    vistos, unicos = set(), []
    for j in todos:
        if j["id"] not in vistos:
            vistos.add(j["id"])
            unicos.append(j)
    return unicos


def fixtures_oficiais(slug_de_id):
    """Os 380 jogos da PL, por clube, já com a dificuldade do lado certo.

    A polaridade sai de `team_h_difficulty`/`team_a_difficulty` conforme o lado
    — trocá-la seria uma inversão silenciosa e plausível, que transformava
    "percurso fácil" em "percurso duro" sem nada partir.
    """
    req = urllib.request.Request(API + "/fixtures/",
                                 headers={"User-Agent": "Mozilla/5.0 fpl-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        jogos = json.load(resp)
    por_clube = {}
    for j in jogos:
        if not j.get("kickoff_time"):
            continue
        data = j["kickoff_time"][:10]
        for casa in (True, False):
            eu = j["team_h"] if casa else j["team_a"]
            adv = j["team_a"] if casa else j["team_h"]
            por_clube.setdefault(eu, []).append({
                "data": data, "kickoff": j["kickoff_time"], "casa": casa,
                "adv": adv, "adv_slug": slug_de_id.get(adv, ""),
                "dif": j["team_h_difficulty"] if casa else j["team_a_difficulty"],
                "evento": j.get("event"),
                "jogado": bool(j.get("finished") or j.get("finished_provisional")),
            })
    return por_clube


def main():
    with io.open(os.path.join(fd.OUT_DIR, "data.json"), encoding="utf-8") as f:
        clubes_fpl = json.load(f)["teams"]
    mapa = ler_mapa_zerozero()
    slug_id = slugs_para_id(mapa, clubes_fpl)
    id_slug = {v: k for k, v in slug_id.items()}
    oficiais = fixtures_oficiais(id_slug)

    epoca_id, epoca_txt, saida, recusados = None, "", {}, {}
    for nome, info in mapa.items():
        team_id = None
        for k, v in clubes_fpl.items():
            if (v["name"] if isinstance(v, dict) else v) == nome:
                team_id = int(k)
        if team_id is None:
            continue
        try:
            primeira = _get_html(f"{ZZ}{info['caminho']}/jogos?epoca_id={epoca_id or 156}&page=1")
        except Exception as exc:
            recusados[str(team_id)] = f"não foi possível ler a página ({exc})"
            fd.registar(f"Calendário: {nome}", False, exc)
            continue
        if epoca_id is None:
            achada = epoca_da_pagina(primeira)
            if not achada:
                fd.registar("Calendário: época", False, "sem <select> na página")
                return 1
            epoca_id, epoca_txt = achada

        linhas = jogos_do_clube(info["caminho"], epoca_id)
        pl_zz = [x for x in linhas if normalizar_comp(x["comp_bruta"]) == "PL"]
        desvios = desvios_por_data(pl_zz, oficiais.get(team_id, []))
        _, divergentes = validar_pl(pl_zz, oficiais.get(team_id, []))
        if len(divergentes) > 2:
            recusados[str(team_id)] = f"{len(divergentes)} jogos da PL não batem com a API"
            fd.registar(f"Calendário: {nome}", False, divergentes[:3])
            continue

        jogos = []
        # A PL vem da API, que é a única com dificuldade; do zerozero só o resto.
        for j in oficiais.get(team_id, []):
            jogos.append({"id": None, "data": j["kickoff"], "comp": "PL",
                          "adv": j["adv"], "adv_nome": None, "adv_slug": j["adv_slug"],
                          "casa": j["casa"], "dif": j["dif"], "jornada": j["evento"],
                          "ronda": None, "jogado": j["jogado"], "hora_incerta": False})
        for x in linhas:
            comp = normalizar_comp(x["comp_bruta"])
            if comp == "PL":
                continue
            iso, incerta = para_utc(x["data"], x["hora"], desvios)
            jogos.append({"id": x["id"], "data": iso, "comp": comp,
                          "adv": slug_id.get(x["adv_slug"]), "adv_nome": x["adv_nome"],
                          "adv_slug": x["adv_slug"], "casa": x["casa"], "dif": None,
                          "jornada": None, "ronda": x["ronda"], "jogado": x["jogado"],
                          "hora_incerta": incerta})
        jogos.sort(key=lambda j: j["data"])
        curto = clubes_fpl[str(team_id)]
        saida[str(team_id)] = {
            "nome": nome,
            "curto": curto["short_name"] if isinstance(curto, dict) else nome[:3].upper(),
            "jogos": jogos,
        }
        time.sleep(0.3)

    nao_pl = sum(1 for c in saida.values() for j in c["jogos"]
                 if j["comp"] != "PL" and not j["jogado"])
    fd.registar("Calendário zerozero", bool(saida),
                f"{len(saida)} clubes, {nao_pl} jogos por realizar fora da PL")
    os.makedirs(fd.OUT_DIR, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": fd.datetime.now(fd.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epoca_id": epoca_id, "epoca": epoca_txt, "clubes": saida,
            "competicoes": NOMES_COMP, "recusados": recusados,
            "diagnostico": fd.DIAGNOSTICO,
        }, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {OUT} ({len(saida)} clubes, {nao_pl} jogos nao-PL por realizar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
