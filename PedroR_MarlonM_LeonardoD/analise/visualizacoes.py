"""
analise/visualizacoes.py
------------------------
Geração de gráficos e visualizações das métricas de simulação (RF-O).

Gráficos disponíveis:
    plotar_serie_temporal()     — evolução de evacuados/mortos/fogo por step
    plotar_mapa_calor()         — mapa de calor de densidade de ocupantes
    plotar_sensibilidade()      — heatmap de análise de sensibilidade
    plotar_distribuicao()       — boxplots de métricas por configuração
    gerar_relatorio_visual()    — gera todos os gráficos de uma vez

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Backend sem interface gráfica (para execução headless)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

from simulacao.config import NUM_ANDARES, GRID_LINHAS, GRID_COLUNAS
from simulacao.edificio import FOGO, FUMACA, ESCADA, SAIDA, PAREDE, ELEVADOR


# Paleta de cores consistente
COR_EVACUADO  = "#2ecc71"   # Verde
COR_MORTO     = "#e74c3c"   # Vermelho
COR_FERIDO    = "#f39c12"   # Laranja
COR_FUGA      = "#3498db"   # Azul
COR_FOGO      = "#e67e22"   # Laranja escuro
COR_PANICO    = "#9b59b6"   # Roxo


def plotar_serie_temporal(
    df: pd.DataFrame,
    output_path: str = "resultados/serie_temporal.png",
    titulo: str = "Evolução da Simulação",
):
    """
    Gráfico de linha com a evolução de:
        - Evacuados, Mortos, Feridos, Em Fuga ao longo dos steps
        - Células em chamas (eixo secundário)
        - Pânico médio (eixo terciário normalizado)
    """
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    fig.suptitle(titulo, fontsize=14, fontweight="bold", y=0.98)

    ax1 = axes[0]
    ax2 = axes[1]

    steps = df.index

    # Painel 1 — Agentes por estado
    ax1.plot(steps, df.get("Evacuados", 0), color=COR_EVACUADO, lw=2.0, label="Evacuados")
    ax1.plot(steps, df.get("EmFuga",    0), color=COR_FUGA,     lw=1.5, label="Em Fuga", ls="--")
    ax1.plot(steps, df.get("Mortos",    0), color=COR_MORTO,    lw=2.0, label="Mortos")
    ax1.plot(steps, df.get("Feridos",   0), color=COR_FERIDO,   lw=1.5, label="Feridos", ls=":")
    ax1.set_ylabel("Número de Agentes", fontsize=11)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Agentes por Estado", fontsize=11)

    # Painel 2 — Fogo e Pânico
    ax2.fill_between(steps, df.get("CelulasFogo", 0),
                     color=COR_FOGO, alpha=0.6, label="Células em Chamas")
    ax2.set_ylabel("Células em Chamas", fontsize=11, color=COR_FOGO)
    ax2.tick_params(axis="y", colors=COR_FOGO)

    ax2b = ax2.twinx()
    ax2b.plot(steps, df.get("PanicoMedio", 0), color=COR_PANICO, lw=1.5, label="Pânico Médio")
    ax2b.set_ylabel("Pânico Médio [0,1]", fontsize=11, color=COR_PANICO)
    ax2b.tick_params(axis="y", colors=COR_PANICO)
    ax2b.set_ylim(0, 1.05)

    ax2.set_xlabel("Steps", fontsize=11)
    ax2.set_title("Propagação do Fogo e Pânico Médio", fontsize=11)
    ax2.grid(True, alpha=0.3)

    # Legenda combinada painel 2
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2b.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Gráfico] {output_path}")


def plotar_mapa_calor(
    modelo,
    andar: int = 0,
    output_path: str = "resultados/mapa_calor.png",
):
    """
    Mapa de calor da densidade de ocupantes em um andar específico.
    Sobrepõe a grade do edifício com a contagem de passagens de agentes.
    """
    grade = modelo.andares[andar]

    # Mapa de ocupação acumulada — conta agentes presentes no estado final
    mapa = np.zeros((GRID_LINHAS, GRID_COLUNAS), dtype=np.float32)
    for ag in modelo.schedule.agents:
        if hasattr(ag, "andar") and ag.andar == andar:
            mapa[ag.linha, ag.col] += 1

    fig, ax = plt.subplots(figsize=(9, 9))

    # Heatmap de densidade
    im = ax.imshow(mapa, cmap="YlOrRd", aspect="equal",
                   interpolation="nearest", alpha=0.85)

    # Sobrepor estrutura do edifício
    estrutura = np.zeros((GRID_LINHAS, GRID_COLUNAS, 4))  # RGBA
    for r in range(GRID_LINHAS):
        for c in range(GRID_COLUNAS):
            cell = int(grade[r, c])
            if cell == PAREDE:
                estrutura[r, c] = [0.2, 0.2, 0.2, 0.8]    # Cinza escuro
            elif cell == FOGO:
                estrutura[r, c] = [1.0, 0.3, 0.0, 0.9]    # Laranja fogo
            elif cell == FUMACA:
                estrutura[r, c] = [0.5, 0.5, 0.5, 0.5]    # Cinza fumaça
            elif cell == ESCADA:
                estrutura[r, c] = [0.0, 0.5, 1.0, 0.7]    # Azul escada
            elif cell == SAIDA:
                estrutura[r, c] = [0.0, 0.8, 0.0, 0.7]    # Verde saída
            elif cell == ELEVADOR:
                estrutura[r, c] = [0.4, 0.0, 0.8, 0.7]    # Roxo elevador

    ax.imshow(estrutura, aspect="equal")
    plt.colorbar(im, ax=ax, label="Densidade de Ocupantes", shrink=0.8)

    # Legenda manual
    legenda = [
        mpatches.Patch(color="#333333", label="Parede"),
        mpatches.Patch(color="#FF4500", label="Fogo"),
        mpatches.Patch(color="#888888", label="Fumaça"),
        mpatches.Patch(color="#007FFF", label="Escada"),
        mpatches.Patch(color="#00CC00", label="Saída"),
        mpatches.Patch(color="#6600CC", label="Elevador (bloqueado)"),
    ]
    ax.legend(handles=legenda, loc="upper right", fontsize=8,
              framealpha=0.9, borderpad=0.5)

    ax.set_title(f"Mapa de Calor — Andar {andar}\n"
                 f"(step {modelo.schedule.steps})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Coluna"); ax.set_ylabel("Linha")

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Gráfico] {output_path}")


def plotar_sensibilidade(
    df_sens: pd.DataFrame,
    output_path: str = "resultados/sensibilidade.png",
):
    """
    Heatmaps da análise de sensibilidade:
        - Taxa de evacuação média
        - Número médio de mortos
        - Tempo médio de evacuação
    """
    metricas = [
        ("taxa_evac_media",   "Taxa de Evacuação Média",    "Blues",   True),
        ("mortos_media",      "Média de Mortos",             "Reds",    False),
        ("tempo_evac_media",  "Tempo Médio de Evacuação",   "Oranges", False),
    ]

    taxas = sorted(df_sens["taxa_propagacao"].unique())
    caps  = sorted(df_sens["capacidade_escada"].unique())

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Análise de Sensibilidade — Parâmetros Críticos",
                 fontsize=13, fontweight="bold")

    for ax, (col, titulo, cmap, annot_fmt_pct) in zip(axes, metricas):
        pivot = df_sens.pivot(
            index="capacidade_escada",
            columns="taxa_propagacao",
            values=col
        )
        fmt = ".1%" if annot_fmt_pct else ".1f"
        sns.heatmap(
            pivot, ax=ax, cmap=cmap, annot=True, fmt=fmt,
            linewidths=0.5, cbar=True,
            xticklabels=[f"{t:.2f}" for t in taxas],
            yticklabels=[str(c) for c in caps],
        )
        ax.set_title(titulo, fontsize=11)
        ax.set_xlabel("Taxa de Propagação do Fogo")
        ax.set_ylabel("Capacidade da Escada (ag/step)")

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Gráfico] {output_path}")


def plotar_distribuicao(
    df_rodadas: pd.DataFrame,
    output_path: str = "resultados/distribuicao.png",
    titulo: str = "Distribuição das Métricas (30 Rodadas)",
):
    """
    Boxplots com a distribuição das principais métricas entre rodadas,
    evidenciando a variabilidade estocástica da simulação.
    """
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    fig.suptitle(titulo, fontsize=13, fontweight="bold")

    ax1, ax2, ax3 = axes

    ax1.boxplot(df_rodadas["taxa_evacuacao"].dropna(), widths=0.5,
                patch_artist=True,
                boxprops=dict(facecolor=COR_EVACUADO, alpha=0.7))
    ax1.set_title("Taxa de Evacuação"); ax1.set_ylabel("Proporção [0,1]")
    ax1.yaxis.grid(True, alpha=0.4)

    ax2.boxplot(df_rodadas["mortos"].dropna(), widths=0.5,
                patch_artist=True,
                boxprops=dict(facecolor=COR_MORTO, alpha=0.7))
    ax2.set_title("Número de Mortos"); ax2.set_ylabel("Agentes")
    ax2.yaxis.grid(True, alpha=0.4)

    ax3.boxplot(df_rodadas["tempo_medio_evac"].dropna(), widths=0.5,
                patch_artist=True,
                boxprops=dict(facecolor=COR_FUGA, alpha=0.7))
    ax3.set_title("Tempo Médio de Evacuação"); ax3.set_ylabel("Steps")
    ax3.yaxis.grid(True, alpha=0.4)

    # Adicionar estatísticas no título de cada eixo
    for ax, col, label in [
        (ax1, "taxa_evacuacao", "μ={:.2f} σ={:.3f}"),
        (ax2, "mortos",         "μ={:.1f} σ={:.1f}"),
        (ax3, "tempo_medio_evac", "μ={:.1f} σ={:.1f}"),
    ]:
        s = df_rodadas[col].dropna()
        if len(s) > 0:
            ax.set_xlabel(label.format(s.mean(), s.std()), fontsize=9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Gráfico] {output_path}")


def gerar_relatorio_visual(modelo, df_serie: pd.DataFrame, output_dir: str = "resultados"):
    """
    Gera todos os gráficos de uma rodada única:
        - Série temporal
        - Mapa de calor (térreo + andar do foco)
    """
    os.makedirs(output_dir, exist_ok=True)
    seed = modelo.seed

    print(f"\n  Gerando visualizações (seed={seed})...")

    plotar_serie_temporal(
        df_serie,
        output_path=os.path.join(output_dir, f"serie_seed{seed}.png"),
        titulo=f"Evolução da Simulação — seed={seed}",
    )
    plotar_mapa_calor(
        modelo, andar=0,
        output_path=os.path.join(output_dir, f"mapa_calor_terreo_seed{seed}.png"),
    )
    # Também gera mapa do andar de foco se diferente do térreo
    andar_foco = getattr(modelo, "_andar_foco", 10)
    if andar_foco != 0:
        plotar_mapa_calor(
            modelo, andar=andar_foco,
            output_path=os.path.join(output_dir, f"mapa_calor_foco_seed{seed}.png"),
        )
