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

## 2026-11-10 — estudo dos índices da página do Draft (jornadas 4 a 10)

Pedido do utilizador: ver o que os 6 melhores de cada posição têm em comum nos índices por que a
página ordena, e se isso serve para escolher. **Veredicto: não serve como método à parte, e o
modelo não foi alterado.** O que os melhores partilham são os próprios resultados (balizas a
zero, bónus, BPS, titularidades), e os índices da FPL (Influence, Creativity, Threat, ICT) não
melhoram a ordem que o modelo já dá. O método do perfil, simulado em três cortes, empata com o
modelo (2.96 contra 2.85 pts por jornada nas escolhas entre livres).

### Pistas a vigiar (remedir a cada verificação a partir da jornada 15)

Duas famílias saíram do ruído (16 testes em 106, contra ~5 esperados por acaso), mas nenhuma
melhorou o onze, por isso não entraram no modelo.

| Pista | Medição em 2026-11-10 (além do modelo, entre titulares esperados, IC95 por clube) | Fora da amostra |
|---|---|---|
| **DEF e GR: resultados desta época e multidão da clássica** | DEF balizas a zero +0.155 [+0.04, +0.27]; DEF subida de preço desde a J1 +0.159 [+0.08, +0.24]; GR equipas que o têm +0.28 [+0.11, +0.42] | DEF + balizas a zero: ordem 0.193 para 0.234; onze 48.5 para 48.2 (6 mudados: 2 melhor, 4 pior) |
| **MED: força do adversário esta época** | xG por jogo do adversário −0.144 [−0.21, −0.06] | ordem 0.118 para 0.141; onze 48.5 para 48.4 |

**Regra para entrarem:** o sinal manter-se com mais jornadas, e o onze não piorar. Se entrarem,
o ajuste é dentro do modelo (mais peso a esta época nos defesas e guarda-redes; adversário nos
médios), não um índice à parte.

**Como remedir** (scripts em `scripts/estudo_indices/`, que escrevem só na pasta que se lhes dá):

```
py scripts/estudo_indices/sondar.py <pasta>            # bootstrap do Draft
py scripts/estudo_indices/recolher_live.py <pasta>     # /event/N/live de cada jornada
py scripts/estudo_indices/sondar_classica.py <pasta>   # bootstrap da clássica
py scripts/estudo_indices/recolher_classica.py <pasta> # histórico por jogador (672 pedidos)
node scripts/precisao.mjs --json <trabalho>/linhas.json
py scripts/estudo_indices/parte_b5.py <pasta> <trabalho>   # intervalos por clube e escolha entre livres
py scripts/estudo_indices/parte_b4.py <pasta> <trabalho> "2:clean_sheets"   # fora da amostra e onze
```

`<trabalho>` tem de conter `comum.py` e `feats.py` (ou aponta-se para `scripts/estudo_indices`,
copiando para lá o `linhas.json`). Os scripts assumem 10 jornadas: o `n=10` de `carregar` e de
`construir` tem de subir com a época.

## 2026-11-10 — jornadas 2 a 10 (verificação feita à mão)

Feita à mão porque a tarefa agendada não completou nenhuma verificação desde 13/10: as 7
execuções pararam todas no primeiro comando, à espera de uma permissão que ninguém aprovou.

**Conjunto avaliado**: 3400 jogador-jornada de quem já se sabia que joga.

| Draft | MAE | RMSE | ρ | viés |
|---|---|---|---|---|
| modelo | **1.75** | **2.60** | **0.591** | −0.02 |
| mistura (época passada + esta) | 1.95 | 2.81 | 0.381 | +0.10 |

No onze, o modelo fez **48.2**, contra 45.9 do melhor ingénuo e 54.4 do oráculo.

**Clássica**: MAE 1.76, RMSE 2.59, ρ 0.596, viés −0.06. No onze, 62.9 contra 61.8 do melhor
ingénuo e 73.1 do oráculo.

**Sinal**: projeções de 0 a 1 pts com viés +0.12 ±0.08 (N=829; +0.10 na clássica). São os
suplentes que entram: previsto 0.60, real 0.84, jogam 44% das vezes e ~35 minutos. **Sem
ajustes**: são jogadores projetados abaixo de 1 ponto, que não entram em onzes nem em waivers.

Os três pontos a vigiar de 13/10 (valor por 90 dos GR, projeções de 5+ pts, avançados)
continuam dentro do ruído.
