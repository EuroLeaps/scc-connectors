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
from datetime import datetime

WORKSPACE_ID = ''
WORKSPACE_KEY = ''
LOG_ANALYTICS_WORKSPACE_TABLE_NAME = ''

# Triggered from a message on SCC Cloud Pub/Sub topic.
@functions_framework.cloud_event
def scc_pubsub_subscribe(scc_event):
    scc_finding = base64.b64decode(scc_event.data["message"]["data"]).decode()
    print("SCC Finding: ", scc_finding)

    event_message='{"time":'+ datetime.now() +',"host":"GoogleCloud","source":"SecurityCommandCenter","sourcetype":"PubSub",SCC' + '"event":'+scc_finding+'}'
    send_to_sentinel(event_message)

def send_to_sentinel(event_message):
    print("Sending log to Sentinel: ", event_message)
