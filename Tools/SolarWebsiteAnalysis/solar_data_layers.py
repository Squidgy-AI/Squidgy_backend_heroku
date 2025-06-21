"""
Solar Data Layers Tool
Provides visual solar analysis layers for addresses using RealWave API
"""

import os
import requests
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
SOLAR_API_KEY = os.getenv('SOLAR_API_KEY', 'your_solar_api_key_here')

def get_data_layers(address: str) -> Dict[str, Any]:
    """Get solar data layers for an address and process images for display"""
    base_url = "https://api.realwave.com/googleSolar"
    headers = {
        "Authorization": f"Bearer {SOLAR_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{base_url}/dataLayers"
    params = {
        "address": address,
        "renderPanels": "true",
        "fileFormat": "jpeg",
        "demo": "true"
    }
    
    try:
        response = requests.post(url, headers=headers, params=params)
        result = response.json()
        
        # Process the response for visualization
        processed_result = {}
        
        # Process image URLs if they exist
        if "rwResult" in result:
            rwResult = result["rwResult"]
            layers = []
            
            # Define the layers to extract and their display names
            layer_mappings = {
                "satelliteImageURL": {
                    "name": "Satellite View",
                    "description": "Satellite image of the property"
                },
                "compositedMarkedRGBURL": {
                    "name": "Property Marker",
                    "description": "Satellite image with property marked"
                },
                "compositedAnnualFluxURL": {
                    "name": "Solar Potential",
                    "description": "Annual solar energy potential overlay"
                },
                "compositedMarkedPanelsURL": {
                    "name": "Solar Panel Layout",
                    "description": "Recommended solar panel configuration"
                }
            }
            
            # Extract layers that exist in the response
            for key, info in layer_mappings.items():
                if key in rwResult and rwResult[key]:
                    layers.append({
                        "name": info["name"],
                        "description": info["description"],
                        "imageUrl": rwResult[key],
                        "type": key.replace("URL", "").lower()
                    })
            
            processed_result["layers"] = layers
            
            # Add expiration info if available
            if "imagesExpireOn" in rwResult:
                processed_result["expiresOn"] = rwResult["imagesExpireOn"]
        
        return processed_result
        
    except Exception as e:
        logger.exception(f"Error fetching solar data layers: {str(e)}")
        return {"error": str(e)}