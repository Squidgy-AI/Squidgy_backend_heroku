"""
Solar Report Generation Tool
Generates comprehensive solar analysis reports using RealWave API
"""

import os
import json
import requests
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
SOLAR_API_KEY = os.getenv('SOLAR_API_KEY', 'your_solar_api_key_here')

def generate_report(address: str) -> Dict[str, Any]:
    """Get solar report for an address and extract PDF download link"""
    base_url = "https://api.realwave.com/googleSolar"
    headers = {
        "Authorization": f"Bearer {SOLAR_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{base_url}/report"
    params = {
        "address": address,
        "organizationName": "Squidgy Solar",
        "leadName": "Potential Client",
        "demo": "true"
    }
    
    try:
        response = requests.post(url, headers=headers, params=params)
        result = response.json()
        
        # Process the response for visualization
        processed_result = {}
        
        # Extract the PDF report URL
        if "rwResult" in result and result["rwResult"] and "reportURL" in result["rwResult"]:
            processed_result["reportUrl"] = result["rwResult"]["reportURL"]
        
        # Extract expiration date
        if "rwResult" in result and result["rwResult"] and "reportExpiresOn" in result["rwResult"]:
            processed_result["expiresOn"] = result["rwResult"]["reportExpiresOn"]
        
        # Extract structured data if available
        if "rwResult" in result and result["rwResult"] and "structuredDataForAgents" in result["rwResult"]:
            try:
                structured_data = json.loads(result["rwResult"]["structuredDataForAgents"])
                
                # Create a summary from the structured data
                summary_parts = []
                
                if "systemSize" in structured_data and "capacityKw" in structured_data["systemSize"]:
                    summary_parts.append(f"System size: {structured_data['systemSize']['capacityKw']:.1f} kW")
                
                if "panelCount" in structured_data:
                    summary_parts.append(f"Panel count: {structured_data['panelCount']}")
                
                if "financialSummary" in structured_data:
                    financial = structured_data["financialSummary"]
                    if "lifetimeSavings" in financial:
                        summary_parts.append(f"Lifetime savings: ${financial['lifetimeSavings']:,.2f}")
                    if "paybackPeriodYears" in financial:
                        summary_parts.append(f"Payback period: {financial['paybackPeriodYears']:.1f} years")
                
                processed_result["summary"] = ". ".join(summary_parts)
                processed_result["reportData"] = structured_data
            except json.JSONDecodeError:
                # If parsing fails, provide a basic summary
                processed_result["summary"] = f"Solar report generated for {address}."
        
        return processed_result
        
    except Exception as e:
        logger.exception(f"Error generating solar report: {str(e)}")
        return {"error": str(e)}