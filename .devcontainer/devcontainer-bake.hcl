variable "devcontainer_layers" {
  default = [
    "docker-client",
    "useradd",
    "pre-commit-base",
    "pre-commit-tool-image",
    "pre-commit"
  ]
}

target "docker-client" {
  contexts = {
    base_context = "docker-image://python:3.12.4"
  }
}
