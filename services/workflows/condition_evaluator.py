"""
Condition Evaluator for Workflow Branching

Standalone module for evaluating conditions to avoid circular imports.
Supports various condition types including contains, equals, regex, and numeric comparisons.
"""

import re
from typing import Dict, Any


class ConditionEvaluator:
    """Evaluates conditions for workflow branching"""
    
    @staticmethod
    def evaluate_condition(condition: Dict[str, Any], output: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a condition against output and variables"""
        condition_type = condition.get('type', 'contains')
        
        if condition_type == 'contains':
            return ConditionEvaluator._evaluate_contains(condition, output)
        elif condition_type == 'equals':
            return ConditionEvaluator._evaluate_equals(condition, output)
        elif condition_type == 'not_contains':
            return not ConditionEvaluator._evaluate_contains(condition, output)
        elif condition_type == 'regex':
            return ConditionEvaluator._evaluate_regex(condition, output)
        elif condition_type == 'numeric':
            return ConditionEvaluator._evaluate_numeric(condition, output)
        else:
            return False
    
    @staticmethod
    def _evaluate_contains(condition: Dict[str, Any], output: str) -> bool:
        """Check if output contains the expected value"""
        expected = condition.get('value', '')
        case_sensitive = condition.get('case_sensitive', False)
        
        if case_sensitive:
            return expected in output
        else:
            return expected.lower() in output.lower()
    
    @staticmethod
    def _evaluate_equals(condition: Dict[str, Any], output: str) -> bool:
        """Check if output equals the expected value"""
        expected = condition.get('value', '')
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
            expected_value = float(condition.get('value', 0))
            operator = condition.get('operator', '==')
            
            if operator == '==':
                return output_value == expected_value
            elif operator == '!=':
                return output_value != expected_value
            elif operator == '>':
                return output_value > expected_value
            elif operator == '<':
                return output_value < expected_value
            elif operator == '>=':
                return output_value >= expected_value
            elif operator == '<=':
                return output_value <= expected_value
            else:
                return False
        except (ValueError, IndexError):
            return False