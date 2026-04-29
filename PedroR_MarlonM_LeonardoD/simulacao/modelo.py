"""
modelo.py
---------
Classe principal do modelo Mesa que orquestra toda a simulação.

Responsabilidades:
    - Inicializar o edifício, os agentes e o modelo de fogo
    - Executar o scheduler (RandomActivation) a cada step
    - Coletar métricas via DataCollector do Mesa
    - Exportar resultados em CSV

Ciclo de simulação por step:
    1. ModeloFogo.step()       — propaga fogo e fumaça
    2. Scheduler.step()        — ativa todos os agentes em ordem aleatória
    3. DataCollector.collect() — registra métricas do step

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import random
import numpy as np
import pandas as pd
from collections import defaultdict

from mesa import Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector

from simulacao.config import (
    NUM_ANDARES, GRID_LINHAS, GRID_COLUNAS,
    NUM_OCUPANTES, NUM_BRIGADISTAS,
    ANDAR_FOCO, CELULA_FOCO, TAXA_PROPAGACAO,
    CAPACIDADE_ESCADA, SEED_PADRAO,
    PROP_ADULTO, PROP_IDOSO, PROP_PCD,
    MAX_STEPS
)
from simulacao.edificio import (
    construir_edificio, LIVRE, ESCADA, FOGO, FUMACA,
    celulas_escada, celulas_saida
)
from simulacao.agentes import OcupanteAgente, BrigadistaAgente, Estado, Perfil
from simulacao.fogo import ModeloFogo


# ---------------------------------------------------------------------------
# Funções auxiliares para o DataCollector
# ---------------------------------------------------------------------------
def _evacuados(model) -> int:
    return sum(1 for a in model.schedule.agents
               if isinstance(a, OcupanteAgente) and a.estado == Estado.EVACUADO)

def _mortos(model) -> int:
    return sum(1 for a in model.schedule.agents
               if isinstance(a, OcupanteAgente) and a.estado == Estado.MORTO)

def _feridos(model) -> int:
    return sum(1 for a in model.schedule.agents
               if isinstance(a, OcupanteAgente) and a.estado == Estado.FERIDO)

def _em_fuga(model) -> int:
    return sum(1 for a in model.schedule.agents
               if isinstance(a, OcupanteAgente) and a.estado == Estado.FUGA)

def _panico_medio(model) -> float:
    ocup = [a for a in model.schedule.agents
            if isinstance(a, OcupanteAgente)
            and a.estado not in (Estado.EVACUADO, Estado.MORTO)]
    return float(np.mean([a.panico for a in ocup])) if ocup else 0.0

def _celulas_fogo(model) -> int:
    return model.modelo_fogo.total_celulas_em_chamas()

def _saude_media(model) -> float:
    ocup = [a for a in model.schedule.agents
            if isinstance(a, OcupanteAgente)
            and a.estado not in (Estado.EVACUADO, Estado.MORTO)]
    return float(np.mean([a.saude for a in ocup])) if ocup else 0.0


# ---------------------------------------------------------------------------
# Modelo Principal
# ---------------------------------------------------------------------------
class ModeloEvacuacao(Model):
    """
    Modelo de simulação de evacuação de edifício em incêndio.

    Parâmetros (todos com valores padrão definidos em config.py):
        num_ocupantes       — quantidade de ocupantes
        andar_foco          — andar inicial do incêndio
        celula_foco         — (linha, col) da célula inicial do fogo
        taxa_propagacao     — probabilidade de propagação por step
        num_brigadistas     — quantidade de brigadistas
        seed                — seed aleatório para reprodutibilidade
        capacidade_escada   — máx. agentes por escada/step
        raio_fumaca         — raio de visibilidade na fumaça
    """

    def __init__(
        self,
        num_ocupantes:     int   = NUM_OCUPANTES,
        andar_foco:        int   = ANDAR_FOCO,
        celula_foco:       tuple = CELULA_FOCO,
        taxa_propagacao:   float = TAXA_PROPAGACAO,
        num_brigadistas:   int   = NUM_BRIGADISTAS,
        seed:              int   = SEED_PADRAO,
        capacidade_escada: int   = CAPACIDADE_ESCADA,
        raio_fumaca:       int   = 3,
    ):
        super().__init__()

        # Reprodutibilidade (RNF-01)
        self.seed = seed
        self.random = random.Random(seed)
        np.random.seed(seed)

        # Parâmetros
        self.num_ocupantes     = num_ocupantes
        self.taxa_propagacao   = taxa_propagacao
        self.capacidade_escada = capacidade_escada

        # Estrutura do edifício
        self.andares = construir_edificio()

        # Modelo de fogo
        self.modelo_fogo = ModeloFogo(self.andares, seed=seed)
        self.modelo_fogo.iniciar_foco(andar_foco, celula_foco[0], celula_foco[1])

        # Scheduler Mesa — ativa agentes em ordem aleatória por step
        self.schedule = RandomActivation(self)

        # Controle de fluxo nas escadas (RF-06): {(andar,linha,col): count_step}
        self._fluxo_escada: dict[tuple, int] = defaultdict(int)

        # Mapa de ocupação por célula: {(andar,linha,col): count}
        self._ocupacao: dict[tuple, int] = defaultdict(int)

        # Índice de agentes por andar para buscas eficientes
        self.grid_agentes: dict[int, list] = defaultdict(list)

        # Contador de evacuados com registro de tempo
        self._evacuados_tempo: list[dict] = []
        self._proximo_id = 0

        # Inicializar agentes
        self._criar_ocupantes(num_ocupantes)
        self._criar_brigadistas(num_brigadistas)

        # DataCollector Mesa — coleta métricas a cada step
        self.datacollector = DataCollector(
            model_reporters={
                "Evacuados":      _evacuados,
                "Mortos":         _mortos,
                "Feridos":        _feridos,
                "EmFuga":         _em_fuga,
                "PanicoMedio":    _panico_medio,
                "CelulasFogo":    _celulas_fogo,
                "SaudeMedia":     _saude_media,
                "Step":           lambda m: m.schedule.steps,
            }
        )

        # Flags de término
        self.running    = True
        self._step_fim  = None

    # ------------------------------------------------------------------
    # Inicialização de agentes
    # ------------------------------------------------------------------
    def _criar_ocupantes(self, n: int):
        """
        Distribui N ocupantes aleatoriamente pelos andares (exceto térreo).
        Respeita proporções de perfil: adulto/idoso/PcD.
        """
        perfis = (
            [Perfil.ADULTO] * int(n * PROP_ADULTO) +
            [Perfil.IDOSO]  * int(n * PROP_IDOSO)  +
            [Perfil.PCD]    * int(n * PROP_PCD)
        )
        # Ajusta arredondamento
        while len(perfis) < n:
            perfis.append(Perfil.ADULTO)
        self.random.shuffle(perfis)

        for i, perfil in enumerate(perfis):
            andar = self.random.randint(1, NUM_ANDARES - 1)
            linha, col = self._posicao_livre(andar)
            ag = OcupanteAgente(self._proximo_id, self, andar, linha, col, perfil)
            self._proximo_id += 1
            self.schedule.add(ag)
            self.grid_agentes[andar].append(ag)
            self._ocupacao[(andar, linha, col)] += 1

    def _criar_brigadistas(self, n: int):
        """
        Cria N brigadistas distribuídos pelos andares intermediários.
        """
        for i in range(n):
            andar = self.random.randint(1, NUM_ANDARES - 1)
            linha, col = self._posicao_livre(andar)
            ag = BrigadistaAgente(self._proximo_id, self, andar, linha, col)
            self._proximo_id += 1
            self.schedule.add(ag)
            self.grid_agentes[andar].append(ag)

    def _posicao_livre(self, andar: int) -> tuple[int, int]:
        """Retorna posição aleatória livre (tipo LIVRE) no andar."""
        grade = self.andares[andar]
        tentativas = 0
        while tentativas < 500:
            r = self.random.randint(1, GRID_LINHAS - 2)
            c = self.random.randint(1, GRID_COLUNAS - 2)
            if int(grade[r, c]) == LIVRE and self._ocupacao.get((andar, r, c), 0) < 2:
                return (r, c)
            tentativas += 1
        # Fallback: qualquer célula livre
        for r in range(1, GRID_LINHAS - 1):
            for c in range(1, GRID_COLUNAS - 1):
                if int(grade[r, c]) == LIVRE:
                    return (r, c)
        return (1, 1)

    # ------------------------------------------------------------------
    # Controle de ocupação e fluxo de escada
    # ------------------------------------------------------------------
    def ocupacao(self, andar: int, linha: int, col: int) -> int:
        """Retorna o número de agentes na célula especificada."""
        return self._ocupacao.get((andar, linha, col), 0)

    def fluxo_escada(self, andar: int, linha: int, col: int) -> int:
        """Retorna o fluxo atual na escada neste step."""
        return self._fluxo_escada.get((andar, linha, col), 0)

    def registrar_fluxo_escada(self, andar: int, linha: int, col: int):
        """Registra uso de escada neste step."""
        self._fluxo_escada[(andar, linha, col)] += 1

    def registrar_evacuado(self, agente: OcupanteAgente):
        """Registra o momento de evacuação de um agente."""
        self._evacuados_tempo.append({
            "unique_id": agente.unique_id,
            "perfil":    agente.perfil.value,
            "step":      self.schedule.steps,
            "saude":     agente.saude,
        })

    # ------------------------------------------------------------------
    # Step principal do modelo
    # ------------------------------------------------------------------
    def step(self):
        """Executa um step completo da simulação."""
        # 1. Resetar contadores de fluxo de escada (por step)
        self._fluxo_escada.clear()

        # 2. Atualizar mapa de ocupação (posições antigas)
        self._ocupacao.clear()
        for ag in self.schedule.agents:
            if isinstance(ag, OcupanteAgente) and ag.estado not in (Estado.EVACUADO, Estado.MORTO):
                self._ocupacao[(ag.andar, ag.linha, ag.col)] += 1

        # 3. Propagar fogo e fumaça
        self.modelo_fogo.step(taxa=self.taxa_propagacao)

        # 4. Ativar todos os agentes
        self.schedule.step()

        # 5. Atualizar índice de agentes por andar
        self._atualizar_grid_agentes()

        # 6. Coletar métricas
        self.datacollector.collect(self)

        # 7. Verificar condição de término
        self._verificar_fim()

    def _atualizar_grid_agentes(self):
        """Reconstrói o índice de agentes por andar."""
        self.grid_agentes.clear()
        for ag in self.schedule.agents:
            andar = ag.andar if hasattr(ag, 'andar') else 0
            self.grid_agentes[andar].append(ag)

    def _verificar_fim(self):
        """
        Encerra a simulação quando todos os ocupantes foram evacuados,
        morreram, ou o limite de steps foi atingido.
        """
        ocupantes = [a for a in self.schedule.agents if isinstance(a, OcupanteAgente)]
        ativos    = [a for a in ocupantes
                     if a.estado not in (Estado.EVACUADO, Estado.MORTO)]

        if not ativos:
            self._step_fim = self.schedule.steps
            self.running   = False

        if self.schedule.steps >= MAX_STEPS:
            self._step_fim = self.schedule.steps
            self.running   = False

    # ------------------------------------------------------------------
    # Execução e exportação
    # ------------------------------------------------------------------
    def executar(self) -> pd.DataFrame:
        """
        Executa a simulação até o término e retorna o DataFrame de métricas.
        """
        while self.running:
            self.step()
        return self.datacollector.get_model_vars_dataframe()

    def metricas_finais(self) -> dict:
        """
        Retorna dicionário com métricas consolidadas ao final da rodada.
        """
        ocupantes = [a for a in self.schedule.agents if isinstance(a, OcupanteAgente)]
        total     = len(ocupantes)
        evacuados = sum(1 for a in ocupantes if a.estado == Estado.EVACUADO)
        mortos    = sum(1 for a in ocupantes if a.estado == Estado.MORTO)
        feridos   = sum(1 for a in ocupantes if a.estado == Estado.FERIDO)

        tempos = [r["step"] for r in self._evacuados_tempo]

        return {
            "seed":             self.seed,
            "total_ocupantes":  total,
            "evacuados":        evacuados,
            "mortos":           mortos,
            "feridos":          feridos,
            "taxa_evacuacao":   evacuados / total if total > 0 else 0.0,
            "step_final":       self._step_fim or self.schedule.steps,
            "tempo_medio_evac": float(np.mean(tempos)) if tempos else None,
            "tempo_max_evac":   float(np.max(tempos))  if tempos else None,
            "celulas_fogo":     self.modelo_fogo.total_celulas_em_chamas(),
            "taxa_propagacao":  self.taxa_propagacao,
            "capacidade_escada":self.capacidade_escada,
        }

    def exportar_csv(self, caminho: str):
        """Exporta o histórico de métricas por step em CSV."""
        df = self.datacollector.get_model_vars_dataframe()
        df.index.name = "step"
        df.to_csv(caminho)
