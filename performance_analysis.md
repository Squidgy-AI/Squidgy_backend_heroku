# Performance Analysis: /n8n/agent/query Endpoint

## Overview
The `/n8n/agent/query` endpoint is experiencing slow performance (20+ seconds). After analyzing the code, I've identified several bottlenecks and optimization opportunities.

## Current Flow
1. **Embedding Generation** - Using sentence-transformers locally
2. **Agent Context Retrieval** - Database query with caching
3. **Client Context Retrieval** - Supabase RPC call with similarity search
4. **Agent Knowledge Retrieval** - Supabase RPC call with similarity search
5. **Context Building** - Aggregating data from multiple sources
6. **Missing Info Check** - Sequential checking of must-have fields
7. **Query Analysis** - Simple confidence calculation
8. **Response Generation** - Template-based response (no AI model calls)

## Identified Bottlenecks

### 1. **Embedding Generation (Potential: 2-5 seconds)**
- **Issue**: Using sentence-transformers model locally, which requires model loading on first use
- **Location**: `embedding_service.py` - `get_embedding()` method
- **Impact**: Model initialization can take 2-5 seconds on first call
- **Evidence**: The model is loaded lazily when first needed

### 2. **Multiple Sequential Database Calls (Major: 10-15 seconds)**
- **Issue**: Making 3+ sequential database calls without parallelization
- **Calls**:
  1. `get_agent_context_from_kb()` - Agent documents query
  2. `get_client_context_similarity()` - RPC call for client context
  3. `get_agent_knowledge_smart()` - RPC call for agent knowledge
- **Impact**: Each RPC call can take 3-5 seconds, totaling 10-15 seconds

### 3. **Inefficient Context Building (Minor: 1-2 seconds)**
- **Issue**: Sequential processing of context data in `build_enhanced_kb_context()`
- **Location**: Lines 1545-1605
- **Impact**: Multiple iterations over data structures

### 4. **No Response Caching**
- **Issue**: No caching for repeated queries
- **Impact**: Same queries take full processing time every time

### 5. **Synchronous Operations**
- **Issue**: Many operations that could run in parallel are executed sequentially
- **Impact**: Cumulative delay of all operations

## Optimization Recommendations

### 1. **Parallelize Database Operations** (Save: 8-10 seconds)
```python
# Instead of sequential calls:
agent_context = await get_agent_context_from_kb(...)
client_context = await get_optimized_client_context(...)
agent_knowledge = await get_optimized_agent_knowledge(...)

# Use asyncio.gather for parallel execution:
agent_context, client_context, agent_knowledge = await asyncio.gather(
    get_agent_context_from_kb(request.agent),
    get_optimized_client_context(request.user_id, query_embedding),
    get_optimized_agent_knowledge(request.agent, query_embedding)
)
```

### 2. **Pre-warm Embedding Model** (Save: 2-5 seconds on cold starts)
```python
# Initialize model at startup, not on first request
# In main.py startup:
embedding_service = get_embedding_service()
_ = embedding_service.get_embedding("warmup")  # Pre-load model
```

### 3. **Implement Response Caching** (Save: 15-20 seconds for repeated queries)
```python
# Add Redis or in-memory caching for:
- Query embeddings (cache for 1 hour)
- Agent contexts (cache for 10 minutes)
- Client contexts (cache for 5 minutes)
- Complete responses for identical queries (cache for 2 minutes)
```

### 4. **Optimize Database Queries**
- Create composite indexes on frequently queried columns
- Consider materialized views for complex aggregations
- Batch similar queries together

### 5. **Add Request-Level Caching**
```python
# Cache within request lifecycle to avoid duplicate operations
request_cache = {}
cache_key = f"{user_id}:{agent}:{query_hash}"
if cache_key in request_cache:
    return request_cache[cache_key]
```

### 6. **Profile and Monitor**
- Add detailed timing logs for each operation
- Use APM tools to identify slow queries
- Monitor database query performance

## Quick Wins (Implement First)

1. **Parallelize the three main database calls** - This alone could save 8-10 seconds
2. **Pre-warm the embedding model** - Saves 2-5 seconds on cold starts
3. **Add simple in-memory caching** for repeated queries within a short timeframe

## Database Optimization Suggestions

1. **Review RPC functions** `get_client_context_similarity` and `get_agent_knowledge_smart`
   - Ensure they have proper indexes
   - Consider limiting the amount of data returned
   - Add query execution plans

2. **Connection Pooling**
   - Ensure Supabase client is using connection pooling
   - Avoid creating new connections per request

## Monitoring Implementation
Add timing logs:
```python
import time
from functools import wraps

def log_timing(operation_name):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"{operation_name} took {duration:.2f}s")
            return result
        return wrapper
    return decorator

# Apply to each major operation
@log_timing("embedding_generation")
async def get_query_embedding(...):
    ...
```

## Expected Performance After Optimization
- Current: 20+ seconds
- After parallelization: 12-15 seconds
- With caching: 2-5 seconds for cached queries
- With all optimizations: 8-10 seconds for new queries, <2 seconds for cached