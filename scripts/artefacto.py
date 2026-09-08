#!/usr/bin/env python3
"""Junta o site num ficheiro HTML unico, para publicar como Artifact.

O dashboard normal e servido pelo servir.py e le os dados de data/*.json. Um
Artifact e um ficheiro so, sem servidor por tras: o CSS, o JS e os dois
data.json vao embutidos, e o app.js usa `window.__DADOS__` quando existe.

O <head> e fornecido por quem publica, por isso aqui so sai o conteudo do
<body> (mais o titulo, que e lido do inicio do ficheiro).

Uso: python scripts/artefacto.py [saida.html]
"""
import io
import json
import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITE = os.path.join(RAIZ, "site")


def ler(*partes):
    with io.open(os.path.join(SITE, *partes), encoding="utf-8") as f:
        return f.read()


def json_seguro(texto):
    """JSON dentro de <script>: fechar a tag no meio de uma string partia a pagina."""
    return texto.replace("</", r"<\/").replace("<!--", r"<\!--")


def main():
    saida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "artefacto.html")
    html = ler("index.html")
    corpo = re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1)
    # O app.js entra inline, depois dos dados.
    corpo = re.sub(r'\s*<script src="app\.js[^"]*"></script>', "", corpo)

    dados = {}
    for modo, ficheiro in (("draft", "data.json"), ("classica", "classica.json")):
        caminho = os.path.join(SITE, "data", ficheiro)
        if os.path.exists(caminho):
            with io.open(caminho, encoding="utf-8") as f:
                dados[modo] = json.load(f)
        else:
            print(f"Aviso: {ficheiro} nao existe; o modo {modo} fica de fora.",
                  file=sys.stderr)

    # Slot próprio (não uma terceira chave em `dados`): esse dicionário é
    # iterado para o "modos: classica, draft" e para o `D = __DADOS__[modo]`
    # do app.js, e o calendário não é um modo.
    cal = {}
    caminho_cal = os.path.join(SITE, "data", "calendario.json")
    if os.path.exists(caminho_cal):
        with io.open(caminho_cal, encoding="utf-8") as f:
            cal = json.load(f)
    else:
        print("Aviso: calendario.json nao existe; o separador fica vazio.",
              file=sys.stderr)

    pagina = (
        "<title>Haaland of Fame</title>\n"
        "<style>\n" + ler("styles.css") + "\n</style>\n"
        + corpo.strip() + "\n"
        '<script type="application/json" id="dados-embutidos">'
        + json_seguro(json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
        + "</script>\n"
        "<script>window.__DADOS__ = JSON.parse("
        'document.getElementById("dados-embutidos").textContent);</script>\n'
        '<script type="application/json" id="calendario-embutido">'
        + json_seguro(json.dumps(cal, ensure_ascii=False, separators=(",", ":")))
        + "</script>\n"
        "<script>window.__CALENDARIO__ = JSON.parse("
        'document.getElementById("calendario-embutido").textContent);</script>\n'
        "<script>\n" + ler("app.js") + "\n</script>\n"
    )
    with io.open(saida, "w", encoding="utf-8") as f:
        f.write(pagina)
    tam = os.path.getsize(saida)
    print(f"OK: {saida} ({tam / 1e6:.1f} MB, modos: {', '.join(sorted(dados))})")


if __name__ == "__main__":
    main()
