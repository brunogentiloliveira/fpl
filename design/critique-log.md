# Registo das rondas de crítica

## Ronda 1 — 2026-10-01 — **4.5 / 10**

Crítico: contexto fresco, só as 4 capturas (Sugestões e Jogadores e Calendário a 1280px,
Sugestões a 390px) mais a intenção declarada. Sem código, sem diffs, sem explicações.

### Verificado por medição própria antes de aceitar

| Achado | Verificação | Veredicto |
|---|---|---|
| O fundo é o azul frio que a tese recusa | `--fundo #12171a` = **matiz 203°**; `--painel` 153°, `--painel-2` 145°, `--borda` 138° | **Procede.** O comentário do CSS diz "não o azul frio de ecrã"; o fundo é azul frio, e é a maior área do ecrã |
| Não há segundo plano | `--painel` vs `--fundo` = **1.13:1** (o crítico leu 1.21 do JPEG; o token é pior) | **Procede** |
| O rótulo da formação contradiz o desenho | A 390px o onze desenha 1-4-1-4-1; o rótulo diz 5-4-1 | **Procede.** É a família de defeito que o CLAUDE.md regista três vezes |
| O campo não tem proporção de campo | 3.61:1 no desktop, 1.17:1 no telemóvel (real: 1.54:1) | **Procede** |
| Legenda do Calendário sem amostras | Confirmado na captura: frase corrida, seis categorias, zero amostras de cor ou forma | **Procede** — defeito meu, introduzido no trabalho do Calendário |
| Glifos cortados no topo | Confirmado na captura dos Jogadores | **Procede** |

### Aceite sem medição independente (plausível, custo de verificar > custo de corrigir)

- Verde com cinco funções sem relação (relógio, PTS/J, distintivos de valor, separador ativo)
- A tabela de Jogadores põe o histórico mais brilhante do que a projeção
- O sublinhado do separador ativo é mais largo do que a palavra
- A caixa dourada do Calendário gasta a cor "a vigiar" num aviso permanente

### Rejeitado

Nada ainda. O crítico respeitou a instrução de não pedir mais espaço em branco nem menos números.

### O que ele diz que vale mais do que tudo o resto

> "Uma decisão move isto mais do que qualquer outra: tornar o campo brilhante o suficiente para
> se ver, e pôr verde/dourado/coral nos onze cartões. Isso converte o herói de papel de parede
> na resposta à pergunta que o produto existe para fazer."

## Ronda 2 — 2026-10-01 — **4.5 / 10** (sem movimento, mas com defeitos novos)

O número não mexeu; os defeitos mudaram por completo. Os da ronda 1 estavam corrigidos e o
crítico atacou terreno que nunca tinha tocado. Pela regra da skill isso não é planalto (há
categorias novas), mas também não é convergência — por isso **paro aqui e escalo**.

### Aceite e corrigido

| Achado | O que se fez |
|---|---|
| "A aresta verde nos onze cartões carrega zero bits" — está sempre toda a gente apta | **Silêncio por omissão.** Apto não leva marca; só dourado e coral aparecem. Um ecrã sem problemas fica calmo e uma excepção é impossível de não ver |
| Não há escala tipográfica: tudo entre 7px e 12px de altura de maiúscula | O total do onze passa de cinzento a reboque (≈12px) para **38.4px, peso 800, algarismos tabulares** — a coisa maior do ecrã. Só peso, tamanho e tracking, sem fonte nenhuma |
| O sombreado da congestão media 1.28–1.41:1 e os três níveis ficavam em 0.13 de rácio | Subidos para 22/36/38% — separam-se e passam o chão de visibilidade |

### Rejeitado, com razão

- **Campo em retrato 0.68:1** — num ecrã de 5 linhas empurraria tudo o resto para baixo. Ficou
  em 2.4:1, que já não é a caixa de correio de 3.95:1 que era.
- **Marcadores a 70% de opacidade para a relva se ver através** — custaria a legibilidade dos
  números, que é o que o cartão existe para dar.
- **Tirar o código do clube do cartão** — é como se sabe contra quem joga.

### Por resolver, e é estrutural

O **eixo do Calendário**. O crítico mediu o que eu não tinha medido: 84 dias em 544px dá 6.5px
por dia, e um marcador tem 19px ≈ 3 dias. Dois jogos na mesma semana **não cabem sem se
sobrepor** — e esse par é exactamente o padrão que o separador existe para mostrar. A correcção
não é visual: é trocar o eixo contínuo por uma coluna fixa por jornada. É trabalho de outra
ordem e fica para decisão do utilizador.

## Entre a ronda 2 e a 3 — 2026-10-02: o que ficou registado, feito

Pedido do utilizador: fazer o que ficou registado aqui. Sem crítico pelo meio. Cada item foi
medido no ecrã antes e depois.

