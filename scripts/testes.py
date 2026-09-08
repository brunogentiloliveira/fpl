#!/usr/bin/env python3
"""Testes da recolha. Só stdlib, sem rede: usa dados sintéticos.

Uso: python scripts/testes.py

Cobre os pontos onde já apareceram erros a sério — o parsing do team news do
Scout (negações e nomes ambíguos), a correspondência de nomes com acentos e
apelidos compostos, e os dois formatos possíveis de /event/{ev}/live.
"""
import json
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as fd

FALHAS = []


def verificar(nome, condicao, detalhe=""):
    if condicao:
        print(f"  ok    {nome}")
    else:
        print(f"  FALHA {nome}: {detalhe}")
        FALHAS.append(nome)


def jogador(pid, web, primeiro, segundo, equipa=1, tipo=3):
    return {"id": pid, "web_name": web, "first_name": primeiro, "second_name": segundo,
            "team": equipa, "element_type": tipo}


# ---------- correspondência de nomes ----------

def testa_nomes():
    print("Correspondência de nomes")
    plantel = [
        jogador(1, "Ødegaard", "Martin", "Ødegaard"),
        jogador(2, "A.Becker", "Alisson", "Ramses Becker"),
        jogador(3, "B.Fernandes", "Bruno", "Borges Fernandes"),
        jogador(4, "Martinez", "Damián", "Martínez Romero"),
        jogador(5, "Virgil", "Virgil", "van Dijk"),
    ]
    verificar("Odegaard sem barra no O casa com Ødegaard",
              fd.casar_nome("Odegaard", plantel) == 1)
    verificar("Alisson casa pelo nome próprio", fd.casar_nome("Alisson", plantel) == 2)
    verificar("Bruno Fernandes casa com o web_name abreviado",
              fd.casar_nome("Bruno Fernandes", plantel) == 3)
    verificar("Van Dijk casa com apelido composto", fd.casar_nome("Van Dijk", plantel) == 5)
    verificar("nome desconhecido não casa", fd.casar_nome("Zidane", plantel) is None)
    verificar("sem_acentos traduz letras que o NFD não decompõe",
              fd.sem_acentos("Ødegaard Håland Ćurić") == "Odegaard Haland Curic",
              fd.sem_acentos("Ødegaard Håland Ćurić"))


# ---------- team news do Fantasy Football Scout ----------

def analisa_linha(texto, plantel):
    """Réplica mínima do que fetch_ffs faz por cada <li> do resumo."""
    marcas = sorted(
        (m.start(), estado)
        for estado, rx in fd.FFS_ESTADOS for m in rx.finditer(texto)
        if not fd.FFS_NEGACAO.search(texto[:m.start()])
    )
    if not marcas:
        return {}
    normalizado = fd.sem_acentos(texto).lower()
    achados = {}
    por_posicao = {}
    for p in plantel:
        rx = fd.padrao_nome(p)
        m = rx.search(normalizado) if rx else None
        if not m:
            continue
        seguintes = [e for pos, e in marcas if pos >= m.start()]
        if seguintes:
            por_posicao.setdefault(m.start(), []).append((p, seguintes[0]))
    for pos, lista in por_posicao.items():
        if len(lista) > 1:
            lista = [(p, e) for p, e in lista
                     if fd._tokens(p["web_name"]) & fd._tokens(normalizado[pos:pos + 40])]
            if len(lista) != 1:
                continue
        achados[lista[0][0]["web_name"]] = lista[0][1]
    return achados


