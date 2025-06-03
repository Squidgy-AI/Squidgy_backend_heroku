# test_new_embeddings.py
import asyncio
from main_test import agent_matcher  # Adjust import

async def test_embedding_search():
    # Test queries
    test_queries = [
        "I need help with pricing",
        "Show me automation options",
        "I want to analyze my website"
    ]


    print("--------------------------------------------------------------------------------------------")
    print("\n\nTesting find_best_agents Best Agent Matching Function:")
    
    for idx,query in enumerate(test_queries):
        print(f"\n\nTest Case {idx}:")
        print(f"\nTesting: {query}")
        
        # Get best agents
        best_agents = await agent_matcher.find_best_agents(query, top_n=3)
        
        for agent, score in best_agents:
            print(f"  {agent}: {score:.2f}%")
        print("--------------------------------------------------------------------------------------------")
    
    print("--------------------------------------------------------------------------------------------")
    print("\n\nTesting check_agent_match Function:")
    # Test specific agent match
    print("\n\nTesting specific agent match:")
    is_match = await agent_matcher.check_agent_match("presaleskb", "I need you to analyse my website info")
    print(f"presaleskb matches pricing query: {is_match}")

if __name__ == "__main__":
    asyncio.run(test_embedding_search())


# test_verify_data.py
# import os
# from supabase import create_client
# from dotenv import load_dotenv

# load_dotenv()

# supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# # Check if presaleskb exists and has embeddings
# result = supabase.table('agent_documents')\
#     .select('id, agent_name, content')\
#     .eq('agent_name', 'presaleskb')\
#     .execute()

# print(f"Documents for presaleskb: {len(result.data)}")

# # Check if embeddings are not null
# result_with_embeddings = supabase.table('agent_documents')\
#     .select('id, agent_name')\
#     .eq('agent_name', 'presaleskb')\
#     .not_.is_('embedding', 'null')\
#     .execute()

# print(f"Documents with embeddings: {len(result_with_embeddings.data)}")

# # Get one document to check embedding dimensions
# if result.data:
#     doc_id = result.data[0]['id']
#     full_doc = supabase.table('agent_documents')\
#         .select('embedding')\
#         .eq('id', doc_id)\
#         .execute()
    
#     if full_doc.data and full_doc.data[0]['embedding']:
#         print(f"Embedding dimensions: {len(full_doc.data[0]['embedding'])}")

# check_embedding_format.py
# import os
# from supabase import create_client
# from dotenv import load_dotenv
# import json

# load_dotenv()
# supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# # Get the problematic document
# result = supabase.table('agent_documents')\
#     .select('id, agent_name, embedding')\
#     .eq('agent_name', 'presaleskb')\
#     .limit(1)\
#     .execute()

# if result.data:
#     doc = result.data[0]
#     embedding = doc['embedding']
    
#     print(f"Embedding type: {type(embedding)}")
#     print(f"Embedding length: {len(embedding)}")
    
#     # Check if it's a string representation
#     if isinstance(embedding, str):
#         print("ERROR: Embedding is stored as string!")
#         print(f"First 200 chars: {embedding[:200]}")
#     elif isinstance(embedding, list):
#         print(f"First 5 values: {embedding[:5]}")
        
#         # Check if values are nested
#         if isinstance(embedding[0], list):
#             print("ERROR: Embedding is nested list!")

# import os
# from supabase import create_client
# from dotenv import load_dotenv
# import json
# import ast

# load_dotenv()
# supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# def fix_existing_embeddings():
#     """Fix embeddings that are stored as strings"""
    
#     # Get all documents with string embeddings
#     result = supabase.table('agent_documents')\
#         .select('id, agent_name, embedding')\
#         .execute()
    
#     if not result.data:
#         print("No documents found")
#         return
    
#     fixed_count = 0
#     for doc in result.data:
#         embedding = doc['embedding']
        
#         if isinstance(embedding, str):
#             try:
#                 # Convert string to list
#                 # First try json.loads
#                 try:
#                     embedding_list = json.loads(embedding)
#                 except json.JSONDecodeError:
#                     # If that fails, try ast.literal_eval
#                     embedding_list = ast.literal_eval(embedding)
                
#                 # Update the document with proper array
#                 update_result = supabase.table('agent_documents')\
#                     .update({'embedding': embedding_list})\
#                     .eq('id', doc['id'])\
#                     .execute()
                
#                 fixed_count += 1
#                 print(f"Fixed document {doc['id']} for agent {doc['agent_name']}")
                
#             except Exception as e:
#                 print(f"Error fixing document {doc['id']}: {e}")
    
#     print(f"\nFixed {fixed_count} documents")

# def store_embedding_correctly(agent_name, content, embedding_vector):
#     """
#     Store embedding correctly as an array, not a string
    
#     Args:
#         agent_name: Name of the agent
#         content: Document content
#         embedding_vector: List of floats representing the embedding
#     """
    
#     # Ensure embedding is a list of floats
#     if isinstance(embedding_vector, str):
#         # If it's a string, parse it
#         try:
#             embedding_vector = json.loads(embedding_vector)
#         except json.JSONDecodeError:
#             embedding_vector = ast.literal_eval(embedding_vector)
    
