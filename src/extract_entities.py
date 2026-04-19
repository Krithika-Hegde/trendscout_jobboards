import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import pandas as pd
import spacy
from config import PROCESSED_DIR

nlp = spacy.load("en_core_web_sm")

SKILL_KEYWORDS = [
    "python", "pytorch", "tensorflow", "llm", "rag", "nlp", "machine learning",
    "deep learning", "sql", "aws", "gcp", "azure", "docker", "kubernetes",
    "javascript", "react", "node", "java", "c++", "scala", "spark", "airflow"
]

def extract_skills(text):
    if not isinstance(text, str):
        return []
    text_lower = text.lower()
    found = [skill for skill in SKILL_KEYWORDS if skill in text_lower]
    return sorted(set(found))

def extract_named_entities(text):
    if not isinstance(text, str) or not text.strip():
        return []
    doc = nlp(text[:5000])
    return [(ent.text, ent.label_) for ent in doc.ents]

def main():
    df = pd.read_csv(PROCESSED_DIR / "jobs_master.csv")

    df["skills"] = (df["title"].fillna("") + " " + df["description"].fillna(""))
    df["skills"] = df["skills"].apply(extract_skills)
    df["named_entities"] = df["description"].apply(extract_named_entities)

    df.to_csv(PROCESSED_DIR / "jobs_enriched.csv", index=False)
    df.to_json(PROCESSED_DIR / "jobs_enriched.json", orient="records", indent=2)

    print("Saved enriched jobs data.")

if __name__ == "__main__":
    main()