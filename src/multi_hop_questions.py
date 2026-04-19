import json
from pathlib import Path

from config import PROCESSED_DIR

OUTPUT_FILE = PROCESSED_DIR / "multi_hop_questions.json"

QUESTIONS = [
    {
        "id": 1,
        "question": "Which companies are hiring for roles with titles containing 'Machine Learning' and that require Python in the description?",
        "notes": "Combine title keywords with technical skill requirements."
    },
    {
        "id": 2,
        "question": "Which job openings located in a U.S. city require both Kubernetes and cloud architecture skills?",
        "notes": "Requires matching location, skills, and infrastructure-related terms."
    },
    {
        "id": 3,
        "question": "Which job postings have a role category containing 'Data' and mention ETL or pipeline experience in the description?",
        "notes": "Requires role category and description-based skill inference."
    },
    {
        "id": 4,
        "question": "Which companies are hiring for roles that mention both research and production in the description?",
        "notes": "Requires combining descriptive language with employer names."
    },
    {
        "id": 5,
        "question": "Which job titles mention 'Infrastructure' and require CI/CD or DevOps experience?",
        "notes": "Combine title semantics with specific operational skills."
    },
    {
        "id": 6,
        "question": "Which locations host jobs that require both model evaluation and benchmarking experience?",
        "notes": "Requires a location-based aggregation of related skill requirements."
    },
    {
        "id": 7,
        "question": "Which companies have open roles that list remote-friendly locations and also list AI or machine learning skills?",
        "notes": "Combine location modality with domain-specific technical skills."
    },
    {
        "id": 8,
        "question": "Which jobs include both security/privacy related terms and are in engineering role categories?",
        "notes": "Requires matching named entity or description terms with role category."
    },
    {
        "id": 9,
        "question": "Which companies are recruiting for senior-level positions that also reference distributed systems or large-scale systems?",
        "notes": "Combine seniority indicators with system architecture language."
    },
    {
        "id": 10,
        "question": "Which job postings are full-time and list either Kubernetes or Docker as required skills?",
        "notes": "Combine employment type with container/orchestration skill requirements."
    },
    {
        "id": 11,
        "question": "Which job titles include platform or infrastructure and also require cloud or AWS experience?",
        "notes": "Combine platform-level titles with cloud skill sets."
    },
    {
        "id": 12,
        "question": "Which companies have roles in the same city for both software engineering and data engineering teams?",
        "notes": "Requires comparing company, location, and role category across openings."
    },
    {
        "id": 13,
        "question": "Which jobs mention both automation and observability in the same description?",
        "notes": "Combines multiple operational proficiency terms within one posting."
    },
    {
        "id": 14,
        "question": "Which companies are hiring for roles that require technical writing or documentation and also involve developer tools?",
        "notes": "Combine communication requirements with engineering tool expertise."
    },
    {
        "id": 15,
        "question": "Which job postings mention both collaboration/teamwork and product or research orientation in the description?",
        "notes": "Combine teamwork language with product or research context."
    }
]


def save_questions():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as output:
        json.dump(QUESTIONS, output, ensure_ascii=False, indent=2)
    print(f"Saved {len(QUESTIONS)} multi-hop questions to {OUTPUT_FILE}")


if __name__ == "__main__":
    save_questions()
