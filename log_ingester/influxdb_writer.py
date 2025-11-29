"""
InfluxDB writer for metrics.
"""
import logging
from typing import List, Dict, Optional
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)


class InfluxDBWriter:
    """Writes metrics to InfluxDB."""
    
    def __init__(self, url: str, token: str, org: str, bucket: str):
        """
        Initialize InfluxDB writer.
        
        Args:
            url: InfluxDB URL
            token: InfluxDB authentication token
            org: InfluxDB organization
            bucket: InfluxDB bucket name
        """
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        
        try:
            self.client = InfluxDBClient(url=url, token=token, org=org)
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            logger.info(f"Connected to InfluxDB: {url}")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            raise
    
    def write_point(self, measurement: str, fields: Dict, tags: Dict = None, timestamp: Optional[str] = None):
        """
        Write a single data point to InfluxDB.
        
        Args:
            measurement: Measurement name (table name)
            fields: Field values (metrics)
            tags: Tag values (dimensions/indexes)
            timestamp: ISO 8601 timestamp string (optional, defaults to now)
        """
        try:
            point = Point(measurement)
            
            # Add tags
            if tags:
                for key, value in tags.items():
                    if value is not None:
                        point.tag(key, str(value))
            
            # Add fields - only add non-null values
            for key, value in fields.items():
                if value is not None:
                    try:
                        if isinstance(value, (int, float)):
                            # Ensure all numeric values are float for consistency
                            point.field(key, float(value))
                        elif isinstance(value, bool):
                            point.field(key, 1 if value else 0)
                        elif isinstance(value, str) and value.strip():
                            point.field(key, value)
                    except Exception as e:
                        logger.warning(f"Skipping field {key} due to error: {e}")
            
            # Set timestamp if provided
            if timestamp:
                from datetime import datetime
                try:
                    # Parse ISO 8601 timestamp
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    point.time(dt)
                except:
                    pass
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            
        except Exception as e:
            logger.error(f"Error writing point to InfluxDB: {e}")
            raise
    
    def write_points(self, points: List[Point]):
        """
        Write multiple points in batch.
        
        Args:
            points: List of Point objects
        """
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=points)
        except Exception as e:
            logger.error(f"Error writing points to InfluxDB: {e}")
            raise
    
    def flush(self):
        """Flush any pending writes."""
        try:
            self.write_api.flush()
        except Exception as e:
            logger.error(f"Error flushing InfluxDB writes: {e}")
    
    def close(self):
        """Close the InfluxDB client."""
        try:
            self.write_api.close()
            self.client.close()
        except Exception as e:
            logger.error(f"Error closing InfluxDB client: {e}")

