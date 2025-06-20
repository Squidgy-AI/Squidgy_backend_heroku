# 🚨 Frontend ID Issue - Using Wrong User ID

## The Problem

The frontend is sending `profile.id` as `user_id`, but it should send `profile.user_id`:

### Current (WRONG):
```json
{
  "user_id": "a59741cd-aed2-44da-a479-78bc601d1596",  // This is profile.id
  "user_mssg": "Hey this is Soma is this john wick?",
  "session_id": "a59741cd-aed2-44da-a479-78bc601d1596_presaleskb"
}
```

### Should Be (CORRECT):
```json
{
  "user_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e",  // This should be profile.user_id
  "user_mssg": "Hey this is Soma is this john wick?",
  "session_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e_presaleskb"
}
```

## From profiles_rows.csv:
```
id: a59741cd-aed2-44da-a479-78bc601d1596 (profile table primary key)
user_id: 80b957fc-de1d-4f28-920c-41e0e2e28e5e (auth user ID - THIS IS WHAT WE NEED!)
```

## Frontend Files Using Wrong ID:

### 1. **ChatContext.tsx** (Main culprit):
```typescript
// Line 107 - WebSocket connection
const ws = new WebSocket(`${WS_URL}/ws/${profile.id}/${sessionId}`);

// Line 451 - Saving messages
user_id: profile.id,  // WRONG!

// Line 475 - Creating sessions
user_id: profile.id,  // WRONG!

// Line 495 - Fetching messages
.eq('user_id', profile.id)  // WRONG!
```

### 2. **EnhancedChat.tsx**:
```typescript
const ws = new WebSocket(`${wsUrl}/ws/${profile.id}/${currentSession}`);
```

### 3. **EnhancedDashboard.tsx**:
```typescript
const sessionId = `${profile.id}_${agentName}`;
.eq('user_id', profile.id)
```

## The Fix

All these instances need to change from:
```typescript
profile.id
```

To:
```typescript
profile.user_id
```

## Why This Matters

1. **Database Consistency**: The backend expects the auth user_id
2. **Security**: Using the correct user_id ensures proper authentication
3. **Data Integrity**: All user data should be linked to the auth user_id

## Quick Test

After fixing, the WebSocket payload should look like:
```json
{
  "user_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e",  // ✅ Correct auth user_id
  "user_mssg": "Test message",
  "session_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e_presaleskb"
}
```