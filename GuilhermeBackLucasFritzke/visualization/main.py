from pathlib import Path

import pandas as pd


def read_csv(name: str, skiprows: int, quotechar: str) -> pd.DataFrame:
    p = Path(".")
    file_path = p / "data" / f"{name}.csv"

    if not file_path.exists():
        raise FileNotFoundError(
            f"Could not find the NetLogo file at: {file_path.resolve()}"
        )

    return pd.read_csv(file_path, skiprows=skiprows, quotechar=quotechar)


def main():
    df = read_csv("ev01", skiprows=18, quotechar='"')

    xy_cols = [col for col in df.columns if col.startswith("x") or col.startswith("y")]
    df_xy = df[xy_cols].copy()

    pens = ["Evacuados", "Feridos", "Mortos"]
    new_cols = []
    for pen in pens:
        new_cols.extend([f"{pen}_x", f"{pen}_y"])

    df_xy.columns = new_cols

    # df_xy.columns = new_cols
    print(df_xy)


if __name__ == "__main__":
    main()
