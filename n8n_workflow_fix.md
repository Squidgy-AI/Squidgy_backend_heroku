# N8N Workflow Fix for Website URL Detection

## Problem
The "Check Client KB for Website Info" node doesn't pass the user's current message, so the backend can't detect URLs in real-time.

## Solution
Update the "Check Client KB for Website Info" node (lines 95-120 in SA___Main_Presales_pin.json):

### Current Configuration:
```json
{
  "name": "Check Client KB for Website Info",
  "parameters": {
    "method": "POST",
    "url": "https://squidgy-back-919bc0659e35.herokuapp.com/n8n/check_client_kb",
    "sendBody": true,
    "bodyParameters": {
      "parameters": [
        {
          "name": "user_id",
          "value": "={{ $('When Executed by Parent Workflow').item.json.body.user_id }}"
        },
        {
          "name": "agent_name",
          "value": "={{ $json.agent_name }}"
        }
      ]
    }
  }
}
```

### Updated Configuration:
```json
{
  "name": "Check Client KB for Website Info", 
  "parameters": {
    "method": "POST",
    "url": "https://squidgy-back-919bc0659e35.herokuapp.com/n8n/check_client_kb",
    "sendBody": true,
    "bodyParameters": {
      "parameters": [
        {
          "name": "user_id",
          "value": "={{ $('When Executed by Parent Workflow').item.json.body.user_id }}"
        },
        {
          "name": "agent_name", 
          "value": "={{ $json.agent_name }}"
        },
        {
          "name": "user_mssg",
          "value": "={{ $('When Executed by Parent Workflow').item.json.body.user_mssg }}"
        }
      ]
    }
  }
}
```

## Instructions:
1. Open the N8N workflow "SA | Main Presales.json"
2. Click on the "Check Client KB for Website Info" node
3. In the body parameters section, add the third parameter:
   - Name: `user_mssg`
   - Value: `={{ $('When Executed by Parent Workflow').item.json.body.user_mssg }}`
4. Save the workflow

## How It Works:
1. User sends message: "Analyze my website https://example.com"
2. Backend receives the message in the check_client_kb endpoint
3. extract_website_urls() function detects "https://example.com"
4. Returns has_website_info=True with the detected URL
5. Workflow proceeds to Agent Main Search instead of asking for website URL
6. Website analysis tools can now be used with the detected URL

## Benefits:
- ✅ Instant URL detection from user messages
- ✅ No need to ask users twice for their website
- ✅ Seamless flow from message to analysis
- ✅ Maintains backward compatibility with stored KB data