"""
Azure Blob Storage reader for log files.
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


class AzureBlobReader:
    """Reads log files from Azure Blob Storage."""
    
    def __init__(self, connection_string: str, account_name: str, container_name: str):
        """
        Initialize Azure Blob Storage reader.
        
        Args:
            connection_string: Azure Blob Storage connection string
            account_name: Storage account name
            container_name: Container name
        """
        if not connection_string:
            raise ValueError("AZURE_BLOB_CONNECTION_STRING is required")
        
        self.connection_string = connection_string
        self.account_name = account_name
        self.container_name = container_name
        
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            self.container_client = self.blob_service_client.get_container_client(container_name)
            logger.info(f"Connected to Azure Blob Storage: {account_name}/{container_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Azure Blob Storage: {e}")
            raise
    
    def list_log_files(self) -> List[str]:
        """
        List all log files in the blob storage container.
        
        Returns:
            List of blob paths
        """
        try:
            blobs = self.container_client.list_blobs()
            log_files = []
            
            for blob in blobs:
                # Include all JSON log files
                if blob.name.endswith('.json') and 'log_' in blob.name:
                    log_files.append(blob.name)
            
            return log_files
        except Exception as e:
            logger.error(f"Error listing log files: {e}")
            return []
    
    def read_log_file(self, blob_path: str) -> Optional[Dict]:
        """
        Read and parse a log file from blob storage.
        
        Args:
            blob_path: Path to the blob file
            
        Returns:
            Parsed JSON data or None if error
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            # Download blob content
            blob_data = blob_client.download_blob()
            content = blob_data.readall()
            
            # Parse JSON
            log_data = json.loads(content.decode('utf-8'))
            
            # Add metadata
            log_data['_blob_path'] = blob_path
            log_data['_ingested_at'] = datetime.utcnow().isoformat() + 'Z'
            
            return log_data
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {blob_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {blob_path}: {e}")
            return None
    
    def get_log_type_from_path(self, blob_path: str) -> str:
        """
        Determine log type from blob path.
        
        Args:
            blob_path: Path to the blob file
            
        Returns:
            Log type: 'api_call', 'node_enter', 'node_exit', 'interaction', 
                     'feedback_failure', 'llm_call'
        """
        if blob_path.startswith('api/'):
            return 'api_call'
        elif blob_path.startswith('agent/nodes/'):
            if '/enter_' in blob_path:
                return 'node_enter'
            elif '/exit_' in blob_path:
                return 'node_exit'
        elif blob_path.startswith('agent/interactions/'):
            return 'interaction'
        elif blob_path.startswith('agent/feedback_failures/'):
            return 'feedback_failure'
        elif blob_path.startswith('agent/llm_calls/'):
            return 'llm_call'
        
        return 'unknown'

