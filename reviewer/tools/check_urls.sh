#!/usr/bin/env bash
# check_urls.sh - Validate that all cited URLs return a valid HTTP status
# Usage: ./check_urls.sh <file>
set -euo pipefail

file="$1"
if [ ! -f "$file" ]; then
    echo "File not found: $file"
    exit 1
fi

urls=$(grep -oP 'https?://[^\s\)\]>"'"'"']+' "$file" | sort -u)

if [ -z "$urls" ]; then
    echo "No URLs found in $file"
    exit 0
fi

failed=0
while IFS= read -r url; do
    # Try HEAD first (no body download)
    status=$(curl -o /dev/null -s -w "%{http_code}" -I -L --max-time 10 "$url" 2>/dev/null || echo "000")
    # Fall back to GET if HEAD is rejected (405) or connection failed
    if [[ "$status" == "405" || "$status" == "000" ]]; then
        status=$(curl -o /dev/null -s -w "%{http_code}" -L --max-time 10 "$url" 2>/dev/null || echo "000")
    fi
    if [[ "$status" =~ ^[23] ]]; then
        echo "OK   $status $url"
    else
        echo "FAIL $status $url"
        failed=$((failed + 1))
    fi
done <<< "$urls"

echo ""
if [ "$failed" -gt 0 ]; then
    echo "$failed URL(s) failed validation"
    exit 1
else
    echo "All URLs valid"
    exit 0
fi
