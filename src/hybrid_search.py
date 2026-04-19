import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import pandas as pd
import json
from typing import List, Dict, Tuple
from config import PROCESSED_DIR, OUTPUT_DIR

class HybridSearchEngine:
    """
    Hybrid search combining:
    1. Vector similarity (semantic)
    2. Graph relationships (structural)
    3. Keyword matching (explicit)
    """

    def __init__(self, vector_store=None, graph_db=None):
        self.vector_store = vector_store
        self.graph_db = graph_db
        self.jobs_df = None
        self.edges_df = None
        self.chunks_df = None
        self._load_data()
        
        # Auto-load ChromaDB if available
        if self.vector_store is None:
            try:
                from create_vector_store import ChromaVectorStore
                self.vector_store = ChromaVectorStore()
                print("[OK] ChromaDB vector store loaded")
            except Exception as e:
                print(f"[WARNING] ChromaDB not available: {e}")

    def _load_data(self):
        """Load reference data"""
        if (PROCESSED_DIR / "jobs_master.csv").exists():
            self.jobs_df = pd.read_csv(PROCESSED_DIR / "jobs_master.csv")
        if (OUTPUT_DIR / "job_graph_edges.csv").exists():
            self.edges_df = pd.read_csv(OUTPUT_DIR / "job_graph_edges.csv")
        if (PROCESSED_DIR / "chroma_chunks.csv").exists():
            self.chunks_df = pd.read_csv(PROCESSED_DIR / "chroma_chunks.csv")

    def vector_search(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search using vector similarity"""
        if not self.vector_store:
            return []

        results = self.vector_store.search_jobs(query, n_results=n_results)
        parsed_results = []

        if results['ids'][0]:
            for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
                parsed_results.append({
                    'rank': i + 1,
                    'method': 'vector',
                    'score': results['distances'][0][i] if 'distances' in results else 1.0 - (i / n_results),
                    'title': metadata.get('title', 'N/A'),
                    'company': metadata.get('company', 'N/A'),
                    'url': metadata.get('job_url', 'N/A'),
                    'snippet': doc[:150],
                    'role_category': metadata.get('role_category', 'N/A')
                })

        return parsed_results

    def keyword_search(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search using keyword matching"""
        if self.jobs_df is None:
            return []

        keywords = query.lower().split()
        scores = []

        for idx, row in self.jobs_df.iterrows():
            text = (str(row.get('title', '')) + ' ' + str(row.get('description', ''))).lower()
            score = sum(text.count(kw) for kw in keywords)
            if score > 0:
                scores.append((idx, score, row))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = scores[:n_results]

        parsed_results = []
        for rank, (idx, score, row) in enumerate(results, 1):
            parsed_results.append({
                'rank': rank,
                'method': 'keyword',
                'score': score,
                'title': row.get('title', 'N/A'),
                'company': row.get('company', 'N/A'),
                'url': row.get('job_url', 'N/A'),
                'snippet': str(row.get('description', ''))[:150],
                'role_category': row.get('role_category', 'N/A')
            })

        return parsed_results

    def graph_search(self, entity: str, relationship: str = None, n_results: int = 5) -> List[Dict]:
        """Search using graph relationships"""
        if self.edges_df is None:
            return []

        # Find related jobs through graph
        if relationship:
            relevant_edges = self.edges_df[
                (self.edges_df['source'] == entity) & 
                (self.edges_df['relationship'] == relationship)
            ]
        else:
            relevant_edges = self.edges_df[
                (self.edges_df['source'] == entity) | 
                (self.edges_df['target'] == entity)
            ]

        results = []
        for idx, edge in relevant_edges.head(n_results).iterrows():
            target = edge['target']
            if target in self.jobs_df['title'].values:
                job = self.jobs_df[self.jobs_df['title'] == target].iloc[0]
                results.append({
                    'rank': len(results) + 1,
                    'method': 'graph',
                    'score': 1.0,
                    'title': job.get('title', 'N/A'),
                    'company': job.get('company', 'N/A'),
                    'url': job.get('job_url', 'N/A'),
                    'snippet': str(job.get('description', ''))[:150],
                    'role_category': job.get('role_category', 'N/A'),
                    'relationship': edge['relationship']
                })

        return results

    def hybrid_search(self, query: str, weights: Dict[str, float] = None, n_results: int = 5) -> Dict:
        """Combined search using all methods"""
        if weights is None:
            weights = {'vector': 0.5, 'keyword': 0.3, 'graph': 0.2}

        results = {
            'vector': self.vector_search(query, n_results),
            'keyword': self.keyword_search(query, n_results),
            'graph': self.graph_search(query, n_results=n_results),
        }

        # Combine and rank results
        combined = {}
        for method, weight in weights.items():
            for result in results.get(method, []):
                key = (result['title'], result['company'])
                if key not in combined:
                    combined[key] = {'combined_score': 0, 'methods': [], 'data': result}
                combined[key]['combined_score'] += weight / (result['rank'] + 1)
                combined[key]['methods'].append(method)

        # Sort by combined score
        ranked = sorted(combined.items(), key=lambda x: x[1]['combined_score'], reverse=True)

        final_results = []
        for rank, ((title, company), item) in enumerate(ranked[:n_results], 1):
            final_results.append({
                'rank': rank,
                'combined_score': round(item['combined_score'], 3),
                'methods': item['methods'],
                **item['data']
            })

        return {
            'query': query,
            'results': final_results,
            'method_results': results,
            'total_results': len(final_results)
        }

def test_search_engine():
    """Test the search engine with sample queries"""
    print("Initializing Hybrid Search Engine...")
    engine = HybridSearchEngine()

    test_queries = [
        "machine learning engineer with python",
        "data center operations remote",
        "infrastructure kubernetes devops",
        "electrical engineering power systems",
        "design ui ux roles"
    ]

    print("\n=== Running Hybrid Search Tests ===\n")

    for query in test_queries:
        print(f"Query: '{query}'")
        results = engine.hybrid_search(query, n_results=3)

        print(f"Found {results['total_results']} results:")
        for result in results['results']:
            print(f"  [{result['rank']}] {result['title']} @ {result['company']}")
            print(f"      Score: {result['combined_score']} | Methods: {result['methods']}")
            print(f"      URL: {result['url']}")
        print()

    # Save results to file
    output_file = PROCESSED_DIR / "hybrid_search_results.json"
    sample_results = {}
    for query in test_queries[:3]:
        sample_results[query] = engine.hybrid_search(query, n_results=3)

    with open(output_file, 'w') as f:
        json.dump(sample_results, f, indent=2, default=str)
    print(f"Saved sample search results to {output_file}")

if __name__ == "__main__":
    test_search_engine()
