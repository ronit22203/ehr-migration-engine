resource "runpod_network_volume" "workspace" {
  count = var.create_network_volume ? 1 : 0

  name        = var.network_volume_name
  size        = var.network_volume_size_gb
  data_center = var.network_volume_data_center
  type        = var.network_volume_type
}