| Registado | O que se fez |
|---|---|
| **O eixo do Calendário** (o estrutural) | Uma **coluna por jornada**, numa `<table>` a sério. Cada célula leva os jogos com que o clube chega a essa jornada. Os jogos fora da liga vão para a jornada *seguinte* a eles (um jogo europeu de terça pesa em quem joga no sábado), e os da PL vão para a sua jornada (o `event` da FPL já trata dos adiamentos). O marcador da PL leva o **adversário** e não o algarismo. A paragem para as seleções passa a ser uma coluna estreita, em vez de uma frase dentro de uma caixa. A 1280px cabem 12 jornadas sem scroll. |
| Letras das provas (F = Conference) | Duas letras: CH, LE, CO, TL, TI, ST. |
| Caixa dourada de ressalvas no topo do Calendário | Passou a texto corrido no fim. O dourado quer dizer "a vigiar", e uma ressalva que está lá sempre não é coisa a vigiar. A frase da paragem saiu, porque a grelha já a mostra. |
| A dificuldade a ser pintada de duas maneiras (a 4 dourada no Calendário e coral nas projeções) | Uma escala só. Verde para fácil e coral para difícil, a 5 em coral **cheio** (estava igual à 4), e **nunca dourado**. O neutro (a 3) ficou só com contorno, porque o texto estava a 3.97:1, abaixo do mínimo. |
| Verde com cinco funções sem relação | O separador ativo, o rótulo por cima do título, o modo premido e a projeção na tabela passaram a creme. Os valores de transferência, os cargos de bola parada e os lugares na tabela passaram a um distintivo neutro (`.estado.info`). O verde fica para disponível e para entra/ganho. |
| Tabela de Jogadores com o histórico mais brilhante do que a projeção | O "Pts" passou a "Total", que recua para cinzento, e a projeção fica em creme a 800. |
| Traço do separador ativo mais largo do que a palavra | Agora é desenhado só por baixo do rótulo. |
| Duas gramáticas para o mesmo dado ("LEE · 3.6" e "DEF · 3.6 pts") | Um só miolo (`mioloChip`) no relvado, no banco, nos Próximos jogos, na Liga ao vivo, no planeador do wildcard e no plantel ótimo da clássica. A projeção é o mais forte da linha. |
| Números desalinhados na linha dos defesas | Nome em cima e números em baixo: os números da fila ficam todos na mesma linha de base (medido, 243px em todos). |
| "Branthw/aite" partido a meio, sem hífen | Hífen suave ao meio das palavras com 9+ letras. |
| "dif. 3" em quase todas as linhas | Só aparece quando a dificuldade não é a neutra. |
| A jornada repetida em cada linha dos Próximos jogos | Passou para o cabeçalho do dia. |
| Cartões dos jogos esticados a 914px | Limitados a 36rem. |
| Frase a explicar o óbvio por cima dos Próximos jogos | Removida. |
| Suplentes numa frase corrida, com "·" a dois níveis | Passaram a cartões, que também mostram quem está em dúvida (a frase não mostrava). |
| Caixa de verificação nativa branca | `color-scheme: dark`, que trata dela, das listas e das barras de scroll. |
| Rodapé com o ✗ enterrado na lista de fontes | As fontes que falharam vêm à frente. |

**Dois defeitos meus que isto destapou:**

- **A suite do `testes.html` abortava a meio desde o commit e345d3b.** A legenda lia
  `C.competicoes` sem guarda, um teste chamava-a com `C = null`, e o erro parava o script:
  corriam 179 verificações em vez de 215, e a página dizia que estava tudo bem com as que tinham
  corrido. Os testes da legenda faziam `array.indexOf("texto")`, que procura um elemento igual,
  não um pedaço de texto, e por isso passavam sempre. Corrigidos os dois.
- **49 jogadores com um distintivo "0M"**: transferências confirmadas pela fonte oficial, que não
  publica valores. O distintivo só aparece quando há valor.

## Ronda 3 — 2026-10-02 — **5 / 10** (era 4.5)

### Verificado por medição antes de aceitar

| Achado | Verificação | Veredicto |
|---|---|---|
| Quatro margens esquerdas, e um salto ao mudar de separador | Separadores a 16px, título a 62px, painéis a 185px e Calendário a 145px (1280px). O salto de 40px fui eu que o introduzi ao alargar só o Calendário. | **Procede** |
| O marcador da PL "treme" ao descer uma coluna | O conteúdo estava centrado, e quem tinha jogo europeu antes empurrava-o ~8px | **Procede** |
| Nomes compridos mais pequenos do que os vizinhos no ecrã largo | O `.longo` aplicava-se a todas as larguras, e no largo cabiam | **Procede** |
| O seletor da janela por cima do onze | O onze **não usa** a janela (horizonte 1, CLAUDE.md). O controlo estava por cima da única secção que não governa. | **Procede** |
| O traço de congestão lê-se como uma regra da tabela | Estava colado ao `border-bottom` da linha | **Procede** |
| "APER." sem unidade | São dias | **Procede** |
| "5-4-1" lê-se como unidade dos pontos | Estava por baixo de "PTS NESTA JORNADA", na mesma letra | **Procede** |
| Faixa dourada de dados velhos a dizer o mesmo que "Atualizado" 40px acima | Confirmado | **Procede** |
| Contagem do deadline verde | Verde é "disponível" | **Procede** |
| Barra de scroll dos separadores no telemóvel | Fazia um segundo traço por baixo do separador ativo | **Procede** |
| O relvado tapado em 76% pelos cartões | 9px entre linhas, e o círculo central ficava todo por baixo | **Procede** |

