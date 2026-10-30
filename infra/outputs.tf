output "template_id" {
  description = "Runpod template id for ehr-migration-engine."
  value       = runpod_template.ehr_migration.id
}

output "template_name" {
  description = "Runpod template display name."
  value       = runpod_template.ehr_migration.name
}

output "network_volume_id" {
  description = "Network volume id (null if create_network_volume is false)."
  value       = var.create_network_volume ? runpod_network_volume.workspace[0].id : null
}

output "network_volume_data_center" {
  description = "Data center of the network volume."
  value       = var.create_network_volume ? runpod_network_volume.workspace[0].data_center : null
}

output "pod_id" {
  description = "Pod id (null if create_pod is false)."
  value       = var.create_pod ? runpod_pod.ehr_migration[0].id : null
}

output "pod_status" {
  description = "Pod lifecycle status."
  value       = var.create_pod ? runpod_pod.ehr_migration[0].status : null
}

output "pod_cost_per_hour" {
  description = "Current USD/hour while RUNNING (0 when EXITED)."
  value       = var.create_pod ? runpod_pod.ehr_migration[0].cost : null
}

output "pod_data_center_id" {
  description = "Data center where the scheduler placed the pod."
  value       = var.create_pod ? runpod_pod.ehr_migration[0].data_center_id : null
}

output "gpu_type_id" {
  description = "Configured GPU type."
  value       = var.gpu_type_id
}

output "bootstrap_hint" {
  description = "Commands to run after SSH into the pod."
  value       = <<-EOT
    # Clone (or sync) the repo onto the volume, then bootstrap:
    cd ${var.ehr_migration_root}
    bash scripts/setup_env.sh
    uv run uvicorn ehr_migration_engine.workbench.api:app --host 0.0.0.0 --port 8501
  EOT
}