#     # Make sure it's a flat list of floats
#     if isinstance(embedding_vector[0], list):
#         embedding_vector = embedding_vector[0]  # Unnest if needed
    
#     # Insert with proper formatting
#     data = {
#         'agent_name': agent_name,
#         'content': content,
#         'embedding': embedding_vector  # This will be sent as a proper array
#     }
    
#     result = supabase.table('agent_documents').insert(data).execute()
#     return result

# def verify_embeddings():
#     """Verify that embeddings are stored correctly"""
    
#     result = supabase.table('agent_documents')\
#         .select('id, agent_name, embedding')\
#         .limit(5)\
#         .execute()
    
#     for doc in result.data:
#         embedding = doc['embedding']
#         print(f"\nDocument {doc['id']} (agent: {doc['agent_name']}):")
#         print(f"  Type: {type(embedding)}")
        
#         if isinstance(embedding, list):
#             print(f"  Length: {len(embedding)}")
#             print(f"  First 3 values: {embedding[:3]}")
#             print("  ✓ Correctly stored as array")
#         else:
#             print("  ✗ Still stored as string!")

# # Example usage for OpenAI embeddings
# def get_and_store_openai_embedding(text, agent_name):
#     """Example of getting OpenAI embedding and storing it correctly"""
#     from openai import OpenAI
    
#     client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
#     # Get embedding
#     response = client.embeddings.create(
#         model="text-embedding-3-small",
#         input=text
#     )
    
#     # Extract the embedding vector (it's already a list)
#     embedding_vector = response.data[0].embedding
    
#     # Store it correctly
#     store_embedding_correctly(agent_name, text, embedding_vector)

# if __name__ == "__main__":
#     print("=== Fixing existing embeddings ===")
#     fix_existing_embeddings()
    
#     print("\n=== Verifying embeddings ===")
#     verify_embeddings()


# import os
# from supabase import create_client
# from dotenv import load_dotenv
# from openai import OpenAI

# load_dotenv()

# supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
# openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# async def test_rpc():
#     # Generate a test embedding
#     response = openai_client.embeddings.create(
#         model="text-embedding-3-small",
#         input="I need help with pricing for my website"
#     )
#     test_embedding = response.data[0].embedding
    
#     print(f"Test embedding dimensions: {len(test_embedding)}")
    
#     # Test match_agent_documents
#     try:
#         result = supabase.rpc(
#             'match_agent_documents',
#             {
#                 'query_embedding': test_embedding,
#                 'match_threshold': 0.5,
#                 'match_count': 5,
#                 'filter_agent': 'presaleskb'
#             }
#         ).execute()
        
#         print(f"\nmatch_agent_documents result:")
#         print(f"Found {len(result.data)} matches")
#         for item in result.data:
#             print(f"  - {item['agent_name']}: {item['similarity']:.3f}")
#     except Exception as e:
#         print(f"Error testing match_agent_documents: {e}")
    
#     # Test match_agents_by_similarity
#     try:
#         result = supabase.rpc(
#             'match_agents_by_similarity',
#             {
#                 'query_embedding': test_embedding,
#                 'match_threshold': 0.3,
#                 'match_count': 10
#             }
#         ).execute()
        
#         print(f"\nmatch_agents_by_similarity result:")
#         print(f"Found {len(result.data)} matches")
        
#         # Group by agent
#         agents = {}
#         for item in result.data:
#             agent = item['agent_name']
#             if agent not in agents or item['similarity'] > agents[agent]:
#                 agents[agent] = item['similarity']
        
#         for agent, score in sorted(agents.items(), key=lambda x: x[1], reverse=True):
#             print(f"  - {agent}: {score:.3f}")
            
#     except Exception as e:
#         print(f"Error testing match_agents_by_similarity: {e}")

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(test_rpc())






# # test_new_embeddings.py
# import asyncio
# from main_test import agent_matcher  # Adjust import path as needed
# import os
# from dotenv import load_dotenv

# load_dotenv()

# async def test_embedding_search():
#     # Test queries
#     test_queries = [
#         "I need help with pricing",
#         "Show me automation options",
#         "I want to analyze my website",
#         "I need a quote for my business"
#     ]
    
#     print("=== Testing Best Agent Matching ===")
#     for query in test_queries:
#         print(f"\nQuery: '{query}'")
        
#         # Get best agents
#         best_agents = await agent_matcher.find_best_agents(query, top_n=3)
        
#         for agent, score in best_agents:
#             print(f"  {agent}: {score:.2f}%")
    
#     # Test specific agent match
#     print("\n\n=== Testing Specific Agent Match ===")
#     test_cases = [
#         ("presaleskb", "I need analysis for my website"),
#         ("presaleskb", "Tell me about your services"),
#         ("leadgenkb", "I want to schedule a demo"),
#         ("socialmediakb", "Help with Facebook ads")
#     ]
    
#     for agent, query in test_cases:
#         is_match = await agent_matcher.check_agent_match(agent, query)
#         print(f"{agent} matches '{query}': {is_match}")

# if __name__ == "__main__":
#     asyncio.run(test_embedding_search())