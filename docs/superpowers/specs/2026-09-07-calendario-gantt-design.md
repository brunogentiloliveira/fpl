# Separador "Calendário": todos os jogos das equipas da PL numa linha do tempo

Data: 2026-09-07
Revisto a 2026-09-07 depois de três revisões automáticas (fonte, recolha, interface). As
correcções estão marcadas com **[rev]** e cada uma traz a medição que a obrigou.

## Contexto

O dashboard só conhece jogos da Premier League, e mesmo esses cortados nos 10 seguintes
(`fetch_fixtures`, `scripts/fetch_data.py:1145`). Os jogos europeus e de taça não existem em
fonte nenhuma que o projeto recolha hoje.

Pedido do utilizador: um separador com **todos os jogos a realizar pelas equipas da liga
inglesa**, incluindo competições europeias e taças, em diagrama de Gantt.

As duas decisões que tem de servir, escolhidas pelo utilizador:

1. **Congestão e rotação** — que clubes chegam à jornada com jogo a meio da semana.
2. **Dificuldade do percurso** — quem tem uma sequência fácil ou dura nas próximas semanas.

## O que este separador NÃO faz

**Não mexe no modelo.** Decidido com o utilizador. Sei *quem* joga na Europa e *quando*, mas não
*quanto custa em minutos*. Aplicar um corte agora seria inventar um número.

O calendário vive num **ficheiro próprio**; nem o `data.json` nem o `classica.json` são tocados,
e o `fixtures` que alimenta as projeções continua cortado nos 10 jogos.

**[rev] O isolamento foi verificado, não assumido.** Do lado da recolha: `fetch_data.py` abre só
`data.json`, `preepoca.json` e `bolaparada.json`; não há `glob`/`listdir`/`os.walk` em `scripts/`.
Do lado do browser: `D.fixtures` tem exactamente 3 consumidores (`jogosNaJanela` em app.js:958,
a amplitude em 983, `jornadasEspeciais` em 2386) e o `D` nunca é fundido depois do arranque.
O módulo novo é só de leitura e nunca escreve em `D` — fica dito no topo do ficheiro, porque o
precedente de mutação em memória existe (`aplicarPlantelManual`, app.js:2073).

## Fontes

| O quê | Onde | Pedidos |
|---|---|---|
| Premier League | `fantasy.premierleague.com/api/fixtures/` | 1 |
| Europa, taças, supertaças | zerozero `/equipa/<slug>/jogos?epoca_id=<N>&page=<P>` | **29** |

**[rev] São 29 pedidos, não 40.** Só 9 dos 20 clubes têm segunda página; os outros 11 devolvem
0 linhas nela. A recolha pára quando uma página devolve menos de 40 linhas.

**A PL vem da API oficial** — é a única das duas com `team_h_difficulty`/`team_a_difficulty`.
Um pedido dá 380 jogos, todos com `kickoff_time` (0 nulos, 0 `provisional_start_time`).

Sondagem dos 20 clubes em 2026-09-07 — 865 linhas, das quais 789 por realizar:

```
760  Premier League          38 x 20
 40  UEFA Champions League   Arsenal, Aston Villa, Liverpool, Man City, Man Utd
 30  Carabao Cup
 24  UEFA Europa League      Bournemouth, Sunderland, Crystal Palace
  6  UEFA Conference League  Brighton (fase de liga)
  2  UEFA Conference League (Qual.)
  2  The FA Community Shield 2026    (ja jogado)
  1  UEFA Super Cup 2026             (ja jogado)
```

Zero jogos de sub-21, femininos, amigáveis ou play-offs. **89 jogos não-PL por realizar.**

**Correcção ao CLAUDE.md.** Diz *"não aparece Europa League em clube nenhum"* e conta *"seis dos
vinte"* em provas europeias. São **nove**, a Liga Europa tem três, e o Brighton está na **fase de
liga** da Conference (6 jogos) e não só na qualificação. A nota antiga veio de se ter lido os
distintivos da página do clube, que listavam "PE" (pré-época). Corrige-se neste trabalho.

