"""
agentes.py
----------
Define os agentes da simulação:

  OcupanteAgente  — adulto padrão, idoso ou PcD. Tenta evacuar o edifício
                    seguindo rota mínima até a escada/saída, desviando de
                    fogo. O nível de pânico influencia a racionalidade.

  BrigadistaAgente — se move mais rápido, reduz o pânico de ocupantes
                     vizinhos e sinaliza rotas alternativas.

Máquina de estados do OcupanteAgente (RF-07, F-Formalismo):
    NORMAL → FUGA → EVACUADO
                  ↘ FERIDO → MORTO

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import math
import random
from enum import Enum, auto

from mesa import Agent

from simulacao.config import (
    VEL_ADULTO, VEL_IDOSO, VEL_PCD, VEL_BRIGADISTA,
    RAIO_PANICO, TAXA_PANICO_FOGO, TAXA_PANICO_FUMACA,
    TAXA_REDUCAO_PANICO, PANICO_LIMITE,
    DANO_FOGO_STEP, DANO_FUMACA_STEP, GRID_LINHAS, GRID_COLUNAS
)
from simulacao.edificio import (
    FOGO, FUMACA, ESCADA, SAIDA, LIVRE,
    eh_transitavel, vizinhos_moore, celulas_escada, celulas_saida
)


# ---------------------------------------------------------------------------
# Enum de estados do ciclo de vida (Formalismo — Máquina de Estados)
# ---------------------------------------------------------------------------
class Estado(Enum):
    NORMAL    = auto()   # Em descanso ou trabalho normal
    FUGA      = auto()   # Em processo de evacuação
    EVACUADO  = auto()   # Saiu com sucesso pelo térreo
    FERIDO    = auto()   # Incapacitado (saúde < 0.3)
    MORTO     = auto()   # Saúde = 0


# ---------------------------------------------------------------------------
# Tipos de perfil de ocupante
# ---------------------------------------------------------------------------
class Perfil(Enum):
    ADULTO = "adulto"
    IDOSO  = "idoso"
    PCD    = "pcd"


# ---------------------------------------------------------------------------
# Agente Ocupante
# ---------------------------------------------------------------------------
class OcupanteAgente(Agent):
    """
    Agente que representa um ocupante do edifício.

    Atributos principais (RF-07):
        andar      — andar atual (0 = térreo)
        linha, col — posição na grade 2D do andar
        velocidade — células máximas movidas por step
        panico     — nível de pânico [0.0, 1.0]
        saude      — nível de saúde  [0.0, 1.0]
        estado     — Estado enum (ciclo de vida)
        perfil     — Perfil enum (adulto/idoso/PcD)
    """

    def __init__(self, unique_id, model, andar: int, linha: int, col: int,
                 perfil: Perfil = Perfil.ADULTO):
        super().__init__(unique_id, model)

        self.andar  = andar
        self.linha  = linha
        self.col    = col
        self.perfil = perfil

        # Velocidade conforme perfil (RF-11)
        self.velocidade_base = {
            Perfil.ADULTO: VEL_ADULTO,
            Perfil.IDOSO:  VEL_IDOSO,
            Perfil.PCD:    VEL_PCD,
        }[perfil]

        self.panico = 0.0   # [0,1] — 0 = calmo, 1 = pânico total
        self.saude  = 1.0   # [0,1] — 1 = saudável, 0 = morto
        self.estado = Estado.NORMAL

        # Acumulador de movimento fracionário (agentes lentos não movem todo step)
        self._acumulador = 0.0

        # Alvo atual de movimento (linha, col) na grade atual
        self._alvo: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # Propriedade de velocidade efetiva (pânico reduz racionalidade)
    # ------------------------------------------------------------------
    @property
    def velocidade(self) -> float:
        """
        Pânico alto reduz levemente a velocidade efetiva, mas pode fazer
        o agente ignorar a rota ótima (RF-09).
        """
        reducao = 0.2 * self.panico
        return max(0.2, self.velocidade_base - reducao)

    # ------------------------------------------------------------------
    # Step principal (chamado pelo scheduler do Mesa)
    # ------------------------------------------------------------------
    def step(self):
        """Executa um passo da simulação para este agente."""
        if self.estado in (Estado.EVACUADO, Estado.MORTO):
            return

        grade = self.model.andares[self.andar]

        # 1. Atualizar pânico com base no ambiente
        self._atualizar_panico(grade)

        # 2. Verificar dano de fogo/fumaça
        self._aplicar_dano(grade)

        # 3. Máquina de estados — transição
        self._transicao_estado(grade)

        if self.estado in (Estado.EVACUADO, Estado.MORTO):
            return

        # 4. Mover em direção à saída
        self._acumulador += self.velocidade
        passos = int(self._acumulador)
        self._acumulador -= passos

        for _ in range(passos):
            self._mover(grade)

    # ------------------------------------------------------------------
    # Atualização do pânico (RF-09)
    # ------------------------------------------------------------------
    def _atualizar_panico(self, grade):
        """
        Incrementa o pânico conforme proximidade ao fogo e fumaça.
        Brigadistas próximos reduzem o pânico.
        """
        delta = 0.0

        # Verificar vizinhança por fogo/fumaça
        for (nr, nc) in vizinhos_moore(self.linha, self.col, raio=RAIO_PANICO):
            cell = int(grade[nr, nc])
            if cell == FOGO:
                # Quanto mais próximo, maior o incremento
                dist = math.hypot(nr - self.linha, nc - self.col)
                delta += TAXA_PANICO_FOGO / max(dist, 0.5)
            elif cell == FUMACA:
                delta += TAXA_PANICO_FUMACA

        # Brigadistas próximos reduzem o pânico
        for ag in self.model.grid_agentes.get(self.andar, []):
            if isinstance(ag, BrigadistaAgente):
                dist = math.hypot(ag.linha - self.linha, ag.col - self.col)
                if dist <= ag.raio_influencia:
                    delta -= TAXA_REDUCAO_PANICO

        self.panico = min(1.0, max(0.0, self.panico + delta))

    # ------------------------------------------------------------------
    # Dano por fogo e fumaça (RF-07)
    # ------------------------------------------------------------------
    def _aplicar_dano(self, grade):
        """Aplica dano de saúde se o agente estiver em célula perigosa."""
        cell = int(grade[self.linha, self.col])
        if cell == FOGO:
            self.saude -= DANO_FOGO_STEP
        elif cell == FUMACA:
            self.saude -= DANO_FUMACA_STEP
        self.saude = max(0.0, self.saude)

    # ------------------------------------------------------------------
    # Máquina de estados (Formalismo)
    # ------------------------------------------------------------------
    def _transicao_estado(self, grade):
        """Atualiza o estado do agente conforme condições atuais."""
        if self.saude <= 0.0:
            self.estado = Estado.MORTO
            return

        if self.saude < 0.3 and self.estado != Estado.FERIDO:
            self.estado = Estado.FERIDO

        # Qualquer ocupante que percebe fogo inicia a fuga
        if self.estado == Estado.NORMAL:
            grade_cell = int(grade[self.linha, self.col])
            if grade_cell == FOGO or self.panico > 0.1:
                self.estado = Estado.FUGA

        # Chegou à saída no térreo → evacuado
        if self.andar == 0:
            cell = int(grade[self.linha, self.col])
            if cell == SAIDA:
                self.estado = Estado.EVACUADO
                self.model.registrar_evacuado(self)

    # ------------------------------------------------------------------
    # Movimento (RF-08)
    # ------------------------------------------------------------------
    def _mover(self, grade):
        """
        Move o agente um passo em direção à saída.
        Se o pânico ultrapassar PANICO_LIMITE, o agente toma decisão
        semi-aleatória (comportamento irracional — RF-09).
        """
        if self.estado in (Estado.EVACUADO, Estado.MORTO):
            return

        # Pânico extremo → movimento aleatório com tendência à saída
        if self.panico >= PANICO_LIMITE and self.random.random() < 0.4:
            self._movimento_aleatorio(grade)
            return

        # Estratégia hierárquica: escada → saída
        alvo = self._calcular_alvo(grade)
        if alvo is None:
            self._movimento_aleatorio(grade)
            return

        # Movimento guloso: escolhe vizinho mais próximo ao alvo
        melhor = None
        melhor_dist = float('inf')
        for (nr, nc) in vizinhos_moore(self.linha, self.col, raio=1):
            if not eh_transitavel(grade, nr, nc):
                continue
            # Não mover para célula com muita gente (RF-10)
            if self.model.ocupacao(self.andar, nr, nc) >= 3:
                continue
            dist = math.hypot(nr - alvo[0], nc - alvo[1])
            if dist < melhor_dist:
                melhor_dist = dist
                melhor = (nr, nc)

        if melhor:
            self._executar_movimento(melhor[0], melhor[1], grade)

    def _calcular_alvo(self, grade) -> tuple[int, int] | None:
        """
        Determina o alvo imediato do agente:
        - Se no térreo: saída mais próxima
        - Caso contrário: escada mais próxima
        """
        if self.andar == 0:
            saidas = celulas_saida(grade)
            if saidas:
                return min(saidas,
                           key=lambda s: math.hypot(s[0]-self.linha, s[1]-self.col))
        else:
            escadas = celulas_escada(grade)
            if escadas:
                return min(escadas,
                           key=lambda e: math.hypot(e[0]-self.linha, e[1]-self.col))
        return None

    def _movimento_aleatorio(self, grade):
        """Move para um vizinho aleatório transitável."""
        opcoes = [(nr, nc) for (nr, nc) in vizinhos_moore(self.linha, self.col)
                  if eh_transitavel(grade, nr, nc)
                  and self.model.ocupacao(self.andar, nr, nc) < 3]
        if opcoes:
            nr, nc = self.random.choice(opcoes)
            self._executar_movimento(nr, nc, grade)

    def _executar_movimento(self, nova_linha: int, nova_col: int, grade):
        """
        Efetua o movimento, incluindo descida de escada para andar inferior.
        """
        cell_destino = int(grade[nova_linha, nova_col])

        # Se entrou em célula de escada E não está no térreo → desce um andar
        if cell_destino == ESCADA and self.andar > 0:
            # Verificar capacidade da escada (RF-06)
            if self.model.fluxo_escada(self.andar, nova_linha, nova_col) >= self.model.capacidade_escada:
                return  # Escada lotada — aguarda próximo step
            self.model.registrar_fluxo_escada(self.andar, nova_linha, nova_col)
            self.andar -= 1  # Desce um andar

        self.linha = nova_linha
        self.col   = nova_col


# ---------------------------------------------------------------------------
# Agente Brigadista (RF-12, RF-13)
# ---------------------------------------------------------------------------
class BrigadistaAgente(Agent):
    """
    Agente brigadista: patrulha andares, reduz pânico de vizinhos e
    sinaliza rotas alternativas.

    Atributos:
        andar, linha, col — posição atual
        velocidade        — 1.5× velocidade do adulto padrão
        raio_influencia   — células ao redor onde reduz pânico
    """

    def __init__(self, unique_id, model, andar: int, linha: int, col: int):
        super().__init__(unique_id, model)

        self.andar           = andar
        self.linha           = linha
        self.col             = col
        self.velocidade      = VEL_BRIGADISTA
        self.raio_influencia = 5   # Raio de redução de pânico

        self._acumulador = 0.0
        self._direcao    = (0, 1)  # Direção inicial de patrulha

    def step(self):
        """Patrulha o andar, priorizando zonas com pânico elevado."""
        self._acumulador += self.velocidade
        passos = int(self._acumulador)
        self._acumulador -= passos

        grade = self.model.andares[self.andar]
        for _ in range(passos):
            self._patrulhar(grade)

    def _patrulhar(self, grade):
        """
        Move em direção ao ocupante com maior pânico no raio de patrulha,
        ou aleatoriamente se não há ninguém em pânico próximo.
        """
        alvo_ag = None
        max_panico = 0.0

        for ag in self.model.grid_agentes.get(self.andar, []):
            if isinstance(ag, OcupanteAgente) and ag.estado == Estado.FUGA:
                dist = math.hypot(ag.linha - self.linha, ag.col - self.col)
                if dist < 8 and ag.panico > max_panico:
                    max_panico = ag.panico
                    alvo_ag = ag

        if alvo_ag:
            # Mover em direção ao ocupante em pânico
            dr = int(math.copysign(1, alvo_ag.linha - self.linha)) if alvo_ag.linha != self.linha else 0
            dc = int(math.copysign(1, alvo_ag.col   - self.col))   if alvo_ag.col   != self.col   else 0
            nr, nc = self.linha + dr, self.col + dc
        else:
            # Patrulha aleatória
            opcoes = [(nr, nc) for (nr, nc) in vizinhos_moore(self.linha, self.col)
                      if eh_transitavel(grade, nr, nc)]
            if not opcoes:
                return
            nr, nc = self.random.choice(opcoes)

        if eh_transitavel(grade, nr, nc):
            self.linha, self.col = nr, nc
