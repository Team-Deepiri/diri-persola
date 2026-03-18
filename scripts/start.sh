#!/bin/bash
set -e

# Check if we're running standalone or as part of platform
if [ -f "../docker-compose.dev.yml" ]; then
    echo "Platform docker-compose found - starting via platform"
    cd .. && docker compose -f docker-compose.dev.yml up -d persola-db persola persola-ui
else
    echo "Starting persola stack standalone"
    docker compose up -d
fi