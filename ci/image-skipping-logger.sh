#!/bin/bash

SKIPPED_LOG="${SKIPPED_LOG_PATH:-$(pwd)/skipped-images.txt}"

init_skipped_log() {
    mkdir -p "$(dirname "$SKIPPED_LOG")"
    > "$SKIPPED_LOG"
}

log_skipped_image() {
    local image_name="$1"
    echo "- ❌ — No matching tag for $image_name" >> "$SKIPPED_LOG"
}


# Print the log contents (for debug/logging)
print_skipped_log() {
    if [[ -f "$SKIPPED_LOG" && -s "$SKIPPED_LOG" ]]; then
        echo "=== Skipped Images ==="
        cat "$SKIPPED_LOG"
        echo "======================"
    else
        echo "No images were skipped."
    fi
}
