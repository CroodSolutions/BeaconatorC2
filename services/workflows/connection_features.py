"""
Advanced connection features for workflow system.
Provides variable substitution, conditional connections, and data flow management.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import re
from PyQt6.QtCore import QObject, pyqtSignal


class VariableType(Enum):
    """Types of variables that can be used in connections"""
    OUTPUT = "output"           # Previous node output
    PARAMETER = "parameter"     # Node parameter value
    GLOBAL = "global"          # Global workflow variable
    ENVIRONMENT = "environment" # Environment variable
    COMPUTED = "computed"      # Computed/derived value


@dataclass
class VariableReference:
    """Reference to a variable in the workflow"""
    name: str
    type: VariableType
    source_node: Optional[str] = None  # For OUTPUT type
    default_value: Any = None
    transform: Optional[str] = None    # Optional transformation function


@dataclass
class ConnectionCondition:
    """Condition that must be met for connection to execute"""
    expression: str
    description: str
    variables: List[VariableReference]
    
    
class ConnectionFeatureManager(QObject):
    """Manages advanced connection features like variables and conditions"""
    
    variable_updated = pyqtSignal(str, object)  # variable_name, value
    condition_evaluated = pyqtSignal(str, bool)  # condition_id, result
    
    def __init__(self):
        super().__init__()
        self.variables = {}  # Global workflow variables
        self.node_outputs = {}  # Node output cache
        self.evaluator = ExpressionEvaluator()
        
    def register_variable(self, name: str, value: Any, var_type: VariableType = VariableType.GLOBAL):
        """Register a global variable"""
        self.variables[name] = {
            'value': value,
            'type': var_type,
            'timestamp': self._get_timestamp()
        }
        self.variable_updated.emit(name, value)
        
    def set_node_output(self, node_id: str, output_value: Any):
        """Set the output value for a node"""
        self.node_outputs[node_id] = {
            'value': output_value,
            'timestamp': self._get_timestamp()
        }
        # Also register as a variable
        self.register_variable(f"node_{node_id}_output", output_value, VariableType.OUTPUT)
        
    def resolve_variable(self, var_ref: VariableReference) -> Any:
        """Resolve a variable reference to its current value"""
        try:
            if var_ref.type == VariableType.OUTPUT:
                if var_ref.source_node and var_ref.source_node in self.node_outputs:
                    value = self.node_outputs[var_ref.source_node]['value']
                else:
                    value = var_ref.default_value
                    
            elif var_ref.type == VariableType.GLOBAL:
                if var_ref.name in self.variables:
                    value = self.variables[var_ref.name]['value']
                else:
                    value = var_ref.default_value
                    
            elif var_ref.type == VariableType.ENVIRONMENT:
                import os
                value = os.environ.get(var_ref.name, var_ref.default_value)
                
            else:
                value = var_ref.default_value
                
            # Apply transformation if specified
            if var_ref.transform and value is not None:
                value = self._apply_transform(value, var_ref.transform)
                
            return value
            
        except Exception as e:
            print(f"Error resolving variable {var_ref.name}: {e}")
            return var_ref.default_value
            
    def substitute_variables(self, text: str, context: Dict[str, Any] = None) -> str:
        """Substitute variables in text using ${variable_name} syntax"""
        if not text:
            return text
            
        context = context or {}
        
        # Pattern to match ${variable_name} or ${node_id.output}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_expr = match.group(1)
            
            # Handle node output references (node_id.output)
            if '.' in var_expr:
                parts = var_expr.split('.', 1)
                node_id, attr = parts
                if attr == 'output' and node_id in self.node_outputs:
                    return str(self.node_outputs[node_id]['value'])
                    
            # Handle direct variable references
            if var_expr in context:
                return str(context[var_expr])
            elif var_expr in self.variables:
                return str(self.variables[var_expr]['value'])
            else:
                # Return the original expression if variable not found
                return match.group(0)
                
        return re.sub(pattern, replace_var, text)
        
    def evaluate_condition(self, condition: ConnectionCondition, context: Dict[str, Any] = None) -> bool:
        """Evaluate a connection condition"""
        try:
            # Build evaluation context
            eval_context = context or {}
            
            # Add variables from condition
            for var_ref in condition.variables:
                value = self.resolve_variable(var_ref)
                eval_context[var_ref.name] = value
                
            # Add global variables
            for name, var_data in self.variables.items():
                if name not in eval_context:
                    eval_context[name] = var_data['value']
                    
            # Evaluate the condition
            result = self.evaluator.evaluate(condition.expression, eval_context)
            self.condition_evaluated.emit(condition.expression, result)
            return bool(result)
            
        except Exception as e:
            print(f"Error evaluating condition '{condition.expression}': {e}")
            return False
            
    def _apply_transform(self, value: Any, transform: str) -> Any:
        """Apply a transformation function to a value"""
        try:
            # Simple transformations
            if transform == "upper":
                return str(value).upper()
            elif transform == "lower":
                return str(value).lower()
            elif transform == "length":
                return len(str(value))
            elif transform == "int":
                return int(value)
            elif transform == "float":
                return float(value)
            elif transform == "strip":
                return str(value).strip()
            elif transform.startswith("substring("):
                # Extract parameters: substring(start,end)
                params = transform[10:-1].split(',')
                start = int(params[0]) if params[0] else 0
                end = int(params[1]) if len(params) > 1 and params[1] else None
                return str(value)[start:end]
            else:
                return value
                
        except Exception as e:
            print(f"Error applying transform '{transform}': {e}")
            return value
            
    def _get_timestamp(self):
        """Get current timestamp"""
        import time
        return time.time()
        
    def get_available_variables(self) -> Dict[str, Dict]:
        """Get all available variables for UI display"""
        available = {}
        
        # Global variables
        for name, data in self.variables.items():
            available[name] = {
                'type': 'global',
                'value': data['value'],
                'display_name': name
            }
            
        # Node outputs
        for node_id, data in self.node_outputs.items():
            var_name = f"{node_id}.output"
            available[var_name] = {
                'type': 'output',
                'value': data['value'],
                'display_name': f"Output from {node_id}"
            }
            
        return available


class ExpressionEvaluator:
    """Safe expression evaluator for conditions"""
    
    def __init__(self):
        # Allowed functions for expressions
        self.allowed_functions = {
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'abs': abs,
            'min': min,
            'max': max,
            'contains': lambda text, substr: substr in text,
            'startswith': lambda text, prefix: text.startswith(prefix),
            'endswith': lambda text, suffix: text.endswith(suffix),
            'matches': self._regex_match,
            'isEmpty': lambda x: not x or str(x).strip() == '',
            'isNumber': self._is_number,
        }
        
    def evaluate(self, expression: str, context: Dict[str, Any]) -> Any:
        """Safely evaluate an expression with given context"""
        # Build safe evaluation environment
        safe_dict = {
            '__builtins__': {},
            **self.allowed_functions,
            **context
        }
        
        try:
            # Use eval with restricted environment
            result = eval(expression, safe_dict)
            return result
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")
            
    def _regex_match(self, text: str, pattern: str) -> bool:
        """Check if text matches regex pattern"""
        try:
            import re
            return bool(re.search(pattern, str(text)))
        except:
            return False
            
    def _is_number(self, value: Any) -> bool:
        """Check if value is a number"""
        try:
            float(value)
            return True
        except:
            return False


class ConnectionDataFlow:
    """Manages data flow through connections with transformations"""
    
    def __init__(self, feature_manager: ConnectionFeatureManager):
        self.feature_manager = feature_manager
        self.flow_history = []
        
    def process_connection_data(self, source_node_id: str, target_node_id: str, 
                              data: Any, transformations: List[Dict] = None) -> Any:
        """Process data flowing through a connection with optional transformations"""
        processed_data = data
        
        # Apply transformations in sequence
        if transformations:
            for transform in transformations:
                processed_data = self._apply_transformation(processed_data, transform)
                
        # Record flow
        self.flow_history.append({
            'source': source_node_id,
            'target': target_node_id,
            'original_data': data,
            'processed_data': processed_data,
            'transformations': transformations or [],
            'timestamp': self.feature_manager._get_timestamp()
        })
        
        return processed_data
        
    def _apply_transformation(self, data: Any, transform: Dict) -> Any:
        """Apply a single data transformation"""
        transform_type = transform.get('type')
        
        if transform_type == 'map':
            # Map values using provided mapping
            mapping = transform.get('mapping', {})
            return mapping.get(str(data), data)
            
        elif transform_type == 'filter':
            # Filter data based on condition
            condition = transform.get('condition')
            if condition:
                try:
                    context = {'value': data}
                    if self.feature_manager.evaluator.evaluate(condition, context):
                        return data
                    else:
                        return None
                except:
                    return data
                    
        elif transform_type == 'format':
            # Format data using template
            template = transform.get('template', '{value}')
            return template.format(value=data)
            
        elif transform_type == 'extract':
            # Extract part of data using regex
            pattern = transform.get('pattern')
            if pattern:
                try:
                    import re
                    match = re.search(pattern, str(data))
                    if match:
                        return match.group(1) if match.groups() else match.group(0)
                except:
                    pass
                    
        return data
        
    def get_flow_history(self, limit: int = 100) -> List[Dict]:
        """Get recent data flow history"""
        return self.flow_history[-limit:]
        
    def clear_history(self):
        """Clear flow history"""
        self.flow_history.clear()