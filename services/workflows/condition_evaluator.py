"""
Condition Evaluator for Workflow Branching

Standalone module for evaluating conditions to avoid circular imports.
Supports various condition types including contains, equals, regex, and numeric comparisons.
"""

import re
from typing import Dict, Any

# Import parameter template engine for variable resolution
try:
    from .parameter_template_engine import ParameterTemplateEngine
    TEMPLATE_ENGINE_AVAILABLE = True
except ImportError:
    TEMPLATE_ENGINE_AVAILABLE = False


class ConditionEvaluator:
    """Evaluates conditions for workflow branching"""
    
    @staticmethod
    def evaluate_condition(condition: Dict[str, Any], output: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a condition against output and variables"""
        # Resolve the input variable to get the actual value to compare
        input_value = ConditionEvaluator._resolve_input_variable(condition, output, variables)
        
        # Get condition type (supporting both old 'type' and new 'condition_type' keys)
        condition_type = condition.get('condition_type', condition.get('type', 'contains'))
        
        if condition_type == 'contains':
            return ConditionEvaluator._evaluate_contains(condition, input_value)
        elif condition_type == 'equals':
            return ConditionEvaluator._evaluate_equals(condition, input_value)
        elif condition_type == 'not_contains':
            return not ConditionEvaluator._evaluate_contains(condition, input_value)
        elif condition_type == 'regex':
            return ConditionEvaluator._evaluate_regex(condition, input_value)
        elif condition_type == 'numeric':
            return ConditionEvaluator._evaluate_numeric(condition, input_value)
        else:
            return False
    
    @staticmethod
    def _resolve_input_variable(condition: Dict[str, Any], output: str, variables: Dict[str, Any]) -> str:
        """Resolve the input variable to get the actual value to compare"""
        # Get the input variable (default to previous_output for backward compatibility)
        input_variable = condition.get('input_variable', '{{previous_output}}')
        
        # If no template engine available, handle basic cases manually
        if not TEMPLATE_ENGINE_AVAILABLE:
            if input_variable == '{{previous_output}}':
                return output
            elif input_variable in variables:
                return str(variables.get(input_variable, ''))
            else:
                # Try to extract variable name from template syntax
                if input_variable.startswith('{{') and input_variable.endswith('}}'):
                    var_name = input_variable[2:-2].strip()
                    return str(variables.get(var_name, ''))
                return input_variable
        
        # Use template engine for full variable resolution
        try:
            # Create a combined context with variables and previous_output
            template_context = variables.copy()
            template_context['previous_output'] = output
            
            engine = ParameterTemplateEngine()
            resolved_value = engine.resolve_template(input_variable, template_context)
            return str(resolved_value)
        except Exception as e:
            print(f"Error resolving input variable '{input_variable}': {e}")
            # Fallback to previous_output for safety
            return output
    
    @staticmethod
    def _evaluate_contains(condition: Dict[str, Any], output: str) -> bool:
        """Check if output contains the expected value"""
        # Support both old 'value' and new 'condition_value' parameter names
        expected = condition.get('condition_value', condition.get('value', ''))
        case_sensitive = condition.get('case_sensitive', False)
        
        if case_sensitive:
            return expected in output
        else:
            return expected.lower() in output.lower()
    
    @staticmethod
    def _evaluate_equals(condition: Dict[str, Any], output: str) -> bool:
        """Check if output equals the expected value"""
        # Support both old 'value' and new 'condition_value' parameter names
        expected = condition.get('condition_value', condition.get('value', ''))
        case_sensitive = condition.get('case_sensitive', False)
        
        output_clean = output.strip()
        
        if case_sensitive:
            return output_clean == expected
        else:
            return output_clean.lower() == expected.lower()
    
    @staticmethod
    def _evaluate_regex(condition: Dict[str, Any], output: str) -> bool:
        """Check if output matches the regex pattern"""
        pattern = condition.get('pattern', '')
        flags = 0
        
        if not condition.get('case_sensitive', True):
            flags |= re.IGNORECASE
            
        try:
            return bool(re.search(pattern, output, flags))
        except re.error:
            return False
    
    @staticmethod
    def _evaluate_numeric(condition: Dict[str, Any], output: str) -> bool:
        """Evaluate numeric condition"""
        try:
            # Extract numbers from output
            numbers = re.findall(r'-?\d+\.?\d*', output)
            if not numbers:
                return False
                
            output_value = float(numbers[0])  # Take first number found
            # Support both old 'value' and new 'value' parameter names for numeric conditions
            expected_value = float(condition.get('value', 0))
            operator = condition.get('operator', '==')
            
            # Map operator names from UI to comparison operators
            operator_map = {
                'equals': '==',
                'greater': '>',
                'less': '<', 
                'greater_equal': '>=',
                'less_equal': '<='
            }
            operator = operator_map.get(operator, operator)
            
            if operator == '==' or operator == 'equals':
                return output_value == expected_value
            elif operator == '!=' or operator == 'not_equals':
                return output_value != expected_value
            elif operator == '>' or operator == 'greater':
                return output_value > expected_value
            elif operator == '<' or operator == 'less':
                return output_value < expected_value
            elif operator == '>=' or operator == 'greater_equal':
                return output_value >= expected_value
            elif operator == '<=' or operator == 'less_equal':
                return output_value <= expected_value
            else:
                return False
        except (ValueError, IndexError):
            return False