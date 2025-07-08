# 🚀 PRODUCTION TESTING GUIDE - Facebook Integration

## 📋 **Pre-Deployment Checklist**

### **1. Environment Variables (Heroku)**
```bash
# Set these in Heroku dashboard or CLI
heroku config:set DYNO=true
heroku config:set FACEBOOK_2FA_EMAIL=squidgy.2fa.monitor@gmail.com
heroku config:set FACEBOOK_2FA_PASSWORD=your-app-specific-password
heroku config:set SUPABASE_URL=https://your-project.supabase.co
heroku config:set SUPABASE_ANON_KEY=your-anon-key
```

### **2. Frontend Environment Variables (Vercel)**
```bash
# Set these in Vercel dashboard
NEXT_PUBLIC_API_BASE=https://squidgy-back-919bc0659e35.herokuapp.com
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## 🧪 **Testing Flow - Step by Step**

### **Step 1: Complete Setup Flow**
1. Go to your Vercel frontend URL
2. Start the SOL Agent setup
3. Complete Solar, Calendar, Notifications steps
4. **IMPORTANT**: Complete GHL Setup - this provides the credentials for Facebook integration

### **Step 2: Test Facebook Integration**
1. Click "Connect Facebook Account" 
2. **In Production**: System will use direct API approach (no browser automation)
3. Watch for these status updates:
   - "Processing Facebook Integration..."
   - "Connecting to GoHighLevel API"
   - "Authenticating with Facebook"
   - "Retrieving your Facebook pages"

### **Step 3: Expected Responses**

**Success Response:**
```json
{
  "status": "success",
  "pages": [
    {
      "facebookPageId": "123456789",
      "facebookPageName": "Your Solar Company",
      "facebookIgnoreMessages": false,
      "isInstagramAvailable": true
    }
  ],
  "approach": "direct_api"
}
```

**OAuth Required Response:**
```json
{
  "status": "oauth_required",
  "oauth_url": "https://facebook.com/v18.0/dialog/oauth?...",
  "message": "Please complete OAuth manually",
  "approach": "manual_oauth"
}
```

## 🔧 **Manual Testing Commands**

### **Test 1: Health Check**
```bash
curl https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/oauth-health
```

**Expected Response:**
```json
{
  "service": "facebook_oauth",
  "status": "healthy",
  "endpoints": [
    "/api/facebook/extract-oauth-params",
    "/api/facebook/integrate",
    "/api/facebook/integration-status/{location_id}",
    "/api/facebook/connect-page"
  ]
}
```

### **Test 2: Integration Endpoint**
```bash
curl -X POST https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integrate \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "GJSb0aPcrBRne73LK3A3",
    "user_id": "utSop6RQjsF2Mwjnr8Gg",
    "email": "ovi.chand@gmail.com",
    "password": "Dummy@123",
    "firm_user_id": "your-supabase-user-id"
  }'
```

### **Test 3: Status Check**
```bash
curl https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integration-status/GJSb0aPcrBRne73LK3A3
```

### **Test 4: Page Connection**
```bash
curl -X POST https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/connect-page \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "GJSb0aPcrBRne73LK3A3",
    "page_id": "test-page-id"
  }'
```

## 📱 **Frontend Testing Flow**

### **Complete User Journey:**

1. **Start Setup**: Navigate to your Vercel app
2. **Complete Previous Steps**: 
   - Solar config ✅
   - Calendar setup ✅ 
   - Notifications ✅
   - GHL Account creation ✅
3. **Facebook Integration**:
   - Click "Connect Facebook Account"
   - System shows processing status
   - Either shows pages selection OR OAuth URL
4. **Select Pages**: Choose which Facebook pages to connect
5. **Complete**: Integration saved to database

### **What to Watch For:**

**Success Indicators:**
- ✅ All API calls return 200 status
- ✅ Facebook pages are displayed
- ✅ User can select pages
- ✅ Data is saved to Supabase
- ✅ Setup progresses to completion

**Error Indicators:**
- ❌ 500 errors in network tab
- ❌ "Failed to start automation" message
- ❌ Timeout errors
- ❌ Database save errors

## 🔍 **Debugging in Production**

### **Check Heroku Logs:**
```bash
heroku logs --tail --app squidgy-back-919bc0659e35
```

### **Common Issues & Solutions:**

**Issue 1: "Failed to start automation"**
```bash
# Check if environment variables are set
heroku config --app squidgy-back-919bc0659e35

# Should show DYNO=true
```

**Issue 2: "JWT token extraction failed"**
```bash
# This is expected in production
# System should fall back to OAuth URL generation
```

**Issue 3: "Database connection failed"**
```bash
# Check Supabase credentials
heroku config:get SUPABASE_URL --app squidgy-back-919bc0659e35
```

## 📊 **Expected Production Behavior**

### **Different from Development:**
- **No Browser Window**: System uses direct API calls
- **OAuth URL**: User may need to complete OAuth manually
- **Faster Response**: Direct API calls are quicker than browser automation
- **More Reliable**: No browser crashes or timeouts

### **Production Flow Diagram:**
```
User Click → Frontend → Backend → GHL API → Facebook API → Database → Response
     ↓           ↓         ↓         ↓           ↓           ↓         ↓
  "Connect"   POST req   Direct    Get JWT    Get Pages   Store    Show Pages
```

## 🎯 **Success Criteria**

### **Test is Successful If:**
1. ✅ Health endpoint returns 200
2. ✅ Integration endpoint starts processing
3. ✅ Status endpoint shows progress
4. ✅ Facebook pages are retrieved (or OAuth URL provided)
5. ✅ User can select pages
6. ✅ Data is saved to database
7. ✅ No 500 errors in logs

### **Test is Failed If:**
1. ❌ Health endpoint returns errors
2. ❌ Integration endpoint returns 500
3. ❌ Browser automation attempts in production
4. ❌ Database save fails
5. ❌ Frontend shows error messages

## 🚀 **Quick Test Script**

Create this test file and run it:

```bash
# Save as test_prod.sh
#!/bin/bash
echo "🧪 Testing Facebook Integration in Production"
echo "=============================================="

echo "Test 1: Health Check"
curl -s https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/oauth-health | jq '.'

echo -e "\nTest 2: Integration Start"
curl -X POST https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integrate \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "test_location",
    "user_id": "test_user",
    "email": "test@example.com",
    "password": "test",
    "firm_user_id": "test_firm"
  }' | jq '.'

echo -e "\nTest 3: Status Check"
sleep 2
curl -s https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integration-status/test_location | jq '.'

echo -e "\n✅ Tests Complete!"
```

## 📞 **Support & Debugging**

### **If Tests Fail:**
1. Check Heroku logs: `heroku logs --tail`
2. Verify environment variables are set
3. Test individual endpoints with curl
4. Check database connections
5. Verify GHL credentials are working

### **Key Debug Points:**
- Environment detection: `DYNO` variable
- API responses: Check status codes
- Database operations: Supabase logs
- Integration status: Check in-memory storage

Ready to push and test! 🚀