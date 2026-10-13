---
name: precisao-modelo
description: Mede a precisão do modelo de projeção do dashboard de FPL (backtest das jornadas já jogadas, contra previsores ingénuos) e propõe ajustes só quando os dados os sustentam. Usar no fim de cada jornada, ou quando o utilizador pergunta pela precisão do modelo, se é preciso afinar o modelo, ou porque é que as projeções falharam.
---

# Precisão do modelo

Verifica se o modelo de projeção (`site/app.js`, função `projecao`) precisa de ajustes, com
números. **O resultado normal é "não mexer"**: os pontos da FPL são muito ruidosos, e a maior
parte dos desvios de uma jornada é ruído. Só se ajusta o que sai do ruído e melhora a
decisão.

O projeto fica em `C:\Users\Gentil\Desktop\Projetos\Claude\fpl`. Lê primeiro a secção
**"Decidido, e porquê não"** do `CLAUDE.md`. Uma ideia que lá esteja só volta com dados que
contradigam a medição original.

## 1. Há alguma coisa nova para avaliar?

- Lê `site/data/data.json`: `game.current_event` e `game.current_event_finished`, e o
  `generated_at`.
- Lê o fim de `docs/precisao-registo.md`, para saber até que jornada já foi avaliado.
- **Jornada nova acabada e dados de antes do fim dela**: corre a recolha, que é a mesma do
  `atualizar.cmd`, sem o servidor. Em PowerShell:

  ```
  $env:LEAGUE_ID="12258"; $env:FPL_ENTRY_ID="2420779"; $env:FPL_LEAGUE_ID="779399"
  py scripts\fetch_data.py; py scripts\fetch_classica.py; py scripts\fetch_calendario.py
  ```

  Os ficheiros de `site/data/` são dados e não se fazem commits deles.
- **A última jornada acabada já está no registo**: diz "nada de novo desde a JN" e pára.

## 2. Correr o backtest

```
node scripts/precisao.mjs
node scripts/precisao.mjs --modo classica
```

O script corre o modelo "no passado". Para cada jornada usa só o que se sabia antes dela e
compara com os pontos reais. Leva meio segundo. O cabeçalho explica a reconstrução e as
aproximações.

## 3. Ler o relatório sem cair nas armadilhas que já apanhámos

- **Secção 1, contra os ingénuos.** O modelo tem de ganhar em **RMSE e na ordenação (ρ)**. No
  erro médio absoluto (MAE) pode perder para a "mistura" sem ser defeito: o MAE premia quem
  prevê a mediana, e os pontos têm uma cauda longa.
- **Secção 5, o onze.** É a métrica que mais conta, porque mede quantos pontos fez o onze
  escolhido por cada previsor. Um ajuste que melhore o erro e piore o onze não entra.
- **Secção 8, a vigiar.** São os desvios cujo IC95 não inclui o zero, com N≥30. **Só estes
  são candidatos a ajuste.** Um viés grande com N pequeno (por exemplo, a faixa 5+ pts com 28
  casos) é ruído até prova em contrário.
- **O conjunto avaliado não pode depender da previsão nem do futuro.** "Com dono hoje" dava
  +0.45 pts de viés falso, porque os gestores apanham quem marcou. O script já usa um conjunto
  limpo (60+ min antes da jornada, ou 900+ na época passada); não o mudes para "os meus".

## 4. Para cada sinal: diagnosticar, ajustar o mínimo, medir antes e depois

1. **Separar minutos de valor por 90** (secção 4). A maior parte dos defeitos reais deste
   modelo foram de minutos, não de valor.
2. **Procurar a causa em casos concretos.** Exporta as linhas com
   `--json <scratchpad>/linhas.json` e olha para os jogadores com mais erro. Exemplos de
   causas já encontradas:
   - guarda-redes com minutos intermédios que não existem em campo;
   - estreantes na clássica com uma referência errada, por falta de draft rank;
   - um ruído de interface a fazer-se passar por sinal.
3. **Implementar o ajuste mais pequeno que ataca a causa**, com um comentário que diz o que
   foi medido, como os outros ajustes do `app.js`.
4. **Medir antes e depois sobre os mesmos dados:**
   ```
   git show HEAD:site/app.js > <scratchpad>/app_antes.js
   node scripts/precisao.mjs --app <scratchpad>/app_antes.js
   node scripts/precisao.mjs
   ```
   Aceita só se o sinal desaparecer ou encolher, o RMSE e o ρ não piorarem, e o onze não
   piorar. Vê também o outro modo (`--modo classica`): o motor é o mesmo.
5. **Se nada sair do ruído, não mexas.** Diz quais os desvios a vigiar na próxima vez.

## 5. Testes e registo

- `py scripts\testes.py` e `site/testes.html` no browser. Para o browser, serve uma **cópia**
  do site no scratchpad com `py scripts\servir.py PORTA`. Nunca escrevas por cima de
  `site/data/`: o `CLAUDE.md` regista dois incidentes de dados destruídos assim.
- Acrescenta um bloco a `docs/precisao-registo.md` com:
  - a data e as jornadas avaliadas;
  - o modelo contra a mistura: MAE, RMSE e ρ;
  - o onze: modelo, melhor ingénuo e oráculo;
  - os sinais;
  - a decisão (ajuste feito, ou "sem ajustes").
- Se houve ajuste, acrescenta uma secção ao `CLAUDE.md`, com as medições. Se uma ideia foi
  medida e rejeitada, acrescenta-a à tabela "Decidido, e porquê não".

## 6. Commit, e o que nunca fazer sozinho

- Trabalha num ramo novo (`claude/precisao-jN`), com commit do código, do registo e do
  `CLAUDE.md`. Os dados de `site/data/` ficam fora do commit.
- **Nunca fundir em `main` nem fazer push sem o utilizador aprovar.** Numa execução agendada
  (sem ninguém a ver), pára no commit no ramo e deixa um resumo curto, em português: a
  precisão desta jornada, os sinais, e o ajuste proposto com os números de antes e depois, ou
  "sem ajustes".
