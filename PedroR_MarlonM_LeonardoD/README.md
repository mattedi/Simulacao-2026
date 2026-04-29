# Simulação de Evacuação de Edifício em Incêndio

**Trabalho Final — Eletiva IV: Simulação**  
**Curso:** Ciência da Computação — FURB (2026)  
**Professor:** M. Mattedi  
**Equipe:** Pedro Rafael · Leonardo Dal'Olmo · Marlon Moser

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Estrutura do Repositório](#estrutura-do-repositório)
3. [Instalação e Execução](#instalação-e-execução)
4. [Parâmetros Configuráveis](#parâmetros-configuráveis)
5. [Ciclo da Simulação (S→M→F→C→E→O)](#ciclo-da-simulação)
6. [Arquitetura do Código](#arquitetura-do-código)
7. [Resultados e Métricas](#resultados-e-métricas)
8. [Referências](#referências)

---

## Visão Geral

Este projeto implementa um **modelo de simulação baseado em agentes (ABM)** para a evacuação emergencial de um edifício de 30 andares em situação de incêndio, desenvolvido com o framework **Python Mesa**.

A simulação modela:
- **Ocupantes** com três perfis distintos: adulto padrão, idoso e pessoa com deficiência (PcD)
- **Brigadistas** que reduzem o pânico e orientam rotas
- **Propagação do fogo e fumaça** via autômato celular probabilístico
- **Gargalos nas escadas** com capacidade de fluxo limitada por step
- **Nível de pânico** como variável contínua que afeta o comportamento dos agentes

---

## Estrutura do Repositório

```
simulacao-incendio/
│
├── simulacao/                  # Pacote principal da simulação
│   ├── __init__.py
│   ├── config.py               # Todos os parâmetros configuráveis
│   ├── edificio.py             # Estrutura física: grades, andares, tipos de célula
│   ├── agentes.py              # OcupanteAgente, BrigadistaAgente (Mesa Agent)
│   ├── fogo.py                 # Autômato celular de propagação do fogo/fumaça
│   └── modelo.py               # ModeloEvacuacao (Mesa Model) — orquestrador
│
├── analise/                    # Pacote de análise e visualização
│   ├── __init__.py
│   ├── experimentos.py         # Rodadas em lote e análise de sensibilidade
│   └── visualizacoes.py        # Gráficos: série temporal, mapa de calor, boxplots
│
├── resultados/                 # Saída automática (CSVs e imagens)
│   └── .gitkeep
│
├── docs/                       # Documentação complementar
│   └── .gitkeep
│
├── run_simulation.py           # Ponto de entrada principal (CLI)
├── gerar_graficos.py           # Geração de gráficos a partir de CSVs existentes
├── requirements.txt            # Dependências Python
└── README.md
```

---

## Instalação e Execução

### Pré-requisitos

- Python 3.11 ou superior
- pip

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Rodada única (configuração padrão)

```bash
python run_simulation.py
```

### 3. Rodada personalizada

```bash
python run_simulation.py `
  --ocupantes 500 `
  --andar-foco 15 `
  --taxa-fogo 0.20 `
  --brigadistas 15 `
  --seed 99v
```

### 4. Experimento estatístico (30 rodadas)

```bash
python run_simulation.py --rodadas 30
```

Gera `resultados/resumo_rodadas.csv` com métricas de cada rodada e séries temporais individuais.

### 5. Análise de sensibilidade completa

```bash
python run_simulation.py --sensibilidade
```

Varia automaticamente:
- **Taxa de propagação do fogo:** 0.05 · 0.10 · 0.15 · 0.20 · 0.30
- **Capacidade da escada:** 2 · 5 · 8 · 12 agentes/step

### 6. Gerar visualizações

```bash
# Gráficos de uma rodada (reexecuta com seed)
python gerar_graficos.py --seed 42

# Heatmap de sensibilidade (requer resultados/sensibilidade.csv)
python gerar_graficos.py --sensibilidade

# Boxplots de distribuição (requer resultados/resumo_rodadas.csv)
python gerar_graficos.py --distribuicao

# Tudo de uma vez
python gerar_graficos.py --tudo
```

---

## Parâmetros Configuráveis

Todos os parâmetros abaixo podem ser ajustados em `simulacao/config.py` ou passados via linha de comando.

| Parâmetro | CLI | Padrão | Descrição |
|---|---|---|---|
| Número de ocupantes | `--ocupantes` | 300 | Total de agentes ocupantes |
| Andar do foco | `--andar-foco` | 10 | Andar inicial do incêndio (0=térreo) |
| Taxa de propagação | `--taxa-fogo` | 0.15 | Prob. de ignição por célula/step |
| Número de brigadistas | `--brigadistas` | 10 | Total de agentes brigadistas |
| Seed aleatório | `--seed` | 42 | Garante reprodutibilidade |
| Capacidade da escada | `--capacidade-esc` | 5 | Máx. agentes por escada/step |
| Raio de fumaça | _(em config.py)_ | 3 | Raio de visibilidade reduzida (células) |

---

## Ciclo da Simulação

O projeto é organizado segundo o ciclo básico da simulação trabalhado na disciplina:

### S — Sistema de Referência

O sistema de referência é um **edifício de 30 andares** (0=térreo, numerados até 29), com:
- Grade **20×20 células** por andar
- Escadas de emergência nos quatro cantos internos (não inflamáveis)
- Elevadores bloqueados durante o incêndio (NBR 9077)
- Saídas de emergência sinalizadas no térreo
- Perfis reais de ocupantes: adultos padrão (70%), idosos (20%) e PcD (10%)
- Material das células: inflamável (corredores/salas) ou não inflamável (concreto/escadas)

### M — Modelo Conceitual (Protocolo ODD)

**Overview:**
- **Propósito:** Simular evacuação emergencial e identificar gargalos, fatores de risco e o impacto de diferentes perfis de ocupantes
- **Entidades:** `OcupanteAgente`, `BrigadistaAgente`, células de fogo/fumaça
- **Escala espacial:** células (≈ 0,5 m²) · andares · edifício
- **Escala temporal:** steps/ticks (≈ 1 segundo por step)

**Design Concepts:**
- **Emergência:** congestionamentos surgem naturalmente da competição por células de escada
- **Adaptação:** agentes desviam de células em chamas e ajustam rotas quando bloqueados
- **Objetivos:** ocupante → minimizar distância à saída; brigadista → minimizar pânico da vizinhança
- **Interação:** conflito de célula entre ocupantes; redução de pânico por brigadistas próximos
- **Estocasticidade:** seed aleatório para posição inicial, propagação do fogo e nível de pânico
- **Observação:** métricas coletadas a cada step via `DataCollector` do Mesa

**Details:**
- **Inicialização:** N ocupantes distribuídos aleatoriamente pelos andares 1–29; fogo inicia no andar e célula configurados
- **Submodelos:** movimentação (busca gulosa + desvio), propagação do fogo (AC), pânico (variável contínua), fluxo de escada (fila com capacidade)

### F — Formalismo

| Submodelo | Formalismo Adotado |
|---|---|
| **Propagação do Fogo** | Autômato Celular: vizinhança de Von Neumann, probabilidade configurável, intensidade crescente |
| **Movimentação dos Agentes** | Sistema reativo + heurística gulosa (mínima distância euclidiana ao alvo) |
| **Nível de Pânico** | Variável contínua [0,1] com incremento por proximidade ao fogo/fumaça e decremento por brigadista |
| **Fluxo nas Escadas** | Fila com capacidade máxima por step — agente aguarda se escada está lotada |
| **Ciclo de Vida do Agente** | Máquina de estados finitos: `NORMAL → FUGA → EVACUADO` / `FERIDO → MORTO` |

### C — Implementação (Python Mesa)

Principais classes:

```
ModeloEvacuacao (mesa.Model)
├── schedule: RandomActivation   — ativa agentes em ordem aleatória
├── datacollector: DataCollector — coleta métricas por step
├── andares: list[np.ndarray]    — grades do edifício
└── modelo_fogo: ModeloFogo      — autômato celular do fogo

OcupanteAgente (mesa.Agent)
├── estado: Estado (FSM)
├── panico: float [0,1]
├── saude: float  [0,1]
└── perfil: Perfil (ADULTO/IDOSO/PCD)

BrigadistaAgente (mesa.Agent)
└── raio_influencia: int

ModeloFogo
├── intensidade: list[np.ndarray]
└── fumaca_timer: list[np.ndarray]
```

### E — Execução

- Mínimo de **30 rodadas** independentes com seeds distintos (`--rodadas 30`)
- Métricas registradas a cada step pelo `DataCollector`
- **Análise de sensibilidade** com variação de 2 parâmetros (`--sensibilidade`)
- Exportação automática de dados brutos em **CSV** por rodada

### O — Observação e Retroalimentação

**Métricas coletadas:**

| Métrica | Descrição |
|---|---|
| Taxa de evacuação | `evacuados / total_ocupantes` |
| Tempo médio de evacuação | Média dos steps até saída individual |
| Número de vítimas | Mortos + feridos ao final |
| Pânico médio | Média do nível de pânico dos agentes ativos |
| Células em chamas | Total de células do tipo FOGO em todos os andares |
| Mapa de calor | Densidade de ocupantes por célula/andar |

**Visualizações geradas:**
- Série temporal de evacuados, mortos, feridos, fogo e pânico por step
- Mapa de calor de densidade de ocupantes no térreo e andar do foco
- Heatmap de sensibilidade (taxa de evacuação × parâmetros)
- Boxplots de distribuição das métricas nas 30 rodadas

---

## Arquitetura do Código

```
step() do ModeloEvacuacao:
  1. _fluxo_escada.clear()          ← reseta contadores de escada
  2. _ocupacao.clear() + rebuild     ← atualiza mapa de ocupação
  3. ModeloFogo.step()               ← propaga fogo e fumaça (AC)
  4. schedule.step()                 ← ativa todos os agentes
     └─ OcupanteAgente.step()
          ├─ _atualizar_panico()     ← vizinhança de fogo/fumaça/brigadistas
          ├─ _aplicar_dano()         ← saúde decresce se em fogo/fumaça
          ├─ _transicao_estado()     ← FSM: NORMAL→FUGA→EVACUADO/MORTO
          └─ _mover()                ← busca gulosa + capacidade escada
     └─ BrigadistaAgente.step()
          └─ _patrulhar()            ← move para ocupante com maior pânico
  5. _atualizar_grid_agentes()       ← índice de agentes por andar
  6. datacollector.collect()         ← registra métricas
  7. _verificar_fim()                ← running=False se todos saíram/morreram
```

---

## Resultados e Métricas

Após execução, os arquivos abaixo são gerados em `resultados/`:

| Arquivo | Conteúdo |
|---|---|
| `rodada_seed{N}.csv` | Série temporal de métricas (step por step) |
| `resumo_rodadas.csv` | Uma linha por rodada com métricas finais |
| `sensibilidade.csv` | Métricas agregadas da análise de sensibilidade |
| `serie_seed{N}.png` | Gráfico de evolução temporal |
| `mapa_calor_terreo_seed{N}.png` | Mapa de densidade no térreo |
| `sensibilidade_heatmap.png` | Heatmaps dos parâmetros críticos |
| `distribuicao_rodadas.png` | Boxplots das 30 rodadas |

---

## Referências

- ABNT NBR 9077:2001 — Saídas de emergência em edifícios
- Grimm, V. et al. (2010). The ODD protocol: A review and first update. *Ecological Modelling*, 221(23), 2760–2768.
- Wilensky, U. & Rand, W. (2015). *An Introduction to Agent-Based Modeling*. MIT Press.
- Mesa — Agent-Based Modeling in Python: https://mesa.readthedocs.io
- Python Mesa GitHub: https://github.com/projectmesa/mesa
