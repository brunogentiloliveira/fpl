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

## Fantasy Football Scout (fonte acrescentada em 2026-08-21, sugerida pelo utilizador)

`https://www.fantasyfootballscout.co.uk/feed/` — RSS (12 itens) de um site especializado em
fantasy da PL. O `robots.txt` permite tudo (`Disallow:` vazio) e o artigo de team news da
jornada está fora do members area. **Porque é que vale a pena**: apanha as conferências de
imprensa antes de a API oficial mudar o `status` (ex.: em 2026-08-21 dava o Pedro Porro fora
da GW1 enquanto a API ainda o tinha como disponível).

- `fetch_ffs()` lê o feed, escolhe o item cujo título tem "team news", vai à página e parseia
  o resumo em lista dentro de `<section class="entry-content">`: cada `<li>` tem
  `<strong>Clube</strong>: notas`. O clube dá o contexto para cruzar nomes **só com o plantel
  desse clube** (é o que evita falsos positivos).
- Estado por proximidade: cada nome fica com a palavra-chave que aparece **a seguir** a ele
  ("Porro + van de Ven out, Solanke + Maddison fit" → 2 fora, 2 aptos). Sem palavra-chave a
  seguir, não classifica — adivinhar pelo texto anterior dava erros.
- Dois travões aprendidos com falsos positivos reais: `FFS_NEGACAO` anula palavras-chave
  precedidas de "no/not/without" ("No injury updates, Iraola on Isak + Gakpo" marcava Isak e
  Gakpo como fora), e nomes de dois jogadores do mesmo clube na mesma posição do texto só
  contam se um deles bater pelo `web_name` (o "Nunes" apanhava o Vitor Reis).
- Só o estado "fora" mexe no modelo (`xmin = 0`, como se estivesse lesionado); "dúvida" e
  "apto" são informativos. O separador Conferências mostra a frase original e avisa quando a
  API ainda diverge. Os onzes prováveis por jogo do FFS são **imagens**, por isso não dá para
  extrair a equipa provável — só o texto de team news.

## Boletim (ordenação, 2026-08-21)

Ordenado por **quem exige ação**, não por data (o ticker do topo é que ficou cronológico):

1. Grupo por dono — `pesoDono`: meus → de outros gestores → livres, com separador
   `<li class="grupo">` e contagem.
2. Gravidade dentro do grupo — `pesoGravidade`: **-1** dado como fora pelo Scout (é a
   informação mais recente e não aparece em mais lado nenhum), 0 fora pela API, 1 dúvida,
   2 saída do clube, 3 resto. Data decrescente desempata.

A saída do clube distingue-se pelo **texto** da notícia (`FRASES_SAIDA`), não pelo status: a
API usa `u`/`n` tanto para quem saiu como para outros indisponíveis. Nota: escrever este
teste como regex com fronteira de palavra através de heredoc do shell corrompeu o ficheiro
(a sequência barra-b virou um caracter backspace literal, e nada casava) — daí a verificação
por `includes`, que também lê melhor.

`noticiasBoletim()` junta as notícias da API com os jogadores que **só o Scout** dá como fora
(`soNoScout`); esses aparecem com distintivo "Fora (Scout)", a data do artigo e a frase
original. Quem tem as duas coisas mostra ambas.

## Pontos esperados a partir das estatísticas subjacentes (2026-08-21)

A pedido do utilizador, o modelo deixou de olhar só para os minutos e para a taxa de pontos
realizada: passa a estimar o que o jogador **gera**.

- `componentesPP90()` calcula, por 90 minutos: presença (2), **xG × 6/6/5/4** conforme a
  posição, **xA × 3**, baliza a zero por Poisson (`exp(-xGC90)` × 4/4/1/0), defesas dos GR
  (÷3), bónus e cartões. `taxaBase()` mistura isto meio a meio com os pontos realmente feitos
  (`PESO_ESPERADO = 0.5`): o xG/xA prevê melhor, os pontos reais apanham o que falta ao modelo.
- **Penáltis, livres e cantos**: os campos de cargo (`penalties_order`, `direct_freekicks_order`,
  `corners_and_indirect_freekicks_order`) vêm **vazios para os 600 jogadores** nesta API — tal
  como `defensive_contribution`, `tackles`, `recoveries` e `clearances_blocks_interceptions`.
  Não há como dar bónus explícito a quem tem o cargo. Mas o valor que geram **já está no xG e
  no xA** (um penálti vale ~0.79 de xG; cantos e livres alimentam o xA de quem os bate).
