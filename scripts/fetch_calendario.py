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
# 2025"). A ordem importa — "Conference" antes de "Cup", "Super Cup" antes de
# "Cup", senão a Supertaça Europeia caía na Taça da Liga.
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

    O nome não serve de chave: 6 dos 20 divergem ("Manchester City" vs
    "Man City", "Tottenham" vs "Spurs"), o que são 27% das linhas. E um
    recurso por tokens é pior — *city* liga o Manchester City ao Hull City.
    O slug está no HTML em todas as linhas e bate exactamente com o
    zerozero.json.
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
