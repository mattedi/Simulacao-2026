"""
fogo.py
-------
Modelo de propagação do fogo e da fumaça como autômato celular (AC).

Formalismo adotado (RF-04, F):
    A cada step, cada célula em chamas tenta se propagar para vizinhos
    de Von Neumann (4 direções). A probabilidade de ignição é controlada
    por TAXA_PROPAGACAO e pelo tipo de material da célula de destino.

Fumaça (RF-05):
    Células adjacentes a fogo geram fumaça com raio configurável.
    Fumaça se dissipa após STEPS_FUMACA_DISSIPA steps.

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import random
import numpy as np

from simulacao.config import (
    TAXA_PROPAGACAO, RAIO_FUMACA,
    NUM_ANDARES, GRID_LINHAS, GRID_COLUNAS
)
from simulacao.edificio import (
    FOGO, FUMACA, LIVRE, ESCADA, SAIDA,
    INFLAMAVEL, vizinhos_moore
)

# Steps até a fumaça ser considerada densa em uma célula
STEPS_FUMACA_DISSIPA = 8

# Direções de Von Neumann (sem diagonais — propagação primária)
VON_NEUMANN = [(-1, 0), (1, 0), (0, -1), (0, 1)]


class ModeloFogo:
    """
    Gerencia a propagação do fogo e da fumaça em todos os andares.

    Atributos:
        andares       — lista de grades numpy (referência compartilhada com o modelo)
        intensidade   — grade de intensidade do fogo [0.0, 1.0] por andar
        fumaca_timer  — contador de steps de fumaça por célula/andar
        rng           — gerador de números aleatórios reproducível
    """

    def __init__(self, andares: list, seed: int = 42):
        self.andares = andares
        self.rng     = random.Random(seed)

        # Intensidade do fogo: 0 = sem fogo, 1 = fogo total
        self.intensidade: list[np.ndarray] = [
            np.zeros((GRID_LINHAS, GRID_COLUNAS), dtype=np.float32)
            for _ in range(NUM_ANDARES)
        ]

        # Contador de fumaça para dissipação
        self.fumaca_timer: list[np.ndarray] = [
            np.zeros((GRID_LINHAS, GRID_COLUNAS), dtype=np.int16)
            for _ in range(NUM_ANDARES)
        ]

    def iniciar_foco(self, andar: int, linha: int, col: int):
        """Inicia o foco do incêndio em uma célula específica."""
        self.andares[andar][linha, col]    = FOGO
        self.intensidade[andar][linha, col] = 1.0

    def step(self, taxa: float | None = None):
        """
        Executa um step do autômato celular:
        1. Propaga fogo para vizinhos inflamáveis
        2. Aumenta intensidade de células já em chamas
        3. Gera fumaça ao redor das chamas
        """
        taxa = taxa if taxa is not None else TAXA_PROPAGACAO

        for a in range(NUM_ANDARES):
            grade    = self.andares[a]
            intens   = self.intensidade[a]
            timer    = self.fumaca_timer[a]
            novas_ch = []  # Posições que pegam fogo neste step

            for r in range(GRID_LINHAS):
                for c in range(GRID_COLUNAS):
                    if grade[r, c] != FOGO:
                        continue

                    # Propagação para vizinhos de Von Neumann
                    for (dr, dc) in VON_NEUMANN:
                        nr, nc = r + dr, c + dc
                        if not (0 <= nr < GRID_LINHAS and 0 <= nc < GRID_COLUNAS):
                            continue
                        vizinho = int(grade[nr, nc])
                        # Só propaga para células inflamáveis
                        if vizinho in INFLAMAVEL:
                            # Probabilidade proporcional à intensidade do foco
                            prob = taxa * float(intens[r, c])
                            if self.rng.random() < prob:
                                novas_ch.append((nr, nc))

                    # Aumenta intensidade gradualmente
                    intens[r, c] = min(1.0, intens[r, c] + 0.05)

            # Aplicar novas chamas
            for (r, c) in novas_ch:
                grade[r, c]    = FOGO
                intens[r, c]   = 0.3   # Começa com intensidade baixa

            # Gerar fumaça ao redor do fogo
            self._gerar_fumaca(grade, timer, a)

    def _gerar_fumaca(self, grade: np.ndarray, timer: np.ndarray, andar: int):
        """
        Células dentro do raio RAIO_FUMACA de qualquer chama recebem fumaça.
        Células com fumaça antiga sem fogo próximo têm o timer decrementado.
        """
        mascara_fumaca = np.zeros_like(grade, dtype=bool)

        for r in range(GRID_LINHAS):
            for c in range(GRID_COLUNAS):
                if grade[r, c] != FOGO:
                    continue
                for (nr, nc) in vizinhos_moore(r, c, raio=RAIO_FUMACA):
                    cell = int(grade[nr, nc])
                    if cell not in (FOGO,):  # Não sobrescreve fogo
                        mascara_fumaca[nr, nc] = True

        # Aplicar fumaça e atualizar timers
        for r in range(GRID_LINHAS):
            for c in range(GRID_COLUNAS):
                cell = int(grade[r, c])
                if mascara_fumaca[r, c] and cell in (LIVRE, SAIDA):
                    grade[r, c]   = FUMACA
                    timer[r, c]   = STEPS_FUMACA_DISSIPA
                elif cell == FUMACA:
                    timer[r, c] -= 1
                    if timer[r, c] <= 0:
                        # Fumaça se dissipa — volta ao estado livre
                        grade[r, c] = LIVRE

    def celulas_em_chamas(self, andar: int) -> list[tuple[int, int]]:
        """Retorna lista de células em chamas no andar especificado."""
        pos = np.argwhere(self.andares[andar] == FOGO)
        return [(int(r), int(c)) for r, c in pos]

    def total_celulas_em_chamas(self) -> int:
        """Retorna o total de células em chamas em todo o edifício."""
        return sum(
            int(np.sum(self.andares[a] == FOGO))
            for a in range(NUM_ANDARES)
        )
