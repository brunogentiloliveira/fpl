# FPL Draft Dashboard

Dashboard pessoal para acompanhar uma liga privada de FPL Draft
(draft.premierleague.com). Corre **100% localmente**: um script Python vai
buscar os dados à API pública do FPL Draft e o site estático é servido na
tua máquina. Nada é publicado online.

## Requisitos

- Python 3 (em Windows: `winget install Python.Python.3.12`)

## Usar

**Windows:** duplo clique em `atualizar.cmd` — atualiza os dados, arranca o
servidor e abre o browser em <http://localhost:8000>. Fecha a janela preta
para desligar.

**Manual (qualquer sistema):**

```bash
LEAGUE_ID=12258 python scripts/fetch_data.py
python -m http.server 8000 --directory site
```

e abre <http://localhost:8000>.

## Estrutura

- `atualizar.cmd` — atalho Windows: recolha + servidor + browser
- `scripts/fetch_data.py` — recolha (só stdlib; `LEAGUE_ID` por variável de ambiente)
- `site/` — frontend estático (HTML/CSS/JS puro, pt-PT, mobile-first)
- `site/data/data.json` — dados gerados pela recolha
- `CLAUDE.md` — especificação, notas da API e fases seguintes
