"""Telco customer churn: data cleaning and analysis pipeline.

Turns the raw IBM Telco Customer Churn CSV into the two analysis-ready
datasets used by the rest of the project:

* Version 1 (``telco_churn_v1_clean.csv``): cleaned and enriched, still
  human-readable. Used for visualisation in Excel.
* Version 2 (``telco_churn_v2_correlation.csv``): fully numeric, one-hot
  encoded. Used for the correlation analysis against churn.

It also saves the correlation-with-churn bar chart.

Run from the repository root:

    python src/pipeline.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
OUT_DIR = ROOT / "data" / "processed"
CHART_PATH = ROOT / "images" / "correlation_with_churn.png"

CONTRACT_MONTHS = {"Month-to-month": 1, "One year": 12, "Two year": 24}
AUTO_PAYMENT_METHODS = {"Bank transfer (automatic)", "Credit card (automatic)"}
SERVICE_COLUMNS = {
    "OnlineSecurity": "online_security",
    "OnlineBackup": "online_backup",
    "DeviceProtection": "device_protection",
    "TechSupport": "tech_support",
    "StreamingTV": "streaming_tv",
    "StreamingMovies": "streaming_movies",
}


def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    """Read the raw CSV, keeping TotalCharges as text so blanks can be found."""
    return pd.read_csv(path, dtype={"TotalCharges": str})


def build_v1(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean and enrich the raw data (Version 1)."""
    df = raw.copy()

    # Contract length in months, placed next to Contract.
    df.insert(df.columns.get_loc("Contract") + 1, "contract_month",
              df["Contract"].map(CONTRACT_MONTHS))

    # Whether the customer pays automatically, placed next to PaperlessBilling.
    df.insert(df.columns.get_loc("PaperlessBilling") + 1, "auto_bill",
              df["PaymentMethod"].isin(AUTO_PAYMENT_METHODS).map({True: "Yes", False: "No"}))

    # SeniorCitizen as Yes/No instead of 1/0.
    df["senior_yes"] = df["SeniorCitizen"].map({0: "No", 1: "Yes"})

    # Collapse "No phone service" / "No internet service" into plain "No".
    df["multiple_lines"] = df["MultipleLines"].replace("No phone service", "No")
    for source, target in SERVICE_COLUMNS.items():
        df[target] = df[source].replace("No internet service", "No")

    # Shorter payment method labels.
    df["payment_method"] = df["PaymentMethod"].str.replace(" (automatic)", "", regex=False)

    # 11 customers have a blank TotalCharges (all with tenure 0): set them to 0.
    df["total_charges"] = pd.to_numeric(df["TotalCharges"].str.strip().replace("", "0"))

    return df


def build_v2(v1: pd.DataFrame) -> pd.DataFrame:
    """Numeric, one-hot encoded dataset for correlation analysis (Version 2)."""
    df = v1.copy()
    df["Churn"] = df["Churn"].map({"No": 0, "Yes": 1})

    df = df.drop(columns=[
        "customerID", "SeniorCitizen", "multiple_lines", "online_security",
        "online_backup", "OnlineBackup", "device_protection", "tech_support",
        "streaming_tv", "streaming_movies", "contract_month", "PaymentMethod",
        "TotalCharges",
    ])

    # Binary-style categoricals: keep one indicator column each.
    keep_numeric = ["Churn", "tenure", "MonthlyCharges", "total_charges"]
    multi_class = ["gender", "InternetService", "Contract", "payment_method"]
    binary_like = [c for c in df.columns if c not in keep_numeric + multi_class]
    df = pd.get_dummies(df, columns=binary_like, drop_first=True)

    # Multi-class categoricals: keep every level so each can be compared.
    df = pd.get_dummies(df, columns=multi_class, drop_first=False)

    dummy_cols = df.columns.difference(keep_numeric)
    df[dummy_cols] = df[dummy_cols].astype(int)
    return df.rename(columns={"senior_yes_Yes": "senior_Yes"})


def save_correlation_chart(v2: pd.DataFrame, path: Path = CHART_PATH) -> pd.Series:
    """Plot each feature's correlation with churn and save it as a PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    corr = v2.corr()["Churn"].drop("Churn").sort_values(ascending=False)
    colors = plt.get_cmap("plasma")(np.linspace(0, 1, len(corr)))

    fig, ax = plt.subplots(figsize=(15, 6))
    corr.plot(kind="bar", color=colors, ax=ax)
    ax.set_title("Correlation of each feature with churn")
    ax.set_ylabel("Pearson correlation")
    ax.axhline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return corr


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    raw = load_raw(args.raw)
    v1 = build_v1(raw)
    v2 = build_v2(v1)

    args.out.mkdir(parents=True, exist_ok=True)
    v1.to_csv(args.out / "telco_churn_v1_clean.csv", index=False)
    v2.to_csv(args.out / "telco_churn_v2_correlation.csv", index=False)
    corr = save_correlation_chart(v2)

    print(f"Raw rows: {len(raw):,} | V1 columns: {v1.shape[1]} | V2 columns: {v2.shape[1]}")
    print(f"Churn rate: {v2['Churn'].mean():.1%}")
    print("Top 3 positive correlations with churn:")
    print(corr.head(3).round(2).to_string())
    print("Top 3 negative correlations with churn:")
    print(corr.tail(3).round(2).to_string())


if __name__ == "__main__":
    main()
