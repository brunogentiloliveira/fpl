# Tarefa agendada: precisão do modelo

A tarefa vive na aplicação do Claude de cada computador, e não vem com o `git clone`. Este ficheiro
guarda o que é preciso para a criar de novo. Basta pedir ao Claude, nesta pasta: "recria a tarefa
agendada a partir de docs/tarefa-agendada.md".

| Campo | Valor |
|---|---|
| Identificador | `fpl-precisao-modelo` |
| Título | FPL — precisão do modelo depois de cada jornada |
| Descrição | Backtest do modelo de projeção do dashboard FPL no fim de cada jornada: regista a precisão e os sinais, e deixa os ajustes para decidir com o utilizador |
| Horário | `0 10 * * 2,5` (terças e sextas às 10:00, hora local) |

**Antes de a criar**, confirma o caminho da pasta do projeto no texto abaixo (segunda linha): no
computador novo pode ser outro.

**Na primeira execução**, carrega em "Run now" com a aplicação aberta e aprova as permissões que
aparecerem. As regras estão em `.claude/settings.json`, e a skill manda escrever os comandos tal e
qual lá estão. Se mesmo assim parar num pedido, é porque um comando saiu escrito de outra maneira.

## Texto da tarefa

```text
Verificação da precisão do modelo de projeção do dashboard de FPL "Haaland of Fame", depois de cada jornada.

O projeto é o repositório git em C:\Users\Gentil\Desktop\Projetos\Claude\fpl. Trabalha sempre a partir dessa pasta.

Esta é uma execução agendada, sem ninguém a ver. Lê o ficheiro .claude/skills/precisao-modelo/SKILL.md desse projeto (é a skill "precisao-modelo") e segue à risca a secção "Execução agendada (sem ninguém a ver)". Os pontos que não podem falhar:

1. Só correm sem autorização os comandos dessa secção, escritos exatamente como lá estão: um por chamada, sem cd, sem ; nem && nem |, sem redirecionamentos, com / nos caminhos. Os ficheiros leem-se com a ferramenta Read, não com a shell. Um comando fora dessa lista não se tenta: ficaria à espera de uma autorização que ninguém vai dar.
2. Corre sempre a recolha (`py scripts/recolher.py`) antes do backtest.
3. Se a última jornada avaliada por `node scripts/precisao.mjs` já estiver em docs/precisao-registo.md, responde só "Nada de novo desde a jornada N" e termina.
4. Não mexas no modelo (site/app.js) nem corras os testes. Se a secção 8 ("A vigiar") do relatório trouxer um sinal, regista-o e deixa o diagnóstico e o ajuste para uma sessão com o utilizador.
5. Acrescenta o resultado a docs/precisao-registo.md e faz commit desse ficheiro e dos dados de site/data num ramo novo `claude/precisao-jN`. Os dados entram porque o estado clínico de cada jornada só existe neles. NUNCA fundas em main nem faças push: isso fica para o utilizador aprovar.
6. Termina com um resumo curto em português de Portugal:
   - a precisão desta verificação (MAE, ordenação ρ e o onze do modelo contra o melhor previsor ingénuo e o oráculo);
   - os sinais encontrados;
   - o que fica por decidir com o utilizador, ou "sem sinais novos".

O utilizador usa o dashboard no computador, não no telemóvel.
```
