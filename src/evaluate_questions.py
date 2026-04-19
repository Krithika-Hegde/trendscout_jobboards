import csv
import json
import re
from pathlib import Path

from config import PROCESSED_DIR

INPUT_QUESTIONS = PROCESSED_DIR / "multi_hop_questions.json"
INPUT_CHUNKS = PROCESSED_DIR / "chroma_chunks.csv"
OUTPUT_JSON = PROCESSED_DIR / "qa_evaluation.json"
OUTPUT_CSV = PROCESSED_DIR / "qa_evaluation.csv"

STOPWORDS = {
    "which", "what", "who", "where", "when", "why", "how",
    "the", "and", "or", "also", "for", "that", "with", "both",
    "in", "on", "of", "to", "a", "an", "is", "are", "as",
    "from", "same", "each", "has", "have", "requiring", "require",
    "role", "roles", "role",
}


def normalize_text(text):
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    return [word.lower() for word in re.findall(r"\w+", normalize_text(text)) if word.lower() not in STOPWORDS]


def load_chunks():
    chunks = []
    with INPUT_CHUNKS.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            chunks.append({
                "chunk_id": row.get("chunk_id", ""),
                "job_url": row.get("job_url", ""),
                "company": row.get("company", ""),
                "title": row.get("title", ""),
                "location": row.get("location", ""),
                "role_category": row.get("role_category", ""),
                "skills": row.get("skills", ""),
                "named_entities": row.get("named_entities", ""),
                "chunk_text": normalize_text(row.get("chunk_text", "")),
            })
    return chunks


def score_chunk(question_terms, chunk):
    text = " ".join([
        chunk["company"], chunk["title"], chunk["location"], chunk["role_category"], chunk["skills"], chunk["chunk_text"]
    ]).lower()
    score = 0
    matched = set()
    for term in question_terms:
        if term in text:
            score += 1
            matched.add(term)
    return score, sorted(matched)


def answer_questions():
    if not INPUT_QUESTIONS.exists():
        raise FileNotFoundError(f"Missing questions file: {INPUT_QUESTIONS}")
    if not INPUT_CHUNKS.exists():
        raise FileNotFoundError(f"Missing chunks file: {INPUT_CHUNKS}")

    with INPUT_QUESTIONS.open("r", encoding="utf-8") as f:
        questions = json.load(f)

    chunks = load_chunks()
    if not chunks:
        raise ValueError("No chunks loaded from input data.")

    results = []
    for question in questions:
        question_id = question.get("id")
        text = question.get("question", "")
        terms = tokenize(text)

        scored = []
        for chunk in chunks:
            score, matches = score_chunk(terms, chunk)
            if score > 0:
                scored.append((score, matches, chunk))

        scored.sort(key=lambda item: (-item[0], item[2].get("chunk_id", "")))

        top_hit = scored[0] if scored else (0, [], chunks[0])
        score, matched_terms, best_chunk = top_hit
        answer = normalize_text(best_chunk.get("chunk_text", ""))
        if len(answer) > 500:
            answer = answer[:500].rsplit(" ", 1)[0] + "..."

        result = {
            "question_id": question_id,
            "question": text,
            "answer": answer,
            "score": score,
            "matched_terms": ", ".join(matched_terms),
            "chunk_id": best_chunk.get("chunk_id"),
            "job_url": best_chunk.get("job_url"),
            "company": best_chunk.get("company"),
            "title": best_chunk.get("title"),
            "location": best_chunk.get("location"),
        }
        results.append(result)

    with OUTPUT_JSON.open("w", encoding="utf-8") as out_json:
        json.dump(results, out_json, ensure_ascii=False, indent=2)

    headers = [
        "question_id", "question", "answer", "score", "matched_terms",
        "chunk_id", "job_url", "company", "title", "location"
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as out_csv:
        writer = csv.DictWriter(out_csv, fieldnames=headers)
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved {len(results)} question answers to {OUTPUT_JSON}")
    print(f"Saved {len(results)} question answers to {OUTPUT_CSV}")


if __name__ == "__main__":
    answer_questions()
