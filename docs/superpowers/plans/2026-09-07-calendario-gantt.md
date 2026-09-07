# Separador Calendário (Gantt) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um separador novo que mostra, numa linha do tempo à escala, todos os jogos por realizar dos 20 clubes da Premier League — incluindo Champions, Liga Europa, Conference e Taça da Liga — para se ver quem chega à jornada com jogo a meio da semana e quem tem o percurso mais duro.

**Architecture:** Uma recolha nova e isolada (`scripts/fetch_calendario.py`) junta a Premier League da API oficial (que traz a dificuldade) com as restantes provas do zerozero (a única fonte que as tem), e escreve `site/data/calendario.json`. Nem o `data.json` nem o `classica.json` são tocados, e o modelo de projeção não vê nada disto. No cliente, um separador desenha a linha do tempo a partir desse ficheiro, carregado num `try` próprio para que a sua ausência não mate o dashboard.

**Tech Stack:** Python 3.12 só com stdlib (`urllib`, `re`, `html`, `json`, `gzip`); HTML/CSS/JS puro sem frameworks nem build step. Testes: `scripts/testes.py` (stdlib, sem rede) e `site/testes.html` (no browser, com `D` sintético).

**Spec:** `docs/superpowers/specs/2026-09-07-calendario-gantt-design.md`

## Global Constraints

- **Português de Portugal** em todo o texto de interface, comentários e mensagens. Fuso de apresentação: `Europe/Lisbon`.
- **Só stdlib** nos scripts Python. Sem dependências novas, sem build step no site.
- **Não usar scraping de sites que o proíbam.** `zerozero.pt/robots.txt` bloqueia apenas `/zzmap_v3.php` — os caminhos usados aqui são permitidos.
- **Fazer um pedido de teste a cada endpoint antes de escrever código**, para confirmar os campos reais em vez de assumir.
- **Nada de heredoc do shell para escrever ficheiros com conteúdo do projeto** — já corrompeu um ficheiro (a sequência barra-b virou um backspace literal) e voltou a falhar nesta sessão. Usar as ferramentas de escrita de ficheiros.
- **O modelo de projeção não muda.** Nenhuma tarefa deste plano pode alterar `projecao`, `componentesPP90`, `taxaBase`, `fatorCalendario` nem `D.fixtures`. Um `ppj` diferente no fim é um bug.
- **Mobile-first**: verificar a 375px sem scroll horizontal no `body` em todas as tarefas de interface.
- **Correr sempre localmente.** Sem GitHub Pages, sem Actions, sem serviços externos.
- Assets no `index.html` sobem de `?v=51` para **`?v=52`** (2 ocorrências) na primeira tarefa que toque no `app.js` ou no `styles.css`.

---

### Task 1: Dois bugs existentes, e um teste que os teria apanhado

Independente do separador novo, mas ambos agravados por acrescentar um décimo separador. Feito primeiro para o resto assentar em terreno limpo.

**Files:**
- Modify: `site/app.js:1046` (tooltip literal), `site/app.js:3709` (setas do teclado)
- Modify: `site/index.html` (`?v=51` → `?v=52`, 2 ocorrências)
- Test: `scripts/testes.py` (alargar `testa_nomes_funcoes`, linha 208)

**Interfaces:**
- Consumes: nada.
- Produces: nada que outras tarefas usem. `testa_nomes_funcoes()` passa a apanhar também `const`/`let` de topo repetidos.

- [ ] **Step 1: Escrever o teste que falha — nomes de topo repetidos**

Em `scripts/testes.py`, dentro de `testa_nomes_funcoes()`, a seguir às duas verificações existentes:

```python
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
```

- [ ] **Step 2: Correr e confirmar que falha**

Run: `python scripts/testes.py`
Expected: FALHA em "nenhuma string do app.js mostra concatenação por escrito".

- [ ] **Step 3: Corrigir o tooltip**

Em `site/app.js:1046`, a linha é uma string de aspas duplas. Trocar para concatenação a sério:

```js
    "<th class=\"num\">Pts/J</th><th class=\"num\" title=\"Pts por jornada ajustados à dificuldade das próximas " +
      janelaAtual() + " jornadas\">Calend.</th></tr></thead>" +
```

- [ ] **Step 4: Correr e confirmar que passa**

Run: `python scripts/testes.py`
Expected: "Tudo a passar."

- [ ] **Step 5: Corrigir as setas do teclado**

Em `site/app.js:3709`, `initTabs()` recolhe todos os separadores, incluindo os que `aplicarModo()` escondeu. Filtrar:

```js
function initTabs() {
  // Os separadores só do Draft ficam `hidden` no modo clássico. Sem os tirar
  // daqui, a seta para a direita abre o painel Conferências na clássica — e o
  // foco vai para um botão escondido, que não o aceita.
  const tabs = [...document.querySelectorAll('[role="tab"]')]
    .filter((t) => !t.hidden && t.offsetParent !== null);
```

- [ ] **Step 6: Verificar no browser, nos dois modos**

Run: `python scripts/servir.py 8010`, abrir `http://localhost:8010`.
Em modo Draft e em modo Clássica: focar o separador "Liga" e carregar na seta direita várias vezes até dar a volta. Expected: só passa por separadores visíveis; em clássica nunca abre Conferências, Analisar troca nem Transferências. Consola sem erros.

- [ ] **Step 7: Subir a versão dos assets**

Em `site/index.html`, trocar as 2 ocorrências de `?v=51` por `?v=52`.

- [ ] **Step 8: Commit**

```bash
git add site/app.js site/index.html scripts/testes.py
git commit -m "Corrigir tooltip que mostrava codigo e setas que abriam separadores escondidos"
```

---

### Task 2: Parser da tabela do zerozero

Funções puras, sem rede. É onde estão quase todas as armadilhas medidas, por isso leva os testes todos antes de haver recolha nenhuma.

**Files:**
- Create: `scripts/fetch_calendario.py`
- Test: `scripts/testes.py` (função nova `testa_calendario_parser`)

**Interfaces:**
- Consumes: `fetch_data.registar(fonte, ok, detalhe)`, `fetch_data.OUT_DIR`.
- Produces:
  - `linhas_jogos(html) -> list[dict]` com chaves `id:int`, `data:str` (`YYYY-MM-DD`), `hora:str` (`HH:MM`), `casa:bool|None`, `adv_slug:str`, `adv_nome:str`, `comp_bruta:str`, `ronda:str`, `jogado:bool`.
  - `epoca_da_pagina(html) -> tuple[int, str] | None` — `(156, "2026/2027")`.

