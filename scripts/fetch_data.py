#!/usr/bin/env python3
"""Recolhe dados da API do FPL Draft e gera site/data/data.json.

Uso: LEAGUE_ID=12258 python scripts/fetch_data.py
Só usa a stdlib. A API é pública e não requer autenticação.
"""
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

BASE = "https://draft.premierleague.com/api"
SKY_RSS = "https://www.skysports.com/rss/12691"  # Sky Sports Transfer Centre

# Fantasy Football Scout: notícias específicas de fantasy, com o resumo de team
# news da jornada. O robots.txt permite tudo (Disallow: vazio, visto 2026-08-21).
FFS_FEED = "https://www.fantasyfootballscout.co.uk/feed/"
# Estado atribuído a cada nome pela palavra-chave que aparece A SEGUIR a ele:
# "Porro + van de Ven out, Solanke + Maddison fit" -> 2 fora, 2 aptos.
FFS_ESTADOS = (
    ("fora", re.compile(
        r"\b(out|absentee|absent|sidelined|injured|injury|ruled out|miss(?:es|ing)?"
        r"|ban(?:ned)?|suspended|unavailable)\b", re.I)),
    ("duvida", re.compile(r"\b(doubt(?:ful)?|could|may|hoping|touch and go|close)\b", re.I)),
    ("apto", re.compile(r"\b(fit|available|recovers?|returns?|back|in contention)\b", re.I)),
)
# "No injury updates" não é uma lesão: negações antes da palavra-chave anulam-na.
FFS_NEGACAO = re.compile(r"\b(no|not|n't|without|free from|zero)\s+(\w+\s+){0,2}$", re.I)
# Nome do clube no artigo -> nome no bootstrap-static.
FFS_CLUBES = {
    "Manchester City": "Man City", "Manchester United": "Man Utd",
    "Tottenham Hotspur": "Spurs", "Nottingham Forest": "Nott'm Forest",
    "Newcastle United": "Newcastle", "Brighton and Hove Albion": "Brighton",
    "Leeds United": "Leeds", "AFC Bournemouth": "Bournemouth",
    "Ipswich Town": "Ipswich Town", "Hull City": "Hull City",
    "Coventry City": "Coventry City",
}

# Feeds por clube do Sky Sports (ids confirmados por sondagem em 2026-08-21).
# Chave = "name" do clube no bootstrap-static.
SKY_CLUBES = {
    "Arsenal": 11670, "Aston Villa": 11677, "Bournemouth": 11743,
    "Brentford": 11748, "Brighton": 11741, "Chelsea": 11668,
    "Coventry City": 11710, "Crystal Palace": 11706, "Everton": 11671,
    "Fulham": 11681, "Hull City": 11714, "Ipswich Town": 11707,
    "Leeds": 11715, "Liverpool": 11669, "Man City": 11679,
    "Man Utd": 11667, "Newcastle": 11678, "Nott'm Forest": 11727,
    "Spurs": 11675, "Sunderland": 11695,
}

# Um item é tratado como conferência/antevisão (e não notícia solta) se bater aqui.
CONF_PADROES = (
    "says", "said", "confirms", "confident", "expects", "insists", "admits",
    "reveals", "latest:", "team news", "press conference", "injury", "injured",
    "ruled out", "doubt", "fitness", "return", "available", "boss", "line-up",
    "lineup", "starting", "suspended", "ban", "back in", "sidelined", "fit",
)
# Ruído promocional/editorial que não interessa para escalar a equipa.
CONF_RUIDO = (
    "super 6", "sky bet", "free bet", "odds", "win £", "quiz", "papers:",
    "predictions", "transfer centre live", "watch:", "highlights", "podcast",
)
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "data")

PLAYER_FIELDS = (
    "id", "code", "web_name", "first_name", "second_name", "team", "element_type",
    "draft_rank", "total_points", "status", "news", "news_added",
    "chance_of_playing_next_round", "form", "points_per_game",
    "minutes", "starts",
    # estatísticas da época anterior, para as projeções
    "goals_scored", "assists", "clean_sheets", "saves", "bonus", "penalties_saved",
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded", "yellow_cards", "red_cards", "own_goals",
    "defensive_contribution", "penalties_missed",
)

# Estatísticas congeladas da época anterior: base do modelo de pontos esperados.
HIST_FIELDS = (
    "minutes", "starts", "total_points", "goals_scored", "assists", "clean_sheets",
    "saves", "bonus", "penalties_saved", "yellow_cards", "red_cards", "own_goals",
    "expected_goals", "expected_assists", "expected_goals_conceded",
    "defensive_contribution", "penalties_missed",
)

# Valores de transferência nos títulos/resumos das notícias (ex.: "£85m deal").
RE_VALOR = re.compile(
    r"(?P<moeda>[£€$])\s?(?P<valor>\d+(?:[.,]\d+)?)\s?(?P<mult>m\b|million|bn\b|billion)", re.I)
# Negócio fechado (mesmo que a notícia também fale de conversas/interesse).
RE_FECHADO = re.compile(
    r"\b(completes?d?|has joined|joins|joined|sealed?|medical"
    r"|agreed? (?:a )?(?:[£€$]?[\d.,]+m? )?deal|signs?\b[^.]{0,60}\bdeal)\b", re.I)
# Ainda em aberto: só rumor, não mexe na projeção.
RE_ABERTO = re.compile(
    r"\b(reject\w*|seek\w*|want\w*|target\w*|interest\w*|talks|bid|eye\w*"
    r"|approach\w*|enquir\w*|consider\w*|linked|monitor\w*)\b", re.I)


