"""
edificio.py
-----------
Representa a estrutura física do edifício: andares, células, escadas,
saídas de emergência e tipos de material.

Cada andar é uma grade 2D de GRID_LINHAS × GRID_COLUNAS células.
Tipos de célula:
    'livre'       — corredor/sala, transitável e inflamável
    'escada'      — célula de escada de emergência (não inflamável)
    'elevador'    — bloqueado durante incêndio (intransitável)
    'saida'       — saída sinalizada (destino final no térreo)
    'parede'      — parede de concreto (não inflamável, intransitável)
    'fogo'        — em chamas (intransitável)
    'fumaca'      — coberta por fumaça (transitável, mas visibilidade reduzida)

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import numpy as np
from simulacao.config import (
    NUM_ANDARES, GRID_LINHAS, GRID_COLUNAS
)


# ---------------------------------------------------------------------------
# Constantes de tipo de célula
# ---------------------------------------------------------------------------
LIVRE    = 0
PAREDE   = 1
ESCADA   = 2
ELEVADOR = 3
SAIDA    = 4
FOGO     = 5
FUMACA   = 6

# Células que podem pegar fogo
INFLAMAVEL = {LIVRE, FUMACA}

# Células intransitáveis para ocupantes normais
INTRANSITAVEL = {PAREDE, ELEVADOR, FOGO}


def _gerar_andar(andar: int) -> np.ndarray:
    """
    Gera o layout de um andar como grade 2D.

    Layout padrão (20×20):
    - Bordas laterais: paredes
    - Coluna 0 e 19: paredes laterais
    - Linha 0 e 19: paredes superior/inferior
    - Cantos NW/SW: escadas de emergência (células 1,1 e 18,1)
    - Cantos NE/SE: escadas de emergência (células 1,18 e 18,18)
    - Centro coluna 10: elevadores (bloqueados)
    - Saídas apenas no térreo (andar 0): células (10,0)
    """
    grade = np.full((GRID_LINHAS, GRID_COLUNAS), LIVRE, dtype=np.int8)

    # Paredes nas bordas do andar
    grade[0, :]  = PAREDE
    grade[-1, :] = PAREDE
    grade[:, 0]  = PAREDE
    grade[:, -1] = PAREDE

    # Escadas de emergência nos quatro cantos internos
    # (RF-02: mínimo 2 por andar; usamos 4 para realismo)
    escadas = [(1, 1), (1, 18), (18, 1), (18, 18)]
    for (r, c) in escadas:
        grade[r, c]     = ESCADA
        grade[r+1, c]   = ESCADA  # escada ocupa 2 células verticalmente

    # Elevadores no centro (bloqueados durante incêndio — NBR 9077)
    for r in range(8, 13):
        grade[r, 10] = ELEVADOR

    # Saídas de emergência apenas no térreo
    if andar == 0:
        grade[10, 0]  = SAIDA   # saída oeste
        grade[10, 19] = SAIDA   # saída leste

    return grade


def construir_edificio() -> list[np.ndarray]:
    """
    Retorna lista de grades numpy, uma por andar (índice 0 = térreo).
    """
    return [_gerar_andar(a) for a in range(NUM_ANDARES)]


def celulas_escada(grade: np.ndarray) -> list[tuple[int, int]]:
    """Retorna todas as posições de escada em uma grade."""
    posicoes = np.argwhere(grade == ESCADA)
    return [(int(r), int(c)) for r, c in posicoes]


def celulas_saida(grade: np.ndarray) -> list[tuple[int, int]]:
    """Retorna todas as posições de saída em uma grade."""
    posicoes = np.argwhere(grade == SAIDA)
    return [(int(r), int(c)) for r, c in posicoes]


def eh_transitavel(grade: np.ndarray, linha: int, coluna: int) -> bool:
    """Verifica se uma célula pode ser ocupada por um agente."""
    if not (0 <= linha < GRID_LINHAS and 0 <= coluna < GRID_COLUNAS):
        return False
    return int(grade[linha, coluna]) not in INTRANSITAVEL


def vizinhos_moore(linha: int, coluna: int, raio: int = 1) -> list[tuple[int, int]]:
    """
    Retorna coordenadas dos vizinhos na vizinhança de Moore (quadrado),
    excluindo a própria célula e posições fora dos limites da grade.
    """
    vizs = []
    for dr in range(-raio, raio + 1):
        for dc in range(-raio, raio + 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = linha + dr, coluna + dc
            if 0 <= nr < GRID_LINHAS and 0 <= nc < GRID_COLUNAS:
                vizs.append((nr, nc))
    return vizs