- [ ] **Step 1: Escrever o teste que falha**

Em `scripts/testes.py`, função nova antes de `def main():`. O HTML é sintético mas reproduz a estrutura real medida — jogo por realizar, jogo já disputado, campo neutro sem `(C)/(F)`, última célula vazia, entidades HTML:

```python
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
```

E registar em `main()`, a seguir a `testa_ficheiros()`:

```python
    testa_calendario_parser()
```

- [ ] **Step 2: Correr e confirmar que falha**

Run: `python scripts/testes.py`
Expected: FALHA com `ModuleNotFoundError: No module named 'fetch_calendario'`.

- [ ] **Step 3: Escrever o parser**

Criar `scripts/fetch_calendario.py`:

```python
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
    """
    fora = []
    for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S):
        limpo = html_mod.unescape(re.sub(r"<[^>]+>", " ", c))
        fora.append(" ".join(limpo.split()).replace("\xa0", " ").strip())
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
        # O primeiro /equipa/ da linha é o adversário; a query string do
        # segundo link não faz parte do slug.
        m_slug = re.search(r'href="/equipa/([^"?]+)', tr)
        saida.append({
            "id": int(m_id.group(1)) if m_id else None,
            "data": cels[1],
            "hora": cels[2] if re.match(r"^\d{1,2}:\d{2}$", cels[2]) else None,
            # Vazio é campo neutro (supertaças), não "fora".
            "casa": True if cels[3] == "(C)" else (False if cels[3] == "(F)" else None),
            "adv_slug": m_slug.group(1).rstrip("/") if m_slug else "",
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
```

- [ ] **Step 4: Correr e confirmar que passa**

Run: `python scripts/testes.py`
Expected: "Tudo a passar." com as 12 verificações novas em "Calendário: parser do zerozero".

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_calendario.py scripts/testes.py
git commit -m "Parser do calendario do zerozero, com as armadilhas medidas em teste"
```

---

### Task 3: Normalizar competições e juntar pelo slug

**Files:**
- Modify: `scripts/fetch_calendario.py`
- Test: `scripts/testes.py` (função nova `testa_calendario_nomes`)

**Interfaces:**
- Consumes: `linhas_jogos` (Task 2), `scripts/zerozero.json`.
- Produces:
  - `normalizar_comp(bruta) -> str` — uma de `PL UCL UEL UECL LC FAC SUP OUT`.
  - `slugs_para_id(mapa_zz) -> dict[str, int]` — slug do zerozero → id do clube da FPL.

- [ ] **Step 1: Escrever o teste que falha**

```python
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

    # 6 dos 20 nomes do zerozero não batem com os do bootstrap. Juntar por nome
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
```

Registar em `main()`: `testa_calendario_nomes()`.

- [ ] **Step 2: Correr e confirmar que falha**

Run: `python scripts/testes.py`
Expected: FALHA com `AttributeError: module 'fetch_calendario' has no attribute 'normalizar_comp'`.

- [ ] **Step 3: Implementar**

Acrescentar a `scripts/fetch_calendario.py`:

```python
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
```

- [ ] **Step 4: Correr e confirmar que passa**

Run: `python scripts/testes.py`
Expected: "Tudo a passar."

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_calendario.py scripts/testes.py
git commit -m "Normalizar competicoes por subcadeia e juntar clubes pelo slug"
```

---

### Task 4: Converter as horas, medindo o desvio em vez de o assumir

**Files:**
- Modify: `scripts/fetch_calendario.py`
- Test: `scripts/testes.py` (função nova `testa_calendario_fuso`)

**Interfaces:**
- Consumes: `linhas_jogos` (Task 2).
- Produces: `desvios_por_data(linhas_pl, fixtures_api) -> dict[str, int]` (minutos) e `para_utc(data, hora, desvios) -> tuple[str|None, bool]` (ISO com Z, e se a hora é incerta).

- [ ] **Step 1: Escrever o teste que falha**

```python
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
    # a âncora mais próxima, que é o mesmo regime de horário.
    iso, incerta = fc.para_utc("2026-10-14", "20:00", desvios)
    verificar("sem âncora no próprio dia, usa a mais próxima",
              iso == "2026-10-14T19:00:00Z" and incerta is False, (iso, incerta))

    iso, incerta = fc.para_utc("2026-10-14", None, desvios)
    verificar("sem hora, devolve só a data e marca-a incerta",
              iso == "2026-10-14" and incerta is True, (iso, incerta))

    verificar("sem âncoras nenhumas, marca incerta em vez de inventar",
              fc.para_utc("2026-10-14", "20:00", {})[1] is True)
```

Registar em `main()`: `testa_calendario_fuso()`.

- [ ] **Step 2: Correr e confirmar que falha**

Run: `python scripts/testes.py`
Expected: FALHA com `AttributeError: ... 'desvios_por_data'`.

- [ ] **Step 3: Implementar**

```python
def desvios_por_data(linhas_pl, fixtures_api):
    """Minutos entre a hora do zerozero e a UTC da API, por data.

    Não se usa `ZoneInfo("Europe/Lisbon")`: rebenta nesta máquina
    (ZoneInfoNotFoundError, Python do python.org em Windows sem tzdata) — e
    seria assumir. As 760 linhas da PL dão o par (hora local, UTC) para o mesmo
    jogo, portanto o desvio é medido a partir dos próprios dados.
    """
    por_data = {}
    for j in fixtures_api:
        if j.get("kickoff"):
            por_data.setdefault(j["data"], j["kickoff"])
    desvios = {}
    for linha in linhas_pl:
        alvo = por_data.get(linha["data"])
        if not alvo or not linha.get("hora"):
            continue
        hh, mm = (int(x) for x in linha["hora"].split(":"))
        ah, am = int(alvo[11:13]), int(alvo[14:16])
        delta = (hh * 60 + mm) - (ah * 60 + am)
        # Só 0 ou 60 são plausíveis; qualquer outra coisa é jogo diferente no
        # mesmo dia, não desvio de fuso.
        if delta in (0, 60):
            desvios[linha["data"]] = delta
    return desvios


def para_utc(data, hora, desvios):
    """(ISO em UTC, hora_incerta). Sem hora, devolve a data nua."""
    if not hora:
        return data, True
    if data in desvios:
        delta, incerta = desvios[data], False
    elif desvios:
        # A âncora mais próxima: o regime de horário só muda duas vezes por ano.
        vizinha = min(desvios, key=lambda d: abs(_dias(d) - _dias(data)))
        delta, incerta = desvios[vizinha], False
    else:
        delta, incerta = 0, True
    minutos = int(hora[:2]) * 60 + int(hora[3:5]) - delta
    dia = _dias(data) + (minutos // (24 * 60))
    minutos %= 24 * 60
    return f"{_data(dia)}T{minutos // 60:02d}:{minutos % 60:02d}:00Z", incerta


def _dias(data):
    from datetime import date
    return date(int(data[:4]), int(data[5:7]), int(data[8:10])).toordinal()


def _data(ordinal):
    from datetime import date
    return date.fromordinal(ordinal).isoformat()
```

