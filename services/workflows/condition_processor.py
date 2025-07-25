"""
Condition Node Processor for Workflow Execution

Handles execution of condition nodes with automatic input piping
and proper branching logic based on condition evaluation results.
"""

from typing import Dict, Any, Optional, List
import re
import json

from .execution_types import ExecutionContext
from .workflow_service import WorkflowNode, WorkflowConnection
from .condition_evaluator import ConditionEvaluator


class ConditionProcessor:
    """Processes condition nodes with automatic input piping and evaluation"""
    
    def __init__(self):
        self.condition_evaluator = ConditionEvaluator()
    
    def execute_condition_node(self, node: WorkflowNode, context: ExecutionContext,
                              workflow_connections: List[WorkflowConnection]) -> Dict[str, Any]:
        """
        Execute a condition node with automatic input piping
        
        Args:
            node: The condition node to execute
            context: Current execution context
            workflow_connections: All workflow connections for finding input
            
        Returns:
            Execution result with condition evaluation outcome
        """
        try:
            # Get input data for the condition (usually from previous node)
            input_data = self._get_condition_input(node, context, workflow_connections)
            
            # Get condition parameters
            condition_config = self._extract_condition_config(node)
            
            # Evaluate the condition
            condition_result = self._evaluate_condition(condition_config, input_data, context.variables)
            
            # Store the condition result for branching logic
            result = {
                'status': 'completed',
                'output': f"Condition evaluated to: {condition_result}",
                'condition_result': condition_result,
                'input_data': input_data,
                'condition_config': condition_config
            }
            
            # Log the evaluation
            print(f"Condition node {node.node_id} evaluated: {condition_result}")
            print(f"  Input: {input_data[:100]}..." if len(input_data) > 100 else f"  Input: {input_data}")
            print(f"  Config: {condition_config}")
            
            return result
            
        except Exception as e:
            error_msg = f"Condition evaluation failed: {str(e)}"
            print(f"ERROR in condition node {node.node_id}: {error_msg}")
            return {
                'status': 'error',
                'output': error_msg,
                'condition_result': False  # Default to false on error
            }
    
    def _get_condition_input(self, node: WorkflowNode, context: ExecutionContext,
                           workflow_connections: List[WorkflowConnection]) -> str:
        """
        Get input data for condition evaluation
        
        Priority order:
        1. Explicit input parameter in node
        2. Previous node output (auto-piping)
        3. Empty string
        """
        # Check if there's an explicit input parameter
        if 'input' in node.parameters:
            return str(node.parameters['input'])
        
        # Auto-pipe from previous node
        previous_node_id = self._find_previous_node(node, workflow_connections)
        if previous_node_id and previous_node_id in context.node_results:
            previous_result = context.node_results[previous_node_id]
            return str(previous_result.get('output', ''))
        
        return ''
    
    def _extract_condition_config(self, node: WorkflowNode) -> Dict[str, Any]:
        """
        Extract condition configuration from node parameters
        
        Supports various parameter formats for flexibility:
        - Direct condition parameters
        - Nested condition object
        - Schema-based condition definitions
        """
        # Start with node parameters
        condition_config = {}
        
        # Look for direct condition parameters
        condition_fields = ['type', 'value', 'pattern', 'operator', 'case_sensitive']
        for field in condition_fields:
            if field in node.parameters:
                condition_config[field] = node.parameters[field]
        
        # Look for nested condition object
        if 'condition' in node.parameters:
            nested_condition = node.parameters['condition']
            if isinstance(nested_condition, dict):
                condition_config.update(nested_condition)
        
        # Set defaults
        if 'type' not in condition_config:
            condition_config['type'] = 'contains'  # Default condition type
        
        # Handle schema-based conditions
        if 'condition_type' in node.parameters:
            condition_config['type'] = node.parameters['condition_type']
        
        if 'condition_value' in node.parameters:
            condition_config['value'] = node.parameters['condition_value']
        
        if 'condition_pattern' in node.parameters:
            condition_config['pattern'] = node.parameters['condition_pattern']
        
        return condition_config
    
    def _evaluate_condition(self, condition_config: Dict[str, Any], 
                          input_data: str, variables: Dict[str, Any]) -> bool:
        """
        Evaluate condition using the ConditionEvaluator
        
        Returns True if condition passes, False if it fails
        """
        try:
            return self.condition_evaluator.evaluate_condition(
                condition_config, input_data, variables
            )
        except Exception as e:
            print(f"Condition evaluation error: {str(e)}")
            return False  # Default to false on evaluation error
    
    def _find_previous_node(self, current_node: WorkflowNode,
                           workflow_connections: List[WorkflowConnection]) -> Optional[str]:
        """Find the immediate predecessor node for the current node"""
        for connection in workflow_connections:
            if connection.target_node_id == current_node.node_id:
                return connection.source_node_id
        return None
    
    def get_condition_branches(self, node: WorkflowNode, 
                              workflow_connections: List[WorkflowConnection]) -> Dict[str, List[str]]:
        """
        Get the branching paths for a condition node
        
        Returns:
            Dictionary with 'true' and 'false' keys containing lists of connected node IDs
        """
        from services.workflows.node_compatibility import ConnectionType
        
        branches = {'true': [], 'false': []}
        
        for connection in workflow_connections:
            if connection.source_node_id == node.node_id:
                # Determine branch type based on connection type
                # This would need to be determined from connection metadata
                # For now, we'll use a simple heuristic
                target_node_id = connection.target_node_id
                
                # Check if connection has type metadata
                if hasattr(connection, 'connection_type'):
                    if connection.connection_type == ConnectionType.CONDITIONAL_TRUE:
                        branches['true'].append(target_node_id)
                    elif connection.connection_type == ConnectionType.CONDITIONAL_FALSE:
                        branches['false'].append(target_node_id)
                    else:
                        # Default branch for non-typed connections
                        branches['true'].append(target_node_id)
                else:
                    # No type information, add to true branch by default
                    branches['true'].append(target_node_id)
        
        return branches
    
    def supports_condition_type(self, condition_type: str) -> bool:
        """Check if a condition type is supported"""
        supported_types = [
            'contains', 'equals', 'not_contains', 'regex', 'numeric',
            'exists', 'empty', 'length_greater', 'length_less'
        ]
        return condition_type in supported_types
    
    def get_condition_schema(self) -> Dict[str, Any]:
        """
        Get the schema for condition node parameters
        
        This can be used by UI components to generate appropriate
        parameter input forms for condition nodes.
        """
        return {
            'type': {
                'type': 'select',
                'options': [
                    'contains', 'equals', 'not_contains', 'regex', 'numeric'
                ],
                'default': 'contains',
                'description': 'Type of condition to evaluate'
            },
            'value': {
                'type': 'text',
                'description': 'Value to compare against (for contains, equals, numeric)'
            },
            'pattern': {
                'type': 'text',
                'description': 'Regular expression pattern (for regex type)'
            },
            'operator': {
                'type': 'select',
                'options': ['==', '!=', '>', '<', '>=', '<='],
                'default': '==',
                'description': 'Numeric comparison operator (for numeric type)'
            },
            'case_sensitive': {
                'type': 'boolean',
                'default': False,
                'description': 'Whether comparison should be case sensitive'
            },
            'input': {
                'type': 'textarea',
                'description': 'Explicit input data (optional - uses previous node output if not specified)'
            }
        }