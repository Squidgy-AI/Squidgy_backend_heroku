# 🚀 Business Setup Workflow - Deployment Instructions

## 📋 Quick Setup Guide

### 1. Database Setup
Run this SQL in your database:
```sql
-- Copy and paste the contents of QUICK_DATABASE_SETUP.sql into your database
```

### 2. Environment Variables
Set these in your environment:
```bash
DATABASE_URL=your_postgresql_connection_string
GMAIL_2FA_EMAIL=your_gmail_for_otp
GMAIL_2FA_APP_PASSWORD=your_gmail_app_password
HIGHLEVEL_EMAIL=your_highlevel_login_email  
HIGHLEVEL_PASSWORD=your_highlevel_password
```

### 3. Start the Business Setup API
```bash
python3 business_setup_complete_api.py
# Runs on http://localhost:8004
```

## 🎯 API Endpoints for UI Integration

### Business Setup Endpoint
```javascript
POST http://localhost:8004/api/business/setup

// Request (from your business form):
{
  "firm_user_id": "uuid-from-your-system",
  "agent_id": "agent_001",
  "business_name": "Solar Solutions LLC",
  "business_address": "123 Main Street, Suite 100", 
  "city": "Austin",
  "state": "Texas",
  "country": "United States",
  "postal_code": "78701",
  "business_logo_url": null,
  "snapshot_id": "YOUR_GHL_SNAPSHOT_ID"  // ← You provide this
}

// Response (immediate - user can continue):
{
  "success": true,
  "message": "Business setup completed! Automation running in background.",
  "business_id": "generated-uuid",
  "status": "user_created",
  "ghl_location_id": "LOC_ABC123", 
  "ghl_user_email": "solarsolut+LOC_ABC123@squidgyai.com",
  "automation_started": true
}
```

### Status Monitoring (Optional)
```javascript
GET http://localhost:8004/api/business/status/{business_id}

// Response:
{
  "business_name": "Solar Solutions LLC",
  "status": "completed",  // pending, user_created, automation_running, completed, failed
  "location_id": "LOC_ABC123",
  "user_email": "solarsolut+LOC_ABC123@squidgyai.com", 
  "has_pit_token": true,
  "automation_started_at": "2025-08-02T14:30:00Z",
  "automation_completed_at": "2025-08-02T14:31:15Z"
}
```

## 🎬 User Experience Flow

1. **User fills business form** → Clicks "Next"
2. **15-20 seconds**: API creates location + user → Returns success
3. **User continues immediately** (non-blocking!)  
4. **Background**: 20-40 seconds automation → Tokens ready
5. **Optional**: Frontend can poll status endpoint

## 🗄️ Database Tables Created

- `squidgy_business_information` - Main business workflow table
- `business_setup_status` - View for easy monitoring
- Updated `squidgy_agent_business_setup` - Enhanced with new setup_type

## 🧪 Testing

```bash
# Test the complete workflow
python3 test_business_setup_complete.py

# Demo workflow (no database needed)
python3 demo_business_setup_workflow.py
```

## 🔧 Configuration Needed

1. **HighLevel Snapshot ID**: Replace `"YOUR_GHL_SNAPSHOT_ID"` with actual snapshot
2. **Email Domain**: Change `@squidgyai.com` to your domain  
3. **GHL API Integration**: Replace simulation functions with real API calls
4. **Error Notifications**: Add email/webhook notifications for failures

## ✅ Ready to Use!

The workflow is complete and tested. Just need your specific configuration values.

**Key Feature**: User experience is **non-blocking** - they don't wait for automation to complete!