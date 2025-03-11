#!/bin/bash

# TAG_VERSION is the identification keyword inside the tag name of the image example:YYYYx, or empty on this place for main,
# jupyter-minimal-ubi9-python-3.11-20250310-60b6ecc <- image tag generated from main
USER_HASH=$1
REPO_OWNER="opendatahub-io"
REPO_NAME="notebooks"
BRANCH=main

# Explicitly check for both cases
if [[ "$REPO_OWNER" == "opendatahub-io" ]]; then
    echo "this is opendatahub-io org"

    GITHUB_API_URL="https://api.github.com/repos/$REPO_OWNER/$REPO_NAME"

    if [[ -n "$USER_HASH" ]]; then
      HASH=$USER_HASH
      echo "Using user-provided HASH: $HASH"
    else
      PAYLOAD=$(curl --silent -H 'Accept: application/vnd.github.v4.raw' "$GITHUB_API_URL/commits?sha=$BRANCH&per_page=1")
      HASH=$(echo "$PAYLOAD" | jq -r '.[0].sha' | cut -c1-7)
      echo "Extracted HASH: $HASH"
    fi

    REPO_ROOT=$(git rev-parse --show-toplevel)
    MANIFEST_DIR="$REPO_ROOT/manifests/base"
    PARAMS_ENV_PATH="$REPO_ROOT/manifests/base/params.env"

    # Get the complete list of images N-version to update
    IMAGES=$(grep "\-n=" "${PARAMS_ENV_PATH}" | cut -d "=" -f 1)

    for image in ${IMAGES}; do

        echo "CHECKING: '${image}'"
        img=$(grep -E "${image}=" "${PARAMS_ENV_PATH}" | cut -d '=' -f2)
        registry=$(echo "${img}" | cut -d '@' -f1)

        skopeo_metadata=$(skopeo inspect --retry-times 3 "docker://${img}")

        src_tag=$(echo "${skopeo_metadata}" | jq '.Env[] | select(startswith("OPENSHIFT_BUILD_NAME=")) | split("=")[1]' | tr -d '"' | sed 's/-amd64$//')
        # This should match with the jupyter-minimal-ubi9-python-3.11-20250310-60b6ecc tag name as is on quay.io registry
        regex="^$src_tag-\d+-$HASH\$"

        latest_tag=$(echo "${skopeo_metadata}" | jq -r --arg regex "$regex" '.RepoTags | map(select(. | test($regex))) | .[0]')
        # use `--no-tags` for skopeo once available in newer version
        digest=$(skopeo inspect --retry-times 3 "docker://${registry}:${latest_tag}" | jq .Digest | tr -d '"')
        output="${registry}@${digest}"
        echo "NEW: ${output}"
        sed -i "s|${image}=.*|${image}=${output}|" "${PARAMS_ENV_PATH}"
    done

    # Updates Commit references on the commit.env file
    COMMIT_ENV_PATH="$REPO_ROOT/manifests/base/commit.env"
    # Get the complete list of commits N-version to update
    COMMIT=$(grep "\-n=" "${COMMIT_ENV_PATH}" | cut -d "=" -f 1)

    for val in ${COMMIT}; do
        echo "${val}"
        sed -i "s|${val}=.*|${val}=$HASH|" "${COMMIT_ENV_PATH}"
    done


elif [[ "$REPO_OWNER" == "red-hat-data-services" ]]; then
    echo "this is red-hat-data-services org"

    GITHUB_API_URL="https://api.github.com/repos/$REPO_OWNER/$REPO_NAME"

    if [[ -n "$USER_HASH" ]]; then
      HASH=$USER_HASH
      echo "Using user-provided HASH: $HASH"
    else
      PAYLOAD=$(curl --silent -H 'Accept: application/vnd.github.v4.raw' "$GITHUB_API_URL/commits?sha=$BRANCH&per_page=1")
      HASH=$(echo "$PAYLOAD" | jq -r '.[0].sha' | cut -c1-7)
      echo "Extracted HASH: $HASH"
    fi

    REPO_ROOT=$(git rev-parse --show-toplevel)
    MANIFEST_DIR="$REPO_ROOT/manifests/base"
    PARAMS_ENV_PATH="$REPO_ROOT/manifests/base/params.env"

    # Get the complete list of images N-version to update
    IMAGES=$(grep "\-n=" "${PARAMS_ENV_PATH}" | cut -d "=" -f 1)

    # The order of the regexes array should match with the params.env file
    REGEXES=("v3-\d{8}-+$HASH" \
              "cuda-[a-z]+-minimal-[a-z0-9]+-[a-z]+-3.11-\d{8}-$HASH" \
              "v3-\d{8}-+$HASH" \
              "v3-\d{8}-+$HASH" \
              "cuda-[a-z]+-tensorflow-[a-z0-9]+-[a-z]+-3.11-\d{8}-$HASH" \
              "v3-\d{8}-+$HASH" \
              "codeserver-[a-z0-9]+-[a-z]+-3.11-\d{8}-$HASH" \
              "rocm-[a-z]+-minimal-[a-z0-9]+-[a-z]+-3.11-\d{8}-$HASH" \
              "rocm-[a-z]+-pytorch-[a-z0-9]+-[a-z]+-3.11-\d{8}-$HASH" \
              "rocm-[a-z]+-tensorflow-[a-z0-9]+-[a-z]+-3.11-\d{8}-$HASH")
          i=0
    for image in ${IMAGES}; do
        echo "CHECKING: '${image}'"
        img=$(grep -E "${image}=" "${PARAMS_ENV_PATH}" | cut -d '=' -f2)
        registry=$(echo "${img}" | cut -d '@' -f1)

        regex=${REGEXES[$i]}
        skopeo_metadata=$(skopeo inspect --retry-times 3 "docker://${img}")
        latest_tag=$(echo "${skopeo_metadata}" | jq -r --arg regex "$regex" '.RepoTags | map(select(. | test($regex))) | .[0]')
        digest=$(skopeo inspect --retry-times 3 "docker://${registry}:${latest_tag}" | jq .Digest | tr -d '"')
        output="${registry}@${digest}"
        echo "NEW: ${output}"
        sed -i "s|${image}=.*|${image}=${output}|" "${PARAMS_ENV_PATH}"
        i=$((i+1))
    done

  COMMIT_ENV_PATH="$REPO_ROOT/manifests/base/commit.env"

  # Get the complete list of commits N-version to update
  COMMIT=$(grep "\-n=" "${COMMIT_ENV_PATH}" | cut -d "=" -f 1)

  for val in ${COMMIT}; do
    echo "${val}"
    sed -i "s|${val}=.*|${val}=$HASH|" "${COMMIT_ENV_PATH}"
  done


else
    echo "This script runs exclusively for the 'opendatahub-io' and 'red-hat-datascience' organizations, as it verifies their corresponding quay.io registries."
fi

