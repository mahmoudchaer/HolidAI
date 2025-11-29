"""
Processes log data and converts to InfluxDB metrics.
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from log_ingester.influxdb_writer import InfluxDBWriter

logger = logging.getLogger(__name__)


class LogProcessor:
    """Processes logs and writes metrics to InfluxDB."""
    
    def __init__(self, influx_writer: InfluxDBWriter):
        """
        Initialize log processor.
        
        Args:
            influx_writer: InfluxDB writer instance
        """
        self.influx_writer = influx_writer
    
    def process_log(self, blob_path: str, log_data: Dict):
        """
        Process a single log entry and write metrics to InfluxDB.
        
        Args:
            blob_path: Path to the blob file
            log_data: Parsed log JSON data
        """
        try:
            # Determine log type from path
            log_type = self._get_log_type_from_path(blob_path)
            
            # Process based on log type
            if log_type == 'api_call':
                self._process_api_call(log_data)
            elif log_type == 'node_exit':
                self._process_node_exit(log_data)
            elif log_type == 'node_enter':
                self._process_node_enter(log_data)
            elif log_type == 'interaction':
                self._process_interaction(log_data)
            elif log_type == 'feedback_failure':
                self._process_feedback_failure(log_data)
            elif log_type == 'llm_call':
                self._process_llm_call(log_data)
            
            # Always write a log count metric
            self._write_log_count(log_type, log_data)
            
        except Exception as e:
            logger.error(f"Error processing log {blob_path}: {e}", exc_info=True)
    
    def _get_log_type_from_path(self, blob_path: str) -> str:
        """Determine log type from blob path."""
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
    
    def _process_api_call(self, log_data: Dict):
        """Process API call log."""
        timestamp = log_data.get('timestamp')
        service = log_data.get('service', 'unknown')
        
        tags = {
            'service': service,
            'endpoint': log_data.get('endpoint', 'unknown'),
            'method': log_data.get('method', 'unknown'),
            'response_status': str(log_data.get('response_status', 0)),
            'user_email': log_data.get('user_id') or log_data.get('user_email', 'unknown'),
            'session_id': log_data.get('session_id', 'unknown'),
        }
        
        fields = {
            'response_time_ms': log_data.get('response_time_ms'),
            'success': log_data.get('success', False),
            'error_count': 1 if not log_data.get('success', False) else 0,
        }
        
        # Add error message as tag if present
        if log_data.get('error_message'):
            tags['error_message'] = log_data.get('error_message')[:100]  # Truncate long messages
        
        self.influx_writer.write_point('api_calls', fields, tags, timestamp)
    
    def _process_node_exit(self, log_data: Dict):
        """Process node exit log."""
        timestamp = log_data.get('timestamp')
        node_name = log_data.get('node_name', 'unknown')
        
        tags = {
            'node_name': node_name,
            'user_email': log_data.get('user_email', 'unknown'),
            'session_id': log_data.get('session_id', 'unknown'),
        }
        
        fields = {
            'latency_ms': log_data.get('latency_ms'),
        }
        
        self.influx_writer.write_point('node_executions', fields, tags, timestamp)
    
    def _process_node_enter(self, log_data: Dict):
        """Process node enter log (just for counting)."""
        timestamp = log_data.get('timestamp')
        node_name = log_data.get('node_name', 'unknown')
        
        tags = {
            'node_name': node_name,
            'user_email': log_data.get('user_email', 'unknown'),
            'session_id': log_data.get('session_id', 'unknown'),
        }
        
        fields = {
            'count': 1,
        }
        
        self.influx_writer.write_point('node_enters', fields, tags, timestamp)
    
    def _process_interaction(self, log_data: Dict):
        """Process interaction log."""
        timestamp = log_data.get('timestamp')
        
        tags = {
            'user_email': log_data.get('user_email', 'unknown'),
            'session_id': log_data.get('session_id', 'unknown'),
        }
        
        fields = {
            'latency_ms': log_data.get('latency_ms'),
        }
        
        self.influx_writer.write_point('interactions', fields, tags, timestamp)
    
    def _process_feedback_failure(self, log_data: Dict):
        """Process feedback failure log."""
        timestamp = log_data.get('timestamp')
        feedback_node = log_data.get('feedback_node', 'unknown')
        
        tags = {
            'feedback_node': feedback_node,
            'user_email': log_data.get('user_email', 'unknown'),
            'session_id': log_data.get('session_id', 'unknown'),
        }
        
        # Extract reason (truncate if too long)
        reason = log_data.get('reason', 'unknown')
        if reason:
            tags['reason'] = reason[:200]  # Truncate long reasons
        
        fields = {
            'failure_count': 1,
        }
        
        self.influx_writer.write_point('feedback_failures', fields, tags, timestamp)
    
    def _process_llm_call(self, log_data: Dict):
        """Process LLM call log."""
        timestamp = log_data.get('timestamp')
        agent_name = log_data.get('agent_name', 'unknown')
        
        tags = {
            'agent_name': agent_name,
            'model': log_data.get('model', 'unknown'),
            'user_email': log_data.get('user_email', 'unknown'),
            'session_id': log_data.get('session_id', 'unknown'),
        }
        
        token_usage = log_data.get('token_usage', {}) or {}
        
        fields = {
            'latency_ms': log_data.get('latency_ms'),
            'prompt_tokens': token_usage.get('prompt_tokens'),
            'completion_tokens': token_usage.get('completion_tokens'),
            'total_tokens': token_usage.get('total_tokens'),
        }
        
        self.influx_writer.write_point('llm_calls', fields, tags, timestamp)
    
    def _write_log_count(self, log_type: str, log_data: Dict):
        """Write a log count metric for time-series analysis."""
        timestamp = log_data.get('timestamp')
        
        tags = {
            'log_type': log_type,
        }
        
        fields = {
            'count': 1,
        }
        
        self.influx_writer.write_point('log_counts', fields, tags, timestamp)

