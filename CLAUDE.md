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

## Janela do calendário (2026-08-21)

Antes eram fixas 3 jornadas (`prox3`, um **total**). Medi a amplitude do fator de dificuldade
no calendário real: **10.0%** a 3 jornadas, 6.0% a 5, 5.0% a 6, **2.4%** a 10 — e entre 3 e 6
uma equipa muda em média 6 lugares em 20. O problema dos 3: com 10% de amplitude o sorteio
inverte diferenças de qualidade entre jogadores (os melhores livres separam-se por 3-5%), e as
decisões de waiver são na prática permanentes. Os 10 matam o sinal.

- **Janela por omissão: 5, com decaimento** `0.85^i` (a próxima jornada pesa mais).
- `prox3` deu lugar a `calFator` (média ponderada, ~1.0) e **`ppjCal = ppj × calFator`** — uma
  **taxa**, não um total: não cresce com a janela e fica comparável aos pts/jornada. Coluna
  "Calend." nas tabelas.
- **Seletor 3/5/8** no topo das Sugestões, guardado em `localStorage` (`janela`). Redesenha
  onze, projeções, sugestões, tabela de jogadores e análise de trocas. Serve para ver se uma
  decisão depende do horizonte: quando não muda entre 3 e 8, é sólida.
- Nos waivers, a **qualidade filtra** (`ganho >= 0.4`) e o **calendário ordena** (`ganhoCal`).
  Os "melhores livres" são ordenados por `ppjCal`, senão o seletor não teria efeito visível.
- O **onze inicial não usa a janela** (horizonte 1, `ppj`) — verificado nos testes.
- A janela para trás (minutos dos últimos 3 jogos) fica em 3: aí a reatividade a mudanças de
  estatuto vale mais do que a estabilidade.
- **O seletor parecia não fazer nada** (reparo do utilizador). Fazia — só que o efeito real do
  calendário é de ±5% e ficava escondido dentro do número final. As sugestões de waiver do topo
  são estruturalmente insensíveis (o Kroupi.Jr está a 0.0 e o substituto a 4.0; ±5% não inverte
  4 pontos), o que é o comportamento certo. Correção foi de comunicação, não de modelo: a coluna
  "Calend." mostra agora o ajuste em percentagem por baixo do valor (`sinalPct`), o tooltip lista
  os adversários com a dificuldade de cada um (`explicarCalendario`), e por baixo do seletor há
  uma frase com a amplitude real dessa janela (`amplitudeCalendario`), a dizer explicitamente que
  serve para afinar entre jogadores parecidos e não para inverter diferenças grandes.

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

## Modo "Clássica" (FPL normal, 2026-08-21)

Segundo modo, a pedido do utilizador, para a FPL clássica
(`fantasy.premierleague.com/api`) a par do Draft. Botão no cabeçalho, guardado em
`localStorage` (`modo`); trocar recarrega a página com o outro ficheiro de dados.

- `scripts/fetch_classica.py` escreve `site/data/classica.json` **na mesma forma** do data.json
  do Draft — é isso que permite reutilizar o motor de projeção inteiro (`projecao`,
  `componentesPP90`, bola parada, calendário, FFS, pré-época) sem uma linha alterada. Importa
  as funções partilhadas de `fetch_data.py`.
- Diferenças reais da clássica, todas lidas da API: orçamento de 100.0M (`squad_total_spend`),
  preços (`now_cost`) e propriedade (`selected_by_percent`), **máximo 3 por clube**
  (`squad_team_limit`), transferências com custo de −4, e chips (2 wildcards, 2 free hits,
  2 bench boosts, 2 triple captains, por metade da época). A tabela de pontuação vem em
  `game_config.scoring` aninhada por posição e é achatada para o formato do Draft
  (`goals_scored_GKP`) que `regra()`/`regraPos()` já esperam.
- **Bónus**: na clássica os campos de bola parada **vêm preenchidos** (131 jogadores), ao
  contrário do Draft. Confirmam a tabela curada à mão (Saka, Buendía, Palmer, Thiago…) e neste
  modo dispensam o `bolaparada.json`.
- O calendário sai de `/fixtures/` num único pedido, com `team_h_difficulty`/`team_a_difficulty`
  já calculadas — não é preciso o truque dos 20 `element-summary` do Draft.
- Interface: `data-modo="draft|classica"` nos separadores e blocos; `aplicarModo()` esconde o
  que não pertence ao modo. Na clássica desaparecem Liga, Equipas e Analisar troca, a coluna
  "Dono" passa a "Preço" (com a percentagem de equipas que o têm), a ordenação por draft rank dá
  lugar a preço, e as Sugestões ganham **Capitão** (o dobro é a maior decisão da jornada),
  **Transferências** (orçamento, limite por clube e se o ganho paga os −4) e **Chips**.
- Sem `FPL_ENTRY_ID` o modo funciona na mesma: capitão entre todos os jogadores e tabela de
  pontos por milhão. Com o id, mostra plantel, banco, chips usados e sugestões para a tua equipa.
  As escolhas de uma jornada só existem depois do deadline (a API dá 404 antes disso).

## Jornada a decorrer: "jogado" vs "finalizada" (2026-08-22)

Bug apanhado com a GW1 a meio (Arsenal-Coventry jogado na sexta, o resto no fim de semana):
os jogadores cujas equipas ainda **não tinham jogado** eram contados como tendo feito 0 minutos,
e a projeção do Isak caiu de 4.3 para 0.9. Três correções:

- `jornadas[ev].equipas` passa a listar **só as equipas cujo jogo já se realizou**
  (`finished` **ou** `finished_provisional`: a API só marca `finished` depois de confirmar os
  bónus, horas depois do apito final).
- `finalizada` continua a exigir o `finished` estrito — é o que decide se a jornada vai para
  cache e se entra na avaliação de precisão, onde os pontos ainda podem mexer com os bónus.
- `utilizacao()` no app.js deixou de usar o `finalizada` da jornada para decidir se conta: usa
  `equipas.includes(p.team)`, ou seja, **o jogo daquele jogador**. Os minutos de quem jogou na
  sexta contam logo; quem joga na segunda não é penalizado entretanto.
- A cache de jornadas ganhou um guarda: uma entrada dada como finalizada mas **sem equipas**
  vem da versão com o erro e é repedida (senão o valor errado ficava lá preso).

## Mini-liga da clássica (2026-08-22)

`FPL_LEAGUE_ID=779399` ("Catan at home", 5 equipas) fixado no `atualizar.cmd`.
`fetch_liga()` lê `/leagues-classic/{id}/standings/` e, por ser uma liga pequena, vai buscar
também as **escolhas de cada participante** (`/entry/{id}/event/{ev}/picks/`, público depois do
deadline). Fica em `classica.json → classica.liga`.

Isso destranca dois separadores no modo clássico, que antes eram só do Draft:

- **Liga**: classificação da mini-liga, com o capitão de cada gestor e a minha linha destacada.
- **Equipas**: cartão por adversário com o plantel e quem está no banco, e **quantas equipas da
  liga partilham cada jogador** ("toda a liga", "3 equipas", "só ele").

No topo das Equipas há o que importa mesmo numa liga pequena: **quem só eu tenho** (é onde a
liga se ganha ou perde) e **quem todos os outros têm e eu não** — este é o risco mais caro,
porque cada ponto que esse jogador faz é terreno perdido para todos ao mesmo tempo. Em
2026-08-22: 13 dos meus 15 eram só meus, e faltavam-me B.Fernandes (capitão de três deles),
João Pedro e Calafiori.

## Próximos jogos (2026-08-22)

Secção nas Sugestões com **quando é que os meus jogadores entram em campo**, hora de Lisboa,
agrupada por dia: hora, jogo, dificuldade, jornada e os meus jogadores em cada partida (com
aviso de quem está fora ou em dúvida). Serve nos dois modos — os "meus" são os do `owner` no
Draft e as `picks` na clássica, e em ambos vêm do mesmo `meusX`.

Para isto foi preciso guardar `kickoff` nas fixtures (antes só se guardava evento, adversário,
casa/fora e dificuldade). E há uma diferença entre as duas APIs que custou a apanhar:

- **Clássica**: `/fixtures/` mantém os jogos por disputar da jornada a decorrer. Basta incluir
  a jornada atual (não só a seguinte) e excluir `finished`/`finished_provisional`.
