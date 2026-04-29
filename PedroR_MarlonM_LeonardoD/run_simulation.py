"""
run_simulation.py
-----------------
Ponto de entrada da simulação via linha de comando.

Exemplos de uso:
    # Rodada única com parâmetros padrão
    python run_simulation.py

    # Rodada única customizada
    python run_simulation.py --ocupantes 500 --andar-foco 15 --taxa-fogo 0.20 --seed 99

    # Experimento com 30 rodadas (análise estatística)
    python run_simulation.py --rodadas 30

    # Análise de sensibilidade (varia taxa de propagação e capacidade de escada)
    python run_simulation.py --sensibilidade

Trabalho Final — Eletiva IV - Simulação — FURB 2026
Equipe: Pedro Rafael, Leonardo Dal'Olmo, Marlon Moser
"""

import argparse
import os
import sys
import time

from simulacao.modelo import ModeloEvacuacao
from simulacao.config import (
    NUM_OCUPANTES, ANDAR_FOCO, CELULA_FOCO,
    TAXA_PROPAGACAO, NUM_BRIGADISTAS, SEED_PADRAO,
    CAPACIDADE_ESCADA, RAIO_FUMACA
)
from analise.experimentos import executar_rodadas, analise_sensibilidade


def parse_args():
    p = argparse.ArgumentParser(
        description="Simulação de evacuação de edifício em incêndio — FURB 2026"
    )
    p.add_argument("--ocupantes",      type=int,   default=NUM_OCUPANTES,
                   help=f"Número de ocupantes (padrão: {NUM_OCUPANTES})")
    p.add_argument("--andar-foco",     type=int,   default=ANDAR_FOCO,
                   help=f"Andar do foco do incêndio (padrão: {ANDAR_FOCO})")
    p.add_argument("--taxa-fogo",      type=float, default=TAXA_PROPAGACAO,
                   help=f"Taxa de propagação do fogo (padrão: {TAXA_PROPAGACAO})")
    p.add_argument("--brigadistas",    type=int,   default=NUM_BRIGADISTAS,
                   help=f"Número de brigadistas (padrão: {NUM_BRIGADISTAS})")
    p.add_argument("--seed",           type=int,   default=SEED_PADRAO,
                   help=f"Seed aleatório (padrão: {SEED_PADRAO})")
    p.add_argument("--capacidade-esc", type=int,   default=CAPACIDADE_ESCADA,
                   help=f"Capacidade máx. por escada/step (padrão: {CAPACIDADE_ESCADA})")
    p.add_argument("--rodadas",        type=int,   default=1,
                   help="Número de rodadas independentes (padrão: 1)")
    p.add_argument("--sensibilidade",  action="store_true",
                   help="Executar análise de sensibilidade completa")
    p.add_argument("--output-dir",     type=str,   default="resultados",
                   help="Diretório para salvar resultados (padrão: resultados/)")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 60)
    print("  Simulação de Evacuação em Incêndio — FURB 2026")
    print("  Equipe: Pedro Rafael · Leonardo Dal'Olmo · Marlon Moser")
    print("=" * 60)

    if args.sensibilidade:
        # Análise de sensibilidade — varia taxa de fogo e capacidade de escada
        print("\n[INFO] Iniciando análise de sensibilidade...")
        analise_sensibilidade(
            output_dir=args.output_dir,
            num_ocupantes=args.ocupantes,
        )
        print(f"\n[OK] Resultados salvos em '{args.output_dir}/'")
        return

    if args.rodadas > 1:
        # Múltiplas rodadas para análise estatística
        print(f"\n[INFO] Executando {args.rodadas} rodadas independentes...")
        params = dict(
            num_ocupantes=args.ocupantes,
            andar_foco=args.andar_foco,
            taxa_propagacao=args.taxa_fogo,
            num_brigadistas=args.brigadistas,
            capacidade_escada=args.capacidade_esc,
        )
        df_resumo = executar_rodadas(
            n_rodadas=args.rodadas,
            params_base=params,
            output_dir=args.output_dir,
        )
        print("\n--- Resumo Estatístico ---")
        print(df_resumo[["taxa_evacuacao", "mortos", "tempo_medio_evac", "step_final"]].describe())
        print(f"\n[OK] CSV exportado em '{args.output_dir}/resumo_rodadas.csv'")
        return

    # Rodada única
    print(f"\n[INFO] Executando rodada única (seed={args.seed})...")
    t0 = time.time()

    modelo = ModeloEvacuacao(
        num_ocupantes=args.ocupantes,
        andar_foco=args.andar_foco,
        celula_foco=CELULA_FOCO,
        taxa_propagacao=args.taxa_fogo,
        num_brigadistas=args.brigadistas,
        seed=args.seed,
        capacidade_escada=args.capacidade_esc,
    )
    modelo.executar()

    elapsed = time.time() - t0
    m = modelo.metricas_finais()

    print(f"\n  Seed:              {m['seed']}")
    print(f"  Ocupantes:         {m['total_ocupantes']}")
    print(f"  Evacuados:         {m['evacuados']}  ({m['taxa_evacuacao']:.1%})")
    print(f"  Mortos:            {m['mortos']}")
    print(f"  Feridos:           {m['feridos']}")
    print(f"  Steps até o fim:   {m['step_final']}")
    print(f"  Tempo médio evac.: {m['tempo_medio_evac']:.1f} steps" if m['tempo_medio_evac'] else "  Tempo médio evac.: N/A")
    print(f"  Células em chamas: {m['celulas_fogo']}")
    print(f"  Tempo real:        {elapsed:.1f}s")

    # Exportar CSV da rodada
    csv_path = os.path.join(args.output_dir, f"rodada_seed{args.seed}.csv")
    modelo.exportar_csv(csv_path)
    print(f"\n[OK] CSV exportado em '{csv_path}'")


if __name__ == "__main__":
    main()