# Registo do que correu bem ou mal em cada fonte. Antes só ia para a consola e
# desaparecia; agora vai para o data.json e aparece no site.
DIAGNOSTICO = []


def registar(fonte, ok, detalhe=""):
    DIAGNOSTICO.append({"fonte": fonte, "ok": bool(ok), "detalhe": str(detalhe)[:160]})
    if not ok:
        print(f"Aviso: {fonte} — {detalhe}", file=sys.stderr)


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def rss_data_para_iso(pubdate):
    """'Fri, 21 Aug 2026 07:56:00 BST' -> ISO UTC (parsedate não conhece BST)."""
    if not pubdate:
        return None
    txt = pubdate.replace(" BST", " +0100").replace(" GMT", " +0000")
    try:
        return parsedate_to_datetime(txt).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


# Letras que o NFD não decompõe (não são letra + acento).
TRADUZ = str.maketrans({"ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
                        "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ß": "ss",
                        "þ": "th", "ð": "d"})


def sem_acentos(txt):
    return "".join(c for c in unicodedata.normalize("NFD", txt.translate(TRADUZ))
                   if unicodedata.category(c) != "Mn")


def ler_rss(url, limite=20):
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    itens = []
    for item in root.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        if not titulo:
            continue
        itens.append({
            "titulo": titulo,
            "link": (item.findtext("link") or "").strip(),
            "data": rss_data_para_iso(item.findtext("pubDate")),
            "resumo": " ".join((item.findtext("description") or "").split())[:220],
        })
        if len(itens) >= limite:
            break
    return itens


def fetch_noticias_mercado():
    """Feed de transferências da Sky. Nunca deve partir a recolha principal."""
    try:
        itens = ler_rss(SKY_RSS)
    except Exception as exc:
        registar("Sky · transferências", False, exc)
        return []
    for it in itens:
        baixa = it["titulo"].lower()
        it["rumor"] = baixa.startswith("papers") or "rumour" in baixa
    # O feed não vem ordenado: a "Transfer Centre LIVE" de anteontem aparecia
    # antes de negócios fechados hoje.
    itens.sort(key=lambda i: i.get("data") or "", reverse=True)
    registar("Sky · transferências", True, f"{len(itens)} notícias")
    return itens


def _rx_nomes(nomes):
    partes = [re.escape(sem_acentos(n).lower()) for n in nomes if len(n) >= 4]
    return re.compile(r"\b(" + "|".join(partes) + r")\b") if partes else None


def padrao_nome(p):
    """Regex do nome de um jogador (sem acentos, fronteiras de palavra)."""
    nomes = {p["web_name"]}
    if p.get("second_name"):
        nomes.update(p["second_name"].split())
    return _rx_nomes(nomes)


def padroes_nome_split(p):
    """(principal, secundário): o web_name vale mais do que um apelido solto.

    Apelidos compostos (ex.: "Martínez Romero") geram falsos positivos, por isso
    só se usa o secundário quando nenhum jogador bate pelo nome principal."""
    principal = _rx_nomes({p["web_name"]})
    outros = set(p["second_name"].split()) if p.get("second_name") else set()
    outros.discard(p["web_name"])
    return principal, _rx_nomes(outros)


def _texto_html(bruto):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto))).strip()