- **Draft**: assim que o deadline passa, a jornada a decorrer **desaparece** do `fixtures` do
  `element-summary` (vai para o `history`, mesmo sem o jogo se ter realizado) **e** do
  `bootstrap-static.fixtures`, que passa a começar na jornada seguinte. O único sítio onde os
  jogos por disputar continuam é **`/event/{ev}/live` → `fixtures`**, de onde são recuperados e
  juntos ao calendário (com dificuldade 3 por omissão, que esse endpoint não a traz).

## Quem já saiu da liga, e a fonte que o diz (2026-08-30)

Reparo do utilizador: as sugestões mandavam trocar o Gyökeres pelo **Watkins**, que ia sair da
liga. Era pior do que parecia.

O Watkins tinha transferência **confirmada pela Premier League** ("completes move to Al Hilal",
£51M) mas o `status` na FPL ainda era `"a"` — a FPL demora a atualizá-lo. O guarda que eu tinha
olhava para o status, não disparava, e como o valor era ≥50M ele ainda **ganhava piso de 75
minutos**: um jogador que saiu da liga aparecia **promovido**.

**Fonte nova, indicada pelo utilizador**: `transfermarkt.pt/premier-league/transfers/wettbewerb/GB1`
(`robots.txt` com `Allow: /`). Lista, por clube, duas tabelas — **Entradas** (coluna Origem) e
**Saídas** (coluna Destino) —, e a primeira célula do cabeçalho diz qual é. É a única fonte que
dá a **direção do negócio** de forma inequívoca.

- `fetch_transfermarkt()` cruza os nomes e devolve quem está nas **saídas e em nenhuma entrada**:
  uma transferência entre dois clubes da liga aparece nas duas listas, por isso é a diferença que
  identifica quem se foi embora. 273 entradas, 230 saídas, **27 jogadores fora da liga** — dois
  deles ainda com `status "a"` na FPL.
- Vai para `data.json → saiu_da_liga` (nos dois modos, com os ids de cada API).
- No app.js, `indisponivel(p)` substitui `STATUS_FORA.has(p.status)` nos **11 sítios** onde
  "fora" significa "não pontua": projeção 0, fora dos livres, fora do onze, fora das sugestões.
  `estadoDe()` mostra "Saiu da liga".

**As sugestões, revistas ao mesmo tempo**: passam a avisar quando um jogador que entra numa
troca **não pode jogar** — ocupa uma das 15 vagas e não pontua. A primeira versão avisava também
para dúvidas de 75% e disparava em 4 de 5 trocas; agora só abaixo de 50%, e passou a 1 em 5.

**O separador das transferências ficou mais simples**, a pedido: das 349 linhas, **152 eram
ruído** (empréstimos de juniores a divisões inferiores, tipo "Ben Broggio → Stevenage"). Por
omissão mostram-se as 197 que interessam — jogadores da FPL ou negócios com valor —, com uma
caixa para ver tudo. A legenda passou de quatro linhas a uma, e a tabela pagina de 40 em 40.

## Trocas de N por N, e a descoberta de que não há win-win (2026-08-26)

Reparo do utilizador: as sugestões eram sempre 1-por-1, e "nem sempre se convence um gestor sem
acrescentar mais valor". Planeado primeiro, discutido, depois implementado até **3-por-3**.

**A restrição que decide tudo**: `size: 15` com `2 GR / 5 DEF / 5 MED / 3 AV` em permanência.
Logo **dar 2 e receber 1 é ilegal** — uma troca é sempre N-por-N e com o **mesmo multiconjunto
de posições** dos dois lados. "Acrescentar valor" não é dar mais jogadores, é dar melhores.

**Custo, medido antes de construir**: 378 combinações a 1, 9 126 a 2, **109 626 a 3** (a
restrição de posições corta 11× o bruto de 1,24 M). A `valorXI` custa 1.4 µs, portanto o
exaustivo leva **~200 ms**. Não foi preciso heurística nenhuma.

**A hipótese que eu tinha escrito no plano estava errada.** Argumentei que o 2-por-2 seria
positivo para os dois lados por causa do banco: um jogador parado no meu banco vale-me zero à
margem e podia valer no onze dele. Testei as **119 130 combinações**: `ambos` dispara **zero
vezes**. A razão é estrutural — com 7 gestores a deterem 15 de 600 jogadores, os cortes do onze
ficam parecidos, e quem está no meu banco também não entra no onze dele. Em 61 057 combinações
em que eu ganho, ele perde sempre.

Consequência: **toda a troca realista nesta liga é "eu ganho, ele perde"**, e a única alavanca é
o que se lhe entrega a mais. Fica o tipo `adocante`, e o `ambos` fica no código porque uma vaga
de lesões pode criar a assimetria — só que hoje não existe.

**O adoçante tem de ser a sério.** A primeira versão aceitava qualquer `dou > recebo` e produzia
propostas a dizer "ele recebe mais do que dá" com **9.9 contra 9.9** — quatro centésimas para
ele perder 2.35 pts/jornada no onze. Agora exige-se `entregue >= ADOCANTE_MIN` (0.4) **e**
`entregue >= metade do que ele perde no onze`: quem perde 2 pontos não aceita por meio.

Mais dois travões: `MARGEM_TAMANHO` (0.15) impede um 3-por-3 de aparecer quando um 1-por-1 já
consegue o mesmo — sem isso saíam sempre os mesmos negócios com enchimento à volta —, e cada
jogador só entra numa proposta, senão saíam cinco variantes do mesmo. As trocas não correm no
modo clássico, onde seriam 119 mil combinações para nada.

## O que faltava nas transferências, e a frase que se contradizia (2026-08-26)

Dois reparos do utilizador, ambos certos.

**"Uma transferência do City não aparece."** A tabela era indexada por jogadores da FPL, e
descartava tudo o resto — **185 negócios com um clube da PL de um dos lados**, incluindo o
Højlund para o Nápoles por £38M. São dois casos: reforços acabados de fechar que a FPL ainda
não tem na base de dados, e saídas da liga. Passam a entrar com o nome da Wikipedia e o
distintivo "fora da FPL"; `jogador` fica a `null` e o modelo ignora-os, que é o correto.
De 128 para **313 transferências, 88 com valor**.

*O caso concreto (Bouaddi, do Lille para o City, £86M) ainda assim não aparecia*: fechou às
11:15 desse dia e nessa altura **não estava nem na FPL nem na Wikipedia**. Está nas notícias do
Mercado, que vêm do live blog, e entra na tabela quando uma fonte estruturada o listar.

**Duas tabelas, dois esquemas.** A página da Wikipedia tem a das transferências
(Date · Player · Moving from · Moving to · Fee) e a dos **empréstimos**
(Start date · End date · Name · Moving from · Moving to), sem coluna de valor. Ler pela posição
punha a data no lugar do nome ("30 June 2027" como jogador). `WIKI_COLUNAS` mapeia pelo
**cabeçalho**, e o rowspan passa a ser resolvido contando as células em falta à esquerda.
94 empréstimos identificados como tal.

**"Mandas trocar o Ødegaard pelo Scott, não faz sentido."** A sugestão em si é marginal (0.43
contra um limiar de 0.4), mas **a frase estava errada**: dizia *"Ødegaard rende 4.9 pts por 90
min, abaixo da alternativa"* com o Scott a **4.4** ao lado. Era uma frase-tampão que nunca olhava
para os números. `porqueSai(x, entra)` passa a receber a alternativa e a dizer o motivo real:
*"rende mais por 90 minutos (4.9 contra 4.4), mas deve jogar menos: 64 min contra 80"*.

O motivo é mesmo esse: **por 90 minutos o modelo dá-lhes exatamente o mesmo** (4.59 os dois),
com composições opostas — o Ødegaard em golos, assistências e bónus, o Scott em contribuição
defensiva (1.19 contra 0.11). A diferença toda está nos minutos, e vem de a época passada ter
sido de 34 titularidades para o Scott e 16 para o Ødegaard. **O modelo não distingue "faltou por
lesão" de "não era titular"** — é o seu ponto cego aqui, e cada jornada em que o Ødegaard
comece reduz o peso desse prior.

**A contribuição defensiva foi validada contra a GW1**, já que dela dependia o caso do Scott:
128 jogadores com 60+ minutos, previsto 18.5% contra 17.2% real, calibrado por faixa (5%→5%,
28%→24%, 50%→57%) e com MAE 0.218 contra 0.285 de dar a média a todos. Uma jornada é pouco,
mas a Poisson não está a mentir.

## Transfer Centre ao vivo do Sky (2026-08-26, página indicada pelo utilizador)

`https://www.skysports.com/transfer-centre` — a mesma coisa que o live blog que o utilizador
mandou, mas por um endereço **estável**: o URL do live blog leva um id que o Sky roda
(`12476234` hoje), e `/transfer-centre` já traz o mesmo conteúdo. O `robots.txt` permite ambos;
só veda `/api/` e um caminho `live-blog-beta`.

