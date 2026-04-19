import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import pandas as pd
import json
import chromadb
from chromadb.config import Settings
from config import PROCESSED_DIR, OUTPUT_DIR

# Optional: Use sentence-transformers for better embeddings
try:
    from sentence_transformers import SentenceTransformer
    HAS_TRANSFORMERS = True
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Lightweight, fast model
except ImportError:
    HAS_TRANSFORMERS = False
    print("Note: sentence-transformers not installed. Using ChromaDB default embeddings.")

class ChromaVectorStore:
    def __init__(self, persist_dir="data/chroma_db"):
        """Initialize ChromaDB client with persistent storage"""
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Use persistent storage
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

        # Use sentence-transformers if available, otherwise default
        if HAS_TRANSFORMERS:
            self.embedding_function = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
            print(f"Using SentenceTransformer embeddings: {EMBEDDING_MODEL}")
        else:
            self.embedding_function = chromadb.utils.embedding_functions.DefaultEmbeddingFunction()
            print("Using ChromaDB default embeddings (OpenAI API-based if configured)")
        
        # Auto-create collections and load data
        self.job_chunks = None
        self.jobs_full = None
        self.skills = None
        self.create_collections()
        self._auto_load_if_exists()

    def create_collections(self):
        """Create collections for different data types"""
        try:
            self.job_chunks = self.client.get_or_create_collection(
                name="job_chunks",
                embedding_function=self.embedding_function,
                metadata={"description": "Job posting chunks for semantic search"}
            )
            self.jobs_full = self.client.get_or_create_collection(
                name="jobs_full",
                embedding_function=self.embedding_function,
                metadata={"description": "Complete job postings"}
            )
            self.skills = self.client.get_or_create_collection(
                name="skills",
                embedding_function=self.embedding_function,
                metadata={"description": "Skills extracted from jobs"}
            )
            print("Created/retrieved ChromaDB collections")
            return True
        except Exception as e:
            print(f"Error creating collections: {e}")
            return False

    def _auto_load_if_exists(self):
        """Auto-load data if it already exists in ChromaDB"""
        try:
            # Check if data already exists by querying collection counts
            chunks_count = self.job_chunks.count()
            jobs_count = self.jobs_full.count()
            skills_count = self.skills.count()
            
            if chunks_count > 0 or jobs_count > 0 or skills_count > 0:
                print(f"✓ Loaded existing ChromaDB data: {chunks_count} chunks, {jobs_count} jobs, {skills_count} skills")
            else:
                # Try loading from files if collections are empty
                chunks_file = PROCESSED_DIR / "chroma_chunks.csv"
                jobs_file = PROCESSED_DIR / "jobs_master.csv"
                edges_file = OUTPUT_DIR / "job_graph_edges.csv"
                
                if chunks_file.exists():
                    self.load_chunks(str(chunks_file))
                if jobs_file.exists():
                    self.load_full_jobs(str(jobs_file))
                if edges_file.exists():
                    self.load_skills_reference(str(edges_file))
        except Exception as e:
            print(f"Note: Could not auto-load data: {e}")

    def load_chunks(self, chunks_file):
        """Load Chroma chunks into vector store"""
        if not Path(chunks_file).exists():
            print(f"Chunks file not found: {chunks_file}")
            return 0

        df = pd.read_csv(chunks_file)
        print(f"Loading {len(df)} chunks into vector store...")

        batch_size = 41  # ChromaDB batch size limit
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]

            # Prepare documents and metadata
            ids = [str(row['chunk_id']) for _, row in batch.iterrows()]
            documents = [row['chunk_text'] for _, row in batch.iterrows()]
            metadatas = [
                {
                    'job_url': row['job_url'],
                    'company': row['company'],
                    'title': row['title'],
                    'role_category': row['role_category'],
                    'chunk_index': int(row['chunk_index'])
                }
                for _, row in batch.iterrows()
            ]

            # Add to collection (embeddings generated automatically)
            self.job_chunks.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

        print(f"Successfully loaded {len(df)} chunks into 'job_chunks' collection")
        return len(df)

    def load_full_jobs(self, jobs_file):
        """Load full job descriptions for reference"""
        if not Path(jobs_file).exists():
            print(f"Jobs file not found: {jobs_file}")
            return 0

        df = pd.read_csv(jobs_file)
        print(f"Loading {len(df)} full job postings into vector store...")

        batch_size = 41
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]

            ids = [f"job_{idx}" for idx in range(i, min(i+batch_size, len(df)))]
            documents = [
                f"{row['title']} at {row['company']} in {row['location']}. {row['description'][:500]}"
                for _, row in batch.iterrows()
            ]
            metadatas = [
                {
                    'job_url': row['job_url'],
                    'company': row['company'],
                    'title': row['title'],
                    'location': row['location'],
                    'role_category': row['role_category'],
                    'employment_type': row.get('employment_type', ''),
                    'dedup_key': row['dedup_key']
                }
                for _, row in batch.iterrows()
            ]

            self.jobs_full.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

        print(f"Successfully loaded {len(df)} full jobs into 'jobs_full' collection")
        return len(df)

    def load_skills_reference(self, edges_file):
        """Load skills as a reference collection"""
        if not Path(edges_file).exists():
            print(f"Edges file not found: {edges_file}")
            return 0

        df = pd.read_csv(edges_file)
        skills_df = df[df['relationship'] == 'REQUIRES'][['target']].drop_duplicates()
        skills_df.columns = ['skill']

        print(f"Loading {len(skills_df)} skills into vector store...")

        ids = [f"skill_{i}" for i in range(len(skills_df))]
        documents = [f"Skill: {skill}" for skill in skills_df['skill']]
        metadatas = [{'skill_name': skill} for skill in skills_df['skill']]

        self.skills.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(f"Successfully loaded {len(skills_df)} skills into 'skills' collection")
        return len(skills_df)

    def search_chunks(self, query, n_results=5):
        """Search for similar job chunks"""
        results = self.job_chunks.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

    def search_jobs(self, query, n_results=5):
        """Search for similar full jobs"""
        results = self.jobs_full.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

    def search_skills(self, query, n_results=5):
        """Search for similar skills"""
        results = self.skills.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

    def get_stats(self):
        """Get collection statistics"""
        stats = {
            'job_chunks': self.job_chunks.count(),
            'jobs_full': self.jobs_full.count(),
            'skills': self.skills.count(),
        }
        return stats

