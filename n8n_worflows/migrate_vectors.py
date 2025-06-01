# migrate_embeddings.py
import os
from openai import OpenAI
from supabase import create_client
import time
from dotenv import load_dotenv

load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def migrate_all_embeddings():
    """Migrate all embeddings to text-embedding-3-small"""
    
    # Get all documents
    print("Fetching all documents...")
    result = supabase.table('agent_documents').select('*').execute()
    documents = result.data
    
    print(f"Found {len(documents)} documents to migrate")
    
    # Confirm
    response = input("This will update ALL embeddings. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        return
    
    # Process each document
    success = 0
    failed = 0
    
    for i, doc in enumerate(documents):
        try:
            print(f"\rProcessing {i+1}/{len(documents)} - Agent: {doc['agent_name']}", end='')
            
            # Generate new embedding with text-embedding-3-small
            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=doc['content']
            )
            new_embedding = response.data[0].embedding
            
            # Update the document
            supabase.table('agent_documents')\
                .update({'embedding': new_embedding})\
                .eq('id', doc['id'])\
                .execute()
            
            success += 1
            time.sleep(0.05)  # Rate limiting
            
        except Exception as e:
            print(f"\nError processing doc {doc['id']}: {e}")
            failed += 1
    
    print(f"\n\nMigration complete!")
    print(f"Success: {success}")
    print(f"Failed: {failed}")

if __name__ == "__main__":
    migrate_all_embeddings()