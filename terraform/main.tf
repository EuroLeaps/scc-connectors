terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.34.0"
    }
  }
}

resource "google_pubsub_topic" "scc_findings_topic" {
  name = "scc-findings-topic"
}

resource "google_scc_notification_config" "scc_findings_export" {
  config_id    = "scc-findings-export"
  organization = "723388619511"
  description  = "Continuous export of SCC findings to Azure Sentinel"
  pubsub_topic =  google_pubsub_topic.scc_findings_topic.id

  streaming_config {
    filter = "category = state = \"ACTIVE\" AND NOT mute=\"MUTED\""
  }
}