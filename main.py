# main.py - Complete integration with conversational handler and vector search agent matching

# Standard library imports
import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Set

# Third-party imports
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel
from supabase import create_client, Client

# Local imports
from agent_config import get_agent_config, AGENTS
from Website.web_scrape import capture_website_screenshot_async, get_website_favicon_async
from embedding_service import get_embedding

# Handler classes

class AgentMatcher:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self._cache = {}  # Cache for agent matching results
        self._cache_ttl = 300  # Cache TTL in seconds (5 minutes)

    async def get_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for the query text using free embedding service"""
        try:
            embedding = get_embedding(text)
            if embedding is None:
                raise Exception("Failed to generate embedding")
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    async def check_agent_match(self, agent_name: str, user_query: str, threshold: float = 0.2) -> bool:
        """Check if a specific agent matches the user query using vector similarity"""
        try:
            # Skip check if agent doesn't exist
            agent_check = self.supabase.table('agent_documents')\
                .select('id')\
                .eq('agent_name', agent_name)\
                .limit(1)\
                .execute()
            
            if not agent_check.data:
                logger.warning(f"No documents found for agent '{agent_name}' in database")
                return False

            # Get cached result if exists
            cache_key = f"agent_match_{agent_name}_{user_query}"
            cached = self._cache.get(cache_key)
            if cached and (datetime.now() - cached['timestamp']).total_seconds() < self._cache_ttl:
                return cached['result']

            # Check if this is a basic greeting - any agent can handle these
            basic_patterns = [
                'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
                'who are you', 'what are you', 'introduce yourself', 'tell me about yourself',
                'what do you do', 'what can you help with', 'how can you help', 'what services',
                'greetings', 'salutations', 'yo', 'howdy', 'how are you', 'how do you do',
                'nice to meet you', 'pleased to meet you', 'what is this', 'explain this',
                'help', 'assistance', 'support', 'info', 'information', 'thanks', 'thank you'
            ]
            
            query_lower = user_query.lower().strip()
            is_basic = any(pattern in query_lower for pattern in basic_patterns) or len(query_lower.split()) <= 3
            
            if is_basic:
                logger.debug(f"Basic query detected: Any agent can handle: '{user_query}'")
                match_result = True
            else:
                # Perform vector search for specific queries
                query_embedding = await self.get_query_embedding(user_query)
                
                result = self.supabase.rpc(
                    'match_agent_documents',
                    {
                        'query_embedding': query_embedding,
                        'match_threshold': threshold,
                        'match_count': 1,
                        'filter_agent': agent_name
                    }
                ).execute()
                
                # Simple check: if we have results above threshold, it's a match
                match_result = bool(result.data and len(result.data) > 0)
            
            # Cache the result
            self._cache[cache_key] = {
                'result': match_result,
                'timestamp': datetime.now()
            }

            logger.debug(f"Agent match {agent_name}: {'SUCCESS' if match_result else 'FAILED'}")
            return match_result
            
        except Exception as e:
            logger.error(f"Error checking agent match: {str(e)}")
            return False

    async def find_best_agents(self, user_query: str, top_n: int = 3) -> List[str]:
        """Find the best matching agents for a user query using vector similarity"""
        try:
            # Get cached result if exists
            cache_key = f"best_agents_{user_query}"
            cached = self._cache.get(cache_key)
            if cached and (datetime.now() - cached['timestamp']).total_seconds() < self._cache_ttl:
                return cached['result']

            query_embedding = await self.get_query_embedding(user_query)
            
            result = self.supabase.rpc(
                'match_agents_by_similarity',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': 0.2,  # Lower threshold
                    'match_count': top_n
                }
            ).execute()
            
            if not result.data:
                return ['presaleskb']
            
            # Extract just agent names in order of similarity
            agent_names = [item['agent_name'] for item in result.data]
            
            # Cache the result
            self._cache[cache_key] = {
                'result': agent_names,
                'timestamp': datetime.now()
            }
            
            return agent_names
            
        except Exception as e:
            logger.error(f"Error finding best agents: {str(e)}")
            return ['presaleskb']

    async def get_recommended_agent(self, user_query: str) -> str:
        """Get the single best recommended agent for a query"""
        try:
            # Get cached result if exists
            cache_key = f"recommended_agent_{user_query}"
            cached = self._cache.get(cache_key)
            if cached and (datetime.now() - cached['timestamp']).total_seconds() < self._cache_ttl:
                return cached['result']

            best_agents = await self.find_best_agents(user_query, top_n=1)
            
            # Return first agent if found, else default
            agent = best_agents[0] if best_agents else 'presaleskb'

            # Cache the result
            self._cache[cache_key] = {
                'result': agent,
                'timestamp': datetime.now()
            }
            
            return agent
            
        except Exception as e:
            logger.error(f"Error getting recommended agent: {str(e)}")
            return 'presaleskb'

# Conversational Handler Class
class ConversationalHandler:
    def __init__(self, supabase_client, n8n_url: str = os.getenv('N8N_MAIN', 'https://n8n.theaiteam.uk/webhook/c2fcbad6-abc0-43af-8aa8-d1661ff4461d')):
        self._cache = {}  # Simple in-memory cache
        self._cache_ttl = 300  # Cache TTL in seconds (5 minutes)
        self.supabase = supabase_client
        self.n8n_url = n8n_url

    async def get_cached_response(self, request_id: str):
        """Get cached response if it exists and is not expired"""
        cache_key = f"response_{request_id}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached['timestamp']).total_seconds() < self._cache_ttl:
                return cached['response']
            del self._cache[cache_key]
        return None

    async def cache_response(self, request_id: str, response: dict):
        """Cache a response with TTL"""
        cache_key = f"response_{request_id}"
        self._cache[cache_key] = {
            'response': response,
            'timestamp': datetime.now()
        }

    async def save_to_history(self, session_id: str, user_id: str, user_message: str, agent_response: str):
        """Save message to chat history"""
        try:
            entry = {
                'session_id': session_id,
                'user_id': user_id,
                'user_message': user_message,
                'agent_response': agent_response,
                'timestamp': datetime.now().isoformat()
            }
            
            result = self.supabase.table('chat_history')\
                .insert(entry)\
                .execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Error saving to history: {str(e)}")
            return None

    async def handle_message(self, request_data: dict):
        """Handle incoming message with conversational logic"""
        try:
            user_mssg = request_data.get('user_mssg', '')
            session_id = request_data.get('session_id', '')
            user_id = request_data.get('user_id', '')
            agent_name = request_data.get('agent_name', 'presaleskb')
            request_id = request_data.get('request_id', str(uuid.uuid4()))

            # Skip empty messages
            if not user_mssg.strip():
                return {
                    'status': 'error',
                    'message': 'Empty message received'
                }

            # Check cache first
            cached_response = await self.get_cached_response(request_id)
            if cached_response:
                return cached_response

            # Process the message
            response = await self.process_message(user_mssg, session_id, user_id, agent_name)

            # Cache the response
            await self.cache_response(request_id, response)

            return response

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            raise

    async def process_message(self, user_mssg: str, session_id: str, user_id: str, agent_name: str):
        """Process the actual message and get response from n8n"""
        try:
            # Prepare payload for n8n
            payload = {
                'user_id': user_id,
                'user_mssg': user_mssg,
                'session_id': session_id,
                'agent_name': agent_name,
                '_original_message': user_mssg  # Store original message for history
            }

            # Call n8n webhook
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(self.n8n_url, json=payload)
                response.raise_for_status()
                
                # Check if response has content before parsing JSON
                if not response.text.strip():
                    logger.error(f"N8N returned empty response body. Status: {response.status_code}")
                    raise Exception("N8N workflow returned empty response - check workflow configuration")
                
                try:
                    n8n_response = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"N8N returned invalid JSON. Raw response: '{response.text}'")
                    raise Exception(f"N8N workflow returned invalid JSON: {str(e)}")
                
                # Log the full N8N response for testing
                logger.debug(f"N8N Response: {json.dumps(n8n_response, indent=2)}")

            # Format response
            formatted_response = {
                'status': n8n_response.get('status', 'success'),
                'agent_name': n8n_response.get('agent_name', agent_name),
                'agent_response': n8n_response.get('agent_response', ''),
                'conversation_state': n8n_response.get('conversation_state', 'complete'),
                'missing_info': n8n_response.get('missing_info', []),
                'timestamp': datetime.now().isoformat()
            }

            return formatted_response

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

# Client KB Manager Class
class ClientKBManager:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        
    async def update_client_kb(self, user_id: str, query: str, agent_name: str):
        """Update client's knowledge base with new query using optimized schema"""
        try:
            start_time = time.time()
            
            # Generate embedding for the query using free service
            query_embedding = await AgentMatcher(self.supabase).get_query_embedding(query)
            
            # Determine context type based on query content
            context_type = self._determine_context_type(query)
            
            # Structure content for better searchability
            content = {
                'query': query,
                'agent_interaction': agent_name,
                'interaction_timestamp': datetime.now().isoformat(),
                'query_type': context_type,
                'user_intent': self._extract_user_intent(query)
            }
            
            # Use optimized client_context table for better performance
            entry = {
                'client_id': user_id,
                'context_type': context_type,
                'content': content,
                'embedding': query_embedding,
                'source_url': None,
                'confidence_score': 1.0,
                'is_active': True
            }
            
            # Use upsert to avoid duplicates while maintaining speed
            result = self.supabase.table('client_context')\
                .upsert(entry, on_conflict='client_id,context_type')\
                .execute()
            
            # Log performance for monitoring
            execution_time = int((time.time() - start_time) * 1000)
            await log_performance_metric("update_client_kb", execution_time, {
                "user_id": user_id,
                "agent_name": agent_name,
                "context_type": context_type,
                "has_embedding": bool(query_embedding)
            })
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            # Log error performance
            execution_time = int((time.time() - start_time) * 1000)
            await log_performance_metric("update_client_kb_error", execution_time, {
                "user_id": user_id,
                "agent_name": agent_name,
                "error": str(e)
            }, success=False, error_message=str(e))
            
            logger.error(f"Error updating client KB: {str(e)}")
            return None
    
    def _determine_context_type(self, query: str) -> str:
        """Determine the type of context based on query content for faster categorization"""
        query_lower = query.lower()
        
        if any(indicator in query_lower for indicator in ['http://', 'https://', 'www.', '.com', '.org']):
            return 'website_info'
        elif any(social in query_lower for social in ['facebook', 'instagram', 'linkedin', 'twitter', 'social']):
            return 'social_media'
        elif any(business in query_lower for business in ['business', 'company', 'industry', 'service', 'product']):
            return 'business_info'
        elif any(location in query_lower for location in ['address', 'location', 'city', 'state', 'country']):
            return 'location_info'
        else:
            return 'general_query'
    
    def _extract_user_intent(self, query: str) -> str:
        """Extract user intent for better context understanding"""
        query_lower = query.lower()
        
        if any(intent in query_lower for intent in ['want', 'need', 'looking for', 'require']):
            return 'requirement'
        elif any(intent in query_lower for intent in ['how', 'what', 'where', 'when', 'why']):
            return 'information_seeking'
        elif any(intent in query_lower for intent in ['help', 'assist', 'support']):
            return 'assistance_request'
        elif any(intent in query_lower for intent in ['problem', 'issue', 'error', 'wrong']):
            return 'problem_solving'
        else:
            return 'general_interaction'

