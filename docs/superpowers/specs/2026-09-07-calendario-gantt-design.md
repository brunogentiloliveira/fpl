# Separador "Calendário": todos os jogos das equipas da PL numa linha do tempo

Data: 2026-09-07

## Contexto

O dashboard só conhece jogos da Premier League, e mesmo esses cortados nos 10 seguintes
(`fetch_fixtures`, `scripts/fetch_data.py:1145`) — o que chega para a janela de projeção mas não
para ver o que aí vem. Os jogos europeus e de taça não existem em fonte nenhuma que o projeto
recolha hoje.

O pedido do utilizador: um separador com **todos os jogos a realizar pelas equipas da liga
inglesa**, incluindo competições europeias e taças, em diagrama de Gantt.

As duas decisões que o separador tem de servir, escolhidas pelo utilizador:

1. **Congestão e rotação** — que clubes chegam à jornada com jogo a meio da semana. É o sinal de
   que o treinador vai poupar gente, e é a lacuna que ficou por fechar quando o zerozero foi
   mapeado em 2026-09-01.
2. **Dificuldade do percurso** — quem tem uma sequência fácil ou dura nas próximas semanas.

## O que este separador NÃO faz

**Não mexe no modelo.** Decidido explicitamente com o utilizador. Tenho *quem* joga na Europa e
*quando*, mas não *quanto custa em minutos* — um treinador roda três jogadores, outro nenhum.
Aplicar um corte agora seria inventar um número, e este projeto tem duas medições (o BPS, o
limiar dos 60 minutos) que existem precisamente por se ter medido em vez de assumido.

Consequência de desenho: o calendário vive num **ficheiro próprio**, e nem o `data.json` nem o
`classica.json` são tocados. O `fixtures` que alimenta as projeções continua cortado nos 10
jogos. Não há caminho por onde isto possa piorar uma projeção sem alguém dar por isso.

Quando houver jornadas suficientes a seguir a jogos europeus (GW4, 7 e 8 são as primeiras),
mede-se o efeito real por clube com os minutos que já se guardam em `jornadas[ev].stats`. Aí
liga-se, com um número medido.

## Fontes

| O quê | Onde | Pedidos |
|---|---|---|
| Premier League | `fantasy.premierleague.com/api/fixtures/` | 1 |
| Europa, taças, supertaças | zerozero `/equipa/<slug>/jogos?epoca_id=156&page=N` | 40 (20 clubes x 2 páginas) |

**A PL vem da API oficial** porque é a única das duas que traz `team_h_difficulty` /
`team_a_difficulty` (1-5) — sem isso não há "dificuldade do percurso". Um pedido dá os 380 jogos
da época com `kickoff_time`.

**O resto vem do zerozero.** O `robots.txt` só bloqueia `zzmap_v3.php`. A tabela de
`/equipa/<slug>/jogos` tem 10 células por linha: `h2h · data ISO · hora · (C)/(F) · _ ·
adversário · resultado · competição · ronda · h2h`. Guarda-se tudo o que **não** for
"Premier League".

Sondagem completa dos 20 clubes em 2026-09-07 (760 linhas de PL + 105 de outras provas):

```
760  Premier League          38 x 20 - bate certo, logo a paginacao apanhou tudo
 40  UEFA Champions League   Arsenal, Aston Villa, Liverpool, Man City, Man Utd
 30  Carabao Cup
 24  UEFA Europa League      Bournemouth, Sunderland, Crystal Palace
  6  UEFA Conference League  Brighton
  2  UEFA Conference League (Qual.)
  2  The FA Community Shield 2026    (ja jogado)
  1  UEFA Super Cup 2026             (ja jogado)
```