### [rev] A tabela está por ordem DECRESCENTE — a página 2 tem os jogos mais próximos

Era o erro mais grave da versão anterior, que dizia que sem a página 2 "se perderiam jogos
distantes". É ao contrário. Medido no Man City:

```
pagina 1: 40 linhas, de 2027-05-30 a 2026-10-11
pagina 2:  8 linhas, de 2026-09-20 a 2026-08-16   <- 4 por realizar
```

**34 jogos por realizar existem só na página 2, e os 34 são dos 9 clubes europeus.** Para o Man
City são a UCL no Porto (08/09), a PL no Man Utd (13/09), a Carabao com o Norwich (17/09) e a PL
com o Sunderland (20/09). Falhar a página 2 apaga a congestão das próximas duas semanas e deixa
uma linha que começa a 11 de outubro — perfeitamente plausível, e cega precisamente para a
decisão que o separador serve.

### [rev] Fuso: o zerozero publica hora local, a API publica UTC

Nas 38 linhas da PL do Man City: **16 diferem 60 minutos, 22 diferem 0**, e a separação bate a
100% com o horário de verão britânico. Dos 89 jogos não-PL por realizar, **45 caem no período
+1h e 44 no de 0h** — escrever `data + "T" + hora + "Z"` fica errado em 51% e certo em 49%.

`ZoneInfo("Europe/Lisbon")` **rebenta nesta máquina** (`ZoneInfoNotFoundError`, Python 3.12 do
python.org sem `tzdata`) — verificado. A solução não precisa de tzdata e é auto-verificável: as
**760 linhas da PL dão o par (hora local, UTC) para o mesmo jogo**, portanto o desvio de cada
data é *medido* a partir dos dados e aplicado aos jogos não-PL da mesma semana. Se uma data não
tiver âncora, o jogo fica com a hora local e uma marca de `hora_incerta`.

### [rev] A validação é por DATA, nunca por data-hora

Corolário do ponto anterior: comparar data-hora rejeitaria 155 dos 380 jogos, e a regra de
recusa deitaria fora os 20 clubes.

### [rev] Chave de junção: o slug, não o nome

**6 dos 20 nomes não batem**, verificado contra `teams` do `data.json`:

```
'Brighton & Hove Albion' vs 'Brighton'      'Manchester United' vs 'Man Utd'
'Leeds United'           vs 'Leeds'         'Nottingham Forest' vs "Nott'm Forest"
'Manchester City'        vs 'Man City'      'Tottenham'         vs 'Spurs'
```

São 214 das 789 linhas (27%). Nas linhas da PL isso só afecta a validação; nas de taça afecta o
produto: **4 dos 12 jogos não-PL entre clubes da PL ficavam com `adv = null`**, e a eliminatória
Liverpool–Spurs de 15/09 ligava de um lado e não do outro. E a verificação "aparece nos dois
clubes" estava construída em cima do mesmo emparelhador, por isso passava em vazio.

Um recurso por tokens é pior: *city* liga "Manchester City" a Hull City e Coventry City — a
armadilha que o CLAUDE.md já documenta.

**A chave certa está no HTML**, em 865/865 linhas: a célula do adversário é
`<a href="/equipa/<slug>">`, e os 20 slugs observados são **exactamente** os 20 de
`scripts/zerozero.json` (igualdade de conjuntos). Junta-se por slug.

Guarda-se também o **id do jogo** (`<tr id="12624704">`, 865/865) — é a única chave estável entre
recolhas, e é o que permite detectar uma **remarcação**, que por `(data, adversário)` seria
indistinguível de um jogo novo.

### [rev] A época lê-se da página, não se escreve à mão

Com `epoca_id=156` fixo, em 2027/28 a recolha devolve as 760 linhas de 2026/27: a verificação
dos 38 por clube **passa**, a janela de datas **passa**, e o ficheiro sai com 0 jogos por
realizar e um ✓ no diagnóstico. Separador em branco, tudo verde.

A página traz a resposta: `<select id="epoca_id">` com `<option value="156" selected>2026/2027`.
Lê-se de lá, e confirma-se contra o ano do primeiro `deadline_time`.