- `calibrarEsperado()`: como o modelo não tem tudo (defensivas a zero), ficava ~14% abaixo da
  média realizada. O fator `calibEsperado` (≈1.15) alinha os níveis sem mexer na ordenação —
  o desvio médio contra o modelo anterior passou de −0.18 para +0.01 pts/90.
- O `historico` no data.json passou a guardar `HIST_FIELDS` (xG, xA, xGC, defesas, bónus,
  cartões, autogolos…) e é **refeito enquanto `current_event` for null**, para apanhar campos
  novos enquanto o bootstrap ainda traz a época passada.
- A coluna Pts/90 tem `title` com a decomposição (presença · golos · assistências · baliza a
  zero · defesas · bónus · cartões), para o número não ser uma caixa preta.

## Pontuação vinda da liga (2026-08-21)

`bootstrap-static → settings` traz a **tabela de pontuação e as regras de plantel da liga**, que
antes estavam escritas à mão no app.js — e com erros. Guardada em `data.json → regras` e lida por
`regra()`/`regraPos()`/`limitesXI()`. Duas correções de facto que isto trouxe:

- **Golo de guarda-redes vale 10**, não 6.
- **Golos sofridos custam −1 por cada 2** a GR e DEF (`concede_limit: 2`), algo que o modelo
  ignorava: premiava a baliza a zero e nunca castigava o reverso, inflacionando defesas de
  equipas fracas. `castigoGolosSofridos()` usa a forma fechada da média de ⌊X/2⌋ numa Poisson:
  `(λ − (1 − e^(−2λ))/2) / 2`. Efeito real: Gabriel (Arsenal) −0.20 pts/90, Milenković
  (Forest) −0.60.
- Também entram penáltis defendidos (×5) e os limites do onze deixam de estar fixos.
- `calibEsperado` subiu de 1.15 para ~1.21 (o modelo esperado ficou mais baixo por causa do
  novo castigo); continua a alinhar o nível sem mexer na ordenação.

## Precisão do modelo (2026-08-21)

O site é estático e o modelo vive no JS, por isso **é o browser que guarda o que projetou**:
`guardarProjecoes()` grava em `localStorage` (`proj:<liga>:<jornada>`) o ppj de cada jogador com
dono, uma só vez por jornada e só enquanto ela não estiver jogada. Quando a jornada fecha,
`avaliarPrecisao()` compara com os pontos reais de `data.json → jornadas` e a secção "Precisão do
modelo" mostra erro médio absoluto, viés (positivo = o modelo ficou aquém) e os maiores desvios.
Limitação assumida: o histórico é por browser; se mudares de dispositivo, começa do zero.

## Diagnóstico das fontes (2026-08-21)

`registar(fonte, ok, detalhe)` acumula `data.json → diagnostico` — antes os avisos só iam para
stderr e desapareciam. O rodapé lista cada fonte com ✓/✗ e o detalhe em tooltip. Há ainda um
banner no topo quando os dados estão velhos: recolha anterior a um deadline **já passado**, ou
com mais de 12 horas.

## Telemóvel (2026-08-21)

`servir.py` já servia em todas as interfaces, mas o endereço não era visível: passa a imprimir
`http://<ip-da-rede-local>:porta` (IP obtido por um socket UDP que não envia nada) além do
localhost. Há `manifest.webmanifest` + `icone.svg` + `theme-color` para "adicionar ao ecrã
principal". **Não há service worker**: exigem contexto seguro (HTTPS ou localhost) e no telemóvel
o acesso é por IP em HTTP simples, onde nunca registariam — foi tentado, falhava, e ficou de fora
em vez de código morto. Consequência: o PC tem de estar com o `atualizar.cmd` a correr.

## Testes (2026-08-21)

- `python scripts/testes.py` — stdlib, sem rede: correspondência de nomes (Ø, apelidos
  compostos, nome próprio), parsing do Scout com os casos que já falharam a sério (negação
  "No injury updates", "Nunes" ambíguo), os formatos de `/event/{ev}/live` e a validade dos
  ficheiros curados.
