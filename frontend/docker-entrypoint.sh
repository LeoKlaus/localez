#!/bin/sh
set -e

envsubst '${ALLOWED_HOSTS}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

PRIVACY_FILE="/usr/share/nginx/html/legal/privacy.md"

if [ ! -f "$PRIVACY_FILE" ]; then
    echo ""
    echo "ERROR: Missing required file: privacy.md"
    echo "Mount your legal directory into the container, e.g.:"
    echo "  -v /path/to/legal:/usr/share/nginx/html/legal"
    echo "or in docker-compose:"
    echo "  volumes:"
    echo "    - ./legal:/usr/share/nginx/html/legal"
    echo ""
    exit 1
fi

exec nginx -g "daemon off;"
