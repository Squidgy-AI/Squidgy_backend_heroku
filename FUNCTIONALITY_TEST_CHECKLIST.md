# ✅ FUNCTIONALITY TEST CHECKLIST - Facebook Integration

## 🚀 **Quick Backend Health Check**

### **Test 1: Verify Backend is Running**
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
  ],
  "timestamp": "2025-01-08T..."
}
```

### **Test 2: Environment Detection**
```bash
curl -X POST https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integrate \
  -H "Content-Type: application/json" \
  -d '{"location_id": "test", "user_id": "test", "email": "test", "password": "test", "firm_user_id": "test"}'
```

**Expected Response:**
```json
{
  "status": "processing",
  "message": "Facebook integration started. Browser automation in progress...",
  "location_id": "test"
}
```

---

## 🎯 **Full Frontend Testing**

### **Step 1: Access Your Frontend**
Go to your **Vercel deployment URL** (e.g., https://your-app.vercel.app)

### **Step 2: Start SOL Agent Setup**
1. Look for "SOL Agent" or "Solar Sales Specialist" 
2. Click to start the setup process
3. You should see a **5-step progress indicator**

### **Step 3: Complete Prerequisites (CRITICAL)**
You **MUST** complete these steps in order:

#### **Step 1: Solar Configuration** ✅
- Fill in solar business details
- Click "Complete Solar Setup"
- Wait for confirmation

#### **Step 2: Calendar Setup** ✅  
- Configure business hours
- Set appointment settings
- Click "Complete Calendar Setup"

#### **Step 3: Notifications Setup** ✅
- Configure notification preferences
- Click "Complete Notifications Setup"

#### **Step 4: GHL Account Setup** ✅ **CRITICAL**
- Click "Create GoHighLevel Account" OR "Use Existing Credentials"
- **This provides the login credentials for Facebook integration**
- Wait for completion message
- Should show: Location ID, User details, Email

### **Step 4: Facebook Integration Test** 🎯

#### **What You Should See:**
- Progress indicator showing "Step 5 of 5"
- Facebook integration component loads
- Blue Facebook icon and "Connect Facebook Account" button

#### **Click "Connect Facebook Account"**
- Button changes to "Starting Automation..." 
- Processing message appears
- Progress updates show

#### **Expected Production Behavior:**
```
✅ Processing Facebook Integration...
• Connecting to GoHighLevel API
• Authenticating with Facebook
• Retrieving your Facebook pages
• Processing integration data
```

#### **Two Possible Outcomes:**

**Outcome A: Success with Pages**
- List of Facebook pages appears
- Checkboxes to select pages
- "Connect X Selected Pages" button
- User can complete integration

**Outcome B: OAuth Required**
- OAuth URL is provided
- User needs to complete OAuth manually
- System waits for JWT token

---

## 🔍 **What to Check in Browser**

### **Open Developer Tools (F12)**

#### **Network Tab:**
Watch for these API calls:
```
POST /api/facebook/integrate          → 200 OK
GET  /api/facebook/integration-status → 200 OK
POST /api/facebook/connect-page       → 200 OK (if pages selected)
```

#### **Console Tab:**
Look for:
- ✅ No red errors
- ✅ Status update logs
- ✅ API response logs

#### **Common Success Indicators:**
```javascript
// In console
✅ Facebook Setup - Primary key validation passed
✅ Integration started successfully
✅ Pages found: [array of pages]
✅ Configuration saved successfully
```

#### **Common Error Indicators:**
```javascript
// In console
❌ Failed to start automation
❌ CORS error
❌ 500 Internal Server Error
❌ Database connection failed
```

---

## 📱 **Mobile Testing**

### **Test on Mobile Device:**
1. Open your Vercel URL on mobile
2. Complete the same flow
3. Verify responsive design works
4. Check touch interactions

---

## 🧪 **Advanced Testing**

### **Test Different Scenarios:**

#### **Test 1: Skip Previous Steps**
- Try to access Facebook integration directly
- Should show appropriate error or redirect

#### **Test 2: Refresh During Process**
- Start Facebook integration
- Refresh page mid-process
- Should maintain state or restart gracefully

#### **Test 3: Network Interruption**
- Start integration
- Disconnect internet briefly
- Reconnect and see if it recovers

---

## 📊 **Performance Testing**

### **Check Load Times:**
- Initial page load: < 3 seconds
- API responses: < 5 seconds
- Database saves: < 2 seconds

### **Monitor Resource Usage:**
- CPU usage reasonable
- Memory usage stable
- No memory leaks

---

## 🚨 **Error Scenarios to Test**

### **Test 1: Invalid Credentials**
- Use wrong GHL credentials
- Should show appropriate error message

### **Test 2: Network Timeout**
- Simulate slow network
- Should show loading states properly

### **Test 3: Database Errors**
- Check with invalid user_id
- Should handle gracefully

---

## 📋 **Success Checklist**

### **✅ Backend Tests Pass:**
- [ ] Health endpoint returns 200
- [ ] Integration endpoint processes requests
- [ ] Status endpoint shows progress
- [ ] No 500 errors in logs

### **✅ Frontend Tests Pass:**
- [ ] Setup flow completes all 5 steps
- [ ] Facebook integration loads correctly
- [ ] User can click "Connect Facebook Account"
- [ ] Processing status shows
- [ ] Either pages appear OR OAuth URL provided
- [ ] No console errors

### **✅ Integration Tests Pass:**
- [ ] Data saves to database
- [ ] User can select pages (if available)
- [ ] Setup completes successfully
- [ ] Final confirmation shows

---

## 🔧 **Debugging Commands**

### **Check Backend Logs:**
```bash
heroku logs --tail --app squidgy-back-919bc0659e35
```

### **Test Individual Endpoints:**
```bash
# Test health
curl https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/oauth-health

# Test integration
curl -X POST https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integrate \
  -H "Content-Type: application/json" \
  -d '{"location_id": "test", "user_id": "test"}'

# Test status
curl https://squidgy-back-919bc0659e35.herokuapp.com/api/facebook/integration-status/test
```

### **Check Environment Variables:**
```bash
heroku config --app squidgy-back-919bc0659e35
```

---

## 🎯 **What Success Looks Like**

### **Complete Success:**
1. User completes all 5 setup steps
2. Facebook integration processes without errors
3. Facebook pages are displayed
4. User can select pages to connect
5. Integration completes and saves to database
6. Setup shows "Complete" status

### **Partial Success:**
1. Integration starts and processes
2. OAuth URL is provided for manual completion
3. User can complete OAuth separately
4. System continues with direct API approach

### **Failure:**
1. Health check fails
2. Integration endpoint returns 500
3. Frontend shows error messages
4. Console shows API errors

---

## 📞 **Next Steps After Testing**

1. **Run the quick backend test** first
2. **Test the complete frontend flow**
3. **Check browser console for errors**
4. **Report results**: What worked, what didn't, any error messages
5. **If issues found**: Provide specific error messages and steps to reproduce

**Ready to test? Start with the backend health check, then test the full frontend flow!** 🚀