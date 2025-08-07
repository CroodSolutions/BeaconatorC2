"""
Parameter Template Engine for Workflow Variable Substitution

Provides templating system for workflow parameters that supports:
- Previous node output: {{previous_output}}
- Specific node output: {{node_<id>.output}}
- Workflow variables: {{variables.<name>}}
- Input data fields: {{input.<field>}}
"""

import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .execution_types import ExecutionContext
from .workflow_service import WorkflowNode, WorkflowConnection


@dataclass
class TemplateVariable:
    """Represents a template variable and its metadata"""
    name: str
    type: str  # 'previous_output', 'node_output', 'variable', 'input'
    value: Any
    description: str = ""


class ParameterTemplateEngine:
    """Engine for substituting template variables in workflow parameters"""
    
    def __init__(self):
        # Regex pattern to match template variables: {{variable_name}} or {{type.name}}
        self.template_pattern = re.compile(r'\{\{([^}]+)\}\}')
        
    def substitute_parameters(self, parameters: Dict[str, Any], context: ExecutionContext, 
                            current_node: WorkflowNode, workflow_connections: List[WorkflowConnection]) -> Dict[str, Any]:
        """
        Substitute template variables in node parameters
        
        Args:
            parameters: Node parameters to process
            context: Current execution context with variables and node results
            current_node: The node whose parameters are being processed
            workflow_connections: All workflow connections for finding previous nodes
            
        Returns:
            Parameters with template variables substituted
        """
        substituted_params = {}
        
        for key, value in parameters.items():
            if isinstance(value, str):
                substituted_params[key] = self._substitute_string(
                    value, context, current_node, workflow_connections
                )
            elif isinstance(value, dict):
                substituted_params[key] = self._substitute_dict(
                    value, context, current_node, workflow_connections
                )
            elif isinstance(value, list):
                substituted_params[key] = self._substitute_list(
                    value, context, current_node, workflow_connections
                )
            else:
                # Non-string values are passed through unchanged
                substituted_params[key] = value
                
        return substituted_params
    
    def _substitute_string(self, text: str, context: ExecutionContext, 
                          current_node: WorkflowNode, workflow_connections: List[WorkflowConnection]) -> str:
        """Substitute template variables in a string"""
        def replace_match(match):
            variable_expr = match.group(1).strip()
            return self._resolve_variable(variable_expr, context, current_node, workflow_connections)
        
        return self.template_pattern.sub(replace_match, text)
    
    def _substitute_dict(self, data: Dict[str, Any], context: ExecutionContext,
                        current_node: WorkflowNode, workflow_connections: List[WorkflowConnection]) -> Dict[str, Any]:
        """Recursively substitute template variables in a dictionary"""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._substitute_string(value, context, current_node, workflow_connections)
            elif isinstance(value, dict):
                result[key] = self._substitute_dict(value, context, current_node, workflow_connections)
            elif isinstance(value, list):
                result[key] = self._substitute_list(value, context, current_node, workflow_connections)
            else:
                result[key] = value
        return result
    
    def _substitute_list(self, data: List[Any], context: ExecutionContext,
                        current_node: WorkflowNode, workflow_connections: List[WorkflowConnection]) -> List[Any]:
        """Recursively substitute template variables in a list"""
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(self._substitute_string(item, context, current_node, workflow_connections))
            elif isinstance(item, dict):
                result.append(self._substitute_dict(item, context, current_node, workflow_connections))
            elif isinstance(item, list):
                result.append(self._substitute_list(item, context, current_node, workflow_connections))
            else:
                result.append(item)
        return result
    
    def _resolve_variable(self, variable_expr: str, context: ExecutionContext,
                         current_node: WorkflowNode, workflow_connections: List[WorkflowConnection]) -> str:
        """
        Resolve a template variable expression to its actual value
        
        Supported patterns:
        - previous_output: Output from the immediate predecessor node
        - node_<id>.output: Output from a specific node by ID
        - variables.<name>: Workflow variable by name
        - input.<field>: Field from input data (for condition nodes)
        """
        try:
            # Handle previous_output
            if variable_expr == 'previous_output':
                previous_node_id = self._find_previous_node(current_node, workflow_connections)
                if previous_node_id and previous_node_id in context.node_results:
                    result = context.node_results[previous_node_id]
                    return str(result.get('output', ''))
                return ''
            
            # Handle node_<id>.output
            if variable_expr.startswith('node_') and variable_expr.endswith('.output'):
                node_id = variable_expr[5:-7]  # Remove 'node_' prefix and '.output' suffix
                if node_id in context.node_results:
                    result = context.node_results[node_id]
                    return str(result.get('output', ''))
                return ''
            
            # Handle variables.<name>
            if variable_expr.startswith('variables.'):
                var_name = variable_expr[10:]  # Remove 'variables.' prefix
                if var_name in context.variables:
                    return str(context.variables[var_name])
                return ''
            
            # Handle input.<field> - for condition nodes processing previous output
            if variable_expr.startswith('input.'):
                field_name = variable_expr[6:]  # Remove 'input.' prefix
                previous_node_id = self._find_previous_node(current_node, workflow_connections)
                if previous_node_id and previous_node_id in context.node_results:
                    result = context.node_results[previous_node_id]
                    output = result.get('output', '')
                    
                    # Try to parse output as structured data
                    if field_name == 'raw':
                        return str(output)
                    elif field_name == 'length':
                        return str(len(output))
                    elif field_name == 'lines':
                        return str(len(output.splitlines()) if output else 0)
                    else:
                        # For other fields, try to extract from structured output
                        return self._extract_field_from_output(output, field_name)
                return ''
            
            # If no pattern matches, return the original expression
            return f"{{{{{variable_expr}}}}}"
            
        except Exception as e:
            print(f"Error resolving template variable '{variable_expr}': {str(e)}")
            return f"{{{{{variable_expr}}}}}"  # Return original on error
    
    def _find_previous_node(self, current_node: WorkflowNode, 
                           workflow_connections: List[WorkflowConnection]) -> Optional[str]:
        """Find the immediate predecessor node for the current node"""
        for connection in workflow_connections:
            try:
                # Handle canvas connections (have start_node/end_node objects)
                if hasattr(connection, 'start_node') and hasattr(connection, 'end_node'):
                    if hasattr(connection.end_node, 'node_id') and connection.end_node.node_id == current_node.node_id:
                        if hasattr(connection.start_node, 'node_id'):
                            return connection.start_node.node_id
                # Handle service connections (have source_node_id/target_node_id)
                elif hasattr(connection, 'source_node_id') and hasattr(connection, 'target_node_id'):
                    if connection.target_node_id == current_node.node_id:
                        return connection.source_node_id
            except Exception:
                continue
        return None
    
    def _extract_field_from_output(self, output: str, field_name: str) -> str:
        """
        Attempt to extract a specific field from node output
        
        This tries various parsing strategies:
        1. JSON parsing if output looks like JSON
        2. Key-value pair extraction
        3. Line-based extraction
        """
        try:
            # Try JSON parsing first
            import json
            if output.strip().startswith(('{', '[')):
                data = json.loads(output)
                if isinstance(data, dict) and field_name in data:
                    return str(data[field_name])
                elif isinstance(data, list) and field_name.isdigit():
                    index = int(field_name)
                    if 0 <= index < len(data):
                        return str(data[index])
        except (json.JSONDecodeError, ValueError, IndexError):
            pass
        
        # Try key-value pair extraction (key: value or key=value)
        for line in output.splitlines():
            line = line.strip()
            for separator in [':', '=']:
                if separator in line:
                    key, value = line.split(separator, 1)
                    if key.strip().lower() == field_name.lower():
                        return value.strip()
        
        # Try line-based extraction (field_name as line number)
        if field_name.startswith('line'):
            try:
                line_num = int(field_name[4:]) if len(field_name) > 4 else 1
                lines = output.splitlines()
                if 1 <= line_num <= len(lines):
                    return lines[line_num - 1]
            except ValueError:
                pass
        
        return ''
    
    def get_available_variables(self, context: Optional[ExecutionContext], 
                               current_node: WorkflowNode, 
                               workflow_connections: List[WorkflowConnection],
                               canvas_variables: Optional[Dict[str, Any]] = None,
                               all_nodes: Optional[List[WorkflowNode]] = None) -> List[TemplateVariable]:
        """
        Get list of available template variables for the current node
        
        This is useful for UI components that want to show users what variables
        they can use in their parameter templates.
        
        Args:
            context: Execution context (may be None during design time)
            current_node: Current workflow node
            workflow_connections: Workflow connections
            canvas_variables: Canvas workflow variables (for design-time editing)
        """
        variables = []
        
        # Add previous_output if there's a previous node
        previous_node_id = self._find_previous_node(current_node, workflow_connections)
        if previous_node_id:
            variables.append(TemplateVariable(
                name="previous_output",
                type="previous_output",
                value="{{previous_output}}",
                description="Output from the previous node"
            ))
        
        # Add all node outputs (runtime context)
        if context and hasattr(context, 'node_results'):
            for node_id, result in context.node_results.items():
                if node_id != current_node.node_id:  # Don't include self
                    variables.append(TemplateVariable(
                        name=f"node_{node_id}.output",
                        type="node_output",
                        value=f"{{{{node_{node_id}.output}}}}",
                        description=f"Output from node {node_id}"
                    ))
        
        # Add all workflow nodes for design-time (when context is not available)
        elif all_nodes or workflow_connections:
            # Prefer using all_nodes if available (more complete)
            if all_nodes:
                workflow_nodes = [node for node in all_nodes if hasattr(node, 'node_id') and node.node_id != current_node.node_id]
            else:
                workflow_nodes = self._get_workflow_nodes_for_design_time(current_node, workflow_connections)
            
            for node in workflow_nodes:
                # Create friendly display name using node title or type
                node_display_name = getattr(node, 'title', None)
                if not node_display_name:
                    node_type = getattr(node, 'node_type', 'unknown')
                    node_display_name = f"{node_type.replace('_', ' ').title()} Node"
                
                # Include module information for action nodes
                module_info = ""
                if hasattr(node, 'parameters') and node.parameters:
                    # Check for module or action_name in parameters
                    module_name = node.parameters.get('module')
                    action_name = node.parameters.get('action_name')
                    if module_name:
                        module_info = f" ({module_name})"
                    elif action_name:
                        module_info = f" ({action_name})"
                    
                if hasattr(node, 'node_id'):
                    # Create enhanced display name with module info
                    enhanced_name = f"{node_display_name}{module_info}"
                    variables.append(TemplateVariable(
                        name=f"{enhanced_name} - Output",
                        type="node_output", 
                        value=f"{{{{node_{node.node_id}.output}}}}",
                        description=f"Output from {enhanced_name} (ID: {node.node_id})"
                    ))
        
        # Add workflow variables from execution context
        if context and hasattr(context, 'variables'):
            for var_name, var_value in context.variables.items():
                variables.append(TemplateVariable(
                    name=f"variables.{var_name}",
                    type="variable",
                    value=f"{{{{variables.{var_name}}}}}",
                    description=f"Workflow variable: {var_name} (runtime)"
                ))
        
        # Add canvas workflow variables (for design-time editing)
        if canvas_variables:
            for var_name, var_value in canvas_variables.items():
                variables.append(TemplateVariable(
                    name=f"variables.{var_name}",
                    type="variable", 
                    value=f"{{{{variables.{var_name}}}}}",
                    description=f"Canvas variable: {var_name} (current value: {var_value})"
                ))
        
        # Add common node data fields (previously "input" fields)
        if current_node.node_type == 'condition' or current_node.node_type.startswith('condition_'):
            node_data_fields = [
                ("input.raw", "Raw input text"),
                ("input.length", "Input text length"), 
                ("input.lines", "Number of lines in input"),
                ("input.line1", "First line of input"),
                ("input.line2", "Second line of input")
            ]
            
            for field_name, description in node_data_fields:
                variables.append(TemplateVariable(
                    name=field_name,
                    type="nodes",  # Changed from "input" to "nodes"
                    value=f"{{{{{field_name}}}}}",
                    description=description
                ))
        
        return variables
    
    def _get_workflow_nodes_for_design_time(self, current_node: WorkflowNode, 
                                           workflow_connections: List[WorkflowConnection]) -> List[WorkflowNode]:
        """
        Extract all workflow nodes from connections for design-time variable generation
        
        Args:
            current_node: The current node
            workflow_connections: All workflow connections
            
        Returns:
            List of all nodes that appear before the current node in the workflow
        """
        # Collect all unique nodes from connections
        all_nodes = set()
        current_node_id = getattr(current_node, 'node_id', None)
        
        if not current_node_id:
            return []
        
        # Add nodes from connections - handle both service and canvas connection types
        for connection in workflow_connections:
            try:
                # Canvas WorkflowConnection (has start_node and end_node objects)
                if hasattr(connection, 'start_node') and hasattr(connection, 'end_node'):
                    start_node = connection.start_node
                    end_node = connection.end_node
                    
                    # Only include nodes that come before the current node
                    if hasattr(end_node, 'node_id') and end_node.node_id == current_node_id:
                        all_nodes.add(start_node)
                    # Also add any nodes that are not the current node for broader availability
                    elif hasattr(start_node, 'node_id') and start_node.node_id != current_node_id:
                        all_nodes.add(start_node)
                    if hasattr(end_node, 'node_id') and end_node.node_id != current_node_id:
                        all_nodes.add(end_node)
                        
                # Service WorkflowConnection (has source_node_id and target_node_id)
                elif hasattr(connection, 'source_node_id') and hasattr(connection, 'target_node_id'):
                    # We can't get node objects from IDs in this context, skip for now
                    pass
                    
            except Exception:
                continue
        
        return list(all_nodes)
    
    def validate_template(self, template_string: str) -> tuple[bool, str]:
        """
        Validate a template string for syntax errors
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # Find all template variables
            matches = self.template_pattern.findall(template_string)
            
            for variable_expr in matches:
                variable_expr = variable_expr.strip()
                
                # Validate variable expression format
                if not variable_expr:
                    return False, "Empty template variable found"
                
                # Check for valid patterns
                valid_patterns = [
                    'previous_output',
                    r'node_\w+\.output',
                    r'variables\.\w+',
                    r'input\.\w+'
                ]
                
                is_valid_pattern = any(
                    re.match(pattern + '$', variable_expr) 
                    for pattern in valid_patterns
                )
                
                if not is_valid_pattern:
                    return False, f"Invalid template variable pattern: {variable_expr}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Template validation error: {str(e)}"