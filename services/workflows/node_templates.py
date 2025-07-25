"""
Node Templates for Common Workflow Operations

Provides pre-configured templates for commonly used workflow nodes,
including condition nodes that can be easily added to workflows.
"""

from typing import Dict, List, Any
from dataclasses import dataclass

from .node_compatibility import ConnectionType


@dataclass
class NodeTemplate:
    """Template for creating workflow nodes"""
    node_type: str
    display_name: str
    description: str
    category: str
    default_parameters: Dict[str, Any]
    connection_points: List[Dict[str, Any]]
    icon: str = ""
    color: str = "#4CAF50"
    
    
class NodeTemplateRegistry:
    """Registry for managing node templates"""
    
    def __init__(self):
        self.templates = {}
        self._register_builtin_templates()
        
    def _register_builtin_templates(self):
        """Register built-in node templates"""
        # Condition node templates
        self.register_template(NodeTemplate(
            node_type="condition_contains",
            display_name="Text Contains",
            description="Check if input text contains a specific value",
            category="conditions",
            default_parameters={
                "condition_type": "contains",
                "value": "",
                "case_sensitive": False
            },
            connection_points=[
                {
                    "type": "conditional_true",
                    "position": "bottom_0",
                    "connection_type": ConnectionType.CONDITIONAL_TRUE,
                    "label": "True"
                },
                {
                    "type": "conditional_false",
                    "position": "bottom_1", 
                    "connection_type": ConnectionType.CONDITIONAL_FALSE,
                    "label": "False"
                }
            ],
            color="#FF9800"
        ))
        
        self.register_template(NodeTemplate(
            node_type="condition_equals",
            display_name="Text Equals",
            description="Check if input text equals a specific value",
            category="conditions",
            default_parameters={
                "condition_type": "equals",
                "value": "",
                "case_sensitive": False
            },
            connection_points=[
                {
                    "type": "conditional_true",
                    "position": "bottom_0",
                    "connection_type": ConnectionType.CONDITIONAL_TRUE,
                    "label": "True"
                },
                {
                    "type": "conditional_false",
                    "position": "bottom_1",
                    "connection_type": ConnectionType.CONDITIONAL_FALSE,
                    "label": "False"
                }
            ],
            color="#FF9800"
        ))
        
        self.register_template(NodeTemplate(
            node_type="condition_regex",
            display_name="Regex Match",
            description="Check if input matches a regular expression",
            category="conditions", 
            default_parameters={
                "condition_type": "regex",
                "pattern": "",
                "case_sensitive": False
            },
            connection_points=[
                {
                    "type": "conditional_true",
                    "position": "bottom_0",
                    "connection_type": ConnectionType.CONDITIONAL_TRUE,
                    "label": "True"
                },
                {
                    "type": "conditional_false",
                    "position": "bottom_1",
                    "connection_type": ConnectionType.CONDITIONAL_FALSE,
                    "label": "False"
                }
            ],
            color="#FF9800"
        ))
        
        self.register_template(NodeTemplate(
            node_type="condition_numeric",
            display_name="Numeric Compare",
            description="Compare numeric values from input",
            category="conditions",
            default_parameters={
                "condition_type": "numeric",
                "value": 0,
                "operator": "=="
            },
            connection_points=[
                {
                    "type": "conditional_true",
                    "position": "bottom_0",
                    "connection_type": ConnectionType.CONDITIONAL_TRUE,
                    "label": "True"
                },
                {
                    "type": "conditional_false",
                    "position": "bottom_1",
                    "connection_type": ConnectionType.CONDITIONAL_FALSE,
                    "label": "False"
                }
            ],
            color="#FF9800"
        ))
        
        # Utility nodes
        self.register_template(NodeTemplate(
            node_type="delay",
            display_name="Delay", 
            description="Wait for a specified number of seconds",
            category="utilities",
            default_parameters={
                "delay_seconds": 1
            },
            connection_points=[
                {
                    "type": "output",
                    "position": "right",
                    "connection_type": ConnectionType.SEQUENTIAL,
                    "label": "Next"
                }
            ],
            color="#607D8B"
        ))
        
        self.register_template(NodeTemplate(
            node_type="variable_set",
            display_name="Set Variable",
            description="Set a workflow variable to a specific value",
            category="utilities",
            default_parameters={
                "variable_name": "",
                "variable_value": ""
            },
            connection_points=[
                {
                    "type": "output",
                    "position": "right",
                    "connection_type": ConnectionType.SEQUENTIAL,
                    "label": "Next"
                }
            ],
            color="#607D8B"
        ))
        
    def register_template(self, template: NodeTemplate):
        """Register a node template"""
        self.templates[template.node_type] = template
        
    def get_template(self, node_type: str) -> NodeTemplate:
        """Get a template by node type"""
        return self.templates.get(node_type)
        
    def get_templates_by_category(self, category: str) -> List[NodeTemplate]:
        """Get all templates in a category"""
        return [template for template in self.templates.values() 
                if template.category == category]
                
    def get_all_templates(self) -> List[NodeTemplate]:
        """Get all registered templates"""
        return list(self.templates.values())
        
    def get_categories(self) -> List[str]:
        """Get all template categories"""
        categories = set(template.category for template in self.templates.values())
        return sorted(list(categories))