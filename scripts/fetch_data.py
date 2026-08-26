#!/usr/bin/env python3
"""Recolhe dados da API do FPL Draft e gera site/data/data.json.

Uso: LEAGUE_ID=12258 python scripts/fetch_data.py
Só usa a stdlib. A API é pública e não requer autenticação.
"""
import html
import gzip
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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


# O Transfer Centre ao vivo. É a página que o utilizador indicou, e traz coisas
# que o RSS não tem: as entradas minuto a minuto (9 dos 10 itens não estavam no
# feed 12691) e o **corpo completo** de cada uma, que é onde os valores estão
# escritos ("in a record-breaking £86m move from Lille").
#
# Duas decisões que a tornam robusta:
#  - o endereço é `/transfer-centre`, que é estável e já traz o JSON-LD; o URL
#    do live blog tem um id que o Sky roda (12476234 hoje, outro amanhã);
#  - lê-se o `LiveBlogPosting` de schema.org, publicado de propósito para
#    máquinas, em vez de raspar HTML que é montado por JavaScript.
# O robots.txt permite `/transfer-centre` e o caminho dos live blogs; só veda
# `/api/` e um caminho `live-blog-beta`.
SKY_AO_VIVO = "https://www.skysports.com/transfer-centre"
# Chega para apanhar o valor, que vem na primeira frase, sem arrastar o artigo
# todo — quanto mais texto, mais nomes de outros jogadores a confundir a
# atribuição do valor.
LIVEBLOG_RESUMO = 400


def _limpar_html(txt):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", txt or "")).split())


def liveblog_itens(doc):
    """HTML da página -> entradas do live blog, no formato dos itens de RSS.

    Lê o `LiveBlogPosting` de schema.org e não o HTML visível, que é montado
    por JavaScript e não existe no que a página devolve."""
    blog = None
    for bloco in re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', doc, re.S):
        try:
            d = json.loads(bloco)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "LiveBlogPosting":
            blog = d
            break
    if not blog:
        return []
    itens = []
    for e in blog.get("liveBlogUpdate") or []:
        titulo = _limpar_html(e.get("headline"))
        if not titulo:
            continue
        data = e.get("datePublished")
        itens.append({
            "titulo": titulo,
            "link": e.get("url") or SKY_AO_VIVO,
            "data": (data[:19] + "Z") if data else None,
            "resumo": _limpar_html(e.get("articleBody"))[:LIVEBLOG_RESUMO],
        })
    return itens


