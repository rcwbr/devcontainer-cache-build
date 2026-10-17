// Shared platforms variable for devcontainer-cache-build bake configs
// Usage: docker buildx bake -f vars.hcl -f docker-bake.hcl ...
//
// This ensures all bake targets that reference `platforms` build for the
// same architectures, preventing intermediate images from being built
// for the CI host platform only (which caused "exec format error" on arm64).
//
// Pattern: rcwbr/mender-client-docker docker/vars.hcl
variable "platforms" {
  type    = list(string)
  default = ["linux/amd64", "linux/arm64"]
}
