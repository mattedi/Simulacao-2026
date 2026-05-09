from pathlib import Path

import pandas as pd

METADATA_DIR = Path("./metadata")
OUTPUT_FILE = "result.csv"
CURRENT_YEAR = 2026


def process_file(file_path: Path) -> pd.DataFrame:
    name = file_path.name.lower()
    source_name = ""
    if "ieee" in name:
        source_name = "IEEE"
        df = pd.read_csv(file_path)
        mapping = {
            "article citation count": "citations",
            "publication year": "year",
            "document title": "title",
            "doi": "doi",
        }
    elif "web" in name:
        source_name = "Web"
        df = pd.read_excel(file_path)
        mapping = {
            "times cited, all databases": "citations",
            "publication year": "year",
            "article title": "title",
            "doi": "doi",
        }
    elif "scopus" in name:
        df = pd.read_csv(file_path)
        source_name = "Scopus"
        mapping = {
            "cited by": "citations",
            "year": "year",
            "title": "title",
            "doi": "doi",
        }
    else:
        return pd.DataFrame()

    df.columns = df.columns.str.strip().str.lower()

    existing_cols = [col for col in mapping.keys() if col in df.columns]
    df = df[existing_cols].rename(columns=mapping)  # pyright: ignore[reportCallIssue]
    df["source"] = source_name

    return df


def main():
    if not METADATA_DIR.exists():
        print(f"Error: Directory {METADATA_DIR} not found.")
        return

    # 1. Collect all data
    all_dfs = [process_file(f) for f in METADATA_DIR.iterdir() if f.is_file()]
    if not all_dfs:
        print("No valid files found.")
        return

    # 2. Combine and Clean
    df = pd.concat(all_dfs, ignore_index=True)

    df["citations"] = pd.to_numeric(df["citations"], errors="coerce")
    df["citations"] = df["citations"].fillna(0)

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["doi"] = df["doi"].astype(str).str.strip().str.lower()

    # Calculate Impact Score
    df["impact"] = df["citations"] / (CURRENT_YEAR - df["year"] + 1)

    # Remove Duplicates & Sort
    df = df.sort_values(by="impact", ascending=False)
    df = df.drop_duplicates(subset="doi", keep="first")

    # Count removed dups
    counts = df["source"].value_counts()
    print("\nQuantidade de artigos únicos por fonte (PRISMA):")
    print(counts)
    print(f"Total: {counts.sum()}")

    top_15 = df.head(15)
    top_15.to_csv(OUTPUT_FILE, index=False)
    print(f"Success! Top 15 results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
