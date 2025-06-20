# 🔗 Backend URLs for n8n Configuration

## The Issue
n8n is getting `ECONNREFUSED ::1:8000` when trying to connect to your backend.

## Solution: Use These URLs in n8n

Replace ALL backend URLs in your n8n workflow with:

### **Option 1: IPv4 Address (Recommended)**
```
http://127.0.0.1:8000
```

### **Option 2: Host Machine (if n8n is in Docker)**
```
http://host.docker.internal:8000
```

## Complete URL List for n8n

Copy these exact URLs into your n8n HTTP Request nodes:

### **Presales Workflow URLs:**
```
http://127.0.0.1:8000/n8n/check_agent_match
http://127.0.0.1:8000/api/client/check_kb
http://127.0.0.1:8000/n8n/find_best_agents
http://127.0.0.1:8000/api/agent/query
http://127.0.0.1:8000/api/website/full-analysis
http://127.0.0.1:8000/api/website/screenshot
http://127.0.0.1:8000/api/website/favicon
```

### **Main Workflow URLs:**
```
http://127.0.0.1:8000/api/stream
```

## Current Working Status ✅

Your backend is responding correctly:
- ✅ http://localhost:8000/n8n/check_agent_match - Working
- ✅ http://127.0.0.1:8000/n8n/check_agent_match - Working  
- ✅ http://0.0.0.0:8000/n8n/check_agent_match - Working

## Why This Happens

The error `ECONNREFUSED ::1:8000` suggests n8n is trying IPv6 localhost (`::1`) but your backend might prefer IPv4 (`127.0.0.1`).

## Quick Fix Steps

1. **Go to your n8n workflow**
2. **Find all HTTP Request nodes**
3. **Replace URLs with `http://127.0.0.1:8000/...`**
4. **Save and test**

## Test After Update

The n8n request should succeed and return:
```json
{
  "agent_name": "presaleskb",
  "user_query": "Hi this is Soma...",
  "is_match": true,
  "status": "success"
}
```