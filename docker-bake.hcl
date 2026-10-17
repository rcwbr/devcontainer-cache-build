// Expected to be used with the shared vars.hcl that declares the
// `platforms` variable. For example:
//   docker buildx bake -f vars.hcl -f docker-bake.hcl -f github-cache-bake.hcl ...

target "docker-client" {
  platforms = platforms
  context    = "https://github.com/rcwbr/dockerfile_partials.git#0.2.1"
  dockerfile = "docker-client/Dockerfile"
  contexts = {
    base_context = "docker-image://python:3.13.0"
    docker_image = "docker-image://docker:27.3.1-cli"
  }
}

target "default" {
  platforms = platforms
  contexts = {
    base_context = "target:docker-client"
  }
}
