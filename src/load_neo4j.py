import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import pandas as pd
from neo4j import GraphDatabase
from config import OUTPUT_DIR, PROCESSED_DIR
import os

# Neo4j connection configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

class Neo4jLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Clear all nodes and relationships"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared existing database")

    def create_constraints(self):
        """Create uniqueness constraints"""
        with self.driver.session() as session:
            # Company name uniqueness
            session.run("CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE")
            # Job URL uniqueness
            session.run("CREATE CONSTRAINT job_url IF NOT EXISTS FOR (j:Job) REQUIRE j.url IS UNIQUE")
            # Skill name uniqueness
            session.run("CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE")
            print("Created database constraints")

    def load_companies(self, jobs_df):
        """Load company nodes"""
        companies = jobs_df['company'].dropna().unique()

        with self.driver.session() as session:
            for company in companies:
                session.run(
                    "MERGE (c:Company {name: $name})",
                    name=company
                )
        print(f"Loaded {len(companies)} companies")

    def load_jobs(self, jobs_df):
        """Load job nodes with properties"""
        with self.driver.session() as session:
            for _, job in jobs_df.iterrows():
                # Create job node
                session.run("""
                    MERGE (j:Job {url: $url})
                    SET j.title = $title,
                        j.location = $location,
                        j.role_category = $role_category,
                        j.description = $description,
                        j.employment_type = $employment_type,
                        j.department = $department
                    """,
                    url=job['job_url'],
                    title=job['title'],
                    location=job.get('location'),
                    role_category=job.get('role_category'),
                    description=job.get('description'),
                    employment_type=job.get('employment_type'),
                    department=job.get('department')
                )
        print(f"Loaded {len(jobs_df)} jobs")

    def load_skills(self, edges_df):
        """Load skill nodes from relationships"""
        skills = edges_df[edges_df['relationship'] == 'REQUIRES']['target'].unique()

        with self.driver.session() as session:
            for skill in skills:
                session.run(
                    "MERGE (s:Skill {name: $name})",
                    name=skill
                )
        print(f"Loaded {len(skills)} skills")

    def create_relationships(self, edges_df):
        """Create relationships between nodes"""
        with self.driver.session() as session:
            for _, edge in edges_df.iterrows():
                source = edge['source']
                relationship = edge['relationship']
                target = edge['target']

                if relationship == 'HIRING_FOR':
                    # Company HIRING_FOR Job
                    session.run("""
                        MATCH (c:Company {name: $company})
                        MATCH (j:Job {url: $job_url})
                        MERGE (c)-[:HIRING_FOR]->(j)
                        """,
                        company=source,
                        job_url=target
                    )

                elif relationship == 'REQUIRES':
                    # Job REQUIRES Skill
                    session.run("""
                        MATCH (j:Job {url: $job_url})
                        MATCH (s:Skill {name: $skill})
                        MERGE (j)-[:REQUIRES]->(s)
                        """,
                        job_url=source,
                        skill=target
                    )

                elif relationship == 'USES_TECH':
                    # Company USES_TECH Skill
                    session.run("""
                        MATCH (c:Company {name: $company})
                        MATCH (s:Skill {name: $skill})
                        MERGE (c)-[:USES_TECH]->(s)
                        """,
                        company=source,
                        skill=target
                    )

        print(f"Created {len(edges_df)} relationships")

    def get_stats(self):
        """Get database statistics"""
        with self.driver.session() as session:
            # Count nodes by type
            company_count = session.run("MATCH (c:Company) RETURN count(c) as count").single()['count']
            job_count = session.run("MATCH (j:Job) RETURN count(j) as count").single()['count']
            skill_count = session.run("MATCH (s:Skill) RETURN count(s) as count").single()['count']

            # Count relationships by type
            hiring_count = session.run("MATCH ()-[:HIRING_FOR]->() RETURN count(*) as count").single()['count']
            requires_count = session.run("MATCH ()-[:REQUIRES]->() RETURN count(*) as count").single()['count']
            uses_tech_count = session.run("MATCH ()-[:USES_TECH]->() RETURN count(*) as count").single()['count']

            return {
                'companies': company_count,
                'jobs': job_count,
                'skills': skill_count,
                'hiring_relationships': hiring_count,
                'requires_relationships': requires_count,
                'uses_tech_relationships': uses_tech_count
            }

def load_to_neo4j(dry_run=False):
    """Main function to load data into Neo4j"""

    # Load data files
    jobs_file = PROCESSED_DIR / "jobs_master.csv"
    edges_file = OUTPUT_DIR / "job_graph_edges.csv"

    if not jobs_file.exists():
        print(f"Error: {jobs_file} not found")
        return

    if not edges_file.exists():
        print(f"Error: {edges_file} not found")
        return

    print("Loading data files...")
    jobs_df = pd.read_csv(jobs_file)
    edges_df = pd.read_csv(edges_file)

    print(f"Loaded {len(jobs_df)} jobs and {len(edges_df)} relationships")

    if dry_run:
        print("\n=== DRY RUN MODE - No database changes ===")
        print("Companies to create:", len(jobs_df['company'].dropna().unique()))
        print("Jobs to create:", len(jobs_df))
        print("Skills to create:", len(edges_df[edges_df['relationship'] == 'REQUIRES']['target'].unique()))
        print("Relationships to create:", len(edges_df))
        print("\nSample relationships:")
        for _, edge in edges_df.head().iterrows():
            print(f"  {edge['source']} -[{edge['relationship']}]-> {edge['target']}")
        return

    # Initialize Neo4j loader
    loader = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        # Clear and setup database
        loader.clear_database()
        loader.create_constraints()

        # Load nodes
        loader.load_companies(jobs_df)
        loader.load_jobs(jobs_df)
        loader.load_skills(edges_df)

        # Create relationships
        loader.create_relationships(edges_df)

        # Get final statistics
        stats = loader.get_stats()

        print("\n=== Neo4j Database Loaded Successfully ===")
        print(f"Companies: {stats['companies']}")
        print(f"Jobs: {stats['jobs']}")
        print(f"Skills: {stats['skills']}")
        print(f"Hiring relationships: {stats['hiring_relationships']}")
        print(f"Requires relationships: {stats['requires_relationships']}")
        print(f"Uses Tech relationships: {stats['uses_tech_relationships']}")

        print(f"\nTotal nodes: {stats['companies'] + stats['jobs'] + stats['skills']}")
        print(f"Total relationships: {stats['hiring_relationships'] + stats['requires_relationships'] + stats['uses_tech_relationships']}")

    except Exception as e:
        print(f"Error loading to Neo4j: {e}")
        print("\n=== Neo4j Setup Instructions ===")
        print("1. Install Neo4j Desktop or Server:")
        print("   - Download from: https://neo4j.com/download/")
        print("   - Or use Neo4j Aura (cloud): https://neo4j.com/cloud/aura/")
        print()
        print("2. Start Neo4j with default settings:")
        print("   - URI: bolt://localhost:7687")
        print("   - User: neo4j")
        print("   - Password: password (change this!)")
        print()
        print("3. For Neo4j Aura cloud:")
        print("   - Set environment variables:")
        print("     NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io")
        print("     NEO4J_USER=neo4j")
        print("     NEO4J_PASSWORD=your-password")
        print()
        print("4. Alternative: Use Docker:")
        print("   docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest")
        print()
        print("Current connection config:")
        print(f"URI: {NEO4J_URI}")
        print(f"User: {NEO4J_USER}")
        print("(Password hidden for security)")

    finally:
        loader.close()

if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    load_to_neo4j(dry_run=dry_run)