def fetch_ffs(players, nomes_clubes):
    """Team news do Fantasy Football Scout: quem está fora, em dúvida ou apto.

    O artigo da jornada traz um resumo em lista, com o clube em negrito e os
    jogadores a seguir. Isso permite cruzar nomes **dentro do clube certo**,
    que é o que evita falsos positivos. Se o formato mudar, devolve vazio e o
    resto da recolha segue na mesma."""
    saida = {"feed": [], "artigo": None, "jogadores": {}}
    try:
        saida["feed"] = [
            {k: it[k] for k in ("titulo", "link", "data", "resumo")}
            for it in ler_rss(FFS_FEED, limite=12)
        ]
    except Exception as exc:
        registar("Fantasy Football Scout", False, exc)
        return saida

    artigo = next((i for i in saida["feed"] if "team news" in i["titulo"].lower()), None)
    if not artigo:
        return saida
    try:
        req = urllib.request.Request(artigo["link"], headers={"User-Agent": "fpl-draft-dashboard"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            pagina = resp.read().decode("utf-8", "ignore")
    except Exception as exc:
        print(f"Aviso: artigo de team news do FFS falhou ({exc}).", file=sys.stderr)
        return saida

    corpo = re.search(r'<section class="entry-content">(.*?)<div class="entry-links"',
                      pagina, re.S)
    if not corpo:
        print("Aviso: corpo do artigo do FFS não reconhecido.", file=sys.stderr)
        return saida

    por_clube = {}
    for p in players:
        por_clube.setdefault(nomes_clubes.get(p["team"]), []).append(p)

    saida["artigo"] = {k: artigo[k] for k in ("titulo", "link", "data")}
    for li in re.findall(r"<li>(.*?)</li>", corpo.group(1), re.S):
        m = re.match(r"\s*<strong>(.*?)</strong>\s*:?(.*)", li, re.S)
        if not m:
            continue
        clube = _texto_html(m.group(1))
        texto = _texto_html(m.group(2))
        candidatos = por_clube.get(FFS_CLUBES.get(clube, clube))
        if not candidatos or not texto:
            continue

        marcas = sorted(
            (mm.start(), estado)
            for estado, rx in FFS_ESTADOS for mm in rx.finditer(texto)
            if not FFS_NEGACAO.search(texto[:mm.start()])
        )
        if not marcas:
            continue

        normalizado = sem_acentos(texto).lower()
        achados = {}
        for p in candidatos:
            rx = padrao_nome(p)
            achado = rx.search(normalizado) if rx else None
            if not achado:
                continue
            # Só conta a palavra-chave que vem DEPOIS do nome ("Porro ... out");
            # sem nenhuma a seguir, não se classifica (melhor do que adivinhar).
            seguintes = [e for pos, e in marcas if pos >= achado.start()]
            if seguintes:
                achados.setdefault(achado.start(), []).append((p, seguintes[0]))

        for pos, lista in achados.items():
            if len(lista) > 1:
                # Dois jogadores do mesmo clube no mesmo sítio do texto (apelidos
                # partilhados): fica o que bate pelo web_name, senão nenhum.
                lista = [(p, e) for p, e in lista
                         if _tokens(p["web_name"]) & _tokens(normalizado[pos:pos + 40])]
                if len(lista) != 1:
                    continue
            p, estado = lista[0]
            saida["jogadores"][str(p["id"])] = {
                "estado": estado, "frase": texto, "clube": clube,
            }
    registar("Fantasy Football Scout", True,
             f"{len(saida['jogadores'])} jogadores classificados")
    return saida


# --- Notícias oficiais da Premier League ---
# A mesma API que alimenta premierleague.com. O robots.txt do site só bloqueia
# parâmetros de rastreio (utm_*, fbclid…) e deixa os caminhos de conteúdo
# livres; a api não declara restrições e é da mesma organização da API do FPL
# que este projeto já usa.
PL_CONTEUDO = "https://api.premierleague.com/content/premierleague/en"

# Etiqueta de conteúdo por clube, no espaço de nomes do site da PL, chaveada
# pelo `name` do bootstrap (como o SKY_CLUBES). Derivada dos nomes oficiais e
# **verificada uma a uma** contra o plantel de cada clube.
#
# A verificação não é zelo a mais: uma etiqueta desconhecida **não dá erro**,
# devolve o feed geral em silêncio. Num primeiro mapeamento automático por
# tokens, "Spurs" foi parar ao Wolverhampton (não partilha nenhuma palavra com
# "Tottenham Hotspur") e "bournemouth" devolveu notícias gerais — o certo é
# "afc-bournemouth". Os dois pareciam funcionar.
PL_CLUBES = {
    "Arsenal": "arsenal", "Aston Villa": "aston-villa",
    "Bournemouth": "afc-bournemouth", "Brentford": "brentford",
    "Brighton": "brighton-and-hove-albion", "Chelsea": "chelsea",
    "Coventry City": "coventry-city", "Crystal Palace": "crystal-palace",
    "Everton": "everton", "Fulham": "fulham", "Hull City": "hull-city",
    "Ipswich Town": "ipswich-town", "Leeds": "leeds-united",
    "Liverpool": "liverpool", "Man City": "manchester-city",
    "Man Utd": "manchester-united", "Newcastle": "newcastle-united",
    "Nott'm Forest": "nottingham-forest", "Spurs": "tottenham-hotspur",
    "Sunderland": "sunderland",
}


def pl_conteudo(tag=None, limite=20):
    """Artigos da API oficial da PL, opcionalmente de uma etiqueta."""
    url = (f"{PL_CONTEUDO}?contentTypes=TEXT&offset=0&limit={limite}"
           "&onlyRestrictedContent=false&detail=DETAILED")
    if tag:
        url += "&tagNames=" + urllib.parse.quote(tag)
    req = urllib.request.Request(url, headers={
        "User-Agent": "fpl-draft-dashboard",
        "Origin": "https://www.premierleague.com"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("content") or []


def pl_item(art):
    """Artigo da PL no mesmo formato dos itens de RSS, para partilhar o resto."""
    data = (art.get("date") or art.get("publishFrom") or "")
    if data and not data.endswith("Z"):
        data = data[:19] + "Z"
    resumo = art.get("description") or art.get("summary") or ""
    ident = art.get("id")
    return {
        "titulo": (art.get("title") or "").strip(),
        "link": art.get("canonicalUrl") or (
            f"https://www.premierleague.com/en/news/{ident}" if ident else ""),
        "data": data or None,
        "resumo": " ".join(str(resumo).split())[:220],
        "fonte": "pl",
    }


def fetch_pl_clubes(nomes):
    """Notícias oficiais de cada clube: {nome_clube: [itens]}.

    Complementa a Sky: aqui vem o que o próprio clube publica — relatos de
    conferência de imprensa e as atualizações do treinador sobre lesões."""
    saida, falhas = {}, []
    for nome in nomes:
        tag = PL_CLUBES.get(nome)
        if not tag:
            falhas.append(nome)
            continue
        try:
            saida[nome] = [pl_item(a) for a in
                           pl_conteudo("club-produced-content:" + tag, 15)]
        except Exception:
            falhas.append(nome)
            saida[nome] = []
    registar("Premier League · clubes", not falhas,
             f"{len(nomes) - len(falhas)}/{len(nomes)} clubes" +
             (f"; falhou {', '.join(falhas)}" if falhas else ""))
    return saida


def fetch_pl_transferencias(players, achados):
    """Transferências confirmadas pela fonte oficial.

    O `extrair_transferencias` decide "confirmada" por regex nos títulos da
    Sky, que é um palpite; um jogador que apareça em `series:transfers` mudou
    mesmo de clube. Não traz valores — esses continuam a vir da Sky —, mas a
    confirmação sozinha já conta: isenta o jogador do castigo de "não foi
    titular no último ensaio" (o onze do clube antigo não diz nada dele)."""
    try:
        artigos = pl_conteudo("series:transfers", 40)
    except Exception as exc:
        registar("Premier League · transferências", False, exc)
        return achados
    padroes = [(p,) + padroes_nome_split(p) for p in players]
    novas = 0
    for art in artigos:
        it = pl_item(art)
        texto = sem_acentos(f'{it["titulo"]} {it["resumo"]}').lower()
        candidatos = [p for p, pr, _ in padroes if pr and pr.search(texto)]
        if not candidatos:
            candidatos = [p for p, _, sec in padroes if sec and sec.search(texto)]
        if not candidatos or len(candidatos) > 3:
            continue
        for p in candidatos:
            # A lista oficial traz entradas e **saídas**. Marcar uma saída como
            # transferência confirmada seria dizer ao modelo o contrário do que
            # aconteceu: o `confirmada` existe para isentar quem mudou de clube
            # do castigo do onze de pré-época e para lhe dar o piso de minutos.
            # Quem já não está na liga tem status u/n e projeção zero de
            # qualquer forma (Reijnders para o Al Qadsiah, Digne para o PSG).
            if p.get("status") in ("u", "n"):
                continue
            chave = str(p["id"])
            ant = achados.get(chave)
            if ant and ant.get("confirmada"):
                continue
            if ant:  # a Sky tinha o valor mas só como rumor
                ant.update(confirmada=True, fonte="Premier League",
                           titulo=it["titulo"], link=it["link"], data=it["data"])
            else:
                achados[chave] = {
                    "valor": 0, "moeda": "", "confirmada": True,
                    "titulo": it["titulo"], "link": it["link"],
                    "data": it["data"], "fonte": "Premier League",
                }
            novas += 1
    registar("Premier League · transferências", True,
             f"{novas} confirmações em {len(artigos)} artigos")
    return achados


def fetch_feeds_clubes():
    """Lê uma vez o feed Sky de cada clube: {nome_clube: [itens]}."""
    feeds = {}
    falhas = []
    for nome, rid in SKY_CLUBES.items():
        try:
            feeds[nome] = ler_rss(f"https://www.skysports.com/rss/{rid}", limite=25)
        except Exception as exc:
            falhas.append(nome)
            feeds[nome] = []
    registar("Sky · clubes", not falhas,
             f"{len(SKY_CLUBES) - len(falhas)}/{len(SKY_CLUBES)} feeds" +
             (f"; falhou {', '.join(falhas)}" if falhas else ""))

    # As notícias oficiais da PL entram pelo mesmo caminho das da Sky, para
    # aproveitarem o filtro de ruído, a deteção de conferência e o cruzamento
    # de nomes limitado ao plantel do clube. Fica aqui, e não no main(), para
    # o modo clássico as ter sem ter de repetir a ligação.
    for nome, itens in fetch_pl_clubes(sorted(PL_CLUBES)).items():
        feeds.setdefault(nome, []).extend(itens)
    for nome, itens in feeds.items():
        feeds[nome] = sem_repetidos(
            sorted(itens, key=lambda i: i.get("data") or "", reverse=True))
    return feeds


def sem_repetidos(itens):
    """A mesma notícia pode chegar pelas duas fontes; fica a mais recente."""
    vistos, unicos = set(), []
    for it in itens:
        chave = sem_acentos(it["titulo"]).lower().strip()
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(it)
    return unicos


def extrair_transferencias(feeds, players, nomes_clubes):
    """Valores de transferência detetados nas notícias, por jogador.

    Uma transferência cara é sinal de que o jogador vai ser titular, por isso
    guarda-se o maior valor confirmado (rumores ficam marcados à parte)."""
    padroes = [(p,) + padroes_nome_split(p) for p in players]
    achados = {}

    for nome_clube, itens in feeds.items():
        for it in itens:
            texto = sem_acentos(f'{it["titulo"]} {it["resumo"]}').lower()
            m = RE_VALOR.search(texto)
            if not m:
                continue
            valor = float(m.group("valor").replace(",", "."))
            if m.group("mult").lower().startswith(("bn", "billion")):
                valor *= 1000
            if valor < 1 or valor > 500:  # ignora ruído (audiências, receitas)
                continue
            # Classificar pelo título: é escrito com precisão, o resumo mistura
            # o negócio fechado com as negociações à volta.
            titulo = sem_acentos(it["titulo"]).lower()
            confirmada = bool(RE_FECHADO.search(titulo)) and not RE_ABERTO.search(titulo)
            if not confirmada and not RE_ABERTO.search(texto):
                continue

            # O web_name manda; apelidos soltos só se ninguém bater pelo principal.
            candidatos = [p for p, pr, _ in padroes if pr and pr.search(texto)]
            if not candidatos:
                candidatos = [p for p, _, sec in padroes if sec and sec.search(texto)]
            if not candidatos or len(candidatos) > 3:  # ambíguo demais
                continue
            for p in candidatos:
                ant = achados.get(p["id"])
                melhor = (confirmada, valor)
                if ant is None or melhor > (ant["confirmada"], ant["valor"]):
                    achados[p["id"]] = {
                        "valor": round(valor, 1),
                        "moeda": m.group("moeda"),
                        "confirmada": confirmada,
                        "titulo": it["titulo"],
                        "link": it["link"],
                        "data": it["data"],
                        "fonte": nome_clube,
                    }
    return {str(k): v for k, v in achados.items()}


def fetch_fixtures(bootstrap, desde_evento):
    """Próximos jogos por clube, com dificuldade (1-5).

    A dificuldade só existe em /element-summary, que é por jogador mas devolve
    o calendário do clube — basta um jogador por equipa (20 pedidos)."""
    representante = {}
    for el in bootstrap["elements"]:
        representante.setdefault(el["team"], el["id"])

    # Assim que o deadline passa, a jornada a decorrer desaparece tanto do
    # `fixtures` do jogador como do bootstrap-static, mesmo com jogos por
    # realizar. Só `/event/{ev}/live` os mantém — e são precisamente os que
    # interessam para saber quem joga hoje.
    por_jogar = {}
    try:
        jogos_atuais = (get(f"/event/{desde_evento}/live") or {}).get("fixtures") or []
    except Exception as exc:
        registar("Jogos da jornada a decorrer", False, exc)
        jogos_atuais = []
    for j in jogos_atuais:
        if j.get("finished") or j.get("finished_provisional"):
            continue
        ev = j.get("event") or desde_evento
        for casa in (True, False):
            eq = j["team_h"] if casa else j["team_a"]
            adv = j["team_a"] if casa else j["team_h"]
            por_jogar.setdefault(str(eq), []).append({
                "event": ev, "opponent": adv, "is_home": casa,
                "difficulty": 3, "kickoff": j.get("kickoff_time"),
            })

    saida = {}
    for team_id, el_id in representante.items():
        try:
            jogos = get(f"/element-summary/{el_id}")["fixtures"]
        except Exception as exc:
            print(f"Aviso: calendário da equipa {team_id} falhou ({exc}).", file=sys.stderr)
            continue
        do_bootstrap = por_jogar.get(str(team_id), [])
        vistos = {(x["event"], x["opponent"]) for x in do_bootstrap}
        saida[str(team_id)] = do_bootstrap + [
            {
                "event": j["event"],
                "opponent": j["opponent"],
                "is_home": j["is_home"],
                "difficulty": j["difficulty"],
                "kickoff": j.get("kickoff_time"),
            }
            for j in jogos
            if j.get("event") and j["event"] >= desde_evento
            and not (j.get("finished") or j.get("finished_provisional"))
            and (j["event"], j["opponent"]) not in vistos
        ][:10]
    return saida


def fetch_conferencias(clubes, meus, feeds):
    """Antevisões/conferências dos clubes onde tenho jogadores.

    `clubes`: [(team_id, nome)]. Cruza cada item com os nomes do meu plantel
    para assinalar quem é mencionado."""
    saida = []
    for team_id, nome in clubes:
        # Só cruzar com os meus jogadores deste clube: evita falsos positivos
        # (apelidos comuns) em notícias que mencionam outras equipas.
        alvos = [(p["id"], padrao_nome(p)) for p in meus if p["team"] == team_id]
        alvos = [(pid, rx) for pid, rx in alvos if rx]
        itens = feeds.get(nome, [])

        filtrados = []
        for it in itens:
            texto = sem_acentos(f'{it["titulo"]} {it["resumo"]}').lower()
            if any(r in texto for r in CONF_RUIDO):
                continue
            item = dict(it)  # os feeds são partilhados com as transferências
            item["conferencia"] = any(k in texto for k in CONF_PADROES)
            item["mencoes"] = [pid for pid, rx in alvos if rx.search(texto)]
            filtrados.append(item)
        # Data mais recente primeiro; depois menções e conferências ao topo.
        filtrados.sort(key=lambda i: i["data"] or "", reverse=True)
        filtrados.sort(key=lambda i: (not i["mencoes"], not i["conferencia"]))
        saida.append({"team_id": team_id, "nome": nome, "itens": filtrados[:8]})
    return saida


def load_anterior(out_path):
    """Recolha anterior completa (ou None na primeira execução)."""
    try:
        with open(out_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def news_anteriores(anterior):
    """ids -> news_added da recolha anterior, para detetar entradas novas no boletim.

    Devolve None se não houver recolha anterior: nesse caso nada é marcado como
    novo, para não pintar o boletim inteiro de vermelho."""
    if not anterior:
        return None
    return {p["id"]: p.get("news_added")
            for p in anterior.get("players", []) if p.get("news")}


def _elementos_live(live):
    """A API devolve `elements` como objeto {id: {...}}; aceitar lista também."""
    els = live.get("elements")
    if isinstance(els, dict):
        return list(els.items())
    if isinstance(els, list):
        return [(e.get("id"), e) for e in els]
    return []


# O que se guarda por jogador em cada jornada, por esta ordem. É uma lista e não
# um dicionário porque multiplica por ~600 jogadores × 38 jornadas: repetir os
# nomes das chaves custaria mais espaço do que os próprios números.
# Os três primeiros são inteiros; os expected vêm como texto ("0.35") na API.
JORNADA_CAMPOS = ("minutes", "total_points", "bps",
                  "expected_goals", "expected_assists", "expected_goals_conceded")


def linha_jornada(s):
    """Estatísticas de um jogador numa jornada, na ordem de JORNADA_CAMPOS."""
    return ([int(s.get(c) or 0) for c in JORNADA_CAMPOS[:3]] +
            [round(float(s.get(c) or 0), 2) for c in JORNADA_CAMPOS[3:]])


def jornada_em_cache(guardada):
    """Entrada de cache reaproveitável, em vez de voltar a pedir a jornada.

    Exige três coisas: estar terminada, ter as equipas registadas (sem elas a
    entrada vem de uma versão com um erro antigo) e ter os campos todos — as
    jornadas recolhidas antes do BPS/xG só têm minutos e pontos, e não vale a
    pena perdê-los para sempre por estarem em cache."""
    if not (guardada and guardada.get("finalizada") and guardada.get("equipas")):
        return False
    primeira = next(iter((guardada.get("stats") or {}).values()), None)
    return primeira is None or len(primeira) >= len(JORNADA_CAMPOS)


def fetch_jornadas(game, anterior):
    """Minutos e pontos de cada jogador em cada jornada já disputada.

    É esta a resposta a "quem jogou e quem ficou de fora": vem da própria API
    do FPL (`/event/{ev}/live`), a mesma que dá os pontos. Jornadas já
    terminadas não voltam a ser pedidas — ficam em cache no data.json."""
    atual = game.get("current_event")
    if not atual:
        return {}
    cache = (anterior or {}).get("jornadas") or {}
    saida = {}
    for ev in range(1, int(atual) + 1):
        chave = str(ev)
        guardada = cache.get(chave)
        if jornada_em_cache(guardada):
            saida[chave] = guardada
            continue
        try:
            live = get(f"/event/{ev}/live")
        except Exception as exc:
            print(f"Aviso: jornada {ev} falhou ({exc}).", file=sys.stderr)
            if guardada:
                saida[chave] = guardada
            continue

        stats = {}
        for eid, dados in _elementos_live(live):
            s = (dados or {}).get("stats") or dados or {}
            if s.get("minutes") or s.get("total_points"):
                # Ausentes = 0 minutos; não vale a pena guardar.
                stats[str(eid)] = linha_jornada(s)
        jogos = live.get("fixtures") or []
        # Duas noções diferentes de "acabou":
        #  - jogado: os 90 minutos já foram, os minutos dos jogadores contam;
        #  - finalizada: a API confirmou os bónus, só aí a jornada vai a cache.
        # Sem isto, quem joga na segunda apareceria com 0 minutos no sábado.
        jogado = lambda j: j.get("finished") or j.get("finished_provisional")
        equipas = sorted({t for j in jogos if jogado(j)
                          for t in (j.get("team_h"), j.get("team_a")) if t})
        saida[chave] = {
            "finalizada": bool(jogos) and all(j.get("finished") for j in jogos),
            "equipas": equipas,
            "stats": stats,
        }
    if saida:
        registar("Jornadas disputadas", True, f"{len(saida)} jornadas")
    return saida


def _tokens(txt):
    limpo = re.sub(r"[.'’]", " ", sem_acentos(txt or "").lower())
    return {t for t in limpo.split() if len(t) >= 3}


def casar_nome(nome, candidatos):
    """Nome escrito num relato -> jogador do FPL, dentro do mesmo clube.

    Pontua pelos tokens em comum (nome próprio, apelidos e web_name), o que
    apanha tanto "Bruno Fernandes" como "Alisson" ou "Van Dijk". Empates entre
    jogadores diferentes ficam por resolver — melhor nenhum do que o errado."""
    alvo = _tokens(nome)
    if not alvo:
        return None
    melhor, pontos, empate = None, 0, False
    for p in candidatos:
        seus = _tokens(f'{p["first_name"]} {p["second_name"]} {p["web_name"]}')
        comuns = len(alvo & seus)
        if comuns > pontos:
            melhor, pontos, empate = p["id"], comuns, False
        elif comuns == pontos and comuns > 0 and melhor != p["id"]:
            empate = True
    return None if (empate or pontos == 0) else melhor


def fetch_preepoca(nomes_clubes, players):
    """Onzes da pré-época, a partir do ficheiro curado scripts/preepoca.json.

    A API do FPL não tem pré-época e o TheSportsDB (a única API gratuita
    aceitável que encontrei) não traz constituição das equipas nos amigáveis,
    só em jogos oficiais — confirmado em 8 clubes a 2026-08-21. Como a
    pré-época já acabou, os dados são estáticos e ficam num ficheiro editável
    à mão, com a fonte de cada jogo."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preepoca.json")
    try:
        with open(caminho, encoding="utf-8") as f:
            bruto = json.load(f)
    except (OSError, ValueError) as exc:
        registar("Pré-época", False, exc)
        return {}

    por_clube = {}
    for p in players:
        por_clube.setdefault(p["team"], []).append(p)
    id_por_nome = {nome: tid for tid, nome in nomes_clubes.items()}

    saida = {}
    for nome, dados in (bruto.get("clubes") or {}).items():
        tid = id_por_nome.get(nome)
        if tid is None:
            print(f"Aviso: clube '{nome}' do preepoca.json não existe na liga.", file=sys.stderr)
            continue
        candidatos = por_clube.get(tid, [])
        def ids(lista):
            saiu = []
            for n in lista or []:
                pid = casar_nome(n, candidatos)
                if pid is None:
                    print(f"Aviso: pré-época {nome}: '{n}' sem correspondência.", file=sys.stderr)
                else:
                    saiu.append(pid)
            return sorted(set(saiu))
        saida[str(tid)] = {
            "data": dados.get("data"),
            "jogo": dados.get("jogo"),
            "fonte": dados.get("fonte"),
            "confianca": dados.get("confianca", "media"),
            "titulares": ids(dados.get("titulares")),
            "suplentes": ids(dados.get("suplentes")),
        }
    registar("Pré-época", True, f"{len(saida)} clubes com onze")
    return saida


def fetch_bolaparada(nomes_clubes, players):
    """Batedores de penáltis, livres e cantos (scripts/bolaparada.json).

    Os campos da API (`penalties_order` e companhia) vêm vazios para todos os
    jogadores, por isso a informação é recolhida à mão de tabelas públicas.
    Guarda a ordem de cada jogador em cada tipo de bola parada."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bolaparada.json")
    try:
        with open(caminho, encoding="utf-8") as f:
            bruto = json.load(f)
    except (OSError, ValueError) as exc:
        registar("Bola parada", False, exc)
        return {}

    por_clube = {}
    for p in players:
        por_clube.setdefault(p["team"], []).append(p)
    id_por_nome = {nome: tid for tid, nome in nomes_clubes.items()}

    saida = {}
    for nome, dados in (bruto.get("clubes") or {}).items():
        tid = id_por_nome.get(nome)
        if tid is None:
            print(f"Aviso: clube '{nome}' do bolaparada.json não existe na liga.", file=sys.stderr)
            continue
        candidatos = por_clube.get(tid, [])
        for tipo, chave in (("penaltis", "pen"), ("livres", "fk"), ("cantos", "cantos")):
            for ordem, quem in enumerate(dados.get(tipo) or [], start=1):
                pid = casar_nome(quem, candidatos)
                if pid is None:
                    print(f"Aviso: bola parada {nome}: '{quem}' sem correspondência.",
                          file=sys.stderr)
                    continue
                registo = saida.setdefault(str(pid), {"confianca": dados.get("confianca", "media")})
                registo.setdefault(chave, ordem)
    registar("Bola parada", True, f"{len(saida)} jogadores com cargo")
    return saida


def snapshot_historico(players, anterior, game):
    """Agregados da época anterior, congelados antes de a nova época os substituir.

    O bootstrap-static traz os totais da época passada até a nova começar; a
    partir daí passam a ser desta época. Guardar o retrato mantém a base das
    projeções quando ainda há poucos jogos disputados."""
    anteriores = (anterior or {}).get("historico")
    # Enquanto a época não arranca, o bootstrap ainda traz os totais da época
    # passada, por isso vale a pena refazer o retrato (apanha campos novos).
    if anteriores and game.get("current_event"):
        return anteriores
    return {str(p["id"]): {c: p.get(c) for c in HIST_FIELDS} for p in players}


# Campos da época passada que o retrato congelado não apanhou a tempo: foram
# acrescentados ao modelo já com a época a decorrer, altura em que o bootstrap
# passou a trazer os totais da época nova. Vêm do `history_past` da API
# clássica, que guarda as épocas completas, e os jogadores cruzam-se pelo
# `code` (604 em 604 batem certo).
BACKFILL_CAMPOS = ("defensive_contribution", "penalties_missed")
BASE_CLASSICA = "https://fantasy.premierleague.com/api"


def get_classica(path):
    req = urllib.request.Request(BASE_CLASSICA + path,
                                 headers={"User-Agent": "fpl-draft-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def completar_historico(historico, players):
    """Preenche no retrato congelado os campos que ele não chegou a apanhar.

    Corre **uma vez**: no fim, os campos ficam com valor (0 quando o jogador
    não tem época passada), portanto a verificação de início dá-os como
    presentes e não se repetem os pedidos."""
    if not historico:
        return historico
    if not any(h.get(c) is None for h in historico.values() for c in BACKFILL_CAMPOS):
        return historico

    try:
        classica = get_classica("/bootstrap-static/")["elements"]
    except Exception as exc:
        registar("Época passada (defensivas)", False, exc)
        return historico
    por_code = {e.get("code"): e["id"] for e in classica}
    # Só quem jogou o suficiente para a taxa dizer alguma coisa; os outros
    # ficam a zero e caem no prior da posição, como já acontecia.
    alvos = [(str(p["id"]), por_code.get(p.get("code"))) for p in players
             if por_code.get(p.get("code"))
             and (historico.get(str(p["id"])) or {}).get("minutes", 0) >= 90]

    def uma(par):
        pid, cid = par
        try:
            passadas = get_classica(f"/element-summary/{cid}/").get("history_past") or []
        except Exception:
            return pid, None
        # A última entrada é a época passada; `history_past` só tem épocas fechadas.
        return pid, (passadas[-1] if passadas else None)

    obtidos = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        for pid, epoca in ex.map(uma, alvos):
            if not epoca:
                continue
            # Guarda-chuva: se os minutos divergirem muito do retrato, é outra
            # época (ou outro jogador) e não vale a pena misturar.
            guardado = (historico.get(pid) or {}).get("minutes") or 0
            if guardado and abs((epoca.get("minutes") or 0) - guardado) > 0.2 * guardado:
                continue
            for campo in BACKFILL_CAMPOS:
                historico[pid][campo] = epoca.get(campo) or 0
            obtidos += 1

    # Quem ficou de fora fica a zero, para isto não voltar a correr.
    for h in historico.values():
        for campo in BACKFILL_CAMPOS:
            h.setdefault(campo, 0)
            if h[campo] is None:
                h[campo] = 0
    registar("Época passada (defensivas)", obtidos > 0,
             f"{obtidos} de {len(alvos)} jogadores")
    return historico


def pick_next_event(events, game):
    """Evento cujo deadline conta para a contagem decrescente."""
    by_id = {ev["id"]: ev for ev in events}
    if game.get("next_event") in by_id:
        return by_id[game["next_event"]]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for ev in events:
        if not ev.get("finished") and ev.get("deadline_time", "") > now:
            return ev
    return None


def main():
    league_id = os.environ.get("LEAGUE_ID", "").strip()
    if not league_id.isdigit():
        sys.exit("Erro: define a variável de ambiente LEAGUE_ID (número da liga no URL).")

    bootstrap = get("/bootstrap-static")
    game = get("/game")
    details = get(f"/league/{league_id}/details")
    status = get(f"/league/{league_id}/element-status")
    transacoes = get(f"/draft/league/{league_id}/transactions")["transactions"]
    registar("API do FPL Draft", True,
             f"{len(bootstrap['elements'])} jogadores, {len(details['league_entries'])} equipas")

    owners = {es["element"]: es["owner"] for es in status["element_status"]}
    out_path = os.path.join(OUT_DIR, "data.json")
    anterior = load_anterior(out_path)
    prev_news = news_anteriores(anterior)

    players = []
    for el in bootstrap["elements"]:
        p = {k: el.get(k) for k in PLAYER_FIELDS}
        p["owner"] = owners.get(el["id"])
        p["news_new"] = bool(
            prev_news is not None and p["news"]
            and (el["id"] not in prev_news or prev_news[el["id"]] != p["news_added"])
        )
        players.append(p)

    events = bootstrap["events"]["data"]
    next_ev = pick_next_event(events, game)

    # Conferências: só os clubes onde tenho jogadores (equipa detetada pelo apelido).
    apelido = os.environ.get("MEU_GESTOR", "Gentil").strip().lower()
    eu = next((e for e in details["league_entries"]
               if apelido in f'{e["player_first_name"]} {e["player_last_name"]}'.lower()), None)
    nomes_clubes = {t["id"]: t["name"] for t in bootstrap["teams"]}
    meus = [p for p in players if eu and p["owner"] == eu["entry_id"]]
    clubes = sorted({(p["team"], nomes_clubes[p["team"]]) for p in meus}, key=lambda c: c[1])
    if not eu:
        print(f"Aviso: gestor '{apelido}' não encontrado; sem conferências.", file=sys.stderr)

    feeds = fetch_feeds_clubes()
    # Começar na jornada a decorrer, não na seguinte: os jogos que ainda faltam
    # hoje são os mais relevantes de todos.
    desde = game.get("current_event") or (next_ev["id"] if next_ev else 1)
    fixtures = fetch_fixtures(bootstrap, desde)
    noticias_mercado = fetch_noticias_mercado()

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "league_id": int(league_id),
        "game": game,
        "next_event": next_ev and {
            "id": next_ev["id"],
            "name": next_ev["name"],
            "deadline_time": next_ev["deadline_time"],
            "waivers_time": next_ev.get("waivers_time"),
            "trades_time": next_ev.get("trades_time"),
        },
        "league": {
            "name": details["league"]["name"],
            "scoring": details["league"]["scoring"],
            "transaction_mode": details["league"]["transaction_mode"],
        },
        "entries": [
            {
                "id": e["id"],
                "entry_id": e["entry_id"],
                "entry_name": e["entry_name"],
                "manager": f'{e["player_first_name"]} {e["player_last_name"]}',
                "short_name": e["short_name"],
                "waiver_pick": e.get("waiver_pick"),
            }
            for e in details["league_entries"]
        ],
        "standings": details["standings"],
        # A liga publica a sua tabela de pontuação e as regras de plantel: o
        # modelo passa a usá-las em vez de valores escritos à mão.
        "diagnostico": DIAGNOSTICO,
        "regras": {
            "scoring": bootstrap.get("settings", {}).get("scoring", {}),
            "squad": bootstrap.get("settings", {}).get("squad", {}),
        },
        "teams": {str(t["id"]): {"name": t["name"], "short_name": t["short_name"]}
                  for t in bootstrap["teams"]},
        "players": players,
        "fixtures": fixtures,
        "jornadas": fetch_jornadas(game, anterior),
        "preepoca": fetch_preepoca(nomes_clubes, players),
        "ffs": fetch_ffs(players, nomes_clubes),
        "bolaparada": fetch_bolaparada(nomes_clubes, players),
        "historico": completar_historico(
            snapshot_historico(players, anterior, game), players),
        "transferencias": fetch_pl_transferencias(players, extrair_transferencias(
            {**feeds, "Transfer Centre": noticias_mercado}, players, nomes_clubes)),
        "conferencias": {
            "equipa": eu["entry_name"] if eu else None,
            "clubes": fetch_conferencias(clubes, meus, feeds),
        },
        "mercado": {
            "noticias": noticias_mercado,
            "transacoes": [
                {k: t.get(k) for k in ("added", "element_in", "element_out",
                                       "entry", "event", "kind", "result")}
                for t in sorted(transacoes, key=lambda t: t.get("added") or "",
                                reverse=True)[:40]
            ],
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {out_path} ({os.path.getsize(out_path)} bytes, "
          f"{len(players)} jogadores, {len(data['entries'])} equipas)")


if __name__ == "__main__":
    main()
