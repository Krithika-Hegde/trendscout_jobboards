import json
import csv
from pathlib import Path
from collections import Counter

from config import PROCESSED_DIR

INPUT_QA = PROCESSED_DIR / "qa_evaluation.json"
OUTPUT_METRICS = PROCESSED_DIR / "qa_metrics.json"
OUTPUT_REPORT = PROCESSED_DIR / "qa_report.md"


def load_qa_results():
    with INPUT_QA.open("r", encoding="utf-8") as f:
        return json.load(f)


def compute_metrics(results):
    if not results:
        return {}

    scores = [r["score"] for r in results]
    matched_terms_counts = [len(r["matched_terms"].split(", ")) if r["matched_terms"] else 0 for r in results]

    metrics = {
        "total_questions": len(results),
        "avg_score": sum(scores) / len(scores),
        "max_score": max(scores),
        "min_score": min(scores),
        "zero_score_count": sum(1 for s in scores if s == 0),
        "avg_matched_terms": sum(matched_terms_counts) / len(matched_terms_counts),
        "score_distribution": dict(Counter(scores)),
    }

    # Top companies and locations from answers
    companies = [r["company"] for r in results if r["company"]]
    locations = [r["location"] for r in results if r["location"]]

    metrics["top_companies"] = dict(Counter(companies).most_common(5))
    metrics["top_locations"] = dict(Counter(locations).most_common(5))

    return metrics


def generate_report(metrics, results):
    report = f"""# QA Evaluation Report

## Overview
- Total questions evaluated: {metrics['total_questions']}
- Average retrieval score: {metrics['avg_score']:.2f}
- Questions with zero matches: {metrics['zero_score_count']}

## Score Distribution
{chr(10).join(f"- Score {score}: {count} questions" for score, count in metrics['score_distribution'].items())}

## Top Companies in Answers
{chr(10).join(f"- {company}: {count}" for company, count in metrics['top_companies'].items())}

## Top Locations in Answers
{chr(10).join(f"- {location}: {count}" for location, count in metrics['top_locations'].items())}

## Sample Results
"""

    for i, result in enumerate(results[:5]):  # First 5 samples
        report += f"""
### Question {result['question_id']}
**Q:** {result['question']}
**Answer:** {result['answer'][:200]}...
**Score:** {result['score']}
**Matched Terms:** {result['matched_terms']}
**Source:** {result['company']} - {result['title']}
"""

    return report


def save_metrics_and_report():
    results = load_qa_results()
    metrics = compute_metrics(results)

    with OUTPUT_METRICS.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    report = generate_report(metrics, results)
    with OUTPUT_REPORT.open("w", encoding="utf-8") as f:
        f.write(report)

    print(f"Saved metrics to {OUTPUT_METRICS}")
    print(f"Saved report to {OUTPUT_REPORT}")


if __name__ == "__main__":
    save_metrics_and_report()
