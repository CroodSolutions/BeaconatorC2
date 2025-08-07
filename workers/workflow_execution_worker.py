import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

from services.workflows.workflow_service import Workflow, WorkflowNode, WorkflowConnection
from services.workflows.execution_types import ExecutionContext, ExecutionStatus
from services.workflows.parameter_template_engine import ParameterTemplateEngine
from services.workflows.condition_processor import ConditionProcessor
from services.workflows.variable_extractor import VariableExtractor
from database import BeaconRepository


class WorkflowExecutionWorker(QThread):
    """Background worker for executing workflows without blocking the UI thread"""
    
    # Signals for communicating with the main thread
    execution_started = pyqtSignal(str)  # execution_id
    execution_completed = pyqtSignal(str, object)  # execution_id, context
    execution_failed = pyqtSignal(str, str)  # execution_id, error_message
    node_started = pyqtSignal(str, str)  # execution_id, node_id
    node_completed = pyqtSignal(str, str, dict)  # execution_id, node_id, result
    execution_progress = pyqtSignal(str, object)  # execution_id, context
    log_message = pyqtSignal(str, str, str)  # execution_id, level, message
    
    def __init__(self, execution_id: str, workflow: Workflow, beacon_id: str, 
                 beacon_repository: BeaconRepository, schema_service=None, canvas_variables: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.execution_id = execution_id
        self.workflow = workflow
        self.beacon_id = beacon_id
        self.beacon_repository = beacon_repository
        self.schema_service = schema_service
        self.canvas_variables = canvas_variables or {}
        self._stop_requested = False
        self._context = None
        
        # Initialize template engine, condition processor, and variable extractor
        self.template_engine = ParameterTemplateEngine()
        self.condition_processor = ConditionProcessor()
        self.variable_extractor = VariableExtractor()
        
    def request_stop(self):
        """Request the worker to stop execution"""
        self._stop_requested = True
        
    def get_context(self) -> Optional[ExecutionContext]:
        """Get the current execution context"""
        return self._context
        
    def run(self):
        """Main execution method that runs in the background thread"""
        try:
            # Create execution context with merged variables
            context_variables = {}
            
            # Start with workflow variables
            if self.workflow.variables:
                context_variables.update(self.workflow.variables)
            
            # Add canvas variables (can override workflow variables)
            context_variables.update(self.canvas_variables)
            
            self._context = ExecutionContext(
                workflow_id=self.workflow.workflow_id,
                beacon_id=self.beacon_id,
                variables=context_variables,
                node_results={},
                execution_log=[],
                status=ExecutionStatus.RUNNING,
                start_time=datetime.now()
            )
            
            # Emit execution started signal
            self.execution_started.emit(self.execution_id)
            self._log("info", f"Starting workflow '{self.workflow.workflow_id}' on beacon {self.beacon_id}")
            self._log("info", f"Workflow has {len(self.workflow.nodes)} nodes and {len(self.workflow.connections)} connections")
            
            # Validate beacon exists and is online
            beacon = self.beacon_repository.get_beacon(self.beacon_id)
            if not beacon:
                raise Exception(f"Beacon {self.beacon_id} not found")
                
            if beacon.status != 'online':
                raise Exception(f"Beacon {self.beacon_id} is not online (status: {beacon.status})")
            
            # Find start node and begin execution
            start_node = self._find_start_node()
            if not start_node:
                raise Exception("No start node found in workflow")
                
            self._log("info", f"Found start node: {start_node.node_id}")
            
            # Execute workflow starting from start node
            self._execute_workflow_from_node(start_node)
            
            # If we reach here without stop request, workflow completed successfully
            if not self._stop_requested:
                self._context.status = ExecutionStatus.COMPLETED
                self._context.end_time = datetime.now()
                self._log("info", "Workflow execution completed successfully")
                self.execution_completed.emit(self.execution_id, self._context)
            else:
                self._context.status = ExecutionStatus.STOPPED
                self._context.end_time = datetime.now()
                self._log("info", "Workflow execution stopped by user")
                self.execution_completed.emit(self.execution_id, self._context)
                
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            self._log("error", error_msg)
            if self._context:
                self._context.status = ExecutionStatus.FAILED
                self._context.end_time = datetime.now()
            self.execution_failed.emit(self.execution_id, error_msg)
            
    def _find_start_node(self) -> Optional[WorkflowNode]:
        """Find the start node in the workflow"""
        for node in self.workflow.nodes:
            if node.node_type == 'start':
                return node
        return None
        
    def _execute_workflow_from_node(self, node: WorkflowNode):
        """Execute workflow starting from a specific node"""
        while node and not self._stop_requested:
            # Execute current node
            self._context.current_node_id = node.node_id
            self.node_started.emit(self.execution_id, node.node_id)
            self._log("info", f"Executing node '{node.node_id}' (Type: {node.node_type})")
            
            try:
                result = self._execute_node(node)
                self._context.node_results[node.node_id] = result
                
                # Extract variables from node output if configured
                self._extract_node_variables(node, result)
                
                self.node_completed.emit(self.execution_id, node.node_id, result)
                
                # Emit progress update
                self.execution_progress.emit(self.execution_id, self._context)
                
                # For action nodes, check if this is the final node
                if (node.node_type == 'action' or 
                    node.node_type.startswith('schema_') or 
                    node.node_type.startswith('action_')):
                    if self._is_final_action_node(node):
                        self._log("info", f"Final action node {node.node_id} completed, ending workflow")
                        break
                
                # Find next node to execute
                node = self._find_next_node(node, result)
                
            except Exception as e:
                error_msg = f"Error executing node {node.node_id}: {str(e)}"
                self._log("error", error_msg)
                result = {'status': 'error', 'output': error_msg}
                self._context.node_results[node.node_id] = result
                self.node_completed.emit(self.execution_id, node.node_id, result)
                break
                
    def _execute_node(self, node: WorkflowNode) -> Dict[str, Any]:
        """Execute a single node with parameter templating"""
        # Apply parameter templating to node parameters
        original_parameters = node.parameters.copy()
        try:
            node.parameters = self.template_engine.substitute_parameters(
                node.parameters, self._context, node, self.workflow.connections
            )
            self._log("debug", f"Applied parameter templating to node {node.node_id}")
        except Exception as e:
            self._log("warning", f"Parameter templating failed for node {node.node_id}: {str(e)}")
            # Continue with original parameters if templating fails
            node.parameters = original_parameters
        
        # Execute node based on type
        if node.node_type == 'start':
            return {'status': 'started', 'output': 'Workflow started successfully'}
            
        elif node.node_type == 'end':
            return {'status': 'ended', 'output': 'Workflow completed successfully'}
            
        elif node.node_type == 'delay':
            delay_seconds = node.parameters.get('delay_seconds', 1)
            self._log("info", f"Delaying execution for {delay_seconds} seconds")
            
            # Sleep in small intervals to allow stop requests
            elapsed = 0
            while elapsed < delay_seconds and not self._stop_requested:
                sleep_time = min(0.1, delay_seconds - elapsed)
                time.sleep(sleep_time)
                elapsed += sleep_time
                
            if self._stop_requested:
                return {'status': 'stopped', 'output': 'Delay interrupted by stop request'}
            return {'status': 'completed', 'output': f'Delayed for {delay_seconds} seconds'}
            
        elif (node.node_type.startswith('schema_') or 
              node.node_type.startswith('action_') or 
              node.node_type == 'action'):
            return self._execute_schema_module(node)
            
        elif (node.node_type.startswith('condition_') or 
              node.node_type == 'condition'):
            return self._execute_condition_node(node)
            
        elif node.node_type == 'set_variable':
            return self._execute_set_variable_node(node)
            
        elif node.node_type == 'file_transfer':
            return self._execute_file_transfer_node(node)
            
        else:
            error_msg = f'Unknown node type: {node.node_type}'
            self._log("error", error_msg)
            return {'status': 'error', 'output': error_msg}
            
    def _execute_schema_module(self, node: WorkflowNode) -> Dict[str, Any]:
        """Execute a schema-based module node"""
        try:
            # Determine if this is a new dynamic action node or legacy schema node
            if node.node_type == 'action':
                # New dynamic action node - get info from parameters
                schema_file = node.parameters.get('schema_file')
                category_name = node.parameters.get('category')
                module_name = node.parameters.get('module')
                
                if not all([schema_file, category_name, module_name]):
                    return {'status': 'error', 'output': 'Missing required parameters: schema_file, category, module'}
                    
                self._log("info", f"Executing dynamic action: {schema_file}/{category_name}/{module_name}")
                
            else:
                # Legacy schema node - get info from module_info
                if not hasattr(node, 'module_info') or not node.module_info:
                    return {'status': 'error', 'output': 'Legacy node missing module_info'}
                    
                module_info = node.module_info
                schema_file = module_info.get('schema_file')
                category_name = module_info.get('category')
                module_name = module_info.get('module_name')
                
                if not all([schema_file, category_name, module_name]):
                    return {'status': 'error', 'output': 'Missing module information in legacy node'}
                    
                self._log("info", f"Executing legacy action: {schema_file}/{category_name}/{module_name}")
            
            # Load schema and get module
            if not self.schema_service:
                return {'status': 'error', 'output': 'Schema service not available'}
                
            schema = self.schema_service.load_schema(schema_file)
            if not schema:
                return {'status': 'error', 'output': f'Failed to load schema: {schema_file}'}
                
            # Get the category
            if category_name not in schema.categories:
                return {'status': 'error', 'output': f'Category {category_name} not found in schema'}
                
            category = schema.categories[category_name]
            
            # Get the module
            if module_name not in category.modules:
                return {'status': 'error', 'output': f'Module {module_name} not found in category {category_name}'}
                
            module = category.modules[module_name]
            
            # Generate command using module and node parameters
            command_parts = [module.command_template]
            
            # Replace parameter placeholders with actual values
            for param_name, param_value in node.parameters.items():
                if param_name not in ['schema_file', 'category', 'module']:  # Skip metadata
                    placeholder = f"{{{param_name}}}"
                    if placeholder in command_parts[0]:
                        command_parts[0] = command_parts[0].replace(placeholder, str(param_value))
            
            command = command_parts[0]
            self._log("info", f"Generated command: {command}")
            
            # Send command to beacon and wait for completion
            beacon = self.beacon_repository.get_beacon(self.beacon_id)
            if not beacon:
                return {'status': 'error', 'output': f'Beacon {self.beacon_id} not found'}
                
            # Set command on beacon
            self.beacon_repository.update_beacon_command(self.beacon_id, command)
            self._log("info", f"Command sent to beacon {self.beacon_id}: {command}")
            
            # Wait for command completion in a thread-safe way
            result = self._wait_for_command_completion(command)
            return result
            
        except Exception as e:
            return {'status': 'error', 'output': f'Schema module execution failed: {str(e)}'}
            
    def _execute_condition_node(self, node: WorkflowNode) -> Dict[str, Any]:
        """Execute a condition node with proper evaluation and branching"""
        return self.condition_processor.execute_condition_node(
            node, self._context, self.workflow.connections
        )
        
    def _execute_set_variable_node(self, node: WorkflowNode) -> Dict[str, Any]:
        """Execute a set_variable node to define and store workflow variables"""
        try:
            # Get variable name and value from parameters (already template-substituted)
            variable_name = node.parameters.get('variable_name', '').strip()
            variable_value = node.parameters.get('variable_value', '').strip()
            
            # Validate required parameters
            if not variable_name:
                return {'status': 'error', 'output': 'Variable name is required but not specified'}
                
            if not variable_value:
                return {'status': 'error', 'output': 'Variable value is required but not specified'}
            
            # Additional validation for variable name format
            if not variable_name.replace('_', '').replace('-', '').isalnum():
                return {'status': 'error', 'output': f'Invalid variable name format: {variable_name}. Use alphanumeric characters, underscores, and hyphens only.'}
            
            # Store the variable in the execution context
            self._context.variables[variable_name] = variable_value
            
            self._log("info", f"Set variable '{variable_name}' = '{variable_value}'")
            
            # Return success result with the set variable information
            return {
                'status': 'completed', 
                'output': f'Variable "{variable_name}" set to: {variable_value}',
                'variable_name': variable_name,
                'variable_value': variable_value
            }
            
        except Exception as e:
            error_msg = f'Failed to set variable: {str(e)}'
            self._log("error", error_msg)
            return {'status': 'error', 'output': error_msg}
        
    def _execute_file_transfer_node(self, node: WorkflowNode) -> Dict[str, Any]:
        """Execute a file_transfer node to queue file upload/download operations"""
        try:
            # Get transfer direction and filename from parameters (already template-substituted)
            transfer_direction = node.parameters.get('transfer_direction', 'to_beacon').strip()
            filename = node.parameters.get('filename', '').strip()
            
            # Validate required parameters
            if not filename:
                return {'status': 'error', 'output': 'Filename is required but not specified'}
                
            if transfer_direction not in ['to_beacon', 'from_beacon']:
                return {'status': 'error', 'output': f'Invalid transfer direction: {transfer_direction}. Must be "to_beacon" or "from_beacon"'}
            
            # Format the appropriate command based on transfer direction
            if transfer_direction == 'to_beacon':
                # Download file to beacon (server -> beacon)
                command = f'download_file {filename}'
                operation_desc = f'Download "{filename}" to beacon'
            else:
                # Upload file from beacon (beacon -> server)
                command = f'upload_file {filename}'
                operation_desc = f'Upload "{filename}" from beacon'
            
            # Queue the command via beacon repository
            if self.beacon_id and self.beacon_repository:
                try:
                    self.beacon_repository.update_beacon_command(self.beacon_id, command)
                    self._log("info", f"File transfer queued: {operation_desc}")
                    
                    # Return success result with the queued operation information
                    return {
                        'status': 'completed', 
                        'output': f'File transfer queued: {operation_desc}',
                        'transfer_direction': transfer_direction,
                        'filename': filename,
                        'command': command
                    }
                    
                except Exception as e:
                    error_msg = f'Failed to queue file transfer command: {str(e)}'
                    self._log("error", error_msg)
                    return {'status': 'error', 'output': error_msg}
            else:
                error_msg = 'No beacon selected or beacon repository not available for file transfer'
                self._log("error", error_msg)
                return {'status': 'error', 'output': error_msg}
            
        except Exception as e:
            error_msg = f'Failed to execute file transfer node: {str(e)}'
            self._log("error", error_msg)
            return {'status': 'error', 'output': error_msg}
        
    def _wait_for_command_completion(self, command: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for a command to complete by monitoring beacon status and output"""
        start_time = time.time()
        command_picked_up = False
        last_output_length = 0
        stable_output_count = 0
        
        self._log("info", f"Waiting for command completion: {command}")
        
        # Get initial output length to detect new output
        initial_output = self._get_beacon_output()
        initial_output_length = len(initial_output)
        
        while time.time() - start_time < timeout and not self._stop_requested:
            try:
                # Get current beacon status
                beacon = self.beacon_repository.get_beacon(self.beacon_id)
                if not beacon:
                    return {'status': 'error', 'output': f'Beacon {self.beacon_id} not found'}
            except Exception as e:
                self._log("warning", f"Database error while checking beacon status: {str(e)}")
                time.sleep(1)
                continue
                
            # Check if beacon is still online
            if beacon.status != 'online':
                return {'status': 'error', 'output': f'Beacon {self.beacon_id} went offline during execution'}
                
            # First, wait for command to be picked up
            if beacon.pending_command and not command_picked_up:
                self._log("debug", "Waiting for command to be picked up by beacon...")
                time.sleep(1)
                continue
                
            # Mark command as picked up when pending_command becomes empty
            if not beacon.pending_command and not command_picked_up:
                command_picked_up = True
                self._log("info", "Command picked up by beacon, waiting for output...")
                
            # Once picked up, wait for new output to appear and stabilize
            if command_picked_up:
                current_output = self._get_beacon_output()
                current_output_length = len(current_output)
                
                # Check if we have new output since command started
                if current_output_length > initial_output_length:
                    # Output is growing, reset stability counter
                    if current_output_length != last_output_length:
                        stable_output_count = 0
                        last_output_length = current_output_length
                    else:
                        # Output length hasn't changed, increment stability
                        stable_output_count += 1
                        
                    # Consider output stable after 3 consecutive checks with same length
                    if stable_output_count >= 3:
                        # Extract new output since command started
                        new_output = current_output[initial_output_length:] if current_output_length > initial_output_length else ""
                        self._log("info", f"Command completed with output length: {len(new_output)}")
                        return {'status': 'completed', 'output': new_output.strip()}
                        
            time.sleep(1)  # Check every second
            
        # Handle timeout or stop request
        if self._stop_requested:
            return {'status': 'stopped', 'output': 'Command execution stopped by user'}
        else:
            # Add a final delay to ensure command completion
            time.sleep(2)
            final_output = self._get_beacon_output()
            new_output = final_output[initial_output_length:] if len(final_output) > initial_output_length else ""
            return {'status': 'timeout', 'output': f'Command timed out after {timeout}s. Partial output: {new_output.strip()[:500]}'}
            
    def _get_beacon_output(self) -> str:
        """Get the current output for the beacon"""
        try:
            # This would typically read from a file or database
            # Implementation depends on how beacon output is stored
            from pathlib import Path
            from config.server_config import ServerConfig
            
            config = ServerConfig()
            output_file = Path(config.LOGS_FOLDER) / f"output_{self.beacon_id}.txt"
            
            if output_file.exists():
                return output_file.read_text(encoding='utf-8', errors='ignore')
            return ""
        except Exception as e:
            self._log("warning", f"Failed to read beacon output: {str(e)}")
            return ""
            
    def _find_next_node(self, current_node: WorkflowNode, result: Dict[str, Any]) -> Optional[WorkflowNode]:
        """Find the next node to execute based on connections and conditions"""
        # Find outgoing connections from current node
        outgoing_connections = [
            conn for conn in self.workflow.connections 
            if conn.source_node_id == current_node.node_id
        ]
        
        if not outgoing_connections:
            return None  # No more nodes to execute
        
        # Handle condition node branching
        if (current_node.node_type == 'condition' or 
            current_node.node_type.startswith('condition_')):
            return self._find_condition_branch(current_node, result, outgoing_connections)
        
        # For non-condition nodes, take the first connection
        next_connection = outgoing_connections[0]
        
        # Find the target node
        for node in self.workflow.nodes:
            if node.node_id == next_connection.target_node_id:
                return node
                
        return None
    
    def _find_condition_branch(self, condition_node: WorkflowNode, result: Dict[str, Any], 
                              outgoing_connections: List[WorkflowConnection]) -> Optional[WorkflowNode]:
        """Find the next node based on condition evaluation result"""
        from services.workflows.node_compatibility import ConnectionType
        
        # Get condition result
        condition_result = result.get('condition_result', False)
        
        # Look for appropriately typed connections
        target_connection_type = (ConnectionType.CONDITIONAL_TRUE if condition_result 
                                else ConnectionType.CONDITIONAL_FALSE)
        
        # Find connection with matching type
        for connection in outgoing_connections:
            if connection.connection_type:
                # Convert string to enum for comparison
                connection_type_str = connection.connection_type
                if connection_type_str == target_connection_type.value:
                    # Find the target node
                    for node in self.workflow.nodes:
                        if node.node_id == connection.target_node_id:
                            self._log("info", f"Condition {condition_node.node_id} branching to {node.node_id} "
                                            f"(result: {condition_result})")
                            return node
        
        # Fallback: if no typed connections found, use simple logic
        # First connection for true, second for false (if available)
        if condition_result and len(outgoing_connections) > 0:
            target_connection = outgoing_connections[0]
        elif not condition_result and len(outgoing_connections) > 1:
            target_connection = outgoing_connections[1]
        elif len(outgoing_connections) > 0:
            # Default to first connection if no appropriate branch found
            target_connection = outgoing_connections[0]
        else:
            return None
        
        # Find the target node
        for node in self.workflow.nodes:
            if node.node_id == target_connection.target_node_id:
                self._log("info", f"Condition {condition_node.node_id} branching to {node.node_id} "
                                f"(fallback logic, result: {condition_result})")
                return node
        
        return None
    
    def _extract_node_variables(self, node: WorkflowNode, result: Dict[str, Any]):
        """Extract variables from node execution results"""
        output = result.get('output', '')
        if not output:
            return
        
        try:
            # Always perform automatic variable extraction
            self.variable_extractor.auto_extract_common_variables(
                output, self._context, node.node_id
            )
            
            # Check if node has custom variable extraction rules
            if 'variable_extraction' in node.parameters:
                extraction_config = node.parameters['variable_extraction']
                if isinstance(extraction_config, dict):
                    extraction_rules = self.variable_extractor.create_extraction_rules_from_config(
                        extraction_config
                    )
                    if extraction_rules:
                        extracted_vars = self.variable_extractor.extract_variables(
                            output, extraction_rules, self._context
                        )
                        self._log("info", f"Extracted {len(extracted_vars)} variables from node {node.node_id}")
        
        except Exception as e:
            self._log("warning", f"Variable extraction failed for node {node.node_id}: {str(e)}")
        
    def _is_final_action_node(self, node: WorkflowNode) -> bool:
        """Check if this action node is the final one before workflow end"""
        # Find connections from this node
        outgoing_connections = [
            conn for conn in self.workflow.connections 
            if conn.source_node_id == node.node_id
        ]
        
        if not outgoing_connections:
            return True  # No outgoing connections, this is final
            
        # Check if all outgoing connections lead to end nodes
        for connection in outgoing_connections:
            target_node = next((n for n in self.workflow.nodes if n.node_id == connection.target_node_id), None)
            if target_node and target_node.node_type != 'end':
                return False  # Found non-end target, not final
                
        return True  # All targets are end nodes or no valid targets found
        
    def _log(self, level: str, message: str):
        """Log a message and emit signal"""
        if self._context:
            log_entry = {
                'timestamp': datetime.now(),
                'level': level,
                'message': message
            }
            self._context.execution_log.append(log_entry)
            
        # Emit signal for main thread logging
        self.log_message.emit(self.execution_id, level, message)