- [ ] **Step 4: Correr e confirmar que passa**

Run: `python scripts/testes.py`
Expected: "Tudo a passar."

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_calendario.py scripts/testes.py
git commit -m "Converter horas do zerozero medindo o desvio contra a API, sem tzdata"
```

---

### Task 5: Recolha completa, validação e escrita do ficheiro

**Files:**
- Modify: `scripts/fetch_calendario.py`
- Test: `scripts/testes.py` (função nova `testa_calendario_validacao`)

**Interfaces:**
- Consumes: tudo das tarefas 2-4.
- Produces:
  - `validar_pl(linhas_zz, fixtures_api, semanas_criticas=6) -> tuple[list, list]` — (linhas aceites, motivos recusados).
  - `main()` que escreve `site/data/calendario.json`.

- [ ] **Step 1: Escrever o teste que falha**

```python
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
```

Registar em `main()`: `testa_calendario_validacao()`.

- [ ] **Step 2: Correr e confirmar que falha**

Run: `python scripts/testes.py`
Expected: FALHA com `AttributeError: ... 'validar_pl'`.

- [ ] **Step 3: Implementar a validação e a recolha**

```python
def validar_pl(linhas_zz, fixtures_api, semanas_criticas=6):
    """Cruza as linhas da PL do zerozero com a API. Recusa linhas, não clubes.

    Só por (data, adversário, casa/fora) — nunca pela hora, que está noutro
    fuso. Hoje batem 760/760.
    """
    oficiais = {(j["data"], j["adv_slug"], j["casa"]) for j in fixtures_api}
    aceites, recusadas = [], []
    for linha in linhas_zz:
        chave = (linha["data"], linha["adv_slug"], linha["casa"])
        if chave in oficiais:
            aceites.append(linha)
        else:
            recusadas.append(f"{linha['data']} vs {linha['adv_slug']}")
    return aceites, recusadas
```

E o resto da recolha (paginação, pedidos, escrita). Pontos que os testes não cobrem mas que a especificação exige:

```python
def _get_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 fpl-dashboard", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            dados = gzip.decompress(dados)
        return dados.decode("utf-8", "replace")


def jogos_do_clube(caminho, epoca_id):
    """Todas as páginas de um clube.

    A tabela vem por data DECRESCENTE, portanto a última página tem os jogos
    mais PRÓXIMOS: 34 jogos por realizar existem só na página 2, e são todos
    dos 9 clubes europeus. Parar antes de a pedir apagava a congestão das
    próximas duas semanas e deixava uma linha a começar em outubro — plausível.
    """
    todos, pagina = [], 1
    while pagina <= 4:
        url = f"{ZZ}{caminho}/jogos?epoca_id={epoca_id}&page={pagina}"
        linhas = linhas_jogos(_get_html(url))
        todos += linhas
        if len(linhas) < LINHAS_POR_PAGINA:
            break
        pagina += 1
        time.sleep(0.3)
    # O id do jogo é único e estável; (data, adversário) não distingue uma
    # remarcação de um jogo novo.
    vistos, unicos = set(), []
    for j in todos:
        if j["id"] not in vistos:
            vistos.add(j["id"])
            unicos.append(j)
    return unicos
