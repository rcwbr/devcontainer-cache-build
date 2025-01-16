#!/bin/env python3

import json
import re
import subprocess
from os import environ as env
from os import getcwd as getcwd
from pathlib import Path

from python_on_whales import docker
from git import Repo, GitConfigParser

INITIALIZE_BUILDER_NAME = "initialize-builder"
DEVCONTAINER_HOST_ENV_VAR_PREFIX = "DEVCONTAINER_HOST_"
DEVCONTAINER_CACHE_BUILD_OVERRIDE_PREFIX = "DEVCONTAINER_CACHE_BUILD_OVERRIDE_"


def sanitize_ref(ref):
  """
  Sanitize string for use as a container ref
  """
  return re.sub(r"[^a-zA-Z0-9_]", "-", ref)


def dict_from_string(key_values_string):
  """
  Extract a dict representation from a string of comma-separated key=value pairs.
  """
  return {
    key: value for (key, value) in [
      tuple(pair.split("=")) for pair in key_values_string.split(",")
    ]
  } if "=" in key_values_string else {}


def docker_destination_list_from_env_var(var_name, default_list):
  """
  Get a list of Docker destinations from a space-separated env var, or return default value
  """
  return (
    [
      dict_from_string(destination_string)
      for destination_string in env.get(var_name).split(" ")
    ]
    if var_name in env
    else default_list
  )


def docker_destination_to_string(docker_destination_dict):
  """
  Get a string representation from a Docker destination object
  """
  return ",".join([f"{key}={value}" for key, value in docker_destination_dict.items()])


def docker_destinations_to_string(docker_destination_list):
  """
  Get a string representation from a list of Docker destination objects
  """
  return " ".join([docker_destination_to_string(destination) for destination in docker_destination_list])


print("Beginning devcontainer-cache-build-initialze.py")


###### Required inputs ######

DEVCONTAINER_IMAGE = env["DEVCONTAINER_IMAGE"]


###### Inputs with empty defaults ######

DEVCONTAINER_BUILD_ADDITIONAL_ARGS = dict_from_string(env.get("DEVCONTAINER_BUILD_ADDITIONAL_ARGS", ""))
DEVCONTAINER_PREBUILD_SCRIPT = env.get("DEVCONTAINER_PREBUILD_SCRIPT")
DEVCONTAINER_REGISTRY = env.get("DEVCONTAINER_REGISTRY")


###### Inputs with simple defaults ######

print("Reading devcontainer-cache-build inputs")

DEVCONTAINER_CONTEXT = env.get("DEVCONTAINER_CONTEXT", ".")
DEVCONTAINER_DEFINITION_TYPE = env.get("DEVCONTAINER_DEFINITION_TYPE", "build")
DEVCONTAINER_PUSH_IMAGE = env.get("DEVCONTAINER_PUSH_IMAGE", "false").lower() in ["true", "t", "yes", "y", "1"]
DEVCONTAINER_DEFAULT_BRANCH_NAME = env.get("DEVCONTAINER_DEFAULT_BRANCH_NAME", "main")
DEVCONTAINER_DEFINITION_FILES = (
  env.get("DEVCONTAINER_DEFINITION_FILES").split(" ")
  if "DEVCONTAINER_DEFINITION_FILES" in env
  else [".devcontainer/Dockerfile"]
)

REPO = Repo(".")
# Configure git to ignore ownership of the current directory
REPO.config_writer(config_level='global').set_value("safe", "directory", getcwd())
# Get the branch name unless in detached head state
GIT_BRANCH = str(REPO.head.commit) if REPO.head.is_detached else str(REPO.head.ref)
# Replace any non-alphanumeric (or underscore) characters in the branch names with dashes
GIT_BRANCH_SANITIZED = sanitize_ref(GIT_BRANCH)
DEVCONTAINER_DEFAULT_BRANCH_NAME_SANITIZED = sanitize_ref(DEVCONTAINER_DEFAULT_BRANCH_NAME)


###### Inputs with computed defaults ######

print("Computing devcontainer-cache-build input defaults")

DEVCONTAINER_IMAGE_REF = (
  f"{DEVCONTAINER_REGISTRY}/{DEVCONTAINER_IMAGE}"
  if DEVCONTAINER_REGISTRY is not None
  else DEVCONTAINER_IMAGE
)

