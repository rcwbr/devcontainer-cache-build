target "docker-client" {
  context = "https://github.com/rcwbr/dockerfile_partials.git#0.2.1"
  dockerfile = "docker-client/Dockerfile"
  contexts = {
    base_context = "docker-image://python:3.13.0"
    docker_image = "docker-image://docker:27.3.1-cli"
  }
}

target "default" {
  contexts = {
    base_context = "target:docker-client"
  }
}
