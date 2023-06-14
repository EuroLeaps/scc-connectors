# TODO enable APIs for pubsub, iam, scc, cloud resource manager, cloud functions, event arc, artifact registry, cloud run
# cloud build
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.34.0"
    }
  }
}

resource "google_pubsub_topic" "default" {
  name = "scc-findings-topic"
  project = "scc-tf1"
}

resource "google_scc_notification_config" "default" {
  config_id    = "scc-findings-export"
  organization = "723388619511"
  description  = "Continuous export of SCC findings to Azure Sentinel"
  pubsub_topic =  google_pubsub_topic.default.id

  streaming_config {
    filter = "state = \"ACTIVE\" AND NOT mute=\"MUTED\""
  }
}

resource "random_id" "bucket_prefix" {
  byte_length = 4
}

resource "google_service_account" "default" {
  account_id   = "scc-azure-connector-sa"
  display_name = "SCC Azure Connector Service Account"
}

resource "google_project_iam_member" "invoking" {
  project = "scc-tf1"
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.default.email}"
  depends_on = [google_service_account.default]
}

resource "google_project_iam_member" "event-receiving" {
  project = "scc-tf1"
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.default.email}"
  depends_on = [google_service_account.default]
}

resource "google_project_iam_member" "log-writer" {
  project = "scc-tf1"
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.default.email}"
  depends_on = [google_service_account.default]
}

resource "google_storage_bucket" "default" {
  name                        = "${random_id.bucket_prefix.hex}-scc-connector-source" # Every bucket name must be globally unique
  location                    = "US"
  uniform_bucket_level_access = true
}

data "archive_file" "default" {
  type        = "zip"
  output_path = "/tmp/function-source.zip"
  source_dir  = "src"
}

resource "google_storage_bucket_object" "default" {
  name   = "src.zip"
  bucket = google_storage_bucket.default.name
  source = data.archive_file.default.output_path
}

resource "google_cloudfunctions2_function" "default" {
  name        = "scc-sentinel-connector"
  location    = "us-central1"
  description = "Cloud Function to send SCC alerts to Azure Sentinel"

  build_config {
    runtime     = "python311"
    entry_point = "entry_point_function" # Set the entry point
    environment_variables = {
      
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
      AZURE_LOG_ANALYTICS_CUSTOM_TABLE = "scc_table"
    }
    ingress_settings               = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision = true
    service_account_email          = google_service_account.default.email
  }

  event_trigger {
    trigger_region = "us-central1"
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.default.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  depends_on = [
    google_service_account.default,
    google_pubsub_topic.default,
    google_scc_notification_config.default,
    google_project_iam_member.invoking,
    google_project_iam_member.event-receiving,
    google_project_iam_member.log-writer,
    ]
}