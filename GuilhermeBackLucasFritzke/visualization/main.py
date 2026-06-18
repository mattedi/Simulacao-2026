import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


# ------------------------------------------------------------------
# 1. MODEL SETTINGS EXTRACTOR
# ------------------------------------------------------------------
def extract_model_settings(file_path: Path) -> dict:
    """Read the 'MODEL SETTINGS' block from a NetLogo plot CSV and return a dict."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        lines = list(reader)

    settings = {}
    for i, row in enumerate(lines):
        if len(row) >= 1 and row[0].strip('"') == "MODEL SETTINGS":
            if i + 2 < len(lines):
                keys = [k.strip('"').strip() for k in lines[i + 1]]
                vals = [v.strip('"').strip() for v in lines[i + 2]]
                for k, v in zip(keys, vals):
                    if v.lower() == "true":
                        settings[k] = True
                    elif v.lower() == "false":
                        settings[k] = False
                    else:
                        try:
                            settings[k] = float(v) if "." in v else int(v)
                        except ValueError:
                            settings[k] = v
            break
    return settings


# ------------------------------------------------------------------
# 2. ROBUST PLOT PARSER (with optional pen renaming)
# ------------------------------------------------------------------
def read_netlogo_plot(name: str, rename_pens: dict = None) -> pd.DataFrame:
    """
    Parse a NetLogo plot CSV into a tidy DataFrame (columns: tick, pen1, pen2, ...).
    rename_pens: dict mapping original pen name -> new pen name (e.g. {"Panico": "Área do Fogo"})
    """
    file_path = Path("data") / f"{name}.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"Could not find {file_path.resolve()}")

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        lines = list(reader)

    data_header_idx = None
    for i, row in enumerate(lines):
        if len(row) >= 2 and row[0].strip('"') == "x" and "pen down?" in row:
            data_header_idx = i
            break

    if data_header_idx is None:
        raise ValueError("Could not locate the data header row in the CSV.")

    pen_row = lines[data_header_idx - 1]
    original_pens = [
        col.strip('"').strip() for col in pen_row if col.strip('"').strip()
    ]

    if rename_pens is None:
        rename_pens = {}
    pens = [rename_pens.get(p, p) for p in original_pens]

    df = pd.read_csv(file_path, skiprows=data_header_idx, quotechar='"')
    n_pens = len(pens)
    y_indices = [1 + 4 * i for i in range(n_pens)]

    df_clean = pd.DataFrame()
    df_clean["tick"] = pd.to_numeric(df.iloc[:, 0], errors="coerce")

    for pen, idx in zip(pens, y_indices):
        df_clean[pen] = pd.to_numeric(df.iloc[:, idx], errors="coerce")

    df_clean = df_clean.dropna(subset=["tick"]).reset_index(drop=True)
    df_clean = df_clean.ffill().fillna(0)
    return df_clean


# ------------------------------------------------------------------
# 3. INSIGHT COMPUTATION
# ------------------------------------------------------------------
def compute_insights(settings, df_evac, df_risk, df_fire):
    """Return a dictionary of computed metrics for plotting."""
    insights = {"settings": settings}

    # Evacuação
    if df_evac is not None and "Evacuados" in df_evac.columns:
        if "Feridos" in df_evac.columns and "Mortos" in df_evac.columns:
            df_evac["Total"] = (
                df_evac["Evacuados"] + df_evac["Feridos"] + df_evac["Mortos"]
            )
            total_agentes = df_evac["Total"].max()
            final = {
                "evac": df_evac["Evacuados"].iloc[-1],
                "fer": df_evac["Feridos"].iloc[-1],
                "mort": df_evac["Mortos"].iloc[-1],
            }
            insights["total_agentes"] = total_agentes
            insights["final"] = final

            t50 = df_evac["tick"][df_evac["Evacuados"] >= total_agentes * 0.5].min()
            t90 = df_evac["tick"][df_evac["Evacuados"] >= total_agentes * 0.9].min()
            insights["t50"] = None if np.isnan(t50) else t50
            insights["t90"] = None if np.isnan(t90) else t90

            if insights["t50"] is None:
                insights["evac_alert"] = "Menos de 50% dos ocupantes evacuados."
            elif insights["t90"] is None:
                insights["evac_alert"] = "Menos de 90% dos ocupantes evacuados."
            else:
                insights["evac_alert"] = None

    # Risco (pânico)
    if df_risk is not None:
        risk_pens = [c for c in df_risk.columns if c != "tick"]
        risk_max = {}
        risk_peak_time = {}
        for pen in risk_pens:
            risk_max[pen] = df_risk[pen].max()
            risk_peak_time[pen] = df_risk["tick"][df_risk[pen].idxmax()]
        insights["risk_pens"] = risk_pens
        insights["risk_max"] = risk_max
        insights["risk_peak_time"] = risk_peak_time

    # Fogo (área do fogo)
    if df_fire is not None:
        fire_pens = [c for c in df_fire.columns if c != "tick"]
        insights["fire_pens"] = fire_pens

    return insights


# ------------------------------------------------------------------
# 4. DASHBOARD PLOTTING (unchanged, except title includes run number)
# ------------------------------------------------------------------
def plot_insights_dashboard(
    insights, df_evac, df_risk, df_fire, output_path, run_label=""
):
    """Create a multi‑panel figure with all insights."""
    sns.set_theme(style="whitegrid")
    plt.rcParams["font.size"] = 10

    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.3)

    # Painel 1: Evacuação
    ax1 = fig.add_subplot(gs[0, 0])
    if df_evac is not None:
        for col in ["Evacuados", "Feridos", "Mortos"]:
            if col in df_evac.columns:
                ax1.plot(df_evac["tick"], df_evac[col], label=col, linewidth=2)
        ax1.set_title("Curva de Evacuação")
        ax1.set_xlabel("Tick")
        ax1.set_ylabel("Agentes")
        ax1.legend()
        if insights.get("t50"):
            ax1.axvline(insights["t50"], color="gray", linestyle="--", alpha=0.7)
            ax1.text(
                insights["t50"],
                ax1.get_ylim()[1] * 0.9,
                "50%",
                rotation=90,
                color="gray",
            )
        if insights.get("t90"):
            ax1.axvline(insights["t90"], color="gray", linestyle="--", alpha=0.7)
            ax1.text(
                insights["t90"],
                ax1.get_ylim()[1] * 0.9,
                "90%",
                rotation=90,
                color="gray",
            )
    else:
        ax1.text(0.5, 0.5, "Sem dados de evacuação", ha="center", va="center")

    # Painel 2: Pizza
    ax2 = fig.add_subplot(gs[0, 1])
    if "final" in insights:
        labels = ["Evacuados", "Feridos", "Mortos"]
        sizes = [
            insights["final"]["evac"],
            insights["final"]["fer"],
            insights["final"]["mort"],
        ]
        colors = ["#2ecc71", "#f39c12", "#e74c3c"]
        explode = (0, 0, 0.1)
        wedges, texts, autotexts = ax2.pie(
            sizes,
            explode=explode,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.7,
        )
        for t in autotexts:
            t.set_fontsize(9)
        ax2.set_title("Distribuição Final dos Ocupantes")
    else:
        ax2.text(0.5, 0.5, "Sem dados", ha="center", va="center")

    # Painel 3: Tempos críticos
    ax3 = fig.add_subplot(gs[0, 2])
    if insights.get("t50") is not None and insights.get("t90") is not None:
        categories = ["50% Evacuados", "90% Evacuados"]
        times = [insights["t50"], insights["t90"]]
        bars = ax3.bar(categories, times, color=["#3498db", "#9b59b6"], width=0.5)
        ax3.set_title("Tempos Críticos de Evacuação")
        ax3.set_ylabel("Ticks")
        for bar, val in zip(bars, times):
            ax3.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{val:.0f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    elif insights.get("t50") is not None and insights.get("t90") is None:
        categories = ["50% Evacuados"]
        times = [insights["t50"]]
        bars = ax3.bar(categories, times, color=["#3498db"], width=0.3)
        ax3.set_title("Tempo para 50% de Evacuação")
        ax3.set_ylabel("Ticks")
        ax3.text(0, times[0] + 1, f"{times[0]:.0f}", ha="center", va="bottom")
        ax3.text(
            0.5,
            0.5,
            "90% não atingido",
            ha="center",
            va="center",
            transform=ax3.transAxes,
            color="red",
            fontsize=9,
        )
    elif insights.get("total_agentes", 0) > 0:
        ax3.text(
            0.5,
            0.5,
            insights.get("evac_alert", "Menos de 50% evacuados"),
            ha="center",
            va="center",
            fontsize=11,
            color="red",
        )
        ax3.set_title("Tempos de Evacuação")
    else:
        ax3.text(0.5, 0.5, "Sem dados de evacuação", ha="center", va="center")

    # Painel 4: Risco (pânico)
    ax4 = fig.add_subplot(gs[1, 0])
    if df_risk is not None:
        risk_pens = insights.get("risk_pens", [])
        for pen in risk_pens:
            ax4.plot(df_risk["tick"], df_risk[pen], label=pen, linewidth=2)
        if risk_pens:
            max_risk = max(insights["risk_max"].values())
            high_thresh = 0.8 * max_risk
            ax4.axhline(
                high_thresh,
                color="red",
                linestyle=":",
                alpha=0.7,
                label=f"Alto risco (> {high_thresh:.2f})",
            )
            high_risk_mask = df_risk[risk_pens].max(axis=1) >= high_thresh
            ax4.fill_between(
                df_risk["tick"],
                0,
                df_risk[risk_pens].max(axis=1),
                where=high_risk_mask,
                color="red",
                alpha=0.1,
                label="Período crítico",
            )
        ax4.set_title("Indicadores de Risco (Pânico)")
        ax4.set_xlabel("Tick")
        ax4.set_ylabel("Nível")
        ax4.legend(fontsize=8)
    else:
        ax4.text(0.5, 0.5, "Sem dados de risco", ha="center", va="center")

    # Painel 5: Progressão do Fogo
    ax5 = fig.add_subplot(gs[1, 1])
    if df_fire is not None:
        fire_pens = insights.get("fire_pens", [])
        for pen in fire_pens:
            ax5.plot(
                df_fire["tick"],
                df_fire[pen],
                label=pen,
                linewidth=2,
                color="darkorange",
            )
        ax5.set_title("Progressão da Área do Fogo")
        ax5.set_xlabel("Tick")
        ax5.set_ylabel("Área / Intensidade")
        ax5.legend()
    else:
        ax5.text(0.5, 0.5, "Sem dados de fogo", ha="center", va="center")

    # Painel 6: Evacuação vs Risco
    ax6 = fig.add_subplot(gs[1, 2])
    if (
        df_evac is not None
        and "Evacuados" in df_evac.columns
        and insights.get("total_agentes", 0) > 0
    ):
        pct_evac = df_evac["Evacuados"] / insights["total_agentes"] * 100
        ax6.plot(
            df_evac["tick"], pct_evac, color="green", linewidth=2, label="% Evacuados"
        )
        ax6.set_ylabel("% Evacuados", color="green")
        ax6.tick_params(axis="y", labelcolor="green")
        ax6.set_xlabel("Tick")
        ax6.set_title("Progresso da Evacuação vs Risco")
        if df_risk is not None and insights.get("risk_pens"):
            ax6b = ax6.twinx()
            risk_pen = insights["risk_pens"][0]
            ax6b.plot(
                df_risk["tick"],
                df_risk[risk_pen],
                color="red",
                linewidth=2,
                linestyle="--",
                label=risk_pen,
            )
            ax6b.set_ylabel(f"Nível de {risk_pen}", color="red")
            ax6b.tick_params(axis="y", labelcolor="red")
        lines1, labels1 = ax6.get_legend_handles_labels()
        lines2, labels2 = (
            ax6b.get_legend_handles_labels() if "ax6b" in locals() else ([], [])
        )
        ax6.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)
    else:
        ax6.text(0.5, 0.5, "Sem dados", ha="center", va="center")

    # Título geral
    settings_str = ", ".join([f"{k}={v}" for k, v in insights["settings"].items()])
    run_info = f" – Execução {run_label}" if run_label else ""
    fig.suptitle(
        f"Análise da Simulação{run_info} – Configurações: {settings_str}",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )

    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"\n📊 Dashboard salvo em: {output_path.resolve()}")
    plt.close()


# ------------------------------------------------------------------
# 5. FILE DISCOVERY & GROUPING
# ------------------------------------------------------------------
def discover_runs(data_dir: Path):
    """
    Scan the data directory and group files by their numeric suffix.
    Returns a dict: { '01': {'ev': path, 'risk': path, 'fire': path}, ... }
    Only files matching ev##.csv, risk##.csv, fire##.csv are considered.
    """
    runs = {}
    pattern = re.compile(r"^(ev|risk|fire)(\d+)\.csv$")
    for f in data_dir.glob("*.csv"):
        m = pattern.match(f.name)
        if m:
            prefix = m.group(1)  # 'ev', 'risk', or 'fire'
            suffix = m.group(2)  # e.g., '02'
            if suffix not in runs:
                runs[suffix] = {}
            if prefix == "ev":
                runs[suffix]["ev"] = f
            elif prefix == "risk":
                runs[suffix]["risk"] = f
            elif prefix == "fire":
                runs[suffix]["fire"] = f
    # Sort by suffix for consistent processing
    return dict(sorted(runs.items()))


# ------------------------------------------------------------------
# 6. PIPELINE MAIN
# ------------------------------------------------------------------
def main():
    data_dir = Path("data")
    runs = discover_runs(data_dir)

    if not runs:
        print(
            "Nenhum arquivo no padrão esperado (ev##.csv, risk##.csv, fire##.csv) encontrado em data/"
        )
        return

    print(f"Encontradas {len(runs)} execuções: {', '.join(runs.keys())}")

    for run_label, file_dict in runs.items():
        print(f"\n{'=' * 50}")
        print(f" Processando execução {run_label} ".center(50, "="))

        # Extract settings from any available file for this run (prefer ev)
        settings_file = (
            file_dict.get("ev") or file_dict.get("risk") or file_dict.get("fire")
        )
        if settings_file is None:
            print("  Nenhum arquivo disponível para esta execução. Pulando.")
            continue
        settings = extract_model_settings(settings_file)

        # Load data (parse only existing files)
        ev_path = file_dict.get("ev")
        risk_path = file_dict.get("risk")
        fire_path = file_dict.get("fire")

        # We need to pass the base name (without extension) to read_netlogo_plot
        # We'll extract it from the path stem.
        df_evac = read_netlogo_plot(ev_path.stem) if ev_path else None
        df_risk = read_netlogo_plot(risk_path.stem) if risk_path else None
        df_fire = None
        if fire_path:
            # Rename 'Panico' to 'Área do Fogo' only for fire files
            fire_rename = {"Panico": "Área do Fogo"}
            df_fire = read_netlogo_plot(fire_path.stem, rename_pens=fire_rename)

        # Compute insights
        insights = compute_insights(settings, df_evac, df_risk, df_fire)

        # Textual summary (optional)
        if "final" in insights:
            print(f"  Ocupantes totais: {int(insights['total_agentes'])}")
            print(
                f"  Evacuados: {insights['final']['evac']:.0f} "
                f"({insights['final']['evac'] / insights['total_agentes'] * 100:.1f}%)"
            )
            if insights.get("t50"):
                print(f"  Tempo 50% evacuação: {insights['t50']:.0f} ticks")
            else:
                print("  ⚠️  Menos de 50% dos ocupantes evacuados.")
        if "risk_max" in insights:
            print("  Riscos máximos:")
            for pen, val in insights["risk_max"].items():
                print(
                    f"    {pen}: {val:.4f} (tick {insights['risk_peak_time'][pen]:.0f})"
                )

        # Generate dashboard for this run
        output_img = data_dir / f"analysis_run_{run_label}.png"
        plot_insights_dashboard(
            insights, df_evac, df_risk, df_fire, output_img, run_label
        )


if __name__ == "__main__":
    main()
