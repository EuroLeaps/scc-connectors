#!/usr/bin/env python

# Copyright 2023 EuroLeaps
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import functions_framework
import requests
import datetime
import hashlib
import hmac
import os
from google.cloud import secretmanager
import google.cloud.logging
from dotenv import load_dotenv
load_dotenv()

# Import the Datadog API client
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.events_api import EventsApi
from datadog_api_client.v1.model.event_create_request import EventCreateRequest

datadog = False
azure_sentinel = False

# Setup logging
client = google.cloud.logging.Client()
logger = client.logger("SCC_Sentinel_Connector")

PROJECT_ID = os.environ.get("PROJECT_ID", "")

def get_secret_from_secret_manager(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    resource_name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": resource_name})
    except Exception as e:
        logger.log_text(f"Error in retreiving secret: {secret_id}: {e.message}, {e.args}", severity="ERROR")
    secret_value = response.payload.data.decode('UTF-8')
    return secret_value

try:
    DD_API_KEY = os.environ["DD_API_KEY"]
    datadog = True
    logger.log_text(f"DD_API_KEY found {len(DD_API_KEY)}. DataDog integration activated.")
except KeyError:
    logger.log_text("DD_API_KEY not found in env file. DataDog integration disabled.")

try:
    AZURE_LOG_ANALTYTICS_WORKSPACE_ID = os.environ["AZURE_LOG_ANALTYTICS_WORKSPACE_ID"]
except KeyError:
    logger.log_text("AZURE_LOG_ANALTYTICS_WORKSPACE_ID not found in env file.. Trying Secret Manager")
    if(PROJECT_ID != ""):
        logger.log_text('PROJECT_ID ', PROJECT_ID)
        AZURE_LOG_ANALTYTICS_WORKSPACE_ID = get_secret_from_secret_manager("AZURE_LOG_ANALTYTICS_WORKSPACE_ID")
        logger.log_text('Retrieved AZURE_LOG_ANALTYTICS_WORKSPACE_ID')
    else:
        logger.log_text("PROJECT_ID not found in env file.. Cannot use Secret Manager. Exiting..")

# For the shared key, use either the primary or the secondary Connected Sources client authentication key 
# If no name is provided as environment variable, then scc_table will be used as default
try: 
    AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY = os.environ["AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY"]
except KeyError:
    logger.log_text("AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY not found in env file.. Trying Secret Manager")
    if(PROJECT_ID != ""):
        logger.log_text(f'PROJECT_ID {PROJECT_ID}')
        AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY = get_secret_from_secret_manager("AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY")
        logger.log_text('Retrieved AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY')
    else:
        logger.log_text("PROJECT_ID not found in env file.. Cannot use Secret Manager. Exiting..")

# The name of the Log Analytics custom table where SCC Alerts will be stored
AZURE_LOG_ANALYTICS_CUSTOM_TABLE = os.environ.get("AZURE_LOG_ANALYTICS_CUSTOM_TABLE", "scc_table")

if AZURE_LOG_ANALTYTICS_WORKSPACE_ID != "" and AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY != "":
    azure_sentinel = True
    logger.log_text(f'Retrieved Azure Log Analytics WorkspaceID {len(AZURE_LOG_ANALTYTICS_WORKSPACE_ID)} and Key {len(AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY)} successfully. Custom table: {AZURE_LOG_ANALYTICS_CUSTOM_TABLE} GCP ProjectID: {PROJECT_ID}. Azure integration activated.')
else:
    logger.log_text(f'Cannot retrieved Azure Log Analytics WorkspaceID or Key successfully. Azure integration disabled.')

# Triggered from a message on SCC Cloud Pub/Sub topic.
@functions_framework.cloud_event
def entry_point_function(scc_event):
    try:
        scc_finding = base64.b64decode(scc_event.data["message"]["data"]).decode(errors = 'ignore')
        scc_finding_json = json.loads(scc_finding)
        
        if azure_sentinel:
            send_to_sentinel(AZURE_LOG_ANALTYTICS_WORKSPACE_ID, AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY, scc_finding_json, AZURE_LOG_ANALYTICS_CUSTOM_TABLE)
        if datadog:
            send_to_datadog(scc_finding_json)
    except Exception as e:
        logger.log_text(f'Error in SCC-Sentinel connector: Type {type(e)} Args {e.args} Object {e}', severity="ERROR")

# Build the API signature
def build_signature(customer_id, shared_key, date, content_length, method, content_type, resource):
    x_headers = 'x-ms-date:' + date
    string_to_hash = method + "\n" + str(content_length) + "\n" + content_type + "\n" + x_headers + "\n" + resource
    bytes_to_hash = bytes(string_to_hash, encoding="utf-8")  
    decoded_key = base64.b64decode(shared_key)
    encoded_hash = base64.b64encode(hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()).decode()
    authorization = "SharedKey {}:{}".format(customer_id,encoded_hash)
    return authorization

# Build and send a request to the POST API
def send_to_sentinel(law_id, auth_key, scc_finding_json, table_name):
    logger.log_text("Sending SCC Alert log to Azure Sentinel..")

    logdata = { "host":"GoogleCloud",
                "source":"SecurityCommandCenter",
                "RawAlert": scc_finding_json
                }
    logdata = json.dumps(logdata)
    logger.log_text(f"SCC Finding json: {logdata}")
    
    method = 'POST'
    content_type = 'application/json'
    resource = '/api/logs'
    rfc1123date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    content_length = len(logdata)
    signature = build_signature(law_id, auth_key, rfc1123date, content_length, method, content_type, resource)
    uri = 'https://' + law_id + '.ods.opinsights.azure.com' + resource + '?api-version=2016-04-01'

    headers = {
        'content-type': content_type,
        'Authorization': signature,
        'Log-Type': table_name,
        'x-ms-date': rfc1123date
    }

    response = requests.post(uri, data=logdata, headers=headers)
    if (response.status_code >= 200 and response.status_code <= 299):
        logger.log_text(f'Sentinel API call successful with response code {response.status_code}')
    else:
        logger.log_text(f"Error calling Sentinel API, response code: {response.status_code}", severity="ERROR")

def send_to_datadog(scc_finding_json):
    body = EventCreateRequest(
        title="Google Cloud Security Command Center Alert: " + scc_finding_json['finding']['category'],
        text=json.dumps(scc_finding_json),
        alert_type="warning",
        source_type_name="Google Cloud Platform",
        tags=[
            "source:Security Command Center",
        ],
    )

    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api_instance = EventsApi(api_client)
        response = api_instance.create_event(body=body)

    logger.log_text(f'DataDog API response: {response}')