- `site/testes.html` — abre no browser e verifica o modelo com um `D` sintético: legalidade do
  onze, ausências a zerar (API e Scout), `ppjSaudavel` a ignorá-las, a tabela de pontuação, o
  castigo por golos sofridos e a bola parada a pesar menos para quem tem historial. 22
  verificações. Exigiu o guarda `window.__TESTES__` antes do `main()` no app.js.

## Bola parada (batedores, 2026-08-21)

Os campos da API (`penalties_order`, `direct_freekicks_order`, cantos) vêm vazios para os 600
jogadores, por isso os cargos ficam em `scripts/bolaparada.json`, recolhidos à mão da tabela
do **Fantasy Football Scout** (que a mantém durante a época) e **cruzados com a RotoWire** em
9 clubes. As duas fontes divergiam no Arsenal (Saka vs Gyökeres) e no Spurs (Solanke vs
Richarlison): esses clubes ficam com `confianca: "media"` e o efeito é reduzido a metade.
`fetch_bolaparada()` casa os nomes por clube (`casar_nome`) — 113 jogadores, os 20 clubes com
batedor de penáltis identificado.

**Como entra no modelo, sem contar a dobrar** (`pontosBolaParada`): um penálti vale ~0.79 de
golo e as equipas ganham ~0.12 por jogo, logo `PEN_GOLOS_90 = 0.095` para o 1.º batedor (20%
para o 2.º, 5% para o 3.º), mais uma parcela pequena para livres diretos e cantos. O ponto
subtil: **quem já batia os penáltis no ano passado tem isso dentro do xG**, portanto somar
outra vez seria duplicar. O acréscimo é multiplicado por `pesoBolaParada`, que mede o quanto
o histórico *não* cobre: 1 se o jogador mudou de clube (o histórico é de outro sítio),
senão `MIN_PRIOR / (minutos + MIN_PRIOR)`. Na prática: B.Fernandes (3065 min, três cargos)
leva só +0.16 pts/90; o Hackney (0 min, transferido, cantos #2) leva o peso todo.

Os cargos aparecem como etiqueta na tabela de projeções (P/LL/C + ordem), na decomposição do
tooltip e nas justificações ("bate os penáltis da equipa").

## Analisador de trocas (separador "Analisar troca", 2026-08-21)

Avalia uma troca concreta — recebida ou a propor — com **N jogadores de cada lado**, não só
1-por-1. Escolhe-se o gestor, marcam-se os jogadores nas duas colunas e a análise é imediata.

- **Validade**: uma troca só é possível se as posições baterem certo dos dois lados (o plantel
  tem de manter 2 GR, 5 DEF, 5 MED, 3 AV). Se não baterem, diz porquê e mostra na mesma os
  números como referência.
- **Métrica**: `valorXI` antes/depois **nas duas equipas** — o que conta é o onze inicial, não
  a soma dos jogadores (um reforço que fica no banco não vale nada à margem).
- Mostra ainda: pts/jornada que entram de cada lado, diferença nas próximas 3 jornadas
  (com dificuldade do calendário) e **pontos da época passada** ("cartaz"), que é o número
  que o outro gestor costuma olhar.
- **Veredicto** em linguagem corrente, com o motivo por jogador (`porqueSai`/`porqueEntra`) e
  avisos que os números não contam: dar alguém que está apenas temporariamente em baixo,
  receber alguém que recupera valor, ou receber quem não sai do banco.
- `ppjSaudavel` passou a ser `projecao(p, ignorarAusencia=true)`: antes só ignorava o estado
  da API, por isso não disparava avisos para quem está fora apenas por indicação do Scout
  (o caso do Pedro Porro). Isto corrigiu também o mesmo ponto cego no aviso dos waivers.

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
- **Fase 2 (feita, separador removido em 2026-08-21)**: existiu um separador "Equipa" com o
  meu plantel e "Alvos de waiver". Foi **removido a pedido do utilizador** por duplicação: o
  plantel está no cartão ★ do separador "Equipas" (aberto por omissão) e os livres estão em
  "Melhores livres" nas Sugestões, aí ordenados por projeção em vez de draft_rank.
  O que se manteve: `news_new` no fetch_data.py (compara com o data.json anterior; primeira
  execução nunca marca nada) e a deteção da equipa pelo apelido do gestor (`MEU_GESTOR`,
  regex /gentil/i em app.js).
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
