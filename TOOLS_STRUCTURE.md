# 🛠️ Tools Structure Documentation

## 📁 Organized Folder Structure

```
SquidgyBackend/
├── Tools/
│   ├── __init__.py                    # Main Tools module
│   ├── SolarWebsiteAnalysis/          # Solar analysis tools
│   │   ├── __init__.py
│   │   ├── solar_insights.py          # get_insights()
│   │   ├── solar_data_layers.py       # get_data_layers()
│   │   └── solar_report.py            # generate_report()
│   ├── Website/                       # Website analysis tools
│   │   ├── __init__.py
│   │   └── web_scrape.py              # screenshot & favicon
│   └── GHL/                           # GoHighLevel CRM tools
│       ├── __init__.py
│       ├── Contacts/                  # Contact management
│       ├── Appointments/              # Appointment management
│       ├── Calendars/                 # Calendar management
│       ├── Users/                     # User management
│       ├── Sub_Accounts/              # Sub-account management
│       ├── access_token.py            # Authentication
│       └── environment/               # Configuration
├── tools_connector.py                 # Central tools manager
├── tools_integration_example.py       # Integration guide
└── TOOLS_STRUCTURE.md                # This documentation
```

## 🚀 How to Use

### Import all tools:
```python
from tools_connector import tools

# Solar Analysis
result = tools.get_solar_insights(address="123 Main St")
result = tools.get_solar_data_layers(address="123 Main St") 
result = tools.generate_solar_report(address="123 Main St")

# Website Analysis
result = await tools.capture_website_screenshot_async(url="https://example.com")
result = await tools.get_website_favicon_async(url="https://example.com")

# GHL CRM
result = tools.create_contact(first_name="John", last_name="Doe", email="john@example.com", phone="+1234567890")
result = tools.get_contact(contact_id="123")
result = tools.create_appointment(...)
```

### Import specific modules:
```python
from Tools.SolarWebsiteAnalysis import get_insights, get_data_layers, generate_report
from Tools.Website import capture_website_screenshot, get_website_favicon
from Tools.GHL import create_contact, get_contact, create_appointment
```

### Agent-specific tools:
```python
from tools_connector import get_tools_for_agent

presales_tools = get_tools_for_agent('presaleskb')
# Returns: ['get_solar_insights', 'get_solar_data_layers', 'generate_solar_report', 'capture_website_screenshot', 'get_website_favicon', 'create_contact', 'get_contact', 'create_appointment']

leadgen_tools = get_tools_for_agent('leadgenkb')  
# Returns: ['capture_website_screenshot', 'get_website_favicon', 'create_contact', 'get_contact']

social_tools = get_tools_for_agent('socialmediakb')
# Returns: ['capture_website_screenshot', 'get_website_favicon', 'create_contact', 'get_contact']
```

## 🎯 Benefits

1. **Organized Structure** - Each tool category in its own folder
2. **Easy Imports** - Simple `from tools_connector import tools`
3. **Agent-Specific Tools** - Defined which tools each agent can use
4. **Reduced main.py** - Move scattered functions to organized modules
5. **Better Performance** - Faster imports and cleaner code organization
6. **No Import Errors** - All modules properly configured with __init__.py files

## ✅ Test Results

All imports working successfully:
- ✅ SolarWebsiteAnalysis tools imported successfully
- ✅ Website tools imported successfully  
- ✅ GHL tools imported successfully
- ✅ All Tools modules imported successfully
- ✅ tools_connector imported successfully

## 🔄 Migration from main.py

Instead of having scattered functions in main.py, replace with:

### Old way:
```python
# 200+ lines of solar functions in main.py
def get_insights(address: str):
    # 80 lines of code...

def get_datalayers(address: str):
    # 80 lines of code...
```

### New way:
```python
from tools_connector import tools

@app.get("/api/solar/insights")
async def solar_insights_endpoint(address: str):
    return tools.get_solar_insights(address)

@app.get("/api/website/screenshot")  
async def website_screenshot_endpoint(url: str):
    return await tools.capture_website_screenshot_async(url)
```

## 📝 Next Steps

1. Update main.py to import from `tools_connector`
2. Replace existing function calls with new organized imports
3. Test locally with `python3 main.py`
4. Deploy to Heroku once confirmed working

This structure provides perfect efficiency and organization for your agent tools!