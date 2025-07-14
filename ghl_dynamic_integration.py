"""
GHL Dynamic Integration Module
Handles dynamic creation of sub-accounts and users in GoHighLevel
Replaces static IDs with dynamic ones for Facebook integration
"""

import json
import logging
import os
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel

# Import GHL functions
from Tools.GHL.Sub_Accounts.create_sub_acc import create_sub_acc
from Tools.GHL.Users.create_user import create_user
from Tools.GHL.environment import constant, config

logger = logging.getLogger(__name__)

# Request Models
class GHLSubAccountRequest(BaseModel):
    """Request model for creating GHL sub-account"""
    client_name: str
    phone_number: str
    address: str
    city: str
    state: str
    country: str
    postal_code: str
    website: str
    timezone: str
    prospect_first_name: str
    prospect_last_name: str
    prospect_email: str
    company_id: Optional[str] = None
    access_token: str
    # Optional fields with defaults
    allow_duplicate_contact: Optional[bool] = False
    allow_duplicate_opportunity: Optional[bool] = False
    allow_facebook_name_merge: Optional[bool] = False
    disable_contact_timezone: Optional[bool] = False
    social_urls: Optional[dict] = None
    
class GHLUserRequest(BaseModel):
    """Request model for creating GHL user"""
    first_name: str
    last_name: str
    email: str
    password: str
    phone_number: str
    location_id: str  # Dynamic location ID from sub-account creation
    company_id: Optional[str] = None
    access_token: str
    agency_token: Optional[str] = None  # For compatibility with existing endpoints

class FacebookConnectionRequest(BaseModel):
    """Request model for connecting Facebook with dynamic GHL IDs"""
    user_id: str
    location_id: str  # Dynamic location ID
    ghl_user_id: str  # Dynamic user ID
    email: str  # Required by FacebookPagesRequest
    password: str  # Required by FacebookPagesRequest
    jwt_token: Optional[str] = None
    manual_token: Optional[bool] = False
    access_token: Optional[str] = None

class CompleteSetupRequest(BaseModel):
    """Request model for complete GHL + Facebook setup"""
    # Sub-account fields
    client_name: str
    phone_number: str
    address: str
    city: str
    state: str
    country: str
    postal_code: str
    website: str
    timezone: str
    prospect_first_name: str
    prospect_last_name: str
    prospect_email: str
    
    # User fields
    user_first_name: str
    user_last_name: str
    user_email: str
    user_password: str
    user_phone_number: str
    
    # Facebook fields
    facebook_user_id: str
    jwt_token: Optional[str] = None
    manual_token: Optional[bool] = False
    
    # Common fields
    company_id: Optional[str] = None
    access_token: str
    
    # Optional sub-account fields
    allow_duplicate_contact: Optional[bool] = False
    allow_duplicate_opportunity: Optional[bool] = False
    allow_facebook_name_merge: Optional[bool] = False
    disable_contact_timezone: Optional[bool] = False
    social_urls: Optional[dict] = None

# Response Models
class GHLSubAccountResponse(BaseModel):
    """Response model for sub-account creation"""
    success: bool
    location_id: Optional[str] = None
    subaccount_name: Optional[str] = None
    message: str
    raw_response: Optional[Dict[str, Any]] = None

class GHLUserResponse(BaseModel):
    """Response model for user creation"""
    success: bool
    user_id: Optional[str] = None
    user_details: Optional[Dict[str, Any]] = None
    message: str
    raw_response: Optional[Dict[str, Any]] = None

class FacebookConnectionResponse(BaseModel):
    """Response model for Facebook connection"""
    success: bool
    message: str
    pages: Optional[list] = None
    connection_details: Optional[Dict[str, Any]] = None