# Dynamic Agent KB Handler Class
class DynamicAgentKBHandler:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        
    async def update_agent_kb(self, agent_name: str, query: str, user_id: str):
        """Update agent's knowledge base with new query"""
        try:
            # Use upsert for more efficient database operation
            entry = {
                'agent_name': agent_name,
                'query': query,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            }
            
            result = self.supabase.table('agent_kb')\
                .upsert(entry, on_conflict='agent_name')\
                .execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Error updating agent KB: {str(e)}")
            return None
    
    async def get_agent_context_from_kb(self, agent_name: str) -> Dict[str, Any]:
        """Get agent context and knowledge base information"""
        try:
            # Get agent configuration from agent_config.py
            from agent_config import get_agent_config
            agent_config = get_agent_config(agent_name)
            
            if not agent_config:
                logger.warning(f"No configuration found for agent: {agent_name}")
                return {
                    'agent_name': agent_name,
                    'description': f"General purpose {agent_name} agent",
                    'must_questions': [],
                    'tools': [],
                    'system_prompt': f"You are {agent_name}, a helpful AI assistant."
                }
            
            # Get recent agent knowledge from database
            try:
                kb_result = self.supabase.table('agent_documents')\
                    .select('content, metadata')\
                    .eq('agent_name', agent_name)\
                    .limit(5)\
                    .execute()
                
                recent_knowledge = []
                if kb_result.data:
                    recent_knowledge = [doc['content'][:500] for doc in kb_result.data[:3]]
                
                agent_config['recent_knowledge'] = recent_knowledge
                
            except Exception as e:
                logger.warning(f"Error getting agent knowledge: {e}")
                agent_config['recent_knowledge'] = []
            
            return agent_config
            
        except Exception as e:
            logger.error(f"Error getting agent context: {e}")
            return {
                'agent_name': agent_name,
                'description': f"General purpose {agent_name} agent",
                'must_questions': [],
                'tools': [],
                'system_prompt': f"You are {agent_name}, a helpful AI assistant.",
                'recent_knowledge': []
            }
    
    async def get_client_industry_context(self, user_id: str) -> Dict[str, Any]:
        """Get client industry and context information"""
        try:
            # Try to get from client_kb first
            result = self.supabase.table('client_kb')\
                .select('*')\
                .eq('user_id', user_id)\
                .limit(1)\
                .execute()
            
            if result.data:
                content = result.data[0].get('content', {})
                return {
                    'user_id': user_id,
                    'niche': content.get('niche', 'Unknown'),
                    'industry': content.get('industry', 'General'),
                    'business_type': content.get('business_type', 'Unknown'),
                    'context_available': True
                }
            
            # Fallback: infer from website data
            website_result = self.supabase.table('website_data')\
                .select('analysis')\
                .eq('user_id', user_id)\
                .limit(1)\
                .execute()
            
            if website_result.data:
                analysis = website_result.data[0].get('analysis', '')
                # Simple industry detection
                industry = 'General'
                if any(term in analysis.lower() for term in ['tech', 'software', 'saas']):
                    industry = 'Technology'
                elif any(term in analysis.lower() for term in ['health', 'medical', 'wellness']):
                    industry = 'Healthcare'
                elif any(term in analysis.lower() for term in ['finance', 'investment', 'banking']):
                    industry = 'Finance'
                
                return {
                    'user_id': user_id,
                    'niche': 'Inferred from website',
                    'industry': industry,
                    'business_type': 'Unknown',
                    'context_available': True
                }
            
            return {
                'user_id': user_id,
                'niche': 'Unknown',
                'industry': 'General',
                'business_type': 'Unknown',
                'context_available': False
            }
            
        except Exception as e:
            logger.error(f"Error getting client context: {e}")
            return {
                'user_id': user_id,
                'niche': 'Unknown',
                'industry': 'General',
                'business_type': 'Unknown',
                'context_available': False
            }
    
    async def analyze_query_with_context(self, query: str, agent_context: Dict, client_context: Dict, kb_context: Dict) -> Dict[str, Any]:
        """Analyze if the query can be answered with available context"""
        try:
            # Simple analysis logic
            confidence = 0.5  # Base confidence
            
            # Increase confidence if we have relevant context
            if kb_context.get('has_sufficient_context', False):
                confidence += 0.3
            
            if client_context.get('context_available', False):
                confidence += 0.2
            
            if len(agent_context.get('recent_knowledge', [])) > 0:
                confidence += 0.2
            
            # Check if query matches agent's domain
            agent_name = agent_context.get('agent_name', '').lower()
            query_lower = query.lower()
            
            if agent_name in query_lower or any(keyword in query_lower for keyword in [
                'social media' if 'social' in agent_name else '',
                'lead' if 'lead' in agent_name else '',
                'sales' if 'sales' in agent_name or 'presales' in agent_name else ''
            ]):
                confidence += 0.2
            
            confidence = min(confidence, 1.0)
            
            return {
                'can_answer': confidence > 0.7,
                'confidence': confidence,
                'required_tools': [],
                'missing_info': []
            }
            
        except Exception as e:
            logger.error(f"Error analyzing query: {e}")
            return {
                'can_answer': False,
                'confidence': 0.3,
                'required_tools': [],
                'missing_info': ['context_analysis_failed']
            }
    
    async def generate_contextual_response(self, query: str, agent_context: Dict, client_context: Dict, kb_context: Dict, tools: List = None) -> str:
        """Generate a contextual response using available information"""
        try:
            agent_name = agent_context.get('agent_name', 'Assistant')
            industry = client_context.get('industry', 'your business')
            
            # Build a simple contextual response
            response_parts = [
                f"Hello! I'm {agent_name}, your {industry.lower()} specialist.",
                f"Regarding your question: '{query}'"
            ]
            
            # Add context-specific information
            if kb_context.get('website_info'):
                response_parts.append("Based on your website information, I can provide targeted advice.")
            
            if agent_context.get('recent_knowledge'):
                response_parts.append("I have relevant knowledge from my training that applies to your situation.")
            
            # Add domain-specific response
            if 'social' in agent_name.lower():
                response_parts.append("For social media marketing, I recommend starting with a content strategy that aligns with your brand voice and target audience.")
            elif 'lead' in agent_name.lower():
                response_parts.append("For lead generation, let's focus on identifying your ideal customer profile and the most effective channels to reach them.")
            elif 'sales' in agent_name.lower() or 'presales' in agent_name.lower():
                response_parts.append("For sales optimization, we should analyze your current sales funnel and identify opportunities for improvement.")
            else:
                response_parts.append("I'm here to help you with your business needs.")
            
            if tools:
                response_parts.append(f"I have {len(tools)} specialized tools available to assist you further.")
            
            return " ".join(response_parts)
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"I understand you're asking about '{query}'. I'm here to help, though I may need a bit more context to provide the most relevant advice."
    
    async def generate_contextual_questions(self, query: str, agent_context: Dict, missing_info: List[str], client_context: Dict) -> List[str]:
        """Generate follow-up questions to gather missing information"""
        try:
            questions = []
            
            for info in missing_info:
                if info == 'website_url':
                    questions.append("What's your website URL so I can better understand your business?")
                elif info == 'client_niche':
                    questions.append("What industry or niche is your business in?")
                elif info == 'property_address':
                    questions.append("What's the address or location for this property?")
                else:
                    questions.append(f"Could you provide more details about {info.replace('_', ' ')}?")
            
            # Add agent-specific questions
            agent_name = agent_context.get('agent_name', '').lower()
            if 'social' in agent_name and len(questions) < 3:
                questions.append("What social media platforms are you currently using?")
            elif 'lead' in agent_name and len(questions) < 3:
                questions.append("What's your current lead generation strategy?")
            elif 'sales' in agent_name and len(questions) < 3:
                questions.append("What's your average deal size or sales cycle?")
            
            return questions[:3]  # Limit to 3 questions
            
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            return ["Could you provide more context about your business and specific needs?"]


