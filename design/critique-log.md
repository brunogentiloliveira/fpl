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
