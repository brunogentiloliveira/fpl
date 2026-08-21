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
- **Sugestões da jornada (feito 2026-08-21, pedido do utilizador)**: o separador passou a
  chamar-se "Sugestões" (ids `tab-sug`/`painel-sug`) com as recomendações no topo e as
  projeções por baixo como fundamentação. Tudo calculado no cliente, sem dados novos da API.
  - **Onze inicial** (`melhorXI`): 1 GR, 3-5 DEF, 2-5 MED, 1-3 AV. Guloso — mínimos por posição
    primeiro, depois as 4 vagas restantes pelos melhores que ainda cabem. `valorXI` = soma
    dos pts/jornada do onze; é a métrica que avalia cada movimento (o banco vale 0 à margem).
    Mostrado como "campo" (`desenharOnze`, secção `#xi-campo`) com formação, total e suplentes.
  - **Justificações** (`porqueSai`/`porqueEntra`/`calendario`): cada sugestão traz uma frase
    em português corrente com o motivo real (lesão, minutos esperados, pts/90, valor da
    transferência, dificuldade dos próximos adversários) em vez de só o número do ganho.
  - **Waivers**: para cada posição, compara os meus com os livres não-lesionados; sugere se
    ganhar ≥0.4 pts/jornada, emparelhamento guloso (cada jogador entra/sai uma vez). Se o meu
    jogador recuperado projetar mais do que o livre, mostra aviso para não trocar um titular
    por causa de uma lesão curta (`ppjSaudavel`).
  - **Trocas**: só 1-por-1 **da mesma posição** (o plantel tem de manter 2/5/5/3 — uma versão
    anterior sugeriu GR por AV). Nota importante: com uma valorização comum aos dois lados,
    uma troca destas é **soma zero**, por isso "ambos ganham no onze" quase nunca dispara.
    O critério que faz trocas acontecer é o do "cartaz": eu ganho na projeção e o outro recebe
    o jogador com mais pontos na época passada (o que um gestor olha primeiro). Os dois números
    aparecem na sugestão para a decisão ser informada.
  - **Contexto da liga**: lugar, pontos e diferença para o líder (quando houver classificação),
    posição na fila de waivers (`waiver_pick`) e nº de movimentos recentes na liga.
- **Utilização real por jornada (feito 2026-08-21, pedido do utilizador)**: quem jogou, quantos
  minutos e quantos pontos — e o efeito disso nas projeções e sugestões.
  - **Fonte**: o utilizador pediu SofaScore/FlashScore. **Não usar**: o SofaScore devolve 403 a
    pedidos automáticos (até no robots.txt) e os termos do FlashScore proíbem extração de dados.
    A mesma informação está na API que já usamos: `GET /event/{ev}/live` dá minutos e pontos por
    jogador em cada jornada (`elements`) e as fixtures dessa jornada.
  - `fetch_jornadas()`: percorre 1..current_event; jornadas já `finalizada` ficam em cache no
    próprio data.json e não são repedidas. Guarda `{finalizada, equipas, stats:{id:[min,pts]}}`;
    quem não jogou não aparece (ausente = 0 minutos) para o ficheiro não crescer. O parser aceita
    `elements` como objeto (Draft) ou lista (FPL clássico) — testado com payloads sintéticos,
    porque a época só arranca a 2026-08-21 às 19:00 UTC.
  - `snapshot_historico()`: congela minutes/starts/total_points da época passada **antes** de o
    bootstrap-static passar a refletir a nova época; fica em `data.json → historico` e nunca é
    recalculado depois da primeira vez. Sem isto, as projeções perderiam a base logo na GW1.
  - **Projeção v2** (app.js): `pp90` = pontos desta época encolhidos para o pp90 histórico (que
    por sua vez já está encolhido para o prior de rank/posição); `xmin` = média dos minutos reais
    das últimas 3 jornadas com peso `min(1, jogos/5)` contra a estimativa histórica — ao 5.º jogo
    a realidade decide sozinha. O piso da transferência cara só se aplica **antes do 3.º jogo**
    (depois disso vale o que se viu em campo). `naoUsado` marca quem tem 0 minutos nos últimos
    jogos estando disponível.
  - `riscoRotacao` passou a usar os minutos reais quando há ≥2 jornadas; só recorre às
    titularidades da época passada antes disso.
- **Pré-época (feito 2026-08-21, pedido do utilizador)**: onzes do último ensaio de cada clube,
  para a GW1 não depender só da época passada.
  - **Fontes avaliadas**: a API do FPL não tem pré-época. O TheSportsDB (chave gratuita "3")
    tem os jogos e resultados, mas **não tem constituição das equipas nos amigáveis** — só em
    jogos oficiais (confirmado em 8 clubes); além disso limita a 30 pedidos/min e não conhece
    o Nott'm Forest. Scraping do Google está fora (os termos proíbem pedidos automáticos e o
    robots.txt bloqueia /search), tal como SofaScore (403) e FlashScore (termos).
  - **Solução**: como a pré-época **já terminou, os dados são estáticos**. Ficam em
    `scripts/preepoca.json`, recolhidos à mão de relatos públicos, com a fonte de cada jogo.
    16 dos 20 clubes têm onze fiável; Bournemouth, Hull, Ipswich e Sunderland ficam de fora
    de propósito (relatos contraditórios ou inexistentes) — melhor sem sinal do que com um errado.
    `fetch_preepoca()` casa os nomes com o plantel do clube (`casar_nome`, por interseção de
    tokens; empates ficam por resolver) e escreve ids em `data.json → preepoca`.
  - **Modelo**: só conta enquanto `jogosObs === 0`. Titular puxa os minutos esperados para 72;
    suplente/não convocado puxa para 30; "não foi titular" (sem lista de suplentes publicada)
    é só −15%, e não se aplica a quem tem transferência confirmada (mudou de clube, o onze do
    clube antigo não diz nada). Confiança "media" vale metade.
  - **Efeito real**: Ødegaard 1.9 → 3.9 pts/jornada (titular na Supertaça, depois de uma época
    passada com poucas titularidades) e Araujo 3.0 → 2.2 (ficou no banco no Liverpool).
  - `sem_acentos` passou a traduzir letras que o NFD não decompõe (ø, đ, ł, ß, æ…), senão
    "Ødegaard" nunca casaria com "Odegaard".
