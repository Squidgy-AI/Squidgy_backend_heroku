import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def check_embeddings():
    conn = psycopg2.connect(
        host=os.getenv('SUPABASE_DB_HOST'),
        database='postgres',
        user='postgres',
        password=os.getenv('SUPABASE_DB_PASSWORD'),
        port=5432
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Check if embeddings exist and their format
        cur.execute("""
            SELECT 
                id,
                agent_name,
                content,
                embedding IS NOT NULL as has_embedding,
                octet_length(embedding::text) as embedding_size
            FROM agent_documents
            ORDER BY agent_name, id
        """)
        
        docs = cur.fetchall()
        print(f"Total documents: {len(docs)}")
        
        for doc in docs:
            print(f"\nDoc {doc['id']} - {doc['agent_name']}:")
            print(f"  Has embedding: {doc['has_embedding']}")
            print(f"  Content preview: {doc['content'][:100]}...")
            print(f"  Embedding size: {doc['embedding_size']}")
            
        # Test similarity between first two documents
        cur.execute("""
            SELECT 
                a.id as id1, 
                b.id as id2,
                a.agent_name as agent1,
                b.agent_name as agent2,
                1 - (a.embedding <=> b.embedding) as similarity
            FROM agent_documents a, agent_documents b
            WHERE a.id < b.id
            LIMIT 5
        """)
        
        print("\n\nSimilarity between documents:")
        for row in cur.fetchall():
            print(f"  Doc {row['id1']} ({row['agent1']}) <-> Doc {row['id2']} ({row['agent2']}): {row['similarity']:.3f}")
            
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    check_embeddings()