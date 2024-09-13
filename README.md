# devcontainer-cache-build

Build devcontainer images using remote Docker cache. This repo contains definitions for a complete workflow around the devcontainer image, including configuration for local building and cache population by CI pipeline.

TODO describe workflow.

## Usage

### Initialize script

The initialize script replaces `build` in `.devcontainer/devcontainer.json`, and computes appropriate configuration for the devcontainer image Docker build command.

#### Initialize script basic usage

To use the script, add `"initializeCommand": "curl https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/0.1.0/initialize | bash"` to your `devcontainer.json`. For example, you might replace

```jsonc
{
  ...
  "build": {
    "dockerfile": "Dockerfile"
  },
  ...
}
```

with 

```jsonc
{
  ...
  "initializeCommand": ".devcontainer/initialize",
  "image": "my-project-devcontainer"
  ...
}
```

and `.devcontainer/initialize`:

```bash
#!/bin/bash

export DEVCONTAINER_IMAGE=my-project-devcontainer
curl https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/0.1.0/initialize | bash
```

#### Initialize script specific version usage

A specific version of the script may be used by adjusting the URL in the `curl` command. The format is `https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/<version ref>/initialize`, where `<version ref>` may be any valid version reference from this repo.

#### Initialize script bake usage

To use the initialize script with [bake](https://docs.docker.com/reference/cli/docker/buildx/bake/), the recommended usage is to set the `DEVCONTAINER_BUILD_ADDITIONAL_ARGS` and `DEVCONTAINER_DEFINITION_FILES` vars to leverage bake file partials as defined in the [dockerfile-partials repository](https://github.com/rcwbr/dockerfile-partials/blob/main/README.md#devcontainer-bake-files-devcontainer-cache-build-usage).

If using a custom [bake file](https://docs.docker.com/build/bake/reference/), the config must contain the following configuration:

```hcl
variable "DEVCONTAINER_OUTPUTS" {
  default = ""
}
variable "DEVCONTAINER_CACHE_FROMS" {
  default = ""
}
variable "DEVCONTAINER_CACHE_TOS" {
  default = ""
}

target "default" {
  dockerfile = ".devcontainer/Dockerfile"
  cache-from = [
    for cache_from in split(" ", trimspace("${DEVCONTAINER_CACHE_FROMS}")):
    "${cache_from}-base"
  ]
  cache-to = [
    for cache_to in split(" ", trimspace("${DEVCONTAINER_CACHE_TOS}")):
    "${cache_to}-base"
  ]
  output = split(" ", trimspace("${DEVCONTAINER_OUTPUTS}"))
}
```

#### Initialize script inputs

The initialize script reads several environment variables as configuration. To provide an empty value for an input and avoid the default, set the variables to `"_NONE_"`.

| Variable | Required | Default | Effect |
| --- | --- | --- | --- |
| `DEVCONTAINER_IMAGE` | &check; | N/A | The tag applied to the image build |
| `DEVCONTAINER_BUILD_ADDITIONAL_ARGS` | &cross; | N/A | Arbitrary additional args forwarded to the `build` or `bake` command |
| `DEVCONTAINER_CACHE_FROMS` | &cross; | `type=registry,ref=[DEVCONTAINER_REGISTRY]-cache-[current git branch name sanitized] type=registry,ref=[DEVCONTAINER_REGISTRY]-cache-[DEVCONTAINER_DEFAULT_BRANCH_NAME, sanitized]` | Each [`cache-from` arg](https://docs.docker.com/reference/cli/docker/buildx/build/#cache-from) to be applied to the image build, space separated |
| `DEVCONTAINER_CACHE_TOS` | &cross; | `type=registry,ref=[DEVCONTAINER_REGISTRY]-cache-[current git branch name sanitized]` | Each [`cache-to` arg](https://docs.docker.com/reference/cli/docker/buildx/build/#cache-to) to be applied to the image build, space separated |
| `DEVCONTAINER_CONTEXT` | &cross; | `.` | The build context for the image |
| `DEVCONTAINER_DEFAULT_BRANCH_NAME` | &cross; | `main` | The branch name from which to always pull cache |
| `DEVCONTAINER_DEFINITION_TYPE` | &cross; | `build` | The image definition type, [basic Docker build (`build`)](https://docs.docker.com/reference/cli/docker/buildx/build/) or [Bake (`bake`)](https://docs.docker.com/reference/cli/docker/buildx/bake/) |
| `DEVCONTAINER_DEFINITION_FILES` | &cross; | `.devcontainer/Dockerfile`, or `.devcontainer/bake.hcl` if `DEVCONTAINER_DEFINITION_TYPE` is `bake` | The Dockerfile or bake config file path(s) for the image build, space separated |
| `DEVCONTAINER_INITIALIZE_PID` | &cross; | N/A | If defined, must be set to the process ID of the command provided to the `devcontainer.json` `initializeCommand` (often `$PPID`). Used to determine whether the context of the `initializeCommand` call is a new container bringup, based on the presence of the the [`--expect-existing-container`](https://github.com/devcontainers/cli/blob/9ba1fdaa11dee087b142d33e4ac13c5788392e34/src/spec-node/devContainersSpecCLI.ts#L196) argument |
| `DEVCONTAINER_OUTPUTS` | &cross; | `type=image,name=[DEVCONTAINER_REGISTRY],push=[DEVCONTAINER_PUSH_IMAGE]` | Each [`output` arg](https://docs.docker.com/reference/cli/docker/buildx/build/#output) to applt to the image build, space separated |
| `DEVCONTAINER_PUSH_IMAGE` | &cross; | `false` | Whether to push the image to the provided registry (requires `DEVCONTAINER_REGISTRY`) |
| `DEVCONTAINER_REGISTRY` | &cross; | `DEVCONTAINER_IMAGE` | The registry for the image and/or cache |

The image build leverages any values provided or computed to `DEVCONTAINER_CACHE_FROM` as cache inputs.

#### Initialize script outputs

The initialize script image build produces several outputs.

- An image in the local daemon image store (the [`image` output type](https://docs.docker.com/reference/cli/docker/buildx/build/#image)) at the name given by `DEVCONTAINER_IMAGE`
- Image build cache output published as specified by `DEVCONTAINER_CACHE_TO`

#### Initialize script GitHub container registry setup

Configuring the initialize script with a plain image name results in targeting outputs and cache to [DockerhHub](https://hub.docker.com/) by default. Setting the `DEVCONTAINER_REGISTRY` to `ghcr.io/[your user/org name]` instead allows you to target the [GitHub container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) instead. To set up a container repository for this in a local environment, use [`docker login`](https://docs.docker.com/reference/cli/docker/login/) [against `ghcr.io`](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-with-a-personal-access-token-classic). For GitHub Codespaces environments, use the following steps:

1. Create a [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic) with [`write:packages` scope](https://docs.github.com/en/codespaces/reference/allowing-your-codespace-to-access-a-private-registry#publishing-a-package-from-a-codespace) for the repository to which the image belongs.
1. Add the token as a [Codespace secret](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces#adding-a-secret), to the repository to which the Codespaces environment belongs.
1. [Use the secret variable to `docker login`](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-with-a-personal-access-token-classic) in the Codespace environment by adding a login command to the devcontainer `initializeCommand` in advance of the `curl` to the intialize script, e.g.:
```bash
# .devcontainer/initialize

echo $DEVCONTAINER_CACHE_BUILD_DEVCONTAINER_INITIALIZE | docker login ghcr.io --username $GITHUB_USER --password-stdin
...
curl https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/0.1.0/initialize | bash
```
