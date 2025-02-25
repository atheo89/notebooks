#!/bin/bash

# HASH=ec54d80
# RELEASE_VERSION=2024b

# echo "HASH=$(echo $HASH )"

# # Find matching files
# files=$(find manifests/base -type f -name "runtime-*.yaml")
# for file in $files; do
#   echo "Processing: $file"
#   # Extract the image_name field
#   img=$(yq e '.spec.tags[].annotations."opendatahub.io/runtime-image-metadata" | fromjson | .[].metadata.image_name' "$file")
#   echo "Extracted image_name: $img"


#   # Extract image tag (name)
#   name=$(yq e '.spec.tags[].name' "$file")
#   echo "Extracted name: $name"

#   # Handling specific cases
#   if [[ $name == tensorflow* ]]; then
#     name="cuda-$name"
#   elif [[ $name == ubi* ]]; then
#     name="minimal-$name"
#   fi

#   # Extract UBI version
#   ubi=$(yq e '.metadata.annotations."opendatahub.io/runtime-image-name"' "$file" | grep -oE 'UBI[0-9]+' | tr '[:upper:]' '[:lower:]')
#   echo "Extracted ubi version: $ubi"

#   # Extract Python version
#   py_version=$(yq e '.metadata.annotations."opendatahub.io/runtime-image-name"' "$file" | grep -oE 'Python [0-9]+\.[0-9]+' | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')

#   echo "Extracted python version: $py_version"


#   registry=$(echo "$img" | cut -d '@' -f1)
#   echo "Extracted registry: $registry"


#   regex="^runtime-$name-$ubi-$py_version-$RELEASE_VERSION-[0-9]{8}-$HASH$"
#   echo "Regex: $regex"


#   latest_tag=$(skopeo inspect --retry-times 3 "docker://$img" | jq -r --arg regex "$regex" '.RepoTags | map(select(. | test($regex))) | .[0]')
#   echo "CHECKING: ${latest_tag}"

#   digest=$(skopeo inspect --retry-times 3 "docker://$registry:$latest_tag" | jq .Digest | tr -d '"')
#   output="${registry}@${digest}"
#   echo "NEW: ${output}"

#   # Update `from.name`
#   yq e -i '(.spec.tags[] | .from.name) = "'"$output"'"' "$file"

#   # Update `image_name`
#   sed -i "s|\(\"image_name\": \"\)[^\"]*|\1${output}|" "$file"

# done

#!/bin/bash

#!/bin/bash

HASH="ec54d80"
RELEASE_VERSION="2024b"

echo "HASH=${HASH}"

find manifests/base -type f -name "runtime-*.yaml" | while read -r file; do
  echo "Processing: $file"

  # Extract values safely
  img=$(yq e '.spec.tags[].annotations."opendatahub.io/runtime-image-metadata" | fromjson | .[].metadata.image_name' "$file" 2>/dev/null)
  name=$(yq e '.spec.tags[].name' "$file" 2>/dev/null)
  ubi=$(yq e '.metadata.annotations."opendatahub.io/runtime-image-name"' "$file" 2>/dev/null | grep -oE 'UBI[0-9]+' | tr '[:upper:]' '[:lower:]')
  py_version=$(yq e '.metadata.annotations."opendatahub.io/runtime-image-name"' "$file" 2>/dev/null | grep -oE 'Python [0-9]+\.[0-9]+' | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')

  # Debugging extracted values
  echo "Extracted: img=$img, name=$name, ubi=$ubi, py_version=$py_version"

  # Handle missing values
  if [[ -z "$img" || -z "$name" || -z "$ubi" || -z "$py_version" ]]; then
    echo "ERROR: Missing required values. Skipping $file"
    continue
  fi

  # Modify name for special cases
  [[ $name == tensorflow* ]] && name="cuda-$name"
  [[ $name == ubi* ]] && name="minimal-$name"

  registry="${img%@*}"  # Extract registry part before '@'
  regex="^runtime-$name-$ubi-$py_version-$RELEASE_VERSION-[0-9]{8}-$HASH$"

  echo "Registry: $registry"
  echo "Regex: $regex"

  # Ensure `registry` is valid
  if [[ -z "$registry" ]]; then
    echo "ERROR: Invalid registry extracted from image. Skipping $file"
    continue
  fi

  # Fetch image tags from skopeo
  skopeo_output=$(skopeo inspect --retry-times 3 "docker://$img" 2>/dev/null)
  if [[ -z "$skopeo_output" ]]; then
    echo "ERROR: skopeo failed for $img. Skipping $file"
    continue
  fi

  latest_tag=$(echo "$skopeo_output" | jq -r --arg regex "$regex" '.RepoTags | map(select(. | test($regex))) | .[0]')

  # Ensure `latest_tag` exists
  if [[ -z "$latest_tag" || "$latest_tag" == "null" ]]; then
    echo "ERROR: No matching tag found for $regex. Skipping $file"
    continue
  fi

  digest=$(echo "$skopeo_output" | jq -r '.Digest')
  output="${registry}@${digest}"
  
  echo "NEW: ${output}"

  # Update YAML file
  yq e -i '
    (.spec.tags[].from.name) = "'"$output"'" |
    (.spec.tags[].annotations."opendatahub.io/runtime-image-metadata" | fromjson | .[].metadata.image_name) = "'"$output"'"
  ' "$file"

done
