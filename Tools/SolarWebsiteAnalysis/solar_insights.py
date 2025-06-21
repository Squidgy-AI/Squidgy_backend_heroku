"""
Solar Insights Analysis Tool
Provides comprehensive solar potential analysis for addresses using RealWave API
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

def get_insights(address: str) -> Dict[str, Any]:
    """Get solar insights for an address with enhanced visualization data"""
    base_url = "https://api.realwave.com/googleSolar"
    headers = {
        "Authorization": f"Bearer {SOLAR_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{base_url}/insights"
    params = {
        "address": address,
        "mode": "full",
        "demo": "true"
    }
    
    try:
        response = requests.post(url, headers=headers, params=params)
        result = response.json()
        
        # Process the response for visualization
        processed_result = {}
        
        # Extract location data for map visualization
        if "rwResult" in result and result["rwResult"] and "center" in result["rwResult"]:
            center = result["rwResult"]["center"]
            processed_result["location"] = {
                "latitude": center.get("latitude"),
                "longitude": center.get("longitude"),
                "address": address
            }
        
        # Extract solar potential data
        if "rwResult" in result and result["rwResult"] and "summary" in result["rwResult"]:
            summary = result["rwResult"]["summary"]
            processed_result["solarPotential"] = {
                "maxSunshineHoursPerYear": summary.get("maxSunshineHoursPerYear"),
                "minPanelCount": summary.get("minPanelCount"),
                "maxPanelCount": summary.get("maxPanelCount"),
                "idealPanelCount": summary.get("idealConfigurations", [{}])[0].get("panelCount") if summary.get("idealConfigurations") else None,
                "maxYearlyEnergy": summary.get("maxIdealYearlyEnergyDcKwh"),
                "estimatedSavings": summary.get("idealCashPurchaseSavings", {}).get("financialDetails", {}).get("lifetimeSavings")
            }
            
            # Add financial data if available
            if "financialSavingsAssumptions" in summary:
                processed_result["financials"] = {
                    "installationCost": summary.get("idealCashPurchaseSavings", {}).get("financialDetails", {}).get("initialAcquisitionCost"),
                    "annualSavings": summary.get("idealCashPurchaseSavings", {}).get("financialDetails", {}).get("averageYearlySavings"),
                    "paybackPeriodYears": summary.get("idealCashPurchaseSavings", {}).get("financialDetails", {}).get("paybackPeriodYears")
                }
        
        # Add raw building insights for detailed analysis if available
        if "rwResult" in result and result["rwResult"] and "solarResults" in result["rwResult"] and "solarPotential" in result["rwResult"]["solarResults"]:
            solar_potential = result["rwResult"]["solarResults"]["solarPotential"]
            processed_result["roofData"] = {
                "maxArrayAreaMeters2": solar_potential.get("maxArrayAreaMeters2"),
                "maxSunshineHoursPerYear": solar_potential.get("maxSunshineHoursPerYear"),
                "carbonOffsetFactorKgPerMwh": solar_potential.get("carbonOffsetFactorKgPerMwh"),
                "panelCapacityWatts": solar_potential.get("panelCapacityWatts"),
                "roofSegmentStats": solar_potential.get("roofSegmentStats", [])
            }
        
        return processed_result
        
    except Exception as e:
        logger.exception(f"Error fetching solar insights: {str(e)}")
        return {"error": str(e)}