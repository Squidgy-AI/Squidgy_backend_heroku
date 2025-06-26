# Enhanced n8n Context Integration Guide

## Overview
The backend now sends rich conversation context to n8n workflows, solving the critical memory issue where agents would forget previous conversation details.

## Enhanced Payload Structure

The n8n workflow now receives this enhanced payload:

```json
{
  "user_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e",
  "user_mssg": "please go ahead",
  "session_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e_presaleskb",
  "agent_name": "presaleskb",
  "timestamp_of_call_made": "2025-06-24T01:45:00.000Z",
  "request_id": "req_1750728639828",
  "_original_message": "please go ahead",
  
  // NEW: Full conversation context
  "conversation_history": [
    {
      "sender": "User",
      "message": "I need you to analyze https://auction.com",
      "timestamp": "2025-06-24T01:44:30.000Z"
    },
    {
      "sender": "Agent", 
      "message": "I'll analyze your website to provide insights...",
      "timestamp": "2025-06-24T01:44:32.000Z"
    },
    {
      "sender": "User",
      "message": "please go ahead",
      "timestamp": "2025-06-24T01:44:36.000Z"
    }
  ],
  
  // NEW: Website analysis data
  "website_data": [
    {
      "url": "https://auction.com",
      "analysis": "{\"company_name\": \"Auction.com\", \"description\": \"...\"}", 
      "created_at": "2025-06-24T01:44:32.000Z"
    }
  ],
  
  // NEW: Client knowledge base
  "client_knowledge_base": {
    "business_info": {...},
    "preferences": {...},
    "industry_context": {...}
  },
  
  // NEW: Intelligent context insights
  "context_insights": {
    "mentioned_urls": ["https://auction.com"],
    "user_requests": ["I need you to analyze https://auction.com"],
    "agent_commitments": ["I'll analyze your website to provide insights..."],
    "user_confirmations": ["please go ahead"],
    "pending_actions": ["User has confirmed to proceed with agent analysis"],
    "analyzed_websites": ["https://auction.com"]
  },
  
  // NEW: Context summary
  "context_summary": {
    "total_messages": 3,
    "websites_analyzed": 1,
    "kb_entries": 2,
    "extracted_insights": 5
  }
}
```

## How to Use Enhanced Context in n8n Workflows

### 1. **Access Conversation History**
```javascript
// Get the last few messages for context
const recentMessages = $json.conversation_history.slice(-5);
const lastUserMessage = recentMessages.filter(m => m.sender === 'User').pop();
const lastAgentMessage = recentMessages.filter(m => m.sender === 'Agent').pop();
```

### 2. **Check for Mentioned URLs**
```javascript
// Check if URLs were mentioned in conversation
const mentionedUrls = $json.context_insights.mentioned_urls;
if (mentionedUrls.length > 0) {
  const urlToAnalyze = mentionedUrls[0]; // Use the first mentioned URL
  return {
    action: 'analyze_website',
    url: urlToAnalyze,
    context: 'URL was previously mentioned in conversation'
  };
}
```

### 3. **Detect User Confirmations**
```javascript
// Check if user has confirmed to proceed
const userConfirmations = $json.context_insights.user_confirmations;
const pendingActions = $json.context_insights.pending_actions;

if (userConfirmations.length > 0 && pendingActions.length > 0) {
  return {
    action: 'proceed_with_analysis',
    message: 'I understand you want me to proceed. Let me analyze the website we discussed.'
  };
}
```

### 4. **Use Website Analysis Data**
```javascript
// Check if website has already been analyzed
const websiteData = $json.website_data;
if (websiteData.length > 0) {
  const analysis = JSON.parse(websiteData[0].analysis);
  return {
    action: 'provide_insights',
    company: analysis.company_name,
    analysis: analysis
  };
}
```

### 5. **Build Contextual Responses**
```javascript
// Example workflow logic for the specific issue
const currentMessage = $json.user_mssg.toLowerCase();
const mentionedUrls = $json.context_insights.mentioned_urls;
const userConfirmations = $json.context_insights.user_confirmations;
const agentCommitments = $json.context_insights.agent_commitments;

// If user says "go ahead" and we previously committed to analyze a URL
if ((currentMessage.includes('go ahead') || currentMessage.includes('proceed')) 
    && mentionedUrls.length > 0 
    && agentCommitments.length > 0) {
  
  const urlToAnalyze = mentionedUrls[0];
  return {
    action: 'analyze_website_now',
    url: urlToAnalyze,
    response: `Perfect! I'll now analyze ${urlToAnalyze} as discussed. Let me provide you with detailed insights about your website...`
  };
}
```

## Critical Fix for the Reported Issue

The specific issue where the agent forgot about https://auction.com can be solved with this n8n workflow logic:

```javascript
// Smart context-aware response logic
const currentMsg = $json.user_mssg.toLowerCase();
const insights = $json.context_insights;

// Case 1: User confirms to proceed with previously mentioned analysis
if ((currentMsg.includes('go ahead') || currentMsg.includes('proceed') || currentMsg.includes('continue'))
    && insights.mentioned_urls.length > 0
    && insights.pending_actions.length > 0) {
  
  const websiteUrl = insights.mentioned_urls[0];
  
  // Check if we already have analysis for this website
  const existingAnalysis = $json.website_data.find(w => w.url === websiteUrl);
  
  if (existingAnalysis) {
    const analysis = JSON.parse(existingAnalysis.analysis);
    return {
      agent_response: `Great! I've already analyzed ${websiteUrl}. Here are the key insights: ${analysis.description}. Based on this analysis, I recommend...`,
      action: 'provide_detailed_insights'
    };
  } else {
    return {
      agent_response: `Perfect! I'll now analyze ${websiteUrl} as we discussed earlier. Please give me a moment to gather comprehensive insights about your website.`,
      action: 'analyze_website',
      url: websiteUrl
    };
  }
}

// Case 2: No context available - ask for clarification
return {
  agent_response: "I'd be happy to help you! Could you please provide more details about what you'd like me to analyze or assist you with?",
  action: 'request_clarification'
};
```

## Benefits of Enhanced Context

1. **Memory Continuity**: Agents remember previous conversation details
2. **Smart URL Detection**: Automatically extracts and remembers mentioned URLs  
3. **Confirmation Handling**: Detects user confirmations and proceeds appropriately
4. **Website Analysis Integration**: Leverages existing website analysis data
5. **Contextual Responses**: Provides relevant responses based on conversation flow
6. **Reduced Redundancy**: Avoids asking for information already provided

## Implementation Priority

**HIGH PRIORITY**: Update the main n8n workflow to use `context_insights.mentioned_urls` and `context_insights.user_confirmations` to solve the immediate memory issue.

**MEDIUM PRIORITY**: Enhance workflows to use full conversation history for more sophisticated context awareness.

**LOW PRIORITY**: Implement advanced client knowledge base integration for personalized responses.