- **A página é montada por JavaScript** — não há `<article>` nem `<time>` no HTML que ela
  devolve. O conteúdo está no **JSON-LD `LiveBlogPosting`** de schema.org, publicado de propósito
  para máquinas. `liveblog_itens()` lê de lá e devolve itens no formato dos de RSS.
- **Porque vale a pena**: 9 dos 10 itens não estavam no feed 12691, e cada um traz o
  **`articleBody` completo**, que é onde os valores aparecem escritos ("in a record-breaking £86m
  move from Lille") — o RSS só dá 220 caracteres de resumo. O corpo é cortado a
  `LIVEBLOG_RESUMO = 400`: chega para o valor, que vem na primeira frase, sem arrastar o artigo
  todo e com ele nomes de outros jogadores.

**Três erros meus que isto destapou**, todos de atribuição de transferências:

- **Janela em falta no modelo.** Quando passei o feed oficial de 40 para 250 artigos (para o
  separador), o corte de data ficou só na lista visível: **62 jogadores** estavam marcados com
  `confirmada` por movimentos de há até 18 meses (o Jackson emprestado ao Bayern em setembro de
  2025). O `confirmada` isenta do castigo da pré-época e dá piso de minutos — nada disso faz
  sentido para quem já lá joga há meia época. `desde` passa a filtrar também as marcas do modelo.
- **`web_name` partilhado.** "Leeds sign England goalkeeper James Trafford" era atribuída ao
  **Reece James e ao Daniel James**, que têm ambos `web_name` "James". `casar_transferencia()`
  passa a tentar primeiro o **nome completo** (só o Trafford tem "james" e "trafford") e só
  recorre ao nome curto quando ninguém bate — exigindo aí que seja um só. Um artigo de
  transferência é sobre um jogador: atribuí-lo a dois é pior do que não o atribuir.
- **Homónimos entre ligas.** Há um Reece James no Rotherham, e a linha da Wikipedia
  "Rotherham United → Sheffield Wednesday" casava com o do Chelsea. Nome nenhum resolve isso;
  `envolve_clube_pl()` exige um clube da Premier League de um dos lados, comparando com os nomes
  oficiais (os slugs de `PL_CLUBES`), que é como a Wikipedia os escreve.

Um teste apanhou ainda que eu passava texto cru aos padrões de nome, que são construídos sobre
texto sem acentos — "Gyokeres" nunca casaria com "Gyökeres".

## A jornada equipa a equipa (2026-08-24, pedido do utilizador)

Tabela no topo do separador **Liga**, só no Draft: por gestor, os pontos já feitos, quantos
jogadores lhe faltam entrar em campo, quem são, e a previsão de onde a jornada vai acabar.
Ordenada pela previsão, com a minha equipa marcada.

- **Só conta o onze.** No Draft o banco não pontua, e sem as escolhas de cada gestor a tabela
  somaria os 15. `fetch_picks_jornada()` vai a `/entry/{entry_id}/event/{ev}` dos 7 gestores
  (`position` 1-11 = onze, 12-15 = banco) e guarda em `data.json → picks_jornada`. Antes do
  deadline o endpoint dá 404: nesse caso a linha cai no plantel todo e a legenda **diz que a
  previsão está inflacionada**, em vez de mostrar um número errado sem aviso.
- **"Já jogou" é o jogo daquele jogador**, não a jornada inteira — a mesma distinção que já
  existia em `utilizacao()`. Com os jogos espalhados pelo fim de semana, quem joga na segunda
  tem tudo por fazer.
- **As substituições automáticas não estão contadas**, e a legenda diz isso: a API só as aplica
  no fim da jornada (`subs` vem vazio a meio).
- Os nomes de quem falta ficam **por baixo do nome da equipa**, não numa coluna própria — numa
  coluna desapareceriam em ecrã estreito, que é onde isto mais se olha.

Um teste meu falhou por estar mal escrito: comparei `feitos` (pontos) com uma contagem de
jogadores. A verificação certa é que nenhum id do banco aparece na lista de quem falta.

## Sugestões da clássica: o que estava partido (2026-08-24)

Reparo do utilizador: "as sugestões da parte clássica não parecem estar a funcionar". Estavam
mesmo, e a causa principal foi **regressão minha da véspera**.

- **Colisão de nomes.** Criei `desenharTransferencias()` para o separador Transferências novo e
  já existia uma função com esse nome para as sugestões da clássica. Em JS isto **não dá erro**:
  a segunda declaração silencia a primeira por hoisting. Resultado: a secção "Transferências"
  das sugestões ficava com o título e nada por baixo, e a consola limpa. A do separador passou a
  `desenharTabelaTransferencias()`. **Há agora um teste** (`testa_nomes_funcoes`) que lê o app.js
  e falha se houver dois `function` de topo com o mesmo nome — teria apanhado isto.
- **Vocabulário do Draft no modo clássico**: o contexto dizia "és o #? na fila de waivers" (não
  há waivers na clássica) e a tabela chamava-se "Melhores livres" (na clássica todos se compram).
  `contextoClassica()` mostra agora equipa, pontos, classificação geral e o lugar na mini-liga.
- **Ordem das secções.** Capitão, Transferências e Chips — as três decisões da jornada — estavam
  **por baixo** da Precisão do modelo e do plantel ideal. Subiram para logo a seguir ao onze.
- **"Melhor plantel possível"** era a versão feita à pressa no deadline, quando o `FPL_ENTRY_ID`
  ainda não era conhecido. Com plantel carregado não serve para nada e passou a ficar escondido
  (`#bloco-otimo`), em vez de aparecer com o título e o corpo vazio.

## Os outros chips e o planeador do wildcard (2026-08-26, pedido do utilizador)

**Os quatro chips passam a olhar para o plantel**, não só o wildcard. A base é
`jornadasEspeciais()`, que conta jogos por clube em cada jornada futura e devolve, dos **meus**
clubes, quais ficam em branco e quais jogam duas vezes.

**A jornada a decorrer fica de fora de propósito.** As fixtures só guardam os jogos por
disputar, por isso a meio de uma jornada os clubes que já jogaram parecem estar em branco — a
GW2 aparecia com 18 "em branco" que eram 18 jogos já realizados. Foi o que me fez desconfiar dos
dados e verificar contra a API antes de construir por cima.

- **Free Hit**: aponta a jornada em que mais clubes meus ficam parados (≥ 4 justifica o chip).
  Hoje nenhum fica, e diz isso em vez de um conselho genérico.
- **Bench Boost**: aponta a primeira jornada dupla; sem duplas no calendário conhecido, diz o
  que o banco projeta e porque é que esperar vale mais.
- **Triple Captain**: se o melhor capitão tiver jornada dupla, recomenda-a; senão dá o nome, o
  ganho e a dificuldade do próximo adversário, e recomenda usar só se for fácil.
- Estado real do calendário em 2026-08-26: **nenhuma jornada dupla** até à 12 e a GW12 com 2
  equipas em branco (nenhuma minha).

**Planeador do wildcard**: `melhorPlantelPossivel(fixos)` passa a aceitar jogadores que têm de
lá estar. Escreves nomes, e o plantel é construído à volta deles dentro dos 100.0M, do 2/5/5/3 e
do máximo de 3 por clube. Os fixos ocupam vaga, contam para o clube e para o orçamento, e o
ciclo de melhorias nunca lhes toca.

- **Recusa com explicação** em vez de devolver um plantel errado: "Escolheste 3 GR e o plantel
  só leva 2", "Escolheste 4 jogadores do MCI e o máximo é 3", ou o custo acima do orçamento.
- **Avisa quando um fixo cai para o banco**, que é o custo escondido de insistir em três caros:
  com Haaland + Saka + Isak, o Isak fica no banco a 9.0M — dinheiro parado que não pontua.
- O número que interessa é a comparação: sem escolhas o onze ideal projeta 52.6 pts/jornada
  contra os 46.0 do plantel atual; insistindo nos três caros cai para 49.9.

## Quando usar o wildcard (2026-08-24, pedido do utilizador)

O chip deixou de ter um texto genérico e passa a olhar para o plantel. `analiseWildcard()`.

**O raciocínio, que não é o óbvio**: o wildcard *não* vale pelo plantel ideal que permite montar
— esse está sempre à frente do teu, porque o modelo tem opiniões e um plantel real tem história.
Vale pelos **−4 que evita**: com uma transferência livre por jornada, fazer N mudanças de uma vez
custa `4 × (N − 1)` pontos.

- Só contam as trocas que **se pagariam a si próprias mesmo com a penalização**
  (`ganho × janela ≥ 4`); as outras não seriam feitas de qualquer maneira e inflacionariam o caso
  a favor do chip.
- **O ganho conta-se no onze** (`valorXI` antes/depois), não na soma das trocas. Isto apanhou um
  erro grosseiro na primeira versão: das 6 trocas sugeridas, **4 eram de jogadores do banco**, e
  trocar quem não joga não dá pontos nenhuns. O número passou de 10.1 para **4.1 pts/jornada** —
  a diferença é real porque as saídas do banco libertam orçamento para o onze.
- **Veredicto com três condições**: ≥ 4 trocas a compensar, penalização ≥ 8 pts, e o ganho no
  onze a pagar a penalização dentro da janela. Quando não recomenda, diz porquê — incluindo o
  caso "as trocas que faltam são quase todas de banco, e o banco não pontua".

## Onde estão os valores das transferências (2026-08-23)

Primeira versão do separador tinha **7 valores em 100**. O utilizador reparou e mandou alargar a
pesquisa, começando pelo Fantasy Football Scout. Fontes sondadas, com o que cada uma deu:

| Fonte | Resultado |
|---|---|
| **Fantasy Football Scout** | **Não serve.** É um site de *fantasy*: "transfers" ali são as trocas de FPL e as mudanças de preço. No sitemap, os artigos de mercado real são de 2008-2010 (Rosicky, Robinho, Megson). |
| Corpo dos artigos da PL | Vem **sempre vazio**, tanto na listagem como no artigo individual. |
| BBC (`/sport/football/transfers/rss.xml`) | 1 item. O de rumores tem 1 valor em 24. |
| Sky Transfer Centre | 3 valores em 20 itens (já era usado). |
| **Guardian** (`football/transfer-window/rss`) | **12 valores em 20** — o melhor dos feeds. Acrescentou 2 jogadores. |
| **Wikipedia** (`List_of_English_football_transfers_summer_2026`) | **824 linhas, 117 jogadores desta liga, 67 com valor.** |

**A conclusão que interessa**: não era falta de fontes, era **falta de histórico**. Todos os
feeds de notícias trazem ~20 itens das últimas duas semanas, e a janela vai de maio a agosto.
A Wikipedia é a única fonte com a janela toda, e ainda por cima tabelada: Data, Jogador, clube
de origem, clube de destino e valor. Resultado: **66 valores em 136** (eram 7 em 100), mais os
clubes, que antes não existiam de todo.

- **Permissão**: o robots.txt bloqueia `/w/` e `/api/` (logo nada de `api.php`), mas
  `/wiki/<artigo>` é permitido — só as páginas `Special:` estão vedadas. Extraem-se factos
  (nomes, clubes, valores), não texto. Pedido com `Accept-Encoding: gzip` (a página tem 3.5 MB).
- **`rowspan`**: a coluna da data agrupa as transferências do mesmo dia, por isso as linhas
  seguintes só têm 4 células e herdam-na. Sem tratar isso apanhavam-se **77 das 824** linhas.
- **Cruzamento de nomes**: exige que **todas** as palavras do nome da Wikipedia estejam no nome
  completo do jogador do FPL. Restritivo de propósito — deu 117 correspondências e **zero
  ambiguidades**.
- **"Free" e "Undisclosed" não são valores em falta**: são informação, e vão para o ecrã como
  "livre" e "n/d". 14 livres e 36 não divulgadas.
- Um teste apanhou que `_texto_celula` não descodificava entidades HTML (`&#163;` ficava
  literal). Na tabela real não dava erro porque a Wikipedia usa caracteres literais — mas era
  uma bomba à espera. A ordem certa é: fora a marcação, depois `html.unescape`, só então as
  notas de rodapé, que podem vir escritas `&#91;1&#93;`.
- **O Guardian entra só para o preço, nunca para a confirmação**: o feed mistura negócios
  fechados com rumores ("Football transfer rumours:", "see £50m bid rejected").

## Separador "Transferências" (2026-08-23, pedido do utilizador)

Só no Draft. Todas as transferências concluídas da janela, da mais recente para a mais antiga,
com o valor quando existe. Vem de `data.json → mercado.transferencias_feitas`.

- **Colunas**: Data · Jogador · Movimento (origem → destino) · Valor · Notícia. Em ecrã
  estreito a coluna da notícia sai (`.col-noticia`) e o link passa para o nome do jogador,
  senão a página ganhava scroll horizontal a 375px (438 contra 375).
- **Junta as fontes, que são complementares**: a PL confirma o negócio mas **não publica
  valores**; a Sky publica valores mas também noticia acordos ainda por fechar. Daí a coluna
  levar um distintivo **PL** (oficializado) ou **Sky** (noticiado) — o Baleba aparece com
  £70M e distintivo Sky porque o "Man Utd agree £70m deal" ainda não estava fechado, e por
  isso ele continua listado no Brighton. Na prática: 97 oficiais, 3 só da Sky, 7 com valor.
- **Inclui as saídas da liga** (distintivo "saiu da liga"), ao contrário do `transferencias`
  que alimenta o modelo — saber que o Reijnders se foi embora é tão útil como saber quem chegou.
- **Janela desta época**: `series:transfers` pagina até 2025 (250 artigos), o que traria dois
  anos de mercado. O corte são 100 dias antes da primeira jornada, calculado a partir do
  `deadline_time` do primeiro evento em vez de uma data escrita à mão. Ficam 100 negócios.
- O mesmo negócio costuma ter dois artigos ("agree deal", depois "completes move"): fica o mais
  recente, mas o valor nunca se perde ao juntá-los.
- Pesquisa por jogador ou clube e filtro "só com valor". `semAcentos()` no app.js replica o
  `sem_acentos` da recolha, incluindo as letras que o NFD não decompõe (ø, đ, ł…).

## Notícias oficiais da Premier League (2026-08-23, pedido do utilizador)

Segunda fonte a par da Sky: `api.premierleague.com/content/premierleague/en`, a **mesma API que
alimenta premierleague.com**. Descoberta a ver que pedidos o próprio site faz (não há RSS, e o
sitemap é só estrutural, sem `<news:>`).

- **Permissão**: o `robots.txt` de www.premierleague.com só bloqueia parâmetros de rastreio
  (`utm_*`, `fbclid`…) e deixa os caminhos de conteúdo livres; `api.premierleague.com` não
  declara robots e a página de termos não menciona acesso automatizado. É a mesma organização
  da API do FPL que o projeto já usa.
- **Endpoint**: `?contentTypes=TEXT&offset=0&limit=N&onlyRestrictedContent=false&detail=DETAILED`
  com `&tagNames=`. Precisa do cabeçalho `Origin: https://www.premierleague.com`. Devolve
  `title`, `description`, `body`, `date`, `canonicalUrl` e `tags`.
- **Etiquetas úteis**: `club-produced-content:<clube>` (o que o próprio clube publica — relatos
  de conferência e atualizações do treinador sobre lesões), `series:transfers`, `label:Club News`.

**A armadilha, e porque é que `PL_CLUBES` é um mapa curado**: uma etiqueta desconhecida **não dá
erro — devolve o feed geral em silêncio**. Num primeiro mapeamento automático por tokens,
"Spurs" foi parar ao **Wolverhampton** (não partilha nenhuma palavra com "Tottenham Hotspur") e
"bournemouth" devolveu notícias gerais (o certo é **`afc-bournemouth`**, a mesma irregularidade
já vista nos slugs da BBC). Os dois *pareciam* funcionar. A validação que apanhou isto foi
semântica: pedir os artigos de cada clube e confirmar que **jogadores desse clube** aparecem lá.
19 em 20 batiam certo à primeira.

**Integração**: `fetch_pl_clubes()` devolve os itens no mesmo formato dos de RSS (`pl_item`) e
entram por dentro de `fetch_feeds_clubes()` — logo aproveitam o filtro de ruído, a deteção de
antevisão e o cruzamento de nomes limitado ao plantel do clube, e servem os **dois modos** sem
duplicar código. `sem_repetidos()` junta a mesma notícia vinda das duas fontes. No separador
Conferências cada item leva um distintivo **PL** ou **Sky**. Resultado: 51 itens oficiais contra
37 da Sky, entre eles coisas como "Arteta's update on Guimaraes' injury after win over Coventry".

**Transferências confirmadas** (`fetch_pl_transferencias`): o `extrair_transferencias` decide
"confirmada" por regex nos títulos da Sky, que é um palpite; quem aparece em `series:transfers`
mudou mesmo de clube. 33 confirmações. Dois travões que a primeira versão não tinha:

- A lista oficial traz **entradas e saídas**. Marcar o Reijnders (Al Qadsiah), o Vicario
  (Juventus) ou o Digne (PSG) como transferência confirmada era dizer ao modelo o contrário do
  que aconteceu. Saltam-se os jogadores com status `u`/`n`.
- A fonte oficial **não publica valores**, e `pisoTransferencia(0)` devolvia **50 minutos** —
  ou seja, qualquer reforço de plantel ganhava piso de meio jogo. O piso passa a exigir
  `valor > 0`: o sinal é "custou caro, logo vai jogar", e sem preço não há sinal. Eram **23
  jogadores** a levar piso indevido. A confirmação sozinha continua a valer para a pré-época
  (o onze do clube antigo não diz nada de quem mudou). Os valores continuam a vir da Sky.

## Contribuição defensiva: uma categoria de pontuação que faltava (2026-08-23)

O maior buraco encontrado até hoje. A liga pontua `defensive_contribution` com **2 pontos** a
quem chega ao limiar de ações defensivas **naquele jogo** (10 para DEF, 12 para MED/AV) e o
modelo ignorava-a por completo — a par de `penalties_missed` e dos limiares de minutos.

Medido em 178 defesas/médios com 900+ min na época passada (`history_past` da API clássica):

| | Média pts/90 | % dos pontos | Amplitude entre jogadores |
|---|---|---|---|
| Defesas (limiar 10) | **0.67** | **15%** | **1.63** (Wieffer → Frimpong) |
| Médios (limiar 12) | **0.37** | 8% | **1.46** (Anderson → Elanga) |
| *Bónus, para comparar* | 0.31 | 7% | 1.31 |
| *Calendário, para comparar* | — | — | ~0.20 |

Com o limiar de waiver em 0.4 pts/jornada, isto sozinho inverte decisões. E o erro era
**sistemático**: subvalorizava defesas e médios de recuperação.

- **Modelo** (`pontosContribuicaoDefensiva`): sendo um limiar **por jogo** e não um total, a
  média não chega — usa-se a mesma Poisson da baliza a zero, `P(X ≥ limiar) × 2`, via
  `probPoissonAtinge`. Aproximação assumida: as ações defensivas são provavelmente mais
  dispersas do que uma Poisson (subestima quem está longe do limiar, sobrestima quem está muito
  acima). Verificável agora que as jornadas ficam guardadas uma a uma.
- **Dados**: a época a decorrer já vinha no bootstrap (`PLAYER_FIELDS`, sem uso). A época
  passada **não estava** no retrato congelado, e este já não se refaz. `completar_historico()`
  vai buscá-la ao `history_past` da API clássica, cruzando pelo **`code`** (604 em 604 batem
  certo), e corre **uma só vez**: no fim os campos ficam a 0 em quem não tem época passada, o
  que faz a verificação de início dá-los como presentes. 366 de 367 elegíveis.
- **Corroboração**: `calibEsperado` — o fator que existe precisamente para tapar o que o modelo
  não tem — caiu de **1.21 para 1.087**. Era a maior parcela em falta.
- **Efeito real**: 3 dos 10 melhores livres mudaram (entram Ampadu, Wieffer, Scott; saem
  Hinshelwood, Neto, Gravenberch); os GR descem ~0.18 (não recebem esta categoria e o nível
  geral baixou). A sugestão de waiver do topo passou a ser o Richards (CRY).
- **Clássica**: publica os pontos mas **não os limiares**. Como escrevê-los à mão foi o que já
  deu dois erros de facto, `completar_limiares()` vai buscá-los ao Draft (mesmas regras de jogo),
  com `LIMIARES_OMISSAO` só como recurso e um registo no diagnóstico.

## As estatísticas desta época a entrar no modelo (2026-08-23)

Antes, a época a decorrer entrava **só como pontos realizados** (`ptsEpoca`, encolhido com
`MIN_PRIOR`); o xG/xA/xGC/bónus ficavam ancorados a maio para sempre. Era o contrário da
premissa do modelo: um avançado com quatro jogos, 1.9 de xG e zero golos continuava a ser
julgado pela época passada.

`historicoCombinado(p, hist)` devolve um objeto com a forma do histórico onde cada estatística
é `contagem desta época + taxa da época passada × MIN_PRIOR`, com `minutes = minEpoca +
MIN_PRIOR`. É a **mesma fórmula que já se usava só para os pontos**, alargada a tudo — por isso
`componentesPP90()` e `taxaBase()` não mudaram uma linha, e o passo especial dos pontos
desapareceu. Com um jogo, esta época pesa ~9%; às dez jornadas, mais de metade.

Dois pormenores: o encolhimento para o prior da posição usa os **minutos reais das duas épocas**
(não os sintéticos do combinado, senão um estreante ficava com o prior subvalorizado), e quem
não tem retrato congelado não é combinado — o `historicoDe` já lhe devolve esta época, e
combinar contá-la-ia duas vezes.

Efeito: Ødegaard 3.85 → 3.51, porque os 11 pontos da GW1 vieram com 0.21 de xG — o modelo passa
a dizer "marcou acima do que gerou, não extrapoles".

## O limiar dos 60 minutos: medido e deixado como está (2026-08-23)

O modelo dá `presenca = 2` e escala tudo por `xmin/90`, quando a presença (2 pts aos 60 min,
1 antes), a baliza a zero e a própria contribuição defensiva são **por jogo**, não por minuto.
Parecia um erro estrutural. Não é, e o motivo é que `xmin = P(joga) × minutos quando joga`:
para quem joga 90 ou não joga, o escalonamento linear está **exatamente certo**.

Medido: **0.048 pts/jornada** de erro médio absoluto em 267 jogadores com 900+ min, **nenhum**
acima de 0.25 (o pior é o Baleba, +0.25, com 72 min por titularidade). Nos jogadores de recurso
(200-900 min, muitos suplentes), 0.154 de média e 1 em 46 acima de 0.25 — e aí as minhas próprias
suposições (80 min por titularidade, 20 por entrada) já valem isso. **Não compensa**; medir
poupou o trabalho.

## BPS: testado e rejeitado; e o que se passou a guardar (2026-08-23)

Pergunta do utilizador: "tens em consideração o BPS por causa dos pontos?". Não — o modelo usa
o **bónus realizado** (`componentesPP90`, parcela `bonus`), e o teste diz que está certo assim.

Medido com `history_past` da API clássica (que **tem** `bps` de épocas anteriores, ao contrário
do `historico` congelado daqui): 575 pares época→época seguinte com 900+ minutos dos dois lados,
validação repetida treinando em metade e testando na outra, com regressão para os dois previsores
(a primeira tentativa deu regressão só ao BPS e inverteu o resultado):

| Previsor do bónus/90 seguinte | MAE | Ganho sobre dar a média a todos |
|---|---|---|
| média a toda a gente | 0.198 | — |
| **BPS/90** | 0.196 | **0.8%** |
| **bónus realizado/90** | **0.184** | **7.3%** |
| metade e metade | 0.187 | 5.8% |

O BPS é quase inútil e misturá-lo **piora**. Razão estrutural: o bónus é um *lugar no top-3
daquele jogo*, e o BPS enche-se de volume (passes, desarmes, recuperações) que não ganha essa
corrida — um defesa acumula BPS e nunca é top-3. Contexto: o bónus vale 7% dos pontos (0.31 em
4.24 pts/90) mas a amplitude entre jogadores é 1.31 pts/90, bem mais do que o calendário.

**O que o teste não cobre**: o regime de início de época. Com 3 jogos o bónus realizado é quase
binário (0 ou 3) e o BPS é contínuo — aí podia acrescentar. Não é testável com a API, porque o
histórico jornada a jornada só existe para a época a decorrer.

Daí a mudança: `fetch_jornadas` (nos dois modos) passa a guardar `JORNADA_CAMPOS` =
**minutos, pontos, BPS, xG, xA, xGC** por jogador e jornada, em lista e não em dicionário
(600 jogadores × 38 jornadas — repetir as chaves custaria mais do que os números). Custo real:
596K → 600K. `jornada_em_cache()` substitui o guarda antigo e **repede as jornadas guardadas
no formato de dois campos**, senão ficavam presas sem BPS para sempre. O `utilizacao()` do
app.js expõe `bps/xg/xa/xgc`, que ficam `undefined` nas jornadas antigas.

Por agora é **só recolha: o modelo não os usa**, e a projeção não mexeu (Ødegaard 3.85 antes e
depois). Serve para responder com números à pergunta do BPS ao fim de 4-5 jornadas.

## Evidência dos primeiros jogos: o Ødegaard pelo Ngumoha (2026-08-22)

Reparo do utilizador: com a GW1 a meio, as sugestões mandavam trocar o **Ødegaard** (75 min e
11 pontos na sexta) pelo **Ngumoha**, que ainda não tinha jogado. Não era uma opinião do modelo
sobre futebol — eram dois defeitos a somar-se, ambos do lado dos **minutos esperados**:

- **A pré-época era cortada a direito.** `jogosObs === 0 ? preEpocaDe(p) : null` deitava fora o
  sinal assim que a equipa jogasse **uma vez**. Ora a pré-época dizia "titular" e a GW1
  *confirmou* — descartava-se uma prova que estava a ser corroborada. Agora o sinal **desvanece**:
  a força é multiplicada por `(1 - peso)`, igual ao que já se fazia com o histórico.
- **O peso da evidência real era baixo demais no início.** `peso = min(1, jogosObs/5)` dava 0.2
  a um jogo, ou seja 80% para a média da época passada (1363 min/38 = 35.9 min/jogo, uma época
  de lesões) contra 20% para os 75 minutos que se acabaram de ver. Passou a **`n/(n+2)`**: um
  jogo vale 1/3, e nunca chega a 1 — o historial mantém sempre alguma palavra, ao contrário do
  `min(1, n/5)`, que aos 5 jogos o silenciava por completo.

Efeito no caso concreto: Ødegaard de `xmin` 43.7 → **64.3** e de 2.62 → **3.85** pts/jornada; a
sugestão desapareceu. O Ngumoha fica nos 3.96 enquanto o Liverpool não jogar, o que é o que a
informação disponível permite dizer.

**A parte que a correção não resolve** (resposta ao "ou só devia esperar pelo fim da jornada?"):
com a jornada a meio, quem já jogou tem literalmente mais um jogo de informação do que os outros
— aqui, 2 equipas em 20. Isso deixou de ser um precipício, mas continua a ser desigual. Em vez de
o esconder, `avisoJornadaACorrer()` põe uma faixa no topo das Sugestões a dizer quantas equipas
já jogaram e que as comparações só ficam equilibradas no fim da jornada. Vale nos dois modos.

Nota: as **frases** deixaram de citar a pré-época passados 3 jogos (`citaPreEpoca`) — o modelo
continua a usá-la com peso residual, mas "começou no banco no último ensaio" em dezembro seria
absurdo.

## O "cartaz" das trocas apanhado na mesma revisão (2026-08-22)

`p.total_points` do bootstrap **passa a contar a época a decorrer** assim que ela arranca, e as
trocas continuavam a chamar-lhe "pontos na época passada": a sugestão dizia que o Ødegaard "fez
11 pontos na época passada". Pior do que a frase, era o **critério** — o desempate das trocas
por cartaz comparava totais de uma jornada em vez de épocas inteiras. `pontosEpocaPassada()`
lê o `historico` congelado (Ødegaard 74, Muñoz 136). Serve para o desempate, para o texto da
proposta, para a linha da tabela na análise de trocas e para o detalhe por jogador.

## Separadores por modo e Mercado (2026-08-22)

- **Conferências** passou a ser **só do Draft** (`data-modo="draft"`), a pedido do utilizador.
- **Mercado** mostra coisas diferentes conforme o modo:
  - *Draft*: movimentos da liga **agrupados por jornada** (`movimentosPorJornada`), da mais
    recente para a mais antiga, mais as notícias de transferências do Sky.
  - *Clássica*: **a liga jornada a jornada** (`desenharMercadoClassica`) — pontos de cada
    equipa, o que ficou no banco, transferências com a penalização, e chips usados. Vem do
    `/entry/{id}/history/` de cada participante, recolhido em `fetch_liga()`.
  - As **notícias de transferências ficam só no Draft**.
- O feed do Sky **não vem ordenado** (uma "Transfer Centre LIVE" de anteontem aparecia antes de
  negócios fechados no próprio dia): `fetch_noticias_mercado` passa a ordenar por data
  decrescente.
- Nomes dos chips traduzidos num sítio só (`nomeChip`), partilhado entre as sugestões e o
  mercado.

## Equipa do utilizador na clássica

`FPL_ENTRY_ID=2420779` ("Bazukas Team") está fixado no `atualizar.cmd`. O id encontra-se
clicando no nome da própria equipa na tabela de uma liga (o URL passa a `/entry/ID/event/N`),
ou em `/api/me/` com sessão iniciada — a página "My Team" não o mostra.

## Versão publicada, para usar fora de casa (2026-08-26, pedido do utilizador)

O dashboard é servido pelo `servir.py` e só se vê na rede local — com o PC ligado. Para o ter
fora de casa, `scripts/artefacto.py` junta tudo num **ficheiro HTML único** (CSS, JS e os dois
`data.json` embutidos, 1.8 MB) que é publicado como Artifact e abre em qualquer lado, **mesmo
com o PC desligado**.

- O `app.js` usa `window.__DADOS__` quando existe e cai no `fetch` de `data/*.json` quando não —
  a mesma base de código serve os dois casos, sem ramo separado.
- O `<head>` é fornecido por quem publica, por isso o ficheiro sai só com o conteúdo do `<body>`
  (mais o `<title>`). O `body` já pinta `background: var(--fundo)`, o que satisfaz o requisito
  de um artifact de tema único.
- `json_seguro()` escapa `</` e `<!--` dentro do JSON: o conteúdo vem de notícias que não
  controlo, e um `</script>` no meio de uma string partia a página inteira. Há teste.
- **É um retrato**, não é ao vivo: só muda quando se volta a publicar (`scripts/artefacto.py` e
  republicar no mesmo URL). A tabela da jornada ao vivo fica congelada no momento da publicação,
  que é a limitação que mais se nota.
- Alternativa para dados ao vivo fora de casa: uma VPN privada (Tailscale) até ao PC. Abrir
  portas no router está fora de questão — o `servir.py` não tem autenticação nenhuma.

## Historial de lesões: medido e rejeitado (2026-09-01)

Página indicada pelo utilizador:
`transfermarkt.pt/<jogador>/verletzungen/spieler/<id>` — tabela com Época · Lesão · de · até ·
Dias · Jogos perdidos. Atacava a lacuna que eu próprio apontei como a maior: **o modelo não
distingue "faltou por lesão" de "não era titular"**.

O caso é real. O Ødegaard perdeu **30 jogos em 7 lesões** em 25/26; as 16 titularidades dele em
38 são explicadas por lesão, não por ser jogador de plantel. (Cuidado na comparação: o
Transfermarkt conta todas as competições, a FPL só as 38 da liga.)

**Recolha**: os ids saem dos planteis (`/<clube>/startseite/verein/<id>`) — 20 pedidos dão ~6000
jogadores; 246 dos meus cruzaram sem ambiguidade, 91 ficaram ambíguos. Deu **623 pares
época→seguinte** com historial.

**A tensão que só os dados resolvem**: saber que faltou por lesão sugere que rende mais quando
apto, mas sete lesões numa época sugerem que volta a faltar. Medição fora da amostra, 300
divisões:

| Previsor dos minutos da época seguinte | MAE | Ganho |
|---|---|---|
| **minutos da época passada (o atual)** | **682** | — |
| + dias de lesão (linear) | 689 | −1.0% |
| minutos por dia disponível | 724 | −6.1% |
| + marca de "época perdida" (90+ dias) | 686 | **+0.1%**, ganha em 187/300 |

**Nada compensa.** O coeficiente linear dos dias é negativo (−0.47 min por dia lesionado): quem
se lesionou joga *menos* a seguir, não mais.

**A armadilha que quase me enganou**: por faixas, quem perdeu 90+ dias passa de 1024 para 1534
minutos — **+48%**, o que parece confirmar a intuição em cheio. Mas quando se põe a marca no
modelo o ganho é 0.1%. Os 48% eram **regressão à média**: minutos baixos já codificam "esteve
lesionado", e a regressão sobre os minutos já prevê a recuperação. A lesão explícita não
acrescenta informação — só a repete.

Contexto para calibrar: o MAE é de ~680 minutos numa época. **Prever minutos é intrinsecamente
ruidoso**, e nenhuma destas variantes muda isso.

Fica **não integrado**. Nota: o historial continua a ter valor *informativo* para o ecrã ("perdeu
30 jogos por lesão na época passada") — o que não tem é valor preditivo, e por isso não entra no
modelo.

## Recolha para a Fase 5: emparelhamentos e estado clínico (2026-09-01)

Ao perguntar "que dados faltam para a Fase 5", a resposta foi que **a maior parte não é esperar
por dados novos — é começar a guardar o que já passa à frente e se deita fora**. Duas adições,
ambas só recolha: **o modelo não lhes toca**.

### Emparelhamentos e resultado por jornada (`jornadas[ev].jogos`)

`[[casa, fora, golos_casa, golos_fora], …]` só dos jogos já realizados. Já se lia o
`/event/{ev}/live → fixtures` para saber que equipas jogaram e deitava-se o resto fora.

Destranca duas coisas hoje impossíveis: o **bónus como lugar no top-3 daquele jogo** (o BPS já
era guardado, faltava saber quem estava no mesmo jogo — e o bónus é um lugar, não uma taxa) e a
**baliza a zero por equipa**, que é o mesmo acontecimento para todos os defesas do clube, o que
permite medir a correlação entre eles.

**É recuperável no passado**, por isso o guarda da cache passa a exigi-lo e as jornadas antigas
foram refeitas.

### Estado clínico por jornada (`jornadas[ev].estados`)

`{id: [status, chance, news_added]}`, e **só de quem não está simplesmente apto** — quem não
aparece estava disponível, e isso poupa nove décimos das linhas. 138 jogadores na GW2.

Serve a maior lacuna do modelo: hoje ele **não distingue "faltou por lesão" de "não era
titular"** (o caso Ødegaard/Scott). Com isto, a pergunta deixa de ser um padrão a inferir de
meia época de ausências e passa a ser um facto registado. O `news_added` fica guardado de
propósito: a recolha corre dias depois do jogo, e sem a data da marcação não se saberia se a
lesão é anterior ou posterior à jornada.

**Ao contrário dos emparelhamentos, não é recuperável**: refazer uma jornada antiga gravaria o
estado de *hoje* numa semana em que ele era outro. Foi o que aconteceu à primeira tentativa —
o guarda novo obrigou a refazer a GW1 e ela apanhou os 138 lesionados de hoje como se fossem os
dela. Corrigido: **só se grava para a jornada a decorrer**, e as anteriores ficam sem ele.
A GW1 fica sem estado clínico para sempre, e é o correto.

Detalhe da interação com a cache: uma jornada que seja a atual **e** já esteja finalizada era
curto-circuitada antes de chegar a gravar o estado. Passa a ser repedida enquanto não o tiver.

**Quando é que a Fase 5 começa a poder ser medida**: lesão contra rotação, ~5 jornadas
(portanto GW7); rotação europeia, 3 a 4 jornadas a seguir a jogos europeus (GW4, 7 e 8 são as
primeiras — finais de outubro); bónus por lugar, assim que houver jornadas suficientes.

## zerozero.pt: mapeado e validado, **por ligar** (2026-09-01)

Fonte indicada pelo utilizador para a lacuna da **rotação por competição europeia**. Recolhido e
validado, mas **deliberadamente não ligado ao modelo** — ver "o que falta" no fim.

`robots.txt` só bloqueia `zzmap_v3.php`. O mapa dos 20 clubes está em `scripts/zerozero.json`.

**A época certa é `epoca_id=156`** (2026/27). A 155 é 2025/26 e tem outros promovidos —
comparei os planteis e três clubes desta liga (Coventry, Hull, Ipswich) não existem lá.

**Validação semântica, não "a página respondeu"**: para cada slug contei quantos jogadores do
plantel desse clube (segundo a FPL) aparecem na página, e exigi ser o clube mais representado
com folga. 20/20, pior caso o Fulham com 18 contra 3.

Três armadilhas, todas do mesmo feitio das que já apanhei noutras fontes:

- **Slugs que redirecionam em silêncio.** `/equipa/brentford` devolve **200** e 266 KB — mas é a
  lista geral de equipas. A forma canónica leva id: `/equipa/brentford/2600`, `sunderland/91`,
  `aston-villa/76`, `hull-city/5096`, `coventry-city/2584`.
- **Palavras banais a casar clubes errados.** "Coventry **City**" com "Manchester **City**". A
  lista de exclusão tem de levar *city*, *united*, *town*, *albion*.
- **`PE` é "Pré-Época"**, não uma prova europeia. Contá-la teria triplicado a lista de clubes
  em competições europeias.

**Quem joga na Europa em 2026/27**: Champions League — Arsenal, Aston Villa, Liverpool, Man City,
Man Utd; Conference League (qualificação) — Brighton; Supertaça Europeia — Aston Villa. Seis dos
vinte. *Não aparece Europa League em clube nenhum*, o que é invulgar e não consegui confirmar.

**O calendário parseia limpo** (`/edicao/<prova>/<id>/calendario`: data ISO, hora e os dois
clubes por linha). Cruzado com as jornadas: GW4, GW7 e GW8 têm cinco clubes desta liga a chegar
ao fim de semana com jogo europeu a meio da semana; as outras não têm nenhum.

**O que falta, e porque é que não liguei nada**: tenho *quem* e *quando*, falta *quanto custa em
minutos*. Um treinador roda três jogadores, outro nenhum — aplicar um corte agora seria inventar
um número. É mensurável com o que já guardo (minutos por jogador e por jornada): quando houver
jornadas suficientes a seguir a jogos europeus, mede-se a diferença real por clube. Mesma
disciplina do limiar dos 60 minutos, que medi e concluí não compensar.

Limitações da recolha em si: só apanhei 14 jogos até 21 de outubro (a página de calendário não
traz a fase de liga toda — é preciso paginar), e só a Champions.

## Fase 2 das melhorias: medir as constantes (2026-09-01)

Fase de **medição**, não de alteração — o resultado podia perfeitamente ser "fica como está", e
para metade foi. Base: `history_past` de 387 jogadores (épocas completas desde 2008/09),
`componentesPP90()` reimplementado em Python, validação repetida em 200 divisões metade/metade.

### `PESO_ESPERADO`: 0.5 → **0.7**

A constante mais influente do modelo e a única grande que nunca tinha sido medida.

| peso | MAE | ganho sobre dar a média a todos |
|---|---|---|
| 0.0 (só realizado) | 0.725 | 20.7% |
| **0.5** (o antigo) | 0.682 | 25.4% |
| **0.7** | **0.672** | **25.9%** |
| 0.8 | 0.673 | 26.4% |
| 1.0 (só esperado) | 0.688 | 24.2% |

O ótimo é um planalto entre 0.7 e 0.8, e o 0.5 fica 1.5% pior. Não é ruído: na comparação
**emparelhada** (mesmo conjunto de teste), 0.8 ganha ao 0.5 em **190 de 200 divisões**. Por
posição o modelo esperado ganha em defesas, médios e avançados (os guarda-redes têm 3 pares, não
dá para dizer). Num subconjunto limpo — só pares em que a contribuição defensiva já existia — dá
o mesmo. Ficou em **0.7**, o extremo conservador: guarda 30% para o que o modelo não vê.

Efeito real: 465 jogadores mexem, 0.284 pts/90 de variação média. Os maiores movimentos são de
quem tem poucos minutos, onde a taxa de pontos realizada é ruidosa — é a direção pretendida.

### `MIN_PRIOR`: fica em **900**, e agora está provado

Medido **na forma que o código usa** — encolher para a época anterior *do próprio jogador*, não
para a média da população:

| estatística | k ótimo | ganho sobre k=900 |
|---|---|---|
| xG | 900 | 0.0% |
| xA | 900 | 0.0% |
| xGC | 1300 | 0.1% |
| bónus | 1800 | 0.4% |
| pontos totais | 1800 | 0.2% |

Nada justifica mexer. A hipótese de que "o xG estabiliza mais depressa e precisa de menos
encolhimento" **não se confirma** quando o prior é o próprio jogador.

### Um resultado que era um artefacto, e como o apanhei

A primeira medição (encolhimento para a **média da população**) dava a contribuição defensiva
com k ótimo de 0/90 e ganhos de 8–18%. Parecia uma descoberta: "a contribuição defensiva é um
papel e não precisa de encolhimento".

**Era falso.** O que me fez desconfiar foi a correlação entre épocas: 0.38 entre t e t+1, mas
**0.00** entre t-1 e t. Duas amostras consecutivas não se comportam assim. Verifiquei: o campo
`defensive_contribution` **só existe a partir de 2024/25** — antes é zero para toda a gente. O
"prior" dos meus trios era uma época em que o dado não existia, e encolher para zeros destrói
qualquer estimativa. Os 17.9% mediam isso.

Conclusão honesta: **o encolhimento da contribuição defensiva não é mensurável hoje**. Só haverá
trios válidos quando a época 2026/27 fechar.

## Fase 1 das melhorias: regras do jogo que faltavam (2026-09-01)

Primeira fase do plano faseado. Duas correções de facto, sem afinação nenhuma — e **nenhuma
muda um número hoje**, que é o resultado esperado: não há jornadas duplas nem em branco na
janela atual (GW3–7) e ninguém tem mais de 2 amarelos. O valor é passarem a estar certas quando
acontecerem.

### Jornadas duplas e em branco no calendário

O `fatorCalendario()` fazia a **média sobre a lista de jogos**, e o comentário por cima dizia
que "jornadas duplas contam duas vezes e as em branco puxam para baixo". **Não fazia nem uma
coisa nem outra**: uma dupla entrava como dois valores numa média (peso nenhum a mais) e uma
jornada em branco simplesmente não aparecia na lista. Documentação a descrever comportamento
que não existia.

Agora agrupa **por jornada**: cada uma contribui com a **soma** dos seus jogos, portanto uma
dupla vale perto do dobro e uma em branco vale zero.

**E ao corrigir isto apareceu um segundo erro, mais subtil**: a janela ancorava no *primeiro
jogo do jogador*, não na próxima jornada da liga. Um clube em branco já na jornada seguinte não
era penalizado — a janela dele começava mais tarde e ninguém pagava por isso. Passa a ancorar em
`next_event`.

`jogosNaJanela()` passa a cortar por jornada e não por número de jogos: com uma dupla, três
jornadas são quatro jogos.

Guarda contra falha silenciosa: um jogo sem `event` conta como a sua própria jornada. Sem isso
colapsariam todos num só e o fator disparava — foi o que um teste antigo apanhou, porque passava
jogos sem `event`.

### Suspensão por acumulação de amarelos

Os `yellow_cards` serviam para tirar pontos mas **nunca para disponibilidade**. `riscoSuspensao()`
corta os minutos esperados pela probabilidade de apanhar o cartão que suspende, e só conta quem
está **a um cartão** do patamar (5 ou 10): com dois ou mais em falta a probabilidade cai muito e
exigiria uma conta em dois passos que não se justifica. Teto de 50%, porque com poucos minutos a
taxa dispara e deixa de ser credível.

Limite assumido: não modelo a data a partir da qual o patamar dos 5 deixa de contar — a API não
a dá.

## Agentes (`.claude/agents/`, 2026-09-01)

Cinco, escolhidos pelo que correu mal neste projeto e não por uma lista genérica. Todos têm o
contexto embutido, para não terem de reler as mil linhas deste ficheiro.

| Agente | Para quê |
|---|---|
| **`verificador`** | Caça **falhas silenciosas** depois de uma recolha. É o de maior retorno: quase todos os bugs reais aqui pareciam funcionar (etiqueta desconhecida a devolver o feed geral, funções JS com o mesmo nome, tabela lida pela posição). |
| **`sondador-de-fontes`** | Avalia uma fonte nova: permissão primeiro, depois o que devolve, depois **quanto acrescenta em números**. Aconteceu três vezes numa sessão. |
| **`medidor`** | Testa uma hipótese do modelo contra dados. Existe para **contrariar intuições** — já o fez duas vezes (o BPS, e o win-win nas trocas que eu próprio tinha escrito no plano). |
| **`revisor-modelo`** | Lacunas no back-end, cada uma com medição. Foi assim que apareceu a contribuição defensiva, o maior buraco que o modelo teve. |
| **`revisor-interface`** | Front-end. **Os erros de interface aqui nunca foram visuais** — foram texto a contradizer os números ao lado ("rende 4.9, abaixo da alternativa" com 4.4 ao lado; "recebe mais do que dá" com 9.9 contra 9.9). |

**Duas regras em todos**: toda a conclusão traz prova (medição ou caso concreto que falha), e
lê-se primeiro a secção "Decidido, e porquê não" — senão cada revisão volta a propor o service
worker e o BPS.

**O que não é agente, de propósito**: a rotina antes do commit (dois conjuntos de testes, duas
recolhas, consola, os dois modos) é determinística e já é script; e tudo o que um teste consegue
afirmar deve ser teste — o `testa_nomes_funcoes` apanha a colisão de nomes em 50 ms, para
sempre, sem arrancar do zero.

## Decidido, e porquê não (consolidado)

As decisões contra alguma coisa estavam espalhadas por mil linhas, e a consequência era
previsível: cada revisão nova voltava a propô-las. Ficam aqui juntas. **Antes de sugerir
qualquer uma destas, é preciso trazer prova nova** — dados que contradigam a medição original,
não uma intuição.

### Fontes postas de lado

| Fonte | Porquê |
|---|---|
| **SofaScore** | 403 a pedidos automáticos, e o próprio robots.txt di-lo. |
| **FlashScore** | Os termos proíbem extração de dados. |
| **Google** (pesquisa) | Os termos proíbem pedidos automáticos e o robots.txt bloqueia `/search`. |
| **TheSportsDB** | Tem os amigáveis mas **não a constituição das equipas** (confirmado em 8 clubes); 30 pedidos/min; não conhece o Nott'm Forest. |
| **Fantasy Football Scout, para transferências** | É um site de *fantasy*: "transfers" ali são trocas de FPL e mudanças de preço. Os artigos de mercado real no sitemap são de 2008-2010. *(Continua a ser usado para team news, onde é bom.)* |
| **BBC** | O feed de transferências tem 1 item; o de rumores, 1 valor em 24. |
| **Corpo dos artigos da PL** | Vem **sempre vazio**, na listagem e no artigo individual. |
| **`api.php` da Wikipedia** | O robots.txt bloqueia `/w/` e `/api/`. Usa-se `/wiki/<artigo>`, que é permitido. |

### Ideias de modelo medidas e rejeitadas

| Ideia | Medição |
|---|---|
| **BPS para prever o bónus** | 0.8% de ganho sobre dar a média a todos, contra 7.3% do bónus realizado; **misturar piora**. 575 pares época→época. |
| **Modelar o limiar dos 60 minutos** | 0.048 pts/jornada de erro em 267 jogadores, **nenhum** acima de 0.25. `xmin` já é `P(joga) × minutos`, por isso o escalonamento linear está certo. |
| **Janela de calendário de 3 jornadas** | 10% de amplitude inverte diferenças de qualidade; 10 jornadas matam o sinal (2.4%). Ficaram **5 com decaimento**. |
| **Heurística para as trocas 3-por-3** | Desnecessária: 119 130 combinações em ~200 ms. O exaustivo chega. |
| **Tabela de pontuação escrita à mão** | Deu **dois erros de facto** (golo de GR a 6 em vez de 10; castigo por golos sofridos em falta). Lê-se de `settings.scoring`. |

*Nota sobre o win-win nas trocas*: medi zero em 119 130 combinações e escrevi que era estrutural.
Dias depois, com os planteis mudados, passou a disparar. A conclusão certa é "é raro", não
"é impossível" — o ramo `ambos` fica no código.

### Infraestrutura

- **GitHub Pages e Actions**: removidos. O utilizador quer o projeto só para si, a correr
  localmente; o repo no GitHub é backup.
- **Service worker**: tentado, não registava. Exige contexto seguro, e no telemóvel o acesso é
  por IP em HTTP simples. Ficou de fora em vez de código morto.
- **Abrir portas no router**: fora de questão — o `servir.py` não tem autenticação nenhuma. Para
  acesso de fora: Artifact (retrato) ou VPN privada.

### Interface

- **Separador "Equipa"**: removido por duplicação — o plantel está em "Equipas" e os livres nas
  Sugestões.
- **Secção visível da pré-época**: removida a pedido; continua a alimentar o modelo.
- **Coluna própria para "quem falta jogar"**: os nomes ficam por baixo do nome da equipa, porque
  numa coluna desapareciam em ecrã estreito.

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
  - **Sem secção própria no site** (removida a pedido do utilizador em 2026-08-21), tal como os
    distintivos "XI pré-época"/"banco pré-época" nas tabelas: fica só como entrada do modelo.
    As justificações das sugestões continuam a citá-la ("foi titular no último ensaio"), porque
    aí é a razão da recomendação e não um mostruário. De qualquer forma deixa de contar sozinha
    assim que houver jornadas disputadas (`jogosObs === 0`), altura em que as menções somem.
  - `sem_acentos` passou a traduzir letras que o NFD não decompõe (ø, đ, ł, ß, æ…), senão
    "Ødegaard" nunca casaria com "Odegaard".
