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
customer_id = os.environ["customer_id"]

# For the shared key, use either the primary or the secondary Connected Sources client authentication key   
shared_key = os.environ["shared_key"]

# The log type is the name of the event that is being submitted
log_type = os.environ["log_type"]

# Triggered from a message on SCC Cloud Pub/Sub topic.
@functions_framework.cloud_event
def scc_pubsub_subscribe(scc_event):
    scc_finding = base64.b64decode(scc_event.data["message"]["data"]).decode()
    print("SCC Finding: ", scc_finding)

    logdata='{"host":"GoogleCloud","source":"SecurityCommandCenter","RawAlert":'+scc_finding+'}'
    send_to_sentinel(customer_id, shared_key, logdata, log_type)

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
def send_to_sentinel(customer_id, shared_key, logdata, log_type):
    print("Sending log to Sentinel: ", logdata)
    method = 'POST'
    content_type = 'application/json'
    resource = '/api/logs'
    rfc1123date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    content_length = len(logdata)
    signature = build_signature(customer_id, shared_key, rfc1123date, content_length, method, content_type, resource)
    uri = 'https://' + customer_id + '.ods.opinsights.azure.com' + resource + '?api-version=2016-04-01'

    headers = {
        'content-type': content_type,
        'Authorization': signature,
        'Log-Type': log_type,
        'x-ms-date': rfc1123date
    }

    response = requests.post(uri, data=logdata, headers=headers)
    if (response.status_code >= 200 and response.status_code <= 299):
        print('Sentinel API Accepted: ', response.status_code)
    else:
        print("Error calling Sentinel API, response code: {}".format(response.status_code))