**Correção de facto que esta sondagem obrigou.** O CLAUDE.md diz *"não aparece Europa League em
clube nenhum, o que é invulgar e não consegui confirmar"* e conta *"seis dos vinte"* clubes em
competições europeias. Está errado: são **nove**, e a Liga Europa tem três. A nota de setembro
veio de se ter lido a lista de competições da *página do clube*, que nessa altura ainda listava
"PE" (pré-época) em vez da prova europeia. A tabela de jogos diz a verdade; os distintivos da
página do clube não diziam. A linha do CLAUDE.md é corrigida como parte deste trabalho.

**A Taça de Inglaterra não existe ainda**, e isso não é falha da fonte: os clubes da PL entram na
3.ª eliminatória, sorteada em dezembro. Aparece sozinha quando for sorteada, sem alteração de
código — a recolha guarda o que lá estiver.

### Duas armadilhas conhecidas, que a recolha tem de tratar

**Paginação.** A tabela dá **40 linhas por página**. Um clube europeu tem 47-48 jogos, portanto
sem a página 2 ficariam 33 jogos da PL em vez de 38 — em silêncio, e com um número plausível. O
parser lê `&page=2` e junta, removendo repetidos por (data, adversário).

**Slugs que redirecionam sem erro.** `/equipa/brentford` devolve **200 e 266 KB** da lista geral
de equipas. As formas canónicas com id estão em `scripts/zerozero.json` (`brentford/2600`,
`sunderland/91`, `aston-villa/76`, `hull-city/5096`, `coventry-city/2584`).

## Validação: as linhas da PL não se deitam fora

O zerozero também lista a Premier League, e essas linhas são redundantes — mas são a melhor
verificação disponível. Como os 380 jogos oficiais já são conhecidos, para cada clube confirma-se
que os jogos da PL lidos no zerozero **batem com os da API** (mesma data, mesmo adversário).

É validação semântica, não "a página respondeu": é o mesmo teste que apanhou o
"Spurs → Wolverhampton" nas etiquetas da PL. Se um clube não bater, a recolha **recusa os jogos
desse clube** e regista a falha no diagnóstico, em vez de escrever lixo no ficheiro.

Verificações de contagem, todas baratas e todas capazes de apanhar truncagem silenciosa:

- 20 clubes, cada um com **38 jogos da PL** no zerozero (total 760).
- Cada jogo não-PL entre dois clubes da PL aparece nos **dois** clubes.
- Nenhuma data fora de 2026-07-01 … 2027-07-01.

## Recolha: `scripts/fetch_calendario.py`

Módulo próprio, stdlib, que importa os utilitários partilhados de `fetch_data.py` (o mesmo padrão
do `fetch_classica.py`). Escreve `site/data/calendario.json` e nada mais.

Chamado pelo `atualizar.cmd` a seguir às duas recolhas. Custo ~41 pedidos, perto de meio minuto;
o calendário muda no máximo uma vez por semana, por isso não vale a pena mais do que isso.

Falha tolerada por clube: um clube que falhe fica sem jogos europeus e com uma entrada no
diagnóstico; os outros 19 seguem.

## Formato de `site/data/calendario.json`

```json
{
  "generated_at": "2026-09-07T10:00:00Z",
  "epoca_id": 156,
  "clubes": {
    "11": {
      "nome": "Man City", "curto": "MCI",
      "jogos": [
        {"data": "2026-10-11T15:30:00Z", "comp": "PL", "adv": 12, "adv_nome": "Liverpool",
         "casa": false, "dif": 5, "jornada": 6},
        {"data": "2026-10-14T19:00:00Z", "comp": "UCL", "adv": null, "adv_nome": "PSG",
         "casa": true, "dif": null, "jornada": null}
      ]
    }
  },
  "competicoes": {"PL": "Premier League", "UCL": "Champions League", "UEL": "Liga Europa",
                  "UECL": "Conference League", "LC": "Carabao Cup", "OUT": "Outras"},
  "diagnostico": [["Calendario zerozero", true, "20 clubes, 102 jogos por realizar fora da PL"]]
}
```