DEVCONTAINER_OUTPUTS = docker_destination_list_from_env_var(
  "DEVCONTAINER_OUTPUTS",
  [{
    "type": "docker",
    "name": DEVCONTAINER_IMAGE
  }] + (
    [{
      "type": "image",
      "name": f"{DEVCONTAINER_IMAGE_REF}:{GIT_BRANCH_SANITIZED}",
      "push": DEVCONTAINER_PUSH_IMAGE
    }]
    if DEVCONTAINER_PUSH_IMAGE
    else []
  )
)

DEVCONTAINER_CACHE_FROMS = docker_destination_list_from_env_var(
  "DEVCONTAINER_CACHE_FROMS",
  # By default, pull cache...
  [
    {
      # ... from the ref populated by CI for this branch
      "type": "registry",
      "ref": f"{DEVCONTAINER_IMAGE_REF}-cache:{GIT_BRANCH_SANITIZED}"
    },
    {
      # ... from the ref populated by local runs for this branch
      "type": "registry",
      "ref": f"{DEVCONTAINER_IMAGE_REF}-cache:local-{GIT_BRANCH_SANITIZED}"
    },
    {
      # ... and from the ref populated by CI for the main branch
      "type": "registry",
      "ref": f"{DEVCONTAINER_IMAGE_REF}-cache:{DEVCONTAINER_DEFAULT_BRANCH_NAME_SANITIZED}"
    }
  ]
)

DEVCONTAINER_CACHE_TOS = docker_destination_list_from_env_var(
  "DEVCONTAINER_CACHE_TOS",
  (
    # By default, push cache to a "-cache" ref if executing in a CI context
    [{
      "type": "registry",
      # Settings as recommended in https://aws.amazon.com/blogs/containers/announcing-remote-cache-support-in-amazon-ecr-for-buildkit-clients/
      "rewrite-timestamp": True,
      "mode": "max",
      "image-manifest": True,
      "oci-mediatypes": True,
      "ref": f"{DEVCONTAINER_IMAGE_REF}-cache:{GIT_BRANCH_SANITIZED}"
    }]
    if env.get("CI", "false").lower() in ["true", "t", "1"]
    else [{
      "type": "registry",
      # Settings as recommended in https://aws.amazon.com/blogs/containers/announcing-remote-cache-support-in-amazon-ecr-for-buildkit-clients/
      "rewrite-timestamp": True,
      "mode": "max",
      "image-manifest": True,
      "oci-mediatypes": True,
      "ref": f"{DEVCONTAINER_IMAGE_REF}-cache:local-{GIT_BRANCH_SANITIZED}"
    }]
  )
)


###### Prepare Docker client credentials ######

DOCKER_CONFIG_JSON = env.get("DOCKER_CONFIG_JSON")
if DOCKER_CONFIG_JSON is not None:
  try:
    print("Loading Docker config JSON from env var")
    docker_config_content = json.loads(DOCKER_CONFIG_JSON)
    docker_config_folder = Path(Path.home(), ".docker")
    docker_config_folder.mkdir(exist_ok=True)
    docker_config_filename = Path(docker_config_folder, "config.json")

    if docker_config_filename.exists() and docker_config_filename.is_file():
      print(f"Docker config file {docker_config_filename} exists, will merge config content")
      with open(docker_config_filename, "r") as docker_config_file:
        try:
          docker_config_content = json.load(docker_config_file) | docker_config_content
        except ValueError:
          print(f"Invalid JSON content in {docker_config_filename}: {docker_config_file.read()}")

    with open(docker_config_filename, "w") as docker_config_file:
      print(f"Writing Docker config JSON to file {docker_config_filename}")
      print(json.dumps(docker_config_content, indent=4))
      json.dump(docker_config_content, docker_config_file, indent=4)

  except ValueError:
    print(f"Invalid JSON content for DOCKER_CONFIG_JSON: {DOCKER_CONFIG_JSON}")
else:
  print(f"No value set for DOCKER_CONFIG_JSON")


###### Execute pre-build script ######

if DEVCONTAINER_PREBUILD_SCRIPT is not None:
  print(f"DEVCONTAINER_PREBUILD_SCRIPT {DEVCONTAINER_PREBUILD_SCRIPT} provided, running...")
  prebuild_result = subprocess.run(
    [DEVCONTAINER_PREBUILD_SCRIPT],
    capture_output=True,
    text=True
  )
  print(f"DEVCONTAINER_PREBUILD_SCRIPT {DEVCONTAINER_PREBUILD_SCRIPT} result: {prebuild_result.stdout}")

###### Find the builder, or create if needed ######