def testa_ffs():
    print("Team news do Scout")
    spurs = [jogador(10, "Pedro Porro", "Pedro", "Porro", 2),
             jogador(11, "Solanke", "Dominic", "Solanke", 2),
             jogador(12, "Maddison", "James", "Maddison", 2)]
    r = analisa_linha("Porro out, Solanke, Maddison fit", spurs)
    verificar("estado vem da palavra-chave a seguir ao nome",
              r == {"Pedro Porro": "fora", "Solanke": "apto", "Maddison": "apto"}, r)

    liverpool = [jogador(20, "Isak", "Alexander", "Isak", 3),
                 jogador(21, "Gakpo", "Cody", "Gakpo", 3)]
    r = analisa_linha("No injury updates, Iraola on Isak + Gakpo", liverpool)
    verificar("negação anula a palavra-chave (ninguém fica fora)", r == {}, r)

    city = [jogador(30, "Matheus N.", "Matheus", "Nunes", 4),
            jogador(31, "Vitor Reis", "Vitor", "Nunes Reis", 4)]
    r = analisa_linha("Doku the only absentee, Nunes recovers", city)
    verificar("nome ambíguo entre dois do mesmo clube fica por classificar",
              "Vitor Reis" not in r, r)

    r = analisa_linha("Squad rotated for the cup", spurs)
    verificar("sem palavras-chave não inventa estados", r == {}, r)


# ---------- /event/{ev}/live ----------

def testa_live():
    print("Jornadas ao vivo")
    casos = {
        "objeto (Draft)": {"elements": {"1": {"stats": {"minutes": 90, "total_points": 8}}},
                           "fixtures": [{"team_h": 1, "team_a": 2, "finished": True}]},
        "lista (FPL clássico)": {"elements": [{"id": 1, "stats": {"minutes": 62, "total_points": 3}}],
                                 "fixtures": [{"team_h": 1, "team_a": 2, "finished": False}]},
        "stats à cabeça": {"elements": {"7": {"minutes": 45, "total_points": 2}}, "fixtures": []},
        "vazio": {"elements": {}, "fixtures": []},
    }
    for nome, live in casos.items():
        elementos = fd._elementos_live(live)
        verificar(f"lê o formato {nome}", isinstance(elementos, list))
    verificar("extrai minutos e pontos do formato objeto",
              fd._elementos_live(casos["objeto (Draft)"])[0][1]["stats"]["minutes"] == 90)

    # A linha por jornada guarda mais do que minutos e pontos: os expected vêm
    # como texto na API e têm de ficar numéricos.
    linha = fd.linha_jornada({"minutes": 78, "total_points": 9, "bps": 31,
                              "expected_goals": "0.4567", "expected_assists": "0.12",
                              "expected_goals_conceded": "1.5"})
    verificar("linha da jornada com BPS e expected",
              linha == [78, 9, 31, 0.46, 0.12, 1.5])
    verificar("campos em falta ficam a zero, não rebentam",
              fd.linha_jornada({"minutes": 5}) == [5, 0, 0, 0.0, 0.0, 0.0])

    # Estado clínico: só quem não está simplesmente apto, para poupar linhas.
    bs = {"elements": [
        {"id": 1, "status": "a", "chance_of_playing_next_round": None, "news_added": None},
        {"id": 2, "status": "a", "chance_of_playing_next_round": 100, "news_added": None},
        {"id": 3, "status": "i", "chance_of_playing_next_round": 0,
         "news_added": "2026-08-15T20:00:06Z"},
        {"id": 4, "status": "d", "chance_of_playing_next_round": 75, "news_added": "x"},
    ]}
    est = fd.estados_da_jornada(bs)
    verificar("quem está apto não ocupa espaço", "1" not in est and "2" not in est)
    verificar("lesionados e dúvidas ficam registados", set(est) == {"3", "4"}, sorted(est))
    verificar("guarda estado, hipótese e desde quando",
              est["3"] == ["i", 0, "2026-08-15T20:00:06Z"], est["3"])
    verificar("bootstrap vazio não rebenta", fd.estados_da_jornada({}) == {})

    # Jornadas guardadas antes destes campos não podem ficar presas na cache.
    JOGOS = [[1, 2, 1, 0]]
    antiga = {"finalizada": True, "equipas": [1, 2], "jogos": JOGOS,
              "stats": {"3": [90, 6]}}
    nova = {"finalizada": True, "equipas": [1, 2], "jogos": JOGOS,
            "stats": {"3": [90, 6, 28, 0.3, 0.1, 1.2]}}
    verificar("sem os emparelhamentos, a jornada é repedida",
              not fd.jornada_em_cache({k: v for k, v in nova.items() if k != "jogos"}))
    verificar("cache antiga (só min/pts) é repedida", not fd.jornada_em_cache(antiga))
    verificar("cache completa é reaproveitada", fd.jornada_em_cache(nova))
    verificar("jornada por terminar nunca vai a cache",
              not fd.jornada_em_cache({**nova, "finalizada": False}))
    verificar("jornada sem equipas é repedida",
              not fd.jornada_em_cache({**nova, "equipas": []}))


