# Runpod infra (RTX 4090)

Terraform for an EHR Migration Engine GPU pod on [Runpod](https://www.runpod.io/), plus the in-pod bootstrap script at [`../scripts/setup_env.sh`](../scripts/setup_env.sh).

Runpod **does not support Docker-in-Docker or Docker Compose** inside pods. Neo4j and Ollama are installed natively by the bootstrap script. Keep using [`../docker-compose.yml`](../docker-compose.yml) on a laptop only.

## Formalized pod / template config

| Setting | Value |
| --- | --- |
| Template name | `ehr-migration-engine` |
| Image | `runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04` |
| GPU | `NVIDIA GeForce RTX 5080` × 1 (fallback; prefer 4090 when stock returns) |
| Cloud | `COMMUNITY` (use `SECURE` when stock allows) |
| Container disk | 50 GB |
| Storage | 100 GB host-local `/workspace` (network volume optional, needs ≥ $5) |
| Ports | `22/tcp`, `8501/http`, `7474/http`, `7687/tcp`, `11434/http` |
| SSH | on |
| Jupyter | off |
| CUDA hosts | any (do not pin exact versions unless required) |
| Env | `EHR_MIGRATION_ROOT`, `OLLAMA_HOST`, `NEO4J_AUTH` |

These defaults live in [`variables.tf`](variables.tf) and [`terraform.tfvars.example`](terraform.tfvars.example).

## Prerequisites

- Terraform **1.6+**
- A Runpod API key
- An SSH public key registered on your Runpod account (for `start_ssh`)

## Apply

```bash
cd infra
export RUNPOD_API_KEY="YOUR_API_KEY"

cp terraform.tfvars.example terraform.tfvars
# Edit network_volume_data_center if needed (must have 4090 Secure capacity).

terraform init
terraform plan
terraform apply
```

If `terraform init` fails verifying the Runpod provider signature (`openpgp: invalid data`), install from the GitHub release into a plugin mirror and pass `-plugin-dir`:

```bash
# Example (darwin_arm64); adjust OS/arch as needed.
mkdir -p /tmp/tf-plugins/registry.terraform.io/runpod/runpod/2.0.0/darwin_arm64
curl -fsSL -o /tmp/runpod-provider.zip \
  https://github.com/runpod/terraform-provider-runpod/releases/download/v2.0.0/terraform-provider-runpod_2.0.0_darwin_arm64.zip
unzip -o /tmp/runpod-provider.zip -d /tmp/tf-plugins/registry.terraform.io/runpod/runpod/2.0.0/darwin_arm64
terraform init -plugin-dir=/tmp/tf-plugins
```

Auth is via `RUNPOD_API_KEY` only. Do not put the key in `*.tfvars`.

Useful knobs:

- `create_pod = false` — publish template only (no hourly GPU burn)
- `desired_state = "EXITED"` — keep the pod in config but stopped
- `create_network_volume = false` — use host-local `persistent_volume` at `/workspace` (default in the example). Network volumes need **≥ $5** account balance; without that the API returns 400. Host-local storage dies with the host — re-pull models after a migrate.
- If create fails with **no instances available**:
  1. Ensure `allowed_cuda_versions = []` and re-apply (clears a CUDA filter left on the template from an earlier apply).
  2. Run `./check_availability.sh` and set `gpu_type_id` to a GPU showing `HIGH`/`MEDIUM`.
  3. Or retry later / deploy from the [console](https://www.runpod.io/console/pods).

Destroy when finished so billing stops:

```bash
terraform destroy
```

## After the pod is up

1. SSH into the pod from the Runpod console (or the printed SSH command).
2. Clone or sync this repo onto the volume:

   ```bash
   cd /workspace
   git clone <your-remote> ehr-migration-engine
   # or: rsync / scp the tree to /workspace/ehr-migration-engine
   ```

3. Bootstrap dependencies (uv, Node 22, Neo4j 5.x, Ollama + `medgemma:4b`, workbench UI):

   ```bash
   cd /workspace/ehr-migration-engine
   bash scripts/setup_env.sh
   ```

   Optional flags: `SKIP_OLLAMA_PULL=1`, `SKIP_NEO4J=1`, `SKIP_UI_BUILD=1`.

4. Serve the workbench so Runpod’s HTTP proxy can reach it. The local Makefile binds `127.0.0.1`; on Runpod bind all interfaces:

   ```bash
   uv run uvicorn ehr_migration_engine.workbench.api:app --host 0.0.0.0 --port 8501
   ```

   Open the Runpod **8501/http** proxy URL for the review UI.

5. Run pipeline stages as usual: `make ocr`, `make extract`, `make normalize`, `make graph`, `make fhir`.

## Layout

```
infra/
  versions.tf              # terraform >= 1.6, runpod/runpod ~> 2.0
  providers.tf
  variables.tf
  template.tf              # runpod_template
  volumes.tf               # runpod_network_volume
  pod.tf                   # runpod_pod (RTX 4090)
  outputs.tf
  terraform.tfvars.example
  README.md
```

Provider docs: [Manage Runpod infrastructure with Terraform](https://docs.runpod.io/integrations/terraform/overview).
