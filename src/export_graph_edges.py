import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import pandas as pd
import ast
from config import PROCESSED_DIR, OUTPUT_DIR

def parse_skills(x):
    if pd.isna(x):
        return []
    try:
        return ast.literal_eval(x)
    except Exception:
        return []

def main():
    df = pd.read_csv(PROCESSED_DIR / "jobs_enriched.csv")
    df["skills"] = df["skills"].apply(parse_skills)

    edges = []

    for _, row in df.iterrows():
        company = row.get("company")
        role = row.get("title")
        location = row.get("location")
        skills = row.get("skills", [])

        if pd.notna(company) and pd.notna(role):
            edges.append({
                "source": company,
                "relationship": "HIRING_FOR",
                "target": role
            })

        if pd.notna(company) and pd.notna(location):
            edges.append({
                "source": company,
                "relationship": "LOCATED_IN",
                "target": location
            })

        for skill in skills:
            if pd.notna(role):
                edges.append({
                    "source": role,
                    "relationship": "REQUIRES",
                    "target": skill
                })
            if pd.notna(company):
                edges.append({
                    "source": company,
                    "relationship": "USES_TECH",
                    "target": skill
                })

    edges_df = pd.DataFrame(edges).drop_duplicates()
    edges_df.to_csv(OUTPUT_DIR / "job_graph_edges.csv", index=False)
    print("Saved job_graph_edges.csv")

if __name__ == "__main__":
    main()