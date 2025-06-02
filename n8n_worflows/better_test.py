import os
from supabase import create_client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def test_queries():
    # More specific queries that should match better
    test_queries = [
        # For presaleskb
        "I need someone to analyze my website and provide pricing",
        "pre-sales consultant for website analysis",
        "Alex can you help with pricing and ROI",
        "analyze client website and present pricing options",
        
        # For leadgenkb
        "James schedule a demo meeting",
        "lead generation specialist for follow-ups",
        "collect contact information and schedule meeting",
        
        # For socialmediakb
        "Sarah help with Facebook ads",
        "social media manager for digital presence",
        "LinkedIn strategy recommendations"
    ]
    
    print("Testing various queries:\n")
    
    for query in test_queries:
        print(f"Query: '{query}'")
        
        # Generate embedding
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        embedding = response.data[0].embedding
        
        # Search
        result = supabase.rpc('match_agents_by_similarity', {
            'query_embedding': embedding,
            'match_threshold': 0.2,  # Lower threshold
            'match_count': 3
        }).execute()
        
        if result.data:
            for doc in result.data[:3]:
                print(f"  - {doc['agent_name']}: {doc['similarity']:.3f}")
        else:
            print("  No matches")
        print()

if __name__ == "__main__":
    test_queries()