locals {
  gcp_organization = "YOUR_ORG_ID"
  gcp_project = "YOUR_PROJ_ID"
  azure_log_analytics_workspace_id = "YOUR_WORKSPACE_ID"
  azure_log_analytics_authentication_key = "YOUR_KEY"
  azure_log_analytics_custom_table = "scc_alerts_table"
}
  
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.34.0"
    }
  }
}

resource "google_project_service" "pubsub_api" {
  service = "pubsub.googleapis.com"
}

resource "google_project_service" "iam_api" {
  service = "iam.googleapis.com"
}

resource "google_project_service" "scc_api" {
  service = "securitycenter.googleapis.com"
}

resource "google_project_service" "resource_manager_api" {
  service = "cloudresourcemanager.googleapis.com"
}

resource "google_project_service" "cloud_functions_api" {
  service = "cloudfunctions.googleapis.com"
}

resource "google_project_service" "eventarc_api" {
  service = "eventarc.googleapis.com"
}

resource "google_project_service" "artifact_registry_api" {
  service = "artifactregistry.googleapis.com"
}

resource "google_project_service" "cloud_run_api" {
  service = "run.googleapis.com"
}

resource "google_project_service" "cloud_build_api" {
  service = "cloudbuild.googleapis.com"
}

resource "google_pubsub_topic" "default" {
  name = "scc-findings-topic"
  depends_on = [google_project_service.pubsub_api]
}

resource "google_scc_notification_config" "default" {
  config_id    = "scc-findings-export"
  organization = local.gcp_organization
  description  = "Continuous export of SCC findings to Azure Sentinel"
  pubsub_topic =  google_pubsub_topic.default.id

  streaming_config {
    filter = "state = \"ACTIVE\" AND NOT mute=\"MUTED\""
  }

  depends_on = [google_project_service.scc_api]
}

resource "random_id" "bucket_prefix" {
  byte_length = 4
}

resource "google_service_account" "default" {
  account_id   = "scc-azure-connector-sa"
  display_name = "SCC Azure Connector Service Account"
  depends_on = [google_project_service.iam_api]
}

resource "google_project_iam_member" "invoking" {
  project = local.gcp_project
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.default.email}"
  depends_on = [google_service_account.default]
}

resource "google_project_iam_member" "event-receiving" {
  project = local.gcp_project
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.default.email}"
  depends_on = [google_service_account.default]
}

resource "google_project_iam_member" "log-writer" {
  project = local.gcp_project
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.default.email}"
  depends_on = [google_service_account.default]
}

resource "google_project_iam_member" "ar-reader" {
  project = local.gcp_project
  role    = "roles/artifactregistry.reader"
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
      AZURE_LOG_ANALTYTICS_WORKSPACE_ID = local.azure_log_analytics_workspace_id
      AZURE_LOG_ANALYTICS_AUTHENTICATION_KEY = local.azure_log_analytics_authentication_key
      AZURE_LOG_ANALYTICS_CUSTOM_TABLE = local.azure_log_analytics_custom_table
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
    google_project_iam_member.ar-reader,
    google_project_service.resource_manager_api,
    google_project_service.cloud_functions_api,
    google_project_service.eventarc_api,
    google_project_service.artifact_registry_api,
    google_project_service.cloud_run_api,
    google_project_service.cloud_build_api,
    ]
}