def fetch_sky_liveblog():
    """Entradas do Transfer Centre ao vivo, no formato dos itens de RSS."""
    try:
        req = urllib.request.Request(SKY_AO_VIVO, headers={
            "User-Agent": "Mozilla/5.0 (fpl-draft-dashboard)",
            "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            bruto = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                bruto = gzip.decompress(bruto)
        itens = liveblog_itens(bruto.decode("utf-8", "replace"))
        registar("Sky · Transfer Centre ao vivo", bool(itens), f"{len(itens)} entradas")
        return itens
    except Exception as exc:
        registar("Sky · Transfer Centre ao vivo", False, exc)
        return []


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


def casar_transferencia(texto, players):
    """Um artigo de transferência é sobre **um** jogador: devolve-o, ou None.

    A ordem importa. Primeiro o **nome completo** — é o que desambigua: o
    título "Leeds sign England goalkeeper James Trafford" contém "james" e
    "trafford", e só o Trafford tem os dois; o Reece James e o Daniel James
    partilham o `web_name` "James" e apanhavam a notícia os dois. Só quando
    ninguém bate pelo nome completo se recorre ao `web_name`, e aí exige-se
    que seja um só: dois jogadores com o mesmo nome curto é ambíguo, e atribuir
    a transferência aos dois é pior do que não a atribuir a nenhum."""
    # Os padrões de nome são construídos sobre texto sem acentos: o texto tem
    # de vir pelo mesmo caminho, senão "Gyokeres" nunca casa com "Gyökeres".
    normalizado = sem_acentos(texto).lower()
    alvo = set(normalizado.replace("-", " ").split())
    completos = [p for p in players
                 if _tokens_nome(f'{p["first_name"]} {p["second_name"]}') <= alvo]
    if len(completos) == 1:
        return completos[0]
    if not completos:
        padroes = [(p,) + padroes_nome_split(p) for p in players]
        curtos = [p for p, pr, _ in padroes if pr and pr.search(normalizado)]
        if len(curtos) == 1:
            return curtos[0]
    return None


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


def pl_conteudo(tag=None, limite=20, offset=0):
    """Artigos da API oficial da PL, opcionalmente de uma etiqueta."""
    url = (f"{PL_CONTEUDO}?contentTypes=TEXT&offset={offset}&limit={limite}"
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


def pl_transferencias_artigos(paginas=3, por_pagina=100):
    """Artigos de `series:transfers`, paginados (o feed vai até 2025)."""
    artigos = []
    for i in range(paginas):
        lote = pl_conteudo("series:transfers", por_pagina, offset=i * por_pagina)
        artigos += lote
        if len(lote) < por_pagina:
            break
    return artigos


# A Wikipedia mantém a lista completa do mercado inglês numa tabela com Data,
# Jogador, clube de origem, clube de destino e **valor** — 824 linhas, das quais
# 117 são jogadores desta liga e 67 têm preço. É a única fonte com histórico:
# todos os feeds de notícias trazem 20 itens das últimas duas semanas, e a
# janela vai de maio a agosto.
#
# **Permissão**: o robots.txt bloqueia `/w/` e `/api/` (por isso nada de
# api.php), mas `/wiki/<artigo>` é permitido — só as páginas `Special:` estão
# vedadas. Extraem-se factos (nomes, clubes, valores), não texto.
WIKI_ARTIGO = "https://en.wikipedia.org/wiki/List_of_English_football_transfers_{janela}"
MESES_EN = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"])}


def _texto_celula(html_celula):
    """Célula de tabela -> texto limpo, sem marcação nem notas de rodapé.

    Pela ordem certa: primeiro fora a marcação, depois as entidades (senão um
    `&lt;b&gt;` escapado virava tag) e só então as notas, que podem vir
    escritas como `&#91;1&#93;`."""
    txt = re.sub(r"<[^>]+>", " ", html_celula)
    txt = html.unescape(txt)
    txt = re.sub(r"\[\s*\d+\s*\]", " ", txt)
    return " ".join(txt.split()).strip()


# A página tem duas tabelas com esquemas diferentes: a das transferências
# (Date, Player, Moving from, Moving to, Fee) e a dos **empréstimos**
# (Start date, End date, Name, Moving from, Moving to), que não tem valor.
# Lê-las pela posição das colunas trocava tudo na segunda — o "Ethan Wheatley"
# aparecia com "30 June 2027" no lugar do nome.
WIKI_COLUNAS = {
    "date": "data", "start date": "data", "player": "jogador", "name": "jogador",
    "moving from": "de", "moving to": "para", "fee": "valor",
}


def parse_wiki_transferencias(html):
    """Tabelas da Wikipedia -> [{data, jogador, de, para, valor}].

    As colunas são identificadas pelo **cabeçalho**, não pela ordem. A coluna
    da data usa `rowspan` para agrupar o mesmo dia: as linhas seguintes trazem
    menos células e herdam as da esquerda — sem isso apanhavam-se 77 das 824."""
    saida = []
    for tabela in re.findall(
            r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>', html, re.S):
        linhas = re.findall(r"<tr[^>]*>(.*?)</tr>", tabela, re.S)
        if not linhas:
            continue
        cabecalho = [WIKI_COLUNAS.get(_texto_celula(c).lower())
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", linhas[0], re.S)]
        if "jogador" not in cabecalho or "para" not in cabecalho:
            continue
        emprestimos = "valor" not in cabecalho
        anterior = {}
        for linha in linhas[1:]:
            cel = [_texto_celula(c) for c in
                   re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", linha, re.S)]
            if not cel:
                continue
            # Menos células do que colunas: as da esquerda vieram de um rowspan.
            herdadas = len(cabecalho) - len(cel)
            if herdadas < 0:
                continue
            reg = {}
            for i, campo in enumerate(cabecalho):
                if not campo:
                    continue
                reg[campo] = anterior.get(campo, "") if i < herdadas else cel[i - herdadas]
            if not reg.get("jogador") or not reg.get("para"):
                continue
            anterior = reg
            saida.append({
                "data": reg.get("data", ""), "jogador": reg["jogador"],
                "de": reg.get("de", ""), "para": reg["para"],
                "valor": "Loan" if emprestimos else reg.get("valor", ""),
            })
    return saida


def data_wiki_para_iso(txt):
    """'8 August 2026' -> '2026-08-08T00:00:00Z'."""
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", (txt or "").strip())
    if not m:
        return None
    mes = MESES_EN.get(m.group(2).lower())
    if not mes:
        return None
    return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}T00:00:00Z"


def valor_wiki(txt):
    """Campo Fee -> (valor, moeda, tipo). 'Free' e 'Undisclosed' não são zero
    desconhecido: são informação, e o ecrã distingue-as."""
    baixo = (txt or "").lower()
    m = re.search(r"([£€$])\s?(\d+(?:\.\d+)?)\s*m", txt or "", re.I)
    if m:
        return round(float(m.group(2)), 1), m.group(1), "valor"
    if "free" in baixo:
        return 0, "", "livre"
    if "undisclos" in baixo:
        return 0, "", "nd"
    if "loan" in baixo:
        return 0, "", "emprestimo"
    return 0, "", "outro"


# Palavras que não distinguem clube nenhum.
_CLUBE_RUIDO = {"and", "fc", "afc", "the"}


def _tokens_clube(nome):
    return {t for t in re.sub(r"[^a-z0-9 ]", " ", sem_acentos(nome or "").lower()).split()
            if t and t not in _CLUBE_RUIDO}


def envolve_clube_pl(de, para):
    """A transferência tem um clube da Premier League de um dos lados?

    Serve para apanhar homónimos: há um Reece James no Rotherham, e a linha
    "Rotherham United → Sheffield Wednesday" casava com o Reece James do
    Chelsea porque o nome é literalmente o mesmo. Nome nenhum resolve isso —
    o clube resolve. Compara-se com os nomes oficiais (os slugs de PL_CLUBES),
    que é como a Wikipedia os escreve."""
    alvos = [_tokens_clube(slug.replace("-", " ")) for slug in PL_CLUBES.values()]
    for nome in (de, para):
        t = _tokens_clube(nome)
        if t and any(t <= a or a <= t for a in alvos):
            return True
    return False


def _tokens_nome(txt):
    return {t for t in sem_acentos(txt or "").lower().replace("-", " ").split() if len(t) >= 3}


def fetch_wikipedia_transferencias(players, ano):
    """Transferências da janela, cruzadas com os jogadores desta liga.

    O cruzamento exige que **todas** as palavras do nome da Wikipedia estejam no
    nome completo do jogador do FPL. É restritivo de propósito: nas 824 linhas
    deu 117 correspondências e **zero ambiguidades**."""
    porJogador, soltas = {}, []
    for janela in (f"summer_{ano}", f"winter_{ano}%E2%80%93{str(ano + 1)[-2:]}"):
        try:
            req = urllib.request.Request(
                WIKI_ARTIGO.format(janela=janela),
                headers={"User-Agent": "fpl-draft-dashboard (dashboard pessoal de FPL)",
                         "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                bruto = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    bruto = gzip.decompress(bruto)
            linhas = parse_wiki_transferencias(bruto.decode("utf-8", "replace"))
        except Exception:
            continue  # a janela de inverno não existe até janeiro
        for r in linhas:
            alvo = _tokens_nome(r["jogador"])
            # Um nome de uma palavra só ("James") casa com meio plantel; a
            # Wikipedia escreve sempre o nome completo, por isso exigir duas
            # palavras não perde nada e evita o falso positivo.
            if len(alvo) < 2:
                continue
            # Sem nenhum clube da PL nos dois lados, não é uma transferência
            # desta liga por muito que o nome bata certo.
            if not envolve_clube_pl(r["de"], r["para"]):
                continue
            cands = [p for p in players
                     if _tokens_nome(f'{p["first_name"]} {p["second_name"]}') >= alvo]
            valor, moeda, tipo = valor_wiki(r["valor"])
            reg = {
                "data": data_wiki_para_iso(r["data"]), "de": r["de"], "para": r["para"],
                "valor": valor, "moeda": moeda, "tipo": tipo,
            }
            if len(cands) == 1:
                porJogador[str(cands[0]["id"])] = reg
            elif not cands:
                # Sem jogador na FPL não há nada a dizer ao modelo, mas a
                # transferência existe e interessa ver: ou é um reforço que a
                # FPL ainda não acrescentou, ou uma saída da liga (o Højlund
                # para o Nápoles por £38M não aparecia em lado nenhum).
                soltas.append(dict(reg, nome=r["jogador"]))
    registar("Wikipedia · mercado", bool(porJogador),
             f"{len(porJogador)} jogadores; "
             f"{sum(1 for v in porJogador.values() if v['tipo'] == 'valor')} com valor; "
             f"{len(soltas)} sem jogador na FPL")
    return porJogador, soltas


# O Guardian tem um feed dedicado ao mercado, e é de longe o que mais valores
# traz: 12 dos 20 itens contra 3 do Transfer Centre da Sky. O robots.txt não
# bloqueia nada de futebol e um RSS existe para ser lido.
#
# **Só serve para o preço, nunca para a confirmação**: o feed mistura negócios
# fechados com rumores ("Football transfer rumours:", "see £50m bid rejected")
# e quem confirma é a fonte oficial da PL. Fontes avaliadas e postas de lado:
# o Fantasy Football Scout (é um site de fantasy — "transfers" ali são as
# trocas de FPL e as mudanças de preço; os artigos de mercado real são de
# 2008-2010), a BBC (o feed de transferências tem 1 item e o de rumores 1 valor
# em 24) e o corpo dos artigos da PL, que vem sempre vazio.
GUARDIAN_MERCADO = "https://www.theguardian.com/football/transfer-window/rss"


def fetch_valores_guardian(players):
    """Valores de transferência no feed de mercado do Guardian: {id: (valor, moeda)}."""
    try:
        itens = ler_rss(GUARDIAN_MERCADO, limite=40)
    except Exception as exc:
        registar("Guardian · valores", False, exc)
        return {}
    padroes = [(p,) + padroes_nome_split(p) for p in players]
    valores = {}
    for it in itens:
        texto = sem_acentos(f'{it["titulo"]} {it["resumo"]}').lower()
        m = RE_VALOR.search(texto)
        if not m:
            continue
        valor = float(m.group("valor").replace(",", "."))
        if m.group("mult").lower().startswith(("bn", "billion")):
            valor *= 1000
        candidatos = [p for p, pr, _ in padroes if pr and pr.search(texto)]
        if not candidatos:
            candidatos = [p for p, _, sec in padroes if sec and sec.search(texto)]
        if len(candidatos) != 1:  # com um valor só, dois nomes é ambíguo demais
            continue
        chave = str(candidatos[0]["id"])
        if valor > valores.get(chave, (0,))[0]:
            valores[chave] = (round(valor, 1), m.group("moeda"))
    registar("Guardian · valores", True, f"{len(valores)} jogadores com valor")
    return valores


def transferencias_feitas(players, artigos, achados, desde=None, valores_extra=None,
                          wiki=None, soltas=None):
    """Transferências concluídas, para o separador Transferências.

    Junta as duas fontes: os artigos oficiais da PL (que confirmam o negócio
    mas não dizem o preço) e o que já foi extraído dos títulos da Sky (que traz
    os valores). Diferente do `transferencias` que alimenta o modelo — aqui
    entram também as **saídas** da Premier League, porque saber que um jogador
    se foi embora é tão útil como saber quem chegou.

    `desde`: só a janela desta época; sem isto vinham dois anos de mercado."""
    padroes = [(p,) + padroes_nome_split(p) for p in players]
    por_id = {p["id"]: p for p in players}
    feitas = {}

    def juntar(pid, titulo, link, data, valor, moeda, oficial):
        if desde and (data or "") < desde:
            return
        p = por_id.get(pid)
        if not p:
            return
        ant = feitas.get(pid)
        # O mesmo negócio costuma ter dois artigos ("agree deal" e depois
        # "completes move"): fica o mais recente, mas nunca se perde um valor.
        if ant:
            if (ant["data"] or "") >= (data or ""):
                if valor and not ant["valor"]:
                    ant.update(valor=valor, moeda=moeda)
                ant["oficial"] = ant["oficial"] or oficial
                return
            valor = valor or ant["valor"]
            moeda = moeda or ant["moeda"]
            oficial = oficial or ant["oficial"]
        # A Wikipedia manda no que é facto tabelado (data, clubes, valor); as
        # notícias mandam no que é relato (título e link).
        w = (wiki or {}).get(str(pid)) or {}
        feitas[pid] = {
            "jogador": pid, "titulo": titulo, "link": link,
            "data": w.get("data") or data,
            "de": w.get("de") or "", "para": w.get("para") or "",
            "saiu": p.get("status") in ("u", "n"),
            "valor": w.get("valor") or valor or 0,
            "moeda": w.get("moeda") or moeda or "",
            "tipo": w.get("tipo") or ("valor" if valor else "outro"),
            # A PL só publica negócios fechados; a Sky também noticia acordos
            # ainda por oficializar ("agree £30m deal for"), por isso a origem
            # da confirmação faz diferença e vai para o ecrã.
            "oficial": oficial,
        }

    for art in artigos:
        it = pl_item(art)
        achado = casar_transferencia(f'{it["titulo"]} {it["resumo"]}', players)
        for p in ([achado] if achado else []):
            v = achados.get(str(p["id"])) or {}
            extra = (valores_extra or {}).get(str(p["id"])) or (None, None)
            juntar(p["id"], it["titulo"], it["link"], it["data"],
                   v.get("valor") or extra[0], v.get("moeda") or extra[1], True)

    # Negócios que só a Sky noticiou (é de lá que vêm os valores).
    for chave, v in achados.items():
        if v.get("confirmada"):
            extra = (valores_extra or {}).get(chave) or (None, None)
            juntar(int(chave), v["titulo"], v["link"], v["data"],
                   v.get("valor") or extra[0], v.get("moeda") or extra[1],
                   v.get("fonte") == "Premier League")

    for chave, w in (wiki or {}).items():
        pid = int(chave)
        if pid not in feitas:
            juntar(pid, "", "", w.get("data"), None, None, False)
    # Negócios que a FPL ainda não conhece (reforços acabados de fechar) ou que
    # já não lhe pertencem (saídas da liga). Entram com o nome da Wikipedia e
    # sem `jogador`, porque não há nenhum a que os ligar.
    avulso = [dict(t, jogador=None, titulo="", link="", saiu=False, oficial=True)
              for t in (soltas or []) if not desde or (t.get("data") or "") >= desde]
    lista = sorted(list(feitas.values()) + avulso,
                   key=lambda t: t["data"] or "", reverse=True)
    registar("Transferências concluídas", bool(lista),
             f"{len(lista)} jogadores; {sum(1 for t in lista if t['valor'])} com valor; "
             f"{sum(1 for t in lista if t['oficial'])} confirmados pela PL")
    return lista


def fetch_pl_transferencias(players, achados, desde=None, valores_extra=None, wiki=None,
                            soltas=None):
    """Transferências confirmadas pela fonte oficial.

    O `extrair_transferencias` decide "confirmada" por regex nos títulos da
    Sky, que é um palpite; um jogador que apareça em `series:transfers` mudou
    mesmo de clube. Não traz valores — esses continuam a vir da Sky —, mas a
    confirmação sozinha já conta: isenta o jogador do castigo de "não foi
    titular no último ensaio" (o onze do clube antigo não diz nada dele)."""
    try:
        artigos = pl_transferencias_artigos()
    except Exception as exc:
        registar("Premier League · transferências", False, exc)
        return achados, []
    padroes = [(p,) + padroes_nome_split(p) for p in players]
    novas = 0
    for art in artigos:
        it = pl_item(art)
        # Só a janela desta época. O feed oficial pagina até 2025, e uma
        # transferência de há 18 meses não é "mudou de clube agora": o
        # `confirmada` isenta do castigo da pré-época e dá piso de minutos,
        # e nada disso faz sentido para quem já lá joga há meia época.
        if desde and (it["data"] or "") < desde:
            continue
        texto = f'{it["titulo"]} {it["resumo"]}'
        achado = casar_transferencia(texto, players)
        for p in ([achado] if achado else []):
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
    # O preço do Guardian também melhora o piso de minutos de quem já está
    # confirmado — é o mesmo dado, vindo de outra fonte.
    for chave, (valor, moeda) in (valores_extra or {}).items():
        alvo = achados.get(chave)
        if alvo and alvo.get("confirmada") and valor > (alvo.get("valor") or 0):
            alvo.update(valor=valor, moeda=moeda)
    # O valor da Wikipedia também melhora o piso de minutos de quem está
    # confirmado — é o mesmo dado, de uma fonte com a janela toda.
    for chave, w in (wiki or {}).items():
        alvo = achados.get(chave)
        if alvo and alvo.get("confirmada") and (w.get("valor") or 0) > (alvo.get("valor") or 0):
            alvo.update(valor=w["valor"], moeda=w["moeda"])
    return achados, transferencias_feitas(players, artigos, achados, desde,
                                          valores_extra, wiki, soltas)


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


def fetch_picks_jornada(entries, game):
    """Onze e banco de cada gestor na jornada a decorrer.

    No Draft só o onze pontua, por isso sem isto a tabela da jornada somaria o
    plantel inteiro. As escolhas só existem depois do deadline: antes disso o
    endpoint devolve 404, e a jornada fica sem picks (a tabela cai no plantel).

    Nota: as substituições automáticas (`subs`) só são aplicadas no fim da
    jornada — a meio vêm sempre vazias."""
    ev = game.get("current_event")
    if not ev:
        return {}
    equipas, falhas = {}, []
    for e in entries:
        try:
            d = get(f"/entry/{e['entry_id']}/event/{ev}")
        except Exception:
            falhas.append(e["entry_name"])
            continue
        picks = sorted(d.get("picks") or [], key=lambda x: x.get("position") or 99)
        if not picks:
            falhas.append(e["entry_name"])
            continue
        equipas[str(e["entry_id"])] = {
            "xi": [x["element"] for x in picks if (x.get("position") or 99) <= 11],
            "banco": [x["element"] for x in picks if (x.get("position") or 99) > 11],
        }
    registar("Onzes da jornada", bool(equipas),
             f"{len(equipas)}/{len(entries)} gestores" +
             (f"; sem escolhas: {', '.join(falhas)}" if falhas else ""))
    return {"evento": ev, "equipas": equipas} if equipas else {}


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
    noticias_mercado = sem_repetidos(sorted(
        fetch_sky_liveblog() + fetch_noticias_mercado(),
        key=lambda i: i.get("data") or "", reverse=True))
    # Janela desta época: 100 dias antes da primeira jornada. Sem isto vinham
    # dois anos de mercado, e o feed oficial vai até 2025.
    primeira = min((e.get("deadline_time") or "" for e in events), default="")
    desde = ((datetime.fromisoformat(primeira.replace("Z", "+00:00")) -
              timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
             if primeira else None)
    wiki_transf, wiki_soltas = fetch_wikipedia_transferencias(
        players, int(primeira[:4]) if primeira else 2026)
    transf_modelo, transf_feitas = fetch_pl_transferencias(
        players, extrair_transferencias(
            {**feeds, "Transfer Centre": noticias_mercado}, players, nomes_clubes),
        desde, fetch_valores_guardian(players), wiki_transf, wiki_soltas)

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
        "picks_jornada": fetch_picks_jornada(details["league_entries"], game),
        "preepoca": fetch_preepoca(nomes_clubes, players),
        "ffs": fetch_ffs(players, nomes_clubes),
        "bolaparada": fetch_bolaparada(nomes_clubes, players),
        "historico": completar_historico(
            snapshot_historico(players, anterior, game), players),
        "transferencias": transf_modelo,
        "conferencias": {
            "equipa": eu["entry_name"] if eu else None,
            "clubes": fetch_conferencias(clubes, meus, feeds),
        },
        "mercado": {
            "noticias": noticias_mercado,
            "transferencias_feitas": transf_feitas,
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
