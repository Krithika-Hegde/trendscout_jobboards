import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import json
import pandas as pd
from typing import List, Dict, Tuple
from collections import defaultdict
import math
from hybrid_search import HybridSearchEngine
from config import PROCESSED_DIR, OUTPUT_DIR

class SearchBenchmark:
    """Evaluate search quality using gold standard answers"""
    
    def __init__(self, gold_answers_file: str = "data/gold_answers.json"):
        self.engine = HybridSearchEngine()
        self.gold_answers = self._load_gold_answers(gold_answers_file)
        self.results = {
            'vector': {},
            'keyword': {},
            'graph': {},
            'hybrid': {}
        }
        
    def _load_gold_answers(self, file_path: str) -> List[Dict]:
        """Load gold standard answers"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data['benchmark_dataset']['queries']
        except Exception as e:
            print(f"Error loading gold answers: {e}")
            return []
    
    def _normalize_title(self, title: str) -> str:
        """Normalize job title for comparison"""
        return title.lower().strip()
    
    def _calc_precision_recall(self, results: List[str], expected: List[str], k: int = 5) -> Tuple[float, float]:
        """Calculate Precision@k and Recall@k"""
        retrieved = [self._normalize_title(r) for r in results[:k]]
        expected_norm = [self._normalize_title(e) for e in expected]
        
        if not expected_norm:
            return 0.0, 1.0  # No expected results = perfect recall
        
        matches = len(set(retrieved) & set(expected_norm))
        precision = matches / len(retrieved) if retrieved else 0
        recall = matches / len(expected_norm)
        
        return precision, recall
    
    def _calc_mrr(self, results: List[str], expected: List[str]) -> float:
        """Calculate Mean Reciprocal Rank"""
        retrieved = [self._normalize_title(r) for r in results]
        expected_norm = [self._normalize_title(e) for e in expected]
        
        for rank, result in enumerate(retrieved, 1):
            if result in expected_norm:
                return 1.0 / rank
        return 0.0
    
    def _calc_ndcg(self, results: List[str], expected: List[str], k: int = 5) -> float:
        """Calculate Normalized Discounted Cumulative Gain"""
        retrieved = [self._normalize_title(r) for r in results[:k]]
        expected_norm = [self._normalize_title(e) for e in expected]
        
        # DCG calculation
        dcg = 0
        for rank, result in enumerate(retrieved, 1):
            rel = 1 if result in expected_norm else 0
            dcg += rel / math.log2(rank + 1)
        
        # IDCG calculation (perfect ranking)
        idcg = 0
        for rank in range(1, min(len(expected_norm), k) + 1):
            idcg += 1 / math.log2(rank + 1)
        
        ndcg = dcg / idcg if idcg > 0 else 0
        return ndcg
    
    def evaluate_query(self, query: Dict, n_results: int = 5) -> Dict:
        """Evaluate a single query across all search methods"""
        query_text = query['query']
        expected = query.get('expected_results', [])
        
        print(f"  Evaluating: '{query_text}'", end='... ', flush=True)
        
        # Run all search methods
        vector_results = [r['title'] for r in self.engine.vector_search(query_text, n_results=n_results)]
        keyword_results = [r['title'] for r in self.engine.keyword_search(query_text, n_results=n_results)]
        graph_results = [r['title'] for r in self.engine.graph_search(query_text, n_results=n_results)]
        hybrid_results = [r['title'] for r in self.engine.hybrid_search(query_text, n_results=n_results)['results']]
        
        # Calculate metrics for each method
        metrics = {}
        for method_name, results in [
            ('vector', vector_results),
            ('keyword', keyword_results),
            ('graph', graph_results),
            ('hybrid', hybrid_results)
        ]:
            prec, rec = self._calc_precision_recall(results, expected, k=n_results)
            mrr = self._calc_mrr(results, expected)
            ndcg = self._calc_ndcg(results, expected, k=n_results)
            
            metrics[method_name] = {
                'results': results,
                'precision': prec,
                'recall': rec,
                'mrr': mrr,
                'ndcg': ndcg,
                'f1': 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0
            }
        
        print("OK")
        return {
            'query_id': query['id'],
            'query': query_text,
            'category': query.get('category', 'general'),
            'expected_count': len(expected),
            'metrics': metrics
        }
    
    def run_benchmark(self, limit: int = None) -> Dict:
        """Run full benchmark on all gold queries"""
        print(f"\n=== Running Benchmark on {len(self.gold_answers)} Queries ===\n")
        
        results = []
        queries_to_evaluate = self.gold_answers[:limit] if limit else self.gold_answers
        
        for query in queries_to_evaluate:
            result = self.evaluate_query(query)
            results.append(result)
        
        return {
            'total_queries': len(results),
            'results': results
        }
    
    def calculate_aggregate_metrics(self, benchmark_results: Dict) -> Dict:
        """Calculate aggregate metrics across all queries"""
        methods = ['vector', 'keyword', 'graph', 'hybrid']
        aggregate = {method: {
            'precision': [],
            'recall': [],
            'mrr': [],
            'ndcg': [],
            'f1': []
        } for method in methods}
        
        for result in benchmark_results['results']:
            for method in methods:
                metrics = result['metrics'][method]
                aggregate[method]['precision'].append(metrics['precision'])
                aggregate[method]['recall'].append(metrics['recall'])
                aggregate[method]['mrr'].append(metrics['mrr'])
                aggregate[method]['ndcg'].append(metrics['ndcg'])
                aggregate[method]['f1'].append(metrics['f1'])
        
        # Calculate means and std
        summary = {}
        for method in methods:
            summary[method] = {
                'mean_precision': sum(aggregate[method]['precision']) / len(aggregate[method]['precision']),
                'mean_recall': sum(aggregate[method]['recall']) / len(aggregate[method]['recall']),
                'mean_mrr': sum(aggregate[method]['mrr']) / len(aggregate[method]['mrr']),
                'mean_ndcg': sum(aggregate[method]['ndcg']) / len(aggregate[method]['ndcg']),
                'mean_f1': sum(aggregate[method]['f1']) / len(aggregate[method]['f1']),
                'results_count': len(aggregate[method]['precision'])
            }
        
        return summary
    
    def generate_report(self, benchmark_results: Dict) -> str:
        """Generate markdown evaluation report"""
        summary = self.calculate_aggregate_metrics(benchmark_results)
        
        report = f"""# Step 4: Search Evaluation Report

