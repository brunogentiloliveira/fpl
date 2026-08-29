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

    # Jornadas guardadas antes destes campos não podem ficar presas na cache.
    antiga = {"finalizada": True, "equipas": [1, 2], "stats": {"3": [90, 6]}}
    nova = {"finalizada": True, "equipas": [1, 2], "stats": {"3": [90, 6, 28, 0.3, 0.1, 1.2]}}
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


def main():
    print("Testes da recolha\n")
    testa_nomes()
    testa_ffs()
    testa_live()
    testa_nomes_funcoes()
    testa_pl()
    testa_casar_transferencia()
    testa_clube_pl()
    testa_artefacto()
    testa_liveblog()
    testa_wiki()
    testa_completar_historico()
    testa_ficheiros()
    print()
    if FALHAS:
        print(f"{len(FALHAS)} teste(s) a falhar: {', '.join(FALHAS)}")
        return 1
    print("Tudo a passar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
