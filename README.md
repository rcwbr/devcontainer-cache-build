# devcontainer-cache-build<a name="devcontainer-cache-build"></a>

Build devcontainer images using remote Docker cache. This repo contains definitions for a complete
workflow around the devcontainer image, including configuration for local building and cache
population by CI pipeline.

<!-- mdformat-toc start --slug=github --maxlevel=6 --minlevel=1 -->

- [devcontainer-cache-build](#devcontainer-cache-build)
  - [Usage](#usage)
    - [Initialize script](#initialize-script)
      - [Initialize script basic usage](#initialize-script-basic-usage)
      - [Initialize script specific version usage](#initialize-script-specific-version-usage)
      - [Initialize script bake usage](#initialize-script-bake-usage)
      - [Initialize script inputs](#initialize-script-inputs)
      - [Initialize script outputs](#initialize-script-outputs)
      - [Initialize script prebuild file usage](#initialize-script-prebuild-file-usage)
      - [Initialize script GitHub container registry setup](#initialize-script-github-container-registry-setup)
    - [GHCR registry setup](#ghcr-registry-setup)
    - [GitHub Actions workflow](#github-actions-workflow)
      - [GitHub Actions workflow inputs usage](#github-actions-workflow-inputs-usage)
  - [Codespaces prebuilds](#codespaces-prebuilds)
    - [Codespace prebuilds configuration](#codespace-prebuilds-configuration)
  - [Contributing](#contributing)
    - [devcontainer](#devcontainer)
      - [devcontainer basic usage](#devcontainer-basic-usage)
      - [devcontainer Codespaces usage](#devcontainer-codespaces-usage)
      - [devcontainer pre-commit usage](#devcontainer-pre-commit-usage)
    - [CI/CD](#cicd)
    - [Settings](#settings)
    - [Local image build](#local-image-build)

<!-- mdformat-toc end -->

## Usage<a name="usage"></a>

This repo defines tooling for the entire lifecycle of a devcontainer cache. Based on the context of
the script call, `devcontainer-cache-build-initialize` supplies build configuration to target cache
to refs for each event in that lifecycle, as described below:

```mermaid
graph TD;
  gha_main_workflow(GitHub Actions main workflow) <--1--> main_cache(registry/image-cache:main-layer)
  gha_pr_workflow(GitHub Actions PR workflow) <--2--> branch_cache(registry/image-cache:branch-layer)
  devcontainer_build(devcontainer build)
  devcontainer_build <--3--> local_branch_cache(registry/image-cache:local-branch-layer)
  main_cache --4-->  gha_pr_workflow & devcontainer_build
  branch_cache --5--> gha_main_workflow & devcontainer_build
  local_branch_cache --6--> gha_main_workflow & gha_main_workflow
  subgraph Registry
    main_cache
    branch_cache
    local_branch_cache
  end
  subgraph GitHub Actions
    gha_main_workflow
    gha_pr_workflow
  end
```

1. GitHub Actions default branch workflows populate the cache for each layer, under the `main` ref.
1. GitHub Actions PR workflows populate the cache for each layer, under the ref for the PR branch
   name.
1. Devcontainer builds populate the cache for each layer, under the ref for the local branch name,
   with a `local-` prefix.
1. The `main` ref cache for each layer is used for builds in all contexts.
1. The branch ref cache for each layer is used for builds in all contexts.
1. The `local-`branch ref cache for each layer is used for builds in all contexts.

### Initialize script<a name="initialize-script"></a>

The initialize script replaces `build` in `.devcontainer/devcontainer.json`, and computes
appropriate configuration for the devcontainer image Docker build command. Internally, it wraps a
Docker container run, in which the configuration logic and build execution is managed.

#### Initialize script basic usage<a name="initialize-script-basic-usage"></a>

To use the script, add
`"initializeCommand": "curl https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/0.8.0/devcontainer-cache-build-initialize | bash"`
to your `devcontainer.json`, or to scripts referenced by it. For example, you might replace

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
curl https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/0.8.0/devcontainer-cache-build-initialize | bash
```

#### Initialize script specific version usage<a name="initialize-script-specific-version-usage"></a>

A specific version of the script may be used by adjusting the URL in the `curl` command. The format
is
`https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/<version ref>/devcontainer-cache-build-initialize`,
where `<version ref>` may be any valid version reference from this repo.

#### Initialize script bake usage<a name="initialize-script-bake-usage"></a>

To use the `devcontainer-cache-build-initialize` script with
[bake](https://docs.docker.com/reference/cli/docker/buildx/bake/), the recommended usage is to set
the `DEVCONTAINER_BUILD_ADDITIONAL_ARGS` and `DEVCONTAINER_DEFINITION_FILES` vars to leverage bake
file partials as defined in the
[dockerfile-partials repository](https://github.com/rcwbr/dockerfile-partials/blob/main/README.md#devcontainer-bake-files-devcontainer-cache-build-usage).

If using a custom [bake file](https://docs.docker.com/build/bake/reference/), the config must
contain the following configuration:

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

#### Initialize script inputs<a name="initialize-script-inputs"></a>

The `devcontainer-cache-build-initialize` script reads several environment variables as
configuration.

| Variable                              | Required | Default                                                                                                                                                                                                                                                                       | Effect                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DEVCONTAINER_IMAGE`                  | ✓        | N/A                                                                                                                                                                                                                                                                           | The tag applied to the image build                                                                                                                                                                                                                                                                                                                                                                                                           |
| `DEVCONTAINER_BUILD_ADDITIONAL_ARGS`  | ✗        | N/A                                                                                                                                                                                                                                                                           | Arbitrary additional args forwarded to the `build` or `bake` command, as comma-separated `key=value` pairs in [Python-on-whales syntax](https://github.com/gabrieldemarmiesse/python-on-whales)                                                                                                                                                                                                                                              |
| `DEVCONTAINER_CACHE_BUILD_OVERRIDE_*` | ✗        | None                                                                                                                                                                                                                                                                          | Special env variables to pass through to the build execution context, that may not be exportable. Supported variables are `USER`, `UID`, and `USER_GID` (e.g. `DEVCONTAINER_CACHE_BUILD_OVERRIDE_USER=my_username`...)                                                                                                                                                                                                                       |
| `DEVCONTAINER_CACHE_FROMS`            | ✗        | `type=registry,ref=[DEVCONTAINER_REGISTRY]-cache:[current git branch name sanitized] type=registry,ref=[DEVCONTAINER_REGISTRY]-cache:local-[current git branch name sanitized] type=registry,ref=[DEVCONTAINER_REGISTRY]-cache:[DEVCONTAINER_DEFAULT_BRANCH_NAME, sanitized]` | Each [`cache-from` arg](https://docs.docker.com/reference/cli/docker/buildx/build/#cache-from) to be applied to the image build, space separated                                                                                                                                                                                                                                                                                             |
| `DEVCONTAINER_CACHE_TOS`              | ✗        | `type=registry,rewrite-timestamp=true,mode=max,ref=[DEVCONTAINER_REGISTRY]-cache:[local-][current git branch name sanitized]`                                                                                                                                                 | Each [`cache-to` arg](https://docs.docker.com/reference/cli/docker/buildx/build/#cache-to) to be applied to the image build, space separated. The default value includes `local-` applied as a version prefix unless `CI=true`                                                                                                                                                                                                               |
| `DEVCONTAINER_CONTEXT`                | ✗        | `.`                                                                                                                                                                                                                                                                           | The build context for the image                                                                                                                                                                                                                                                                                                                                                                                                              |
| `DEVCONTAINER_DEFAULT_BRANCH_NAME`    | ✗        | `main`                                                                                                                                                                                                                                                                        | The branch name from which to always pull cache                                                                                                                                                                                                                                                                                                                                                                                              |
| `DEVCONTAINER_DEFINITION_TYPE`        | ✗        | `build`                                                                                                                                                                                                                                                                       | The image definition type, [basic Docker build (`build`)](https://docs.docker.com/reference/cli/docker/buildx/build/) or [Bake (`bake`)](https://docs.docker.com/reference/cli/docker/buildx/bake/)                                                                                                                                                                                                                                          |
| `DEVCONTAINER_DEFINITION_FILES`       | ✗        | `.devcontainer/Dockerfile`, or `.devcontainer/bake.hcl` if `DEVCONTAINER_DEFINITION_TYPE` is `bake`                                                                                                                                                                           | The Dockerfile or bake config file path(s) for the image build, space separated                                                                                                                                                                                                                                                                                                                                                              |
| `DEVCONTAINER_INITIALIZE_PID`         | ✗        | N/A                                                                                                                                                                                                                                                                           | If defined, must be set to the process ID of the command provided to the `devcontainer.json` `initializeCommand` (often `$PPID`). Used to determine whether the context of the `initializeCommand` call is a new container bringup, based on the presence of the the [`--expect-existing-container`](https://github.com/devcontainers/cli/blob/9ba1fdaa11dee0.8.042d33e4ac13c5788392e34/src/spec-node/devContainersSpecCLI.ts#L196) argument |
| `DEVCONTAINER_OUTPUTS`                | ✗        | `type=image,name=[DEVCONTAINER_REGISTRY],push=[DEVCONTAINER_PUSH_IMAGE]`                                                                                                                                                                                                      | Each [`output` arg](https://docs.docker.com/reference/cli/docker/buildx/build/#output) to apply to the image build, space separated                                                                                                                                                                                                                                                                                                          |
| `DEVCONTAINER_PREBUILD_SCRIPT`        | ✗        | None                                                                                                                                                                                                                                                                          | The path to a script to execute in advance of image build operations, e.g. for `docker login`s (see [Initialize script prebuild file usage](#initialize-script-prebuild-file-usage)). Relative to the repo root; must resolve to a file within the repo directory                                                                                                                                                                            |
| `DEVCONTAINER_PUSH_IMAGE`             | ✗        | `false`                                                                                                                                                                                                                                                                       | Whether to push the image to the provided registry (requires `DEVCONTAINER_REGISTRY`)                                                                                                                                                                                                                                                                                                                                                        |
| `DEVCONTAINER_REGISTRY`               | ✗        | `DEVCONTAINER_IMAGE`                                                                                                                                                                                                                                                          | The registry for the image and/or cache                                                                                                                                                                                                                                                                                                                                                                                                      |
| `*`                                   | ✗        | N/A                                                                                                                                                                                                                                                                           | In the case of bake builds, all additional environment variables are forwarded to the build execution context                                                                                                                                                                                                                                                                                                                                |

The image build leverages any values provided or computed to `DEVCONTAINER_CACHE_FROM` as cache
inputs.

#### Initialize script outputs<a name="initialize-script-outputs"></a>

The `devcontainer-cache-build-initialize` script image build produces several outputs.

- An image in the local daemon image store (the
  [`image` output type](https://docs.docker.com/reference/cli/docker/buildx/build/#image)) at the
  name given by `DEVCONTAINER_IMAGE`
- Image build cache output published as specified by `DEVCONTAINER_CACHE_TO`

#### Initialize script prebuild file usage<a name="initialize-script-prebuild-file-usage"></a>

The initialize script supports injecting a script (identified via the `DEVCONTAINER_PREBUILD_SCRIPT`
env var) before build actions are taken, for example to perform authentication actions such as
`docker login` within the initialize script container context. As the script must be available
within the container context to execute, the value provided to `DEVCONTAINER_PREBUILD_SCRIPT` must
be a file within the repository directory, so that it may be mounted to the container.

Env vars from the host (especially useful for authenication use cases) are available to the
`DEVCONTAINER_PREBUILD_SCRIPT` script, but are remapped under a `DEVCONTAINER_HOST_` prefix. For
example, `DOCKERHUB_PASSWORD` in the host would be available to the script as
`DEVCONTAINER_HOST_DOCKERHUB_PASSWORD`.

#### Initialize script GitHub container registry setup<a name="initialize-script-github-container-registry-setup"></a>

Configuring the `devcontainer-cache-build-initialize` script with a plain image name results in
targeting outputs and cache to [DockerHub](https://hub.docker.com/) by default. Setting the
`DEVCONTAINER_REGISTRY` to `ghcr.io/[your user/org name]` instead allows you to target the
[GitHub container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
instead. To set up a container repository for this in a local environment, use
[`docker login`](https://docs.docker.com/reference/cli/docker/login/)
[against `ghcr.io`](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-with-a-personal-access-token-classic).
For GitHub Codespaces environments, use the following steps:

1. Create a
   [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic)
   with
   [`write:packages` scope](https://docs.github.com/en/codespaces/reference/allowing-your-codespace-to-access-a-private-registry#publishing-a-package-from-a-codespace)
   for the repository to which the image belongs.
1. Add the token as a
   [Codespace secret](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces#adding-a-secret),
   to the repository to which the Codespaces environment belongs.
1. Name the variable for the token secret as `[prefix for your repo]_CONTAINER_REGISTRY_PASSWORD`
1. Create another secret with the same name prefix but for the username
   `[prefix for your repo]_CONTAINER_REGISTRY_USER`, with the value set to your GitHub username
1. Create another secret with the same name prefix called
   `[prefix for your repo]_CONTAINER_REGISTRY_SERVER`, with the value set to `ghcr.io`

These are
[automatically applied by GitHub](https://docs.github.com/en/codespaces/reference/allowing-your-codespace-to-access-a-private-registry#accessing-images-stored-in-other-registries)
to authenticate in a Codespace. This is necessary because
[other secrets are not accessible during Codespace image build](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces#using-secrets).

### GHCR registry setup<a name="ghcr-registry-setup"></a>

If using GHCR as the `DEVCONTAINER_REGISTRY`, the addition of any layer to the devcontainer
definition involves configuring a registry for it with appropriate access. This is best achieved by
leveraging the [GitHub Actions workflow](#github-actions-workflow), as registry configuration is
established automatically. To do this, simply open a PR that contains the layer addition, before
trying to rebuild a devcontainer/Codespace with the layer addition. Otherwise, registries may be
created as private and require a manual settings change to make them public.

### GitHub Actions workflow<a name="github-actions-workflow"></a>

Leveraging the entire lifecycle of the devcontainer cache requires applying a CI/CD workflow to
prepopulate cache. This may be achieved via the reusable workflow defined in
`.github/workflows/devcontainer-cache-build.yaml`, e.g.:

```yaml
on: push
jobs:
  devcontainer-cache-build:
    uses: >-
      rcwbr/devcontainer-cache-build/.github/workflows/devcontainer-cache-build.yaml@0.8.0
    permissions:
      packages: write
```

The default behavior of the workflow provides arguments for use with the
[useradd Dockerfile partial](https://github.com/rcwbr/dockerfile-partials/tree/main/useradd) for
Codespaces user provisioning. These arguments must be forwarded to the
`devcontainer-cache-build-initialize` script, e.g. via the `DEVCONTAINER_BUILD_ADDITIONAL_ARGS`
variable:

```bash
# .devcontainer/initialize

export DEVCONTAINER_BUILD_ADDITIONAL_ARGS="$@"
curl https://raw.githubusercontent.com/rcwbr/devcontainer-cache-build/0.8.0/devcontainer-cache-build-initialize | bash
```

#### GitHub Actions workflow inputs usage<a name="github-actions-workflow-inputs-usage"></a>

| Input                                     | Required | Default       | Type   | Effect                                                                                                                                  |
| ----------------------------------------- | -------- | ------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `build-context-user`                      | ✗        | `"codespace"` | string | The user name to set for the .devcontainer/initialize call                                                                              |
| `build-context-uid`                       | ✗        | `1000`        | number | The UID to set for the .devcontainer/initialize call                                                                                    |
| `build-context-gid`                       | ✗        | `1000`        | number | The USER_GID to set for the .devcontainer/initialize call                                                                               |
| `devcontainer-cache-build-image-override` | ✗        | `""`          | string | The image name to use to override the default devcontainer-cache-build image                                                            |
| `initialize-args`                         | ✗        | `""`          | string | Args to provide to the `devcontainer-cache-build-initialize` script; by default set to values for building Codespaces-compatible images |

## Codespaces prebuilds<a name="codespaces-prebuilds"></a>

[Codespace prebuilds](https://docs.github.com/en/codespaces/prebuilding-your-codespaces/about-github-codespaces-prebuilds)
may be configured to enhance cached bringup in Codespaces by effectively snapshotting a devcontainer
_after_ pull and execution of the `devcontainer-cache-build` Docker image as configured by the
`.devcontainer/initialize` script.

### Codespace prebuilds configuration<a name="codespace-prebuilds-configuration"></a>

Per the below setup steps, GitHub will be configured to prebuild the Codespace on pushes to the
default branch. This way, Codespace bringups will only need to execute when starting a _new_
Codespace from branch that contains a delta relative to the default branch.

1. If using GHCR as the devcontainer image registry, retrieve (or replace, including in the
   `[prefix for your repo]_CONTAINER_REGISTRY_PASSWORD` user Codespace secret) the Personal Access
   Token created in the
   [Initialize script GitHub container registry setup step](#initialize-script-github-container-registry-setup).
   1. Alternatively, create a new token. The same scopes are required, and the role is similar,
      albeit in a conceptually shared context.
1. In repository settings,
   [add a Codespace secret](https://docs.github.com/en/codespaces/managing-codespaces-for-your-organization/managing-development-environment-secrets-for-your-repository-or-organization#adding-secrets-for-a-repository)
   named `CODESPACES_PREBUILD_TOKEN` (see
   [docs](https://docs.github.com/en/codespaces/prebuilding-your-codespaces/allowing-a-prebuild-to-access-other-repositories#allowing-a-prebuild-write-access-to-external-resources))
   with the token as the value.
1. Add two more repo Codespace secrets (as no mechanism for simple variables exists) for
   [user configuration](https://github.com/rcwbr/dockerfile-partials#useradd-codespaces-usage):
   1. Set `USER` to `codespace`
   1. Set `UID` to `1000`
1. In repo settings,
   [configure a Codespaces prebuild](https://docs.github.com/en/codespaces/prebuilding-your-codespaces/configuring-prebuilds)
   1. Select Set up prebuild
   1. Select the default branch
   1. Set Prebuild triggers to Every push
   1. Select appropriate region availability to your case
   1. Set Template history to 1
   1. Optionally, specify recipients for Failure notifications

## Contributing<a name="contributing"></a>

### devcontainer<a name="devcontainer"></a>

This repo contains a [devcontainer definition](https://containers.dev/) in the `.devcontainer`
folder. It leverages its own devcontainer cache build tool and layers
[defined in the dockerfile-partials repo](https://github.com/rcwbr/dockerfile-partials).

#### devcontainer basic usage<a name="devcontainer-basic-usage"></a>

The devcontainer cache build tool requires authentication to the GitHub package registry, as a token
stored as `DOCKERFILE_PARTIALS_DEVCONTAINER_INITIALIZE` (see
[instructions](#initialize-script-github-container-registry-setup)).

#### devcontainer Codespaces usage<a name="devcontainer-codespaces-usage"></a>

For use with Codespaces, the `DOCKERFILE_PARTIALS_DEVCONTAINER_INITIALIZE` token (see
[devcontainer basic usage](#devcontainer-basic-usage)) must be stored as a Codespaces secret (see
[instructions](#initialize-script-github-container-registry-setup)), as must values for `USER`, and
`UID` (see
[useradd Codespaces usage](https://github.com/rcwbr/dockerfile-partials#useradd-codespaces-usage)).

#### devcontainer pre-commit usage<a name="devcontainer-pre-commit-usage"></a>

By default, the devcontainer configures [pre-commit](https://pre-commit.com/) hooks in the
repository to ensure commits pass basic testing. This includes enforcing
[conventional commit messages](https://www.conventionalcommits.org/en/v1.0.0/) as the standard for
this repository, via [commitlint](https://github.com/conventional-changelog/commitlint).

### CI/CD<a name="cicd"></a>

This repo uses the [release-it-gh-workflow](https://github.com/rcwbr/release-it-gh-workflow) with
the file-bumper image as its release automation.

A [Docker Bake](https://github.com/docker/bake-action) workflow packages and releases the
devcontainer-cache-build image.

It uses its own [reusable devcontainer cache build workflow](#github-actions-workflow) to
pre-populate the devcontainer cache.

Linting is enforced via a
[pre-commit workflow](https://github.com/rcwbr/dockerfile-partials/blob/main/.github/workflows/pre-commit.yaml),
and a [Dive Docker image efficiency analysis](https://github.com/wagoodman/dive) job analyses the
storage efficiency of the devcontainer-cache-build image.

### Settings<a name="settings"></a>

The GitHub repo settings for this repo are defined as code using the
[Probot settings GitHub App](https://probot.github.io/apps/settings/). Settings values are defined
in the `.github/settings.yml` file. Enabling automation of settings via this file requires
installing the app.

The settings applied are as recommended in the
[release-it-gh-workflow usage](https://github.com/rcwbr/release-it-gh-workflow/blob/4dea4eaf328b60f92dab1b5bd2a63daefa85404b/README.md?plain=1#L58),
including tag and branch protections, GitHub App and environment authentication, and required
checks.

### Local image build<a name="local-image-build"></a>

To build the devcontainer-cache-build tool image locally, use the following command:

```bash
docker builder create --use --driver docker-container # Skip if you already have a docker-container builder activated
export IMAGE_NAME=devcontainer-cache-build
docker buildx bake -f github-cache-bake.hcl -f cwd://docker-bake.hcl https://github.com/rcwbr/dockerfile-partials.git#0.8.0
```
