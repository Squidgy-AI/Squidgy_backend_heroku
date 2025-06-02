import os
from supabase import create_client
from dotenv import load_dotenv
import json
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

# For direct PostgreSQL connection
def fix_embeddings_direct():
    """Fix embeddings using direct PostgreSQL connection"""
    
    # You'll need these in your .env:
    # SUPABASE_DB_HOST=db.xxxxxxxxxxxx.supabase.co
    # SUPABASE_DB_PASSWORD=your_password
    
    conn_params = {
        'host': os.getenv('SUPABASE_DB_HOST'),
        'database': 'postgres',
        'user': 'postgres',
        'password': os.getenv('SUPABASE_DB_PASSWORD'),
        'port': 5432
    }
    
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get all documents
        cur.execute("SELECT id, agent_name, embedding::text FROM agent_documents")
        docs = cur.fetchall()
        
        print(f"Found {len(docs)} documents")
        
        for doc in docs:
            # Parse the string representation
            embedding_str = doc['embedding']
            if isinstance(embedding_str, str) and embedding_str.startswith('['):
                # Already in correct format
                continue
                
            # Convert to proper format
            embedding_list = json.loads(embedding_str) if '{' in embedding_str else eval(embedding_str)
            
            # Update with proper vector format
            cur.execute(
                "UPDATE agent_documents SET embedding = %s::vector WHERE id = %s",
                (embedding_list, doc['id'])
            )
            print(f"Fixed document {doc['id']} for agent {doc['agent_name']}")
        
        conn.commit()
        print("All embeddings fixed!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    fix_embeddings_direct()