# GoogleCloud-SecurityCommandCenter-AzureSentinel-Integration

This connector allows you to send security alerts from Google Cloud Security Command Center to Microsoft Azure Sentinel Log Analytics Workspace in almost realtime.

## Architecture


## Step-by-Step Setup Instructions

### Setting up Azure Sentinel Log Analytics Workspace

### Create a .env file with the following environment variables
```
customer_id=YOUR_LOG_ANALYTICS_WORKSPACE_ID
shared_key=YOUR_PRIMARY_OR_SECONDARY_CLIENT_AUTHENTICATION_KEY
log_type=YOUR_CUSTOM_LOG_TABLE_NAME
```

### Create a continuous pubsub export of send SCC Alerts

### Create a Cloud Function in Google Cloud with code in this repository