# ---------- notícias oficiais da Premier League ----------

def testa_pl():
    print("Premier League (fonte oficial)")
    # O mapa de clubes é curado porque uma etiqueta errada não dá erro: devolve
    # o feed geral. Estes dois já passaram por bons num mapeamento automático.
    verificar("todos os clubes da Sky têm etiqueta na PL",
              set(fd.SKY_CLUBES) == set(fd.PL_CLUBES),
              sorted(set(fd.SKY_CLUBES) ^ set(fd.PL_CLUBES)))
    verificar("Bournemouth usa o slug oficial, não o nome curto",
              fd.PL_CLUBES["Bournemouth"] == "afc-bournemouth")
    verificar("Spurs aponta para o Tottenham, não para o Wolverhampton",
              fd.PL_CLUBES["Spurs"] == "tottenham-hotspur")

    art = {"title": " Arsenal sign X ", "description": "  algum   resumo ",
           "date": "2026-08-21T10:00:00", "canonicalUrl": "https://exemplo/1"}
    it = fd.pl_item(art)
    verificar("artigo da PL fica no formato dos itens de RSS",
              set(it) >= {"titulo", "link", "data", "resumo", "fonte"})
    verificar("título e resumo vêm limpos",
              it["titulo"] == "Arsenal sign X" and it["resumo"] == "algum resumo")
    verificar("data fica em ISO com Z", it["data"].endswith("Z"))
    verificar("sem canonicalUrl, constrói o link pelo id",
              fd.pl_item({"title": "t", "id": 99})["link"].endswith("/99"))

    # Notícias repetidas nas duas fontes contam uma vez.
    itens = [{"titulo": "Arsenal sign X", "data": "2026-08-21T10:00:00Z"},
             {"titulo": "arsenal sign x", "data": "2026-08-20T10:00:00Z"},
             {"titulo": "Outra coisa", "data": "2026-08-19T10:00:00Z"}]
    verificar("a mesma notícia das duas fontes conta uma vez",
              len(fd.sem_repetidos(itens)) == 2)


# ---------- app.js: nomes de funções ----------

def testa_nomes_funcoes():
    print("Funções do app.js")
    # Duas funções com o mesmo nome não dão erro em JS: a segunda silencia a
    # primeira. Foi assim que `desenharTransferencias` do separador novo apagou
    # a das sugestões da clássica, e a secção ficou vazia sem nada na consola.
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = io.open(os.path.join(base, "site", "app.js"), encoding="utf-8").read()
    nomes = re.findall(r"^function\s+([A-Za-z_$][\w$]*)\s*\(", js, re.M)
    repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
    verificar("nenhuma função de topo está declarada duas vezes",
              not repetidos, repetidos)
    verificar("o app.js tem funções para verificar", len(nomes) > 50)

    # Um `const` de topo declarado duas vezes é SyntaxError e apaga a página
    # inteira — pior do que a colisão de funções, que só silencia uma delas.
    consts = re.findall(r"^(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=", js, re.M)
    repetidos_c = sorted({n for n in consts if consts.count(n) > 1})
    verificar("nenhuma constante de topo está declarada duas vezes",
              not repetidos_c, repetidos_c)

    # O tooltip da coluna "Calend." já esteve dentro de uma string de aspas
    # duplas com `' + janelaAtual() + '` lá dentro, e o utilizador lia o código.
    verificar("nenhuma string do app.js mostra concatenação por escrito",
              "' + janelaAtual() + '" not in js,
              "há uma expressão JS dentro de uma string de aspas duplas")


