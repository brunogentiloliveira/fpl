#!/usr/bin/env python3
"""Testes da recolha. Só stdlib, sem rede: usa dados sintéticos.

Uso: python scripts/testes.py

Cobre os pontos onde já apareceram erros a sério — o parsing do team news do
Scout (negações e nomes ambíguos), a correspondência de nomes com acentos e
apelidos compostos, e os dois formatos possíveis de /event/{ev}/live.
"""
import contextlib
import json
import io
import os
import re
import sys
import tempfile

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
    nomes = re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", js, re.M)
    repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
    verificar("nenhuma função de topo está declarada duas vezes",
              not repetidos, repetidos)
    verificar("o app.js tem funções para verificar", len(nomes) > 50)
    # O regex antigo (`^function\s+`) não apanhava `async function` — nem
    # `carregarCalendario` nem `main` entravam na lista, e o guarda contra
    # nomes duplicados tinha um ponto cego precisamente nas funções async.
    verificar("apanha também 'async function' (ex.: carregarCalendario, main)",
              {"carregarCalendario", "main"}.issubset(set(nomes)), nomes)

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

    # Teste funcional: gera o artefacto a sério com um calendario.json
    # perigoso (o revisor injectou isto à mão e confirmou que escapa; isto
    # prende essa confirmação num teste automático). Os dois testes que
    # existiam aqui antes só faziam grep no código-fonte à procura de
    # "__CALENDARIO__" e da ausência de dados["calendario"] — uma mudança
    # que tirasse o json_seguro() só do embed do calendário passava a
    # suite inteira sem ninguém dar conta, porque o grep nunca gera nada.
    caminho_cal = os.path.join(artefacto.SITE, "data", "calendario.json")
    with open(caminho_cal, "rb") as f:
        cal_original = f.read()
    marca = "TESTE_CALENDARIO_PERIGOSO"
    payload_script = f"</script><script>{marca}(1)</script>"
    payload_comentario = f"<!--{marca}-->"
    cal_perigoso = {
        "generated_at": "2026-09-07T00:00:00Z",
        "clubes": {"1": {"nome": f"Sunderland{payload_script}{payload_comentario}"}},
    }
    try:
        with io.open(caminho_cal, "w", encoding="utf-8") as f:
            json.dump(cal_perigoso, f, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as tmp:
            saida_tmp = os.path.join(tmp, "artefacto_teste.html")
            argv_antigo = sys.argv
            saida_capturada = io.StringIO()
            try:
                sys.argv = ["artefacto.py", saida_tmp]
                with contextlib.redirect_stdout(saida_capturada):
                    artefacto.main()
            finally:
                sys.argv = argv_antigo
            with io.open(saida_tmp, encoding="utf-8") as f:
                html = f.read()
    finally:
        # Repor o calendário verdadeiro mesmo que o teste falhe a meio.
        with open(caminho_cal, "wb") as f:
            f.write(cal_original)

    linha = saida_capturada.getvalue()
    verificar("o slot window.__CALENDARIO__ chega ao artefacto gerado",
              "window.__CALENDARIO__ = JSON.parse" in html, "falta o slot")
    verificar("o </script> do calendário sai escapado no artefacto gerado",
              payload_script not in html, "payload cru encontrado no artefacto")
    verificar("...e a forma escapada do </script> chega ao ficheiro",
              payload_script.replace("</", r"<\/") in html,
              "forma escapada não encontrada")
    verificar("o <!-- do calendário sai escapado no artefacto gerado",
              payload_comentario not in html, "comentário cru encontrado no artefacto")
    verificar("...e a forma escapada do <!-- chega ao ficheiro",
              payload_comentario.replace("<!--", r"<\!--") in html,
              "forma escapada do comentário não encontrada")
    # Verificação funcional em vez de grep: se o calendário fosse parar ao
    # dicionário `dados` (um "modo"), esta linha passaria a dizer "modos:
    # calendario, classica, draft".
    verificar("o calendário não vira um 'modo' na linha impressa pelo artefacto.py",
              "modos: classica, draft" in linha, linha)


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
    verificar("jogo fora fica com casa=False, não confundido com campo neutro",
              ucl["casa"] is False, ucl["casa"])

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


def testa_calendario_nomes():
    print("Calendário: competições e clubes")
    import fetch_calendario as fc

    casos = [
        ("Premier League 26/27", "PL"),
        ("UEFA Champions League 26/27", "UCL"),
        ("UEFA Europa League 26/27", "UEL"),
        ("UEFA Conference League 26/27", "UECL"),
        ("UEFA Conference League (Qual.) 26/27", "UECL"),
        ("Carabao Cup 26/27", "LC"),
        ("EFL League Cup 26/27", "LC"),
        # O rótulo muda com o patrocinador e com o ano civil: fixar a string
        # inteira quebrava na época seguinte.
        ("The Emirates FA Cup 25/26", "FAC"),
        ("The FA Cup 26/27", "FAC"),
        ("The FA Community Shield 2026", "SUP"),
        ("Community Shield 2025", "SUP"),
        ("UEFA Super Cup 2026", "SUP"),
        ("Qualquer Outra Coisa", "OUT"),
    ]
    for bruta, esperado in casos:
        verificar(f"{bruta!r} -> {esperado}",
                  fc.normalizar_comp(bruta) == esperado, fc.normalizar_comp(bruta))

    # O adv_nome das linhas de jogo diverge do nome da FPL em 6 dos 20
    # clubes ("Brighton & Hove Albion" vs "Brighton"). Juntar por esse nome
    # deixava 4 dos 12 jogos de taça entre clubes da PL sem adversário.
    mapa = fc.ler_mapa_zerozero()
    slugs = fc.slugs_para_id(mapa, {"1": {"name": "Arsenal"}})
    verificar("o mapa tem os 20 clubes", len(mapa) == 20, len(mapa))
    verificar("todos os caminhos são /equipa/<slug>",
              all(v["caminho"].startswith("/equipa/") for v in mapa.values()))
    # Os slugs que precisam de id têm-no: sem ele a página redirecciona.
    com_id = {"brentford": "2600", "sunderland": "91", "aston-villa": "76",
              "hull-city": "5096", "coventry-city": "2584"}
    caminhos = {v["caminho"] for v in mapa.values()}
    for slug, ident in com_id.items():
        verificar(f"o caminho do {slug} leva id",
                  f"/equipa/{slug}/{ident}" in caminhos, sorted(caminhos))

    # A correcção central da tarefa: juntar pelo slug e não pelo nome. Isto
    # exercita `slugs_para_id` a sério, com os 20 clubes reais da FPL —
    # sem estas três afirmações a chamada acima não prova nada sobre o que
    # a função devolve.
    with io.open(os.path.join(fd.OUT_DIR, "data.json"), encoding="utf-8") as f:
        clubes_reais = json.load(f)["teams"]
    slugs_reais = fc.slugs_para_id(mapa, clubes_reais)
    verificar("com os 20 clubes reais da FPL, os 20 slugs encontram id",
              len(slugs_reais) == 20, len(slugs_reais))
    # /equipa/sunderland/91: a chave pára no primeiro "/" — prova que é o
    # slug (não o caminho todo) que serve de chave.
    verificar("a chave do sunderland é só o slug e aponta para o id 20",
              slugs_reais.get("sunderland") == 20, slugs_reais.get("sunderland"))
    # Com um clubes_fpl incompleto (só o Arsenal), a função não rebenta:
    # regista os 19 que faltam no diagnóstico e devolve só o que encontrou.
    verificar("clubes_fpl parcial não rebenta, devolve só o que encontrou",
              slugs == {"arsenal": 1}, slugs)


def testa_calendario_fuso():
    print("Calendário: fuso horário")
    import fetch_calendario as fc

    # O zerozero publica hora local do Reino Unido e a API publica UTC. Medido:
    # 16 de 38 linhas do Man City diferem 60 min, e a separação bate a 100% com
    # o horário de verão britânico. Escrever data+"T"+hora+"Z" ficava errado em
    # 51% dos jogos — intermitente, que é o pior tipo.
    linhas_pl = [
        {"data": "2026-10-11", "hora": "16:30", "adv_slug": "liverpool"},   # verão
        {"data": "2027-01-06", "hora": "20:00", "adv_slug": "chelsea"},     # inverno
    ]
    api = [
        {"data": "2026-10-11", "kickoff": "2026-10-11T15:30:00Z"},
        {"data": "2027-01-06", "kickoff": "2027-01-06T20:00:00Z"},
    ]
    desvios = fc.desvios_por_data(linhas_pl, api)
    verificar("mede +60 min no horário de verão",
              desvios.get("2026-10-11") == 60, desvios)
    verificar("mede 0 min no horário de inverno",
              desvios.get("2027-01-06") == 0, desvios)

    iso, incerta = fc.para_utc("2026-10-11", "20:00", desvios)
    verificar("aplica o desvio medido nesse dia",
              iso == "2026-10-11T19:00:00Z" and incerta is False, (iso, incerta))

    # Um jogo europeu a meio da semana não tem jogo da PL no mesmo dia: usa-se
    # a âncora mais próxima, que é o mesmo regime de horário. 14 de outubro
    # fica a 3 dias da âncora de verão (11/10) e a mais de 80 dias da de
    # inverno (06/01) — a aritmética tem de escolher a de verão.
    iso, incerta = fc.para_utc("2026-10-14", "20:00", desvios)
    verificar("sem âncora no próprio dia, usa a mais próxima",
              iso == "2026-10-14T19:00:00Z" and incerta is False, (iso, incerta))

    iso, incerta = fc.para_utc("2026-10-14", None, desvios)
    verificar("sem hora, devolve só a data e marca-a incerta",
              iso == "2026-10-14" and incerta is True, (iso, incerta))

    verificar("sem âncoras nenhumas, marca incerta em vez de inventar",
              fc.para_utc("2026-10-14", "20:00", {})[1] is True)

    # Aritmética à volta da meia-noite: subtrair 60 min a um jogo às 00:30
    # muda o dia, não só a hora. Sem a divisão inteira sobre os minutos totais
    # isto dava hora negativa (-00:30) em vez de recuar um dia.
    iso, incerta = fc.para_utc("2026-10-11", "00:30", desvios)
    verificar("desvio que cruza a meia-noite recua também o dia",
              iso == "2026-10-10T23:30:00Z" and incerta is False, (iso, incerta))


def testa_calendario_validacao():
    print("Calendário: validação contra a API")
    import fetch_calendario as fc

    api = [{"data": "2026-10-11", "adv_slug": "liverpool", "casa": False,
            "kickoff": "2026-10-11T15:30:00Z", "dif": 4, "evento": 6},
           {"data": "2026-10-17", "adv_slug": "ipswich-town", "casa": True,
            "kickoff": "2026-10-17T14:00:00Z", "dif": 2, "evento": 7}]
    boas = [{"data": "2026-10-11", "adv_slug": "liverpool", "casa": False},
            {"data": "2026-10-17", "adv_slug": "ipswich-town", "casa": True}]

    aceites, recusadas = fc.validar_pl(boas, api)
    verificar("linhas que batem passam todas", len(aceites) == 2 and not recusadas)

    # Uma remarcação não pode derrubar o clube: 700 das 760 linhas ainda vão
    # mexer com as escolhas televisivas, e os jogos europeus são a única coisa
    # que esta fonte acrescenta.
    ma = boas + [{"data": "2027-03-01", "adv_slug": "chelsea", "casa": True}]
    aceites, recusadas = fc.validar_pl(ma, api)
    verificar("uma divergência distante recusa a linha, não o clube",
              len(aceites) == 2 and len(recusadas) == 1, (len(aceites), recusadas))

    # A validação é por DATA. Comparar data-hora rejeitaria 155 dos 380 jogos
    # por causa do fuso, e a regra de recusa deitava fora os 20 clubes.
    verificar("a hora não entra na comparação",
              len(fc.validar_pl(boas, api)[0]) == 2)

    # semanas_criticas: a PL confirma as escolhas televisivas com 5-6
    # semanas de antecedência — uma divergência aí dentro não é uma
    # remarcação normal, e escala para recusar o clube inteiro mesmo sendo
    # só 1 divergência (o limiar de "mais de 2" sozinho não a apanhava).
    from datetime import datetime, timedelta, timezone
    hoje = datetime.now(timezone.utc).date()
    perto = (hoje + timedelta(days=10)).isoformat()
    longe = (hoje + timedelta(days=300)).isoformat()

    com_divergencia_perto = boas + [{"data": perto, "adv_slug": "chelsea", "casa": True}]
    aceites, recusadas = fc.validar_pl(com_divergencia_perto, api, semanas_criticas=6)
    verificar("divergência dentro da janela crítica recusa o clube, não só a linha",
              aceites == [] and len(recusadas) == 3, (aceites, recusadas))

    com_divergencia_longe = boas + [{"data": longe, "adv_slug": "chelsea", "casa": True}]
    aceites, recusadas = fc.validar_pl(com_divergencia_longe, api, semanas_criticas=6)
    verificar("a mesma divergência, fora da janela crítica, recusa só a linha",
              len(aceites) == 2 and len(recusadas) == 1, (aceites, recusadas))


def testa_calendario_epoca():
    print("Calendário: a época lida tem de bater com a API")
    import fetch_calendario as fc

    # O bug crítico: escrever `epoca_id=156` à mão fazia o zerozero ecoar de
    # volta a época pedida (medido ao vivo: ?epoca_id=155 devolve sempre
    # "2025/2026", mesmo depois de a época ter mudado), e a verificação de
    # então — só o <select> — via sempre a página "confirmar-se" a si
    # própria. A segunda fonte (o ano do 1º deadline da FPL, independente do
    # zerozero) é o que apanha uma página a mostrar a época errada.
    pagina_errada = """
    <select id="epoca_id">
      <option value="155" selected>2025/2026</option>
      <option value="156">2026/2027</option>
    </select>
    """
    pagina_certa = """
    <select id="epoca_id">
      <option value="156" selected>2026/2027</option>
    </select>
    """

    verificar("caminho de aborto dispara com uma época que não bate com a API",
              fc.confirmar_epoca(pagina_errada, 2026) is None)
    verificar("não dispara quando as duas fontes concordam",
              fc.confirmar_epoca(pagina_certa, 2026) == (156, "2026/2027"),
              fc.confirmar_epoca(pagina_certa, 2026))
    verificar("dispara também sem <select> nenhum na página",
              fc.confirmar_epoca("<html></html>", 2026) is None)
    verificar("sem ano vindo da API (falha de rede), dispara — nunca confia às cegas",
              fc.confirmar_epoca(pagina_certa, None) is None)

    # As duas peças, isoladas: o <select> sozinho não distingue a página
    # errada da certa (lê o que lá está, e é só isso). É a segunda fonte
    # que apanha a divergência.
    verificar("epoca_da_pagina sozinha só lê o que o <select> diz",
              fc.epoca_da_pagina(pagina_errada) == (155, "2025/2026"))
    verificar("epoca_coerente é que compara com a API e apanha a divergência",
              fc.epoca_coerente("2025/2026", 2026) is False
              and fc.epoca_coerente("2026/2027", 2026) is True)


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
    testa_calendario_nomes()
    testa_calendario_fuso()
    testa_calendario_validacao()
    testa_calendario_epoca()
    print()
    if FALHAS:
        print(f"{len(FALHAS)} teste(s) a falhar: {', '.join(FALHAS)}")
        return 1
    print("Tudo a passar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
