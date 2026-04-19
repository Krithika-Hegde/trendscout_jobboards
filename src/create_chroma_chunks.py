import csv
import json
import re
from pathlib import Path

from config import PROCESSED_DIR

INPUT_FILE = PROCESSED_DIR / "jobs_enriched.json"
OUTPUT_JSONL = PROCESSED_DIR / "chroma_chunks.jsonl"
OUTPUT_CSV = PROCESSED_DIR / "chroma_chunks.csv"

MAX_CHARS = 800
MIN_CHARS = 250


def normalize_text(text):
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_long_text(text, max_chars=MAX_CHARS):
    parts = []
    current = []
    current_len = 0

    for word in text.split():
        part_len = len(word) + 1
        if current_len + part_len > max_chars and current:
            parts.append(" ".join(current).strip())
            current = [word]
            current_len = len(word) + 1
        else:
            current.append(word)
            current_len += part_len

    if current:
        parts.append(" ".join(current).strip())

    return parts


def split_paragraph(paragraph, max_chars=MAX_CHARS):
    if len(paragraph) <= max_chars:
        return [paragraph]

    chunks = []
    current = []
    current_len = 0

    for sentence in re.split(r"(?<=[.?!])\s+", paragraph):
        sentence = sentence.strip()
        if not sentence:
            continue

        if current_len + len(sentence) + 1 <= max_chars:
            current.append(sentence)
            current_len += len(sentence) + 1
            continue

        if current:
            chunks.append(" ".join(current).strip())
        if len(sentence) <= max_chars:
            current = [sentence]
            current_len = len(sentence) + 1
        else:
            chunks.extend(split_long_text(sentence, max_chars=max_chars))
            current = []
            current_len = 0

    if current:
        chunks.append(" ".join(current).strip())

    return chunks


def chunk_text(text, max_chars=MAX_CHARS, min_chars=MIN_CHARS):
    text = normalize_text(text)
    if not text:
        return []

    paragraphs = [normalize_text(p) for p in re.split(r"\n{2,}", text) if normalize_text(p)]
    chunks = []

    for paragraph in paragraphs:
        chunks.extend(split_paragraph(paragraph, max_chars=max_chars))

    merged = []
    for chunk in chunks:
        if merged and len(merged[-1]) < min_chars and len(merged[-1]) + len(chunk) + 1 <= max_chars:
            merged[-1] = f"{merged[-1]} {chunk}"
        else:
            merged.append(chunk)

    return merged


def job_text(job):
    title = normalize_text(job.get("title"))
    company = normalize_text(job.get("company"))
    location = normalize_text(job.get("location"))
    description = normalize_text(job.get("description"))

    header = " | ".join(part for part in [title, company, location] if part)
    if header and description:
        return f"{header}\n\n{description}"
    return description or header


def build_rows(job_idx, job):
    job_url = job.get("job_url")
    company = normalize_text(job.get("company"))
    title = normalize_text(job.get("title"))
    location = normalize_text(job.get("location"))
    role_category = normalize_text(job.get("role_category"))
    skills = job.get("skills") or []
    named_entities = job.get("named_entities") or []
    content = job_text(job)

    if not content:
        return []

    chunks = chunk_text(content)
    if not chunks:
        return []

    base_id = job_url.split("/")[-1] if job_url else str(job_idx)
    rows = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_id = f"{base_id}-{idx}"
        rows.append({
            "chunk_id": chunk_id,
            "job_idx": job_idx,
            "job_url": job_url,
            "company": company,
            "title": title,
            "location": location,
            "role_category": role_category,
            "skills": ", ".join(skills) if isinstance(skills, list) else normalize_text(skills),
            "named_entities": json.dumps(named_entities, ensure_ascii=False),
            "chunk_index": idx,
            "chunk_text": chunk,
        })
    return rows


def build_chunks():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        jobs = json.load(f)

    rows = []
    for job_idx, job in enumerate(jobs, start=1):
        rows.extend(build_rows(job_idx, job))

    headers = [
        "chunk_id",
        "job_idx",
        "job_url",
        "company",
        "title",
        "location",
        "role_category",
        "skills",
        "named_entities",
        "chunk_index",
        "chunk_text",
    ]

    with OUTPUT_JSONL.open("w", encoding="utf-8") as out_jsonl:
        for row in rows:
            out_jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as out_csv:
        writer = csv.DictWriter(out_csv, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} chunks to {OUTPUT_JSONL}")
    print(f"Saved {len(rows)} chunks to {OUTPUT_CSV}")


if __name__ == "__main__":
    build_chunks()