# ---------- cruzar transferências com jogadores ----------

def testa_casar_transferencia():
    print("Transferências: a quem pertencem")
    jog = lambda i, w, pn, ap: {"id": i, "web_name": w, "first_name": pn, "second_name": ap}
    # Três jogadores reais que colidem: dois com o web_name "James", e o
    # Trafford, que é sobre quem a notícia realmente é.
    players = [jog(1, "James", "Reece", "James"),
               jog(2, "James", "Daniel", "James"),
               jog(3, "Trafford", "James", "Trafford"),
               jog(4, "Gyökeres", "Viktor", "Gyökeres")]
    achado = fd.casar_transferencia(
        "Leeds sign England goalkeeper James Trafford from Man City", players)
    verificar("o nome completo desambigua entre homónimos",
              achado and achado["id"] == 3, achado and achado["web_name"])
    verificar("web_name partilhado por dois não atribui a nenhum",
              fd.casar_transferencia("James joins on loan", players) is None)
    verificar("web_name único ainda funciona",
              (fd.casar_transferencia("Arsenal sign Gyokeres", players) or {}).get("id") == 4)
    verificar("texto sem jogador nenhum devolve None",
              fd.casar_transferencia("Board confirms new stadium plans", players) is None)


def testa_clube_pl():
    print("Transferências: envolvem a Premier League?")
    verificar("saída para fora da liga conta (um lado é da PL)",
              fd.envolve_clube_pl("Manchester City", "Al Qadsiah"))
    verificar("entrada de fora da liga conta", fd.envolve_clube_pl("Lille", "Manchester City"))
    verificar("nomes por extenso da Wikipedia são reconhecidos",
              fd.envolve_clube_pl("Brighton & Hove Albion", "Derby County") and
              fd.envolve_clube_pl("Nottingham Forest", "Excelsior") and
              fd.envolve_clube_pl("Bournemouth", "Lorient"))
    verificar("negócio entre dois clubes de fora é rejeitado",
              not fd.envolve_clube_pl("Rotherham United", "Sheffield Wednesday"))
    verificar("campos vazios não passam por engano",
              not fd.envolve_clube_pl("", ""))


# ---------- Transfer Centre ao vivo ----------

def testa_liveblog():
    print("Transfer Centre ao vivo")
    doc = """
    <html><head>
    <script type="application/ld+json">{"@type":"WebSite","name":"Sky"}</script>
    <script type="application/ld+json">{
      "@type": "LiveBlogPosting",
      "liveBlogUpdate": [
        {"headline": "Man City complete &#x27;record&#x27; Bouaddi deal",
         "articleBody": "<p>City have completed the signing in a <b>&#163;86m</b> move.</p>",
         "datePublished": "2026-08-26T11:15:00+01:00",
         "url": "https://www.skysports.com/x/1"},
        {"headline": "", "articleBody": "sem titulo"},
        {"headline": "Sem data nem url", "articleBody": "corpo"}
      ]}</script>
    </head></html>"""
    itens = fd.liveblog_itens(doc)
    verificar("ignora o JSON-LD que não é do live blog e lê o certo", len(itens) == 2)
    verificar("entradas sem título não entram",
              all(i["titulo"] for i in itens))
    verificar("entidades HTML descodificadas no título",
              itens[0]["titulo"] == "Man City complete 'record' Bouaddi deal")
    verificar("corpo sem marcação e com o valor legível",
              itens[0]["resumo"] == "City have completed the signing in a £86m move.",
              itens[0]["resumo"])
    verificar("data em ISO com Z", itens[0]["data"] == "2026-08-26T11:15:00Z")
    verificar("sem data fica a None, sem rebentar", itens[1]["data"] is None)
    verificar("sem url cai na página do Transfer Centre",
              itens[1]["link"] == fd.SKY_AO_VIVO)
    verificar("o corpo é cortado para não arrastar o artigo todo",
              all(len(i["resumo"]) <= fd.LIVEBLOG_RESUMO for i in itens))
    verificar("página sem LiveBlogPosting devolve lista vazia",
              fd.liveblog_itens("<html></html>") == [])
    verificar("JSON inválido não rebenta a recolha",
              fd.liveblog_itens('<script type="application/ld+json">{isto nao</script>') == [])


