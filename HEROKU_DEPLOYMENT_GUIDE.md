# 🚀 HEROKU DEPLOYMENT GUIDE FOR FACEBOOK INTEGRATION

## ⚠️ **Critical Issues & Solutions**

### **1. Playwright on Heroku**

**THE PROBLEM:**
- Playwright browser automation **DOES NOT WORK** on standard Heroku dynos
- Heroku dynos have no GUI, limited memory, and 30-second timeouts
- Browser automation requires persistent display servers

**THE SOLUTION:**
We've implemented a **hybrid approach** that:
- Uses browser automation in **local development** 
- Falls back to **direct API calls** in **production (Heroku)**

### **2. Deployment Architecture**

```
Development:  Frontend → Backend → Playwright Browser Automation
Production:   Frontend → Backend → Direct GHL API Calls
```

## 📋 **Heroku Deployment Steps**

### **Step 1: Set up Heroku Buildpacks**

```bash
# Add buildpacks to your Heroku app
heroku buildpacks:add heroku/python
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-apt
heroku buildpacks:add https://github.com/mxschmitt/heroku-buildpack-playwright
```

### **Step 2: Environment Variables**

```bash
# Set environment variables
heroku config:set DYNO=true
heroku config:set FACEBOOK_2FA_EMAIL=squidgy.2fa.monitor@gmail.com
heroku config:set FACEBOOK_2FA_PASSWORD=your-app-specific-password
heroku config:set SUPABASE_URL=your-supabase-url
heroku config:set SUPABASE_KEY=your-supabase-key
```

### **Step 3: Required Files**

Make sure these files exist in your backend:

**`Aptfile`** (for system dependencies):
```
chromium-browser
chromium-chromedriver
xvfb
```

**`requirements.txt`** (add these lines):
```
playwright==1.40.0
psutil==5.9.6
pyee==11.0.1
```

**`Procfile`** (create if doesn't exist):
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### **Step 4: Code Changes for Production**

The backend automatically detects Heroku and switches approaches:

```python
# In main.py
is_heroku = os.environ.get('DYNO') is not None

if is_heroku:
    # Use direct API calls (no browser automation)
    from facebook_integration_alternative import integrate_facebook_production
    result = await integrate_facebook_production(request)
else:
    # Use browser automation (local development)
    from facebook_integration_service import FacebookIntegrationService
    result = await service.integrate_facebook(fb_request)
```

## 🔄 **How It Works in Production**

### **Local Development:**
1. User clicks "Connect Facebook Account"
2. Backend launches visible browser
3. Automates login with 2FA handling
4. Extracts Facebook pages
5. User selects pages to connect

### **Production (Heroku):**
1. User clicks "Connect Facebook Account"
2. Backend generates OAuth URL
3. User completes OAuth manually
4. Backend uses JWT token for direct API calls
5. Extracts Facebook pages via GHL API
6. User selects pages to connect

## 🛠️ **Alternative Production Flows**

### **Option A: Manual OAuth (Recommended)**
```typescript
// Frontend shows OAuth URL for manual completion
if (status.status === 'oauth_required') {
  window.open(status.oauth_url, '_blank');
  // User completes OAuth manually
  // Backend gets JWT token from GHL
  // Continues with page extraction
}
```

### **Option B: Pre-extracted JWT**
```typescript
// Frontend passes JWT token from GHL setup
const response = await fetch('/api/facebook/integrate', {
  body: JSON.stringify({
    ...request,
    jwt_token: ghlSetup.jwt_token // From previous step
  })
});
```

### **Option C: Third-party Service**
```typescript
// Use external service like Browserless or Puppeteer Cluster
const browserlessUrl = 'https://chrome.browserless.io';
// Send automation requests to external service
```

## 📝 **Deployment Checklist**

### **Backend (Heroku):**
- [ ] Add all required buildpacks
- [ ] Set environment variables
- [ ] Create Aptfile with system dependencies
- [ ] Update requirements.txt
- [ ] Test with `heroku local web`
- [ ] Deploy: `git push heroku main`

### **Frontend (Vercel):**
- [ ] Set environment variables:
  ```bash
  NEXT_PUBLIC_API_BASE=https://your-app.herokuapp.com
  NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
  NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-key
  ```
- [ ] Test build: `npm run build`
- [ ] Deploy: `vercel --prod`

## 🚨 **Common Issues & Solutions**

### **Issue 1: Browser Won't Launch**
```bash
# Check logs
heroku logs --tail

# Common error: "Browser executable not found"
# Solution: Ensure buildpacks are added in correct order
```

### **Issue 2: Memory Errors**
```bash
# Upgrade dyno type
heroku ps:scale web=1:standard-1x
```

### **Issue 3: Timeout Errors**
```bash
# Increase timeout (max 30s on Heroku)
# Or use background jobs with Redis
heroku addons:create heroku-redis:mini
```

## 📊 **Performance Considerations**

### **Local Development:**
- Browser automation: ~10-30 seconds
- Memory usage: ~200-500MB
- CPU usage: High during automation

### **Production (Heroku):**
- Direct API calls: ~2-5 seconds
- Memory usage: ~50-100MB
- CPU usage: Low

## 🔐 **Security Considerations**

### **Credentials Storage:**
```bash
# Store sensitive data as environment variables
heroku config:set GHL_OAUTH_TOKEN=your-token
heroku config:set FACEBOOK_APP_SECRET=your-secret
```

### **CORS Configuration:**
```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-frontend.vercel.app",
        "http://localhost:3000"  # Remove in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🧪 **Testing Production Deployment**

### **Test Script:**
```bash
# Test health endpoint
curl https://your-app.herokuapp.com/api/facebook/oauth-health

# Test integration endpoint
curl -X POST https://your-app.herokuapp.com/api/facebook/integrate \
  -H "Content-Type: application/json" \
  -d '{"location_id": "test", "user_id": "test"}'
```

### **Frontend Testing:**
```bash
# Test production build locally
npm run build
npm run start

# Test with production API
NEXT_PUBLIC_API_BASE=https://your-app.herokuapp.com npm run dev
```

## 🔄 **Migration Strategy**

### **Phase 1: Hybrid Deployment**
- Deploy both approaches
- Use browser automation for development
- Use direct API for production

### **Phase 2: Full Migration**
- Once stable, remove browser automation
- Use only direct API approach
- Simplify deployment process

## 📈 **Monitoring & Logging**

### **Add Logging:**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In integration function
logger.info(f"Starting Facebook integration for {location_id}")
```

### **Monitor Performance:**
```bash
# Check dyno usage
heroku ps

# Check logs
heroku logs --tail --app your-app-name
```

## 🎯 **Conclusion**

**YES, the deployment will work on Heroku** with our hybrid approach:

1. **Frontend on Vercel**: ✅ No issues
2. **Backend on Heroku**: ✅ Works with direct API calls
3. **Browser Automation**: ⚠️ Only works locally, alternatives for production
4. **Facebook Integration**: ✅ Works in both environments

The key is that we've built **two approaches** that automatically switch based on the environment, ensuring seamless operation in both development and production.