Pela mesma razão, *"nenhuma data fora de 2026-07-01 … 2027-07-01"* é uma **afirmação que recusa**,
não um filtro que descarta linhas: com `epoca_id=155` as linhas de maio de 2026 caem dentro da
janela e sobreviveriam a um filtro.

### [rev] Estrutura real das linhas

A descrição anterior ("10 células, começa e acaba em h2h") só vale para jogos por realizar da PL.
Três desvios medidos:

- **célula 0** é `V`/`E`/`D` nos jogos já disputados (76 linhas), não `h2h`;
- **célula 3** (`(C)`/`(F)`) vem **vazia** em campo neutro — o Aston Villa–PSG da Supertaça. Um
  `r[3] == "(C)"` transformava isso em "fora" sem avisar;
- **célula 9** vem vazia em 106 das 865, e **30 delas são jogos por jogar** — outra vez, os mais
  próximos.

A assinatura de classes tem só 2 variantes, e é por aí que se filtra (mais `len == 10`), não pela
posição nem pelo texto. Contagens de células na página: 10 (865), 13 (75, classificação), 1 (27)
— **sem rowspan**, ao contrário da Wikipedia.

`html.unescape` é obrigatório e só **depois** de tirar a marcação: a página usa entidades
nomeadas (`&ccedil;`, `&nbsp;`, `&amp;`).

### [rev] Cobertura: a fonte só garante a PL, e as rondas por sortear são a maior lacuna

A própria página avisa: *"Competições completas no zerozero.pt: Premier League 2026/27, The FA
Community Shield 2026. Quanto às restantes edições, zerozero.pt não pode garantir…"*.

Medido: os 9 clubes europeus têm **exactamente 8 jogos** (a fase de liga), a acabar em 27/01/2027;
a Carabao pára na 3.ª eliminatória (17/09). **A partir de fevereiro o calendário é quase só PL** —
e o Gantt mostraria o Man City com a primavera limpa, que é o contrário da verdade.

Dentro da janela longa já morde hoje: a **4.ª eliminatória da Carabao (fim de outubro)** e os
quartos (dezembro) caem lá dentro e não estão sorteados. A partir de 18/09 a janela mostrará
"taça = 0" para os 20 clubes, numa prova onde 16 continuam vivos.

**Isto é requisito de ecrã, não de código**: onde há ronda marcada e não sorteada, e o clube ainda
está na prova, aparece uma marca **"por sortear"** com a data do sorteio. Sem ela o separador
afirma "não joga" quando o que sabe é "não sei". Também precisa de chave própria para a Taça de
Inglaterra, senão cai em "Outras" — e o rótulo varia com o patrocinador
("The Emirates FA Cup 25/26"), por isso a normalização é por subcadeia.

### [rev] As horas de novembro em diante são marcadores de posição

Distribuição de `kickoff_time` na API: outubro 38 jogos com **10 horas distintas**; novembro 32
jogos com **3** (30 às 15:00); abril 30 jogos com **1** (todos às 14:00). A PL confirma as
escolhas televisivas com ~5-6 semanas de antecedência e `provisional_start_time` está a `false`
em 380/380 — **não há bandeira que o distinga**. O separador di-lo por escrito para lá de ~6
semanas, em vez de fingir precisão que não tem.

## Validação

Cruzam-se as linhas da PL do zerozero com os 380 jogos da API, **por data, adversário (slug) e
casa/fora**. Hoje batem **760/760**.

**[rev] Recusa por linha, não por clube.** A versão anterior recusava o clube inteiro à primeira
divergência — e como 700 das 760 linhas ainda vão mexer com as escolhas televisivas, uma única
remarcação derrubava o clube e com ele os jogos europeus, que são a única coisa que a fonte
acrescenta. Recusa-se a linha; só se escala para o clube acima de **2 divergências**, ou de
qualquer divergência dentro das próximas 6 semanas.