# ---------- mercado na Wikipedia ----------

def testa_wiki():
    print("Mercado (Wikipedia)")
    # A data usa rowspan: as linhas seguintes têm 4 células e herdam-na. Sem
    # isto apanhavam-se 77 das 824 linhas da tabela real.
    html = """
    <table class="wikitable sortable">
    <tr><th>Date</th><th>Player</th><th>Moving from</th><th>Moving to</th><th>Fee</th></tr>
    <tr><td rowspan="2">8 August 2026</td><td>Bruno Guimar&#227;es</td>
        <td>Newcastle United</td><td>Arsenal</td><td>&#163;75m<sup>[1]</sup></td></tr>
    <tr><td>Joe Bloggs</td><td>Leeds United</td><td>Derby County</td><td>Free<sup>[2]</sup></td></tr>
    <tr><td>9 August 2026</td><td>Ana Silva</td><td>Porto</td><td>Fulham</td>
        <td>Undisclosed</td></tr>
    </table>"""
    linhas = fd.parse_wiki_transferencias(html)
    verificar("lê as três linhas, incluindo as que herdam a data", len(linhas) == 3)
    verificar("a linha sem data herda a de cima",
              linhas[1]["data"] == "8 August 2026" and linhas[1]["jogador"] == "Joe Bloggs")
    verificar("cabeçalho não conta como transferência",
              all(l["jogador"] != "Player" for l in linhas))
    verificar("notas de rodapé saem do texto", linhas[0]["valor"] == "£75m")
    verificar("clubes de origem e destino",
              linhas[0]["de"] == "Newcastle United" and linhas[0]["para"] == "Arsenal")

    verificar("data em inglês -> ISO",
              fd.data_wiki_para_iso("8 August 2026") == "2026-08-08T00:00:00Z")
    verificar("data com dia de dois dígitos",
              fd.data_wiki_para_iso("23 July 2026") == "2026-07-23T00:00:00Z")
    verificar("data inválida não rebenta", fd.data_wiki_para_iso("qualquer coisa") is None)

    # "Free" e "Undisclosed" são informação, não valores em falta.
    verificar("valor em libras", fd.valor_wiki("£75m") == (75.0, "£", "valor"))
    verificar("valor com decimais", fd.valor_wiki("£8.5m")[0] == 8.5)
    verificar("transferência livre", fd.valor_wiki("Free")[2] == "livre")
    verificar("valor não divulgado", fd.valor_wiki("Undisclosed")[2] == "nd")
    verificar("campo vazio não vira zero com valor", fd.valor_wiki("")[2] == "outro")

    # A segunda tabela da página é de empréstimos e tem outro esquema: sem
    # coluna de valor e com duas de data. Lida pela posição, o nome do jogador
    # saía na coluna da data.
    emprestimos = """
    <table class="wikitable">
    <tr><th>Start date</th><th>End date</th><th>Name</th>
        <th>Moving from</th><th>Moving to</th></tr>
    <tr><td>4 February 2026</td><td>30 June 2026</td><td>Tomas Kalinauskas</td>
        <td>Burton Albion</td><td>Roda JC</td></tr>
    </table>"""
    emp = fd.parse_wiki_transferencias(emprestimos)
    verificar("tabela de empréstimos: o nome vem da coluna certa",
              emp and emp[0]["jogador"] == "Tomas Kalinauskas", emp and emp[0])
    verificar("empréstimo fica marcado como tal",
              emp and fd.valor_wiki(emp[0]["valor"])[2] == "emprestimo")
    verificar("data do empréstimo é a de início",
              emp and emp[0]["data"] == "4 February 2026")
    verificar("tabela sem colunas reconhecíveis é ignorada",
              fd.parse_wiki_transferencias(
                  '<table class="wikitable"><tr><th>A</th><th>B</th></tr>'
                  "<tr><td>1</td><td>2</td></tr></table>") == [])


