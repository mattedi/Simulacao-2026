"""
config.py
---------
Parâmetros configuráveis da simulação de evacuação em incêndio.

Todos os valores definidos aqui podem ser sobrescritos via linha de comando
(run_simulation.py --help) ou passados diretamente ao construtor do modelo.

Trabalho Final — Eletiva IV - Simulação
FURB — Ciência da Computação — 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

# ---------------------------------------------------------------------------
# Parâmetros do edifício
# ---------------------------------------------------------------------------
NUM_ANDARES         = 30    # Número total de andares (0 = térreo)
GRID_LINHAS         = 20    # Linhas da grade por andar
GRID_COLUNAS        = 20    # Colunas da grade por andar

# ---------------------------------------------------------------------------
# Parâmetros dos agentes (RF-11)
# ---------------------------------------------------------------------------
NUM_OCUPANTES       = 300   # Quantidade de ocupantes iniciais
NUM_BRIGADISTAS     = 10    # Quantidade de brigadistas

# Velocidades base (células por step)
VEL_ADULTO          = 1.0
VEL_IDOSO           = 0.6   # 60% do adulto padrão
VEL_PCD             = 0.4   # 40% do adulto padrão
VEL_BRIGADISTA      = 1.5   # 150% do adulto padrão

# Proporção dos perfis de ocupantes
PROP_ADULTO         = 0.70
PROP_IDOSO          = 0.20
PROP_PCD            = 0.10

# ---------------------------------------------------------------------------
# Parâmetros do incêndio (RF-03, RF-04)
# ---------------------------------------------------------------------------
ANDAR_FOCO          = 10            # Andar onde o fogo começa
CELULA_FOCO         = (10, 10)      # (linha, coluna) da célula inicial do fogo
TAXA_PROPAGACAO     = 0.15          # Probabilidade de propagação por step [0,1]

# ---------------------------------------------------------------------------
# Parâmetros da fumaça (RF-05)
# ---------------------------------------------------------------------------
RAIO_FUMACA         = 3             # Raio de visibilidade reduzida (células)

# ---------------------------------------------------------------------------
# Parâmetros das escadas (RF-06)
# ---------------------------------------------------------------------------
CAPACIDADE_ESCADA   = 5             # Máx. agentes que passam por escada/step

# ---------------------------------------------------------------------------
# Parâmetros de pânico (RF-09)
# ---------------------------------------------------------------------------
RAIO_PANICO         = 4            # Raio de influência do fogo sobre o pânico
TAXA_PANICO_FOGO    = 0.08         # Incremento de pânico por step (fogo próximo)
TAXA_PANICO_FUMACA  = 0.03         # Incremento de pânico por step (fumaça próxima)
TAXA_REDUCAO_PANICO = 0.05         # Redução de pânico por brigadista próximo
PANICO_LIMITE       = 0.7          # Acima disto o agente toma decisão aleatória

# ---------------------------------------------------------------------------
# Parâmetros de saúde (RF-07)
# ---------------------------------------------------------------------------
DANO_FOGO_STEP      = 0.4          # Dano de saúde por step dentro do fogo
DANO_FUMACA_STEP    = 0.08         # Dano de saúde por step com fumaça densa

# ---------------------------------------------------------------------------
# Reprodutibilidade e execução
# ---------------------------------------------------------------------------
SEED_PADRAO         = 42
MAX_STEPS           = 3000         # Limite máximo de steps por rodada