# Core Functions
async def create_ghl_subaccount(request: GHLSubAccountRequest) -> GHLSubAccountResponse:
    """
    Create a new GHL sub-account and return the dynamic location_id
    
    Args:
        request: GHLSubAccountRequest with all required fields
        
    Returns:
        GHLSubAccountResponse with location_id and status
    """
    try:
        logger.info(f"Creating GHL sub-account for client: {request.client_name}")
        
        # Use company_id from request or default from constants
        company_id = request.company_id or constant.constant.Company_Id
        
        # Create sub-account using the existing function
        result = create_sub_acc(
            client_name=request.client_name,
            phone_number=request.phone_number,
            address=request.address,
            city=request.city,
            state=request.state,
            country=request.country,
            postal_code=request.postal_code,
            website=request.website,
            timezone=request.timezone,
            prospect_first_name=request.prospect_first_name,
            prospect_last_name=request.prospect_last_name,
            prospect_email=request.prospect_email,
            company_id=request.company_id or constant.constant.Company_Id,
            access_token=request.access_token,
            allow_duplicate_contact=request.allow_duplicate_contact,
            allow_duplicate_opportunity=request.allow_duplicate_opportunity,
            allow_facebook_name_merge=request.allow_facebook_name_merge,
            disable_contact_timezone=request.disable_contact_timezone,
            social_urls=request.social_urls
        )
        
        # Extract location_id from response
        # The GHL API returns the location ID directly in the 'id' field
        if isinstance(result, dict):
            location_id = result.get('id')  # Direct ID field
            if location_id:
                logger.info(f"✅ Sub-account created successfully with location_id: {location_id}")
                return GHLSubAccountResponse(
                    success=True,
                    location_id=location_id,
                    message="Sub-account created successfully",
                    raw_response=result
                )
            # Also check for nested location.id format as fallback
            elif 'location' in result and result['location'].get('id'):
                location_id = result['location']['id']
                logger.info(f"✅ Sub-account created successfully with nested location_id: {location_id}")
                return GHLSubAccountResponse(
                    success=True,
                    location_id=location_id,
                    message="Sub-account created successfully",
                    raw_response=result
                )
        
        # Check if it's a string response indicating success
        if isinstance(result, str):
            if "success" in result.lower() or "created" in result.lower():
                logger.info(f"✅ Sub-account creation successful: {result}")
                logger.info(f"Using fallback location_id: {constant.constant.location_id}")
                return GHLSubAccountResponse(
                    success=True,
                    location_id=constant.constant.location_id,  # Use fallback
                    message=f"Sub-account created successfully (using fallback ID): {result}",
                    raw_response={"message": result, "fallback_used": True}
                )
            else:
                logger.error(f"❌ Sub-account creation failed: {result}")
                return GHLSubAccountResponse(
                    success=False,
                    location_id=None,
                    message=f"Sub-account creation failed: {result}",
                    raw_response={"message": result}
                )
        
        # If we get here, something unexpected happened
        logger.error(f"❌ Unexpected response format: {result}")
        return GHLSubAccountResponse(
            success=False,
            location_id=None,
            message=f"Unexpected response format: {result}",
            raw_response=result
        )
            
    except Exception as e:
        logger.error(f"❌ Error creating GHL sub-account: {str(e)}")
        return GHLSubAccountResponse(
            success=False,
            message=f"Error creating sub-account: {str(e)}"
        )

async def create_ghl_user(request: GHLUserRequest) -> GHLUserResponse:
    """
    Create a new GHL user in the specified location and return the dynamic user_id
    
    Args:
        request: GHLUserRequest with all required fields including location_id
        
    Returns:
        GHLUserResponse with user_id and status
    """
    try:
        logger.info("🚀 DYNAMIC create_ghl_user function called!")
        logger.info(f"Creating GHL user: {request.email} in location: {request.location_id}")
        
        # Use company_id from request or default from constants
        company_id = request.company_id or constant.constant.Company_Id
        
        # Log access token (first 5 and last 5 chars only for security)
        if request.access_token:
            token_preview = f"{request.access_token[:5]}...{request.access_token[-5:]}" if len(request.access_token) > 10 else "[INVALID TOKEN]"
            logger.info(f"Using access token for user creation: {token_preview}")
        
        # Generate unique email by appending random number to prevent duplicates
        original_email = request.email
        if '@' in original_email:
            email_parts = original_email.split('@')
            random_number = random.randint(1000, 9999)
            unique_email = f"{email_parts[0]}+{random_number}@{email_parts[1]}"
            logger.info(f"Generated unique email: {original_email} -> {unique_email}")
        else:
            unique_email = original_email
            logger.warning(f"Invalid email format, using original: {original_email}")
        
        # Create user using the existing function with dynamic location_id
        # Explicitly pass None for scopes to avoid invalid default scopes
        response = create_user(
            first_name=request.first_name,
            last_name=request.last_name,
            email=unique_email,  # Use unique email to prevent duplicates
            password=request.password,
            phone_number=request.phone_number,
            account_type=config.config.default_account_type if hasattr(config, 'config') else "account",  # Use config default
            role=config.config.default_role if hasattr(config, 'config') else "user",  # Use config default
            company_id=company_id,
            location_ids=[request.location_id],  # Use dynamic location_id
            permissions=None,  # Avoid default permissions that might be invalid
            scopes=[],  # Pass empty list to avoid default invalid scopes
            scopes_assigned_to_only=[],  # Pass empty list to avoid default scopes
            access_token=request.access_token
        )
        
        # Extract user_id from response
        # Based on GHL API documentation, the response should contain user information
        if response and isinstance(response, dict):
            # Common response formats from GHL API:
            # Option 1: Direct user_id field
            user_id = response.get('user_id') or response.get('userId') or response.get('id')
            
            # Option 2: Nested in user object
            if not user_id and 'user' in response:
                user_id = response['user'].get('id') or response['user'].get('user_id')
            
            # Option 3: Nested in data object
            if not user_id and 'data' in response:
                user_id = response['data'].get('id') or response['data'].get('user_id')
            
            if user_id:
                logger.info(f"✅ User created successfully. User ID: {user_id}")
                return GHLUserResponse(
                    success=True,
                    user_id=user_id,
                    user_details={
                        'name': f"{request.first_name} {request.last_name}",
                        'email': unique_email,  # Show the actual email used
                        'original_email': original_email,  # Keep track of original
                        'location_id': request.location_id
                    },
                    message=f"User created successfully with email: {unique_email}",
                    raw_response=response
                )
            else:
                logger.error(f"❌ User ID not found in response: {response}")
                return GHLUserResponse(
                    success=False,
                    message="User created but user_id not found in response",
                    raw_response=response
                )
        else:
            logger.error(f"❌ Invalid response format: {response}")
            return GHLUserResponse(
                success=False,
                message="Invalid response format from GHL API",
                raw_response=response
            )
            
    except Exception as e:
        logger.error(f"❌ Error creating GHL user: {str(e)}")
        return GHLUserResponse(
            success=False,
            message=f"Error creating user: {str(e)}"
        )

