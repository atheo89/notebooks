#!/bin/bash

# TAG_VERSION is the identification keyword inside the tag name of the image example:YYYYx, or empty on this place for main,
# jupyter-minimal-ubi9-python-3.11-20250310-60b6ecc <- image tag generated from main
USER_HASH=$1
REPO_OWNER="opendatahub-io"
REPO_NAME="notebooks"
BRANCH=main
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