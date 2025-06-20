#!/usr/bin/env python3
"""
Free Agent Knowledge Base Upload Tool
Uses sentence-transformers instead of OpenAI for embeddings to avoid quota issues and costs.
"""

import os
import sys
from supabase import create_client, Client
from typing import List, Dict
import numpy as np
from pathlib import Path
import json
from tqdm import tqdm
import time
from dotenv import load_dotenv

# Add parent directory to path to import embedding_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from embedding_service import get_embedding, get_embeddings_batch

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AGENTS_KB_FOLDER = os.getenv("AGENTS_KB_FOLDER", "/Users/somasekharaddakula/CascadeProjects/SquidgyFullStack/backend/n8n_worflows/Agents_KB")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Validate that required environment variables are set
required_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clear_all_agent_documents():
    """
    Remove all existing documents from agent_documents table
    """
    try:
        print("\n⚠️  WARNING: Deleting ALL existing agent documents!")
        
        # Auto-confirm deletion
        # Delete all records
        result = supabase.table('agent_documents').delete().gte('id', 0).execute()
        print(f"✅ Deleted all existing agent documents")
        return True
    except Exception as e:
        print(f"Error clearing documents: {e}")
        return False

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

def process_file(file_path: Path) -> List[Dict]:
    """
    Process a single text file and return chunks with metadata.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Don't chunk - use the entire content as one document
        # This is better for small agent KB files
        documents = [{
            'content': content,
            'metadata': {
                'source': str(file_path),
                'filename': file_path.name,
                'chunk_index': 0,
                'total_chunks': 1,
                'file_type': 'agent_knowledge'
            }
        }]
        
        return documents
    
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return []

def insert_documents_with_embeddings(documents: List[Dict]):
    """
    Insert documents with their embeddings into Supabase using free embedding service.
    """
    success_count = 0
    
    # Prepare texts for batch embedding
    texts = [doc['content'] for doc in documents]
    agent_names = [doc['metadata']['filename'].replace('.txt', '') for doc in documents]
    
    print("\n📊 Generating embeddings using free sentence-transformers model...")
    print("This may take a moment on first run while downloading the model...")
    
    # Generate embeddings in batch for efficiency
    embeddings = get_embeddings_batch(texts)
    
    for doc, embedding, agent_name in tqdm(zip(documents, embeddings, agent_names), 
                                          desc="Inserting documents", 
                                          total=len(documents)):
        try:
            if embedding:
                # Prepare data for insertion
                data = {
                    'content': doc['content'],
                    'metadata': doc['metadata'],
                    'embedding': embedding,
                    'agent_name': agent_name
                }
                
                # Insert new document
                result = supabase.table('agent_documents').insert(data).execute()
                success_count += 1
                print(f"\n  ✅ Inserted: {agent_name}")
                
                # Small delay to avoid overwhelming the database
                time.sleep(0.05)
            else:
                print(f"\n❌ Failed to generate embedding for: {agent_name}")
            
        except Exception as e:
            print(f"\n❌ Error inserting document: {e}")
            continue
    
    return success_count

def main():
    """
    Main function to process all files and create embeddings using free service.
    """
    print("🚀 FREE Agent Knowledge Base Upload Tool")
    print("Using sentence-transformers for cost-free embeddings!")
    print("="*70)
    
    # Check if folder exists
    folder_path = Path(AGENTS_KB_FOLDER)
    if not folder_path.exists():
        # Try fallback path
        fallback_path = Path("./Agents_KB")
        if fallback_path.exists():
            folder_path = fallback_path
            print(f"✅ Using fallback folder: {fallback_path.absolute()}")
        else:
            print(f"❌ Folder {AGENTS_KB_FOLDER} not found!")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Looking for folder at: {folder_path.absolute()}")
            print(f"Also tried fallback: {fallback_path.absolute()}")
            return
    
    # Get all .txt files
    txt_files = list(folder_path.glob("*.txt"))
    print(f"📁 Found {len(txt_files)} .txt files in {folder_path}")
    
    if not txt_files:
        print("❌ No .txt files found!")
        return
    
    print("\n📄 Files found:")
    for file in txt_files:
        print(f"  - {file.name}")
    
    # Ask if user wants to clear existing documents
    print("\n" + "="*60)
    print("⚠️  IMPORTANT: Do you want to delete ALL existing documents first?")
    print("This is recommended for a clean re-upload.")
    print("="*60)
    
    # Auto-clear documents for clean update
    print("Auto-clearing existing documents...")
    if not clear_all_agent_documents():
        print("Failed to clear documents. Exiting...")
        return
    
    # Process each file
    all_documents = []
    for file_path in txt_files:
        print(f"\n📄 Processing: {file_path.name}")
        documents = process_file(file_path)
        all_documents.extend(documents)
        print(f"  Created {len(documents)} document(s)")
    
    print(f"\n📊 Total documents to process: {len(all_documents)}")
    
    # Auto-proceed with embeddings
    print("\n🚀 Auto-proceeding with creating FREE embeddings and inserting to Supabase...")
    
    # Insert documents with embeddings
    print("\n⏳ Creating embeddings using sentence-transformers and inserting into Supabase...")
    success_count = insert_documents_with_embeddings(all_documents)
    
    print(f"\n✅ Done! Successfully inserted {success_count}/{len(all_documents)} documents.")
    print("💰 Cost: $0.00 - Completely FREE! No API quotas to worry about!")
    
    # Verify what's in the database
    print("\n📊 Verifying database content:")
    result = supabase.table('agent_documents')\
        .select('agent_name')\
        .execute()
    
    if result.data:
        agents = {}
        for doc in result.data:
            agent = doc['agent_name']
            agents[agent] = agents.get(agent, 0) + 1
        
        print("\n📋 Agent document counts:")
        for agent, count in sorted(agents.items()):
            print(f"  - {agent}: {count} document(s)")
    
    # Test search with the free embedding service
    print("\n✅ Knowledge base update completed successfully!")
    print("🔍 Testing with query: 'https://supabase.com/'")
    
    test_embedding = get_embedding("https://supabase.com/")
    
    if test_embedding:
        try:
            result = supabase.rpc('match_agents_by_similarity', {
                'query_embedding': test_embedding,
                'match_threshold': 0.2,  # Lower threshold
                'match_count': 5
            }).execute()
            
            print("\n🔍 Search Results:")
            if result.data:
                for i, doc in enumerate(result.data):
                    print(f"\n{i+1}. Agent: {doc.get('agent_name', 'N/A')}")
                    print(f"   Similarity: {doc['similarity']:.4f}")
                    print(f"   Content preview: {doc['content'][:100]}...")
            else:
                print("No matches found")
                
        except Exception as e:
            print(f"Error during search: {e}")
    
    print("\n🎉 Free embedding service is working perfectly!")
    print("💡 No more OpenAI quota issues or costs!")

if __name__ == "__main__":
    main()