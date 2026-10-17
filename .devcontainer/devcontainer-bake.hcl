variable "devcontainer_layers" {
  default = [
    "docker-client",
    "gh",
    "zsh-base",
    "zsh-thefuck-pyenv",
    "zsh",
    "tmux",
    "hermes-webui",
    "useradd",
    "pre-commit-base",
    "pre-commit-tool-image",
    "pre-commit"
  ]
}

target "docker-client" {
  platforms = platforms
  contexts = {
    base_context = "docker-image://python:3.12.4"
  }
}