# ---------- retrato da época passada ----------

def testa_completar_historico():
    print("Retrato da época passada")
    # Já preenchido: tem de sair sem tocar na rede (se pedisse, rebentava aqui,
    # porque não há players nem ligação a contar).
    cheio = {"1": {"minutes": 2000, "defensive_contribution": 300, "penalties_missed": 1}}
    verificar("não repete o trabalho quando os campos já lá estão",
              fd.completar_historico(cheio, []) is cheio)
    verificar("histórico vazio passa incólume", fd.completar_historico({}, []) == {})

    # Sem jogadores para cruzar, tudo fica a zero em vez de ficar a None —
    # senão a verificação de início dava sempre em falta e repetia os pedidos.
    vazio = {"1": {"minutes": 2000}}
    saida = fd.completar_historico(vazio, [])
    verificar("campos em falta ficam a zero, não a None",
              saida["1"]["defensive_contribution"] == 0
              and saida["1"]["penalties_missed"] == 0)
    verificar("e à segunda já não há nada a fazer",
              fd.completar_historico(saida, []) is saida)


# ---------- Transfermarkt: quem saiu da liga ----------

def testa_transfermarkt():
    print("Transfermarkt (direção do negócio)")
    # Cada clube tem duas tabelas e a primeira célula do cabeçalho diz qual é.
    html = """
    <table><tr><th>Entradas</th><th>Idade</th><th>Origem</th><th>Valor</th></tr>
    <tr><td>Bruno Guimar&#227;es B. Guimar&#227;es</td><td>28</td><td>Newcastle</td>
        <td>87,50 M &#8364;</td></tr></table>
    <table><tr><th>Sa&#237;das</th><th>Idade</th><th>Destino</th><th>Valor</th></tr>
    <tr><td>Ollie Watkins O. Watkins</td><td>30</td><td>Al Hilal</td>
        <td>51,00 M &#8364;</td></tr>
    <tr><td>Bruno Guimar&#227;es B. Guimar&#227;es</td><td>28</td><td>Arsenal</td>
        <td>87,50 M &#8364;</td></tr></table>"""
    entradas, saidas = fd.transfermarkt_tabelas(html)
    verificar("separa entradas de saídas pelo cabeçalho",
              len(entradas) == 1 and len(saidas) == 2, (entradas, saidas))
    verificar("o cabeçalho não conta como jogador",
              all("Idade" not in n for n in entradas + saidas))

    players = [
        {"id": 1, "first_name": "Ollie", "second_name": "Watkins", "web_name": "Watkins"},
        {"id": 2, "first_name": "Bruno", "second_name": "Guimarães", "web_name": "Bruno G."},
    ]
    # O Guimarães está nas duas listas (mudou entre clubes da PL): fica.
    # O Watkins só está nas saídas: foi-se embora.
    def casar(nome):
        alvo = fd._tokens_nome(nome)
        c = [p for p in players
             if fd._tokens_nome(f'{p["first_name"]} {p["second_name"]}') >= alvo]
        return c[0] if len(c) == 1 else None
    ficaram = {p["id"] for p in (casar(n) for n in entradas) if p}
    fora = {p["id"] for p in (casar(n) for n in saidas) if p and p["id"] not in ficaram}
    verificar("quem só está nas saídas conta como fora da liga", fora == {1}, fora)
    verificar("quem muda entre clubes da liga não conta como fora", 2 not in fora)
    verificar("página sem tabelas não rebenta", fd.transfermarkt_tabelas("<html/>") == ([], []))


