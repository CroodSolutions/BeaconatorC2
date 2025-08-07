"""
Variable Extraction System for Workflow Output Processing

Provides mechanisms to extract and store variables from node outputs
for use in subsequent workflow steps.
"""

import re
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .execution_types import ExecutionContext


@dataclass
class ExtractionRule:
    """Defines how to extract a variable from output"""
    variable_name: str
    extraction_type: str  # 'regex', 'json_path', 'line', 'key_value'
    pattern: str
    description: str = ""
    required: bool = False


class VariableExtractor:
    """Extracts variables from node outputs using configurable rules"""
    
    def __init__(self):
        self.default_extractors = {
            'regex': self._extract_regex,
            'json_path': self._extract_json_path,
            'line': self._extract_line,
            'key_value': self._extract_key_value,
            'first_word': self._extract_first_word,
            'last_word': self._extract_last_word,
            'length': self._extract_length,
            'line_count': self._extract_line_count
        }
    
    def extract_variables(self, output: str, extraction_rules: List[ExtractionRule], 
                         context: ExecutionContext) -> Dict[str, Any]:
        """
        Extract variables from output using the provided rules
        
        Args:
            output: The output text to extract from
            extraction_rules: List of extraction rules to apply
            context: Current execution context (for storing variables)
            
        Returns:
            Dictionary of extracted variables
        """
        extracted_vars = {}
        
        for rule in extraction_rules:
            try:
                extractor = self.default_extractors.get(rule.extraction_type)
                if extractor:
                    value = extractor(output, rule.pattern)
                    if value is not None:
                        extracted_vars[rule.variable_name] = value
                        # Also store in execution context
                        context.variables[rule.variable_name] = value
                        print(f"Extracted variable '{rule.variable_name}': {value}")
                    elif rule.required:
                        print(f"WARNING: Required variable '{rule.variable_name}' could not be extracted")
                else:
                    print(f"WARNING: Unknown extraction type '{rule.extraction_type}' for variable '{rule.variable_name}'")
            except Exception as e:
                error_msg = f"Error extracting variable '{rule.variable_name}': {str(e)}"
                print(f"ERROR: {error_msg}")
                if rule.required:
                    raise Exception(error_msg)
        
        return extracted_vars
    
    def _extract_regex(self, output: str, pattern: str) -> Optional[str]:
        """Extract using regular expression"""
        try:
            match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
            if match:
                # Return first group if available, otherwise the whole match
                return match.group(1) if match.groups() else match.group(0)
            return None
        except re.error as e:
            print(f"Invalid regex pattern '{pattern}': {str(e)}")
            return None
    
    def _extract_json_path(self, output: str, json_path: str) -> Optional[Any]:
        """Extract from JSON output using simple path notation"""
        try:
            # Try to parse as JSON
            data = json.loads(output.strip())
            
            # Simple path parsing (e.g., "user.name" or "items[0].id")
            path_parts = json_path.split('.')
            current = data
            
            for part in path_parts:
                # Handle array indices like "items[0]"
                if '[' in part and ']' in part:
                    key, index_part = part.split('[', 1)
                    index = int(index_part.rstrip(']'))
                    if key:
                        current = current[key][index]
                    else:
                        current = current[index]
                else:
                    current = current[part]
            
            return current
        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            print(f"JSON path extraction failed for '{json_path}': {str(e)}")
            return None
    
    def _extract_line(self, output: str, line_spec: str) -> Optional[str]:
        """Extract specific line(s) from output"""
        try:
            lines = output.splitlines()
            
            if line_spec.isdigit():
                # Single line number (1-based)
                line_num = int(line_spec)
                if 1 <= line_num <= len(lines):
                    return lines[line_num - 1]
            elif '-' in line_spec:
                # Line range (e.g., "2-5")
                start, end = map(int, line_spec.split('-'))
                if 1 <= start <= len(lines) and 1 <= end <= len(lines):
                    return '\n'.join(lines[start-1:end])
            elif line_spec == 'first':
                return lines[0] if lines else None
            elif line_spec == 'last':
                return lines[-1] if lines else None
            
            return None
        except (ValueError, IndexError) as e:
            print(f"Line extraction failed for '{line_spec}': {str(e)}")
            return None
    
    def _extract_key_value(self, output: str, key: str) -> Optional[str]:
        """Extract value for a specific key from key-value pairs"""
        try:
            for line in output.splitlines():
                line = line.strip()
                
                # Try different separators
                for separator in [':', '=', '\t']:
                    if separator in line:
                        parts = line.split(separator, 1)
                        if len(parts) == 2:
                            line_key = parts[0].strip()
                            line_value = parts[1].strip()
                            
                            # Case-insensitive key matching
                            if line_key.lower() == key.lower():
                                return line_value
            
            return None
        except Exception as e:
            print(f"Key-value extraction failed for key '{key}': {str(e)}")
            return None
    
    def _extract_first_word(self, output: str, _: str) -> Optional[str]:
        """Extract the first word from output"""
        words = output.strip().split()
        return words[0] if words else None
    
    def _extract_last_word(self, output: str, _: str) -> Optional[str]:
        """Extract the last word from output"""
        words = output.strip().split()
        return words[-1] if words else None
    
    def _extract_length(self, output: str, _: str) -> int:
        """Extract the length of the output"""
        return len(output)
    
    def _extract_line_count(self, output: str, _: str) -> int:
        """Extract the number of lines in output"""
        return len(output.splitlines())
    
    def auto_extract_common_variables(self, output: str, context: ExecutionContext, 
                                    node_id: str) -> Dict[str, Any]:
        """
        Automatically extract common variables from output
        
        This provides a set of standard variables that are often useful:
        - output_length: Length of the output
        - line_count: Number of lines
        - first_line: First line of output
        - last_line: Last line of output
        - exit_code: Extracted exit code (if present)
        - error_detected: Whether error indicators are present
        """
        auto_vars = {}
        
        # Basic metrics
        auto_vars[f'{node_id}_output_length'] = len(output)
        lines = output.splitlines()
        auto_vars[f'{node_id}_line_count'] = len(lines)
        
        if lines:
            auto_vars[f'{node_id}_first_line'] = lines[0]
            auto_vars[f'{node_id}_last_line'] = lines[-1]
        
        # Look for exit codes
        exit_code_match = re.search(r'exit\s+code[:\s]+(\d+)', output, re.IGNORECASE)
        if exit_code_match:
            auto_vars[f'{node_id}_exit_code'] = int(exit_code_match.group(1))
        
        # Error detection
        error_indicators = ['error', 'failed', 'exception', 'denied', 'not found']
        auto_vars[f'{node_id}_error_detected'] = any(
            indicator in output.lower() for indicator in error_indicators
        )
        
        # Store in execution context
        for var_name, var_value in auto_vars.items():
            context.variables[var_name] = var_value
        
        return auto_vars
    
    def create_extraction_rules_from_config(self, config: Dict[str, Any]) -> List[ExtractionRule]:
        """
        Create extraction rules from a configuration dictionary
        
        Expected format:
        {
            "variables": [
                {
                    "name": "user_id",
                    "type": "regex",
                    "pattern": "User ID: (\\d+)",
                    "required": true
                },
                ...
            ]
        }
        """
        rules = []
        
        variables_config = config.get('variables', [])
        for var_config in variables_config:
            rule = ExtractionRule(
                variable_name=var_config['name'],
                extraction_type=var_config['type'],
                pattern=var_config['pattern'],
                description=var_config.get('description', ''),
                required=var_config.get('required', False)
            )
            rules.append(rule)
        
        return rules
    
    def get_supported_extraction_types(self) -> List[Dict[str, str]]:
        """Get list of supported extraction types with descriptions"""
        return [
            {
                'type': 'regex',
                'description': 'Extract using regular expression pattern',
                'example': r'User ID: (\d+)'
            },
            {
                'type': 'json_path',
                'description': 'Extract from JSON using path notation',
                'example': 'user.name or items[0].id'
            },
            {
                'type': 'line',
                'description': 'Extract specific line(s)',
                'example': '1 (first line), last, 2-5 (range)'
            },
            {
                'type': 'key_value',
                'description': 'Extract value for a key from key:value pairs',
                'example': 'username'
            },
            {
                'type': 'first_word',
                'description': 'Extract the first word',
                'example': ''
            },
            {
                'type': 'last_word',
                'description': 'Extract the last word',
                'example': ''
            },
            {
                'type': 'length',
                'description': 'Get output length',
                'example': ''
            },
            {
                'type': 'line_count',
                'description': 'Get number of lines',
                'example': ''
            }
        ]