async def connect_facebook_with_dynamic_ids(request: FacebookConnectionRequest) -> FacebookConnectionResponse:
    """
    Connect Facebook pages using dynamic GHL location_id and user_id
    
    Args:
        request: FacebookConnectionRequest with dynamic IDs
        
    Returns:
        FacebookConnectionResponse with connection status
    """
    try:
        logger.info(f"Connecting Facebook for user: {request.user_id} with location: {request.location_id}")
        
        # Import Facebook integration function
        from facebook_pages_api_working import get_facebook_pages, FacebookPagesRequest
        
        # Get access token from request or environment
        access_token = request.access_token or os.getenv('GHL_ACCESS_TOKEN') or constant.constant.Agency_Access_Key
        
        # Log access token (first 5 and last 5 chars only for security)
        if access_token:
            token_preview = f"{access_token[:5]}...{access_token[-5:]}" if len(access_token) > 10 else "[INVALID TOKEN]"
            logger.info(f"Using access token for Facebook connection: {token_preview}")
        
        # Create Facebook request with dynamic IDs
        facebook_request = FacebookPagesRequest(
            user_id=request.user_id,
            location_id=request.location_id,  # Use dynamic location_id
            email=request.email,  # Add required email field
            password=request.password,  # Add required password field
            firm_user_id=request.ghl_user_id,  # Use dynamic user_id as firm_user_id
            manual_jwt_token=request.jwt_token  # Use manual_jwt_token field name
        )
        
        # Call Facebook integration
        facebook_response = await get_facebook_pages(facebook_request)
        
        if facebook_response.success:
            logger.info(f"✅ Facebook connection successful for user: {request.user_id}")
            return FacebookConnectionResponse(
                success=True,
                message="Facebook pages connected successfully with dynamic GHL IDs",
                pages=facebook_response.pages,
                connection_details={
                    'location_id': request.location_id,
                    'ghl_user_id': request.ghl_user_id,
                    'pages_count': len(facebook_response.pages) if facebook_response.pages else 0
                }
            )
        else:
            logger.error(f"❌ Facebook connection failed: {facebook_response.message}")
            return FacebookConnectionResponse(
                success=False,
                message=f"Facebook connection failed: {facebook_response.message}"
            )
            
    except Exception as e:
        logger.error(f"❌ Error connecting Facebook with dynamic IDs: {str(e)}")
        return FacebookConnectionResponse(
            success=False,
            message=f"Error connecting Facebook: {str(e)}"
        )

