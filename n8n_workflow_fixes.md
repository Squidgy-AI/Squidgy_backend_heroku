# 🔧 n8n Workflow Fix Guide

## Issues Found in Your Workflows

### 1. **Main Workflow (`SA___Main_Workflow.json`)**
- ✅ Has "Respond to Webhook" node (line 228)
- ✅ Workflow connections are properly configured
- ❌ **CRITICAL**: "Respond to Webhook" node is **NOT DISABLED** - this is good!
- ❌ **ISSUE**: Backend URLs point to old Heroku instance

### 2. **Presales Workflow (`SA___Main_Presales_json.json`)**
- ✅ Has "Respond to Webhook" node (line 235)
- ❌ **CRITICAL**: "Respond to Webhook" node is **DISABLED** (line 237)
- ❌ **ISSUE**: Backend URLs point to old Heroku instance
- ❌ **ISSUE**: Multiple other nodes are disabled

## 🚨 **ROOT CAUSE**: Disabled "Respond to Webhook" Node

The presales workflow has its "Respond to Webhook" node disabled, so it processes everything but never returns a response to your backend.

## 🛠️ **FIXES NEEDED**

### Fix 1: Enable "Respond to Webhook" Node in Presales Workflow
```
In n8n Editor:
1. Open "SA | Main Presales.json" workflow
2. Find the "Respond to Webhook" node (should be grayed out)
3. Right-click → "Enable" or click the disable toggle
4. Make sure it's connected to "AI Agent" node
```

### Fix 2: Update All Backend URLs
**Change ALL instances of:**
```
FROM: https://squidgy-back-919bc0659e35.herokuapp.com
TO:   http://localhost:8000
```

**OR use the local test webhook that already points to localhost:8000:**
```
Local Test Webhook: https://n8n.theaiteam.uk/webhook/1fc715f3-4415-4f7b-8f28-50630605df9d
Environment Variable: N8N_LOCAL_TEST (already added to .env)
Backend Base URL: BACKEND_BASE_URL=http://localhost:8000
```

**Nodes to update in Presales Workflow:**
- Line 63: "Check Agent Match" → `/n8n/check_agent_match`
- Line 95: "Check Client KB for Website Info" → `/api/client/check_kb`
- Line 154: "Finding Best Agent" → `/n8n/find_best_agents`
- Line 178: "Agent Main Search" → `/api/agent/query`
- Line 267: "Website Analysis Tool" → `/api/website/full-analysis`
- Line 341: "Website Screenshot" → `/api/website/screenshot`
- Line 364: "Website Favicon" → `/api/website/favicon`

**Nodes to update in Main Workflow:**
- Line 24: "Send Acknowledgment" → `/api/stream`
- Line 91: "Send Final Status" → `/api/stream`

### Fix 3: Enable Other Disabled Nodes in Presales Workflow
**Nodes that should be ENABLED:**
- "When chat message received" (line 19: disabled)
- "Webhook" (line 58: disabled)
- "Website Analysis Tool" (line 293: disabled)

## 🧪 **Testing After Fixes**

Run this test to verify the fix:
```bash
python test_n8n_workflow_fix.py
```

Expected result after fixes:
```json
{
  "user_id": "test_user_123",
  "session_id": "test_session",
  "agent_name": "presaleskb",
  "timestamp_of_call_made": "2025-06-20T...",
  "request_id": "req_1749924095849",
  "agent_response": "Hello! I'm the presales assistant..."
}
```

## 📋 **Quick Fix Checklist**

- [ ] Enable "Respond to Webhook" node in Presales workflow
- [ ] Update all Heroku URLs to localhost:8000
- [ ] Enable disabled nodes in Presales workflow
- [ ] Test with `python test_n8n_workflow_fix.py`
- [ ] Test full UI → Backend → n8n flow

## 🎯 **Why This Will Fix Everything**

1. **Main Issue**: Presales workflow processes but never responds
2. **Secondary Issue**: Old URLs prevent backend communication
3. **After Fix**: n8n will return proper JSON responses
4. **Result**: Your UI → WebSocket → Backend → n8n → Response flow will work

The "Respond to Webhook" node being disabled is why you see HTTP 200 with empty responses. Once enabled, n8n will return the AI agent's response in proper JSON format.