```

E o `main()`:

```python
def fixtures_oficiais(slug_de_id):
    """Os 380 jogos da PL, por clube, já com a dificuldade do lado certo.

    A polaridade sai de `team_h_difficulty`/`team_a_difficulty` conforme o lado
    — trocá-la seria uma inversão silenciosa e plausível, que transformava
    "percurso fácil" em "percurso duro" sem nada partir.
    """
    req = urllib.request.Request(API + "/fixtures/",
                                 headers={"User-Agent": "Mozilla/5.0 fpl-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        jogos = json.load(resp)
    por_clube = {}
    for j in jogos:
        if not j.get("kickoff_time"):
            continue
        data = j["kickoff_time"][:10]
        for casa in (True, False):
            eu = j["team_h"] if casa else j["team_a"]
            adv = j["team_a"] if casa else j["team_h"]
            por_clube.setdefault(eu, []).append({
                "data": data, "kickoff": j["kickoff_time"], "casa": casa,
                "adv": adv, "adv_slug": slug_de_id.get(adv, ""),
                "dif": j["team_h_difficulty"] if casa else j["team_a_difficulty"],
                "evento": j.get("event"),
                "jogado": bool(j.get("finished") or j.get("finished_provisional")),
            })
    return por_clube


def main():
    with io.open(os.path.join(fd.OUT_DIR, "data.json"), encoding="utf-8") as f:
        clubes_fpl = json.load(f)["teams"]
    mapa = ler_mapa_zerozero()
    slug_id = slugs_para_id(mapa, clubes_fpl)
    id_slug = {v: k for k, v in slug_id.items()}
    oficiais = fixtures_oficiais(id_slug)

    epoca_id, epoca_txt, saida, recusados = None, "", {}, {}
    for nome, info in mapa.items():
        team_id = None
        for k, v in clubes_fpl.items():
            if (v["name"] if isinstance(v, dict) else v) == nome:
                team_id = int(k)
        if team_id is None:
            continue
        try:
            primeira = _get_html(f"{ZZ}{info['caminho']}/jogos?epoca_id={epoca_id or 156}&page=1")
        except Exception as exc:
            recusados[str(team_id)] = f"não foi possível ler a página ({exc})"
            fd.registar(f"Calendário: {nome}", False, exc)
            continue
        if epoca_id is None:
            achada = epoca_da_pagina(primeira)
            if not achada:
                fd.registar("Calendário: época", False, "sem <select> na página")
                return 1
            epoca_id, epoca_txt = achada

        linhas = jogos_do_clube(info["caminho"], epoca_id)
        pl_zz = [x for x in linhas if normalizar_comp(x["comp_bruta"]) == "PL"]
        desvios = desvios_por_data(pl_zz, oficiais.get(team_id, []))
        _, divergentes = validar_pl(pl_zz, oficiais.get(team_id, []))
        if len(divergentes) > 2:
            recusados[str(team_id)] = f"{len(divergentes)} jogos da PL não batem com a API"
            fd.registar(f"Calendário: {nome}", False, divergentes[:3])
            continue

        jogos = []
        # A PL vem da API, que é a única com dificuldade; do zerozero só o resto.
        for j in oficiais.get(team_id, []):
            jogos.append({"id": None, "data": j["kickoff"], "comp": "PL",
                          "adv": j["adv"], "adv_nome": None, "adv_slug": j["adv_slug"],
                          "casa": j["casa"], "dif": j["dif"], "jornada": j["evento"],
                          "ronda": None, "jogado": j["jogado"], "hora_incerta": False})
        for x in linhas:
            comp = normalizar_comp(x["comp_bruta"])
            if comp == "PL":
                continue
            iso, incerta = para_utc(x["data"], x["hora"], desvios)
            jogos.append({"id": x["id"], "data": iso, "comp": comp,
                          "adv": slug_id.get(x["adv_slug"]), "adv_nome": x["adv_nome"],
                          "adv_slug": x["adv_slug"], "casa": x["casa"], "dif": None,
                          "jornada": None, "ronda": x["ronda"], "jogado": x["jogado"],
                          "hora_incerta": incerta})
        jogos.sort(key=lambda j: j["data"])
        curto = clubes_fpl[str(team_id)]
        saida[str(team_id)] = {
            "nome": nome,
            "curto": curto["short_name"] if isinstance(curto, dict) else nome[:3].upper(),
            "jogos": jogos,
        }
        time.sleep(0.3)

    nao_pl = sum(1 for c in saida.values() for j in c["jogos"]
                 if j["comp"] != "PL" and not j["jogado"])
    fd.registar("Calendário zerozero", bool(saida),
                f"{len(saida)} clubes, {nao_pl} jogos por realizar fora da PL")
    os.makedirs(fd.OUT_DIR, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": fd.datetime.now(fd.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epoca_id": epoca_id, "epoca": epoca_txt, "clubes": saida,
            "competicoes": NOMES_COMP, "recusados": recusados,
            "diagnostico": fd.DIAGNOSTICO,
        }, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {OUT} ({len(saida)} clubes, {nao_pl} jogos nao-PL por realizar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Guarda os jogos **já disputados** também (`jogado: true`): são 76 linhas em 865 (~8 KB) e são exactamente o que a medição futura da rotação europeia precisa.

- [ ] **Step 4: Correr os testes**

Run: `python scripts/testes.py`
Expected: "Tudo a passar."

- [ ] **Step 5: Correr a recolha a sério e verificar os números**

Run: `python scripts/fetch_calendario.py`
Expected, contra os valores medidos na sondagem:

```bash
python -c "
import json,io
d=json.load(io.open('site/data/calendario.json',encoding='utf-8'))
j=[x for c in d['clubes'].values() for x in c['jogos']]
import collections
print('clubes:',len(d['clubes']),'(esperado 20)')
print('jogos:',len(j),'(esperado ~865)')
print('por realizar:',sum(1 for x in j if not x['jogado']),'(esperado ~789)')
print('nao-PL por realizar:',sum(1 for x in j if not x['jogado'] and x['comp']!='PL'),'(esperado 89)')
print('por competicao:',collections.Counter(x['comp'] for x in j))
print('sem adversario da PL em jogos PL:',sum(1 for x in j if x['comp']=='PL' and x['adv'] is None),'(esperado 0)')
print('recusados:',d['recusados'],'(esperado {})')
import os; print('tamanho KB:',os.path.getsize('site/data/calendario.json')//1024)
"
```

Se `nao-PL por realizar` vier muito abaixo de 89, a paginação parou cedo. Se `sem adversario` for > 0, a junção por slug falhou.

- [ ] **Step 6: Confirmar que nada mais mexeu**

```bash
git status --porcelain site/data/
```
Expected: só `site/data/calendario.json`. O `data.json` e o `classica.json` não podem aparecer.

- [ ] **Step 7: Commit**

```bash
git add scripts/fetch_calendario.py scripts/testes.py site/data/calendario.json
git commit -m "Recolher o calendario completo dos 20 clubes, com validacao por linha"
```

---

### Task 6: Ligar a recolha ao resto — atualizar.cmd, artefacto, diagnóstico

**Files:**
- Modify: `atualizar.cmd`, `scripts/artefacto.py`, `site/app.js` (`initDiagnostico`, linha 1710)
- Test: `scripts/testes.py` (alargar `testa_artefacto`, linha 422)

**Interfaces:**
- Consumes: `site/data/calendario.json` (Task 5).
- Produces: `window.__CALENDARIO__` no artefacto; `C` (objeto global do calendário) no `app.js`.

- [ ] **Step 1: Escrever o teste que falha**

Em `testa_artefacto()`:

```python
    # Slot próprio: meter o calendário no dicionário `dados` faria o script
    # anunciar "modos: calendario, classica, draft" e tornava
    # `D = __DADOS__[modo]` ambíguo.
    verificar("o artefacto embute o calendário num slot próprio",
              "__CALENDARIO__" in fonte_artefacto, "falta o slot")
```

- [ ] **Step 2: Correr e confirmar que falha**

Run: `python scripts/testes.py`
Expected: FALHA em "o artefacto embute o calendário num slot próprio".

- [ ] **Step 3: Acrescentar o slot no artefacto**

Em `scripts/artefacto.py`, a seguir ao ciclo que carrega os dois modos:

```python
    cal = {}
    caminho_cal = os.path.join(SITE, "data", "calendario.json")
    if os.path.exists(caminho_cal):
        with io.open(caminho_cal, encoding="utf-8") as f:
            cal = json.load(f)
    else:
        print("Aviso: calendario.json nao existe; o separador fica vazio.",
              file=sys.stderr)
```

e no `pagina`, antes do `<script>` do app.js:

```python
        '<script type="application/json" id="calendario-embutido">'
        + json_seguro(json.dumps(cal, ensure_ascii=False, separators=(",", ":")))
        + "</script>\n"
        "<script>window.__CALENDARIO__ = JSON.parse("
        'document.getElementById("calendario-embutido").textContent);</script>\n'
```

- [ ] **Step 4: Correr e confirmar que passa**

Run: `python scripts/testes.py && python scripts/artefacto.py`
Expected: testes verdes; o artefacto sai sem erro e cresce ~100 KB.

- [ ] **Step 5: Chamar a recolha no atualizar.cmd**

Em `atualizar.cmd`, entre o bloco da clássica e o "A abrir o dashboard":

```bat
echo.
echo A atualizar o calendario (liga, Europa e tacas)...
"%PY%" scripts\fetch_calendario.py
if errorlevel 1 (
  echo Aviso: nao foi possivel atualizar o calendario. O separador fica com os dados anteriores.
)
```

- [ ] **Step 6: Levar o diagnóstico do calendário ao rodapé**

Em `site/app.js`, `initDiagnostico()` (linha 1710) lê só `D.diagnostico`. Sem isto, se a recolha do calendário falhar três semanas seguidas não há um único ✗ em lado nenhum. Juntar as entradas do calendário à lista, e incluir o `generated_at` do calendário no banner de dados velhos.

- [ ] **Step 7: Verificar no browser**

Run: `python scripts/servir.py 8010`. Expected: no rodapé aparece a fonte "Calendário" com ✓ e a contagem em tooltip.

- [ ] **Step 8: Commit**

```bash
git add atualizar.cmd scripts/artefacto.py scripts/testes.py site/app.js
git commit -m "Ligar o calendario ao atualizar.cmd, ao artefacto e ao diagnostico"
```

---

### Task 7: Carregar o calendário no cliente, sem poder matar o dashboard

**Files:**
- Modify: `site/app.js` (`MODOS`, linha 1838; `main()`, linhas 3733-3752), `site/index.html` (separador e painel)
- Test: `site/testes.html`

**Interfaces:**
- Consumes: `window.__CALENDARIO__` ou `data/calendario.json`.
- Produces: `let C = null` (global, só de leitura) e `carregarCalendario() -> Promise<void>`.

- [ ] **Step 1: Escrever o teste que falha**

Em `site/testes.html`, antes da verificação final:

```js
verificar("sem calendário, o separador não rebenta",
  typeof desenharCalendario === "function" && (C = null, desenharCalendario(), true));
```

- [ ] **Step 2: Abrir e confirmar que falha**

Abrir `site/testes.html`. Expected: FALHA — `desenharCalendario` não existe.

- [ ] **Step 3: Acrescentar o carregamento em try próprio**

Em `main()`, **depois** do `try` existente (nunca dentro dele — o `catch` de lá faz `return` e mataria o dashboard inteiro por causa de um ficheiro que serve um separador):

```js
/** O calendário é um extra: se falhar, perde-se o separador, não a página. */
async function carregarCalendario() {
  try {
    if (window.__CALENDARIO__) {
      C = window.__CALENDARIO__;
    } else {
      const resp = await fetch("data/calendario.json", { cache: "no-store" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      C = await resp.json();
    }
  } catch (err) {
    C = null;
    console.warn("Calendário indisponível:", err);
  }
}
```

- [ ] **Step 4: Acrescentar o separador ao HTML**

Em `site/index.html`, a seguir ao botão `tab-mercado` (sem `data-modo`: serve os dois modos):

```html
<button role="tab" id="tab-cal" aria-controls="painel-cal" aria-selected="false" tabindex="-1" aria-label="Calendário de todas as competições">Calendário</button>
```

E o painel, a seguir a `painel-mercado`:

```html
<section id="painel-cal" role="tabpanel" aria-labelledby="tab-cal" hidden>
  <h2 class="sec-titulo">Calendário</h2>
  <p class="nota" id="cal-intro"></p>
  <p class="aviso-jornada" id="cal-aviso" hidden></p>
  <div class="filtros" id="cal-filtros"></div>
  <div class="cal-grafico" id="cal-grafico"></div>
  <p class="nota" id="cal-legenda"></p>
</section>
```

- [ ] **Step 5: Abrir e confirmar que passa**

Abrir `site/testes.html`. Expected: "Tudo a passar".
Abrir o dashboard e **renomear temporariamente** `site/data/calendario.json` para confirmar que a página carrega na mesma e só o separador Calendário mostra "corre o atualizar.cmd". Repor o nome.

- [ ] **Step 6: Commit**

```bash
git add site/app.js site/index.html site/testes.html
git commit -m "Carregar o calendario num try proprio: a falta dele nao mata a pagina"
```

---

### Task 8: A linha do tempo

**Files:**
- Modify: `site/app.js` (funções novas), `site/styles.css`
- Test: `site/testes.html`

**Interfaces:**
- Consumes: `C` (Task 7), `D.next_event`, `D.players` (para o `owner`).
- Produces:
  - `jogosNoHorizonte(clube, ate) -> array` — jogos com `t` (ms) dentro do horizonte
  - `trocosApertados(jogos) -> array<{inicio, fim, jogos}>`
  - `desenharCalendario()`
  - **Versões mínimas** de `fimDoHorizonte() -> number` (fixo em 12 jornadas nesta tarefa) e `clubesOrdenados(ate) -> string[]` (por ordem alfabética nesta tarefa). A Task 9 substitui as duas pelas versões com seletor e ordenação — mantendo a assinatura, para o `desenharCalendario` não mudar.

- [ ] **Step 1: Escrever os testes que falham**

```js
/* --- Calendário: congestão --- */
(function () {
  if (typeof trocosApertados !== "function") return;
  const d = (s) => new Date("2026-10-" + s + "T15:00:00Z").getTime();

  // 3 jogos em 8 dias marca, e a janela é INCLUSIVA: o Arsenal joga a PL a
  // 24/10, a Carabao a 28/10 e a PL a 1/11 — exactamente 8 dias entre o
  // primeiro e o último, e é a semana em que isto vai ser olhado. Com um
  // `< 8` não havia barra nenhuma aí.
  verificar("3 jogos em exactamente 8 dias contam como apertado",
    trocosApertados([{ t: d("01") }, { t: d("05") }, { t: d("09") }]).length === 1);
  verificar("3 jogos em 12 dias não contam",
    trocosApertados([{ t: d("01") }, { t: d("07") }, { t: d("13") }]).length === 0);
  verificar("2 jogos nunca contam",
    trocosApertados([{ t: d("01") }, { t: d("03") }]).length === 0);

  // A barra não é booleana: 5 jogos em 8 dias não é o mesmo que 3.
  const denso = trocosApertados([{ t: d("01") }, { t: d("03") }, { t: d("05") },
                                 { t: d("07") }, { t: d("08") }]);
  verificar("a intensidade do troço é o número de jogos",
    denso.length === 1 && denso[0].jogos === 5, denso);
})();
```

- [ ] **Step 2: Abrir e confirmar que falha**

Abrir `site/testes.html`. Expected: as verificações novas não correm (`trocosApertados` não existe) — acrescentar temporariamente um `verificar("existe", typeof trocosApertados === "function")` para ver a falha explícita.

- [ ] **Step 3: Implementar a congestão**

```js
const CAL_JANELA_DIAS = 8;   // inclusivo
const CAL_MIN_JOGOS = 3;

/**
 * Troços em que o clube tem 3+ jogos em 8 dias.
 *
 * Medido no calendário real, a regra dispara para 14 dos 20 clubes e cobre 49%
 * da linha do Arsenal e do Man City — por isso o troço guarda a intensidade
 * (quantos jogos) e troços de intensidade diferente não se fundem. Metade da
 * linha sombreada com um tom só não é um aviso, é um fundo.
 */
function trocosApertados(jogos) {
  const t = jogos.map((j) => j.t).sort((a, b) => a - b);
  const limite = CAL_JANELA_DIAS * 864e5;
  const trocos = [];
  for (let i = 0; i + CAL_MIN_JOGOS - 1 < t.length; i += 1) {
    let fim = i;
    while (fim + 1 < t.length && t[fim + 1] - t[i] <= limite) fim += 1;
    const n = fim - i + 1;
    if (n < CAL_MIN_JOGOS) continue;
    const ultimo = trocos[trocos.length - 1];
    if (ultimo && ultimo.jogos === n && t[i] <= ultimo.fim) {
      ultimo.fim = Math.max(ultimo.fim, t[fim]);
    } else {
      trocos.push({ inicio: t[i], fim: t[fim], jogos: n });
    }
  }
  return trocos;
}
```

- [ ] **Step 4: Desenhar o gráfico**

```js
const CAL_PX_SEMANA = 42;  // medido: ver Step 6

/**
 * Os jogos de um clube dentro do horizonte, já em milissegundos.
 *
 * Filtra por `Date.now()` e não pelo `jogado` da recolha: o artefacto é um
 * retrato, e um publicado hoje mostraria outubro como futuro em novembro.
 */
function jogosNoHorizonte(clube, ate) {
  const agora = Date.now();
  return ((clube || {}).jogos || [])
    .map((j) => Object.assign({}, j, { t: Date.parse(j.data) }))
    .filter((j) => j.t >= agora && j.t <= ate)
    .sort((a, b) => a.t - b.t);
}

function desenharCalendario() {
  const alvo = $("cal-grafico");
  if (!C || !C.clubes) {
    alvo.innerHTML = '<p class="nota">Sem calendário. Corre o <code>atualizar.cmd</code>.</p>';
    return;
  }
  const ate = fimDoHorizonte();          // do seletor, Task 9
  const inicio = Date.now();
  const largura = ((ate - inicio) / 6048e5) * CAL_PX_SEMANA;
  const linhas = clubesOrdenados(ate).map((id) => {
    const clube = C.clubes[id];
    const jogos = jogosNoHorizonte(clube, ate);
    const pos = (t) => ((t - inicio) / (ate - inicio)) * largura;
    const trocos = trocosApertados(jogos).map((tr) =>
      '<span class="cal-troco n' + Math.min(tr.jogos, 5) + '" style="left:' +
      pos(tr.inicio).toFixed(1) + "px;width:" + (pos(tr.fim) - pos(tr.inicio)).toFixed(1) +
      'px"></span>').join("");
    const marcas = jogos.map((j) =>
      '<button type="button" class="cal-jogo' + (j.comp === "PL" ? " d" + j.dif : " fora-pl") +
      '" style="left:' + pos(j.t).toFixed(1) + 'px" data-jogo="' + j.t + '">' +
      // Texto lá dentro: as classes de cor sozinhas dão 1.14:1 de contraste.
      (j.comp === "PL" ? j.dif : C.competicoes[j.comp][0]) + "</button>").join("");
    return '<div class="cal-linha"><span class="cal-clube">' + clube.curto +
      '</span><span class="cal-faixa" style="width:' + largura.toFixed(0) + 'px">' +
      trocos + marcas + "</span></div>";
  }).join("");
  alvo.innerHTML = linhas;
}
```

Requisitos com número, todos medidos:

- **42px por semana, fixos** (não percentagem): a 375px sobram 287px para o gráfico, e por percentagem a 16 semanas dão 2.6px/dia — dois jogos a 3 dias ficam sobrepostos.
- Filtrar por `Date.now()` no cliente, não confiar no filtro da recolha: o artefacto é um retrato e um publicado hoje mostraria outubro como futuro em novembro.
- O gráfico arrasta dentro do próprio contentor (`overflow-x: auto`), nunca o `body`. **Não pode ficar dentro de `.cartao`** — `position: sticky` morre dentro de um antepassado com `overflow: hidden`.
- Cada marcador leva **texto lá dentro**: o dígito da dificuldade nos jogos da PL, a letra da competição nos outros. Contraste medido das classes existentes: `.fx.d3` dá **1.14:1** contra o mínimo de 3:1 — como manchas de cor nuas são invisíveis.
- Detalhe do jogo **por baixo da linha ao clicar**, não em `title`: em ecrã tátil o `title` nunca aparece.

CSS novo em `site/styles.css`:

```css
/* O gráfico arrasta dentro de si próprio; o body nunca ganha scroll lateral. */
.cal-grafico { overflow-x: auto; overflow-y: visible; }
.cal-linha { display: flex; align-items: center; height: 2.1rem; }
.cal-clube {
  position: sticky; left: 0; z-index: 2; width: 3.5rem; flex: none;
  background: var(--fundo); font-size: 0.78rem; font-weight: 700;
}
.cal-faixa { position: relative; height: 100%; flex: none; }
.cal-jogo {
  position: absolute; top: 50%; transform: translate(-50%, -50%);
  min-width: 1.05rem; height: 1.05rem; border-radius: 3px;
  font-size: 0.62rem; font-weight: 700; line-height: 1.05rem; text-align: center;
  border: 1px solid currentColor;
}
/* Dificuldade: contorno a sério e não fundo esbatido. Os fundos das .fx dão
   1.14:1 contra o --painel (mínimo 3:1) e só funcionam lá porque têm sempre
   texto por cima. A dificuldade 1 não existe nos 380 jogos (casa 2-4, fora
   2-5), por isso não há regra para ela nem entrada na legenda. */
.cal-jogo.d2 { color: var(--acento); background: color-mix(in srgb, var(--acento) 16%, transparent); }
.cal-jogo.d3 { color: var(--texto-2); background: var(--painel-2); }
.cal-jogo.d4 { color: var(--aviso); background: color-mix(in srgb, var(--aviso) 16%, transparent); }
.cal-jogo.d5 { color: var(--perigo); background: color-mix(in srgb, var(--perigo) 20%, transparent); }
/* Europa e taças: círculo contornado, sem preenchimento — não têm dificuldade
   para mostrar, e uma cor por competição colidia com o vocabulário do site
   (verde disponível, dourado a vigiar, coral fora). */
.cal-jogo.fora-pl { border-radius: 50%; background: transparent; color: var(--texto); }
.cal-troco {
  position: absolute; top: 0; bottom: 0; border-radius: 3px;
  background: color-mix(in srgb, var(--aviso) 10%, transparent);
}
.cal-troco.n4 { background: color-mix(in srgb, var(--aviso) 18%, transparent); }
.cal-troco.n5 { background: color-mix(in srgb, var(--perigo) 20%, transparent); }
```

- [ ] **Step 5: Abrir e confirmar que passa**

Abrir `site/testes.html`. Expected: "Tudo a passar" com as verificações novas.

- [ ] **Step 6: Verificar a geometria no browser, a 375px e a 1100px**

Run: `python scripts/servir.py 8010`. No separador Calendário, com o browser a 375px:

```js
document.body.scrollWidth <= document.documentElement.clientWidth
```
Expected: `true` (o `body` não ganha scroll horizontal).

- [ ] **Step 7: Commit**

```bash
git add site/app.js site/styles.css site/testes.html
git commit -m "Desenhar a linha do tempo, com a congestao por intensidade"
```

---

### Task 9: Colunas, ordenação, ecrã estreito e estados vazios

**Files:**
- Modify: `site/app.js`, `site/styles.css`, `site/index.html`
- Test: `site/testes.html`

**Interfaces:**
- Consumes: tudo da Task 8.
- Produces: `resumoClube(clube, jogos) -> {jogos, apertado, dificuldade, meus}`.

- [ ] **Step 1: Escrever os testes que falham**

```js
(function () {
  if (typeof resumoClube !== "function") return;
  // Medido: no horizonte longo, o número de jogos tem 3 valores distintos em
  // 20 clubes (empates de 9 e 10), e os dias apertados têm 7. Ordenar pela
  // contagem empatava metade da liga; é o "apertado" que separa.
  const a = resumoClube(1, [{ t: 1e12 }, { t: 1e12 + 2 * 864e5 }, { t: 1e12 + 4 * 864e5 }], {});
  const b = resumoClube(1, [{ t: 1e12 }, { t: 1e12 + 20 * 864e5 }, { t: 1e12 + 40 * 864e5 }], {});
  verificar("o mesmo número de jogos pode dar apertado diferente",
    a.jogos === b.jogos && a.apertado > b.apertado, [a, b]);
  verificar("a dificuldade média ignora os jogos sem dificuldade",
    resumoClube(1, [{ t: 1e12, dif: 4 }, { t: 1e12, dif: null }], {}).dificuldade === 4);
  verificar("clube sem jogos no horizonte não dá NaN",
    resumoClube(1, [], {}).dificuldade === null);
  verificar("conta os meus jogadores desse clube",
    resumoClube(7, [], { 7: 3 }).meus === 3);
})();
```

- [ ] **Step 2: Abrir e confirmar que falha**

Abrir `site/testes.html`. Expected: as verificações novas falham.

- [ ] **Step 3: Implementar as colunas e a ordenação**

Duas colunas fixas ao lado do nome do clube, ambas ordenáveis:

| coluna | o que é | serve |
|---|---|---|
| **Apertado** | dias dentro de um troço de 3 jogos em 8 dias | congestão |
| **Dificuldade** | média dos adversários da PL, com o nº de jogos | percurso |

Substituem as duas frases da versão anterior da especificação, que **podiam contradizer o gráfico por cima delas** (o Brighton seria anunciado como "percurso mais duro" com média 3.5 enquanto a coluna Calend. lhe dá **+2%**, o melhor bónus da liga) e discordar uma da outra (a 21/11 o texto diria "nenhum clube joga a meio da semana" com 9 das 20 linhas sombreadas três dias depois).

A coluna Dificuldade leva a escala ("3.1 em 5, 1 fácil") e, como o `amplitudeCalendario()` já faz (app.js:982), uma linha por baixo com a amplitude real, a dizer que serve para afinar entre clubes parecidos e não para inverter diferenças grandes.

Em vez de ★ — que com `owner != null` marcaria **18 de 20 clubes** no Draft e 11 de 20 bem feito —, mostra-se o **número de jogadores meus por clube**, que também ordena.

**Por omissão mostram-se só os meus clubes**, com um interruptor para os 20. Dos 20, só 9 jogam na Europa; dos meus 11 de hoje, **6 não jogam** e a linha deles é uma fila de marcadores semanais sempre igual — ruído para a decisão 1 e redundante para a 2, que cabe na coluna. O projeto já filtra assim em Conferências, Próximos jogos e Utilização.

```js
/** Quantos jogadores meus tem cada clube. Só do meu plantel, não de todos. */
function meusPorClube() {
  // O padrão do resto do ficheiro (app.js:1065, 1585, 3176): a minha equipa
  // descobre-se pelo apelido do gestor no Draft, e pelo `equipa.id` na
  // clássica. `owner != null` sozinho daria 18 dos 20 clubes.
  const eu = ehClassica()
    ? ((minhaEquipaClassica() || {}).id)
    : ((D.entries.find((e) => MEU_GESTOR.test(e.manager)) || {}).entry_id);
  const conta = {};
  D.players.forEach((p) => {
    if (eu != null && p.owner === eu) {
      conta[p.team] = (conta[p.team] || 0) + 1;
    }
  });
  return conta;
}

/** Os números por que se ordena. Ambos ficam à vista, ao lado do clube. */
function resumoClube(teamId, jogos, meus) {
  const trocos = trocosApertados(jogos);
  // Dias dentro de troço apertado — mede a congestão melhor do que a contagem
  // de jogos, que no horizonte longo tem 3 valores distintos em 20 clubes.
  const apertado = trocos.reduce(
    (t, tr) => t + Math.round((tr.fim - tr.inicio) / 864e5) + 1, 0);
  const comDif = jogos.filter((j) => typeof j.dif === "number");
  return {
    jogos: jogos.length,
    apertado: apertado,
    // Só os jogos da PL têm dificuldade; a Europa não tem nenhuma para dar.
    dificuldade: comDif.length
      ? comDif.reduce((t, j) => t + j.dif, 0) / comDif.length : null,
    nJogosDif: comDif.length,
    meus: (meus || {})[teamId] || 0,
  };
}
```

- [ ] **Step 4: Horizonte em jornadas, não em semanas**

Seletor **6 jornadas / 12 jornadas / resto da época**, guardado em `localStorage` como `calHorizonte`. Medido: com uma paragem de 20 dias entre 20/09 e 10/10, uma janela de 4 semanas tem **2 jogos da PL por clube**; medir em semanas dá um número de jogos que varia enormemente com a altura do ano. O rótulo diz **"Horizonte"** e não "Janela", para não colidir com o seletor das Sugestões.

- [ ] **Step 5: Lista em ecrã estreito**

Abaixo de 40rem, mostrar a lista por clube em vez da linha do tempo — é o padrão que o projeto já usa (`.col-noticia` na tabela de transferências) e o CLAUDE.md regista que o scroll horizontal foi medido e recusado ("438 contra 375").

- [ ] **Step 6: Estados vazios, cada um com a sua frase**

- **Ronda por sortear**: onde há ronda marcada e não sorteada e o clube ainda está na prova, marca **"por sortear"** com a data do sorteio. Sem isto o separador afirma "não joga" quando o que sabe é "não sei" — e a partir de 18/09 mostraria "taça = 0" para os 20 clubes numa prova onde 16 continuam vivos.
- **Clube recusado na validação**: linha marcada **"sem dados"** com o motivo, nunca linha vazia — uma linha em branco lê-se como "clube tranquilo".
- **Paragem para selecções**: frase a dizê-lo, senão o vazio parece avaria.
- **Horas provisórias**: para lá de ~6 semanas, dizer que as horas ainda não estão confirmadas (novembro tem 30 dos 32 jogos às 15:00, abril tem os 30 às 14:00, e não há bandeira na API que o distinga).
- **Clássica sem `FPL_ENTRY_ID`**: ninguém tem `owner`; cai nos 20 clubes em vez de lista vazia.
- **Legenda construída a partir do que está no horizonte**, senão mostra cores sem marcador.

- [ ] **Step 7: Redesenhar quando o plantel manual muda**

Chamar o desenho do calendário a partir de `desenharClassica()` e não só do `main()`: `aplicarPlantelManual()` (app.js:2073) reescreve o `owner` em memória, e senão a contagem de jogadores meus por clube ficava com o plantel da jornada passada — a armadilha já documentada no CLAUDE.md para o `initClassica()`.

- [ ] **Step 8: Correr tudo e verificar no browser**

Run: `python scripts/testes.py` → "Tudo a passar."
Abrir `site/testes.html` → "Tudo a passar".
No dashboard, nos **dois modos**: alternar o horizonte e confirmar que a ordem muda; ordenar por Apertado e por Dificuldade; a 375px confirmar a lista e `document.body.scrollWidth <= document.documentElement.clientWidth`; consola sem erros.

- [ ] **Step 9: Confirmar que o modelo não mexeu**

```bash
python -c "
import json,io
d=json.load(io.open('site/data/data.json',encoding='utf-8'))
print('fixtures por clube (esperado 10):', {k:len(v) for k,v in list(d['fixtures'].items())[:3]})
"
```
E no browser, comparar o `ppj` de 3 jogadores antes e depois deste plano: **têm de ser iguais**.

- [ ] **Step 10: Commit**

```bash
git add site/app.js site/styles.css site/index.html site/testes.html
git commit -m "Colunas por que se ordena, lista em ecra estreito e estados vazios"
```

---

### Task 10: Documentar no CLAUDE.md, incluindo a correcção de facto

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Corrigir a linha errada sobre a Liga Europa**

Na secção "zerozero.pt: mapeado e validado, **por ligar**", a frase *"Não aparece Europa League em clube nenhum, o que é invulgar e não consegui confirmar"* e a contagem *"Seis dos vinte"* estão erradas. São **nove** clubes, a Liga Europa tem três (Bournemouth, Sunderland, Crystal Palace) e o Brighton está na **fase de liga** da Conference, não só na qualificação. A nota antiga veio de se ter lido os distintivos da página do clube, que listavam "PE" (pré-época). Se ficasse, a próxima revisão partia dela.

- [ ] **Step 2: Escrever a secção nova**

Uma secção "## Separador Calendário (2026-09-07)" com: as duas decisões que serve; a ordem decrescente da tabela e porque é que a página 2 é a que importa; o fuso medido em vez de assumido; a junção por slug e os 6 nomes que não batem; a época lida da página; a validação por linha; e porque é que **não liga ao modelo**.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Documentar o separador Calendario e corrigir o facto errado sobre a Liga Europa"
```

---

## Verificação final

1. `python scripts/testes.py` — tudo a passar.
2. `site/testes.html` no browser — tudo a passar.
3. `python scripts/fetch_data.py`, `python scripts/fetch_classica.py`, `python scripts/fetch_calendario.py` — as três sem erro, e `git status` só com os três JSON.
4. Os dois modos, consola sem erros, a 375px e a 1100px.
5. `python scripts/artefacto.py` — sai sem erro, e o separador Calendário funciona no ficheiro único.
6. O `ppj` de 3 jogadores igual ao de antes deste plano.