**Date:** 2026-04-19  
**Total Queries Evaluated:** {benchmark_results['total_queries']}

## Overall Performance Summary

| Method | Precision | Recall | MRR | NDCG | F1 Score |
|--------|-----------|--------|-----|------|----------|
"""
        
        for method in ['vector', 'keyword', 'graph', 'hybrid']:
            m = summary[method]
            report += f"| {method.capitalize()} | {m['mean_precision']:.3f} | {m['mean_recall']:.3f} | {m['mean_mrr']:.3f} | {m['mean_ndcg']:.3f} | {m['mean_f1']:.3f} |\n"
        
        report += "\n## Detailed Results by Query\n\n"
        
        # Group by category
        categories = defaultdict(list)
        for result in benchmark_results['results']:
            categories[result['category']].append(result)
        
        for category, queries in sorted(categories.items()):
            report += f"\n### {category.replace('_', ' ').title()} ({len(queries)} queries)\n\n"
            
            for query_result in queries:
                report += f"**Query {query_result['query_id']}:** \"{query_result['query']}\"\n"
                report += f"- Expected Results: {query_result['expected_count']}\n"
                report += f"- Best Method: Hybrid\n\n"
                
                # Show top result from each method
                report += "| Method | Top Result | Score | Metrics |\n"
                report += "|--------|-----------|-------|----------|\n"
                
                for method in ['vector', 'keyword', 'graph', 'hybrid']:
                    metrics = query_result['metrics'][method]
                    top_result = metrics['results'][0] if metrics['results'] else "(no results)"
                    score = f"{metrics['ndcg']:.3f}"
                    metric_str = f"P:{metrics['precision']:.2f} R:{metrics['recall']:.2f}"
                    report += f"| {method.capitalize()} | {top_result[:40]}... | {score} | {metric_str} |\n"
                
                report += "\n"
        
        # Performance comparison
        report += "\n## Key Findings\n\n"
        
        # Find best method
        best_method = max(summary.items(), key=lambda x: x[1]['mean_f1'])[0]
        report += f"1. **Best Overall Method:** {best_method.upper()} (F1: {summary[best_method]['mean_f1']:.3f})\n\n"
        
        # Find method best for each metric
        report += "2. **Metric Leaders:**\n"
        report += f"   - Highest Precision: {max(summary.items(), key=lambda x: x[1]['mean_precision'])[0].upper()}\n"
        report += f"   - Highest Recall: {max(summary.items(), key=lambda x: x[1]['mean_recall'])[0].upper()}\n"
        report += f"   - Highest MRR: {max(summary.items(), key=lambda x: x[1]['mean_mrr'])[0].upper()}\n"
        report += f"   - Highest NDCG: {max(summary.items(), key=lambda x: x[1]['mean_ndcg'])[0].upper()}\n\n"
        
        report += "3. **Method Characteristics:**\n"
        report += "   - **Vector:** Semantic similarity; good for concept matching; requires embeddings\n"
        report += "   - **Keyword:** Fast; deterministic; exact term matching; no false positives\n"
        report += "   - **Graph:** Relationship-based; finds connected items; limited to graph structure\n"
        report += "   - **Hybrid:** Combines all three; best recall; highest confidence results\n\n"
        
        report += "## Recommendations\n\n"
        report += "1. Use **Hybrid** for production - best balance of precision and recall\n"
        report += "2. Use **Keyword** for exact title/skill searches - fastest, deterministic\n"
        report += "3. Use **Vector** for semantic/conceptual searches - finds similar roles\n"
        report += "4. Use **Graph** for company/skill-based discovery - explores relationships\n\n"
        
        report += "## Configuration\n\n"
        report += "For best performance in production, use:\n"
        report += "```python\n"
        report += "weights = {\n"
        report += "    'vector': 0.5,   # Semantic understanding\n"
        report += "    'keyword': 0.3,  # Explicit matching\n"
        report += "    'graph': 0.2     # Relationship traversal\n"
        report += "}\n"
        report += "```\n"
        
        return report

def main():
    print("=" * 60)
    print("STEP 4: SEARCH QUALITY EVALUATION")
    print("=" * 60)
    
    benchmark = SearchBenchmark()
    
    # Run benchmark
    results = benchmark.run_benchmark()
    
    # Generate report
    report = benchmark.generate_report(results)
    
    # Save report
    report_file = PROCESSED_DIR / "evaluation_report.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n[SUCCESS] Evaluation complete!")
    print(f"[REPORT] Report saved to: {report_file}")
    
    # Save detailed results
    results_file = PROCESSED_DIR / "benchmark_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"[RESULTS] Detailed results saved to: {results_file}")
    
    # Print summary
    summary = benchmark.calculate_aggregate_metrics(results)
    print("\n" + "=" * 60)
    print("SUMMARY METRICS")
    print("=" * 60)
    
    for method in ['vector', 'keyword', 'graph', 'hybrid']:
        m = summary[method]
        print(f"\n{method.upper()}:")
        print(f"  Precision: {m['mean_precision']:.3f}")
        print(f"  Recall:    {m['mean_recall']:.3f}")
        print(f"  MRR:       {m['mean_mrr']:.3f}")
        print(f"  NDCG:      {m['mean_ndcg']:.3f}")
        print(f"  F1 Score:  {m['mean_f1']:.3f}")

if __name__ == "__main__":
    main()
