#!/bin/bash

while getopts "m:" opt; do
  case $opt in
    m)
      message="$OPTARG"
      ;;
    *)
      echo "Usage: $0 -m \"your message\""
      exit 1
      ;;
  esac
done

# Use the message

versions="migrations/versions"
cache="migrations/versions/__pycache__"

similar_versions=$(find "$versions" -type f -name "*$message*" 2>/dev/null)
similar_cache=$(find "$cache" -type f -name "*$message*" 2>/dev/null)

if [ -z "$message" ]; then
    echo "Error: Message is required"
    echo "Usage: $0 -m \"your message\""
    exit 1
fi

if [[ ${#message} -lt 5 ]]; then
    echo "Error: Message '$message' is too short or generic. Use a more descriptive message (min 5 characters)."
    exit 1
fi

if [[ -n "$similar_versions" || -n "$similar_cache" ]]; then
    echo "⚠️ Warning: Found existing files containing the message \"$message\":"
    [[ -n "$similar_versions" ]] && echo "$similar_versions"
    [[ -n "$similar_cache" ]] && echo "$similar_cache"
    echo "❌ Aborting to prevent overwriting or deleting similar files."
    exit 1
fi


echo "✅ All checks passed. Proceeding..."

if ! alembic revision --autogenerate -m "$message"; then
    echo "Error: Failed to generate migration"
    exit 1
fi

if ! alembic upgrade head;
    then
        echo "Error: Failed to apply migration"
        # Delete files containing the message from versions and cache directories
        find "$versions" -name "*$message*" -type f -delete 2>/dev/null
        find "$cache" -name "*$message*" -type f -delete 2>/dev/null
        exit 1
fi
