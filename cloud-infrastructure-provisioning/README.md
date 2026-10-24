# Cloud Infrastructure Provisioning — InfraGuard

InfraGuard pairs a reusable OpenTofu/Terraform module with a small Go gate for infrastructure plan JSON. It provisions a private, encrypted, versioned AWS S3 bucket and refuses plan changes that delete resources or weaken the bucket public-access block. The project solves the common gap between writing declarative infrastructure and reviewing destructive or exposed changes before apply.

## Features and boundaries

- Go CLI validates an IaC module by running formatter, backend-free init, and validate with OpenTofu (default) or Terraform.
- `plan-check` reviews machine-readable `terraform show -json` output, rejects deletes and rejects public S3 access block regressions.
- HCL module enables all four S3 public-access protections, bucket-owner-enforced ownership, server-side AES256 encryption, versioning, and required ownership/cost tags.
- No cloud apply, credentials, API keys, state files, or personal data are included. No cloud resource is created by tests or CI.
- Go components have no third-party dependencies. OpenTofu/Terraform and the AWS provider are separate external tools/provider requirements.

## Requirements and setup

Install Go 1.23+ and either OpenTofu 1.6+ or Terraform 1.6+. The Terraform module initializes the AWS provider pinned to the `~> 5.0` minor series. Provider initialization downloads the provider plugin; do this only in a trusted environment.

```sh
cd cloud-infrastructure-provisioning
go test ./...
go vet ./...
go build -o infraguard ./cmd/infraguard
```

Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, set a globally unique bucket name, region and owner tag. Local configuration and credentials are not committed. Set `INFRA_TOOL=terraform` if using Terraform instead of the default `tofu`.

## Demonstration

```sh
go run ./cmd/infraguard help
go run ./cmd/infraguard validate terraform
tofu -chdir=terraform plan -out=portfolio.tfplan
tofu -chdir=terraform show -json portfolio.tfplan > portfolio-plan.json
go run ./cmd/infraguard plan-check portfolio-plan.json
```

The plan JSON can contain sensitive values. Keep it local, restrict its permissions, and remove it after review. Never commit `*.tfplan`, `*.tfstate`, `*.tfstate.*`, credentials, or real `terraform.tfvars`. `plan-check` does not call `apply`; operators must inspect the full plan, verify account/region/workspace, and obtain their normal change approval before applying. The policy is an additional guard, not a complete cloud security review.

## Architecture

```text
cmd/infraguard/       CLI and bounded external-tool invocation
internal/planpolicy/  plan JSON parsing, delete/public-access checks, diagnostic redaction
terraform/            AWS provider configuration and private S3 module
.github/workflows/    Go tests/vet and OpenTofu format/init/validate
```

The plan reader caps input at 32 MiB. It counts proposed creates/updates and denies deletes. The policy currently checks S3 public-access block resources only; it does not model all AWS IAM, network, KMS, drift, cost, or provider-specific risks. AWS credentials are intentionally not required in CI because CI only initializes and validates. No apply or live cloud deployment was performed.

## Verification

`go test ./...` covers safe plan summaries, destructive-plan denial, public S3 access denial, malformed JSON and credential redaction. `go vet ./...` checks the Go code. The workflow validates HCL with OpenTofu. The local Termux environment has Go but does not have OpenTofu/Terraform, so HCL/provider initialization and the real CLI validation are pending CI or a machine with the IaC tool installed.

## Contribution

Keep tests synthetic, avoid live apply in CI, and add negative policy tests for every new guard. Before changes, run `gofmt -w cmd internal`, `go test ./...`, `go vet ./...`, and `infraguard validate terraform` in an environment with OpenTofu/Terraform.
