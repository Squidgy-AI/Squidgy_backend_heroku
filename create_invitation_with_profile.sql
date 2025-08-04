-- Function to create invitation with profile
-- This ensures no foreign key constraint violations

CREATE OR REPLACE FUNCTION create_invitation_with_profile(
    p_sender_id UUID,
    p_recipient_email TEXT,
    p_sender_company_id UUID,
    p_group_id UUID DEFAULT NULL,
    p_token TEXT DEFAULT gen_random_uuid()::TEXT
) RETURNS JSON AS $$
DECLARE
    v_recipient_id UUID;
    v_invitation_id UUID;
    v_profile_id UUID;
    v_result JSON;
BEGIN
    -- Normalize email
    p_recipient_email := LOWER(TRIM(p_recipient_email));
    
    -- Check if profile already exists for this email
    SELECT user_id, id INTO v_recipient_id, v_profile_id
    FROM profiles
    WHERE LOWER(email) = p_recipient_email
    LIMIT 1;
    
    -- If profile doesn't exist, create one
    IF v_recipient_id IS NULL THEN
        -- Generate new user_id
        v_recipient_id := gen_random_uuid();
        
        -- Create profile for the invited user
        INSERT INTO profiles (
            id,
            user_id,
            email,
            full_name,
            company_id,
            role,
            email_confirmed,
            created_at,
            updated_at
        ) VALUES (
            gen_random_uuid(),  -- profile id
            v_recipient_id,     -- user_id
            p_recipient_email,  -- email
            NULL,              -- full_name (to be filled when they accept)
            p_sender_company_id, -- company_id (same as sender's company)
            'member',          -- default role
            false,             -- email_confirmed (will be true after they accept)
            NOW(),
            NOW()
        )
        RETURNING id INTO v_profile_id;
        
        RAISE NOTICE 'Created new profile for % with user_id %', p_recipient_email, v_recipient_id;
    ELSE
        RAISE NOTICE 'Profile already exists for % with user_id %', p_recipient_email, v_recipient_id;
    END IF;
    
    -- Now create the invitation with valid recipient_id
    INSERT INTO invitations (
        sender_id,
        recipient_id,       -- This is now guaranteed to exist in profiles
        recipient_email,
        sender_company_id,
        group_id,
        status,
        token,
        created_at,
        expires_at
    ) VALUES (
        p_sender_id,
        v_recipient_id,     -- Valid user_id from profiles table
        p_recipient_email,
        p_sender_company_id,
        p_group_id,
        'pending',
        p_token,
        NOW(),
        NOW() + INTERVAL '7 days'
    )
    ON CONFLICT (sender_id, recipient_email) 
    DO UPDATE SET
        status = 'pending',
        token = p_token,
        created_at = NOW(),
        expires_at = NOW() + INTERVAL '7 days'
    RETURNING id INTO v_invitation_id;
    
    -- Return result with all relevant IDs
    v_result := json_build_object(
        'success', true,
        'invitation_id', v_invitation_id,
        'recipient_id', v_recipient_id,
        'profile_id', v_profile_id,
        'token', p_token,
        'recipient_email', p_recipient_email,
        'message', CASE 
            WHEN v_profile_id IS NOT NULL THEN 'Invitation created with new profile'
            ELSE 'Invitation created for existing user'
        END
    );
    
    RETURN v_result;
    
EXCEPTION
    WHEN OTHERS THEN
        RETURN json_build_object(
            'success', false,
            'error', SQLERRM,
            'detail', SQLSTATE
        );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION create_invitation_with_profile TO authenticated;

-- Example usage:
-- SELECT create_invitation_with_profile(
--     'sender-user-id'::uuid,
--     'newuser@example.com',
--     'company-id'::uuid
-- );

-- Test function to verify it works
-- This will create a profile if needed and then create the invitation
/*
DO $$
DECLARE
    v_result JSON;
BEGIN
    -- Test with a new email
    v_result := create_invitation_with_profile(
        (SELECT user_id FROM profiles WHERE email = 'info@squidgy.net' LIMIT 1),
        'testinvite@example.com',
        (SELECT company_id FROM profiles WHERE email = 'info@squidgy.net' LIMIT 1)
    );
    
    RAISE NOTICE 'Result: %', v_result;
END $$;
*/