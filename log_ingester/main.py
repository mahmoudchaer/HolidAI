"""
Main entry point for the log ingestion service.
Reads logs from Azure Blob Storage and writes metrics to InfluxDB.
"""
import os
import time
import logging
from dotenv import load_dotenv
from log_ingester.azure_reader import AzureBlobReader
from log_ingester.influxdb_writer import InfluxDBWriter
from log_ingester.log_processor import LogProcessor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main ingestion loop."""
    # Initialize components
    blob_reader = AzureBlobReader(
        connection_string=os.getenv('AZURE_BLOB_CONNECTION_STRING'),
        account_name=os.getenv('AZURE_BLOB_ACCOUNT_NAME', 'holidailogs'),
        container_name=os.getenv('AZURE_BLOB_CONTAINER', 'holidai-logs')
    )
    
    influx_writer = InfluxDBWriter(
        url=os.getenv('INFLUXDB_URL', 'http://localhost:8086'),
        token=os.getenv('INFLUXDB_TOKEN'),
        org=os.getenv('INFLUXDB_ORG', 'holidai'),
        bucket=os.getenv('INFLUXDB_BUCKET', 'holidai-logs')
    )
    
    processor = LogProcessor(influx_writer)
    
    ingest_interval = int(os.getenv('INGEST_INTERVAL', '60'))
    
    logger.info("Starting log ingestion service...")
    logger.info(f"Ingest interval: {ingest_interval} seconds")
    
    # Track processed files to avoid reprocessing
    processed_files = set()
    
    while True:
        try:
            logger.info("Scanning for new log files...")
            
            # Get all log files from blob storage
            log_files = blob_reader.list_log_files()
            logger.info(f"Found {len(log_files)} log files")
            
            # Process new files
            new_files = [f for f in log_files if f not in processed_files]
            if new_files:
                logger.info(f"Processing {len(new_files)} new log files...")
                
                for blob_path in new_files:
                    try:
                        log_data = blob_reader.read_log_file(blob_path)
                        if log_data:
                            processor.process_log(blob_path, log_data)
                            processed_files.add(blob_path)
                    except Exception as e:
                        logger.error(f"Error processing {blob_path}: {e}", exc_info=True)
                
                # Flush any pending writes
                influx_writer.flush()
                logger.info("Batch processing complete")
            else:
                logger.info("No new files to process")
            
            # Wait before next scan
            time.sleep(ingest_interval)
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(ingest_interval)


if __name__ == '__main__':
    main()

