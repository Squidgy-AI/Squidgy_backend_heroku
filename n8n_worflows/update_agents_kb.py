import os
from openai import OpenAI
from supabase import create_client, Client
from typing import List, Dict
import numpy as np
from pathlib import Path
import json
from tqdm import tqdm
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AGENTS_KB_FOLDER = os.getenv("AGENTS_KB_FOLDER", "./Agents_KB")  # Default to ./Agents_KB if not set
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Validate that required environment variables are set
required_vars = ["OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks.
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at a sentence boundary
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            
            if break_point > chunk_size * 0.5:  # Only break if we're past halfway
                chunk = text[start:start + break_point + 1]
                end = start + break_point + 1
        
        chunks.append(chunk.strip())
        start = end - overlap
    
    return [chunk for chunk in chunks if chunk]  # Filter out empty chunks

def get_embedding(text: str) -> List[float]:
    """
    Get embedding for a text using OpenAI API.
    """
    try:
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

def process_file(file_path: Path) -> List[Dict]:
    """
    Process a single text file and return chunks with metadata.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create chunks
        chunks = chunk_text(content)
        
        # Prepare documents with metadata
        documents = []
        for i, chunk in enumerate(chunks):
            doc = {
                'content': chunk,
                'metadata': {
                    'source': str(file_path),
                    'filename': file_path.name,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'file_type': 'agent_knowledge'
                }
            }
            documents.append(doc)
        
        return documents
    
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return []

def upsert_documents_with_embeddings(documents: List[Dict]):
    """
    Upsert documents with their embeddings into Supabase.
    Updates existing documents or inserts new ones based on agent_name and chunk_index.
    """
    for doc in tqdm(documents, desc="Creating embeddings and upserting"):
        try:
            # Get embedding
            embedding = get_embedding(doc['content'])
            
            if embedding:
                # Extract agent_name from filename (remove .txt extension)
                agent_name = doc['metadata']['filename'].replace('.txt', '')
                chunk_index = doc['metadata']['chunk_index']
                
                # Prepare data for insertion/update
                data = {
                    'content': doc['content'],
                    'metadata': doc['metadata'],
                    'embedding': embedding,
                    'agent_name': agent_name
                }
                
                # Check if document exists based on agent_name and chunk_index
                existing = supabase.table('agent_documents').select('id').eq('agent_name', agent_name).eq('metadata->>chunk_index', str(chunk_index)).execute()
                
                if existing.data and len(existing.data) > 0:
                    # Update existing document
                    result = supabase.table('agent_documents').update(data).eq('agent_name', agent_name).eq('metadata->>chunk_index', str(chunk_index)).execute()
                    print(f"\n  Updated: {agent_name} - chunk {chunk_index}")
                else:
                    # Insert new document
                    result = supabase.table('agent_documents').insert(data).execute()
                    print(f"\n  Inserted: {agent_name} - chunk {chunk_index}")
                
                # Rate limiting to avoid hitting API limits
                time.sleep(0.1)
            
        except Exception as e:
            print(f"\nError upserting document: {e}")
            continue

def main():
    """
    Main function to process all files and create embeddings.
    """
    # Check if folder exists
    folder_path = Path(AGENTS_KB_FOLDER)
    if not folder_path.exists():
        print(f"Folder {AGENTS_KB_FOLDER} not found!")
        return
    
    # Get all .txt files
    txt_files = list(folder_path.glob("*.txt"))
    print(f"Found {len(txt_files)} .txt files in {AGENTS_KB_FOLDER}")
    
    if not txt_files:
        print("No .txt files found!")
        return
    
    # Process each file
    all_documents = []
    for file_path in txt_files:
        print(f"\nProcessing: {file_path.name}")
        documents = process_file(file_path)
        all_documents.extend(documents)
        print(f"  Created {len(documents)} chunks")
    
    print(f"\nTotal documents to process: {len(all_documents)}")
    
    # Confirm before proceeding
    response = input("\nProceed with creating embeddings and upserting to Supabase? (y/n): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return
    
    # Insert/Update documents with embeddings
    print("\nCreating embeddings and upserting into Supabase...")
    upsert_documents_with_embeddings(all_documents)
    
    print("\nDone! All documents have been processed and upserted.")
    
    # Optional: Test the search function
    test_search = input("\nWould you like to test the search function? (y/n): ")
    if test_search.lower() == 'y':
        test_query = input("Enter a test query: ")
        test_agent = input("Enter agent name to search (or press Enter for all agents): ").strip()
        
        test_embedding = get_embedding(test_query)
        
        if test_embedding:
            if test_agent:
                # Search within specific agent
                result = supabase.rpc('match_agent_documents_by_name', {
                    'query_embedding': test_embedding,
                    'agent_name_filter': test_agent,
                    'match_count': 5
                }).execute()
                print(f"\nSearch Results for agent '{test_agent}':")
            else:
                # Search across all agents
                result = supabase.rpc('match_agent_documents', {
                    'query_embedding': test_embedding,
                    'match_count': 5
                }).execute()
                print("\nSearch Results across all agents:")
            
            for i, doc in enumerate(result.data):
                print(f"\n{i+1}. Similarity: {doc['similarity']:.4f}")
                print(f"   Agent: {doc.get('agent_name', 'N/A')}")
                print(f"   Content: {doc['content'][:200]}...")
                print(f"   Metadata: {doc['metadata']}")

if __name__ == "__main__":
    main()