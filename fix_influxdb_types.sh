#!/bin/bash
# Script to fix InfluxDB type conflicts by clearing and recreating the bucket

echo "This script will clear the InfluxDB bucket to fix type conflicts."
echo "All existing data will be lost!"
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

echo "Stopping services..."
docker-compose stop log-ingester

echo "Clearing InfluxDB data..."
docker-compose exec influxdb influx bucket delete --name holidai-logs --org holidai --token holidai-admin-token-change-in-production || true

echo "Recreating bucket..."
docker-compose exec influxdb influx bucket create --name holidai-logs --org holidai --token holidai-admin-token-change-in-production || true

echo "Restarting services..."
docker-compose start log-ingester

echo "Done! The ingester will now start writing data with correct types."
echo "Note: You may need to wait a few minutes for new data to appear."

