# 🔧 Fix: Always Use user_id, Never Use id

## Current Problem
- Frontend sends: `profile.id` (wrong!)
- Backend expects: `user_id` (correct!)
- We need to ensure frontend sends `profile.user_id`

## The Rule
**ALWAYS use `user_id`, NEVER use `id`**

## Frontend Fixes Needed

### 1. **ChatContext.tsx**
```typescript
// WRONG ❌
user_id: profile.id
const ws = new WebSocket(`${WS_URL}/ws/${profile.id}/${sessionId}`);

// CORRECT ✅
user_id: profile.user_id
const ws = new WebSocket(`${WS_URL}/ws/${profile.user_id}/${sessionId}`);
```

### 2. **EnhancedChat.tsx**
```typescript
// WRONG ❌
const ws = new WebSocket(`${wsUrl}/ws/${profile.id}/${currentSession}`);

// CORRECT ✅
const ws = new WebSocket(`${wsUrl}/ws/${profile.user_id}/${currentSession}`);
```

### 3. **EnhancedDashboard.tsx**
```typescript
// WRONG ❌
const sessionId = `${profile.id}_${agentName}`;
.eq('user_id', profile.id)

// CORRECT ✅
const sessionId = `${profile.user_id}_${agentName}`;
.eq('user_id', profile.user_id)
```

### 4. **All Database Queries**
```typescript
// WRONG ❌
.eq('user_id', profile.id)
.eq('id', someValue)

// CORRECT ✅
.eq('user_id', profile.user_id)
.eq('user_id', someValue)
```

## Backend Verification

The backend is already correct - it uses `user_id` everywhere:
- API models use `user_id: str`
- Database operations use `client_id` (which stores user_id)
- No direct usage of `id` field

## Testing After Fix

### 1. WebSocket Connection
```typescript
// Should connect with:
ws://localhost:8000/ws/80b957fc-de1d-4f28-920c-41e0e2e28e5e/session_id
```

### 2. API Calls
```json
{
  "user_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e",
  "user_mssg": "Test message",
  "session_id": "80b957fc-de1d-4f28-920c-41e0e2e28e5e_presaleskb",
  "agent_name": "presaleskb"
}
```

## Database Schema Check

Ensure all tables use `user_id` not `id` for user references:
- ✅ `chat_messages.user_id`
- ✅ `chat_sessions.user_id`
- ✅ `client_kb.client_id` (stores user_id)
- ✅ `client_context.client_id` (stores user_id)

## Summary of Changes

### Frontend (Multiple files):
```diff
- user_id: profile.id
+ user_id: profile.user_id

- `${profile.id}_${agentName}`
+ `${profile.user_id}_${agentName}`

- .eq('user_id', profile.id)
+ .eq('user_id', profile.user_id)
```

### Backend:
No changes needed - already using `user_id` correctly!

## Important Note
The `profile.user_id` field contains the Supabase auth user ID (e.g., "80b957fc-de1d-4f28-920c-41e0e2e28e5e"), which is what should be used throughout the system for user identification.