# ---------- ficheiro unico para publicar ----------

def testa_artefacto():
    print("Artefacto de ficheiro único")
    # JSON dentro de <script>: fechar a tag no meio de uma string partia a
    # página inteira, e o conteúdo vem de notícias que não controlo.
    import artefacto
    perigo = '{"t":"</script><b>ola</b>"}'
    seguro = artefacto.json_seguro(perigo)
    verificar("fecho de script escapado", "</script>" not in seguro, seguro)
    verificar("continua a ser JSON válido",
              json.loads(seguro.replace("<\/", "</"))["t"].startswith("</script>"))
    verificar("comentário HTML escapado",
              "<!--" not in artefacto.json_seguro('{"t":"<!-- x"}'))


# ---------- ficheiros curados ----------

def testa_ficheiros():
    print("Ficheiros curados")
    base = os.path.dirname(os.path.abspath(__file__))
    for nome, chave in (("preepoca.json", "clubes"), ("bolaparada.json", "clubes")):
        caminho = os.path.join(base, nome)
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
            verificar(f"{nome} é JSON válido com clubes", bool(dados.get(chave)))
        except (OSError, ValueError) as exc:
            verificar(f"{nome} é JSON válido com clubes", False, exc)

    with open(os.path.join(base, "bolaparada.json"), encoding="utf-8") as f:
        bp = json.load(f)["clubes"]
    sem_pen = [c for c, d in bp.items() if not d.get("penaltis")]
    verificar("todos os clubes têm batedor de penáltis", not sem_pen, sem_pen)
    conf_ok = all(d.get("confianca") in ("alta", "media") for d in bp.values())
    verificar("confiança declarada em todos os clubes", conf_ok)

    with open(os.path.join(base, "preepoca.json"), encoding="utf-8") as f:
        pe = json.load(f)["clubes"]
    sem_fonte = [c for c, d in pe.items() if not d.get("fonte")]
    verificar("cada onze de pré-época tem fonte", not sem_fonte, sem_fonte)


CAL_HTML = """
<select id="epoca_id">
  <option value="155">2025/2026</option>
  <option value="156" selected>2026/2027</option>
  <option value="157">2027/2028</option>
</select>
<table><tr><th></th><th>J</th><th>V</th><th>E</th><th>D</th><th>DG</th>
<th>A</th><th>AA</th><th>V</th><th>US</th><th>F</th><th></th><th></th></tr>
<tr id="12253550" class="parent">
 <td class="h2h">h2h</td><td class="double">2027-05-30</td><td>16:00</td>
 <td>(C)</td><td><a href="/equipa/sunderland/91"><img src="x.png"></a></td>
 <td class="text"><a href="/equipa/sunderland/91?epoca_id=156">Sunderland</a></td>
 <td class="result"><a href="/jogo/2027-05-30-sunderland-manchester-city/12253550">-</a></td>
 <td class="text">Premier League 26/27</td><td class="away">J38</td>
 <td class="double right">h2h</td></tr>
<tr id="12624711" class="parent">
 <td class="h2h">h2h</td><td class="double">2026-10-14</td><td>20:00</td>
 <td>(F)</td><td><a href="/equipa/paris-saint-germain"><img src="x.png"></a></td>
 <td class="text"><a href="/equipa/paris-saint-germain">PSG</a></td>
 <td class="result"><a href="/jogo/x/12624711">-</a></td>
 <td class="text">UEFA Champions League 26/27</td><td class="away">&nbsp;</td>
 <td class="double right"></td></tr>
<tr id="11999001" class="parent">
 <td class="form">V</td><td class="double">2026-08-12</td><td>20:00</td>
 <td></td><td><a href="/equipa/paris-saint-germain"><img src="x.png"></a></td>
 <td class="text"><a href="/equipa/paris-saint-germain">PSG</a></td>
 <td class="result"><a href="/jogo/y/11999001">2-1</a></td>
 <td class="text">UEFA Super Cup 2026</td><td class="away">F</td>
 <td class="multimedia right"></td></tr>
<tr id="11999002" class="parent">
 <td class="h2h">h2h</td><td class="double">2026-09-16</td><td>19:45</td>
 <td>(C)</td><td><a href="/equipa/brighton-hove-albion"><img src="x.png"></a></td>
 <td class="text"><a href="/equipa/brighton-hove-albion">Brighton &amp; Hove Albion</a></td>
 <td class="result"><a href="/jogo/z/11999002">-</a></td>
 <td class="text">Carabao Cup 26/27</td><td class="away">3R</td>
 <td class="double right">h2h</td></tr>
</table>
"""


