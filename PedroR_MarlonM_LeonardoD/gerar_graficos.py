"""
gerar_graficos.py
-----------------
Script autônomo para gerar todos os gráficos e visualizações
a partir dos CSVs já produzidos pela simulação.

Uso:
    # Gerar gráficos de uma rodada única (reexecuta com seed)
    python gerar_graficos.py --seed 42

    # Gerar gráficos de análise de sensibilidade
    python gerar_graficos.py --sensibilidade

    # Gerar distribuição a partir de resumo_rodadas.csv
    python gerar_graficos.py --distribuicao

    # Gerar tudo
    python gerar_graficos.py --tudo

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import argparse
import os
import pandas as pd

from simulacao.modelo import ModeloEvacuacao
from analise.visualizacoes import (
    plotar_serie_temporal, plotar_mapa_calor,
    plotar_sensibilidade, plotar_distribuicao,
    gerar_relatorio_visual,
)


def parse_args():
    p = argparse.ArgumentParser(description="Gerar visualizações da simulação")
    p.add_argument("--seed",           type=int, default=42)
    p.add_argument("--output-dir",     type=str, default="resultados")
    p.add_argument("--sensibilidade",  action="store_true")
    p.add_argument("--distribuicao",   action="store_true")
    p.add_argument("--tudo",           action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 50)
    print("  Gerador de Visualizações — FURB 2026")
    print("=" * 50)

    if args.tudo or (not args.sensibilidade and not args.distribuicao):
        # Executa rodada e gera visualizações básicas
        print(f"\n[Rodada única] seed={args.seed}")
        modelo = ModeloEvacuacao(seed=args.seed)
        df = modelo.executar()
        gerar_relatorio_visual(modelo, df, output_dir=args.output_dir)

    if args.sensibilidade or args.tudo:
        csv_path = os.path.join(args.output_dir, "sensibilidade.csv")
        if os.path.exists(csv_path):
            print(f"\n[Sensibilidade] Lendo {csv_path}")
            df_sens = pd.read_csv(csv_path)
            plotar_sensibilidade(
                df_sens,
                output_path=os.path.join(args.output_dir, "sensibilidade_heatmap.png")
            )
        else:
            print(f"[AVISO] {csv_path} não encontrado. Execute run_simulation.py --sensibilidade primeiro.")

    if args.distribuicao or args.tudo:
        csv_path = os.path.join(args.output_dir, "resumo_rodadas.csv")
        if os.path.exists(csv_path):
            print(f"\n[Distribuição] Lendo {csv_path}")
            df_rod = pd.read_csv(csv_path)
            plotar_distribuicao(
                df_rod,
                output_path=os.path.join(args.output_dir, "distribuicao_rodadas.png")
            )
        else:
            print(f"[AVISO] {csv_path} não encontrado. Execute run_simulation.py --rodadas 30 primeiro.")

    print(f"\n[OK] Visualizações salvas em '{args.output_dir}/'")


if __name__ == "__main__":
    main()