def create_vector_store():
    """Main function to create and populate vector store"""

    print("Initializing ChromaDB vector store...")
    store = ChromaVectorStore(persist_dir=str(PROCESSED_DIR / "chroma_db"))

    if not store.create_collections():
        print("Failed to create collections")
        return

    # Load data
    chunks_loaded = store.load_chunks(PROCESSED_DIR / "chroma_chunks.csv")
    jobs_loaded = store.load_full_jobs(PROCESSED_DIR / "jobs_master.csv")
    skills_loaded = store.load_skills_reference(OUTPUT_DIR / "job_graph_edges.csv")

    # Print statistics
    stats = store.get_stats()
    print("\n=== ChromaDB Vector Store Created ===")
    print(f"Job chunks: {stats['job_chunks']}")
    print(f"Full jobs: {stats['jobs_full']}")
    print(f"Skills: {stats['skills']}")
    print(f"Total embeddings: {sum(stats.values())}")

    # Test search
    print("\n=== Testing Vector Search ===")
    test_queries = [
        "machine learning engineer roles",
        "python programming skills",
        "remote data science positions"
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = store.search_jobs(query, n_results=2)
        if results['ids'][0]:
            for i, doc in enumerate(results['documents'][0]):
                print(f"  Result {i+1}: {doc[:100]}...")
                if results['metadatas'][0][i]:
                    print(f"    Company: {results['metadatas'][0][i].get('company', 'N/A')}")
        else:
            print("  No results found")

    print("\n✅ Vector store ready for semantic search!")
    return store

if __name__ == "__main__":
    create_vector_store()
