#!/usr/bin/env python3
"""Servidor local do site com cache desligado.

O http.server normal nao envia Cache-Control, e o browser pode mostrar
versoes antigas do index.html/app.js depois de uma atualizacao do projeto.
Uso: python scripts/servir.py [porto]  (por omissao 8000)
"""
import http.server
import os
import socket
import sys


class SemCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def ip_local():
    """IP desta maquina na rede local, para abrir o site no telemovel.

    Abrir um socket UDP para um endereco externo nao envia nada: so faz o
    sistema escolher a interface de saida, e dai tiramos o IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
    os.chdir(site)
    print(f"A servir {os.getcwd()} (sem cache)")
    print(f"  neste PC:      http://localhost:{port}")
    ip = ip_local()
    if ip:
        print(f"  no telemovel:  http://{ip}:{port}")
        print("  (mesma rede Wi-Fi; da primeira vez o Windows pode pedir para")
        print("   autorizar o Python em redes privadas)")
    http.server.ThreadingHTTPServer(("", port), SemCacheHandler).serve_forever()


if __name__ == "__main__":
    main()
