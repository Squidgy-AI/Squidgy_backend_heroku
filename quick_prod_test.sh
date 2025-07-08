#!/bin/bash

echo "🚀 QUICK PRODUCTION TEST - Facebook Integration"
echo "=============================================="

# Test 1: Health Check
echo "📡 Test 1: Health Check"
curl -s https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/oauth-health | jq '.'

echo -e "\n📡 Test 2: Integration Endpoint"
curl -X POST https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integrate \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "test_location_prod",
    "user_id": "test_user_prod",
    "email": "test@example.com",
    "password": "test123",
    "firm_user_id": "test_firm_user"
  }' | jq '.'

echo -e "\n📡 Test 3: Status Check"
sleep 3
curl -s https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integration-status/test_location_prod | jq '.'

echo -e "\n📡 Test 4: Connect Page"
curl -X POST https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/connect-page \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "test_location_prod",
    "page_id": "test_page_123"
  }' | jq '.'

echo -e "\n✅ Production tests complete!"
echo "📋 Next: Test the full flow in your frontend at your Vercel URL"