load_dotenv()
# Initialize FastAPI app
app = FastAPI()
logger = logging.getLogger(__name__)
active_connections: Dict[str, WebSocket] = {}
streaming_sessions: Dict[str, Dict[str, Any]] = {}
# Request deduplication cache
request_cache: Dict[str, float] = {}

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
N8N_MAIN = os.getenv("N8N_MAIN", "https://n8n.theaiteam.uk/webhook/c2fcbad6-abc0-43af-8aa8-d1661ff4461d")
N8N_MAIN_TEST = os.getenv("N8N_MAIN_TEST")

N8N_STREAM_TEST = os.getenv("N8N_STREAM_TEST")
N8N_STREAM_TEST_TEST = os.getenv("N8N_STREAM_TEST_TEST")


print(f"Using Supabase URL: {SUPABASE_URL}")

# Initialize Supabase client
def create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize handlers
active_requests: Set[str] = set()

# Initialize Supabase client  
supabase = create_supabase_client()

# Initialize handlers
agent_matcher = AgentMatcher(supabase_client=supabase)
conversational_handler = ConversationalHandler(
    supabase_client=supabase,
    n8n_url=os.getenv('N8N_MAIN', 'https://n8n.theaiteam.uk/webhook/c2fcbad6-abc0-43af-8aa8-d1661ff4461d')
)
client_kb_manager = ClientKBManager(supabase_client=supabase)
dynamic_agent_kb_handler = DynamicAgentKBHandler(supabase_client=supabase)

print("Application initialized")

background_results = {}
running_tasks: Dict[str, Dict[str, Any]] = {}

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AGENT_DESCRIPTIONS = {
    agent_name: agent_config.description 
    for agent_name, agent_config in AGENTS.items()
}


# Models
class WebsiteFaviconRequest(BaseModel):
    url: str
    session_id: str
    user_id: str

class N8nMainRequest(BaseModel):
    user_id: str
    user_mssg: str
    session_id: str
    agent_name: str
    timestamp_of_call_made: Optional[str] = None
    request_id: Optional[str] = None

class N8nResponse(BaseModel):
    user_id: str
    agent_name: str
    agent_response: str
    responses: List[Dict[str, Any]]
    timestamp: str
    status: str

class StreamUpdate(BaseModel):
    type: str
    user_id: str
    agent_name: Optional[str] = None
    agent_names: Optional[str] = None
    message: str
    progress: int
    agent_response: Optional[str] = None
    metadata: dict

class ConversationState(Enum):
    INITIAL = "initial"
    COLLECTING_INFO = "collecting_info"
    PROCESSING = "processing"
    COMPLETE = "complete"

class N8nCheckAgentMatchRequest(BaseModel):
    agent_name: str
    user_query: str
    threshold: Optional[float] = 0.3

class N8nFindBestAgentsRequest(BaseModel):
    user_query: str
    top_n: Optional[int] = 3
    min_threshold: Optional[float] = 0.3

class ClientKBCheckRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    force_refresh: Optional[bool] = False

class ClientKBResponse(BaseModel):
    user_id: str
    has_website_info: bool
    website_url: Optional[str] = None
    website_analysis: Optional[Dict[str, Any]] = None
    company_info: Optional[Dict[str, Any]] = None
    kb_status: str
    message: str
    action_required: Optional[str] = None
    last_updated: Optional[str] = None

class AgentKBQueryRequest(BaseModel):
    user_id: str
    user_mssg: str
    agent: str

class AgentKBQueryResponse(BaseModel):
    user_id: str
    agent: str
    response_type: str  # "direct_answer", "needs_tools", "needs_info"
    agent_response: Optional[str] = None
    required_tools: Optional[List[Dict[str, Any]]] = None
    follow_up_questions: Optional[List[str]] = None
    missing_information: Optional[List[Dict[str, Any]]] = None
    confidence_score: float
    kb_context_used: bool
    status: str

class WebsiteAnalysisRequest(BaseModel):
    url: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

class WebsiteScreenshotRequest(BaseModel):
    url: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

# Conversational Handler Class
# API Endpoints
@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Squidgy AI WebSocket Server is running"}

@app.get("/health")
async def health_check_detailed():
    return {
        "status": "healthy",
        "active_connections": len(active_connections),
        "streaming_sessions": len(streaming_sessions)
    }

@app.get("/debug/agent-docs/{agent_name}")
async def debug_agent_docs(agent_name: str):
    """Debug endpoint to check agent documents in database"""
    try:
        docs = supabase.table('agent_documents')\
            .select('id, content')\
            .eq('agent_name', agent_name)\
            .execute()
        
        return {
            "agent_name": agent_name,
            "documents_found": len(docs.data) if docs.data else 0,
            "documents": docs.data[:3] if docs.data else [],  # Show first 3 docs
            "sample_content": docs.data[0]['content'][:200] + "..." if docs.data else None
        }
    except Exception as e:
        return {"error": str(e)}

