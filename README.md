# GoogleCloud SecurityCommandCenter to AzureSentinel Integration

This connector allows you to send security alerts from Google Cloud Security Command Center to Microsoft Azure Sentinel Log Analytics Workspace in almost realtime.
If you have created a better version of this integration, please do contribute by creating a pull request!

### Architecture Flow

![Alt text](architecture.png?raw=true "Integration Architecture")

In the above diagram:
1. SCC streams security alerts to a PubSub queue
2. A Cloud function is setup that subscribes to the PubSub queue and gets triggered by EventArc
3. The Cloud Function calls the Data Collection API of Azure Sentinel with HMAC-SHA256 authorization
4. On the Azure Sentinel side, the Data Collection Endpoint (DCE) routes the security alert to a custom table in the Log Analytics Workspace

End-to-end latency from when an alert is triggered to when it appears in Sentinel is within a couple of seconds

### Step-by-Step Setup Instructions

#### Setting up Azure Sentinel Log Analytics Workspace

#### Create a .env file with the following environment variables
```
customer_id=YOUR_LOG_ANALYTICS_WORKSPACE_ID
shared_key=YOUR_PRIMARY_OR_SECONDARY_CLIENT_AUTHENTICATION_KEY
log_type=YOUR_CUSTOM_LOG_TABLE_NAME
```

#### Create a continuous pubsub export of send SCC Alerts

#### Create a Cloud Function in Google Cloud with code in this repository
