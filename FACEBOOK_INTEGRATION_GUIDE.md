# 🚀 Facebook Integration with Browser Automation

## Overview

This system implements a complete Facebook integration for the Squidgy platform that includes:

- **Browser Automation**: Visible browser automation that users can see
- **2FA Handling**: Automatic email monitoring for 2FA codes
- **Facebook Pages Discovery**: Automatically finds all Facebook pages
- **Page Selection**: Allows users to choose which pages to connect
- **Database Storage**: Stores integration data in Supabase

## Architecture

```
Frontend (React) → Backend (FastAPI) → Facebook Service (Playwright) → Database (Supabase)
```

## Files

### Frontend Files
- `src/components/EnhancedChatFacebookSetup.tsx` - Main Facebook setup component
- `src/components/ProgressiveSOLSetup.tsx` - Progressive setup flow
- `database/squidgy_business_fb_integration.sql` - Database schema

### Backend Files
- `main.py` - FastAPI endpoints for Facebook integration
- `facebook_integration_service.py` - Core integration service with browser automation
- `test_facebook_integration.py` - Test suite

## How It Works

### 1. Frontend Initiation
```typescript
// User clicks "Connect Facebook Account"
const response = await fetch('/api/facebook/integrate', {
  method: 'POST',
  body: JSON.stringify({
    location_id: 'GHL_location_id',
    user_id: 'GHL_user_id',
    email: 'ghl_login_email',
    password: 'ghl_login_password',
    firm_user_id: 'supabase_user_id'
  })
});
```

### 2. Backend Processing
```python
# Start browser automation in background
@app.post("/api/facebook/integrate")
async def integrate_facebook(request: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_facebook_integration, request)
    return {"status": "processing"}
```

### 3. Browser Automation
```python
# Launch visible browser with Playwright
browser = await p.chromium.launch(headless=False)
# Login to GoHighLevel
# Handle 2FA with email monitoring
# Extract JWT token from network requests
# Get Facebook pages from GHL API
```

### 4. Status Polling
```typescript
// Frontend polls for status updates
const checkStatus = async () => {
  const response = await fetch(`/api/facebook/integration-status/${location_id}`);
  const status = await response.json();
  
  if (status.status === 'success') {
    setAvailablePages(status.pages);
    setIntegrationStatus('selecting_pages');
  }
};
```

### 5. Page Selection
```typescript
// User selects which pages to connect
const selectedPages = ['page_id_1', 'page_id_2'];
await completeIntegration(selectedPages);
```

## API Endpoints

### POST /api/facebook/integrate
Start Facebook integration with browser automation

**Request:**
```json
{
  "location_id": "GHL_location_id",
  "user_id": "GHL_user_id", 
  "email": "ghl_login_email",
  "password": "ghl_login_password",
  "firm_user_id": "supabase_user_id",
  "enable_2fa_bypass": false
}
```

**Response:**
```json
{
  "status": "processing",
  "message": "Facebook integration started. Browser automation in progress...",
  "location_id": "GHL_location_id"
}
```

### GET /api/facebook/integration-status/{location_id}
Get current integration status

**Response:**
```json
{
  "status": "success",
  "pages": [
    {
      "facebookPageId": "page_123",
      "facebookPageName": "Solar Company",
      "facebookIgnoreMessages": false,
      "isInstagramAvailable": true
    }
  ],
  "completed_at": "2025-01-08T10:30:00Z"
}
```

### POST /api/facebook/connect-page
Connect a specific Facebook page to GHL

**Request:**
```json
{
  "location_id": "GHL_location_id",
  "page_id": "facebook_page_id"
}
```

## Browser Automation Flow

1. **Launch Browser**: Opens Chromium in non-headless mode (visible to user)
2. **Navigate to GHL**: Goes to https://app.gohighlevel.com/login
3. **Fill Credentials**: Automatically fills email and password
4. **Handle 2FA**: Monitors email for 2FA codes if required
5. **Extract JWT**: Captures JWT token from network requests
6. **Get Facebook Pages**: Calls GHL API to get Facebook pages
7. **Store Data**: Saves page data to database

## Database Schema

```sql
CREATE TABLE squidgy_business_fb_integration (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_user_id UUID NOT NULL REFERENCES profiles(user_id),
    location_id VARCHAR(255) NOT NULL,
    
    -- Facebook OAuth Data
    fb_access_token TEXT,
    fb_token_expires_at TIMESTAMPTZ,
    
    -- Facebook Pages Data
    fb_pages_data JSONB,
    selected_page_ids VARCHAR(255)[],
    
    -- GHL Integration Status
    ghl_integration_status VARCHAR(50) DEFAULT 'pending',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(firm_user_id, location_id)
);
```

## 2FA Email Monitoring

The system monitors email for 2FA codes using IMAP:

```python
# Configure email monitoring
email_config = EmailConfig(
    imap_server="imap.gmail.com",
    imap_port=993,
    email_address="squidgy.2fa.monitor@gmail.com",
    email_password="app-specific-password"
)

# Monitor for 2FA codes
async def _get_2fa_code_from_email(self) -> Optional[str]:
    mail = imaplib.IMAP4_SSL(self.email_config.imap_server)
    mail.login(self.email_config.email_address, self.email_config.email_password)
    
    # Search for GHL emails
    result, data = mail.search(None, '(FROM "noreply@gohighlevel.com" UNSEEN)')
    
    # Extract 6-digit codes
    code_match = re.search(r'\\b(\\d{6})\\b', email_body)
    return code_match.group(1) if code_match else None
```

## Error Handling

The system handles various error scenarios:

- **Login Failures**: Retries with different selectors
- **2FA Timeouts**: 30-second timeout for email codes
- **Network Issues**: Graceful failures with user feedback
- **Browser Crashes**: Automatic cleanup and status updates

## Testing

Run the test suite:

```bash
cd /Users/somasekharaddakula/CascadeProjects/SquidgyBackend
python test_facebook_integration.py
```

## Production Considerations

1. **Email Credentials**: Store in environment variables
2. **Rate Limiting**: Implement rate limiting for API calls
3. **Monitoring**: Add logging and monitoring for browser automation
4. **Cleanup**: Implement cleanup for failed integrations
5. **Security**: Use secure credential storage

## User Experience

### What Users See:
1. Click "Connect Facebook Account"
2. See loading spinner with progress messages
3. Browser window opens automatically
4. 2FA prompt appears if needed
5. List of Facebook pages appears
6. Select pages to connect
7. Integration complete confirmation

### Progress Messages:
- "Starting browser automation..."
- "Launching browser..."
- "Logging into GoHighLevel..."
- "Handling 2FA verification..."
- "Extracting Facebook pages..."
- "Integration complete!"

## Future Enhancements

1. **Real-time Updates**: WebSocket connection for live updates
2. **Batch Operations**: Connect multiple pages at once
3. **Scheduling**: Schedule social media posts
4. **Analytics**: Track integration success rates
5. **Templates**: Pre-configured integration templates

## Troubleshooting

### Common Issues:
1. **Browser Not Opening**: Check Playwright installation
2. **2FA Timeout**: Verify email configuration
3. **Login Failures**: Check GHL credentials
4. **Page Not Found**: Verify location_id is correct

### Debug Mode:
Set `headless=False` in browser launch to see automation in action.

## Support

For issues or questions, contact the development team or check the logs for detailed error messages.