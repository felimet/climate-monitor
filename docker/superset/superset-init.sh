#!/bin/bash

# Upgrade the database
superset db upgrade

# Create an admin user if it doesn't exist
# Note: Check if admin exists first to avoid errors on restart, or just let it fail safely
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USERNAME}" \
    --firstname Superset \
    --lastname Admin \
    --email "${SUPERSET_ADMIN_EMAIL}" \
    --password "${SUPERSET_ADMIN_PASSWORD}" || true

# Initialize Superset
superset init

# Import Datasources
if [ -f /app/docker/superset/datasources.yaml ]; then
    echo "Importing datasources..."
    superset import-datasources -p /app/docker/superset/datasources.yaml
fi
