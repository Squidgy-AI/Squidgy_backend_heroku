import requests

def call_webhook(message, userid=None, sessionid=None, workflow="w1", agent="soma", tool="t1"):
    """
    Makes a POST request to the webhook endpoint.
    
    Args:
        message (str): The message to send to the webhook
        userid (str, optional): The user ID parameter. Defaults to None.
        sessionid (str, optional): The session ID parameter. Defaults to None.
        workflow (str, optional): The workflow parameter. Defaults to "w1".
        agent (str, optional): The agent parameter. Defaults to "soma".
        tool (str, optional): The tool parameter. Defaults to "t1".
        
    Returns:
        dict: The JSON response from the webhook, or None if the request failed
    """
    base_url = "https://n8n.theaiteam.uk/webhook/agentshub"
    
    # Prepare parameters
    params = {
        "workflow": workflow,
        "agent": agent,
        "message": message,
        "tool": tool
    }
    
    # Add optional parameters if provided
    if userid is not None:
        params["userid"] = userid
    
    if sessionid is not None:
        params["sessionid"] = sessionid
    
    try:
        # Make the POST request
        response = requests.post(base_url, params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                # Return text if not JSON
                return {"text": response.text}
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None

# Example usage
if __name__ == "__main__":
    result = call_webhook("hello", userid="user123", sessionid="sess456")
    print(result)