def testa_calendario_parser():
    print("Calendário: parser do zerozero")
    import fetch_calendario as fc
    jogos = fc.linhas_jogos(CAL_HTML)
    verificar("lê as 4 linhas de jogo e ignora o cabeçalho de 13 células",
              len(jogos) == 4, len(jogos))

    por_id = {j["id"]: j for j in jogos}
    verificar("guarda o id do jogo, que é a chave estável entre recolhas",
              12253550 in por_id and 12624711 in por_id, sorted(por_id))

    pl = por_id[12253550]
    verificar("lê data, hora e casa/fora", pl["data"] == "2027-05-30"
              and pl["hora"] == "16:00" and pl["casa"] is True, pl)
    verificar("junta pelo slug e não pelo nome", pl["adv_slug"] == "sunderland",
              pl["adv_slug"])
    verificar("o slug perde a query string",
              "?" not in pl["adv_slug"] and "epoca_id" not in pl["adv_slug"])

    # Campo neutro: a célula do (C)/(F) vem vazia. Um `== "(C)"` dava "fora".
    sup = por_id[11999001]
    verificar("campo neutro fica com casa=None, não com casa=False",
              sup["casa"] is None, sup["casa"])
    verificar("célula 0 com V/E/D marca o jogo como já disputado",
              sup["jogado"] is True and por_id[12253550]["jogado"] is False)

    # Última célula vazia em 30 dos jogos por jogar — e são os mais próximos.
    ucl = por_id[12624711]
    verificar("linha com a última célula vazia é lida na mesma",
              ucl["comp_bruta"].startswith("UEFA Champions"), ucl["comp_bruta"])
    verificar("&nbsp; na ronda não vira texto literal",
              ucl["ronda"] == "", repr(ucl["ronda"]))

    # Entidades nomeadas: a página é UTF-8 mas usa &amp;, &ccedil;, &nbsp;.
    lc = por_id[11999002]
    verificar("entidades HTML são desescapadas depois de tirar a marcação",
              lc["adv_nome"] == "Brighton & Hove Albion", lc["adv_nome"])
    verificar("lê a ronda quando existe", lc["ronda"] == "3R", lc["ronda"])

    # A época lê-se da página; escrevê-la à mão dá um ficheiro vazio com ✓.
    verificar("lê a época seleccionada da própria página",
              fc.epoca_da_pagina(CAL_HTML) == (156, "2026/2027"),
              fc.epoca_da_pagina(CAL_HTML))
    verificar("sem <select> devolve None", fc.epoca_da_pagina("<html></html>") is None)


def main():
    print("Testes da recolha\n")
    testa_nomes()
    testa_ffs()
    testa_live()
    testa_nomes_funcoes()
    testa_pl()
    testa_casar_transferencia()
    testa_clube_pl()
    testa_transfermarkt()
    testa_artefacto()
    testa_liveblog()
    testa_wiki()
    testa_completar_historico()
    testa_ficheiros()
    testa_calendario_parser()
    print()
    if FALHAS:
        print(f"{len(FALHAS)} teste(s) a falhar: {', '.join(FALHAS)}")
        return 1
    print("Tudo a passar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