# Agent matching endpoints
# @app.post("/api/agents/check-match")
# async def check_agent_match_endpoint(agent_name: str, user_query: str):
#     """API endpoint to check if an agent matches a query using vector similarity"""
#     try:
#         is_match = await agent_matcher.check_agent_match(agent_name, user_query)
#         return {
#             "agent_name": agent_name,
#             "user_query": user_query,
#             "is_match": is_match
#         }
#     except Exception as e:
#         logger.error(f"Error checking agent match: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @app.post("/api/agents/find-best")
# async def find_best_agents_endpoint(user_query: str, top_n: int = 3):
#     """API endpoint to find best matching agents using vector similarity"""
#     try:
#         best_agents = await agent_matcher.find_best_agents(user_query, top_n)
#         return {
#             "user_query": user_query,
#             "recommendations": [
#                 {
#                     "agent_name": agent_name,
#                     "match_percentage": round(score, 2),
#                     "rank": idx + 1
#                 }
#                 for idx, (agent_name, score) in enumerate(best_agents)
#             ]
#         }
#     except Exception as e:
#         logger.error(f"Error finding best agents: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# N8N agent matching endpoints
@app.post("/n8n/check_agent_match")
async def n8n_check_agent_match(request: N8nCheckAgentMatchRequest):
    """N8N webhook endpoint to check if a specific agent matches the user query"""
    try:
        is_match = await agent_matcher.check_agent_match(
            agent_name=request.agent_name,
            user_query=request.user_query,
            threshold=request.threshold
        )
        
        # Debug logging
        logger.debug(f"Agent Match Check - Agent: {request.agent_name}, Query: {request.user_query}, Result: {is_match}")
        
        return {
            "agent_name": request.agent_name,
            "user_query": request.user_query,
            "is_match": is_match,
            "threshold_used": request.threshold,
            "recommendation": f"Agent '{request.agent_name}' is {'suitable' if is_match else 'not optimal'} for this query",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error in n8n_check_agent_match: {str(e)}")
        return {
            "agent_name": request.agent_name,
            "user_query": request.user_query,
            "is_match": False,
            "error": str(e),
            "status": "error"
        }

@app.post("/n8n/find_best_agents")
async def n8n_find_best_agents(request: N8nFindBestAgentsRequest):
    """N8N webhook endpoint to find the best matching agents for a user query"""
    try:
        best_agents = await agent_matcher.find_best_agents(
            user_query=request.user_query,
            top_n=request.top_n
        )
        
        recommendations = []
        for idx, agent_name in enumerate(best_agents):
            # Simplified quality assessment - all matched agents are good
            quality = "Good match"
            description = f"{quality} - {AGENT_DESCRIPTIONS.get(agent_name, 'handles specialized queries')}"
            
            recommendations.append({
                "agent_name": agent_name,
                "rank": idx + 1,
                "description": description
            })
        
        response = {
            "user_query": request.user_query,
            "recommendations": recommendations,
            "total_agents_found": len(recommendations),
            "status": "success"
        }
        
        if recommendations:
            response["best_agent"] = recommendations[0]["agent_name"]
        else:
            response["best_agent"] = "presaleskb"
            response["message"] = "No agents found, using default agent"
        
        return response
        
    except Exception as e:
        logger.error(f"Error in n8n_find_best_agents: {str(e)}")
        return {
            "user_query": request.user_query,
            "best_agent": "presaleskb",
            "recommendations": [],
            "error": str(e),
            "status": "error",
            "message": "Error finding agents, using default"
        }

@app.post("/n8n/analyze_agent_query")
async def n8n_analyze_agent_query(request: Dict[str, Any]):
    """Combined N8N webhook endpoint that performs both agent checking and recommendation"""
    try:
        user_query = request.get("user_query", "")
        current_agent = request.get("current_agent")
        get_recommendations = request.get("get_recommendations", True)
        top_n = request.get("top_n", 3)
        
        response = {
            "user_query": user_query,
            "analysis_timestamp": datetime.now().isoformat(),
            "status": "success"
        }
        
        if current_agent:
            is_match = await agent_matcher.check_agent_match(current_agent, user_query)
            response["current_agent_analysis"] = {
                "agent_name": current_agent,
                "is_suitable": is_match,
                "recommendation": "Keep current agent" if is_match else "Consider switching agents"
            }
        
        if get_recommendations:
            best_agents = await agent_matcher.find_best_agents(user_query, top_n)
            
            response["recommended_agents"] = [
                {
                    "agent_name": name,
                    "rank": idx + 1
                }
                for idx, name in enumerate(best_agents)
            ]
            
            if best_agents:
                best_agent = best_agents[0]
                
                if current_agent and current_agent == best_agent:
                    response["routing_decision"] = "keep_current"
                    response["routing_message"] = f"Current agent '{current_agent}' is optimal"
                else:
                    response["routing_decision"] = "switch_agent"
                    response["suggested_agent"] = best_agent
                    response["routing_message"] = f"Switch to '{best_agent}'"
            else:
                response["routing_decision"] = "use_default"
                response["suggested_agent"] = "presaleskb"
                response["routing_message"] = "No match found, use default agent"
        
        return response
        
    except Exception as e:
        logger.error(f"Error in n8n_analyze_agent_query: {str(e)}")
        return {
            "user_query": request.get("user_query", ""),
            "error": str(e),
            "status": "error",
            "routing_decision": "use_default",
            "suggested_agent": "presaleskb"
        }

@app.get("/n8n/agent_matcher/health")
async def n8n_agent_matcher_health():
    """Health check for agent matching service"""
    try:
        agent_matcher.supabase.table('agent_documents').select('id').limit(1).execute()
        
        return {
            "service": "agent_matcher",
            "status": "healthy",
            "database": "connected",
            "endpoints": [
                "/n8n/check_agent_match",
                "/n8n/find_best_agents",
                "/n8n/analyze_agent_query"
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "service": "agent_matcher",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Client KB endpoints
@app.post("/n8n/client/check_kb")
async def check_client_kb(request: ClientKBCheckRequest):
    """Check if client has website information in KB and return appropriate response"""
    try:
        kb_data = await client_kb_manager.get_client_kb(request.user_id, 'website_info')
        
        if kb_data and not request.force_refresh:
            content = kb_data.get('content', {})
            website_info = content.get('website_info', {})
            
            return ClientKBResponse(
                user_id=request.user_id,
                has_website_info=True,
                website_url=website_info.get('url'),
                website_analysis=website_info,
                company_info={
                    'name': website_info.get('company_name'),
                    'niche': website_info.get('niche'),
                    'description': website_info.get('description'),
                    'services': website_info.get('services', [])
                },
                kb_status='complete',
                message='Client information found',
                last_updated=kb_data.get('updated_at')
            )
        
        website_result = None
        if request.session_id:
            website_result = supabase.table('website_data')\
                .select('*')\
                .eq('user_id', request.user_id)\
                .eq('session_id', request.session_id)\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
        else:
            website_result = supabase.table('website_data')\
                .select('*')\
                .eq('user_id', request.user_id)\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
        
        if website_result and website_result.data:
            website_data = website_result.data[0]
            
            chat_history_result = supabase.table('chat_history')\
                .select('*')\
                .eq('user_id', request.user_id)\
                .order('timestamp', desc=False)\
                .execute()
            
            chat_history = chat_history_result.data if chat_history_result else []
            
            kb_content = await client_kb_manager.analyze_and_update_kb(
                request.user_id,
                website_data,
                chat_history
            )
            
            if kb_content:
                website_info = kb_content.get('website_info', {})
                return ClientKBResponse(
                    user_id=request.user_id,
                    has_website_info=True,
                    website_url=website_info.get('url'),
                    website_analysis=website_info,
                    company_info={
                        'name': website_info.get('company_name'),
                        'niche': website_info.get('niche'),
                        'description': website_info.get('description'),
                        'services': website_info.get('services', [])
                    },
                    kb_status='updated',
                    message='Client KB updated with latest information',
                    last_updated=datetime.now().isoformat()
                )
        
        return ClientKBResponse(
            user_id=request.user_id,
            has_website_info=False,
            kb_status='missing_website',
            message='Please provide your website URL to continue',
            action_required='collect_website_url'
        )
        
    except Exception as e:
        logger.error(f"Error checking client KB: {str(e)}")
        return ClientKBResponse(
            user_id=request.user_id,
            has_website_info=False,
            kb_status='error',
            message=f'Error checking client information: {str(e)}',
            action_required='retry'
        )

@app.post("/n8n/client/update_website")
async def update_client_website(request: Dict[str, Any]):
    """Update client KB when website URL is provided"""
    try:
        user_id = request.get('user_id')
        session_id = request.get('session_id')
        website_url = request.get('website_url')
        
        if not all([user_id, website_url]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        analysis = await conversational_handler.analyze_website_with_perplexity(website_url)
        
        website_entry = {
            'user_id': user_id,
            'session_id': session_id or str(uuid.uuid4()),
            'url': website_url,
            'analysis': json.dumps(analysis) if analysis else None,
            'created_at': datetime.now().isoformat()
        }
        
        website_result = supabase.table('website_data')\
            .upsert(website_entry, on_conflict='session_id,url')\
            .execute()
        
        if website_result.data:
            chat_history_result = supabase.table('chat_history')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('timestamp', desc=False)\
                .execute()
            
            chat_history = chat_history_result.data if chat_history_result else []
            
            kb_content = await client_kb_manager.analyze_and_update_kb(
                user_id,
                website_result.data[0],
                chat_history
            )
            
            return {
                'status': 'success',
                'user_id': user_id,
                'website_url': website_url,
                'analysis': analysis,
                'kb_updated': bool(kb_content),
                'message': 'Website information saved and KB updated'
            }
        
    except Exception as e:
        logger.error(f"Error updating client website: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/n8n/client/context/{user_id}")
async def get_client_context(user_id: str):
    """Get complete client context for agent use"""
    try:
        kb_results = supabase.table('client_kb')\
            .select('*')\
            .eq('client_id', user_id)\
            .execute()
        
        context = {
            'user_id': user_id,
            'kb_entries': {}
        }
        
        if kb_results.data:
            for entry in kb_results.data:
                context['kb_entries'][entry['kb_type']] = entry['content']
        
        chat_history = supabase.table('chat_history')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('timestamp', desc=False)\
            .limit(50)\
            .execute()
        
        context['recent_conversations'] = chat_history.data if chat_history else []
        
        website_data = supabase.table('website_data')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if website_data and website_data.data:
            context['current_website'] = website_data.data[0]
        
        return context
        
    except Exception as e:
        logger.error(f"Error getting client context: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/n8n/check_client_kb")
async def n8n_check_client_kb(request: Dict[str, Any]):
    """N8N-specific endpoint for checking client KB"""
    try:
        kb_request = ClientKBCheckRequest(
            user_id=request.get('user_id'),
            session_id=request.get('session_id'),
            force_refresh=request.get('force_refresh', False)
        )
        
        response = await check_client_kb(kb_request)
        
        n8n_response = response.model_dump()
        
        if response.has_website_info:
            n8n_response['next_action'] = 'proceed_with_agent'
            n8n_response['routing'] = 'continue'
        else:
            n8n_response['next_action'] = 'request_website'
            n8n_response['routing'] = 'collect_info'
            n8n_response['prompt_message'] = "To provide you with accurate information about our services and pricing, could you please share your website URL?"
        
        return n8n_response
        
    except Exception as e:
        logger.error(f"Error in n8n_check_client_kb: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'next_action': 'handle_error',
            'routing': 'error'
        }

# WebSocket message processing function that calls n8n
async def process_websocket_message_with_n8n(request_data: Dict[str, Any], websocket: WebSocket, request_id: str):
    """Process WebSocket message through n8n workflow (same as HTTP endpoints)"""
    try:
        logger.info(f"Processing WebSocket message via n8n: {request_id}")
        
        # Use the same conversational handler as HTTP endpoints
        n8n_response = await conversational_handler.handle_message(request_data)
        
        logger.info(f"✅ n8n response received for request {request_id}")
        print(f"✅ n8n response received for request {request_id}")
        
        # Send response back through WebSocket
        try:
            await websocket.send_json({
                "type": "response",
                "requestId": request_id,
                "response": n8n_response,
                "timestamp": int(time.time() * 1000)
            })
            logger.info(f"📤 Response sent via WebSocket for request {request_id}")
            print(f"📤 Response sent via WebSocket for request {request_id}")
        except Exception as ws_error:
            logger.error(f"❌ Failed to send WebSocket response for request {request_id}: {ws_error}")
            print(f"❌ Failed to send WebSocket response for request {request_id}: {ws_error}")
            raise
        
        # Save to chat history (same as HTTP endpoints)
        await conversational_handler.save_to_history(
            request_data["session_id"],
            request_data["user_id"], 
            request_data["user_mssg"],
            n8n_response.get("agent_response", "")
        )
        
        logger.info(f"✅ WebSocket message processed successfully: {request_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing WebSocket message {request_id}: {str(e)}")
        
        # Send error response
        try:
            await websocket.send_json({
                "type": "error",
                "requestId": request_id,
                "error": str(e),
                "timestamp": int(time.time() * 1000)
            })
        except Exception as send_error:
            logger.error(f"Failed to send error response: {send_error}")

# Helper functions for optimized client context aggregation
async def get_optimized_client_context(user_id: str, query_embedding: List[float]) -> Dict[str, Any]:
    """Get comprehensive client context using optimized database functions"""
    try:
        # Use the optimized function from the new schema
        result = supabase.rpc('get_client_context_similarity', {
            'client_id_param': user_id,
            'query_embedding': query_embedding,
            'similarity_threshold': 0.7,
            'limit_count': 10
        }).execute()
        
        context_data = {}
        if result.data:
            # Aggregate different types of context
            for item in result.data:
                context_type = item['context_type']
                content = item['content']
                similarity = item['similarity']
                
                if context_type not in context_data:
                    context_data[context_type] = []
                
                context_data[context_type].append({
                    'content': content,
                    'similarity': similarity,
                    'id': item['id']
                })
        
        # Fallback to legacy client industry context if no optimized data
        if not context_data:
            return await dynamic_agent_kb_handler.get_client_industry_context(user_id)
        
        # Build structured client context
        structured_context = {
            'user_id': user_id,
            'context_sources': len(context_data),
            'website_info': context_data.get('website_info', []),
            'social_media': context_data.get('social_media', []),
            'business_info': context_data.get('business_info', []),
            'other_sources': {k: v for k, v in context_data.items() 
                           if k not in ['website_info', 'social_media', 'business_info']}
        }
        
        return structured_context
        
    except Exception as e:
        logger.warning(f"Error getting optimized client context: {e}")
        # Fallback to legacy method
        return await dynamic_agent_kb_handler.get_client_industry_context(user_id)

async def get_optimized_agent_knowledge(agent_name: str, query_embedding: List[float]) -> Dict[str, Any]:
    """Get agent knowledge using optimized database function with usage tracking"""
    try:
        # Use the optimized function from the new schema
        result = supabase.rpc('get_agent_knowledge_smart', {
            'agent_name_param': agent_name,
            'query_embedding': query_embedding,
            'similarity_threshold': 0.7,
            'limit_count': 5
        }).execute()
        
        knowledge_data = {
            'agent_name': agent_name,
            'knowledge_items': [],
            'total_relevance': 0.0
        }
        
        if result.data:
            for item in result.data:
                knowledge_item = {
                    'id': item['id'],
                    'content': item['content'],
                    'metadata': item['metadata'],
                    'similarity': item['similarity'],
                    'relevance_score': item['relevance_score'],
                    'combined_score': item['similarity'] * item['relevance_score']
                }
                knowledge_data['knowledge_items'].append(knowledge_item)
                knowledge_data['total_relevance'] += knowledge_item['combined_score']
        
        return knowledge_data
        
    except Exception as e:
        logger.warning(f"Error getting optimized agent knowledge: {e}")
        # Fallback to legacy method
        return await dynamic_agent_kb_handler.get_agent_context_from_kb(agent_name)

async def build_enhanced_kb_context(user_id: str, client_context: Dict, agent_knowledge: Dict) -> Dict[str, Any]:
    """Build comprehensive KB context from multiple optimized sources"""
    try:
        kb_context = {
            'sources': [],
            'website_info': {},
            'social_media': {},
            'business_info': {},
            'chat_history': {},
            'agent_insights': {},
            'similarity_scores': {}
        }
        
        # Process client context data
        if client_context.get('website_info'):
            for item in client_context['website_info']:
                content = item['content']
                kb_context['website_info'].update(content)
                kb_context['sources'].append('website_info')
                kb_context['similarity_scores']['website_info'] = item['similarity']
        
        if client_context.get('social_media'):
            for item in client_context['social_media']:
                content = item['content']
                kb_context['social_media'].update(content)
                kb_context['sources'].append('social_media')
                kb_context['similarity_scores']['social_media'] = item['similarity']
        
        if client_context.get('business_info'):
            for item in client_context['business_info']:
                content = item['content']
                kb_context['business_info'].update(content)
                kb_context['sources'].append('business_info')
                kb_context['similarity_scores']['business_info'] = item['similarity']
        
        # Process agent knowledge
        if agent_knowledge.get('knowledge_items'):
            kb_context['agent_insights'] = {
                'relevant_knowledge': [item['content'] for item in agent_knowledge['knowledge_items'][:3]],
                'total_relevance': agent_knowledge.get('total_relevance', 0.0),
                'knowledge_count': len(agent_knowledge['knowledge_items'])
            }
            kb_context['sources'].append('agent_knowledge')
        
        # Get enhanced chat history with better indexing
        try:
            chat_result = supabase.table('chat_history')\
                .select('sender, message, timestamp')\
                .eq('user_id', user_id)\
                .order('timestamp', desc=True)\
                .limit(10)\
                .execute()
            
            if chat_result.data:
                recent_messages = [msg for msg in chat_result.data if msg['sender'] == 'User'][:5]
                kb_context['chat_history'] = {
                    'recent_user_messages': [msg['message'] for msg in recent_messages],
                    'message_count': len(chat_result.data),
                    'last_interaction': chat_result.data[0]['timestamp'] if chat_result.data else None
                }
                kb_context['sources'].append('chat_history')
        except Exception as e:
            logger.warning(f"Error getting chat history: {e}")
        
        # Get website data with better performance
        try:
            website_result = supabase.table('website_data')\
                .select('url, analysis, created_at')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(3)\
                .execute()
            
            if website_result.data:
                kb_context['analyzed_websites'] = [{
                    'url': site['url'],
                    'analysis': site.get('analysis', ''),
                    'analyzed_at': site['created_at']
                } for site in website_result.data]
                kb_context['sources'].append('website_analysis')
        except Exception as e:
            logger.warning(f"Error getting website data: {e}")
        
        # Calculate overall context quality score
        kb_context['context_quality'] = len(kb_context['sources']) / 6.0  # Max 6 sources
        kb_context['has_sufficient_context'] = len(kb_context['sources']) >= 3
        
        return kb_context
        
    except Exception as e:
        logger.error(f"Error building enhanced KB context: {e}")
        return {}

async def check_missing_must_info(must_questions: List[str], kb_context: Dict, client_context: Dict) -> List[str]:
    """Check for missing must-have information using enhanced context"""
    missing_info = []
    
    try:
        for must_q in must_questions:
            question_lower = must_q.lower()
            
            if 'website' in question_lower:
                has_website = (
                    kb_context.get('website_info', {}).get('url') or
                    kb_context.get('analyzed_websites') or
                    any('http' in msg for msg in kb_context.get('chat_history', {}).get('recent_user_messages', []))
                )
                if not has_website:
                    missing_info.append('website_url')
            
            elif 'niche' in question_lower or 'industry' in question_lower:
                has_niche = (
                    client_context.get('niche') and client_context.get('niche') != 'Unknown' or
                    kb_context.get('business_info', {}).get('industry') or
                    kb_context.get('website_info', {}).get('industry')
                )
                if not has_niche:
                    missing_info.append('client_niche')
            
            elif 'address' in question_lower or 'location' in question_lower:
                has_location = (
                    kb_context.get('business_info', {}).get('address') or
                    kb_context.get('website_info', {}).get('location') or
                    client_context.get('location')
                )
                if not has_location:
                    missing_info.append('property_address')
    
    except Exception as e:
        logger.warning(f"Error checking missing must info: {e}")
    
    return missing_info

async def log_performance_metric(operation_type: str, execution_time_ms: int, operation_details: Dict, success: bool = True, error_message: str = None):
    """Log performance metrics to the optimized performance table"""
    try:
        metric_data = {
            'operation_type': operation_type,
            'operation_details': operation_details,
            'execution_time_ms': execution_time_ms,
            'success': success,
            'error_message': error_message
        }
        
        supabase.table('performance_metrics').insert(metric_data).execute()
        
    except Exception as e:
        logger.warning(f"Error logging performance metric: {e}")

# Agent KB query endpoints with optimized database schema
@app.post("/n8n/agent/query")
async def agent_kb_query(request: AgentKBQueryRequest):
    """Enhanced agent query with optimized client context aggregation using new schema"""
    try:
        start_time = time.time()
        
        # Generate query embedding for similarity searches
        query_embedding = await AgentMatcher(supabase).get_query_embedding(request.user_mssg)
        
        # Get agent context from KB with smart caching and usage tracking
        agent_context = await dynamic_agent_kb_handler.get_agent_context_from_kb(request.agent)
        
        # Get comprehensive client context using optimized database functions
        client_context = await get_optimized_client_context(request.user_id, query_embedding)
        
        # Get agent-specific knowledge with usage tracking
        agent_knowledge = await get_optimized_agent_knowledge(request.agent, query_embedding)
        
        # Build comprehensive KB context from multiple sources
        kb_context = await build_enhanced_kb_context(
            request.user_id, 
            client_context, 
            agent_knowledge
        )
        
        # Check for must-have information requirements
        must_questions = agent_context.get('must_questions', [])
        missing_must_info = await check_missing_must_info(must_questions, kb_context, client_context)
        
        # Handle critical missing information
        if 'website_url' in missing_must_info:
            follow_up_questions = await dynamic_agent_kb_handler.generate_contextual_questions(
                request.user_mssg,
                agent_context,
                ['website_url'],
                client_context
            )
            
            # Log performance metrics
            execution_time = int((time.time() - start_time) * 1000)
            await log_performance_metric("agent_query_missing_info", execution_time, {
                "agent": request.agent,
                "user_id": request.user_id,
                "missing_info": missing_must_info
            })
            
            return AgentKBQueryResponse(
                user_id=request.user_id,
                agent=request.agent,
                response_type="needs_info",
                follow_up_questions=follow_up_questions,
                missing_information=[{
                    "field": "website_url",
                    "reason": "Required by agent's MUST questions to provide accurate analysis",
                    "priority": "critical"
                }],
                confidence_score=0.9,
                kb_context_used=bool(kb_context),
                status="missing_critical_info"
            )
        
        # Analyze query with enhanced context
        analysis = await dynamic_agent_kb_handler.analyze_query_with_context(
            request.user_mssg,
            agent_context,
            client_context,
            kb_context
        )
        
        # Generate response based on analysis
        if analysis.get('can_answer') and analysis.get('confidence', 0) > 0.7:
            available_tools = agent_context.get('tools', [])
            required_tool_names = analysis.get('required_tools', [])
            tools_to_use = [t for t in available_tools if t['name'] in required_tool_names]
            
            agent_response = await dynamic_agent_kb_handler.generate_contextual_response(
                request.user_mssg,
                agent_context,
                client_context,
                kb_context,
                tools_to_use
            )
            
            # Log successful performance
            execution_time = int((time.time() - start_time) * 1000)
            await log_performance_metric("agent_query_success", execution_time, {
                "agent": request.agent,
                "user_id": request.user_id,
                "confidence": analysis.get('confidence', 0.8),
                "tools_used": len(tools_to_use),
                "context_sources": len(kb_context.get('sources', []))
            })
            
            return AgentKBQueryResponse(
                user_id=request.user_id,
                agent=request.agent,
                response_type="needs_tools" if tools_to_use else "direct_answer",
                agent_response=agent_response,
                required_tools=tools_to_use if tools_to_use else None,
                confidence_score=analysis.get('confidence', 0.8),
                kb_context_used=bool(kb_context),
                status="success"
            )
        
        else:
            # Handle insufficient information case
            all_missing = missing_must_info + analysis.get('missing_info', [])
            
            follow_up_questions = await dynamic_agent_kb_handler.generate_contextual_questions(
                request.user_mssg,
                agent_context,
                all_missing,
                client_context
            )
            
            missing_info_formatted = []
            for info in all_missing:
                missing_info_formatted.append({
                    "field": info,
                    "reason": f"Required by {request.agent} agent to provide accurate response",
                    "priority": "high" if info in missing_must_info else "medium"
                })
            
            # Log performance for insufficient info case
            execution_time = int((time.time() - start_time) * 1000)
            await log_performance_metric("agent_query_needs_info", execution_time, {
                "agent": request.agent,
                "user_id": request.user_id,
                "missing_info_count": len(all_missing),
                "confidence": analysis.get('confidence', 0.5)
            })
            
            return AgentKBQueryResponse(
                user_id=request.user_id,
                agent=request.agent,
                response_type="needs_info",
                follow_up_questions=follow_up_questions,
                missing_information=missing_info_formatted,
                confidence_score=analysis.get('confidence', 0.5),
                kb_context_used=bool(kb_context),
                status="needs_more_info"
            )
            
    except Exception as e:
        # Log error performance
        execution_time = int((time.time() - start_time) * 1000)
        await log_performance_metric("agent_query_error", execution_time, {
            "agent": request.agent,
            "user_id": request.user_id,
            "error": str(e)
        }, success=False, error_message=str(e))
        
        logger.error(f"Error in agent_kb_query: {str(e)}")
        return AgentKBQueryResponse(
            user_id=request.user_id,
            agent=request.agent,
            response_type="error",
            agent_response="I encountered an error processing your request. Please try again.",
            confidence_score=0.0,
            kb_context_used=False,
            status="error"
        )

@app.post("/n8n/agent/query/wrapper")
async def n8n_agent_kb_query(request: Dict[str, Any]):
    """N8N-compatible version of agent KB query endpoint"""
    try:
        query_request = AgentKBQueryRequest(
            user_id=request.get('user_id'),
            user_mssg=request.get('user_mssg'),
            agent=request.get('agent')
        )
        
        response = await agent_kb_query(query_request)
        
        n8n_response = response.model_dump()
        
        if response.response_type == "direct_answer":
            n8n_response['workflow_action'] = 'send_response'
            n8n_response['next_node'] = 'format_and_send'
            
        elif response.response_type == "needs_tools":
            n8n_response['workflow_action'] = 'execute_tools'
            n8n_response['next_node'] = 'tool_executor'
            n8n_response['tool_sequence'] = [t['name'] for t in (response.required_tools or [])]
            
        elif response.response_type == "needs_info":
            n8n_response['workflow_action'] = 'collect_information'
            n8n_response['next_node'] = 'info_collector'
            n8n_response['ui_action'] = 'show_form'
            
        n8n_response['execution_metadata'] = {
            'timestamp': datetime.now().isoformat(),
            'agent_type': request.get('agent'),
            'has_context': response.kb_context_used,
            'confidence': response.confidence_score
        }
        
        return n8n_response
        
    except Exception as e:
        logger.error(f"Error in n8n_agent_kb_query: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'workflow_action': 'handle_error',
            'next_node': 'error_handler'
        }

@app.post("/n8n/agent/refresh_kb")
async def refresh_agent_kb(agent_name: str):
    """Refresh agent KB by re-reading from agent_documents"""
    try:
        result = supabase.table('agent_documents')\
            .select('id')\
            .eq('agent_name', agent_name)\
            .limit(1)\
            .execute()
        
        if result.data:
            return {
                'status': 'success',
                'message': f'Agent KB for {agent_name} is available',
                'document_count': len(result.data)
            }
        else:
            return {
                'status': 'not_found',
                'message': f'No KB documents found for agent: {agent_name}'
            }
            
    except Exception as e:
        logger.error(f"Error refreshing agent KB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Main n8n endpoints
@app.post("/n8n_main_req/{agent_name}/{session_id}")
async def n8n_main_request(request: N8nMainRequest, agent_name: str, session_id: str):
    """Handle main request to n8n workflow with conversational logic"""
    try:
        # Generate a unique request ID
        request_id = request.request_id or str(uuid.uuid4())
        
        request.agent_name = agent_name
        request.session_id = session_id
        
        # Skip empty messages
        if not request.user_mssg or request.user_mssg.strip() == "":
            logger.info("Skipping empty message")
            return {
                "status": "success",
                "message": "Empty message ignored",
                "request_id": request_id
            }
        
        # Deduplicate requests
        request_key = f"{session_id}:{request.user_mssg}:{agent_name}"
        current_time = time.time()
        
        # Check if duplicate within 2 seconds
        if request_key in request_cache:
            if current_time - request_cache[request_key] < 2.0:
                logger.info(f"Duplicate request detected: {request.user_mssg[:30]}...")
                return {
                    "status": "success",
                    "message": "Duplicate request ignored",
                    "request_id": request_id,
                    "agent_response": "Processing your previous message..."
                }
        
        request_cache[request_key] = current_time
        
        # Clean old cache entries
        for k in list(request_cache.keys()):
            if current_time - request_cache[k] > 10:
                del request_cache[k]
        
        # Only process the request if it's not an initial message or session change
        if request.user_mssg and request.user_mssg.strip() != "":
            request_data = {
                "user_id": request.user_id,
                "user_mssg": request.user_mssg,
                "session_id": request.session_id,
                "agent_name": request.agent_name,
                "timestamp_of_call_made": datetime.now().isoformat(),
                "request_id": request_id
            }
            
            # Check cache first
            cached_response = await conversational_handler.get_cached_response(request_id)
            if cached_response:
                logger.info(f"Returning cached response for request_id: {request_id}")
                return cached_response
                
            n8n_payload = await conversational_handler.handle_message(request_data)
            logger.info(f"Sending to n8n: {n8n_payload}")
            
            n8n_response = await call_n8n_webhook(n8n_payload)
            
            # Enhanced logging for debugging
            logger.debug(f"N8N Main Request - ID: {request_id}, Session: {session_id}, Agent: {agent_name}, Message: {request.user_mssg}, Response: {json.dumps(n8n_response, indent=2)}")
            
            logger.info(f"Received from n8n: {n8n_response}")
            
            formatted_response = {
                "user_id": n8n_response.get("user_id", request.user_id),
                "agent_name": n8n_response.get("agent_name", request.agent_name),
                "agent_response": n8n_response.get("agent_response", n8n_response.get("agent_responses", "")),
                "responses": n8n_response.get("responses", []),
                "timestamp": n8n_response.get("timestamp", datetime.now().isoformat()),
                "status": n8n_response.get("status", "success"),
                "request_id": request_id,
                "conversation_state": n8n_response.get("conversation_state", "complete"),
                "missing_info": n8n_response.get("missing_info", []),
                "images": extract_image_urls(n8n_response.get("agent_response", ""))
            }
            
            # Cache the response
            await conversational_handler.cache_response(request_id, formatted_response)
            
            await conversational_handler.save_to_history(
                request.session_id,
                request.user_id,
                request_data.get("_original_message", request.user_mssg),
                formatted_response["agent_response"]
            )
            
            return formatted_response
        else:
            # For initial messages or empty messages, just return a success response
            return {
                "status": "success",
                "message": "Initial message received",
                "request_id": request_id
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in n8n_main_request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/n8n_main_req_stream")
async def n8n_main_request_stream(request: N8nMainRequest):
    """Handle streaming request to n8n workflow"""
    try:
        if not request.timestamp_of_call_made:
            request.timestamp_of_call_made = datetime.now().isoformat()
        
        request_data = {
            "user_id": request.user_id,
            "user_mssg": request.user_mssg,
            "session_id": request.session_id,
            "agent_name": request.agent_name,
            "timestamp_of_call_made": request.timestamp_of_call_made
        }
        
        n8n_payload = await conversational_handler.handle_message(request_data)
        
        return StreamingResponse(
            stream_n8n_response(n8n_payload),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Error in n8n_main_request_stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Streaming endpoint
@app.post("/api/stream")
async def receive_stream_update(update: StreamUpdate):
    """Endpoint that receives streaming updates from n8n and forwards to WebSocket clients"""
    try:
        connection_id = f"{update.user_id}_{update.metadata.get('session_id', '')}"
        
        session_key = f"{update.user_id}:{update.metadata.get('request_id', '')}"
        if session_key not in streaming_sessions:
            streaming_sessions[session_key] = {
                "updates": [],
                "complete": False
            }
        
        streaming_sessions[session_key]["updates"].append(update.model_dump())
        
        if update.type in ["complete", "final"]:
            streaming_sessions[session_key]["complete"] = True
        
        if connection_id in active_connections:
            websocket = active_connections[connection_id]
            await websocket.send_json({
                "type": update.type,
                "agent": update.agent_name or update.agent_names,
                "message": update.message,
                "progress": update.progress,
                "requestId": update.metadata.get("request_id"),
                "metadata": update.metadata,
                "timestamp": int(time.time() * 1000)
            })
            
            if update.type == "complete" and update.agent_response:
                await websocket.send_json({
                    "type": "agent_response",
                    "agent": update.agent_name,
                    "message": update.agent_response,
                    "requestId": update.metadata.get("request_id"),
                    "final": True,
                    "timestamp": int(time.time() * 1000)
                })
        
        return {"status": "received", "connection_id": connection_id}
        
    except Exception as e:
        logger.error(f"Error in receive_stream_update: {str(e)}")
        return {"status": "error", "error": str(e)}
    
@app.post("/api/website/analyze")
async def analyze_website_endpoint(request: WebsiteAnalysisRequest):
    """
    Endpoint 1: Analyze website using Perplexity AI - NO TIMEOUTS
    """
    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""
        Please analyze the website {request.url} and provide a summary in exactly this format:
        --- *Company name*: [Extract company name]
        --- *Website*: {request.url}
        --- *Contact Information*: [Any available contact details]
        --- *Description*: [2-3 sentence summary of what the company does]
        --- *Tags*: [Main business categories, separated by periods]
        --- *Takeaways*: [Key business value propositions]
        --- *Niche*: [Specific market focus or specialty]
        """
        
        # NO TIMEOUT - let it take as long as needed
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json={
                    "model": "sonar-reasoning-pro",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis_text = result["choices"][0]["message"]["content"]
                
                # Parse the analysis
                parsed_analysis = {}
                lines = analysis_text.split('\n')
                for line in lines:
                    if '*Company name*:' in line:
                        parsed_analysis['company_name'] = line.split(':', 1)[1].strip()
                    elif '*Description*:' in line:
                        parsed_analysis['description'] = line.split(':', 1)[1].strip()
                    elif '*Niche*:' in line:
                        parsed_analysis['niche'] = line.split(':', 1)[1].strip()
                    elif '*Tags*:' in line:
                        parsed_analysis['tags'] = line.split(':', 1)[1].strip()
                    elif '*Takeaways*:' in line:
                        parsed_analysis['takeaways'] = line.split(':', 1)[1].strip()
                    elif '*Contact Information*:' in line:
                        parsed_analysis['contact_info'] = line.split(':', 1)[1].strip()
                
                # Save to database if user_id provided
                if request.user_id and request.session_id:
                    try:
                        supabase.table('website_data').upsert({
                            'user_id': request.user_id,
                            'session_id': request.session_id,
                            'url': request.url,
                            'analysis': json.dumps(parsed_analysis),
                            'created_at': datetime.now().isoformat()
                        }).execute()
                    except Exception as db_error:
                        logger.error(f"Error saving to database: {db_error}")
                
                return {
                    "status": "success",
                    "url": request.url,
                    "analysis": parsed_analysis,
                    "raw_analysis": analysis_text,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "error",
                    "message": f"Perplexity API error: {response.status_code}",
                    "details": response.text
                }
                
    except Exception as e:
        logger.error(f"Error in analyze_website_endpoint: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/api/website/screenshot")
async def capture_website_screenshot_endpoint(request: WebsiteScreenshotRequest):
    """
    Endpoint 2: Capture full website screenshot
    Returns screenshot URL from Supabase Storage
    """
    try:
        # Use the async version
        result = await capture_website_screenshot_async(
            url=request.url,
            session_id=request.session_id
        )
        
        # If successful and user_id provided, save metadata to database
        if result['status'] == 'success' and request.user_id:
            try:
                supabase.table('website_screenshots').upsert({
                    'user_id': request.user_id,
                    'session_id': request.session_id or str(uuid.uuid4()),
                    'url': request.url,
                    'screenshot_path': result['path'],
                    'public_url': result.get('public_url'),
                    'created_at': datetime.now().isoformat()
                }).execute()
            except Exception as db_error:
                logger.error(f"Error saving screenshot metadata: {db_error}")
        
        return {
            "status": result['status'],
            "message": result['message'],
            "screenshot_url": result.get('public_url'),
            "storage_path": result.get('path'),
            "filename": result.get('filename'),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in capture_website_screenshot_endpoint: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "screenshot_url": None
        }

@app.post("/api/website/favicon")
async def get_website_favicon_endpoint(request: WebsiteFaviconRequest):
    """
    Endpoint 3: Extract and save website favicon/logo
    Returns favicon URL from Supabase Storage
    """
    try:
        # Use the async version
        result = await get_website_favicon_async(
            url=request.url,
            session_id=request.session_id
        )
        
        # If successful and user_id provided, save metadata to database
        if result['status'] == 'success' and request.user_id:
            try:
                supabase.table('website_favicons').upsert({
                    'user_id': request.user_id,
                    'session_id': request.session_id or str(uuid.uuid4()),
                    'url': request.url,
                    'favicon_path': result['path'],
                    'public_url': result.get('public_url'),
                    'created_at': datetime.now().isoformat()
                }).execute()
            except Exception as db_error:
                logger.error(f"Error saving favicon metadata: {db_error}")
        
        return {
            "status": result['status'],
            "message": result.get('message', 'Favicon processed'),
            "favicon_url": result.get('public_url'),
            "storage_path": result.get('path'),
            "filename": result.get('filename'),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in get_website_favicon_endpoint: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "favicon_url": None
        }
    
@app.post("/api/website/full-analysis-async")
async def full_website_analysis_async(request: WebsiteAnalysisRequest):
    """
    Fire-and-forget endpoint that starts all operations and returns immediately
    """
    task_id = str(uuid.uuid4())
    
    # Initialize result structure
    background_results[task_id] = {
        "status": "started",
        "url": request.url,
        "session_id": request.session_id or str(uuid.uuid4()),
        "started_at": datetime.now().isoformat(),
        "analysis": {"status": "pending"},
        "screenshot": {"status": "pending"},
        "favicon": {"status": "pending"}
    }
    
    # Define async function to run all operations
    async def run_all_operations():
        try:
            # Run all three operations in parallel
            analysis_task = asyncio.create_task(analyze_website_endpoint(request))
            screenshot_task = asyncio.create_task(capture_website_screenshot_endpoint(
                WebsiteScreenshotRequest(
                    url=request.url,
                    session_id=request.session_id,
                    user_id=request.user_id
                )
            ))
            favicon_task = asyncio.create_task(get_website_favicon_endpoint(
                WebsiteFaviconRequest(
                    url=request.url,
                    session_id=request.session_id,
                    user_id=request.user_id
                )
            ))
            
            # Wait for each to complete and update results
            try:
                background_results[task_id]["analysis"] = await analysis_task
            except Exception as e:
                background_results[task_id]["analysis"] = {"status": "error", "message": str(e)}
            
            try:
                background_results[task_id]["screenshot"] = await screenshot_task
            except Exception as e:
                background_results[task_id]["screenshot"] = {"status": "error", "message": str(e)}
            
            try:
                background_results[task_id]["favicon"] = await favicon_task
            except Exception as e:
                background_results[task_id]["favicon"] = {"status": "error", "message": str(e)}
            
            # Update overall status
            all_success = all(
                background_results[task_id].get(key, {}).get("status") == "success" 
                for key in ["analysis", "screenshot", "favicon"]
            )
            background_results[task_id]["status"] = "complete"
            background_results[task_id]["overall_status"] = "success" if all_success else "partial_success"
            background_results[task_id]["completed_at"] = datetime.now().isoformat()
            
        except Exception as e:
            background_results[task_id]["status"] = "error"
            background_results[task_id]["error"] = str(e)
    
    # Start the operations without waiting
    asyncio.create_task(run_all_operations())
    
    # Return immediately
    return {
        "task_id": task_id,
        "status": "accepted",
        "message": "Analysis started in background",
        "check_url": f"/api/website/task/{task_id}",
        "url": request.url,
        "started_at": datetime.now().isoformat()
    }


# Add this endpoint to main.py if it doesn't exist
@app.get("/chat-history")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    try:
        result = supabase.table('chat_history')\
            .select('*')\
            .eq('session_id', session_id)\
            .order('timestamp', desc=False)\
            .execute()
        
        if result.data:
            history = []
            for msg in result.data:
                history.append({
                    'sender': 'AI' if msg['sender'] == 'agent' else 'User',
                    'message': msg['message'],
                    'timestamp': msg['timestamp']
                })
            return {'history': history, 'status': 'success'}
        else:
            return {'history': [], 'status': 'success'}
            
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}")
        return {'history': [], 'status': 'error', 'error': str(e)}

# Application logs endpoint

# Keep last 100 log entries in memory
app_logs = deque(maxlen=100)

# Custom log handler to capture logs
class InMemoryLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            'timestamp': record.created,
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName
        }
        app_logs.append(log_entry)

# Add the handler to the logger
memory_handler = InMemoryLogHandler()
memory_handler.setLevel(logging.INFO)
logger.addHandler(memory_handler)

@app.get("/logs")
async def get_application_logs(limit: int = 50):
    """Get recent application logs"""
    try:
        # Get last N logs
        recent_logs = list(app_logs)[-limit:]
        
        # Format logs for response
        formatted_logs = []
        for log in recent_logs:
            formatted_logs.append({
                'timestamp': datetime.fromtimestamp(log['timestamp']).isoformat(),
                'level': log['level'],
                'message': log['message'],
                'module': log['module'],
                'function': log['function']
            })
        
        return {
            'status': 'success',
            'logs': formatted_logs,
            'count': len(formatted_logs),
            'total_available': len(app_logs)
        }
    except Exception as e:
        logger.error(f"Error fetching logs: {str(e)}")
        return {
            'status': 'error',
            'message': str(e),
            'logs': []
        }

# Combined endpoint that runs all three tools
@app.post("/api/website/full-analysis")
async def full_website_analysis(request: WebsiteAnalysisRequest):
    """
    Optimized for Heroku's 30-second limit
    Total execution time: max 25 seconds to leave buffer
    """
    try:
        results = {
            "url": request.url,
            "session_id": request.session_id or str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat()
        }
        
        # Start all tasks
        analysis_task = asyncio.create_task(analyze_website_endpoint(request))
        screenshot_task = asyncio.create_task(capture_website_screenshot_endpoint(
            WebsiteScreenshotRequest(
                url=request.url,
                session_id=request.session_id,
                user_id=request.user_id
            )
        ))
        favicon_task = asyncio.create_task(get_website_favicon_endpoint(
            WebsiteFaviconRequest(
                url=request.url,
                session_id=request.session_id,
                user_id=request.user_id
            )
        ))
        
        # Wait for all tasks with a total timeout of 25 seconds
        # This leaves 5 seconds buffer for response processing
        try:
            # Use gather with timeout for all tasks
            all_results = await asyncio.wait_for(
                asyncio.gather(
                    analysis_task,
                    screenshot_task,
                    favicon_task,
                    return_exceptions=True
                ),
                timeout=25.0  # Total timeout
            )
            
            # Process results
            results["analysis"] = all_results[0] if not isinstance(all_results[0], Exception) else {
                "status": "error",
                "message": str(all_results[0])
            }
            results["screenshot"] = all_results[1] if not isinstance(all_results[1], Exception) else {
                "status": "error", 
                "message": str(all_results[1])
            }
            results["favicon"] = all_results[2] if not isinstance(all_results[2], Exception) else {
                "status": "error",
                "message": str(all_results[2])
            }
            
        except asyncio.TimeoutError:
            # Timeout hit - get whatever is ready
            results["analysis"] = await analysis_task if analysis_task.done() else {
                "status": "timeout",
                "message": "Analysis timed out"
            }
            results["screenshot"] = await screenshot_task if screenshot_task.done() else {
                "status": "timeout",
                "message": "Screenshot timed out"
            }
            results["favicon"] = await favicon_task if favicon_task.done() else {
                "status": "timeout",
                "message": "Favicon timed out"
            }
        
        # Determine overall status
        all_success = all(
            results.get(key, {}).get("status") == "success" 
            for key in ["analysis", "screenshot", "favicon"]
        )
        
        results["overall_status"] = "success" if all_success else "partial_success"
        
        return results
        
    except Exception as e:
        logger.error(f"Error in full_website_analysis: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "url": request.url
        }

# WebSocket endpoint
@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """WebSocket endpoint that routes through n8n with streaming support"""
    connection_id = f"{user_id}_{session_id}"
    logger.info(f"New WebSocket connection: {connection_id}")
    
    await websocket.accept()
    
    active_connections[connection_id] = websocket
    
    async def send_ping():
        """Send periodic ping to keep connection alive"""
        while connection_id in active_connections:
            try:
                await asyncio.sleep(30)  # Ping every 30 seconds
                if connection_id in active_connections:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": int(time.time() * 1000)
                    })
            except Exception:
                break
    
    # Start ping task
    ping_task = asyncio.create_task(send_ping())
    
    try:
        # Send initial connection status
        await websocket.send_json({
            "type": "connection_status",
            "status": "connected",
            "message": "WebSocket connection established",
            "timestamp": int(time.time() * 1000)
        })
        
        while True:
            try:
                # Use timeout to prevent hanging
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message_data = json.loads(data)
                
                request_id = message_data.get("requestId", str(uuid.uuid4()))
                
                user_input = message_data.get("message", "").strip()
                
                # Handle ping/pong and skip processing for empty messages  
                if message_data.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": int(time.time() * 1000)
                    })
                    continue
                elif message_data.get("type") == "pong":
                    continue
                elif not user_input or message_data.get("type") == "connection_status":
                    continue
                    
                # Check if this request is already being processed
                if request_id in active_requests:
                    logger.info(f"Request {request_id} is already being processed, skipping")
                    continue
                    
                active_requests.add(request_id)
                
                try:
                    await websocket.send_json({
                        "type": "ack",
                        "requestId": request_id,
                        "message": "Message received, processing...",
                        "timestamp": int(time.time() * 1000)
                    })
                    
                    # Use the working conversational handler (same as HTTP endpoints)
                    request_data = {
                        "user_id": user_id,
                        "user_mssg": user_input,
                        "session_id": session_id,
                        "agent_name": message_data.get("agent", "presaleskb"),
                        "timestamp_of_call_made": datetime.now().isoformat()
                    }
                    
                    # Process via conversational handler (calls n8n webhook)
                    # Don't await here to keep WebSocket responsive, but ensure task completion
                    task = asyncio.create_task(
                        process_websocket_message_with_n8n(request_data, websocket, request_id)
                    )
                    
                    # Add task completion callback for debugging
                    def task_done_callback(task_result):
                        try:
                            if task_result.exception():
                                logger.error(f"❌ WebSocket task failed for {request_id}: {task_result.exception()}")
                                print(f"❌ WebSocket task failed for {request_id}: {task_result.exception()}")
                            else:
                                logger.info(f"✅ WebSocket task completed successfully for {request_id}")
                                print(f"✅ WebSocket task completed successfully for {request_id}")
                        except Exception as e:
                            logger.error(f"Error in task callback: {e}")
                            print(f"Error in task callback: {e}")
                    
                    task.add_done_callback(task_done_callback)
                    
                finally:
                    active_requests.discard(request_id)
                    
            except asyncio.TimeoutError:
                logger.info(f"WebSocket timeout for {connection_id}, checking if still alive")
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": int(time.time() * 1000)
                    })
                except Exception:
                    logger.info(f"Connection {connection_id} appears dead, closing")
                    break
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received, skipping")
                continue
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {connection_id}")
        
    except Exception as e:
        logger.exception(f"WebSocket error: {str(e)}")
        
    finally:
        # Clean up
        ping_task.cancel()
        if connection_id in active_connections:
            del active_connections[connection_id]
        logger.info(f"WebSocket connection closed: {connection_id}")


@app.get("/api/agents/config")
async def get_agents_config():
    """Get all agent configurations"""
    return {
        "agents": [agent.model_dump() for agent in AGENTS.values()]
    }

@app.get("/api/agents/config/{agent_name}")
async def get_agent_config_endpoint(agent_name: str):
    """Get specific agent configuration"""
    agent = get_agent_config(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    return agent.model_dump()

def extract_image_urls(text: str) -> List[str]:
    """Extract Supabase storage URLs from text"""
    import re
    # Match Supabase storage URLs
    pattern = r'https://[^\s]+\.supabase\.co/storage/v1/[^\s]+\.(png|jpg|jpeg|gif|webp)'
    return re.findall(pattern, text, re.IGNORECASE)


@app.post("/api/website/analyze-background")
async def analyze_website_background(request: WebsiteAnalysisRequest, background_tasks: BackgroundTasks):
    """
    Start website analysis in background and return task ID immediately
    This avoids any timeout issues
    """
    task_id = str(uuid.uuid4())
    
    async def run_analysis():
        try:
            result = await analyze_website_endpoint(request)
            background_results[task_id] = {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now().isoformat()
            }
        except Exception as e:
            background_results[task_id] = {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            }
    
    # Start the background task
    background_tasks.add_task(run_analysis)
    
    background_results[task_id] = {
        "status": "processing",
        "started_at": datetime.now().isoformat(),
        "url": request.url
    }
    
    return {
        "task_id": task_id,
        "status": "processing",
        "message": "Analysis started in background",
        "check_url": f"/api/website/task/{task_id}"
    }

@app.get("/api/website/task/{task_id}")
async def get_background_task_result(task_id: str):
    """Check the status of a background task"""
    if task_id not in background_results:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return background_results[task_id]

@app.post("/api/send-invitation-email")
async def send_invitation_email(request: dict):
    """Send invitation email using backend Supabase client"""
    try:
        email = request.get('email')
        token = request.get('token')
        sender_name = request.get('senderName', 'Someone')
        invite_url = request.get('inviteUrl')
        
        if not email or not token or not invite_url:
            return {
                "success": False,
                "error": "Missing required fields",
                "details": f"Missing: {', '.join([k for k, v in {'email': email, 'token': token, 'invite_url': invite_url}.items() if not v])}"
            }
        
        print(f"Backend: Attempting to send invitation email to {email}")
        print(f"Backend: Invite URL: {invite_url}")
        
        # Try using the backend's Supabase client for admin operations
        try:
            # Check if user already exists
            existing_user = supabase.table('profiles').select('id, email').eq('email', email).execute()
            print(f"Backend: Existing user check: {len(existing_user.data) if existing_user.data else 0} users found")
            
            # For now, return success with manual link since SMTP might not be configured
            return {
                "success": False,
                "error": "Email sending not configured in backend",
                "fallback_url": invite_url,
                "message": f"Invitation created for {email}. Please share the link manually.",
                "invitation_details": {
                    "recipient": email,
                    "sender": sender_name,
                    "link": invite_url,
                    "token": token
                }
            }
            
        except Exception as supabase_error:
            print(f"Backend: Supabase operation failed: {str(supabase_error)}")
            return {
                "success": False,
                "error": "Backend database error",
                "details": str(supabase_error),
                "fallback_url": invite_url
            }
            
    except Exception as e:
        print(f"Backend: Send invitation email error: {str(e)}")
        return {
            "success": False,
            "error": "Backend invitation processing failed",
            "details": str(e)
        }

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)