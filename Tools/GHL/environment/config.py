class Config:
    # API Endpoints
    appointment_url = "https://services.leadconnectorhq.com/calendars/events/appointments/"
    sub_acc_url = "https://services.leadconnectorhq.com/locations/"
    calendars_url = "https://services.leadconnectorhq.com/calendars/"
    users_url = "https://services.leadconnectorhq.com/users/"
    contacts_url = "https://services.leadconnectorhq.com/contacts/"
    auth_token_url = "https://services.leadconnectorhq.com/oauth/token"
    
    # Access Tokens
    Nestle_access_token = "pit-98e16ccd-8c1e-4e6f-a96d-57ef6cb2cf62"
    Nestle_contacts_convo_token = "pit-1fc00b1f-35e7-4a86-90c0-ccdeefd935b0"
    
    # Default Sub-Account Creation Parameters
    default_client_name = "Test Dynamic Client LLC"
    default_phone_number = "+1234567890"
    default_address = "123 Test Street"
    default_city = "Test City"
    default_state = "CA"
    default_country = "US"
    default_postal_code = "12345"
    default_website = "https://testclient.com"
    default_timezone = "US/Pacific"
    
    # Default Prospect Information
    default_prospect_first_name = "John"
    default_prospect_last_name = "Doe"
    default_prospect_email = "john.doe@testclient.com"
    
    # Default User Creation Parameters
    default_user_first_name = "Admin"
    default_user_last_name = "User"
    default_user_email = "Somashekhar34@gmail.com" # Will have random number appended for uniqueness
    default_user_password = "Dummy@123"
    default_user_phone_number = "+1234567891"
    default_account_type = "account"
    default_role = "user"
    
    # Default Facebook Connection Parameters
    default_facebook_user_id = "test_facebook_user_123"
    default_manual_token = True

# Export the Config class as a module
config = Config()