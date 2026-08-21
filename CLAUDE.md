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
- `GET /element-summary/{element_id}`: `fixtures[]` (event, opponent, is_home, **difficulty** 1-5)
  e `history[]` (por jornada, vazio antes da época). **Não tem** épocas anteriores. As fixtures
  são do clube do jogador, por isso basta 1 jogador por equipa (20 pedidos) para ter tudo;
  o `fixtures` do bootstrap-static só traz 3 jornadas e **sem** dificuldade.
- Explorados em 2026-08-21 (pré-época): `GET /entry/{entry_id}/public` (entry com event_points/
  overall_points, null antes da GW1); `GET /entry/{entry_id}/history` (**resultados por jornada**,
  `history: []` antes da época); `GET /entry/{entry_id}/event/{ev}` (404 "No pick history" antes
  da GW1 — escolhas por jornada); `GET /event/{ev}/live` (stats ao vivo por jogador + fixtures);
  `GET /draft/league/{id}/transactions` (waivers/free agency da liga: element_in/out, entry,
  event, kind, result). **Não existem** `/league/{id}/` (raiz), `/league/{id}/standings`
  nem `/league/{id}/trades`.

## Feeds RSS do Sky Sports (ids confirmados por sondagem em 2026-08-21)

`https://www.skysports.com/rss/{id}` — 12691 Transfer Centre; por clube: Man Utd 11667,
Chelsea 11668, Liverpool 11669, Arsenal 11670, Everton 11671, Spurs 11675, Aston Villa 11677,
Newcastle 11678, Man City 11679, Fulham 11681, Sunderland 11695, Crystal Palace 11706,
Ipswich 11707, Coventry 11710, Hull 11714, Leeds 11715, Nott'm Forest 11727, Brighton 11741,
Bournemouth 11743, Brentford 11748 (mapa completo em `SKY_CLUBES`, chaveado pelo `name` do
bootstrap). Itens: title, description, link, pubDate (BST/GMT), category. Alternativa avaliada:
feeds por clube da BBC (`feeds.bbci.co.uk/sport/football/teams/{slug}/rss.xml`) — funcionam mas
com slugs irregulares (`afc-bournemouth`, `manchester-united`) e menos citações de treinador.

## Arquitetura

- `scripts/fetch_data.py` — Python só com stdlib; `LEAGUE_ID` vem de variável de ambiente;
  junta tudo num único `site/data/data.json` (jogadores já com `owner` embutido).
- `atualizar.cmd` — atalho Windows: corre a recolha (LEAGUE_ID=12258), arranca
  `scripts/servir.py` (servidor com `Cache-Control: no-cache` — o http.server puro deixava
  o browser preso a versões antigas do site) e abre o browser. É assim que o site se usa.
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
- **Fase 2 (feita)**: separador "Equipa" (aria-label "A minha equipa") — plantel de 15 por
  posição com estado clínico e alerta; "Alvos de waiver" (10 livres com melhor draft_rank
  por posição, sem status fora); realce a vermelho de jogadores meus novos no boletim.
  A deteção de novidades compara com o data.json anterior no fetch_data.py (`news_new`;
  primeira execução nunca marca nada). A equipa é detetada pelo apelido do gestor
  (regex /gentil/i em app.js), com fallback para o nome "Buendia Porro".
- **Fase 3 (feita)**: separador "Equipas" — cartão `<details>` por gestor, ordenado por rank
  (fallback waiver_pick antes da época): plantel de 15 por posição, contagem "N fora" /
  "N dúvidas" / "plantel completo", equipa do utilizador com ★ e aberta por omissão.
  Sem confrontos (liga classic). `waiver_pick` acrescentado às entries do data.json.
  Quando a época arrancar, `/entry/{id}/history` dá resultados por jornada (ver secção API)
  se se quiser enriquecer os cartões.
- **Fase 4 (feita)**: separador "Mercado" com duas secções. (1) "Movimentos da liga":
  waivers/free agency dos 7 gestores via `/draft/league/{id}/transactions` (40 mais recentes,
  aceites vs recusados, nomes resolvidos). (2) "Notícias de transferências": RSS do Sky Sports
  Transfer Centre (`skysports.com/rss/12691`), escolhido pelo utilizador em 2026-08-21 entre
  Sky/Guardian/BBC; lido no fetch_data.py (stdlib ET, falha tolerada sem partir a recolha),
  itens "Papers"/"rumour" etiquetados como rumor. Tudo em `data.json → mercado`.
- **Separador "Conferências" (feito 2026-08-21, pedido do utilizador)**: antevisões de imprensa
  dos clubes onde tenho jogadores + lista de jogadores meus em risco de não jogar/não ser titular.
  - Recolha: `fetch_conferencias()` lê o feed Sky de cada clube do meu plantel (equipa detetada
    pelo apelido, env `MEU_GESTOR`, default "Gentil"), filtra ruído promocional (`CONF_RUIDO`),
    marca `conferencia` por palavras-chave (`CONF_PADROES`) e cruza os nomes dos **meus jogadores
    desse clube** (sem acentos, `\b`) → `mencoes`. Cruzar só com o clube evita falsos positivos
    de apelidos comuns. Falhas de feed são toleradas. Sai em `data.json → conferencias`.
  - Risco (calculado no app.js, `riscoJogador`): nível 3 fora (status i/s/u/n), 2 dúvida ou
    rotação forte, 1 a vigiar. Rotação usa `minutes`/`starts` (novos em PLAYER_FIELDS):
    antes da época compara com 38 jornadas (≤12 titularidades = risco alto, ≤21 = vigiar);
    com época a decorrer usa `starts/current_event` (<0.4 alto, <0.7 vigiar) e só a partir da
    GW3. Se o jogador já não joga, a linha de rotação é omitida.
- **Separador "Projeções" (feito 2026-08-21, pedido do utilizador)**: pontos estimados por
  jornada para qualquer jogador, com o meu plantel e os melhores livres; a tabela de Jogadores
  ganhou coluna "Pts/J" e ordenação (rank / projeção / pontos).
  - Modelo (em app.js, `projecao`, propositadamente transparente e afinável):
    `pp90` = pontos por 90 da época passada **com encolhimento** para o prior (mediana dos
    K=15 jogadores de draft rank vizinho na mesma posição, `MIN_PRIOR=900` minutos de peso) —
    evita valores absurdos de quem jogou pouco e dá estimativa a quem tem 0 minutos na PL.
    `xmin` = minutos/38 da época passada (ou o prior, se estreante), com **piso por transferência
    cara confirmada** (≥50M→75, ≥30M→68, ≥15M→58, senão 50), 0 se fora e ×chance se dúvida.
    `ppj` = pp90 × xmin/90; "Próx. 3" soma 3 jornadas com fator de dificuldade
    `1 + (3-dif)×0.06`. Ex. real: Savinho passou de 1.1 para 3.8 pts/jornada com os £85M.
  - Transferências: `extrair_transferencias()` lê valores (`£/€/$ Xm`) nos feeds Sky de **todos**
    os clubes + Transfer Centre. Classificação pelo **título** (o resumo mistura negociações):
    `RE_FECHADO` sem `RE_ABERTO` = confirmada, caso contrário rumor (sem efeito na projeção).
    Correspondência de nomes com precedência: `web_name` primeiro, apelidos soltos do
    `second_name` só se ninguém bater pelo principal — apelidos compostos ("Martínez Romero")
    davam falsos positivos. Saídas da PL ficam com status "u" e projeção 0, portanto não
    beneficiam do piso.
