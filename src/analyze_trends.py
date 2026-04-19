import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import ast
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
from config import PROCESSED_DIR, OUTPUT_DIR

def parse_skill_list(x):
    if pd.isna(x):
        return []
    if isinstance(x, list):
        return x
    try:
        return ast.literal_eval(x)
    except Exception:
        return []

def main():
    df = pd.read_csv(PROCESSED_DIR / "jobs_enriched.csv")

    company_counts = df["company"].dropna().value_counts().head(15).reset_index()
    company_counts.columns = ["company", "job_count"]
    company_counts.to_csv(OUTPUT_DIR / "top_hiring_companies.csv", index=False)

    role_counts = df["role_category"].dropna().value_counts().reset_index()
    role_counts.columns = ["role_category", "count"]
    role_counts.to_csv(OUTPUT_DIR / "top_role_categories.csv", index=False)

    location_counts = df["location"].dropna().value_counts().head(15).reset_index()
    location_counts.columns = ["location", "count"]
    location_counts.to_csv(OUTPUT_DIR / "top_locations.csv", index=False)

    df["skills"] = df["skills"].apply(parse_skill_list)
    skill_counter = Counter()
    for row in df["skills"]:
        skill_counter.update(row)

    skill_df = pd.DataFrame(skill_counter.most_common(20), columns=["skill", "count"])
    skill_df.to_csv(OUTPUT_DIR / "top_skills.csv", index=False)

    role_counts.plot(kind="bar", x="role_category", y="count", legend=False, figsize=(10, 6))
    plt.title("Top Role Categories")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "top_role_categories.png")
    plt.close()

    skill_df.plot(kind="bar", x="skill", y="count", legend=False, figsize=(10, 6))
    plt.title("Top Skills")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "top_skills.png")
    plt.close()

    print("Trend analysis complete.")
    
if __name__ == "__main__":
    main()