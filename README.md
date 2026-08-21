# FPL Draft Dashboard

Dashboard estático para acompanhar uma liga privada de FPL Draft
(draft.premierleague.com), servido pelo GitHub Pages e atualizado
automaticamente pelo GitHub Actions. Sem backend: um script Python gera
JSONs estáticos a partir da API pública do FPL Draft.

## Configuração (uma vez)

1. **Variável `LEAGUE_ID`** — em *Settings → Secrets and variables → Actions →
   Variables → New repository variable*, cria `LEAGUE_ID` com o número da tua
   liga (o número no URL de draft.premierleague.com, ex.: `12258`).
2. **GitHub Pages** — em *Settings → Pages → Build and deployment → Source*,
   escolhe **GitHub Actions**.
3. Corre o workflow uma vez à mão: *Actions → "Atualizar dados e publicar" →
   Run workflow*. A partir daí corre sozinho (diário de manhã + quinta e sexta
   ao fim da tarde, hora de Lisboa).

## Testar localmente

Com Python instalado:

```bash
LEAGUE_ID=12258 python scripts/fetch_data.py
python -m http.server 8000 --directory site
```

Sem Python mas com Docker (ex.: Windows):

```bash
docker run --rm -v "$PWD:/app" -w /app -e LEAGUE_ID=12258 python:3.12-slim python scripts/fetch_data.py
docker run --rm -v "$PWD/site:/site" -p 8000:8000 python:3.12-slim python -m http.server 8000 --directory /site
```

Depois abre <http://localhost:8000>.

## Estrutura

- `scripts/fetch_data.py` — recolha (só stdlib; `LEAGUE_ID` por variável de ambiente)
- `site/` — frontend estático (HTML/CSS/JS puro, pt-PT, mobile-first)
- `site/data/data.json` — dados gerados (commitados pelo bot)
- `.github/workflows/update.yml` — cron + deploy para Pages
- `CLAUDE.md` — especificação, notas da API e fases seguintes