### Feito

Uma só largura (`--largura: 63rem`) e uma só margem esquerda para cabeçalho, separadores e
painéis: **145px em todos**, medido. Os separadores ficaram com a largura do texto. Casas fixas
por célula no Calendário: medido, **uma só posição x por coluna nas 12**. O traço de congestão
fica 3px acima da linha da tabela e engrossa com a intensidade (3, 4 e 5px). Os dias levam
unidade. O `.longo` ficou só abaixo dos 40rem. O seletor da janela desceu para baixo do banco, e
no telemóvel o onze passou a aparecer acima da dobra. A formação ficou à parte do rótulo. Os
dados velhos aparecem como "· há 12 h" a dourado, ao lado da hora, e a faixa fica só para o
deadline já passado. A contagem é neutra, dourada no último dia e coral nas últimas 3 horas. O
ponto do ticker deixou de ser coral. Os títulos de secção passaram a maiúsculas pequenas com
tracking, como o briefing diz que são. O relvado ficou com cantos de campo (3px), mais relva à
vista e alinhado à margem.

### Rejeitado, com razão

- **Relvado em retrato e nomes sobre a relva sem cartão.** Pedido pela terceira vez, rejeitado
  pela terceira vez, pelas razões da ronda 2.
- **Dificuldade numa rampa neutra de luminosidade.** Pedido pela segunda vez. Verde para fácil e
  coral para difícil é a convenção da própria FPL e de todas as tabelas de jogos de fantasy, que
  o utilizador lê sem legenda. Ficou escrito no briefing como **exceção assumida**, e o dourado
  saiu da escala. **É a decisão de gosto que está em aberto para o utilizador**, não para o
  crítico.
- **O total do onze como delta contra o onze atual.** Não há com quê comparar antes do deadline:
  a API só publica as escolhas depois dele (404).
- **Cartões de estado em todos os onze** ("os cartões não têm cor"). É o silêncio por omissão
  decidido na ronda 2: hoje ninguém do onze está em dúvida.
- **Esconder o ticker nas Sugestões, tirar o título da página, ordenar a tabela pelos
  cabeçalhos, linhas de 36px nos Jogadores.** Fora do que estava registado, e cada um mexe em
  comportamento, não só em aspeto.
- **Duas colunas nas Sugestões (relvado | ações).** É a sugestão com mais mérito das que ficaram
  de fora, mas é uma reestruturação do separador, não um acerto. Fica para decisão do utilizador.

## Ronda 4 — 2026-10-02 — **5.5 / 10** (fim do ciclo)

Quarta ronda, que é o limite da skill. A nota subiu meio ponto em cada ronda (4.5, 4.5, 5,
5.5), mas o que falta agora são **pedidos repetidos que contrariam decisões tomadas**, e não
defeitos novos de execução:

- o relvado em retrato ou em meio-campo (quarta vez);
- a dificuldade numa rampa neutra (terceira vez);
- um total do onze com termo de comparação (segunda vez).

Mais rondas não resolvem isto: são decisões de gosto e de âmbito, e quem as toma é o
utilizador.

### Feito depois da ronda (dois defeitos meus de hoje, verificados)

- Os marcadores das provas europeias eram a marca mais forte da grelha (texto creme, 15.7:1),
  acima dos da liga, que levam a dificuldade. Passaram a cinzento, e lêem-se pela forma.
- O rótulo vertical "seleções" estava a ~9px. Subiu para 0.62rem e passou a creme.

### Em aberto, para o utilizador decidir

| Proposta do crítico | Rondas | Porque não se fez sozinho |
|---|---|---|
| Primeiro ecrã como veredicto: até três ordens ("Larga X, pega Y · +0.9/j") ao lado do relvado, na coluna que hoje está vazia | 3, 4 | Reestrutura o separador. É a de maior mérito. |
| O número grande como diferença contra o onze atual | 3, 4 | Antes do deadline a API não publica o onze atual (404) |
| Relvado em meio-campo a 1.30:1, com grande área e faixas ao ritmo das linhas | 2, 3, 4 | Empurra tudo para baixo num ecrã de 5 linhas |
| Dificuldade numa rampa neutra, cor só para o estado | 2, 3, 4 | Verde/coral é a convenção da FPL. Está no briefing como exceção assumida. |
| Ticker estático: três alertas, os meus primeiro, traduzidos | 4 | Muda o comportamento do ticker |
| Menos separadores, com Sugestões primeiro e por omissão | 3, 4 | Muda a navegação |
| Tabela de Jogadores: linhas de 40px, ordenação por Pts/J, dono em cinzento e "Livre" a creme | 3, 4 | Fora do que estava registado |
