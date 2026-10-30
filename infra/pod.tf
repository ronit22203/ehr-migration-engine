resource "runpod_pod" "ehr_migration" {
  count = var.create_pod ? 1 : 0

  name        = var.pod_name
  template_id = runpod_template.ehr_migration.id

  gpu_type_id = var.gpu_type_id
  gpu_count   = var.gpu_count
  cloud       = var.cloud
  disk        = var.container_disk_gb

  # Empty list clears inheritance of an old exact CUDA filter from the template.
  # A non-empty exact list with no matching hosts returns 400 capacity errors.
  allowed_cuda_versions = var.allowed_cuda_versions
  desired_state         = var.desired_state

  start_ssh     = true
  start_jupyter = false

  ports = var.ports

  env = {
    EHR_MIGRATION_ROOT = var.ehr_migration_root
    OLLAMA_HOST        = "0.0.0.0"
    NEO4J_AUTH         = "neo4j/password"
  }

  # Network volume outlives the pod (models, data/, HF/Ollama caches).
  # Pins placement to the volume's data center.
  data_center_ids = var.create_network_volume ? [
    runpod_network_volume.workspace[0].data_center
  ] : null

  network_volumes = var.create_network_volume ? [{
    volume_id = runpod_network_volume.workspace[0].id
    path      = var.network_volume_mount_path
  }] : null

  # When no network volume, use host-local persistent storage at /workspace.
  persistent_volume = var.create_network_volume ? null : {
    size = var.network_volume_size_gb
    path = var.network_volume_mount_path
  }
}