# Combined Flow Function
async def complete_ghl_facebook_setup_from_request(
    request: CompleteSetupRequest
) -> Dict[str, Any]:
    """
    Complete end-to-end setup from a single request model
    
    Args:
        request: CompleteSetupRequest with all required fields
        
    Returns:
        Dict with complete setup results
    """
    # Convert to individual request models
    # Get access token from request or environment
    access_token = request.access_token or os.getenv('GHL_ACCESS_TOKEN') or constant.constant.Agency_Access_Key
    
    # Log access token (first 5 and last 5 chars only for security)
    if access_token:
        token_preview = f"{access_token[:5]}...{access_token[-5:]}" if len(access_token) > 10 else "[INVALID TOKEN]"
        logger.info(f"Using access token: {token_preview}")
    else:
        logger.warning("No access token provided!")
    
    subaccount_data = GHLSubAccountRequest(
        client_name=request.client_name,
        phone_number=request.phone_number,
        address=request.address,
        city=request.city,
        state=request.state,
        country=request.country,
        postal_code=request.postal_code,
        website=request.website,
        timezone=request.timezone,
        prospect_first_name=request.prospect_first_name,
        prospect_last_name=request.prospect_last_name,
        prospect_email=request.prospect_email,
        company_id=request.company_id,
        access_token=access_token,  # Use the resolved access token
        allow_duplicate_contact=request.allow_duplicate_contact,
        allow_duplicate_opportunity=request.allow_duplicate_opportunity,
        allow_facebook_name_merge=request.allow_facebook_name_merge,
        disable_contact_timezone=request.disable_contact_timezone,
        social_urls=request.social_urls
    )
    
    user_data = {
        "first_name": request.user_first_name,
        "last_name": request.user_last_name,
        "email": request.user_email,
        "password": request.user_password,
        "phone_number": request.user_phone_number,
        "access_token": access_token  # Use the same resolved access token
    }
    
    facebook_data = {
        "user_id": request.facebook_user_id,
        "jwt_token": request.jwt_token,
        "manual_token": request.manual_token,
        "access_token": access_token  # Use the same resolved access token
    }
    
    # Call the original function
    return await complete_ghl_facebook_setup(subaccount_data, user_data, facebook_data)

async def complete_ghl_facebook_setup(
    subaccount_data: GHLSubAccountRequest,
    user_data: Dict[str, Any],
    facebook_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Complete end-to-end setup: Create sub-account -> Create user -> Connect Facebook
    
    Args:
        subaccount_data: Data for creating GHL sub-account
        user_data: Data for creating GHL user (without location_id)
        facebook_data: Data for Facebook connection (without dynamic IDs)
        
    Returns:
        Dict with complete setup results
    """
    try:
        logger.info("🚀 Starting complete GHL + Facebook setup flow")
        
        # Step 1: Create GHL Sub-account
        logger.info("📍 Step 1: Creating GHL sub-account...")
        subaccount_response = await create_ghl_subaccount(subaccount_data)
        
        if not subaccount_response.success:
            return {
                'success': False,
                'step_failed': 'subaccount_creation',
                'message': f"Failed to create sub-account: {subaccount_response.message}",
                'subaccount_response': subaccount_response.dict()
            }
        
        dynamic_location_id = subaccount_response.location_id
        logger.info(f"✅ Sub-account created. Location ID: {dynamic_location_id}")
        
        # Step 2: Create GHL User in the new sub-account
        logger.info("👤 Step 2: Creating GHL user...")
        user_request = GHLUserRequest(
            location_id=dynamic_location_id,  # Use dynamic location_id
            **user_data
        )
        user_response = await create_ghl_user(user_request)
        
        if not user_response.success:
            return {
                'success': False,
                'step_failed': 'user_creation',
                'message': f"Failed to create user: {user_response.message}",
                'subaccount_response': subaccount_response.dict(),
                'user_response': user_response.dict()
            }
        
        dynamic_user_id = user_response.user_id
        logger.info(f"✅ User created. User ID: {dynamic_user_id}")
        
        # Step 3: Connect Facebook with dynamic IDs
        logger.info("📘 Step 3: Connecting Facebook...")
        facebook_request = FacebookConnectionRequest(
            location_id=dynamic_location_id,  # Use dynamic location_id
            ghl_user_id=dynamic_user_id,     # Use dynamic user_id
            **facebook_data
        )
        facebook_response = await connect_facebook_with_dynamic_ids(facebook_request)
        
        # Return complete results
        result = {
            'success': facebook_response.success,
            'message': 'Complete GHL + Facebook setup completed successfully' if facebook_response.success else 'Setup completed with Facebook connection issues',
            'dynamic_ids': {
                'location_id': dynamic_location_id,
                'user_id': dynamic_user_id
            },
            'subaccount_response': subaccount_response.dict(),
            'user_response': user_response.dict(),
            'facebook_response': facebook_response.dict()
        }
        
        if facebook_response.success:
            logger.info("🎉 Complete setup flow successful!")
        else:
            logger.warning(f"⚠️ Setup completed but Facebook connection failed: {facebook_response.message}")
        
        return result
        
    except Exception as e:
        logger.error(f"💥 Error in complete setup flow: {str(e)}")
        return {
            'success': False,
            'step_failed': 'setup_flow',
            'message': f"Error in complete setup flow: {str(e)}"
        }
