"""Recolha completa, sem servidor: o que o atualizar.cmd faz antes de abrir o site.

Existe para a rotina agendada (skill precisao-modelo). Uma execucao sem ninguem a ver so pode
correr comandos autorizados a partida, e a autorizacao e dada pelo texto do comando: definir as
variaveis de ambiente na linha de comandos mudava esse texto de shell para shell, e sem elas a
recolha da classica corria na mesma, mas sem o plantel, sem erro nenhum.

Uso:  py scripts/recolher.py
"""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Os mesmos ids do atualizar.cmd. Uma variavel ja definida no ambiente tem precedencia.
IDS = {"LEAGUE_ID": "12258", "FPL_ENTRY_ID": "2420779", "FPL_LEAGUE_ID": "779399"}

PASSOS = ["fetch_data.py", "fetch_classica.py", "fetch_calendario.py"]


def main():
    env = dict(os.environ)
    for nome, valor in IDS.items():
        env.setdefault(nome, valor)
    # A saida pode estar a ser capturada (sem consola), e ai o Python do Windows usa cp1252.
    env.setdefault("PYTHONIOENCODING", "utf-8")

    falhas = []
    for passo in PASSOS:
        print(f"== {passo}", flush=True)
        feito = subprocess.run([sys.executable, str(RAIZ / "scripts" / passo)], cwd=RAIZ, env=env)
        if feito.returncode != 0:
            falhas.append(passo)

    if falhas:
        print("Falharam: " + ", ".join(falhas), flush=True)
        return 1
    print("Recolha completa.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
