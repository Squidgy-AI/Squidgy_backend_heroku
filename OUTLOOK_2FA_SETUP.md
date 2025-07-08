# 🔐 OUTLOOK 2FA SETUP GUIDE

## Overview

This enhanced 2FA service handles the complete GoHighLevel 2FA flow with Microsoft Outlook email monitoring for `sa+01@squidgy.ai` accounts.

## 🎯 Complete 2FA Flow

### **Step 1: User Login**
- Browser navigates to GHL login
- User credentials are filled automatically
- Login button is clicked

### **Step 2: 2FA Detection**
- System detects 2FA page
- Automatically selects "Email" option
- Clicks "Send Code" button

### **Step 3: Email Monitoring**
- Connects to Microsoft Outlook via IMAP
- Monitors `sa+01@squidgy.ai` for GHL emails
- Extracts 6-digit OTP codes automatically

### **Step 4: OTP Input**
- Automatically fills OTP in browser
- Handles both single input and digit boxes
- Submits form and completes login

## 📧 Outlook Email Configuration

### **Required Settings:**

1. **Email Address:** `sa+01@squidgy.ai`
2. **IMAP Server:** `outlook.office365.com`
3. **IMAP Port:** `993`
4. **App Password:** Generated from Microsoft Account

### **Email Patterns Monitored:**
- `noreply@gohighlevel.com`
- `no-reply@gohighlevel.com`
- `support@gohighlevel.com`

## 🛠️ Setup Instructions

### **1. Enable IMAP in Outlook**

1. Go to [Outlook.com](https://outlook.com)
2. Click **Settings** (gear icon)
3. Go to **Mail** → **Sync email**
4. **Enable IMAP access**
5. Save settings

### **2. Create App-Specific Password**

1. Go to [Microsoft Account Security](https://account.microsoft.com/security)
2. Click **Advanced security options**
3. Under **App passwords**, click **Create a new app password**
4. Select **Email apps**
5. **Copy the generated password** (save it securely)

### **3. Set Environment Variables**

#### **For Local Development:**
```bash
export OUTLOOK_2FA_EMAIL="sa+01@squidgy.ai"
export OUTLOOK_2FA_PASSWORD="your-app-specific-password"
```

#### **For Heroku Production:**
```bash
heroku config:set OUTLOOK_2FA_EMAIL=sa+01@squidgy.ai
heroku config:set OUTLOOK_2FA_PASSWORD=your-app-specific-password
```

## 🧪 Testing the Setup

### **Run the Test Suite:**
```bash
cd /Users/somasekharaddakula/CascadeProjects/SquidgyBackend
python test_outlook_2fa.py
```

### **Expected Output:**
```
✅ Email connection successful!
✅ OTP pattern extraction working
✅ Test 1: 'Your code is 123456' → 123456
✅ Test 2: 'Security code: 789012' → 789012
```

## 🔍 OTP Extraction Patterns

The service recognizes these OTP patterns:

```python
patterns = [
    r'verification code[:\s]*(\d{6})',
    r'security code[:\s]*(\d{6})',
    r'access code[:\s]*(\d{6})',
    r'login code[:\s]*(\d{6})',
    r'your code[:\s]*(\d{6})',
    r'code[:\s]*(\d{6})',
    r'\b(\d{6})\b',  # Any 6-digit number
    r'(\d{4})',     # 4-digit codes
]
```

## 🎮 Browser Input Handling

### **OTP Input Methods:**

1. **Single Input Field:**
   ```html
   <input type="text" name="otp" />
   ```

2. **Individual Digit Boxes:**
   ```html
   <input maxlength="1" class="digit-input" />
   <input maxlength="1" class="digit-input" />
   <!-- ... 6 boxes total -->
   ```

### **Form Submission:**
- Automatic submit button detection
- Enter key fallback
- Multiple selector attempts

## 🚨 Troubleshooting

### **Common Issues:**

1. **Email Connection Failed**
   ```
   ❌ Email connection failed: [AUTHENTICATIONFAILED]
   ```
   **Solution:** Check app-specific password and IMAP settings

2. **No OTP Found**
   ```
   ℹ️ No OTP found in recent emails
   ```
   **Solution:** Verify email patterns and check spam folder

3. **OTP Input Failed**
   ```
   ⌨️ OTP input error: Element not found
   ```
   **Solution:** Check browser automation selectors

### **Debug Steps:**

1. **Test Email Connection:**
   ```bash
   python test_outlook_2fa.py
   ```

2. **Check Environment Variables:**
   ```bash
   echo $OUTLOOK_2FA_EMAIL
   echo $OUTLOOK_2FA_PASSWORD
   ```

3. **Monitor Email Manually:**
   - Send test 2FA from GHL
   - Check if email arrives
   - Verify OTP extraction

## 🔧 Integration with Facebook Service

### **Enhanced Service Usage:**
```python
from enhanced_2fa_service import Enhanced2FAService, OutlookEmailConfig

# Initialize
outlook_config = OutlookEmailConfig()
enhanced_2fa = Enhanced2FAService(outlook_config)

# Handle 2FA in browser automation
result = await enhanced_2fa.handle_ghl_2fa_flow(page)

if result["success"]:
    print("✅ 2FA completed!")
else:
    print(f"❌ 2FA failed: {result['error']}")
```

### **Integration Points:**
- `facebook_integration_service.py` - Main integration
- `main.py` - Environment configuration
- Browser automation - Playwright page handling

## 📊 Production Deployment

### **Environment Variables Required:**
```bash
OUTLOOK_2FA_EMAIL=sa+01@squidgy.ai
OUTLOOK_2FA_PASSWORD=your-app-specific-password
DYNO=true  # For Heroku detection
```

### **Heroku Deployment:**
```bash
heroku config:set OUTLOOK_2FA_EMAIL=sa+01@squidgy.ai
heroku config:set OUTLOOK_2FA_PASSWORD=your-app-password
git push heroku main
```

## 🎯 Success Criteria

### **2FA Flow Should:**
1. ✅ Detect 2FA page automatically
2. ✅ Select email option
3. ✅ Click send code button
4. ✅ Monitor Outlook email for OTP
5. ✅ Extract 6-digit code
6. ✅ Input code in browser
7. ✅ Submit form successfully
8. ✅ Complete login process

### **Expected Timeline:**
- **Email delivery:** 5-30 seconds
- **OTP extraction:** 1-2 seconds
- **Browser input:** 2-3 seconds
- **Total 2FA time:** 10-60 seconds

## 📞 Support

### **If 2FA Fails:**
1. Check Outlook email credentials
2. Verify IMAP is enabled
3. Test email connection manually
4. Check browser automation logs
5. Verify OTP pattern extraction

### **Contact Info:**
- Check implementation in `enhanced_2fa_service.py`
- Run test suite: `python test_outlook_2fa.py`
- Monitor logs during automation process

## 🚀 Ready for Production

The enhanced 2FA service is now configured for:
- ✅ Microsoft Outlook email monitoring
- ✅ `sa+01@squidgy.ai` account handling
- ✅ Complete browser automation integration
- ✅ Production environment variables
- ✅ Comprehensive error handling

**Test the complete flow and deploy when ready!** 🎉