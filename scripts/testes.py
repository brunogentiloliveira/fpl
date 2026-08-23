#!/usr/bin/env python3
"""Testes da recolha. Só stdlib, sem rede: usa dados sintéticos.

Uso: python scripts/testes.py

Cobre os pontos onde já apareceram erros a sério — o parsing do team news do
Scout (negações e nomes ambíguos), a correspondência de nomes com acentos e
apelidos compostos, e os dois formatos possíveis de /event/{ev}/live.
"""
import json
import os
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
