# Fix Supabase CORS and Auth Configuration

## 1. Add Your Vercel Domain to Supabase

1. Go to your [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **Authentication → URL Configuration**
4. Add these URLs:

### Site URL:
```
https://boiler-plate-v1-lake.vercel.app
```

### Redirect URLs (add all of these):
```
https://boiler-plate-v1-lake.vercel.app
https://boiler-plate-v1-lake.vercel.app/*
https://boiler-plate-v1-lake.vercel.app/auth/callback
https://boiler-plate-v1-lake.vercel.app/auth/reset-password
http://localhost:3000
http://localhost:3000/*
```

## 2. Enable CORS in Supabase

1. Still in Supabase Dashboard
2. Go to **Settings → API**
3. Under **CORS Allowed Origins**, add:
```
https://boiler-plate-v1-lake.vercel.app
https://*.vercel.app
http://localhost:3000
```

## 3. Configure Email Templates

1. Go to **Authentication → Email Templates**
2. For the **Reset Password** template, ensure the link uses:
```
{{ .SiteURL }}/auth/reset-password?token={{ .Token }}&type=recovery
```

## 4. Check Email Settings

1. Go to **Authentication → Providers → Email**
2. Ensure **Enable Email Confirmations** is properly configured
3. Check SMTP settings if using custom SMTP

## 5. Environment Variables in Vercel

Make sure these are set in your Vercel project settings:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## 6. If 502 Bad Gateway Persists

This could indicate:
- Supabase service issues (check status.supabase.com)
- Rate limiting on Supabase's end
- Authentication service overload

Try:
1. Wait a few minutes
2. Check Supabase status page
3. Contact Supabase support if it persists