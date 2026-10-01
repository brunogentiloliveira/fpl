# Design brief — Haaland of Fame

**Este briefing não propõe uma identidade nova.** Descreve a que o projeto já tem, escrita no
cabeçalho do `site/styles.css` e espalhada pelo `CLAUDE.md`, para o crítico ter contra o que
julgar. A skill é explícita: num repositório com sistema de design, novidade é defeito e
consistência é o objetivo.

## Tese estética

A **folha de equipa de um scout**, não um dashboard de operações. Fundo escuro com tom de relva
ao fim da tarde — deliberadamente não o azul frio de ecrã que quase todos os dashboards usam.
Uma única linguagem de cor repetida em toda a aplicação, com significado fixo: **verde
disponível, dourado a vigiar, coral fora**. O onze sugerido é desenhado como relvado a sério
(faixas cortadas, círculo central, linha de meio-campo) e é **o único momento decorativo do
projeto** — porque é o único sítio que já é, de facto, uma folha de equipa.

## Objetivo emocional

Abrir e, em três segundos, saber **o que exige ação hoje**. A ferramenta de quem tem 10 minutos
antes do deadline, não de quem quer admirar gráficos.

## Anti-objetivos

- **Não é um dashboard de operações.** Nada de azul frio, cartões iguais em grelha, ou números
  grandes sem decisão por trás.
- **Nada de fontes externas.** O projeto corre 100% local e publica-se como ficheiro único
  offline; importar uma fonte seria a primeira dependência de rede a quebrar essa promessa.
- **Nada decorativo fora do relvado.** Sem gradientes de enfeite, sem glows, sem manchas de
  fundo. O relvado é a exceção, e é exceção porque é literal.
- **A cor nunca é decoração.** Verde, dourado e coral têm significado fixo. Usar coral porque
  "fica bem" estraga a leitura em toda a app.
- **Nada que esconda um número atrás de uma animação.** Mobile-first a 375px, sem scroll
  horizontal no `body`, `prefers-reduced-motion` respeitado.
- **Nenhum texto a contradizer o número ao lado.** É o erro que este projeto comete mais
  (está documentado três vezes no `CLAUDE.md`) e o que mais lhe custa.

## Estrutura

Cabeçalho fino → faixa de avisos → ticker de notícias → 10 separadores → painel. O esqueleto por
omissão que seria de recusar: barra fixa, herói centrado, três cartões de features. Nada disso
existe aqui, e não deve passar a existir — isto é uma ferramenta densa, não uma página de
apresentação.

## Cor

`--fundo #12171a` · `--painel #1b2420` · `--painel-2 #232f28` · `--borda #2c362f`
`--texto #f4f1e8` · `--texto-2 #99a397`
**Acentos com significado**: `--acento #3ecf82` (relva/disponível) · `--aviso #e8b23f` (ouro do
Hall of Fame/a vigiar) · `--perigo #ef6b57` (coral/fora) · `--foco #6fb8ff` (só o anel de foco,
fora da paleta de propósito para se destacar).

## Tipografia

Só a pilha do sistema (`system-ui`), por decisão documentada. A personalidade tem de vir de
**peso, tracking e escala**, não de uma fonte comprada. Hoje os títulos de secção usam
maiúsculas pequenas com tracking largo.

## Textura e material

Superfície lisa. O único material é o relvado do onze. Sombra única (`--sombra`), dois raios
(`--raio 10px`, `--raio-lg 14px`).

## Movimento

Quase nenhum, de propósito. O ticker desliza; tudo o resto é estático. `prefers-reduced-motion`
corta o ticker. Não há nada a animar à entrada.

## O risco assumido

O **relvado**. Num projeto que recusa decoração em todo o lado, desenhar um campo de futebol a
sério é a decisão que um designer cauteloso cortaria. Fica porque é a única peça do ecrã que é
literalmente aquilo que representa.

## Referências — o nível a atingir

Não há imagens de referência; o nível é definido pelo próprio sistema. O crítico julga:
1. O relvado cumpre a promessa do cabeçalho do CSS ("faixas cortadas, círculo central, linha de
   meio-campo")?
2. A linguagem de cor é legível e consistente, ou há cor sem significado?
3. A densidade serve a decisão em 3 segundos, ou enterra-a?

---
Sem seed: a fase Discover **não foi corrida**, por decisão da própria skill.
