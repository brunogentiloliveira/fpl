# Registo da precisão do modelo

Um bloco por verificação, mais recente no fim. Gerado com `scripts/precisao.mjs` (ver a skill
`precisao-modelo`). Erro em pts por jogador e jornada; viés = real − previsto; ρ = ordenação
(Spearman); "onze" = pontos do onze escolhido nos planteis atuais da liga, por jornada.

## 2026-10-13 — jornadas 2 a 6 (primeira verificação)

**Conjunto avaliado**: 1805 jogador-jornada de quem já se sabia que joga.

**Draft** (depois dos ajustes):

| | MAE | RMSE | ρ | viés |
|---|---|---|---|---|
| modelo | **1.77** | **2.65** | **0.597** | 0.00 |
| mistura (época passada + esta) | 2.00 | 2.89 | 0.392 | +0.09 |

No onze, o modelo fez **49.4**, contra 48.1 do melhor ingénuo e 54.9 do oráculo.

**Clássica** (depois dos ajustes): MAE 1.78, RMSE 2.64, ρ 0.600, viés −0.03. No onze, 64.8
contra 61.2 do melhor ingénuo e 71.0 do oráculo (só 5 onzes: o meu plantel).

**Sinais encontrados e ajustes feitos:**

- **Guarda-redes com minutos intermédios.** Os GR previstos com 30-60 min jogaram 1 vez em 59
  (previsão 1.89, real 0.03). A regra nova é que o GR do último jogo do clube joga, e acerta
  97.8% de 365 casos. Em todos os jogadores, o erro passou de 1.22 para 1.16 e o ρ de 0.692
  para 0.720.
- **Estreantes na clássica sem draft rank**, com referência dos titulares estabelecidos (+1 pt
  por 90). Passou a usar-se o preço. O viés passou de −0.13 para −0.03 e as projeções de 2-3
  pts de −0.38 ±0.24 para −0.12.

**A vigiar na próxima verificação** (hoje ainda dentro do ruído):

- O valor por 90 dos GR está 10% acima do real (−0.39 ±0.58).
- As projeções de 5+ pts saem 0.88 acima do real, mas são só 28 casos (±1.82).
- Os avançados estão 0.21 abaixo (±0.41).
