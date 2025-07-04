# Solar Sub-Account Snapshot Cloning

## Overview

This module provides functionality for cloning Solar sub-accounts in GoHighLevel by using a combination of manual location cloning and workflow documentation. Due to API restrictions in GoHighLevel that prevent direct workflow cloning for Solar sub-accounts, this solution focuses on:

1. Creating new sub-accounts via the location API
2. Documenting workflows from the source location for manual recreation
3. Providing a fallback mechanism to attempt snapshot imports (though these are currently blocked by the API)

## API Restrictions & Workarounds

Through extensive testing, we've confirmed that GoHighLevel Solar sub-accounts have specific API restrictions:

**Working Endpoints:**
- ✅ List workflows: `GET /v1/workflows` (with Solar token)
- ✅ Create locations: `POST /v1/locations/` (with Agency API key)

**Blocked Endpoints (all return 404):**
- ❌ Get individual workflow details: `/v1/workflows/{id}`
- ❌ Duplicate workflow: `/v1/workflows/{id}/duplicate`
- ❌ Copy workflow: `/v1/workflows/{id}/copy`
- ❌ Clone workflow: `/v1/workflows/{id}/clone`
- ❌ Create workflow with source reference
- ❌ Snapshot import endpoints (all tested variants)

## Solution Architecture

The solution consists of several components:

1. **Solar Clone Router** (`solar_clone_router.py`): FastAPI router that exposes endpoints for Solar sub-account cloning
2. **Workflow Snapshot Helper** (`workflow_snapshot_helper.py`): Utility to document workflows as JSON snapshots
3. **Manual Clone Module** (`manual_clone.py`): Functions to manually clone locations and custom values
4. **Models** (`solar_clone_models.py`): Pydantic models for API requests and responses

## API Endpoints

### Clone Solar Sub-Account

```
POST /api/ghl/solar-clone
```

**Request Body:**
```json
{
  "source_location_id": "string",
  "target_name": "string",
  "snapshot_id": "string", // Optional
  "document_workflows": true // Optional, defaults to true
}
```

**Response:**
```json
{
  "success": true,
  "new_location_id": "string",
  "new_location_name": "string",
  "snapshot_import_attempted": false,
  "snapshot_import_success": false,
  "workflows_documented": 5,
  "error": null,
  "details": {}
}
```

### List Solar Workflows

```
POST /api/ghl/solar-workflows
```

**Request Body:**
```json
{
  "location_id": "string"
}
```

**Response:**
```json
{
  "success": true,
  "workflows": [
    {
      "id": "string",
      "name": "string",
      "status": "string",
      "createdAt": "string",
      "updatedAt": "string"
    }
  ],
  "count": 5,
  "error": null
}
```

## Workflow Documentation

When `document_workflows` is set to `true` (default), the system will:

1. Retrieve all workflows from the source location
2. Create a JSON snapshot for each workflow
3. Save these snapshots to a timestamped directory under `workflow_snapshots/`

These snapshots can then be used as a reference for manually recreating workflows in the new sub-account.

## Usage Example

```python
import requests

# Clone a Solar sub-account
response = requests.post(
    "http://localhost:8000/api/ghl/solar-clone",
    json={
        "source_location_id": "JUTFTny8EXQOSB5NcvAA",
        "target_name": "New Solar Account"
    }
)

result = response.json()
print(f"New location created: {result['new_location_id']}")
print(f"Workflows documented: {result['workflows_documented']}")
```

## Testing

A test script (`test_solar_clone_api.py`) is provided to verify the functionality of the Solar clone API. Run it with:

```bash
python test_solar_clone_api.py
```

## Future Improvements

1. **Monitor API Changes**: Regularly check if GoHighLevel restores or introduces snapshot import/create endpoints
2. **Workflow Recreation Automation**: Develop tools to automate the recreation of workflows using the documented JSON snapshots
3. **UI Integration**: Build a user interface for triggering cloning workflows and monitoring progress
4. **Enhanced Error Handling**: Add more robust error handling and recovery mechanisms

## Notes

- The solution uses both the Solar-specific access token and the Agency API key for different operations
- Workflow documentation is the most reliable fallback given the current API restrictions
- All API calls are logged for troubleshooting purposes
