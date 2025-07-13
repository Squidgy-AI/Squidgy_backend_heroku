# main.py - Complete integration with conversational handler and vector search agent matching

# Standard library imports
import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, Optional, List, Set

# Third-party imports
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from starlette.websockets import WebSocketState
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel
from supabase import create_client, Client

# Local imports
from agent_config import get_agent_config, AGENTS
from Website.web_scrape import capture_website_screenshot, get_website_favicon_async
from embedding_service import get_embedding
from tools_connector import tools
from safe_agent_selector import SafeAgentSelector, safe_agent_selection_endpoint
from solar_api_connector import SolarApiConnector, SolarInsightsRequest as SolarInsightsReq, SolarDataLayersRequest as SolarDataLayersReq, get_solar_analysis_for_agent
from facebook_pages_api_working import FacebookPagesRequest, FacebookPagesResponse, get_facebook_pages

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
            # Fallback: return a simple dummy embedding based on text hash
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()
            # Convert hash to a 384-dimensional embedding (matching sentence-transformers output)
            dummy_embedding = []
            for i in range(0, min(len(text_hash), 32), 2):
                val = int(text_hash[i:i+2], 16) / 255.0  # Normalize to 0-1
                dummy_embedding.extend([val] * 12)  # Repeat to get 384 dimensions
            
            # Pad or trim to exactly 384 dimensions
            while len(dummy_embedding) < 384:
                dummy_embedding.append(0.0)
            return dummy_embedding[:384]

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
        """Save message to chat history - saves user and agent messages separately with duplicate prevention"""
        try:
            # Check for existing user message to prevent duplicates (within last 10 seconds)
            existing_user = self.supabase.table('chat_history')\
                .select('id, timestamp')\
                .eq('session_id', session_id)\
                .eq('user_id', user_id)\
                .eq('message', user_message)\
                .eq('sender', 'User')\
                .gte('timestamp', (datetime.now() - timedelta(seconds=10)).isoformat())\
                .order('timestamp', desc=True)\
                .limit(1)\
                .execute()
            
            # Only save user message if not duplicate
            user_result = None
            if not existing_user.data:
                user_entry = {
                    'session_id': session_id,
                    'user_id': user_id,
                    'sender': 'User',
                    'message': user_message,
                    'timestamp': datetime.now().isoformat()
                }
                
                try:
                    user_result = self.supabase.table('chat_history')\
                        .insert(user_entry)\
                        .execute()
                except Exception as insert_error:
                    # Handle unique constraint violation gracefully
                    if 'duplicate key value violates unique constraint' in str(insert_error):
                        logger.debug(f"Duplicate message caught by database constraint for session {session_id}")
                        user_result = None
                    else:
                        raise insert_error
            else:
                logger.debug(f"Skipping duplicate user message for session {session_id}")
            
            # Save agent response if provided
            agent_result = None
            if agent_response and agent_response.strip():
                # Check for existing agent response to prevent duplicates (within last 10 seconds)
                existing_agent = self.supabase.table('chat_history')\
                    .select('id, timestamp')\
                    .eq('session_id', session_id)\
                    .eq('user_id', user_id)\
                    .eq('message', agent_response)\
                    .eq('sender', 'Agent')\
                    .gte('timestamp', (datetime.now() - timedelta(seconds=10)).isoformat())\
                    .order('timestamp', desc=True)\
                    .limit(1)\
                    .execute()
                
                if not existing_agent.data:
                    agent_entry = {
                        'session_id': session_id,
                        'user_id': user_id,
                        'sender': 'Agent',
                        'message': agent_response,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    try:
                        agent_result = self.supabase.table('chat_history')\
                            .insert(agent_entry)\
                            .execute()
                    except Exception as insert_error:
                        # Handle unique constraint violation gracefully
                        if 'duplicate key value violates unique constraint' in str(insert_error):
                            logger.debug(f"Duplicate agent response caught by database constraint for session {session_id}")
                            agent_result = None
                        else:
                            raise insert_error
                else:
                    logger.debug(f"Skipping duplicate agent response for session {session_id}")
                
                return {
                    'user_entry': user_result.data[0] if user_result.data else None,
                    'agent_entry': agent_result.data[0] if agent_result.data else None
                }
            
            return {
                'user_entry': user_result.data[0] if user_result.data else None,
                'agent_entry': None
            }
            
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
            response = await self.process_message(user_mssg, session_id, user_id, agent_name, request_id)

            # Cache the response
            await self.cache_response(request_id, response)

            return response

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            raise

    async def process_message(self, user_mssg: str, session_id: str, user_id: str, agent_name: str, request_id: Optional[str] = None):
        """Process the actual message and get response from n8n with full conversation context"""
        try:
            # Generate request_id if not provided
            if not request_id:
                request_id = str(uuid.uuid4())
            
            logger.info(f"🧠 Building conversation context for session {session_id}")
            
            # 1. Get conversation history for context
            chat_history = []
            try:
                chat_result = self.supabase.table('chat_history')\
                    .select('sender, message, timestamp')\
                    .eq('session_id', session_id)\
                    .order('timestamp', desc=False)\
                    .limit(20)\
                    .execute()
                
                if chat_result.data:
                    chat_history = [
                        {
                            'sender': msg['sender'],
                            'message': msg['message'],
                            'timestamp': msg['timestamp']
                        }
                        for msg in chat_result.data
                    ]
                logger.info(f"📚 Retrieved {len(chat_history)} previous messages for context")
            except Exception as e:
                logger.warning(f"Could not retrieve chat history: {str(e)}")
            
            # 2. Get website data for context
            website_context = []
            try:
                website_result = self.supabase.table('website_data')\
                    .select('url, analysis, created_at')\
                    .eq('user_id', user_id)\
                    .order('created_at', desc=True)\
                    .limit(5)\
                    .execute()
                
                if website_result.data:
                    website_context = website_result.data
                logger.info(f"🌐 Retrieved {len(website_context)} website analyses for context")
            except Exception as e:
                logger.warning(f"Could not retrieve website data: {str(e)}")
            
            # 3. Get client KB for context
            client_kb_context = {}
            try:
                kb_result = self.supabase.table('client_kb')\
                    .select('kb_type, content')\
                    .eq('client_id', user_id)\
                    .execute()
                
                if kb_result.data:
                    for entry in kb_result.data:
                        client_kb_context[entry['kb_type']] = entry['content']
                logger.info(f"📊 Retrieved {len(client_kb_context)} KB entries for context")
            except Exception as e:
                logger.warning(f"Could not retrieve client KB: {str(e)}")
            
            # 4. Extract contextual information from conversation
            context_insights = self._extract_conversation_insights(chat_history, website_context)
            logger.info(f"🔍 Extracted context insights: {list(context_insights.keys())}")
                
            # Prepare enhanced payload for n8n with full context
            payload = {
                'user_id': user_id,
                'user_mssg': user_mssg,
                'session_id': session_id,
                'agent_name': agent_name,
                'timestamp_of_call_made': datetime.now().isoformat(),
                'request_id': request_id,
                '_original_message': user_mssg,
                # ENHANCED CONTEXT DATA
                'conversation_history': chat_history,
                'website_data': website_context,
                'client_knowledge_base': client_kb_context,
                'context_insights': context_insights,
                'context_summary': {
                    'total_messages': len(chat_history),
                    'websites_analyzed': len(website_context),
                    'kb_entries': len(client_kb_context),
                    'extracted_insights': len(context_insights)
                }
            }
            
            logger.info(f"🚀 Sending enhanced payload to n8n with {len(chat_history)} messages, {len(website_context)} websites, {len(client_kb_context)} KB entries")

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
                logger.info(f"N8N Response: {json.dumps(n8n_response, indent=2)}")
                print(f"🔍 N8N Response: {json.dumps(n8n_response, indent=2)}")
                
                # Parse n8n response - handle both direct object and array with output field
                parsed_data = {}
                print(f"🔍 STEP 1 - n8n_response type: {type(n8n_response)}")
                print(f"🔍 STEP 1 - n8n_response is list: {isinstance(n8n_response, list)}")
                if isinstance(n8n_response, list):
                    print(f"🔍 STEP 1 - list length: {len(n8n_response)}")
                
                if isinstance(n8n_response, list) and len(n8n_response) > 0:
                    # Handle array format: [{"output": "JSON_STRING"}]
                    first_item = n8n_response[0]
                    print(f"🔍 STEP 2 - first_item: {json.dumps(first_item, indent=2)}")
                    print(f"🔍 STEP 2 - 'output' in first_item: {'output' in first_item}")
                    
                    if 'output' in first_item:
                        try:
                            # Parse the JSON string inside output field
                            output_string = first_item['output']
                            print(f"🔍 STEP 3 - output_string: {output_string}")
                            print(f"🔍 STEP 3 - output_string type: {type(output_string)}")
                            
                            parsed_data = json.loads(output_string)
                            print(f"🔍 STEP 4 - parsed_data: {json.dumps(parsed_data, indent=2)}")
                            print(f"🔍 STEP 4 - parsed_data agent_response: '{parsed_data.get('agent_response', 'NOT_FOUND')}'")
                            
                            logger.info(f"Parsed output data: {json.dumps(parsed_data, indent=2)}")
                            print(f"✅ Parsed output data: {json.dumps(parsed_data, indent=2)}")
                        except json.JSONDecodeError as e:
                            print(f"🔍 STEP 3 - JSON parse error: {e}")
                            logger.error(f"Failed to parse output JSON: {e}")
                            parsed_data = first_item
                    else:
                        print(f"🔍 STEP 2 - No 'output' field, using first_item directly")
                        parsed_data = first_item
                elif isinstance(n8n_response, dict):
                    # Handle direct object format - but check if it has output field first
                    print(f"🔍 STEP 2 - Direct dict format")
                    
                    if 'output' in n8n_response:
                        try:
                            # Parse the JSON string inside output field  
                            output_string = n8n_response['output']
                            print(f"🔍 STEP 2.1 - Dict has 'output' field: {output_string}")
                            print(f"🔍 STEP 2.1 - output_string type: {type(output_string)}")
                            
                            parsed_data = json.loads(output_string)
                            print(f"🔍 STEP 2.2 - parsed dict output: {json.dumps(parsed_data, indent=2)}")
                            print(f"🔍 STEP 2.2 - parsed dict agent_response: '{parsed_data.get('agent_response', 'NOT_FOUND')}'")
                        except json.JSONDecodeError as e:
                            print(f"🔍 STEP 2.1 - Dict JSON parse error: {e}")
                            parsed_data = n8n_response
                    else:
                        print(f"🔍 STEP 2.1 - Dict has no 'output' field, using directly")
                        parsed_data = n8n_response
                else:
                    print(f"🔍 STEP 2 - Unexpected format")
                    logger.error(f"Unexpected n8n response format: {type(n8n_response)}")
                    parsed_data = {}

            # Format response using parsed data
            print(f"🔍 STEP 5 - About to format response using parsed_data")
            print(f"🔍 STEP 5 - parsed_data.get('agent_response'): '{parsed_data.get('agent_response', 'NOT_FOUND')}'")
            
            formatted_response = {
                'status': parsed_data.get('status', 'success'),
                'agent_name': parsed_data.get('agent_name', agent_name),
                'agent_response': parsed_data.get('agent_response', ''),
                'conversation_state': parsed_data.get('conversation_state', 'complete'),
                'missing_info': parsed_data.get('missing_info', []),
                'output_action': parsed_data.get('output_action'),  # Add output_action to response
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"🔍 STEP 6 - Final formatted response agent_response: '{formatted_response.get('agent_response', 'NOT_FOUND')}'")
            
            logger.info(f"Final formatted response: {json.dumps(formatted_response, indent=2)}")
            print(f"📤 Final formatted response: {json.dumps(formatted_response, indent=2)}")

            return formatted_response

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def analyze_website_with_perplexity(self, website_url: str):
        """Analyze website using Perplexity API and return structured data"""
        try:
            if not PERPLEXITY_API_KEY:
                logger.error("PERPLEXITY_API_KEY not found in environment variables")
                return {}
                
            headers = {
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""
            Please analyze the website {website_url} and provide a summary in exactly this format:
            --- *Company name*: [Extract company name]
            --- *Website*: {website_url}
            --- *Contact Information*: [Any available contact details]
            --- *Description*: [2-3 sentence summary of what the company does]
            --- *Tags*: [Main business categories, separated by periods]
            --- *Takeaways*: [Key business value propositions]
            --- *Niche*: [Specific market focus or specialty]
            """
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json={
                        "model": "sonar-reasoning-pro",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1000,
                        "temperature": 0.2
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    logger.info(f"Perplexity analysis for {website_url}: {content[:200]}...")
                    
                    # Parse the structured response
                    parsed_analysis = {
                        'raw_content': content,
                        'url': website_url,
                        'analyzed_at': datetime.now().isoformat()
                    }
                    
                    # Extract structured data from response
                    for line in content.split('\n'):
                        if '---' in line and ':' in line:
                            key = line.split(':', 1)[0].replace('---', '').replace('*', '').strip().lower().replace(' ', '_')
                            value = line.split(':', 1)[1].strip()
                            parsed_analysis[key] = value
                    
                    return parsed_analysis
                else:
                    logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                    return {
                        'error': f"API request failed with status {response.status_code}",
                        'url': website_url,
                        'analyzed_at': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"Error analyzing website {website_url} with Perplexity: {str(e)}")
            return {
                'error': str(e),
                'url': website_url,
                'analyzed_at': datetime.now().isoformat()
            }

    def _extract_conversation_insights(self, chat_history: List[Dict], website_context: List[Dict]) -> Dict[str, Any]:
        """Extract key insights from conversation history and website context"""
        insights = {
            'mentioned_urls': [],
            'user_requests': [],
            'agent_commitments': [],
            'pending_actions': [],
            'user_confirmations': []
        }
        
        try:
            # Extract URLs mentioned in conversation
            url_patterns = [
                r'https?://[^\s]+',
                r'www\.[^\s]+\.[a-zA-Z]{2,}',
                r'[^\s]+\.[a-zA-Z]{2,}(?:/[^\s]*)?'
            ]
            
            for msg in chat_history:
                message_lower = msg['message'].lower()
                
                # Extract URLs
                import re
                for pattern in url_patterns:
                    urls = re.findall(pattern, msg['message'])
                    for url in urls:
                        if url not in insights['mentioned_urls']:
                            insights['mentioned_urls'].append(url)
                
                # Extract user requests and confirmations
                if msg['sender'] == 'User':
                    if any(word in message_lower for word in ['analyze', 'check', 'look at', 'review', 'examine']):
                        insights['user_requests'].append(msg['message'])
                    if any(phrase in message_lower for phrase in ['go ahead', 'please proceed', 'yes', 'continue', 'do it', 'sure']):
                        insights['user_confirmations'].append(msg['message'])
                
                # Extract agent commitments
                elif msg['sender'] == 'Agent':
                    if any(phrase in message_lower for phrase in ['i will', "i'll", 'let me', 'i can', 'i am going to']):
                        insights['agent_commitments'].append(msg['message'])
            
            # Check for pending actions (agent promised but user confirmed)
            if insights['agent_commitments'] and insights['user_confirmations']:
                insights['pending_actions'] = ['User has confirmed to proceed with agent analysis']
            
            # Add website analysis context
            if website_context:
                insights['analyzed_websites'] = [w['url'] for w in website_context]
            
            return insights
            
        except Exception as e:
            logger.warning(f"Error extracting conversation insights: {str(e)}")
            return insights

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
    
    async def get_client_kb(self, user_id: str, kb_type: str = "website_info") -> Optional[Dict[str, Any]]:
        """Retrieve client KB entry"""
        try:
            result = self.supabase.table('client_kb')\
                .select('*')\
                .eq('client_id', user_id)\
                .eq('kb_type', kb_type)\
                .single()\
                .execute()
            
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting client KB: {str(e)}")
            return None
    
    async def analyze_and_update_kb(self, user_id: str, website_data: Dict[str, Any], chat_history: List[Dict[str, Any]]):
        """Analyze website data and chat history to update KB"""
        try:
            # Extract website information
            analysis_data = {}
            if website_data.get('analysis'):
                try:
                    analysis_data = json.loads(website_data.get('analysis', '{}'))
                except json.JSONDecodeError:
                    analysis_data = {}
            
            website_info = {
                'url': website_data.get('url'),
                'company_name': analysis_data.get('company_name'),
                'description': analysis_data.get('description'),
                'niche': analysis_data.get('niche'),
                'tags': analysis_data.get('tags'),
                'services': analysis_data.get('services', []),
                'contact_info': analysis_data.get('contact_info', {}),
                'last_analyzed': website_data.get('created_at')
            }
            
            # Extract insights from chat history
            chat_insights = await self.extract_chat_insights(chat_history)
            
            kb_content = {
                'website_info': website_info,
                'chat_insights': chat_insights,
                'extracted_requirements': [],
                'preferences': {},
                'last_updated': datetime.now().isoformat()
            }
            
            # Save to database
            entry = {
                'client_id': user_id,
                'kb_type': 'website_info',
                'content': kb_content,
                'is_active': True,
                'last_updated': datetime.now().isoformat()
            }
            
            result = self.supabase.table('client_kb')\
                .upsert(entry, on_conflict='client_id,kb_type')\
                .execute()
            
            logger.info(f"Updated KB for user {user_id} with website {website_info['url']}")
            return kb_content
            
        except Exception as e:
            logger.error(f"Error analyzing and updating KB: {str(e)}")
            return None
    
    async def extract_chat_insights(self, chat_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract insights from chat history"""
        insights = {
            'topics_discussed': [],
            'user_preferences': {},
            'common_questions': [],
            'interaction_summary': []
        }
        
        try:
            for chat in chat_history[-10:]:  # Look at last 10 messages
                message = chat.get('message', '')
                role = chat.get('role', 'user')
                
                if role == 'user':
                    # Extract topics and keywords
                    topics = self._extract_topics(message)
                    insights['topics_discussed'].extend(topics)
                    
                    # Look for questions
                    if any(q in message.lower() for q in ['what', 'how', 'where', 'when', 'why', '?']):
                        insights['common_questions'].append(message)
                
                insights['interaction_summary'].append({
                    'role': role,
                    'message': message[:100],  # Truncate for storage
                    'timestamp': chat.get('timestamp')
                })
            
            # Remove duplicates and limit size
            insights['topics_discussed'] = list(set(insights['topics_discussed']))[:20]
            insights['common_questions'] = insights['common_questions'][-5:]
            
        except Exception as e:
            logger.error(f"Error extracting chat insights: {str(e)}")
        
        return insights
    
    def _extract_topics(self, message: str) -> List[str]:
        """Extract topics from a message"""
        topics = []
        message_lower = message.lower()
        
        # Common business topics
        business_topics = {
            'pricing': ['price', 'cost', 'fee', 'rate', 'pricing', 'budget'],
            'services': ['service', 'offering', 'product', 'solution'],
            'support': ['help', 'support', 'assist', 'guidance'],
            'integration': ['integrate', 'connect', 'api', 'webhook'],
            'features': ['feature', 'functionality', 'capability'],
            'timeline': ['when', 'timeline', 'schedule', 'deadline'],
            'team': ['team', 'staff', 'employee', 'person'],
            'technology': ['tech', 'technology', 'platform', 'system']
        }
        
        for topic, keywords in business_topics.items():
            if any(keyword in message_lower for keyword in keywords):
                topics.append(topic)
        
        return topics

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
import threading

# Thread-safe global variables with locks
active_connections: Dict[str, WebSocket] = {}
streaming_sessions: Dict[str, Dict[str, Any]] = {}
request_cache: Dict[str, float] = {}
_connections_lock = threading.Lock()
_requests_lock = threading.Lock()

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

# Pre-warm embedding model at startup to avoid cold start delays
@app.on_event("startup")
async def startup_event():
    """Pre-warm models and initialize caches for optimal performance"""
    try:
        print("🚀 Starting high-performance optimizations...")
        
        # Pre-warm embedding model
        start_time = time.time()
        dummy_embedding = await AgentMatcher(supabase).get_query_embedding("warmup query")
        warmup_time = int((time.time() - start_time) * 1000)
        print(f"🧠 Embedding model pre-warmed in {warmup_time}ms")
        
        # Initialize any other caches or connections here
        print("✅ High-performance optimizations ready!")
        
    except Exception as e:
        print(f"⚠️ Startup optimization warning: {e}")
        # Don't fail startup if optimization fails

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
    session_id: Optional[str] = None
    user_id: Optional[str] = None

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
    agent_name: Optional[str] = None

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
    agent_name: Optional[str] = None

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

# Solar API Models
class SolarInsightsRequest(BaseModel):
    address: str
    monthly_electric_bill: Optional[float] = None
    monthly_electric_usage_kwh: Optional[float] = None
    mode: Optional[str] = "summary"  # "full", "summary", "solarResults"
    demo: Optional[bool] = False

class SolarDataLayersRequest(BaseModel):
    address: str
    render_panels: Optional[bool] = True
    file_format: Optional[str] = "jpeg"
    demo: Optional[bool] = False

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
                "/n8n/analyze_agent_query",
                "/n8n/safe_agent_select"
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

@app.post("/n8n/safe_agent_select")
async def n8n_safe_agent_select(request: Dict[str, Any]):
    """Safe agent selection with loop prevention and comprehensive fallbacks"""
    try:
        return await safe_agent_selection_endpoint(request, supabase, agent_matcher)
    except Exception as e:
        logger.error(f"❌ Safe agent selection endpoint error: {str(e)}")
        return {
            "selected_agent": "presaleskb",
            "strategy_used": "error_fallback",
            "confidence_score": 0.1,
            "error": str(e),
            "success": False
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
                last_updated=kb_data.get('updated_at'),
                agent_name=request.agent_name
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
                    last_updated=datetime.now().isoformat(),
                    agent_name=request.agent_name
                )
        
        return ClientKBResponse(
            user_id=request.user_id,
            has_website_info=False,
            kb_status='missing_website',
            message='Please provide your website URL to continue',
            action_required='collect_website_url',
            agent_name=request.agent_name
        )
        
    except Exception as e:
        logger.error(f"Error checking client KB: {str(e)}")
        return ClientKBResponse(
            user_id=request.user_id,
            has_website_info=False,
            kb_status='error',
            message=f'Error checking client information: {str(e)}',
            action_required='retry',
            agent_name=request.agent_name
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
    """N8N-specific endpoint for checking client KB and current message for website URLs"""
    try:
        kb_request = ClientKBCheckRequest(
            user_id=request.get('user_id'),
            session_id=request.get('session_id'),
            force_refresh=request.get('force_refresh', False),
            agent_name=request.get('agent_name')
        )
        
        # Check stored KB first
        response = await check_client_kb(kb_request)
        n8n_response = response.model_dump()
        
        # Store original response for reference
        n8n_response['_original_has_website_info'] = response.has_website_info
        
        # If no stored website info, check current user message for URLs
        if not response.has_website_info:
            user_message = request.get('user_message') or request.get('user_mssg', '')
            
            if user_message:
                detected_urls = extract_website_urls(user_message)
                
                if detected_urls:
                    logger.info(f"Detected website URLs in user message: {detected_urls}")
                    
                    # Create a contextual response based on the user's request and detected URL
                    url = detected_urls[0]
                    agent_name = request.get('agent_name', 'presaleskb')
                    user_id = request.get('user_id')
                    session_id = request.get('session_id', str(uuid.uuid4()))
                    
                    # SAVE THE URL TO DATABASE - This was missing!
                    try:
                        # Analyze the website and save to database
                        analysis = await conversational_handler.analyze_website_with_perplexity(url)
                        
                        website_entry = {
                            'user_id': user_id,
                            'session_id': session_id,
                            'url': url,
                            'analysis': json.dumps(analysis) if analysis else None,
                            'created_at': datetime.now().isoformat()
                        }
                        
                        website_result = supabase.table('website_data')\
                            .upsert(website_entry, on_conflict='session_id,url')\
                            .execute()
                        
                        # Update the client KB with the new website data
                        if website_result.data:
                            chat_history_result = supabase.table('chat_history')\
                                .select('*')\
                                .eq('user_id', user_id)\
                                .order('timestamp', desc=False)\
                                .execute()
                            
                            chat_history = chat_history_result.data if chat_history_result else []
                            
                            # Update client KB with website and chat history
                            await client_kb_manager.analyze_and_update_kb(
                                user_id,
                                website_result.data[0],
                                chat_history
                            )
                            
                            logger.info(f"Successfully saved website {url} to database for user {user_id}")
                        
                    except Exception as e:
                        logger.error(f"Error saving website URL to database: {str(e)}")
                        # Continue anyway - we'll still provide contextual response
                    
                    # Generate an appropriate response based on the user's message and agent
                    contextual_response = await generate_contextual_response_for_detected_url(
                        user_message, url, agent_name
                    )
                    
                    # Override response to indicate we found a URL and provide initial context
                    n8n_response.update({
                        'has_website_info': True,
                        'website_url': url,
                        'website_analysis': analysis if 'analysis' in locals() else None,
                        'detected_urls': detected_urls,
                        'next_action': 'proceed_with_agent',
                        'routing': 'continue',
                        'url_source': 'current_message',
                        'contextual_response': contextual_response,
                        'message': contextual_response,
                        'kb_updated': True
                    })
                    
                    return n8n_response
        
        # Original logic for existing KB data or no URLs found
        if response.has_website_info:
            n8n_response['next_action'] = 'proceed_with_agent'
            n8n_response['routing'] = 'continue'
            n8n_response['url_source'] = 'stored_kb'
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
            # Check if we need to switch agents based on output_action
            output_action = n8n_response.get("output_action")
            current_agent = request_data.get("agent_name", "AI")
            target_agent = n8n_response.get("agent_name", current_agent)
            
            print(f"🔍 Agent switching check - Current: {current_agent}, Target: {target_agent}, Action: {output_action}")
            
            # Handle agent switching for need_website_info
            if output_action == "need_website_info" and target_agent != current_agent:
                # Send agent switch message
                transition_message = f"Hey, I will be able to better answer your question. {n8n_response.get('agent_response', '')}"
                
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "agent_switch",
                        "from_agent": current_agent,
                        "to_agent": target_agent,
                        "message": transition_message,
                        "requestId": request_id,
                        "session_id": request_data.get("session_id"),
                        "maintain_history": True,
                        "timestamp": int(time.time() * 1000)
                    })
                else:
                    logger.warning(f"WebSocket connection closed, cannot send agent switch for {request_id}")
                print(f"✅ Sent agent_switch message from {current_agent} to {target_agent}")
                
            elif n8n_response.get("agent_response"):
                # Normal agent response (same agent or different action)
                final_message = n8n_response.get("agent_response")
                
                # If it's need_website_info but same agent, add transition phrase
                if output_action == "need_website_info" and target_agent == current_agent:
                    final_message = f"Let me help you with that. {final_message}"
                
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "agent_response",
                        "agent": target_agent,
                        "message": final_message,
                        "requestId": request_id,
                        "final": True,
                        "output_action": output_action,
                        "timestamp": int(time.time() * 1000)
                    })
                else:
                    logger.warning(f"WebSocket connection closed, cannot send agent response for {request_id}")
                print(f"✅ Sent agent_response via WebSocket: {final_message[:100]}...")
            else:
                print(f"⚠️ No agent_response found in n8n_response to send via WebSocket")
                print(f"⚠️ n8n_response keys: {list(n8n_response.keys())}")
                print(f"⚠️ n8n_response content: {json.dumps(n8n_response, indent=2)}")
            
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
        
        # Send error response with connection state check
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "error",
                    "requestId": request_id,
                    "error": str(e),
                    "timestamp": int(time.time() * 1000)
                })
            else:
                logger.warning(f"WebSocket connection closed, cannot send error response for {request_id}")
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
    """High-performance agent query with parallel processing and multi-level caching"""
    try:
        start_time = time.time()
        print(f"🚀 Starting optimized agent query for {request.agent}")
        
        # Check for URLs in the user message first
        detected_urls = extract_website_urls(request.user_mssg)
        contextual_prefix = ""
        
        if detected_urls:
            logger.info(f"Detected URLs in agent query: {detected_urls}")
            # Generate contextual response for detected URL
            contextual_response = await generate_contextual_response_for_detected_url(
                request.user_mssg, detected_urls[0], request.agent
            )
            
            # For now, return the contextual response immediately
            # This ensures users get immediate feedback instead of null responses
            enhanced_response = f"{contextual_response}\n\nI'm ready to analyze {detected_urls[0]} and provide specific insights about your business needs, pricing options, and recommendations based on what I find."
            
            logger.info(f"Returning immediate contextual response for URL: {detected_urls[0]}")
            return AgentKBQueryResponse(
                user_id=request.user_id,
                agent=request.agent,
                response_type="direct_answer",
                agent_response=enhanced_response,
                required_tools=None,
                confidence_score=0.85,
                kb_context_used=True,
                status="success"
            )
            
            # Keep the original contextual_prefix for additional processing if needed
            contextual_prefix = contextual_response + "\n\nNow let me analyze your website in detail:\n\n"
        
        # Check cache first for entire response
        cache_key = f"agent_query_{request.agent}_{hash(request.user_mssg)}_{request.user_id}"
        cached_response = await conversational_handler.get_cached_response(cache_key)
        if cached_response and not detected_urls:  # Don't use cache for URL queries
            print(f"⚡ Cache hit! Returning cached response in {int((time.time() - start_time) * 1000)}ms")
            return cached_response
        
        embedding_start = time.time()
        # Generate query embedding for similarity searches
        query_embedding = await AgentMatcher(supabase).get_query_embedding(request.user_mssg)
        embedding_time = int((time.time() - embedding_start) * 1000)
        print(f"🧠 Embedding generated in {embedding_time}ms")
        
        parallel_start = time.time()
        # PARALLEL PROCESSING - Execute all database operations simultaneously
        agent_context_task = dynamic_agent_kb_handler.get_agent_context_from_kb(request.agent)
        client_context_task = get_optimized_client_context(request.user_id, query_embedding)
        agent_knowledge_task = get_optimized_agent_knowledge(request.agent, query_embedding)
        
        # Wait for all operations to complete in parallel
        agent_context, client_context, agent_knowledge = await asyncio.gather(
            agent_context_task,
            client_context_task, 
            agent_knowledge_task,
            return_exceptions=True
        )
        parallel_time = int((time.time() - parallel_start) * 1000)
        print(f"🔄 Parallel operations completed in {parallel_time}ms")
        
        # Handle any exceptions from parallel operations
        if isinstance(agent_context, Exception):
            print(f"⚠️ Agent context error: {agent_context}")
            agent_context = {}
        if isinstance(client_context, Exception):
            print(f"⚠️ Client context error: {client_context}")
            client_context = {}
        if isinstance(agent_knowledge, Exception):
            print(f"⚠️ Agent knowledge error: {agent_knowledge}")
            agent_knowledge = {}
        
        context_start = time.time()
        # Build comprehensive KB context from multiple sources
        kb_context = await build_enhanced_kb_context(
            request.user_id, 
            client_context, 
            agent_knowledge
        )
        context_time = int((time.time() - context_start) * 1000)
        print(f"📚 KB context built in {context_time}ms")
        
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
            
            # Prepend contextual prefix if URLs were detected
            if contextual_prefix:
                agent_response = f"{contextual_prefix}{agent_response}"
            
            # Create response object
            response = AgentKBQueryResponse(
                user_id=request.user_id,
                agent=request.agent,
                response_type="needs_tools" if tools_to_use else "direct_answer",
                agent_response=agent_response,
                required_tools=tools_to_use if tools_to_use else None,
                confidence_score=analysis.get('confidence', 0.8),
                kb_context_used=bool(kb_context),
                status="success"
            )
            
            # Cache successful response for 2 minutes
            await conversational_handler.cache_response(cache_key, response, ttl=120)
            
            # Log successful performance with detailed timing
            execution_time = int((time.time() - start_time) * 1000)
            print(f"✅ Optimized agent query completed in {execution_time}ms (Target: <8000ms)")
            print(f"📊 Breakdown: Embedding({embedding_time}ms) + Parallel({parallel_time}ms) + Context({context_time}ms)")
            
            await log_performance_metric("agent_query_success", execution_time, {
                "agent": request.agent,
                "user_id": request.user_id,
                "confidence": analysis.get('confidence', 0.8),
                "tools_used": len(tools_to_use),
                "context_sources": len(kb_context.get('sources', [])),
                "embedding_time_ms": embedding_time,
                "parallel_time_ms": parallel_time,
                "context_time_ms": context_time
            })
            
            return response
        
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
        # Log error performance with timing breakdown
        execution_time = int((time.time() - start_time) * 1000)
        print(f"❌ Agent query failed in {execution_time}ms: {str(e)}")
        
        await log_performance_metric("agent_query_error", execution_time, {
            "agent": request.agent,
            "user_id": request.user_id,
            "error": str(e)
        }, success=False, error_message=str(e))
        
        logger.error(f"Error in optimized agent_kb_query: {str(e)}")
        # If we detected URLs, at least return the contextual response
        error_response = "I encountered an error processing your request. Please try again."
        if contextual_prefix:
            error_response = f"{contextual_prefix}However, I encountered an error with the detailed analysis. Please try again."
        
        return AgentKBQueryResponse(
            user_id=request.user_id,
            agent=request.agent,
            response_type="direct_answer" if contextual_prefix else "error",
            agent_response=error_response,
            confidence_score=0.7 if contextual_prefix else 0.0,
            kb_context_used=bool(contextual_prefix),
            status="success" if contextual_prefix else "error"
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
        result = await capture_website_screenshot(
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
    
    except ConnectionResetError as conn_err:
        logger.warning(f"Connection reset for {connection_id}: {str(conn_err)}")
        
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {str(e)}")
        
    finally:
        # Cancel ping task
        ping_task.cancel()
        # Remove connection from active connections
        if connection_id in active_connections:
            del active_connections[connection_id]
        logger.info(f"WebSocket connection closed and cleaned up: {connection_id}")


@app.get("/api/agents/config")
async def get_all_agent_configs():
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

def extract_website_urls(text: str) -> List[str]:
    """Extract website URLs from text"""
    import re
    # Match various URL patterns
    patterns = [
        r'https?://[^\s]+',  # http:// or https://
        r'www\.[^\s]+\.[a-zA-Z]{2,}',  # www.example.com
        r'[^\s]+\.[a-zA-Z]{2,}(?:/[^\s]*)?'  # example.com or example.com/path
    ]
    
    urls = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        urls.extend(matches)
    
    # Filter out obvious non-URLs and clean up
    cleaned_urls = []
    for url in urls:
        # Remove trailing punctuation
        url = re.sub(r'[.,;!?]+$', '', url)
        
        # Skip if it's clearly not a website (email, file extensions, etc.)
        if any(url.lower().endswith(ext) for ext in ['.jpg', '.png', '.pdf', '.doc', '.zip']):
            continue
        if '@' in url and '.' in url:  # Likely an email
            continue
        if len(url.split('.')) < 2:  # Must have at least one dot
            continue
            
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            if url.startswith('www.'):
                url = 'https://' + url
            else:
                # Check if it looks like a domain
                if '.' in url and len(url.split('.')[-1]) >= 2:
                    url = 'https://' + url
        
        cleaned_urls.append(url)
    
    return list(set(cleaned_urls))  # Remove duplicates

# Cache for agent KB info to avoid repeated database queries
_agent_kb_cache = {}
_cache_ttl = 300  # 5 minutes

async def load_agent_kb_info(agent_name: str) -> dict:
    """Dynamically load agent information from agent_documents table with caching"""
    import re
    import time
    
    # Check cache first
    cache_key = f"agent_kb_{agent_name}"
    current_time = time.time()
    
    if cache_key in _agent_kb_cache:
        cached_data, timestamp = _agent_kb_cache[cache_key]
        if current_time - timestamp < _cache_ttl:
            logger.debug(f"Using cached KB info for {agent_name}")
            return cached_data
    
    default_info = {
        'name': 'Assistant',
        'role': 'Assistant',
        'responsibilities': ['General assistance'],
        'expertise_areas': ['General support'],
        'common_queries': ['General questions']
    }
    
    try:
        # Query agent_documents table for this agent's KB content
        result = supabase.table('agent_documents')\
            .select('content, metadata')\
            .eq('agent_name', agent_name)\
            .execute()
        
        if not result.data:
            logger.warning(f"No KB data found in agent_documents table for {agent_name}")
            return default_info
        
        # Combine all content chunks for this agent
        combined_content = ""
        for doc in result.data:
            if doc.get('content'):
                combined_content += doc['content'] + "\n"
        
        if not combined_content.strip():
            logger.warning(f"Empty KB content for {agent_name}")
            return default_info
        
        # Extract information using regex patterns
        info = {}
        
        # Extract role/name from "You are a [role] named [name]"
        role_match = re.search(r'You are a(?: friendly)?\s+([^,\n]+?)(?:\s+named\s+(\w+))?(?:\s+who|\s+\.)', combined_content, re.IGNORECASE)
        if role_match:
            info['role'] = role_match.group(1).strip()
            info['name'] = role_match.group(2) if role_match.group(2) else info['role']
        else:
            info['role'] = default_info['role']
            info['name'] = default_info['name']
        
        # Extract key responsibilities
        responsibilities_match = re.search(r'Key Responsibilities:(.*?)(?=\n\n|\nExpertise|\nCommon|$)', combined_content, re.DOTALL | re.IGNORECASE)
        if responsibilities_match:
            resp_text = responsibilities_match.group(1)
            # Extract numbered/bulleted items
            responsibilities = re.findall(r'\d+\.\s*([^\n]+)', resp_text)
            info['responsibilities'] = responsibilities if responsibilities else default_info['responsibilities']
        else:
            info['responsibilities'] = default_info['responsibilities']
        
        # Extract expertise areas
        expertise_match = re.search(r'Expertise Areas:(.*?)(?=\n\n|\nCommon|\nTools|$)', combined_content, re.DOTALL | re.IGNORECASE)
        if expertise_match:
            exp_text = expertise_match.group(1)
            # Extract bulleted items
            expertise = re.findall(r'-\s*([^\n]+)', exp_text)
            info['expertise_areas'] = expertise if expertise else default_info['expertise_areas']
        else:
            info['expertise_areas'] = default_info['expertise_areas']
        
        # Extract common queries examples
        queries_match = re.search(r'Common Queries I Handle:(.*?)(?=\n\n|\nBasic|\nTools|\nMUST|$)', combined_content, re.DOTALL | re.IGNORECASE)
        if queries_match:
            queries_text = queries_match.group(1)
            queries = re.findall(r'-\s*"([^"]+)"', queries_text)
            info['common_queries'] = queries if queries else default_info['common_queries']
        else:
            info['common_queries'] = default_info['common_queries']
        
        logger.info(f"Successfully loaded KB info for {agent_name} from database: {info['name']} - {info['role']}")
        logger.info(f"Agent {agent_name} expertise: {info['expertise_areas'][:3]}")
        
        # Cache the result
        _agent_kb_cache[cache_key] = (info, current_time)
        
        return info
        
    except Exception as e:
        logger.error(f"Error loading KB info for {agent_name} from database: {str(e)}")
        
        # Fallback to file-based loading if database fails
        try:
            import os
            kb_file_path = f"/Users/somasekharaddakula/CascadeProjects/SquidgyBackend/n8n_worflows/Agents_KB/{agent_name}.txt"
            
            if os.path.exists(kb_file_path):
                logger.info(f"Falling back to file-based KB loading for {agent_name}")
                with open(kb_file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                # Same extraction logic as above but for file content
                info = {}
                
                role_match = re.search(r'You are a(?: friendly)?\s+([^,\n]+?)(?:\s+named\s+(\w+))?(?:\s+who|\s+\.)', content, re.IGNORECASE)
                if role_match:
                    info['role'] = role_match.group(1).strip()
                    info['name'] = role_match.group(2) if role_match.group(2) else info['role']
                else:
                    info['role'] = default_info['role']
                    info['name'] = default_info['name']
                
                responsibilities_match = re.search(r'Key Responsibilities:(.*?)(?=\n\n|\nExpertise|\nCommon|$)', content, re.DOTALL | re.IGNORECASE)
                if responsibilities_match:
                    resp_text = responsibilities_match.group(1)
                    responsibilities = re.findall(r'\d+\.\s*([^\n]+)', resp_text)
                    info['responsibilities'] = responsibilities if responsibilities else default_info['responsibilities']
                else:
                    info['responsibilities'] = default_info['responsibilities']
                
                expertise_match = re.search(r'Expertise Areas:(.*?)(?=\n\n|\nCommon|\nTools|$)', content, re.DOTALL | re.IGNORECASE)
                if expertise_match:
                    exp_text = expertise_match.group(1)
                    expertise = re.findall(r'-\s*([^\n]+)', exp_text)
                    info['expertise_areas'] = expertise if expertise else default_info['expertise_areas']
                else:
                    info['expertise_areas'] = default_info['expertise_areas']
                
                queries_match = re.search(r'Common Queries I Handle:(.*?)(?=\n\n|\nBasic|\nTools|\nMUST|$)', content, re.DOTALL | re.IGNORECASE)
                if queries_match:
                    queries_text = queries_match.group(1)
                    queries = re.findall(r'-\s*"([^"]+)"', queries_text)
                    info['common_queries'] = queries if queries else default_info['common_queries']
                else:
                    info['common_queries'] = default_info['common_queries']
                
                logger.info(f"Successfully loaded KB info for {agent_name} from file fallback")
                
                # Cache the fallback result too
                _agent_kb_cache[cache_key] = (info, current_time)
                
                return info
                
        except Exception as fallback_error:
            logger.error(f"File fallback also failed for {agent_name}: {str(fallback_error)}")
        
        return default_info

async def populate_agent_documents_table():
    """Utility function to populate agent_documents table from KB files"""
    import os
    import json
    from embedding_service import get_embedding
    
    agents_kb_dir = "/Users/somasekharaddakula/CascadeProjects/SquidgyBackend/n8n_worflows/Agents_KB"
    
    if not os.path.exists(agents_kb_dir):
        logger.error(f"Agents KB directory not found: {agents_kb_dir}")
        return False
    
    try:
        for filename in os.listdir(agents_kb_dir):
            if filename.endswith('.txt'):
                agent_name = filename.replace('.txt', '')
                file_path = os.path.join(agents_kb_dir, filename)
                
                logger.info(f"Processing {agent_name} KB file...")
                
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                # Check if this agent already exists in the table
                existing_result = supabase.table('agent_documents')\
                    .select('id')\
                    .eq('agent_name', agent_name)\
                    .limit(1)\
                    .execute()
                
                if existing_result.data:
                    logger.info(f"Agent {agent_name} already exists in agent_documents table, skipping...")
                    continue
                
                # Generate embedding for the content
                logger.info(f"Generating embedding for {agent_name}...")
                embedding = get_embedding(content)
                
                if embedding is None:
                    logger.error(f"Failed to generate embedding for {agent_name}")
                    continue
                
                # Insert into agent_documents table
                insert_data = {
                    'agent_name': agent_name,
                    'content': content,
                    'embedding': embedding,
                    'metadata': {
                        'source': 'kb_file',
                        'filename': filename,
                        'content_length': len(content),
                        'chunk_index': 0
                    }
                }
                
                result = supabase.table('agent_documents')\
                    .insert(insert_data)\
                    .execute()
                
                if result.data:
                    logger.info(f"Successfully inserted {agent_name} into agent_documents table")
                else:
                    logger.error(f"Failed to insert {agent_name} into agent_documents table")
        
        logger.info("Finished populating agent_documents table")
        return True
        
    except Exception as e:
        logger.error(f"Error populating agent_documents table: {str(e)}")
        return False

async def generate_contextual_response_for_detected_url(user_message: str, url: str, agent_name: str) -> str:
    """Generate a contextual response when a URL is detected in the user's message"""
    
    # Dynamically load agent information from KB files
    agent_info = await load_agent_kb_info(agent_name)
    
    # Analyze the user's intent based on their message
    user_message_lower = user_message.lower()
    
    # Create capabilities summary from agent's actual expertise
    capabilities = ', '.join(agent_info['expertise_areas'][:3])  # Use first 3 expertise areas
    if len(agent_info['expertise_areas']) > 3:
        capabilities += ', and more'
    
    # Determine user intent
    intent_keywords = {
        'analyze': ['analyze', 'analysis', 'review', 'check', 'examine', 'look at', 'evaluate'],
        'pricing': ['price', 'cost', 'pricing', 'charges', 'fees', 'rates', 'quote'],
        'services': ['services', 'help', 'offer', 'provide', 'do', 'capabilities'],
        'improve': ['improve', 'optimize', 'enhance', 'better', 'fix', 'recommendations'],
        'compare': ['compare', 'vs', 'versus', 'against', 'difference'],
        'general': ['website', 'site', 'business', 'company']
    }
    
    detected_intent = 'general'
    for intent, keywords in intent_keywords.items():
        if any(keyword in user_message_lower for keyword in keywords):
            detected_intent = intent
            break
    
    # Generate contextual responses based on intent and agent's actual KB
    responses = {
        'analyze': f"I found your website {url}! As your {agent_info['role']}, I'll analyze it and provide insights on {capabilities}. Let me examine your site and give you actionable recommendations.",
        
        'pricing': f"I see you've shared {url} and want to know about pricing. As your {agent_info['role']}, I'll analyze your website to understand your business needs and provide you with relevant pricing information for our services.",
        
        'services': f"Perfect! I found your website {url}. As your {agent_info['role']}, I can help you with {capabilities}. Let me analyze your site to better understand how I can assist you.",
        
        'improve': f"Great! I found {url} and I can see you want to improve it. As your {agent_info['role']}, I'll analyze your website and provide specific recommendations for {capabilities} to enhance your online presence.",
        
        'compare': f"I found your website {url}. As your {agent_info['role']}, I can analyze your site and help you understand how our services compare to others in terms of {capabilities}.",
        
        'general': f"Thanks for sharing {url}! As your {agent_info['role']}, I'll analyze your website to provide you with insights on {capabilities}. This will help me give you more targeted recommendations."
    }
    
    base_response = responses.get(detected_intent, responses['general'])
    
    # Add a call-to-action based on the agent's actual responsibilities
    primary_responsibility = agent_info['responsibilities'][0] if agent_info['responsibilities'] else "provide recommendations"
    cta = f" I specialize in {primary_responsibility.lower()} and can provide you with detailed insights."
    
    return f"{base_response}{cta}"


@app.post("/admin/populate-agent-documents")
async def populate_agent_documents_endpoint():
    """Admin endpoint to populate agent_documents table from KB files"""
    try:
        success = await populate_agent_documents_table()
        if success:
            return {
                "status": "success",
                "message": "Agent documents table populated successfully"
            }
        else:
            return {
                "status": "error", 
                "message": "Failed to populate agent documents table"
            }
    except Exception as e:
        logger.error(f"Error in populate_agent_documents_endpoint: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

@app.get("/admin/test-agent-kb/{agent_name}")
async def test_agent_kb_loading(agent_name: str):
    """Test endpoint to check dynamic agent KB loading"""
    try:
        info = await load_agent_kb_info(agent_name)
        return {
            "status": "success",
            "agent_name": agent_name,
            "agent_info": info
        }
    except Exception as e:
        logger.error(f"Error testing agent KB loading for {agent_name}: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

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

# =============================================================================
# TOOL ENDPOINTS - Organized Tools Integration
# =============================================================================

@app.get("/api/solar/insights")
async def solar_insights_endpoint(address: str):
    """Get solar insights for an address using RealWave API"""
    try:
        result = tools.get_solar_insights(address)
        return result
    except Exception as e:
        logger.error(f"Error in solar insights endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/solar/data-layers")
async def solar_data_layers_endpoint(address: str):
    """Get solar data layers for visualization"""
    try:
        result = tools.get_solar_data_layers(address)
        return result
    except Exception as e:
        logger.error(f"Error in solar data layers endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/solar/report")
async def solar_report_endpoint(address: str):
    """Generate comprehensive solar report"""
    try:
        result = tools.generate_solar_report(address)
        return result
    except Exception as e:
        logger.error(f"Error in solar report endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/website/screenshot")
async def website_screenshot_endpoint(url: str, session_id: str = None):
    """Capture website screenshot"""
    try:
        result = await tools.capture_website_screenshot_async(url, session_id)
        return result
    except Exception as e:
        logger.error(f"Error in website screenshot endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/website/favicon")
async def website_favicon_endpoint(url: str, session_id: str = None):
    """Get website favicon"""
    try:
        result = await tools.get_website_favicon_async(url, session_id)
        return result
    except Exception as e:
        logger.error(f"Error in website favicon endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ghl/contact")
async def create_contact_endpoint(
    first_name: str,
    last_name: str, 
    email: str,
    phone: str,
    location_id: str = None,
    company_name: str = None
):
    """Create a new contact in GoHighLevel"""
    try:
        result = tools.create_contact(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            location_id=location_id,
            company_name=company_name
        )
        return result
    except Exception as e:
        logger.error(f"Error in create contact endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ghl/contact/{contact_id}")
async def get_contact_endpoint(contact_id: str, location_id: str = None):
    """Get contact details from GoHighLevel"""
    try:
        result = tools.get_contact(contact_id, location_id)
        return result
    except Exception as e:
        logger.error(f"Error in get contact endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# AGENT BUSINESS SETUP ENDPOINTS
# =============================================================================

class AgentSetupRequest(BaseModel):
    user_id: str
    agent_id: str
    agent_name: str
    setup_data: Dict[str, Any]
    is_enabled: bool = True
    setup_type: str = "agent_config"  # agent_config, SolarSetup, CalendarSetup, NotificationSetup, SOLAgent
    session_id: Optional[str] = None

class AgentStatusRequest(BaseModel):
    user_id: str
    agent_id: str
    is_enabled: bool
    setup_type: str = "agent_config"  # agent_config, SolarSetup, CalendarSetup, NotificationSetup, SOLAgent

@app.get("/api/agents/setup/{user_id}")
async def get_user_agents(user_id: str):
    """Get all agent setups for a user"""
    try:
        result = supabase.table('squidgy_agent_business_setup')\
            .select('*')\
            .eq('firm_user_id', user_id)\
            .order('agent_id')\
            .execute()
        
        if result.data:
            return {
                "status": "success",
                "agents": result.data,
                "count": len(result.data)
            }
        else:
            return {
                "status": "success", 
                "agents": [],
                "count": 0
            }
            
    except Exception as e:
        logger.error(f"Error getting user agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/setup/{user_id}/{agent_id}")
async def get_agent_setup(user_id: str, agent_id: str, setup_type: Optional[str] = None):
    """Get specific agent setup for a user, optionally filtered by setup_type"""
    try:
        query = supabase.table('squidgy_agent_business_setup')\
            .select('*')\
            .eq('firm_user_id', user_id)\
            .eq('agent_id', agent_id)
        
        # If setup_type is provided, filter by it
        if setup_type:
            query = query.eq('setup_type', setup_type)
            result = query.single().execute()
        else:
            # If no setup_type specified, get all setups for this agent
            result = query.execute()
        
        if result.data:
            return {
                "status": "success",
                "agent": result.data,
                "exists": True
            }
        else:
            return {
                "status": "success",
                "agent": None,
                "exists": False
            }
            
    except Exception as e:
        logger.error(f"Error getting agent setup: {str(e)}")
        return {
            "status": "success",
            "agent": None,
            "exists": False
        }

@app.post("/api/agents/setup")
async def create_or_update_agent_setup(request: AgentSetupRequest):
    """Create or update agent setup for a user"""
    try:
        # For setup_type specific updates, we need to consider the unique constraint
        # Try to update first using firm_user_id, agent_id, and setup_type
        update_result = supabase.table('squidgy_agent_business_setup')\
            .update({
                'agent_name': request.agent_name,
                'setup_json': request.setup_data,
                'is_enabled': request.is_enabled,
                'session_id': request.session_id,
                'updated_at': datetime.now().isoformat()
            })\
            .eq('firm_user_id', request.user_id)\
            .eq('agent_id', request.agent_id)\
            .eq('setup_type', request.setup_type)\
            .execute()
        
        # If no rows updated, insert new record
        if not update_result.data or len(update_result.data) == 0:
            insert_result = supabase.table('squidgy_agent_business_setup')\
                .insert({
                    'firm_user_id': request.user_id,
                    'agent_id': request.agent_id,
                    'agent_name': request.agent_name,
                    'setup_json': request.setup_data,
                    'setup_type': request.setup_type,
                    'session_id': request.session_id,
                    'is_enabled': request.is_enabled,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                })\
                .execute()
            
            return {
                "status": "success",
                "action": "created",
                "agent": insert_result.data[0] if insert_result.data else None
            }
        else:
            return {
                "status": "success", 
                "action": "updated",
                "agent": update_result.data[0] if update_result.data else None
            }
            
    except Exception as e:
        logger.error(f"Error creating/updating agent setup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/status")
async def update_agent_status(request: AgentStatusRequest):
    """Update agent enabled/disabled status"""
    try:
        result = supabase.table('squidgy_agent_business_setup')\
            .update({
                'is_enabled': request.is_enabled,
                'updated_at': datetime.now().isoformat()
            })\
            .eq('firm_user_id', request.user_id)\
            .eq('agent_id', request.agent_id)\
            .eq('setup_type', request.setup_type)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return {
                "status": "success",
                "agent": result.data[0],
                "enabled": request.is_enabled
            }
        else:
            # No record exists for this setup_type
            return {
                "status": "error",
                "message": f"No {request.setup_type} configuration found for agent {request.agent_id}. Complete the progressive setup first.",
                "enabled": False
            }
            
    except Exception as e:
        logger.error(f"Error updating agent status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/agents/setup/{user_id}/{agent_id}")
async def delete_agent_setup(user_id: str, agent_id: str, setup_type: Optional[str] = None):
    """Delete agent setup for a user, optionally filtered by setup_type"""
    try:
        query = supabase.table('squidgy_agent_business_setup')\
            .delete()\
            .eq('firm_user_id', user_id)\
            .eq('agent_id', agent_id)
        
        # If setup_type is provided, filter by it
        if setup_type:
            query = query.eq('setup_type', setup_type)
        
        result = query.execute()
        
        return {
            "status": "success",
            "deleted": True,
            "count": len(result.data) if result.data else 0
        }
        
    except Exception as e:
        logger.error(f"Error deleting agent setup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Progressive Setup Convenience Endpoints
@app.get("/api/agents/setup/{user_id}/{agent_id}/progress")
async def get_agent_setup_progress(user_id: str, agent_id: str):
    """Get setup progress for SOL Agent progressive setup"""
    try:
        # Get all setup types for this agent
        result = supabase.table('squidgy_agent_business_setup')\
            .select('setup_type, is_enabled, created_at, updated_at')\
            .eq('firm_user_id', user_id)\
            .eq('agent_id', agent_id)\
            .in_('setup_type', ['SolarSetup', 'CalendarSetup', 'NotificationSetup'])\
            .execute()
        
        setup_progress = {
            'solar_completed': False,
            'calendar_completed': False,
            'notifications_completed': False,
            'solar_completed_at': None,
            'calendar_completed_at': None,
            'notifications_completed_at': None
        }
        
        if result.data:
            for setup in result.data:
                if setup['setup_type'] == 'SolarSetup' and setup['is_enabled']:
                    setup_progress['solar_completed'] = True
                    setup_progress['solar_completed_at'] = setup['created_at']
                elif setup['setup_type'] == 'CalendarSetup' and setup['is_enabled']:
                    setup_progress['calendar_completed'] = True
                    setup_progress['calendar_completed_at'] = setup['created_at']
                elif setup['setup_type'] == 'NotificationSetup' and setup['is_enabled']:
                    setup_progress['notifications_completed'] = True
                    setup_progress['notifications_completed_at'] = setup['created_at']
        
        return {
            "status": "success",
            "progress": setup_progress,
            "setups_found": len(result.data) if result.data else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting agent setup progress: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================

# GHL Sub-account and User Creation Endpoints
class GHLSubAccountRequest(BaseModel):
    company_id: str
    snapshot_id: str
    agency_token: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: Optional[str] = None
    website: Optional[str] = None
    prospect_first_name: Optional[str] = None
    prospect_last_name: Optional[str] = None
    prospect_email: Optional[str] = None
    allow_duplicate_contact: bool = False
    allow_duplicate_opportunity: bool = False
    allow_facebook_name_merge: bool = False
    disable_contact_timezone: bool = False
    subaccount_name: Optional[str] = None

class SecureGHLSubAccountRequest(BaseModel):
    subaccount_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: Optional[str] = None
    website: Optional[str] = None
    business_email: Optional[str] = None
    prospect_email: Optional[str] = None
    prospect_first_name: Optional[str] = None
    prospect_last_name: Optional[str] = None
    allow_duplicate_contact: Optional[bool] = False
    allow_duplicate_opportunity: Optional[bool] = False
    allow_facebook_name_merge: Optional[bool] = False
    disable_contact_timezone: Optional[bool] = False
    
class GHLUserCreationRequest(BaseModel):
    company_id: str
    location_id: str
    agency_token: str
    # All fields below are optional with defaults
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    account_type: Optional[str] = "account"
    role: Optional[str] = "user"
    custom_permissions: Optional[Dict[str, Any]] = None

# Global variable to store location_id after subaccount creation
last_created_location_id = None

@app.post("/api/ghl/create-subaccount")
async def create_ghl_subaccount(request: SecureGHLSubAccountRequest):
    """Create a GoHighLevel sub-account with solar snapshot"""
    global last_created_location_id
    
    try:
        # Generate unique name with timestamp
        timestamp = datetime.now().strftime("%H%M%S")
        subaccount_name = request.subaccount_name or f"SolarSetup_Clone_{timestamp}"

        # Import and use the working GoHighLevel API credentials from constants
        try:
            from GHL.environment.constant import Constant
            constants = Constant()
            company_id = constants.Company_Id
            # Try Agency_Access_Key as it might be a non-expiring access key
            agency_token = constants.Agency_Access_Key
            snapshot_id = "7oAH6Cmto5ZcWAaEsrrq"  # Updated snapshot ID
            logger.info(f"Using Agency_Access_Key for authentication")
        except ImportError:
            # Fallback to hardcoded values if import fails
            company_id = "lp2p1q27DrdGta1qGDJd"
            agency_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJsb2NhdGlvbl9pZCI6ImxCUHFnQm93WDFDc2pIYXkxMkxZIiwidmVyc2lvbiI6MSwiaWF0IjoxNzMxOTkyNDg3MDU0LCJzdWIiOiJhWjBuNGV0ck5DRUIyOXNvbmE4TSJ9.czCh27fEwqxW4KzDx0gVbYcpdtcChy_31h9SoQuptAA"
            snapshot_id = "7oAH6Cmto5ZcWAaEsrrq"
            logger.info(f"Using fallback Nestle_Api_Key for authentication")
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {agency_token}",
            "Version": "2021-07-28",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }


        # Set default values for missing fields
        phone = request.phone or "+17166044029"
        address = request.address or "456 Solar Demo Avenue"
        city = request.city or "Buffalo"
        state = request.state or "NY"
        country = request.country or "US"
        postal_code = request.postal_code or "14201"
        website = request.website if hasattr(request, 'website') and request.website else f"https://solar-{timestamp}.com"

        # Determine timezone based on country if not provided
        if not request.timezone:
            try:
                # Import the consolidated timezone utility
                from ghl_timezone_utils import get_timezone_for_ghl
                country_code = country
                # Get timezone based on country and validate it
                timezone = get_timezone_for_ghl(country_code)
                logger.info(f"Automatically selected timezone '{timezone}' based on country '{country_code}'")
            except Exception as e:
                # Fallback to default timezone if there's an error
                timezone = "America/New_York"
                logger.warning(f"Error selecting timezone by country: {str(e)}. Using default: {timezone}")
        else:
            timezone = request.timezone

        # Set prospect info with defaults or provided values
        prospect_first_name = request.prospect_first_name or "Solar"
        prospect_last_name = request.prospect_last_name or "Customer"
        prospect_email = request.prospect_email or f"admin+{timestamp}@solar-setup.com"

        # Use business email if provided, otherwise use prospect email
        business_email = request.business_email if hasattr(request, 'business_email') and request.business_email else prospect_email
        
        # Validate country code - GHL expects 2-letter country codes
        # Based on GHL API documentation - using common valid country codes
        valid_country_codes = {
            "AF", "AL", "DZ", "AD", "AO", "AG", "AR", "AM", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", 
            "BE", "BZ", "BJ", "BT", "BO", "BA", "BW", "BR", "BN", "BG", "BF", "BI", "KH", "CM", "CA", "CV", 
            "CF", "TD", "CL", "CN", "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CY", "CZ", "DK", 
            "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "ET", "FJ", "FI", "FR", "GA", "GM", "GE", 
            "DE", "GH", "GR", "GD", "GT", "GN", "GW", "GY", "HT", "HN", "HK", "HU", "IS", "IN", "ID", "IR", 
            "IQ", "IE", "IL", "IT", "JM", "JP", "JO", "KZ", "KE", "KI", "KP", "KR", "XK", "KW", "KG", "LA", 
            "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MK", "MG", "MW", "MY", "MV", "ML", "MT", "MR", 
            "MU", "MX", "FM", "MD", "MC", "MN", "ME", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "NZ", "NI", 
            "NE", "NG", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PL", "PT", "QA", "RO", 
            "RU", "RW", "KN", "LC", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SK", "SI", 
            "SB", "SO", "ZA", "ES", "LK", "SD", "SR", "SZ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", 
            "TG", "TO", "TT", "TN", "TR", "TM", "TV", "UG", "GB", "UA", "AE", "US", "UY", "UZ", "VU", "VE", 
            "VN", "YE", "ZM", "ZW"
        }
        
        # Ensure country code is valid, default to "US" if not  
        country_code = request.country.upper() if request.country and request.country.upper() in valid_country_codes else "US"
        
        # Prepare payload
        payload = {
            "name": subaccount_name,  # Use subaccount_name as the business name
            "phone": phone,
            "email": business_email,  # Include email at the top level for business email
            "companyId": company_id,
            "address": address,
            "city": city,
            "state": state,
            "country": country,
            "postalCode": postal_code,
            "website": website,
            "timezone": timezone,
            "prospectInfo": {
                "firstName": prospect_first_name,
                "lastName": prospect_last_name,
                "email": prospect_email
            },
            "settings": {
                "allowDuplicateContact": request.allow_duplicate_contact,
                "allowDuplicateOpportunity": request.allow_duplicate_opportunity,
                "allowFacebookNameMerge": request.allow_facebook_name_merge,
                "disableContactTimezone": request.disable_contact_timezone
            },
            "snapshotId": snapshot_id
        }

        logger.info(f"Creating GHL sub-account: {subaccount_name}")
        logger.info(f"Using API credentials - Company ID: {company_id}, Snapshot ID: {snapshot_id}")
        logger.info(f"API Token (first 20 chars): {agency_token[:20]}...")
        logger.info(f"Payload: {payload}")
        
        logger.info(f"Creating GHL sub-account: {subaccount_name} with country: {country_code}")
        
        # Make the API call
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://services.leadconnectorhq.com/locations/",
                headers=headers,
                json=payload
            )

            # Log response details for debugging
            logger.info(f"GHL API Response Status: {response.status_code}")
            logger.info(f"GHL API Response Headers: {dict(response.headers)}")
            try:
                response_json = response.json()
                logger.info(f"GHL API Response Body: {response_json}")
            except:
                logger.info(f"GHL API Response Text: {response.text}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            location_id = data.get('id')
            last_created_location_id = location_id  # Store for user creation
            
            logger.info(f"Successfully created sub-account with ID: {location_id}")
            
            return {
                "status": "success",
                "message": "Sub-account created successfully",
                "location_id": location_id,
                "subaccount_name": subaccount_name,
                "details": data
            }
        else:
            # logger.error(f"Failed to create sub-account: {response.status_code} - {response.text}")
            # Get detailed error information
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json
            except:
                pass

            logger.error(f"Failed to create sub-account: {response.status_code} - {error_detail}")

            # Provide more helpful error messages based on status code
            if response.status_code == 401:
                error_msg = "Authentication failed - Invalid API token"
            elif response.status_code == 403:
                error_msg = "Access forbidden - Check API permissions"
            elif response.status_code == 400:
                error_msg = f"Bad request - Invalid payload: {error_detail}"
            elif response.status_code == 500:
                error_msg = f"GoHighLevel server error: {error_detail}"
            else:
                error_msg = f"Failed to create sub-account: {error_detail}"
            raise HTTPException(
                status_code=response.status_code,
                detail=error_msg
            )
            
    except httpx.TimeoutException:
        logger.error("Timeout while creating sub-account")
        raise HTTPException(status_code=504, detail="Timeout while creating sub-account")
    except Exception as e:
        logger.error(f"Error creating sub-account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ghl/create-user")
async def create_ghl_user(request: GHLUserCreationRequest):
    """Create a GoHighLevel user (OVI user only, not admin)"""
    try:
        # Full permissions for the user
         # Set default values for missing fields
        timestamp = datetime.now().strftime("%H%M%S")
        first_name = request.first_name or "Ovi"
        last_name = request.last_name or "Colton"
        password = request.password or "Dummy@123"
        phone = request.phone or "+17166044029"

        # Generate unique email to avoid conflicts if not provided
        email = request.email or f"ovi+{timestamp}@test-solar.com"

        # Use custom permissions if provided, otherwise use default permissions
        permissions = request.custom_permissions if request.custom_permissions else {
            "campaignsEnabled": True,
            "campaignsReadOnly": False,
            "contactsEnabled": True,
            "workflowsEnabled": True,
            "workflowsReadOnly": False,
            "triggersEnabled": True,
            "funnelsEnabled": True,
            "websitesEnabled": True,
            "opportunitiesEnabled": True,
            "dashboardStatsEnabled": True,
            "bulkRequestsEnabled": True,
            "appointmentsEnabled": True,
            "reviewsEnabled": True,
            "onlineListingsEnabled": True,
            "phoneCallEnabled": True,
            "conversationsEnabled": True,
            "assignedDataOnly": False,
            "adwordsReportingEnabled": True,
            "membershipEnabled": True,
            "facebookAdsReportingEnabled": True,
            "attributionsReportingEnabled": True,
            "settingsEnabled": True,
            "tagsEnabled": True,
            "leadValueEnabled": True,
            "marketingEnabled": True,
            "agentReportingEnabled": True,
            "botService": True,
            "socialPlanner": True,
            "bloggingEnabled": True,
            "invoiceEnabled": True,
            "affiliateManagerEnabled": True,
            "contentAiEnabled": True,
            "refundsEnabled": True,
            "recordPaymentEnabled": True,
            "cancelSubscriptionEnabled": True,
            "paymentsEnabled": True,
            "communitiesEnabled": True,
            "exportPaymentsEnabled": True
        }
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {request.agency_token}",
            "Version": "2021-07-28",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Use the actual user email for downstream Facebook integration
        # This ensures the same credentials are used throughout the flow
        
        # Prepare payload for Soma's user account
        payload = {
            "companyId": request.company_id,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "password": password,
            "phone": phone,
            "type": request.account_type,
            "role": request.role,
            "locationIds": [request.location_id],
            "permissions": permissions
        }
        
    
        # Make the API call
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://services.leadconnectorhq.com/users/",
                headers=headers,
                json=payload
            )
        
        if response.status_code in [200, 201]:
            data = response.json()
            user_id = data.get('id')
            
            logger.info(f"✅ User created successfully: {user_id}")
            
            return {
                "status": "success",
                "user_id": user_id,
                "message": "GoHighLevel user created successfully!",
                "details": {
                    "name": f"{request.first_name} {request.last_name}",
                    "email": email,
                    "role": "user",
                    "location_id": request.location_id,
                    "created_at": datetime.now().isoformat()
                }
            }
        else:
            logger.error(f"Failed to create user: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to create user: {response.text}"
            )
            
    except httpx.TimeoutException:
        logger.error("Timeout while creating user")
        raise HTTPException(status_code=504, detail="Timeout while creating user")
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def create_agency_user(
    company_id: str,
    location_id: str,
    agency_token: str,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    phone: str,
    role: str = "user",
    permissions: dict = None,
    scopes: list = None
):
    """Create user using agency-level API (like Ovi Colton pattern)"""
    
    payload = {
        "companyId": company_id,
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "password": password,
        "phone": phone,
        "type": "account",
        "role": role,
        "locationIds": [location_id],  # Assign to specific location
        "permissions": permissions or {},
        "scopes": scopes or [],
        "scopesAssignedToOnly": []  # Empty for full access
    }
    
    headers = {
        "Authorization": f"Bearer {agency_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://services.leadconnectorhq.com/users/",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 201:
                user_data = response.json()
                return {
                    "status": "success",
                    "message": "User created successfully via agency API",
                    "user_id": user_data.get("id"),
                    "details": {
                        "name": f"{first_name} {last_name}",
                        "email": email,
                        "role": role,
                        "location_ids": [location_id]
                    },
                    "raw_response": user_data
                }
            else:
                error_text = response.text
                logger.error(f"Failed to create user via agency API: {response.status_code} - {error_text}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create user: {response.status_code} - {error_text}"
                )
                
    except Exception as e:
        logger.error(f"Exception in agency user creation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"User creation failed: {str(e)}")

@app.post("/api/ghl/create-subaccount-and-user")
async def create_subaccount_and_user(request: GHLSubAccountRequest):
    """Create both sub-account and user in one call - triggered after Solar setup completion"""
    try:
        # First create the sub-account
        secure_request = SecureGHLSubAccountRequest(
            subaccount_name=request.subaccount_name,
            phone=request.phone,
            address=request.address,
            city=request.city,
            state=request.state,
            country=request.country,
            postal_code=request.postal_code,
            timezone=request.timezone,
            website=request.website if hasattr(request, 'website') else None,
            prospect_email=request.prospect_email,
            prospect_first_name=request.prospect_first_name,
            prospect_last_name=request.prospect_last_name,
            allow_duplicate_contact=request.allow_duplicate_contact,
            allow_duplicate_opportunity=request.allow_duplicate_opportunity,
            allow_facebook_name_merge=request.allow_facebook_name_merge,
            disable_contact_timezone=request.disable_contact_timezone
        )

        subaccount_response = await create_ghl_subaccount(secure_request)
        
        if subaccount_response["status"] != "success":
            return subaccount_response
        
        location_id = subaccount_response["location_id"]
        
        # Create TWO users: 1) Business Owner 2) Soma Addakula
        
        # First user: Business Owner with form data
        business_user_request = GHLUserCreationRequest(
            company_id=request.company_id,
            location_id=location_id,
            agency_token=request.agency_token,
            first_name=request.prospect_first_name,
            last_name=request.prospect_last_name,
            email=request.prospect_email,
            password="Dummy@123",  # Standard password as requested
            phone=request.phone
        )
        
        # Create users using proper agency-level API with full permissions
        
        # Full permissions (same as Ovi Colton example)
        full_permissions = {
            "campaignsEnabled": True,
            "campaignsReadOnly": False,
            "contactsEnabled": True,
            "workflowsEnabled": True,
            "workflowsReadOnly": False,
            "triggersEnabled": True,
            "funnelsEnabled": True,
            "websitesEnabled": True,
            "opportunitiesEnabled": True,
            "dashboardStatsEnabled": True,
            "bulkRequestsEnabled": True,
            "appointmentsEnabled": True,
            "reviewsEnabled": True,
            "onlineListingsEnabled": True,
            "phoneCallEnabled": True,
            "conversationsEnabled": True,
            "assignedDataOnly": False,
            "adwordsReportingEnabled": True,
            "membershipEnabled": True,
            "facebookAdsReportingEnabled": True,
            "attributionsReportingEnabled": True,
            "settingsEnabled": True,
            "tagsEnabled": True,
            "leadValueEnabled": True,
            "marketingEnabled": True,
            "agentReportingEnabled": True,
            "botService": True,
            "socialPlanner": True,
            "bloggingEnabled": True,
            "invoiceEnabled": True,
            "affiliateManagerEnabled": True,
            "contentAiEnabled": True,
            "refundsEnabled": True,
            "recordPaymentEnabled": True,
            "cancelSubscriptionEnabled": True,
            "paymentsEnabled": True,
            "communitiesEnabled": True,
            "exportPaymentsEnabled": True
        }
        
        # Use empty scopes array (will disable all scopes but allow user creation)
        location_scopes = []
        
        # Create business user using agency API
        business_user_response = await create_agency_user(
            company_id=request.company_id,
            location_id=location_id,
            agency_token=request.agency_token,
            first_name=request.prospect_first_name,
            last_name=request.prospect_last_name,
            email=request.prospect_email,
            password="Dummy@123",
            phone=request.phone,
            role="user",
            permissions=full_permissions,
            scopes=location_scopes
        )
        
        # Second user: Soma Addakula with location-specific email
        # Use location-specific email to avoid conflicts
        soma_email = f"somashekhar34@gmail.com"
        
        soma_user_request = GHLUserCreationRequest(
            company_id=request.company_id,
            location_id=location_id,
            agency_token=request.agency_token,
            first_name="Soma",
            last_name="Addakula",
            email=soma_email,  # Use unique email per location
            password="Dummy@123",
            phone=request.phone or "+17166044029"  # Use business phone or default
        )
        
        # Create Soma user using agency API
        soma_user_response = await create_agency_user(
            company_id=request.company_id,
            location_id=location_id,
            agency_token=request.agency_token,
            first_name="Soma",
            last_name="Addakula",
            email="somashekhar34@gmail.com",
            password="Dummy@123",
            phone="+17166044029",
            role="user",
            permissions=full_permissions,
            scopes=location_scopes
        )
        
        # Return combined response with SOMA's credentials for downstream Facebook integration
        return {
            "status": "success",
            "message": "GoHighLevel sub-account and TWO users created successfully!",
            "subaccount": subaccount_response,
            "business_user": business_user_response,
            "soma_user": soma_user_response,
            "user": soma_user_response,  # Main user field points to Soma for Facebook integration
            "facebook_integration_credentials": {
                "email": soma_user_request.email,  # Soma's credentials for Facebook
                "password": soma_user_request.password,  # Soma's credentials  
                "phone": soma_user_request.phone,  # Soma's credentials
                "location_id": location_id,
                "user_id": soma_user_response.get("user_id") if soma_user_response.get("status") == "success" else None,
                "ready_for_facebook": True
            },
            "details": {
                "name": f"{soma_user_request.first_name} {soma_user_request.last_name}",
                "email": soma_user_request.email,
                "role": "Admin User"
            },
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in combined creation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Facebook OAuth Integration Endpoints
# =============================================================================

class FacebookOAuthRequest(BaseModel):
    locationId: str
    userId: str

class FacebookOAuthExtractor:
    """Facebook OAuth parameter extraction utility for GHL integration"""
    
    @staticmethod
    async def extract_params(location_id: str, user_id: str) -> dict:
        """Extract OAuth parameters from GHL Facebook service"""
        try:
            ghl_url = f"https://services.leadconnectorhq.com/social-media-posting/oauth/facebook/start?locationId={location_id}&userId={user_id}"
            
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.get(ghl_url)
                
                if response.status_code not in [301, 302]:
                    raise ValueError(f"Expected redirect from GHL service, got {response.status_code}")
                
                redirect_url = response.headers.get('location', '')
                if not redirect_url or 'facebook.com' not in redirect_url:
                    raise ValueError(f"Invalid redirect URL: {redirect_url}")
                
                params = {}
                
                if 'facebook.com/privacy/consent/gdp' in redirect_url:
                    # Extract from GDPR consent page (URL encoded)
                    import re
                    import urllib.parse
                    patterns = {
                        'app_id': r'params%5Bapp_id%5D=(\d+)',
                        'redirect_uri': r'params%5Bredirect_uri%5D=%22([^%]+(?:%[^%]+)*)',
                        'scope': r'params%5Bscope%5D=(%5B[^%]+(?:%[^%]+)*%5D)',
                        'state': r'params%5Bstate%5D=%22([^%]+(?:%[^%]+)*)',
                        'logger_id': r'params%5Blogger_id%5D=%22([^%]+)'
                    }
                    
                    for param, pattern in patterns.items():
                        match = re.search(pattern, redirect_url)
                        if match:
                            value = match.group(1)
                            
                            if param == 'app_id':
                                params['app_id'] = value
                                params['client_id'] = value
                            elif param == 'redirect_uri':
                                params['redirect_uri'] = urllib.parse.unquote(value.replace('\\%2F', '/').replace('\\', ''))
                            elif param == 'scope':
                                try:
                                    scope_str = urllib.parse.unquote(value)
                                    scope_array = json.loads(scope_str.replace('\\', ''))
                                    params['scope'] = ','.join(scope_array)
                                except:
                                    params['scope'] = 'email,pages_show_list,pages_read_engagement'
                            elif param == 'state':
                                params['state'] = urllib.parse.unquote(value.replace('\\', ''))
                            elif param == 'logger_id':
                                params['logger_id'] = value
                    
                    params['response_type'] = 'code'
                    
                elif 'facebook.com/dialog/oauth' in redirect_url:
                    # Extract from direct OAuth URL
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(redirect_url)
                    query_params = parse_qs(parsed.query)
                    
                    for key, value in query_params.items():
                        params[key] = value[0] if value else None
                
                return {
                    'success': True,
                    'params': params,
                    'redirect_url': redirect_url,
                    'extracted_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Facebook OAuth extraction error: {str(e)}")
            raise

@app.post("/api/facebook/extract-oauth-params")
async def extract_facebook_oauth_params(request: FacebookOAuthRequest):
    """
    Extract Facebook OAuth parameters from GHL service for Squidgy chat integration
    
    This endpoint is used by the chat window in the frontend to generate
    Facebook OAuth URLs for solar sales specialists to connect their Facebook accounts.
    """
    try:
        logger.info(f"🔍 Extracting Facebook OAuth params for location: {request.locationId}, user: {request.userId}")
        
        result = await FacebookOAuthExtractor.extract_params(request.locationId, request.userId)
        
        logger.info(f"✅ Successfully extracted Facebook OAuth parameters")
        logger.info(f"   Client ID: {result['params'].get('client_id', 'NOT_FOUND')}")
        logger.info(f"   Redirect URI: {result['params'].get('redirect_uri', 'NOT_FOUND')}")
        
        return result
        
    except ValueError as e:
        logger.error(f"❌ Facebook OAuth extraction error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"💥 Unexpected error in Facebook OAuth extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/facebook/oauth-health")
async def facebook_oauth_health():
    """Health check for Facebook OAuth service"""
    return {
        "service": "facebook_oauth",
        "status": "healthy",
        "endpoints": [
            "/api/facebook/extract-oauth-params",
            "/api/facebook/integrate",
            "/api/facebook/integration-status/{location_id}",
            "/api/facebook/connect-page"
        ],
        "timestamp": datetime.now().isoformat()
    }

# =============================================================================
# FACEBOOK INTEGRATION WITH BROWSER AUTOMATION
# =============================================================================

# In-memory storage for integration status (in production, use Redis or database)
integration_status = {}

@app.post("/api/facebook/integrate")
async def integrate_facebook(request: dict, background_tasks: BackgroundTasks):
    """Start Facebook integration with browser automation"""
    
    location_id = request.get('location_id')
    if not location_id:
        raise HTTPException(status_code=400, detail="location_id required")
    
    # Initialize status
    integration_status[location_id] = {
        "status": "processing",
        "current_step": "Starting browser automation...",
        "started_at": datetime.now().isoformat()
    }
    
    # Start background task
    background_tasks.add_task(run_facebook_integration, request)
    
    return {
        "status": "processing",
        "message": "Facebook integration started. Browser automation in progress...",
        "location_id": location_id
    }

async def run_facebook_integration(request: dict):
    """Run the actual Facebook integration with browser automation"""
    
    location_id = request.get('location_id')
    
    try:
        # Import os here to avoid issues
        import os
        
        # Check if we're on Heroku
        is_heroku = os.environ.get('DYNO') is not None
        
        if is_heroku:
            # Use alternative approach for Heroku
            integration_status[location_id]["current_step"] = "Using Heroku-compatible integration..."
            
            from facebook_integration_alternative import integrate_facebook_production
            result = await integrate_facebook_production(request)
            
            if result["status"] == "success":
                integration_status[location_id] = {
                    "status": "success",
                    "pages": result["data"].get("pages", []),
                    "completed_at": datetime.now().isoformat(),
                    "approach": "direct_api"
                }
            elif result["status"] == "oauth_required":
                integration_status[location_id] = {
                    "status": "oauth_required",
                    "oauth_url": result["oauth_url"],
                    "message": "Please complete OAuth manually",
                    "approach": "manual_oauth"
                }
            else:
                integration_status[location_id] = {
                    "status": "failed",
                    "error": result.get("error", "Unknown error"),
                    "failed_at": datetime.now().isoformat()
                }
        else:
            # Use browser automation for local development
            integration_status[location_id]["current_step"] = "Launching browser..."
            
            # Import the Facebook service (only when needed)
            import sys
            import os
            
            # Add the current directory to the Python path
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            
            from facebook_integration_service import FacebookIntegrationService, FacebookIntegrationRequest, EmailConfig
            
            # Configure email for 2FA - Microsoft Outlook
            email_config = EmailConfig(
                email_address=os.environ.get("OUTLOOK_2FA_EMAIL", "sa+01@squidgy.ai"),
                email_password=os.environ.get("OUTLOOK_2FA_PASSWORD", "your-outlook-app-password")
            )
            
            # Create service
            service = FacebookIntegrationService(email_config)
            
            # Create request
            fb_request = FacebookIntegrationRequest(
                location_id=request.get('location_id'),
                user_id=request.get('user_id'),
                email=request.get('email'),
                password=request.get('password'),
                firm_user_id=request.get('firm_user_id'),
                enable_2fa_bypass=request.get('enable_2fa_bypass', False)
            )
            
            # Update status
            integration_status[location_id]["current_step"] = "Logging into GoHighLevel..."
            
            # Run integration
            result = await service.integrate_facebook(fb_request)
            
            if result["status"] == "success":
                integration_status[location_id] = {
                    "status": "success",
                    "pages": result["data"].get("pages", []),
                    "completed_at": datetime.now().isoformat(),
                    "approach": "browser_automation"
                }
            else:
                integration_status[location_id] = {
                    "status": "failed",
                    "error": result.get("error", "Unknown error"),
                    "failed_at": datetime.now().isoformat()
                }
            
    except Exception as e:
        integration_status[location_id] = {
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        }

@app.get("/api/facebook/integration-status/{location_id}")
async def get_integration_status(location_id: str):
    """Get the current integration status for a location"""
    
    if location_id not in integration_status:
        return {
            "status": "not_found",
            "message": "No integration found for this location"
        }
    
    return integration_status[location_id]

@app.post("/api/facebook/connect-page")
async def connect_facebook_page(request: dict):
    """Connect a specific Facebook page to GHL - REAL IMPLEMENTATION"""
    
    location_id = request.get('location_id')
    page_id = request.get('page_id')
    jwt_token = request.get('jwt_token')
    
    print(f"🔍 Connection request received:")
    print(f"   Location ID: {location_id}")
    print(f"   Page ID: {page_id}")
    print(f"   JWT Token: {jwt_token[:50] + '...' if jwt_token else 'None'}")
    
    if not location_id or not page_id or not jwt_token:
        missing_fields = []
        if not location_id: missing_fields.append('location_id')
        if not page_id: missing_fields.append('page_id')
        if not jwt_token: missing_fields.append('jwt_token')
        
        error_msg = f"Missing required fields: {', '.join(missing_fields)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    try:
        # Get page details from database first
        supabase_url = "https://aoteeitreschwzkbpqyd.supabase.co"
        supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFvdGVlaXRyZXNjaHd6a2JwcXlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxMjAwMzQsImV4cCI6MjA1OTY5NjAzNH0.S7P9-G4CaSE6DWycNq0grv-x6UCIsfLvXooCtMwaKHM"
        
        supabase_client = create_client(supabase_url, supabase_key)
        
        # Get page details from database
        page_response = supabase_client.table('squidgy_facebook_pages')\
            .select("*")\
            .eq('location_id', location_id)\
            .eq('page_id', page_id)\
            .execute()
        
        if not page_response.data:
            raise HTTPException(status_code=404, detail=f"Page {page_id} not found in database")
        
        page_data = page_response.data[0]
        
        # Prepare payload for GHL API (based on complete_facebook_viewer.py)
        pages_to_attach = [{
            "facebookPageId": page_data['page_id'],
            "facebookPageName": page_data['page_name'],
            "facebookIgnoreMessages": False,
            "isInstagramAvailable": page_data.get('is_instagram_available', False)
        }]
        
        attach_payload = {"pages": pages_to_attach}
        
        # Call the REAL GHL API to connect the page
        headers = {
            "token-id": jwt_token,
            "channel": "APP",
            "source": "WEB_USER",
            "version": "2021-07-28",
            "accept": "application/json",
            "content-type": "application/json"
        }
        
        attach_url = f"https://backend.leadconnectorhq.com/integrations/facebook/{location_id}/pages"
        
        print(f"🔗 Connecting page {page_data['page_name']} to GHL...")
        print(f"   URL: {attach_url}")
        print(f"   Payload: {json.dumps(attach_payload, indent=2)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                attach_url,
                headers=headers,
                json=attach_payload
            )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code in [200, 201]:
            # Update database to mark as connected
            supabase_client.table('squidgy_facebook_pages')\
                .update({
                    'is_connected_to_ghl': True,
                    'connected_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('location_id', location_id)\
                .eq('page_id', page_id)\
                .execute()
            
            return {
                "success": True,
                "message": f"Page {page_data['page_name']} successfully connected to GHL",
                "page_name": page_data['page_name'],
                "page_id": page_id,
                "ghl_response": response.json() if response.status_code == 200 else None
            }
        else:
            return {
                "success": False,
                "message": f"Failed to connect page to GHL: {response.status_code}",
                "error": response.text
            }
    
    except Exception as e:
        print(f"💥 Error connecting page: {e}")
        return {
            "success": False,
            "message": f"Error connecting page: {str(e)}"
        }

@app.post("/api/facebook/get-pages", response_model=FacebookPagesResponse)
async def get_facebook_pages_endpoint(request: FacebookPagesRequest):
    """
    Main Facebook integration endpoint with 2FA automation
    Handles browser automation, JWT extraction, and Facebook pages retrieval
    """
    return await get_facebook_pages(request)

# =============================================================================

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