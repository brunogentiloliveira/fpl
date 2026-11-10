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
    com visto verde no diagnóstico. Não chega parar aqui: a página ecoa de
    volta qualquer `epoca_id` pedido (confirmado ao vivo: `?epoca_id=155`
    devolve sempre "2025/2026", mesmo depois de a época ter mudado), por
    isso quem chama isto tem de pedir a primeira página SEM esse parâmetro —
    só assim o <select> reflecte a época actual em vez de ecoar o pedido.
    """
    bloco = re.search(r'<select[^>]*epoca_id.*?</select>', pagina, re.S)
    if not bloco:
        return None
    m = re.search(r'<option[^>]*value="(\d+)"[^>]*\bselected[^>]*>([^<]+)',
                  bloco.group(0))
    if not m:
        return None
    return int(m.group(1)), m.group(2).strip()


def ano_da_api():
    """Ano do 1º deadline da época, lido da API oficial da FPL.

    Segunda confirmação da época, independente do <select> do zerozero —
    barata (um pedido) e uma fonte completamente diferente. Se o
    comportamento da página mudar outra vez em silêncio (como já aconteceu
    com o eco do `epoca_id`), isto continua a apanhar.
    """
    req = urllib.request.Request(API + "/bootstrap-static/",
                                 headers={"User-Agent": "Mozilla/5.0 fpl-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = json.load(resp)
    eventos = dados.get("events") or []
    if not eventos or not eventos[0].get("deadline_time"):
        return None
    return int(eventos[0]["deadline_time"][:4])


def epoca_coerente(epoca_txt, ano_api):
    """O ano do rótulo lido no zerozero ("2026/2027") bate com `ano_da_api()`?

    Sem `ano_api` (a API falhou a dar-nos um ano) ou sem ano nenhum no
    rótulo, não há como confirmar — devolve False, que é o lado seguro:
    antes escrever nada do que confiar às cegas.
    """
    m = re.search(r"\d{4}", epoca_txt or "")
    if not m or not ano_api:
        return False
    return int(m.group()) == ano_api


def confirmar_epoca(pagina, ano_api):
    """(id, rótulo) da época — só se o <select> existir E bater com a API.

    As duas condições de aborto num sítio só: sem <select> (a página mudou
    de estrutura) ou o ano lido a não bater com `ano_da_api()` (a página
    ecoou de volta um `epoca_id` errado, ou voltou a mudar de
    comportamento em silêncio). Qualquer uma devolve None — nunca um
    palpite escrito no ficheiro final.
    """
    achada = epoca_da_pagina(pagina)
    if not achada or not epoca_coerente(achada[1], ano_api):
        return None
    return achada


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


# Quão perto (em dias) a âncora POSTERIOR precisa de estar da data-alvo para
# entrar na verificação de desacordo, em para_utc(). As âncoras são jogos de
# PL do próprio clube (~1 por semana); uma que caia muito mais longe (ex.: a
# paragem de inverno, a ~80 dias) não é vizinha nenhuma, é só a única que
# existe do lado de lá — não deve tornar incerta uma data que já tem uma
# âncora anterior próxima e sem conflito nenhum por perto.
ANCORA_VIZINHA_DIAS = 10


def para_utc(data, hora, desvios):
    """(ISO em UTC, hora_incerta). Sem hora, devolve a data nua.

    A âncora por distância ABSOLUTA atravessa a mudança de horário: 22/10
    fica a 4 dias de uma âncora de Verão (18/10, BST) e só a 3 de uma de
    Inverno (25/10 — o próprio dia da troca, já GMT) — "mais próxima"
    escolhia a errada, e ainda marcava `hora_incerta=False`, como se
    estivesse certa. A troca de horário acontece num instante só, por isso a
    âncora ANTERIOR à data está sempre do mesmo lado dela; usa-se essa, com
    recurso à posterior só quando não há nenhuma antes. Quando as duas
    existem, estão a `ANCORA_VIZINHA_DIAS` uma da outra (a data cai mesmo na
    semana da troca) e DISCORDAM, o valor da anterior continua a ser o mais
    plausível — mas fica `hora_incerta`, em vez de se afirmar uma certeza
    que não se tem.
    """
    if not hora:
        return data, True
    if data in desvios:
        delta, incerta = desvios[data], False
    else:
        alvo = _dias(data)
        anteriores = {d: v for d, v in desvios.items() if _dias(d) < alvo}
        posteriores = {d: v for d, v in desvios.items() if _dias(d) > alvo}
        anterior = max(anteriores, key=_dias, default=None)
        posterior = min(posteriores, key=_dias, default=None)
        if anterior is not None:
            delta = desvios[anterior]
            incerta = (posterior is not None
                       and _dias(posterior) - alvo <= ANCORA_VIZINHA_DIAS
                       and desvios[posterior] != delta)
        elif posterior is not None:
            delta, incerta = desvios[posterior], False
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


# Quantos jogos da PL podem ter no zerozero uma data diferente da da API sem se
# desconfiar da página. Uma remarcação mexe em poucos jogos de cada vez (em
# 2026-11-10 eram 2 em 380, o pior clube com 2); um erro de leitura das datas
# mexe em quase todos. Um quarto das 38 linhas separa bem os dois casos.
REMARCADAS_MAX = 9


def validar_pl(linhas_zz, fixtures_api):
    """Cruza as linhas da PL do zerozero com a API, jogo a jogo.

    Devolve (aceites, recusadas, remarcadas). Quem decide se o clube cai é
    `motivo_recusa()`.

    O jogo identifica-se por (adversário, casa/fora): numa época cada par só
    acontece uma vez, e batem 760 em 760. A data não serve para identificar,
    porque a PL remarca jogos e as duas fontes não atualizam ao mesmo tempo.
    Em 2026-11-10 a API já tinha o Forest-Everton no domingo 20/12 e o
    Forest-Hull a 05/01, e o zerozero ainda os dava a 19/12 e a 06/01. Com a
    data dentro da chave, isso eram "jogos que não batem", e a regra que
    recusava o clube por qualquer divergência nas 6 semanas seguintes deitou
    fora o Forest e o Everton inteiros. Essa regra partia de que a essa
    distância os jogos já estão fixos; é ao contrário, é quando as escolhas
    da televisão saem e as fontes se desencontram.

    - aceites: o mesmo jogo, na mesma data.
    - remarcadas: o mesmo jogo, com outra data. Vale a da API, que é de onde
      os jogos da PL saem de qualquer maneira.
    - recusadas: um jogo que a API não tem (outro adversário, ou o campo
      trocado). É o que denuncia a página de outro clube ou de outra época.

    Nunca pela hora, que está noutro fuso.
    """
    datas_do_jogo = {}
    for j in fixtures_api:
        datas_do_jogo.setdefault((j["adv_slug"], j["casa"]), set()).add(j["data"])
    aceites, recusadas, remarcadas = [], [], []
    for linha in linhas_zz:
        datas = datas_do_jogo.get((linha["adv_slug"], linha["casa"]))
        if datas is None:
            recusadas.append(f"{linha['data']} vs {linha['adv_slug']}")
        elif linha["data"] in datas:
            aceites.append(linha)
        else:
            remarcadas.append(f"{linha['data']} vs {linha['adv_slug']} "
                              f"(na API: {', '.join(sorted(datas))})")
    return aceites, recusadas, remarcadas


def motivo_recusa(recusadas, remarcadas):
    """Porque é que não se confia na página do clube, ou None se se confia.

    Mais de 2 jogos que a API não tem já não é um adiamento: é a página
    errada. Mais de `REMARCADAS_MAX` datas diferentes já não é a televisão: é
    um erro de leitura das datas, que estragaria também as dos jogos europeus.
    """
    if len(recusadas) > 2:
        return f"{len(recusadas)} jogos da PL que a API não tem"
    if len(remarcadas) > REMARCADAS_MAX:
        return f"{len(remarcadas)} jogos da PL com data diferente da API"
    return None


def _get_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 fpl-dashboard", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            dados = gzip.decompress(dados)
        return dados.decode("utf-8", "replace")


def jogos_do_clube(caminho, epoca_id, pagina1_html=None):
    """Todas as páginas de um clube.

    A tabela vem por data DECRESCENTE, portanto a última página tem os jogos
    mais PRÓXIMOS: cada clube com prova europeia tem 7 a 9 jogos por realizar
    só na página 2 (89 jogos fora da PL por realizar, no total dos 20
    clubes). Parar antes de a pedir apagava a congestão das próximas duas
    semanas e deixava uma linha a começar em outubro — plausível.

    `pagina1_html`, se vier, é a página 1 já lida por quem chama (para
    confirmar a época, ver `main()`) — poupa pedi-la outra vez aqui. Sem
    isto os 20 clubes pediam a mesma URL da página 1 duas vezes (49 pedidos
    em vez dos 29 que a especificação afirma), e para 19 deles a primeira
    resposta nem chegava a ser parseada: era lida só para confirmar a época
    (já sabida) e deitada fora.
    """
    if pagina1_html is not None:
        primeiras = linhas_jogos(pagina1_html)
        todos = list(primeiras)
        pagina, parar = 2, len(primeiras) < LINHAS_POR_PAGINA
    else:
        todos, pagina, parar = [], 1, False
    while not parar and pagina <= 4:
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
    try:
        ano_api = ano_da_api()
    except Exception as exc:
        fd.registar("Calendário: época", False,
                    f"não foi possível confirmar o ano pela API ({exc})")
        return 1

    epoca_id, epoca_txt, saida, recusados = None, "", {}, {}
    for nome, info in mapa.items():
        team_id = None
        for k, v in clubes_fpl.items():
            if (v["name"] if isinstance(v, dict) else v) == nome:
                team_id = int(k)
        if team_id is None:
            continue
        # Nunca um epoca_id escrito à mão: a primeira página pede-se SEM o
        # parâmetro, para o zerozero devolver a época actual por omissão —
        # com o parâmetro ele ecoa de volta o que se pediu (ver
        # `epoca_da_pagina`), o que nunca dispararia o aborto na época
        # seguinte. Essa mesma resposta serve também de página 1 dos jogos
        # deste clube (passada a `jogos_do_clube` a seguir): sem a
        # reaproveitar, os 20 clubes pediam a página 1 duas vezes — 49
        # pedidos em vez dos 29 que a especificação afirma — e para 19
        # deles a primeira resposta era lida só para ser deitada fora sem
        # ser parseada.
        url = (f"{ZZ}{info['caminho']}/jogos?page=1" if epoca_id is None else
               f"{ZZ}{info['caminho']}/jogos?epoca_id={epoca_id}&page=1")
        try:
            primeira = _get_html(url)
        except Exception as exc:
            recusados[str(team_id)] = f"não foi possível ler a página ({exc})"
            fd.registar(f"Calendário: {nome}", False, exc)
            continue
        if epoca_id is None:
            achada = confirmar_epoca(primeira, ano_api)
            if not achada:
                fd.registar("Calendário: época", False,
                            f"sem <select> na página, ou ano incoerente com a API "
                            f"({ano_api!r})")
                return 1
            epoca_id, epoca_txt = achada

        linhas = jogos_do_clube(info["caminho"], epoca_id, primeira)
        pl_zz = [x for x in linhas if normalizar_comp(x["comp_bruta"]) == "PL"]
        desvios = desvios_por_data(pl_zz, oficiais.get(team_id, []))
        _, divergentes, remarcadas = validar_pl(pl_zz, oficiais.get(team_id, []))
        motivo = motivo_recusa(divergentes, remarcadas)
        if motivo:
            recusados[str(team_id)] = motivo
            fd.registar(f"Calendário: {nome}", False, (divergentes or remarcadas)[:3])
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
