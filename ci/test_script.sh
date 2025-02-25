#!/bin/bash

BRANCH_NAME=$1
FILE_NAME="${BRANCH_NAME}.txt"

# Create a file with the branch name
echo "This file was created for branch: $BRANCH_NAME" > "$FILE_NAME"

echo "File '$FILE_NAME' has been created."