# Formalized Runpod pod template for the EHR migration engine.
# Single source of truth for image, disk, ports, env, and SSH flags.
# The pod resource references this template via template_id.

resource "runpod_template" "ehr_migration" {
  name  = var.template_name
  image = var.image
  disk  = var.container_disk_gb

  category   = "NVIDIA"
  serverless = false
  public     = false

  start_ssh     = true
  start_jupyter = false

  # Must be [] (not null) to clear a previously set exact CUDA filter on the template.
  allowed_cuda_versions = var.allowed_cuda_versions

  # Host-local mount only when we are not attaching a network volume on the
  # pod (network_volumes and persistent_volume are mutually exclusive).
  persistent_volume = var.create_network_volume ? null : {
    size = var.network_volume_size_gb
    path = var.network_volume_mount_path
  }

  ports = var.ports

  env = {
    EHR_MIGRATION_ROOT = var.ehr_migration_root
    OLLAMA_HOST        = "0.0.0.0"
    NEO4J_AUTH         = "neo4j/password"
  }
}