- `adv` é o id do clube da FPL quando o adversário é da PL, senão `null` e vale o `adv_nome`.
- `dif` só existe nos jogos da PL — é o que a API dá e o zerozero não.
- Só jogos **por realizar**; os já jogados não servem nenhuma das duas decisões.
- Tamanho estimado: ~90 KB.

## Interface: separador "Calendário"

Nos **dois modos** — os 20 clubes são os mesmos no Draft e na clássica.

### O gráfico

- **Eixo dos dias à escala**, uma linha por clube. O rótulo do clube fica `position: sticky` à
  esquerda enquanto se arrasta o gráfico; o scroll horizontal vive **dentro** do gráfico
  (`overflow-x: auto`), nunca no `body` — é requisito fixo do projeto e verifica-se a 375px.
- Cada jogo é um marcador na data certa, posicionado por percentagem do intervalo da janela.
- **PL**: colorido pela dificuldade, reaproveitando `.fx.d1`–`.fx.d5` que já existe (verde 1-2,
  neutro 3, coral 4-5).
- **Europa e taças**: forma distinta (losango contornado) e cor por competição. Não têm
  dificuldade para mostrar, e fingir uma seria inventar.
- `title` em cada marcador: competição, adversário, casa/fora, data e hora de Lisboa, e a
  dificuldade quando existe.

### A barra do Gantt é a congestão

Um jogo é um instante; o que tem duração é o aperto. Sombreia-se o troço da linha onde o clube
tem 3 ou mais jogos em qualquer janela deslizante de 8 dias, da data do primeiro à do último
esses jogos. Janelas que se sobreponham fundem-se numa barra só. É a única coisa no
gráfico que é mesmo uma barra, e é exatamente o que o utilizador quer ver.

### Controlos e ordenação

- Seletor de horizonte **4 / 8 / 16 semanas**, guardado em `localStorage` (`calJanela`), no mesmo
  padrão do seletor de janela das Sugestões.
- Ordenado por **número de jogos na janela**, decrescente — o mais carregado em cima. Empate
  desfeito pela dificuldade média. Clubes onde tenho jogadores levam ★ (via `owner`, que funciona
  nos dois modos).

### As duas leituras em texto, por baixo

Números, não só cores:

1. **Quem joga a meio da semana antes da próxima jornada** — clubes com jogo não-PL nos 4 dias
   anteriores ao seu próximo jogo da PL, com os meus jogadores desses clubes nomeados.
2. **Percurso mais fácil e mais duro da janela** — por dificuldade média dos jogos da PL, com o
   número ao lado.

## Testes

`scripts/testes.py` (stdlib, sem rede), contra um pedaço de HTML guardado em
`scripts/testes_dados/zerozero_jogos.html`:

- o parser lê as 10 células e a linha certa (data ISO, (C)/(F), competição, ronda);
- **pagina**: com duas páginas de 40, devolve mais de 40 jogos;
- linhas de cabeçalho e de classificação (13 células) são ignoradas;
- a normalização de competição mapeia "UEFA Europa League 26/27" para `UEL`;
- a validação contra a PL oficial **recusa** um clube cujos jogos da PL não batam;
- todos os caminhos de `zerozero.json` que precisam de id têm-no.

`site/testes.html` (modelo sintético):

- a janela corta pelas datas certas e não deixa passar jogos já realizados;
- a deteção de congestão marca 3 jogos em 8 dias e não marca 3 em 12;
- a ordenação põe o clube mais carregado em primeiro;
- um clube sem jogos europeus não ganha barra nenhuma.

`scripts/artefacto.py` passa a embutir `calendario.json` (mais ~90 KB no ficheiro único).

## Fora de âmbito

- Ligar a congestão ao modelo de projeção (decidido: só depois de medida).
- Taça de Inglaterra (não sorteada).
- Resultados de jogos já realizados.
- Jogos de sub-21, femininos ou amigáveis.
