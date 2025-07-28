"""
Email confirmation validation middleware for SquidgyBackend
"""
import logging
from functools import wraps
from fastapi import HTTPException
from supabase import Client

logger = logging.getLogger(__name__)

async def verify_email_confirmed(supabase: Client, user_id: str) -> bool:
    """
    Verify that user has confirmed their email
    
    Args:
        supabase: Supabase client instance
        user_id: User ID to check
        
    Returns:
        bool: True if email is confirmed, False otherwise
    """
    # TEMPORARY: Skip email confirmation check for development
    # TODO: Re-enable this once email confirmation is properly configured
    logger.info(f"⚠️ SKIPPING email confirmation check for user {user_id} (development mode)")
    return True
    
    # Original email confirmation logic (commented out for now)
    # try:
    #     result = supabase.table('profiles')\
    #         .select('email_confirmed, email')\
    #         .eq('user_id', user_id)\
    #         .single()\
    #         .execute()
    #     
    #     if result.data and result.data.get('email_confirmed'):
    #         logger.info(f"✅ Email confirmed for user {user_id}: {result.data.get('email')}")
    #         return True
    #     
    #     logger.warning(f"❌ Email not confirmed for user {user_id}: {result.data.get('email') if result.data else 'No profile found'}")
    #     return False
    #     
    # except Exception as e:
    #     logger.error(f"Error checking email confirmation for user {user_id}: {str(e)}")
    #     return False

def require_email_confirmed(supabase: Client):
    """
    Decorator factory that creates a decorator requiring email confirmation
    
    Args:
        supabase: Supabase client instance
        
    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            # Extract user_id from the function arguments
            user_id = None
            
            # Check if user_id is in kwargs
            if 'user_id' in kwargs:
                user_id = kwargs['user_id']
            # Check if it's in args (for functions that take user_id as first param)
            elif len(args) > 0 and hasattr(args[0], 'user_id'):
                user_id = args[0].user_id
            # Check if it's a request object with user_id
            elif len(args) > 0 and hasattr(args[0], 'get'):
                user_id = args[0].get('user_id')
            
            if not user_id:
                raise HTTPException(
                    status_code=400, 
                    detail="User ID is required for this operation"
                )
            
            # Verify email confirmation
            if not await verify_email_confirmed(supabase, user_id):
                raise HTTPException(
                    status_code=403, 
                    detail="Email confirmation required. Please check your email and click the confirmation link."
                )
            
            return await f(*args, **kwargs)
        return decorated_function
    return decorator

async def check_email_confirmation_status(supabase: Client, user_id: str) -> dict:
    """
    Check email confirmation status for a user
    
    Args:
        supabase: Supabase client instance
        user_id: User ID to check
        
    Returns:
        dict: Status information
    """
    try:
        result = supabase.table('profiles')\
            .select('email_confirmed, email, full_name')\
            .eq('user_id', user_id)\
            .single()\
            .execute()
        
        if not result.data:
            return {
                'status': 'error',
                'message': 'User profile not found',
                'email_confirmed': False
            }
        
        return {
            'status': 'success',
            'email_confirmed': result.data.get('email_confirmed', False),
            'email': result.data.get('email'),
            'full_name': result.data.get('full_name')
        }
        
    except Exception as e:
        logger.error(f"Error checking email status for user {user_id}: {str(e)}")
        return {
            'status': 'error',
            'message': str(e),
            'email_confirmed': False
        }