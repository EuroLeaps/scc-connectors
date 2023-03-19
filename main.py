#!/usr/bin/env python

# Copyright 2023 XXX
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
import functions_framework
import requests
import datetime
import hashlib
import hmac
import os
from dotenv import load_dotenv
load_dotenv()

# Update the customer ID to your Log Analytics workspace ID
try:
    AZURE_LOG_ANALTYTICS_WORKSPACE_ID = os.environ["AZURE_LOG_ANALTYTICS_WORKSPACE_ID"]
except KeyError:
    print("AZURE_LOG_ANALTYTICS_WORKSPACE_ID not found in env file.. Trying Secret Manager")

# For the shared key, use either the primary or the secondary Connected Sources client authentication key 
# If no name is provided as environment variable, then scc_table will be used as default
try: 
    AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY = os.environ["AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY"]
except KeyError:
    print("AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY not found in env file.. Trying Secret Manager")

# The name of the Log Analytics custom table where SCC Alerts will be stored
AZURE_LOG_ANALYTICS_CUSTOM_TABLE = os.environ.get("AZURE_LOG_ANALYTICS_CUSTOM_TABLE", "scc_table")

# Triggered from a message on SCC Cloud Pub/Sub topic.
@functions_framework.cloud_event
def entry_point_function(scc_event):
    scc_finding = base64.b64decode(scc_event.data["message"]["data"]).decode()
    print("SCC Finding Received: ", scc_finding)

    logdata='{"host":"GoogleCloud","source":"SecurityCommandCenter","RawAlert":'+scc_finding+'}'
    send_to_sentinel(AZURE_LOG_ANALTYTICS_WORKSPACE_ID, AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY, logdata, AZURE_LOG_ANALYTICS_CUSTOM_TABLE)

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
def send_to_sentinel(law_id, auth_key, logdata, table_name):
    print("Sending SCC Alert log to Azure Sentinel..")
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
        print('Sentinel API Accepted: ', response.status_code)
    else:
        print("Error calling Sentinel API, response code: {}".format(response.status_code))