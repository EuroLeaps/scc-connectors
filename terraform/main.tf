terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.34.0"
    }
  }
}

provider "google" {
}

resource "google_pubsub_topic" "scc_findings_topic" {
  name = "scc-findings-topic"
  project = "scc-tf"
}

resource "google_scc_notification_config" "scc_findings_export" {
  config_id    = "scc-findings-export"
  organization = "723388619511"
  description  = "Continuous export of SCC findings to Azure Sentinel"
  pubsub_topic =  google_pubsub_topic.scc_findings_topic.id

  streaming_config {
    filter = "state = \"ACTIVE\" AND NOT mute=\"MUTED\""
  }
}

data "http" "src_code" {
  url = "https://raw.githubusercontent.com/EuroAlphabets/integration-scc-sentinel/blob/main/src.zip"
}

resource "random_id" "bucket_prefix" {
  byte_length = 8
}

resource "google_storage_bucket" "default" {
  name                        = "${random_id.bucket_prefix.hex}-scc-connector-source" # Every bucket name must be globally unique
  location                    = "US"
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "default" {
  name   = "src.zip"
  bucket = google_storage_bucket.default.name
  source = data.http.config.response_body
}

resource "google_cloudfunctions2_function" "scc_sentinel_connector" {
  name        = "scc-sentinel-connector"
  location    = "us-central1"
  description = "Cloud Function to send SCC alerts to Azure Sentinel"

  build_config {
    runtime     = "python3.11"
    entry_point = "entry_point_function" # Set the entry point
    environment_variables = {
      BUILD_CONFIG_TEST = "build_test"
    }
    source {
      storage_source {
        bucket = google_storage_bucket.default.name
        object = google_storage_bucket_object.default.name
      }
    }
  }

  service_config {
    max_instance_count = 100
    min_instance_count = 0
    available_memory   = "256M"
    timeout_seconds    = 60
    environment_variables = {
      SERVICE_CONFIG_TEST = "config_test"
    }
    ingress_settings               = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision = true
    # service_account_email          = google_service_account.default.email
  }

  event_trigger {
    trigger_region = "us-central1"
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.scc_findings_topic.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }
}