**[rev] Um clube recusado nunca aparece como linha vazia.** Uma linha em branco lê-se como "clube
tranquilo, não joga a meio da semana" — a falha viraria resposta. A linha fica marcada
**"sem dados"** com o motivo, e há aviso no topo do separador.

Verificações de contagem: 20 clubes, 38 linhas de PL cada; cada jogo não-PL entre dois clubes da
PL aparece nos dois; nenhuma data fora da época.

## Recolha: `scripts/fetch_calendario.py`

Módulo próprio, stdlib, que importa os utilitários de `fetch_data.py` (padrão do
`fetch_classica.py`). Escreve `site/data/calendario.json` e nada mais. Chamado pelo
`atualizar.cmd` a seguir às duas recolhas. Falha tolerada por clube.

**[rev]** A dificuldade sai por `fetch_classica.fetch_fixtures` (scripts/fetch_classica.py:98),
que já escolhe `team_h_difficulty`/`team_a_difficulty` conforme o lado. Reescrever isso é uma
inversão de polaridade silenciosa e plausível, que trocaria "percurso fácil" por "duro".

## Formato de `site/data/calendario.json`

```json
{
  "generated_at": "2026-09-07T10:00:00Z",
  "epoca_id": 156,
  "clubes": {
    "15": {
      "nome": "Man City", "curto": "MCI",
      "jogos": [
        {"id": 12624704, "data": "2026-10-11T15:30:00Z", "comp": "PL",
         "adv": 14, "adv_nome": "Liverpool", "adv_slug": "liverpool",
         "casa": false, "dif": 4, "jornada": 6, "ronda": null, "jogado": false},
        {"id": 12624711, "data": "2026-10-14T19:00:00Z", "comp": "UCL",
         "adv": null, "adv_nome": "PSG", "adv_slug": "paris-saint-germain",
         "casa": true, "dif": null, "jornada": null, "ronda": "", "jogado": false}
      ]
    }
  },
  "competicoes": {"PL": "Premier League", "UCL": "Champions League", "UEL": "Liga Europa",
                  "UECL": "Conference League", "LC": "Taça da Liga", "FAC": "Taça de Inglaterra",
                  "SUP": "Supertaças", "OUT": "Outras"},
  "recusados": {},
  "diagnostico": [["Calendario zerozero", true, "20 clubes, 89 jogos por realizar fora da PL"]]
}
```

**[rev] Correcções ao exemplo anterior**: os ids estavam errados (11 é **Hull City**, 12 é
**Ipswich Town**; Man City é **15**, Liverpool **14**), e a dificuldade do Man City fora com o
Liverpool é **4**, não 5. Confirmado que os **20 ids são idênticos nos dois modos** — é o que
torna legítimo um `calendario.json` único partilhado.

**[rev] Guardam-se também os jogos já disputados.** A versão anterior guardava "só por realizar",
o que apagava exactamente o que a medição futura da rotação europeia precisa: para medir a GW4
são precisos os jogos de 08-10/09. São **76 linhas em 865 (~8 KB)**, e como o ficheiro só encolhe
ao longo da época, guardar tudo nunca custa mais do que custa hoje. Havia ainda incoerência
interna: a validação conta 38 linhas de PL por clube, que só existem se as jogadas forem
parseadas — eram parseadas e deitadas fora. `jogado` distingue-as.

**[rev] Campos acrescentados**: `id` (chave estável entre recolhas, detecta remarcações),
`adv_slug` (chave de junção correcta), `ronda` (`'3R'`, `'F'`, `''` na fase de liga — rodar antes
de uma eliminatória e antes de um jogo de grupos não é a mesma coisa).

Tamanho medido com os 865 jogos reais: **~98 KB** compacto.

## Interface: separador "Calendário"

Nos dois modos.

### [rev] A janela ancora-se em jornadas, não em semanas

Medido nos 350 jogos por realizar: há uma paragem de **20 dias** entre 20/09 e 10/10, outra de 14
em novembro e uma de 21 entre 20/03 e 10/04. Uma janela de 4 semanas escolhida hoje tem **2 jogos
da PL por clube**; 8 semanas tem 5-6; 16 semanas tem 14. Medir em semanas dá um número de jogos
que varia enormemente com a altura do ano.

