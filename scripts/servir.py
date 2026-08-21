#!/usr/bin/env python3
"""Servidor local do site com cache desligado.

O http.server normal nao envia Cache-Control, e o browser pode mostrar
versoes antigas do index.html/app.js depois de uma atualizacao do projeto.
Uso: python scripts/servir.py [porto]  (por omissao 8000)
"""
import http.server
import os
import sys


class SemCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
    os.chdir(site)
    print(f"A servir {os.getcwd()} em http://localhost:{port} (sem cache)")
    http.server.ThreadingHTTPServer(("", port), SemCacheHandler).serve_forever()


if __name__ == "__main__":
    main()
