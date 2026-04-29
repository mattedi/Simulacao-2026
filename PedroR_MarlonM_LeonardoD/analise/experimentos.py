"""
analise/experimentos.py
-----------------------
Funções para execução de múltiplas rodadas e análise de sensibilidade.

  executar_rodadas()     — N rodadas com seeds distintos (RNF-04)
  analise_sensibilidade() — varia taxa de propagação e capacidade de escada

Os resultados são exportados automaticamente para CSV (RF-E: exportar CSV).

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import os
import itertools
import numpy as np
import pandas as pd

from simulacao.modelo import ModeloEvacuacao
from simulacao.config import (
    NUM_OCUPANTES, ANDAR_FOCO, CELULA_FOCO,
    TAXA_PROPAGACAO, NUM_BRIGADISTAS, CAPACIDADE_ESCADA
)


def executar_rodadas(
    n_rodadas:   int  = 30,
    params_base: dict = None,
    output_dir:  str  = "resultados",
    seeds:       list = None,
) -> pd.DataFrame:
    """
    Executa N rodadas independentes com seeds distintos e retorna
    DataFrame com métricas finais de cada rodada.

    Parâmetros:
        n_rodadas   — quantidade de rodadas (mínimo 30 — RNF-04)
        params_base — dicionário de parâmetros base (usa config.py se None)
        output_dir  — diretório para salvar CSVs individuais
        seeds       — lista de seeds (gera sequencial se None)

    Retorno:
        DataFrame com uma linha por rodada e colunas de métricas.
    """
    os.makedirs(output_dir, exist_ok=True)

    params = {
        "num_ocupantes":     NUM_OCUPANTES,
        "andar_foco":        ANDAR_FOCO,
        "celula_foco":       CELULA_FOCO,
        "taxa_propagacao":   TAXA_PROPAGACAO,
        "num_brigadistas":   NUM_BRIGADISTAS,
        "capacidade_escada": CAPACIDADE_ESCADA,
    }
    if params_base:
        params.update(params_base)

    seeds = seeds or list(range(1, n_rodadas + 1))
    resultados = []

    for i, seed in enumerate(seeds, 1):
        print(f"  Rodada {i:>3}/{n_rodadas}  (seed={seed})", end="\r", flush=True)
        modelo = ModeloEvacuacao(**params, seed=seed)
        modelo.executar()
        m = modelo.metricas_finais()

        # Salvar CSV de série temporal desta rodada
        csv_path = os.path.join(output_dir, f"serie_seed{seed:04d}.csv")
        modelo.exportar_csv(csv_path)

        resultados.append(m)

    print()  # Limpa linha do progresso
    df = pd.DataFrame(resultados)
    df.to_csv(os.path.join(output_dir, "resumo_rodadas.csv"), index=False)
    return df


def analise_sensibilidade(
    output_dir:   str = "resultados",
    num_ocupantes: int = NUM_OCUPANTES,
    n_rodadas_por_config: int = 5,
) -> pd.DataFrame:
    """
    Análise de sensibilidade: varia dois parâmetros principais (RF-E):
        1. taxa_propagacao   — [0.05, 0.10, 0.15, 0.20, 0.30]
        2. capacidade_escada — [2, 5, 8, 12]

    Para cada combinação, executa n_rodadas_por_config rodadas e
    agrega as métricas (média ± desvio padrão).

    Retorno:
        DataFrame com resultados agregados de cada configuração.
    """
    os.makedirs(output_dir, exist_ok=True)

    taxas      = [0.05, 0.10, 0.15, 0.20, 0.30]
    capacidades = [2, 5, 8, 12]

    todas_configs = list(itertools.product(taxas, capacidades))
    total_configs = len(todas_configs)
    resultados_todos = []

    print(f"\n[Sensibilidade] {total_configs} configurações × {n_rodadas_por_config} rodadas cada")
    print(f"  Total de rodadas: {total_configs * n_rodadas_por_config}\n")

    for idx, (taxa, cap) in enumerate(todas_configs, 1):
        print(f"  Config {idx:>2}/{total_configs}  taxa={taxa:.2f}  cap={cap}")
        subdir = os.path.join(output_dir, f"sens_taxa{taxa:.2f}_cap{cap}")
        os.makedirs(subdir, exist_ok=True)

        seeds = list(range(idx * 100, idx * 100 + n_rodadas_por_config))
        df_config = executar_rodadas(
            n_rodadas=n_rodadas_por_config,
            params_base={
                "num_ocupantes":     num_ocupantes,
                "taxa_propagacao":   taxa,
                "capacidade_escada": cap,
            },
            output_dir=subdir,
            seeds=seeds,
        )

        # Agregar métricas
        agg = {
            "taxa_propagacao":       taxa,
            "capacidade_escada":     cap,
            "taxa_evac_media":       df_config["taxa_evacuacao"].mean(),
            "taxa_evac_std":         df_config["taxa_evacuacao"].std(),
            "mortos_media":          df_config["mortos"].mean(),
            "mortos_std":            df_config["mortos"].std(),
            "tempo_evac_media":      df_config["tempo_medio_evac"].mean(),
            "tempo_evac_std":        df_config["tempo_medio_evac"].std(),
            "step_final_media":      df_config["step_final"].mean(),
            "celulas_fogo_media":    df_config["celulas_fogo"].mean(),
            "n_rodadas":             n_rodadas_por_config,
        }
        resultados_todos.append(agg)

    df_sens = pd.DataFrame(resultados_todos)
    csv_path = os.path.join(output_dir, "sensibilidade.csv")
    df_sens.to_csv(csv_path, index=False)
    print(f"\n[OK] Análise de sensibilidade salva em '{csv_path}'")
    return df_sens