Seletor **próximas 6 jornadas / 12 jornadas / resto da época**, guardado em `localStorage`
(`calHorizonte`). O eixo continua em datas reais, e a paragem para selecções aparece como o vazio
que é — com uma frase a dizê-lo, senão parece avaria.

**[rev]** O rótulo diz "Horizonte" e não "Janela", para não colidir com o seletor de janela das
Sugestões, que é em jornadas mas significa outra coisa (`localStorage: janela`, app.js:754).

### [rev] Duas ordenações explícitas, em vez de duas frases

A versão anterior punha por baixo do gráfico duas leituras em texto. **Podiam contradizer o
gráfico e a tabela de projeções**: o Brighton seria anunciado como "percurso mais duro" (média 3.5)
enquanto a coluna Calend. lhe dá **+2%**, o melhor bónus de calendário da liga — a média ignora o
decaimento e as jornadas em branco, e as polaridades estão invertidas (3.5 alto = mau, +2% = bom).
É o padrão do "rende 4.9, abaixo da alternativa" com 4.4 ao lado.

E as duas frases também discordavam entre si: "quem joga a meio da semana" olha para 4 dias antes
de um jogo, a barra olha para todo o horizonte. A 21/11 o texto diria "nenhum clube joga a meio da
semana" com **9 das 20 linhas sombreadas três dias depois**.

Substituem-se por **duas colunas fixas ao lado do nome do clube**, por que se pode ordenar:

| coluna | o que é | serve |
|---|---|---|
| **Apertado** | dias dentro de um troço de 3 jogos em 8 dias | decisão 1 |
| **Dificuldade** | média dos adversários da PL no horizonte, com o nº de jogos | decisão 2 |

A ordenação passa a ser a resposta, e o número que ordena está à vista — o inverso do problema
habitual. A coluna Dificuldade leva a escala ("3.1 em 5, 1 fácil") e, à semelhança do
`amplitudeCalendario()` que já existe (app.js:982), uma linha por baixo com a amplitude real, a
dizer que serve para afinar entre clubes parecidos e não para inverter diferenças grandes.

**[rev] A barra deixa de ser booleana.** Medida sobre o calendário real, a regra 3-em-8 dispara
para **14 dos 20 clubes** e cobre **49% da linha** do Arsenal e do Man City — metade da linha
sombreada não é um aviso, é um fundo, e o conjunto de clubes com barra é o mesmo conjunto que já
tem losangos. Passa a **intensidade** (3, 4, 5+ jogos por 8 dias), troços de intensidade diferente
não se fundem, e o número de dias apertados é a coluna que ordena. A janela dos 8 dias é
**inclusiva** (`≤ 8`): Arsenal joga 24/10, Carabao 28/10 e PL 1/11 — exactamente 8 dias, e é a
semana em que o utilizador vai olhar.

**[rev] A folga é em dias, não binária.** Man Utd recebe o Sabah a 10/09 e joga a PL a 13/09 (3
dias); Man City joga no Porto a 08/09 e joga a PL a 13/09 (5 dias). É o mesmo jogo — Man
Utd–Man City — e um corte aos 4 dias nomeava um e omitia o outro. Mostra-se a folga e o
casa/fora, que custa o mesmo e não mente.

### [rev] Por omissão, só os meus clubes

Dos 20, **9 jogam na Europa**; dos meus 11 clubes hoje, **6 não jogam** e a linha deles é uma fila
de marcadores semanais sempre igual. O projeto já filtra por "meus" em Conferências, Próximos
jogos e Utilização. Interruptor para ver os 20.

**[rev] O ★ não serve como marca**: `owner != null` dá **18 de 20 clubes** no Draft, e mesmo feito
bem (`p.owner === eu.entry_id`) dá 11 de 20 — mais de metade das linhas destacadas. Mostra-se o
**número de jogadores meus por clube**, que também ordena.