initialize_builder = None
if INITIALIZE_BUILDER_NAME in [builder.name for builder in docker.buildx.list()]:
  initialize_builder = docker.buildx.inspect(INITIALIZE_BUILDER_NAME)
  print(f"Builder {INITIALIZE_BUILDER_NAME} found with status {docker.buildx.inspect(INITIALIZE_BUILDER_NAME).status}")
else:
  print(f"No builder {INITIALIZE_BUILDER_NAME} found, creating:")
  initialize_builder = docker.buildx.create(
    bootstrap=True,
    driver="docker-container",
    name=INITIALIZE_BUILDER_NAME
  )
  print(f"Builder {INITIALIZE_BUILDER_NAME} created, status {initialize_builder.status}")


###### Gather env vars from devcontainer host ######

# Strip DEVCONTAINER_HOST_ENV_VAR_PREFIX
devcontainer_host_env_vars = {
  name.removeprefix(DEVCONTAINER_HOST_ENV_VAR_PREFIX): value
  for name, value in env.items()
  if name.startswith(DEVCONTAINER_HOST_ENV_VAR_PREFIX)
  # Exclude potentially problematic env vars
  and name.removeprefix(DEVCONTAINER_HOST_ENV_VAR_PREFIX) not in [
    "PATH",
    "HOME",
  ]
}

# Extract USER, UID, and USER_GID special env vars
for var_name in ["USER", "UID", "USER_GID"]:
  if f"{DEVCONTAINER_CACHE_BUILD_OVERRIDE_PREFIX}{var_name}" in devcontainer_host_env_vars:
    value = devcontainer_host_env_vars[f"{DEVCONTAINER_CACHE_BUILD_OVERRIDE_PREFIX}{var_name}"]
    print(f"{var_name} override specified, using override value {value}")
    devcontainer_host_env_vars[var_name] = value


###### Generate bake args ######

if DEVCONTAINER_DEFINITION_TYPE.lower() == "bake":
  # In the case of Docker bake, pre-generate command args as the bake config is used for cache pre-population
  bake_params = {
    "variables": { # Bake variables are overridden by env vars
      "SOURCE_DATE_EPOCH": "1731797200", # Specify a static value for image and layer timestamps
      "DEVCONTAINER_CACHE_FROMS": docker_destinations_to_string(DEVCONTAINER_CACHE_FROMS),
      "DEVCONTAINER_CACHE_TOS": docker_destinations_to_string(DEVCONTAINER_CACHE_TOS),
      "DEVCONTAINER_OUTPUTS": docker_destinations_to_string(DEVCONTAINER_OUTPUTS),
      # Add devcontainer host env vars to the bake config
      **devcontainer_host_env_vars   
    },
    "builder": initialize_builder,
    "files": DEVCONTAINER_DEFINITION_FILES,
    **DEVCONTAINER_BUILD_ADDITIONAL_ARGS
  }


###### Pre-pull cache images ######

if DEVCONTAINER_DEFINITION_TYPE.lower() == "build":
  # Docker build case 
  for output_image in DEVCONTAINER_OUTPUTS:
    # Pull each output image to pre-populate cache
    if "ref" in output_image:
      print(f"Pulling image for cache population: {image_name}")
      docker.pull(output_image["ref"])
elif DEVCONTAINER_DEFINITION_TYPE.lower() == "bake":
  # Docker bake case
  bake_config = docker.buildx.bake(print=True, **bake_params)
  for target_name, target in bake_config["target"].items():
    for pull_image in target["output"]:
      if "ref" in dict_from_string(pull_image):
        image_name = dict_from_string(pull_image)["ref"]
        print(f"Pulling image for {target_name} cache population: {image_name}")
        docker.pull(image_name)


###### Execute the build ######

if DEVCONTAINER_DEFINITION_TYPE.lower() == "build":
  # Docker build case
  docker.buildx.build(
    builder=initialize_builder,
    file=DEVCONTAINER_DEFINITION_FILES[0], # Build command only accepts one file
    output=DEVCONTAINER_OUTPUTS[0], # Python-on-whales limitation of one output
    cache_from=DEVCONTAINER_CACHE_FROMS,
    cache_to=DEVCONTAINER_CACHE_TOS[0], # Python-on-whales limitation of one cache-to
    context_path=DEVCONTAINER_CONTEXT,
    **DEVCONTAINER_BUILD_ADDITIONAL_ARGS
  )
elif DEVCONTAINER_DEFINITION_TYPE.lower() == "bake":
  # Docker bake case
  print(json.dumps(docker.buildx.bake(
    print=True,
    **bake_params
  ), indent=2))
  docker.buildx.bake(**bake_params)
