# Invitation Foreign Key Constraint Fix

## Overview
This fix resolves the `invitations_recipient_id_fkey` foreign key constraint error by creating a profile entry for invited users before creating the invitation.

## What Changed

### 1. Database Function
A new SQL function `create_invitation_with_profile` that:
- Checks if a profile exists for the recipient email
- If not, creates a new profile with:
  - `email_confirmed: false`
  - `company_id`: same as sender's company
  - `role: 'member'`
- Creates the invitation with valid `recipient_id`
- Returns success/error status with all relevant IDs

### 2. Backend API Endpoint
Updated `/api/send-invitation-email` to:
- Create profile first (if needed)
- Create invitation with valid recipient_id
- Send invitation email
- Handle all error cases gracefully

### 3. Files Modified
- `main.py`: Updated invitation endpoint
- `invitation_handler.py`: New handler class (optional, for modularity)
- `create_invitation_with_profile.sql`: Database function

## Deployment Steps

### 1. Deploy Database Function
Run this SQL in your Supabase SQL editor:

```sql
-- Copy the contents of create_invitation_with_profile.sql
-- and execute in Supabase SQL editor
```

### 2. Deploy Backend Code
```bash
# Commit and push the changes
git add -A
git commit -m "Fix invitation foreign key constraint by creating profiles first"
git push heroku main
```

### 3. Test the Fix
1. Try sending an invitation to a new email address
2. Check that no foreign key errors occur
3. Verify profile is created in the profiles table
4. Verify invitation is created in the invitations table

## How It Works

1. **User sends invitation** → Frontend calls `/api/send-invitation-email`
2. **Backend creates profile** → New profile with `email_confirmed: false`
3. **Backend creates invitation** → With valid `recipient_id` from profile
4. **Email sent** → User receives invitation email
5. **User accepts** → Updates profile with full details and sets `email_confirmed: true`

## Benefits
- ✅ No more foreign key constraint errors
- ✅ Clean database relationships maintained
- ✅ Pre-registered users in the system
- ✅ Can track pending invitations properly
- ✅ Profile ready when user accepts invitation

## Rollback (if needed)
If you need to rollback:
1. Remove the SQL function: `DROP FUNCTION IF EXISTS create_invitation_with_profile;`
2. Revert the main.py changes
3. Clean up any test profiles created with `email_confirmed = false`