**[rev]** O separador tem de ser redesenhado a partir de `desenharClassica()` e não só do `main()`:
`aplicarPlantelManual()` reescreve o `owner` em memória, e senão ficaria com o plantel da jornada
passada — a armadilha já documentada no CLAUDE.md para o `initClassica()`.

### [rev] Geometria: 42px por semana, fixos, e lista abaixo de 40rem

A 375px: `main` tem `padding: 1rem` → 343px; rótulo ~56px; sobram **287px**. Com posicionamento
por percentagem, a 16 semanas dá **2.6px/dia** e dois jogos a 3 dias de distância ficam a 7.7px —
sobrepostos. O intervalo de 3 dias é o normal (PL sábado → UCL terça).

`px/semana = 7 × largura_do_marcador ÷ intervalo_mínimo_em_dias`. Com marcador de 12px e
intervalo de 2 dias dá **42px/semana**; com o dígito da dificuldade lá dentro (~16px), 56px.

Larguras resultantes a 42px/semana: 6 jornadas ≈ 300px (cabe), 12 jornadas ≈ 590px, resto da época
muito mais. **Fixa-se px/semana** (não percentagem) e o gráfico arrasta dentro do próprio
contentor (`overflow-x: auto`), nunca o `body`.

**Abaixo de 40rem, mostra-se a lista por clube em vez da linha do tempo** — é o padrão que o
projeto já usa (a tabela de transferências esconde `.col-noticia`, e o CLAUDE.md regista que o
scroll horizontal foi medido e recusado: "438 contra 375").

Dois avisos: `position: sticky` morre dentro de um antepassado com `overflow: hidden`, por isso o
gráfico **não vai dentro de `.cartao`**; e o anel de foco global (`outline: 3px` + `offset: 2px`,
styles.css:44) acrescenta 10px à volta do marcador, que a 42px/semana desenha por cima do vizinho.

### [rev] Os marcadores levam texto, não são manchas de cor

Contraste medido das classes existentes contra `--painel`: `.fx.d1/.d2` **1.51:1**, `.fx.d3`
**1.14:1**, `.fx.d4/.d5` **1.29:1**. O mínimo para um objecto gráfico não-textual é **3:1** —
**nenhuma passa**. As `.fx` só funcionam hoje porque **têm sempre texto lá dentro** (o nome do
adversário, ou "dif. 4"). Como manchas nuas seriam invisíveis, e a `d3` é 45% dos jogos.

Além disso, o vocabulário de cor do projeto está declarado no topo do `styles.css` — *verde
disponível, dourado a vigiar, coral fora* — e uma cor por competição colide com ele: um losango
dourado da Taça lê-se como "a vigiar".

Portanto: **dígito da dificuldade dentro do marcador da PL** (`3`, `4`), **letra da competição
dentro do europeu** (`C`, `E`, `L`), forma diferente (PL retângulo cheio, resto losango
contornado), contorno em vez de preenchimento, e casa/fora por sinal e não por tom.
**[rev]** A dificuldade **1 nunca ocorre** nos 380 jogos (casa ∈ {2,3,4}, fora ∈ {2,3,4,5}) — a
legenda não anuncia um valor que não existe.

### [rev] `title` não chega

Em ecrã tátil o `title` **nunca aparece**, e num `<span>` não é anunciado de forma fiável por
leitor de ecrã. Fazer 200 marcadores `<button>` daria 200 paragens de tabulação. A saída é o
detalhe **por baixo da linha ao clicar**, e a lista em ecrã estreito.

### [rev] Estados vazios e falhas

- **`calendario.json` em falta**: `main()` (app.js:3733) tem **um** `try` e o `catch` faz `return`
  depois de escrever "Não foi possível carregar os dados". Um segundo `fetch` lá dentro **mata o
  dashboard inteiro** por causa de um ficheiro que serve um separador. Tem de ser `try` próprio,
  e o separador diz "corre o `atualizar.cmd`".
- **Diagnóstico**: `initDiagnostico()` (app.js:1710) lê só `D.diagnostico` e `D.generated_at`. Um
  diagnóstico dentro do `calendario.json` nunca chegaria ao rodapé, e o banner de dados velhos não
  olharia para o `generated_at` do calendário — se a recolha falhasse três semanas, o separador
  mostrava um calendário plausível sem um único ✗. Ambos passam a incluí-lo.
