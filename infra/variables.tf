variable "template_name" {
  type        = string
  description = "Runpod template display name."
  default     = "ehr-migration-engine"
}

variable "pod_name" {
  type        = string
  description = "Runpod pod display name."
  default     = "ehr-migration-engine"
}

variable "image" {
  type        = string
  description = "Base container image (CUDA + Python 3.11)."
  default     = "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04"
}

variable "gpu_type_id" {
  type        = string
  description = "GPU catalog id (see ./check_availability.sh)."
  default     = "NVIDIA GeForce RTX 5080"
}

variable "gpu_count" {
  type        = number
  description = "Number of GPUs."
  default     = 1
}

variable "cloud" {
  type        = string
  description = "Cloud tier: SECURE or COMMUNITY. COMMUNITY usually has more 4090 capacity."
  default     = "COMMUNITY"

  validation {
    condition     = contains(["SECURE", "COMMUNITY"], var.cloud)
    error_message = "cloud must be SECURE or COMMUNITY."
  }
}

variable "container_disk_gb" {
  type        = number
  description = "Ephemeral container disk size in GB."
  default     = 50
}

variable "network_volume_name" {
  type        = string
  description = "Network volume name for /workspace."
  default     = "ehr-migration-workspace"
}

variable "network_volume_size_gb" {
  type        = number
  description = "Network volume size in GB (models, data/, caches)."
  default     = 100
}

variable "network_volume_data_center" {
  type        = string
  description = "Data center for the network volume (pins the pod). Example: EU-RO-1, US-KS-2."
  default     = "US-KS-2"
}

variable "network_volume_type" {
  type        = string
  description = "Storage tier: STANDARD or HIGH_PERFORMANCE."
  default     = "HIGH_PERFORMANCE"
}

variable "network_volume_mount_path" {
  type        = string
  description = "Mount path inside the pod for the network volume."
  default     = "/workspace"
}

variable "allowed_cuda_versions" {
  type        = list(string)
  description = "Exact CUDA host versions for placement. Empty list = any (recommended). Non-empty exact matches often cause capacity errors."
  default     = []
}

variable "ports" {
  type        = list(string)
  description = "Exposed ports as PORT/PROTOCOL."
  default = [
    "22/tcp",
    "8501/http",
    "7474/http",
    "7687/tcp",
    "11434/http",
  ]
}

variable "ehr_migration_root" {
  type        = string
  description = "Repo path inside the pod (on the network volume)."
  default     = "/workspace/ehr-migration-engine"
}

variable "desired_state" {
  type        = string
  description = "Managed pod lifecycle: RUNNING or EXITED."
  default     = "RUNNING"

  validation {
    condition     = contains(["RUNNING", "EXITED"], var.desired_state)
    error_message = "desired_state must be RUNNING or EXITED."
  }
}

variable "create_pod" {
  type        = bool
  description = "When false, only create the template and network volume (no billing pod)."
  default     = true
}

variable "create_network_volume" {
  type        = bool
  description = "When false, skip network volume (pod uses template persistent_volume only)."
  default     = true
}
