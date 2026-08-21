# FPL Draft Dashboard — "Haaland of Fame"

Dashboard estático para acompanhar uma liga privada de FPL Draft (draft.premierleague.com),
inspirado no "Draft Room". **Corre 100% localmente** (decisão de 2026-08-21: o utilizador quer
o projeto só para si — sem GitHub Pages nem Actions; o repo no GitHub é só backup).
Sem backend nem base de dados: JSONs estáticos gerados por um script Python.

## Factos da liga (confirmados na API em 2026-08-21)

- ID da liga: **12258** — nome: "Haaland of Fame", época 2026/27.
- 7 gestores. `scoring: "c"` (**classic**, não head-to-head), `transaction_mode: "free-agency"`.
- A equipa do utilizador é **"Buendia Porro"** (gestor Bruno **Gentil**, `league_entry id 61532`,
  `entry_id 61414`). Nota: "Gentil" é o apelido do gestor, não o nome da equipa.
- Idioma do site: português de Portugal. Fuso: Europe/Lisbon. Mobile-first (uso sobretudo no telemóvel).

## API (pública, sem autenticação) — campos reais confirmados

Base: `https://draft.premierleague.com/api`

- `GET /bootstrap-static`
  - `elements[]`: id, web_name, first_name, second_name, team (id do clube), element_type
    (1 GR, 2 DEF, 3 MED, 4 AV), draft_rank, total_points, status (a/d/i/s/u/n), news,
    news_added, chance_of_playing_next_round, form, points_per_game, …
  - `teams[]`: id, name, short_name, code, pulse_id
  - `element_types[]`: id, singular_name_short, plural_name, …
  - `events`: `{ current, data: [{ id, name, deadline_time, waivers_time, trades_time, finished, … }] }`
    → **os deadlines estão AQUI, não em /api/game**. Horas em UTC (ISO 8601 com Z).
- `GET /game`: current_event (null antes da época), current_event_finished, next_event,
  processing_status, waivers_processed, trades_time_for_approval. **Sem datas.**
- `GET /league/{id}/details`: `league` (name, scoring, transaction_mode, draft_dt, …),
  `league_entries[]` (id [= league_entry usado nos standings], entry_id [usado no owner
  do element-status], 
  entry_name, player_first_name, player_last_name, short_name, waiver_pick),
  `standings[]` (league_entry, rank, last_rank, total, event_total) — rank/total são null antes da GW1.
- `GET /league/{id}/element-status`: `element_status[]` (element, owner [**entry_id** de league_entries
  ou null se livre], status, in_accepted_trade).

## Arquitetura

- `scripts/fetch_data.py` — Python só com stdlib; `LEAGUE_ID` vem de variável de ambiente;
  junta tudo num único `site/data/data.json` (jogadores já com `owner` embutido).
- `atualizar.cmd` — atalho Windows: corre a recolha (LEAGUE_ID=12258), arranca
  `python -m http.server 8000 --directory site` e abre o browser. É assim que o site se usa.
- `site/` — HTML/CSS/JS puro, sem frameworks nem build step. Tema escuro, focus visível,
  `prefers-reduced-motion` respeitado (ticker sem animação).
- Já **não há** workflow do GitHub Actions (removido quando o projeto passou a só-local);
  se voltar a ser preciso, está no histórico do git (commit da Fase 1).

## Ambiente da máquina

Windows 11, sem Docker ativo nem WSL. Python 3.12 instalado via winget em 2026-08-21
(`%LocalAppData%\Programs\Python\Python312\`, com `py` launcher) — atenção: shells abertas
antes da instalação não o têm no PATH; usar o caminho absoluto ou o `atualizar.cmd`,
que já tem fallback.

## Estado das fases

- **Fase 1 (feita)**: recolha + página única com cabeçalho (última atualização +
  contagem para o deadline), ticker de notícias, separadores Liga / Boletim / Jogadores
  (pesquisa, filtro por posição, "só livres", ordenado por draft_rank).
- **Fase 2 (por fazer)**: separador "A minha equipa" — detetar a equipa do Bruno Gentil
  ("Buendia Porro"), plantel de 15 por posição com estado clínico; bloco "Alvos de waiver"
  (10 livres com melhor draft_rank por posição, escondendo status fora); realçar a vermelho
  jogadores meus que entraram no boletim desde a última atualização.
- **Fase 3 (por fazer)**: separador "Equipas" — cartão por gestor (15 por posição, contagem de
  lesionados). A liga é classic, não h2h, portanto sem confrontos; explorar `/api/league/{ID}/`
  para resultados por jornada antes de implementar.
- **Fase 4 (opcional, por fazer)**: transferências confirmadas e rumores via RSS — avaliar
  primeiro 2-3 fontes públicas com prós/contras e propor ao utilizador antes de implementar.
  Sem scraping de sites que o proíbam.