- **[rev] Filtragem por `Date.now()` no cliente**, não só na recolha: o `artefacto.py` é um
  retrato, e um artefacto publicado hoje e aberto em novembro mostraria outubro como futuro, com
  barras de congestão no passado.
- **Paragem para selecções**: a 21/09 uma janela curta tem 19 dos 28 dias sem um jogo da PL. Diz-se
  por escrito.
- **Clássica sem `FPL_ENTRY_ID`**: ninguém tem `owner`; o separador cai nos 20 clubes em vez de
  mostrar uma lista vazia.
- **Legenda construída a partir do que está na janela**, senão mostra chaves de cor sem marcador.

## Bugs existentes que este trabalho corrige de caminho

Dois, ambos verificados, ambos agravados por um décimo separador:

- **[app.js:1046]** o `title` da coluna "Calend." está dentro de uma string de aspas duplas com
  `' + janelaAtual() + '` lá dentro: o utilizador lê *"das próximas ' + janelaAtual() + '
  jornadas"*. É o tooltip que explica o número que este separador vai mostrar ao lado.
- **[app.js:3709]** `initTabs()` recolhe os 9 `[role="tab"]` sem filtrar os escondidos (3 são só do
  Draft). Em modo clássico, seta para a direita a partir de "Liga" abre o painel Conferências.

## Testes

`scripts/testes.py`, contra HTML guardado em `scripts/testes_dados/`:

- as duas assinaturas de classes; linhas de 13 e 1 células ignoradas;
- **a ordem decrescente e a paragem na página com < 40 linhas**;
- célula 0 `V/E/D` = jogado; **célula 3 vazia = campo neutro**, não "fora";
- **conversão de fuso a partir das âncoras da PL**, com um caso de verão e um de inverno;
- entidades HTML (`&nbsp;`, `&ccedil;`) desescapadas depois de tirar a marcação;
- junção por **slug** e não por nome — com os 6 nomes que não batem como casos;
- normalização por subcadeia: "The Emirates FA Cup 25/26" → `FAC`, "Community Shield 2025" → `SUP`;
- a época lida do `<select selected>`, e recusa quando não bate com o `deadline_time`;
- a validação **recusa a linha** e só escala para o clube acima do limiar;
- todos os caminhos de `zerozero.json` chegam ao clube certo.

`site/testes.html`:

- o horizonte corta por jornada e o cliente filtra por `Date.now()`;
- congestão: 3 jogos em 8 dias marca, **exactamente 8 dias marca** (inclusivo), 3 em 12 não;
- troços de intensidade diferente não se fundem;
- a ordenação por "apertado" separa Man City de Sunderland com o mesmo número de jogos;
- clube recusado aparece "sem dados" e nunca como linha vazia;
- a legenda só mostra competições presentes na janela.

**[rev]** `testa_nomes_funcoes` (scripts/testes.py:208) apanha `^function` duplicado mas **não**
`const`/`let` de topo duplicado, que é `SyntaxError` e apaga a página inteira. Alarga-se, já que
se vai acrescentar nomes num ficheiro com `calendario`, `fatorCalendario`, `explicarCalendario`,
`amplitudeCalendario`, `janelaAtual` e um id de DOM `janela`.

**[rev]** `artefacto.py` ganha slot próprio `window.__CALENDARIO__` — meter no dicionário `dados`
faria o script anunciar *"modos: calendario, classica, draft"* e tornaria `D = __DADOS__[modo]`
ambíguo.

## Fora de âmbito

- Ligar a congestão ao modelo (só depois de medida).
- Resultados e classificações; jogos de sub-21, femininos ou amigáveis.
- **Levar os jogos não-PL para dentro de "Próximos jogos"** (app.js:1121). É provavelmente a
  integração de maior valor — é aí que a decisão de escalação se toma — mas é uma alteração a uma
  funcionalidade existente que o utilizador não pediu. Fica registada como seguimento.
