#!/bin/bash
set -e

echo "Initializing InfluxDB..."

# Wait for InfluxDB to be ready
until curl -s http://localhost:8086/ping; do
    echo "Waiting for InfluxDB to be ready..."
    sleep 1
done

# Create database and user
influx -execute "CREATE DATABASE homeassistant"
influx -execute "CREATE USER optimizer WITH PASSWORD 'tuggummi'"
influx -execute "GRANT ALL ON homeassistant TO optimizer"

echo "InfluxDB initialization complete!"
