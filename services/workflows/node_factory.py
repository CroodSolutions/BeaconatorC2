from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from PyQt6.QtCore import QPointF
import uuid

from .node_compatibility import ConnectionType, NodeCapability


@dataclass
class NodeTemplate:
    """Template for creating nodes with predefined configurations"""
    node_type: str
    display_name: str
    description: str
    category: str
    icon: Optional[str] = None
    default_parameters: Dict[str, Any] = field(default_factory=dict)
    input_requirements: List[str] = field(default_factory=list)    # What this node needs as input
    output_capabilities: List[str] = field(default_factory=list)   # What this node can provide
    conditional_outputs: List[str] = field(default_factory=list)   # Conditional branches this node supports
    error_outputs: List[str] = field(default_factory=list)         # Error handling outputs
    auto_configure_rules: Dict[str, Any] = field(default_factory=dict)  # Auto-configuration based on context
    schema_integration: Optional[Dict[str, str]] = None             # Schema file/module mapping
    validation_rules: Dict[str, Any] = field(default_factory=dict) # Parameter validation
    ui_layout: str = "simple"                                      # UI layout type
    
    def get_action_points(self) -> List[Dict[str, Any]]:
        """Get list of action points this node should have"""
        action_points = []
        
        # Special handling for conditional nodes - no "Next" button, specific positioning
        if self.conditional_outputs and self.node_type == "condition":
            # For condition nodes: True on right, False on bottom
            for i, condition in enumerate(self.conditional_outputs):
                if i == 0:  # First conditional output (True) goes on the right
                    action_points.append({
                        "type": "conditional_true",
                        "position": "right",
                        "connection_type": ConnectionType.CONDITIONAL_TRUE,
                        "label": condition
                    })
                else:  # Second conditional output (False) goes on bottom
                    action_points.append({
                        "type": "conditional_false", 
                        "position": "bottom",
                        "connection_type": ConnectionType.CONDITIONAL_FALSE,
                        "label": condition
                    })
        else:
            # Primary output point (most nodes have this)
            if self.output_capabilities:
                action_points.append({
                    "type": "output",
                    "position": "right",
                    "connection_type": ConnectionType.SEQUENTIAL,
                    "label": "Next"
                })
            
            # Conditional outputs for non-condition nodes
            for i, condition in enumerate(self.conditional_outputs):
                action_points.append({
                    "type": "conditional_output",
                    "position": f"bottom_{i}",
                    "connection_type": ConnectionType.CONDITIONAL_TRUE if i == 0 else ConnectionType.CONDITIONAL_FALSE,
                    "label": condition
                })
        
            
        return action_points


@dataclass
class ConnectionContext:
    """Context information for creating connections"""
    source_node_type: str
    source_node_id: str
    connection_type: ConnectionType
    source_output_data: Optional[Dict[str, Any]] = None
    workflow_variables: Dict[str, Any] = field(default_factory=dict)
    execution_path: List[str] = field(default_factory=list)


class NodeTemplateRegistry:
    """Registry of all available node templates with schema filtering support"""
    
    def __init__(self, schema_service=None, active_schema_files: List[str] = None):
        self.templates: Dict[str, NodeTemplate] = {}
        self.schema_service = schema_service
        self._schemas_loaded = False
        self._schema_action_templates: Dict[str, Set[str]] = {}  # Track templates by schema file
        
        self._load_builtin_templates()
        
    def _load_builtin_templates(self):
        """Load built-in node templates"""
        
        # Control flow nodes
        self.register_template(NodeTemplate(
            node_type="start",
            display_name="Start",
            description="Beginning of workflow execution",
            category="Control Flow",
            icon="start",
            output_capabilities=["workflow_start"],
            auto_configure_rules={"position": "workflow_start"}
        ))
        
        self.register_template(NodeTemplate(
            node_type="end", 
            display_name="End",
            description="End of workflow execution",
            category="Control Flow",
            icon="stop",
            input_requirements=["any"],
            auto_configure_rules={"position": "workflow_end"}
        ))
        
        self.register_template(NodeTemplate(
            node_type="condition",
            display_name="Condition",
            description="Branch workflow based on conditions",
            category="Control Flow",
            icon="branch",
            input_requirements=["data"],
            conditional_outputs=["True", "False"],
            default_parameters={
                "condition_type": "contains",
                "condition_value": "",
                "case_sensitive": False
            },
            validation_rules={
                "condition_value": {"required": True, "min_length": 1}
            }
        ))
        
        self.register_template(NodeTemplate(
            node_type="delay",
            display_name="Delay",
            description="Wait for specified time before continuing",
            category="Control Flow", 
            icon="clock",
            input_requirements=["any"],
            output_capabilities=["timing_complete"],
            default_parameters={
                "delay_seconds": 5,
                "delay_type": "fixed"
            },
            validation_rules={
                "delay_seconds": {"required": True, "min_value": 1, "max_value": 3600}
            }
        ))
        
        self.register_template(NodeTemplate(
            node_type="set_variable",
            display_name="Set Variable",
            description="Define and set workflow variables with template support",
            category="Actions",
            icon="variable",
            input_requirements=["any"],
            output_capabilities=["variable_set", "variable_output"],
            default_parameters={
                "variable_name": "",
                "variable_value": ""
            },
            validation_rules={
                "variable_name": {"required": True, "min_length": 1},
                "variable_value": {"required": True, "min_length": 1}
            }
        ))
        
        self.register_template(NodeTemplate(
            node_type="file_transfer",
            display_name="File Transfer",
            description="Queue file upload/download operations between server and beacon",
            category="Actions",
            icon="file_transfer",
            input_requirements=["any"],
            output_capabilities=["file_transfer_queued"],
            default_parameters={
                "transfer_direction": "to_beacon",
                "filename": ""
            },
            validation_rules={
                "transfer_direction": {"required": True, "allowed_values": ["to_beacon", "from_beacon"]},
                "filename": {"required": True, "min_length": 1}
            }
        ))
        

        
        
        
        
        # Error handling nodes
        self.register_template(NodeTemplate(
            node_type="error_handler",
            display_name="Error Handler",
            description="Handle errors and implement recovery logic", 
            category="Error Handling",
            icon="alert",
            input_requirements=["error_data"],
            output_capabilities=["error_handled", "recovery_data"],
            default_parameters={
                "recovery_action": "continue",
                "log_error": True,
                "notify_user": False
            }
        ))
        
        # Generic action node for schema modules
        self.register_template(NodeTemplate(
            node_type="action",
            display_name="Execute Module",
            description="Execute a module from the selected beacon schemas",
            category="Actions",
            icon="play",
            input_requirements=["workflow_start"],
            output_capabilities=["action_output", "command_result"],
            error_outputs=["action_failed"],
            default_parameters={
                "schema_file": "",
                "category": "",
                "module": ""
            },
            validation_rules={
                "schema_file": {"required": True, "min_length": 1},
                "category": {"required": True, "min_length": 1},
                "module": {"required": True, "min_length": 1}
            }
        ))
        
        
    def _load_schema_action_templates(self):
        """Load Action node templates from selected beacon schemas"""
        if not self.schema_service:
            return
            
        try:
            # Load from all available schema files since we're no longer filtering by active schemas
            schema_files_to_load = []
            
            for schema_file in schema_files_to_load:
                try:
                    schema = self.schema_service.load_schema(schema_file)
                    if not schema:
                        continue
                    
                    # Track templates for this schema
                    if schema_file not in self._schema_action_templates:
                        self._schema_action_templates[schema_file] = set()
                        
                    # Create Action node templates for each module in each category
                    for category_name, category in schema.categories.items():
                        for module_name, module in category.modules.items():
                            template = self._create_action_template_from_schema(
                                schema_file, category_name, module_name, category, module
                            )
                            if template:
                                self._schema_action_templates[schema_file].add(template.node_type)
                                
                except Exception as e:
                    print(f"Skipping schema file {schema_file}: {e}")
                    continue
                        
        except Exception as e:
            print(f"Error loading schema action templates: {e}")
            
    def _create_action_template_from_schema(self, schema_file: str, category_name: str, 
                                          module_name: str, category, module):
        """Create an Action node template from a schema module"""
        try:
            # Create node type identifier
            node_type = f"action_{category_name}_{module_name}"
            
            # Get module properties
            display_name = module.display_name
            description = module.description
            
            # Convert schema parameters to template parameters
            default_parameters = {}
            validation_rules = {}
            
            for param_name, param_config in module.parameters.items():
                try:
                    # Set default values
                    default_value = param_config.default if param_config.default is not None else ''
                    if param_config.type.value == 'integer':
                        default_value = int(default_value) if default_value else 0
                    elif param_config.type.value == 'boolean':
                        default_value = bool(default_value) if default_value else False
                    
                    default_parameters[param_name] = default_value
                    
                    # Create validation rules
                    validation = {}
                    if param_config.required:
                        validation['required'] = True
                        
                    if param_config.validation:
                        if param_config.validation.min_length is not None:
                            validation['min_length'] = param_config.validation.min_length
                        if param_config.validation.max_length is not None:
                            validation['max_length'] = param_config.validation.max_length
                        if param_config.validation.min_value is not None:
                            validation['min_value'] = param_config.validation.min_value
                        if param_config.validation.max_value is not None:
                            validation['max_value'] = param_config.validation.max_value
                            
                    if validation:
                        validation_rules[param_name] = validation
                        
                except (AttributeError, ValueError) as e:
                    # Skip parameters with invalid types or values
                    print(f"Skipping invalid parameter {param_name} in {category_name}.{module_name}: {e}")
                    continue
            
            # Create category display name
            category_display = category.display_name
            
            # Create the template
            template = NodeTemplate(
                node_type=node_type,
                display_name=display_name,
                description=description,
                category=f"Actions - {category_display}",
                icon="play",  # Default icon for action nodes
                input_requirements=["workflow_start"],
                output_capabilities=["action_output", "command_result"],
                error_outputs=["action_failed"],
                default_parameters=default_parameters,
                schema_integration={
                    "schema_file": schema_file,
                    "category": category_name,
                    "module_name": module_name
                },
                validation_rules=validation_rules,
                ui_layout="simple"
            )
            
            self.register_template(template)
            return template
            
        except Exception as e:
            print(f"Error creating action template for {category_name}.{module_name}: {e}")
            return None
        
    def register_template(self, template: NodeTemplate):
        """Register a new node template"""
        self.templates[template.node_type] = template
        
    def get_template(self, node_type: str) -> Optional[NodeTemplate]:
        """Get template for a node type"""

        return self.templates.get(node_type)
        
    def get_templates_by_category(self, category: str) -> List[NodeTemplate]:
        """Get all templates in a category"""

        return [template for template in self.templates.values() 
                if template.category == category]
        
    def get_all_categories(self) -> List[str]:
        """Get list of all template categories"""

        categories = set(template.category for template in self.templates.values())
        return sorted(list(categories))
        
    def get_compatible_templates(self, source_node_type: str, 
                                connection_type: ConnectionType) -> List[NodeTemplate]:
        """Get templates compatible with a source node and connection type"""
        return list(self.templates.values())
    
    
    def _reload_schema_templates(self):
        """Reload all schema-based templates"""
        # Remove existing schema-based templates
        self._clear_schema_templates()
        
        # Reset schema loading state
        self._schemas_loaded = False
        
        # No need to reload schema templates since we use generic action template
        self._schemas_loaded = True
    
    def _load_templates_for_schema(self, schema_file: str):
        """Load templates for a specific schema"""
        if not self.schema_service:
            return
            
        try:
            schema = self.schema_service.load_schema(schema_file)
            if not schema:
                return
            
            # Track templates for this schema
            if schema_file not in self._schema_action_templates:
                self._schema_action_templates[schema_file] = set()
                
            # Create templates for this schema
            for category_name, category in schema.categories.items():
                for module_name, module in category.modules.items():
                    template = self._create_action_template_from_schema(
                        schema_file, category_name, module_name, category, module
                    )
                    if template:
                        self._schema_action_templates[schema_file].add(template.node_type)
                        
        except Exception as e:
            print(f"Error loading templates for schema {schema_file}: {e}")
    
    def _unload_templates_for_schema(self, schema_file: str):
        """Unload templates for a specific schema"""
        if schema_file in self._schema_action_templates:
            # Remove all templates associated with this schema
            template_types = self._schema_action_templates[schema_file].copy()
            for template_type in template_types:
                if template_type in self.templates:
                    del self.templates[template_type]
            
            # Clear tracking for this schema
            del self._schema_action_templates[schema_file]
    
    def _clear_schema_templates(self):
        """Remove all schema-based templates"""
        for schema_file in list(self._schema_action_templates.keys()):
            self._unload_templates_for_schema(schema_file)
    
    def get_templates_by_schema(self, schema_file: str) -> List[NodeTemplate]:
        """Get all templates from a specific schema"""
        if schema_file not in self._schema_action_templates:
            return []
        
        template_types = self._schema_action_templates[schema_file]
        return [self.templates[template_type] for template_type in template_types 
                if template_type in self.templates]
    
    def get_schema_for_template(self, template: NodeTemplate) -> Optional[str]:
        """Get the schema file that provided a template"""
        if template.schema_integration:
            return template.schema_integration.get("schema_file")
        return None


class NodeFactory:
    """Creates nodes from templates with proper connections"""
    
    def __init__(self, template_registry: NodeTemplateRegistry = None, schema_service=None):
        self.template_registry = template_registry or NodeTemplateRegistry(schema_service)
        
    def create_node_from_template(self, template: NodeTemplate, 
                                position: QPointF, 
                                connection_context: Optional[ConnectionContext] = None) -> Dict[str, Any]:
        """Create and configure a node with automatic parameter setup"""
        
        # Generate unique node ID
        node_id = f"{template.node_type}_{uuid.uuid4().hex[:8]}"
        
        # Start with default parameters
        parameters = template.default_parameters.copy()
        
        # Apply auto-configuration based on context
        if connection_context:
            auto_config = self._apply_auto_configuration(template, connection_context)
            parameters.update(auto_config)
            
        # Create module info for schema integration
        module_info = {}
        if template.schema_integration:
            module_info = {
                "display_name": template.display_name,
                "schema_file": self._get_schema_file_for_template(template),
                "category": template.schema_integration.get("schema_category"),
                "module_name": template.schema_integration.get("schema_module")
            }
        
        # Create node data structure
        node_data = {
            "node_id": node_id,
            "node_type": template.node_type,
            "position": {"x": position.x(), "y": position.y()},
            "module_info": module_info,
            "parameters": parameters,
            "conditions": [],
            "template": template,  # Store template reference
            "created_at": datetime.now().isoformat(),
            "auto_configured": bool(connection_context)
        }
        
        return node_data
        
    def _apply_auto_configuration(self, template: NodeTemplate, 
                                 context: ConnectionContext) -> Dict[str, Any]:
        """Apply automatic configuration based on connection context"""
        auto_config = {}
        
        # Apply template-specific auto-configuration rules
        for rule_name, rule_config in template.auto_configure_rules.items():
            if rule_name == "inherit_from_source":
                # Inherit certain parameters from source node
                source_params = context.source_output_data or {}
                for param in rule_config:
                    if param in source_params:
                        auto_config[param] = source_params[param]
                        
            elif rule_name == "workflow_variables":
                # Use workflow variables to pre-populate parameters
                for param, var_name in rule_config.items():
                    if var_name in context.workflow_variables:
                        auto_config[param] = context.workflow_variables[var_name]
                        
            elif rule_name == "connection_type_defaults":
                # Apply different defaults based on connection type
                type_defaults = rule_config.get(context.connection_type.value, {})
                auto_config.update(type_defaults)
                
        return auto_config
        
    def _get_schema_file_for_template(self, template: NodeTemplate) -> Optional[str]:
        """Determine appropriate schema file for template"""
        # This would integrate with the schema service to find appropriate schemas
        # For now, return a default based on category
        category_schema_mapping = {
            "Basic Operations": "python_beacon.yaml",
            "File Operations": "python_beacon.yaml", 
            "Information Gathering": "python_beacon.yaml",
            "Persistence": "python_beacon.yaml",
            "Control Flow": None,  # Control flow nodes don't need schemas
            "Error Handling": None,
            "Communication": None
        }
        
        return category_schema_mapping.get(template.category)
        
    def create_node_with_auto_positioning(self, template: NodeTemplate,
                                        source_node_data: Dict[str, Any],
                                        connection_type: ConnectionType,
                                        existing_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create node with automatic positioning relative to source"""
        from .node_positioning import NodePositionManager
        
        position_manager = NodePositionManager()
        position = position_manager.calculate_next_position(
            source_node_data, connection_type, template, existing_nodes
        )
        
        connection_context = ConnectionContext(
            source_node_type=source_node_data["node_type"],
            source_node_id=source_node_data["node_id"],
            connection_type=connection_type,
            source_output_data=source_node_data.get("parameters", {})
        )
        
        return self.create_node_from_template(template, position, connection_context)
        
    def validate_node_parameters(self, template: NodeTemplate, 
                                parameters: Dict[str, Any]) -> List[str]:
        """Validate node parameters against template rules"""
        errors = []
        
        for param_name, validation_rules in template.validation_rules.items():
            if param_name not in parameters:
                if validation_rules.get("required", False):
                    errors.append(f"Required parameter '{param_name}' is missing")
                continue
                
            value = parameters[param_name]
            
            # Check type validation
            if "type" in validation_rules:
                expected_type = validation_rules["type"]
                if expected_type == "file" and not isinstance(value, str):
                    errors.append(f"Parameter '{param_name}' must be a file path")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"Parameter '{param_name}' must be an integer")
                    
            # Check value constraints
            if isinstance(value, str):
                if "min_length" in validation_rules and len(value) < validation_rules["min_length"]:
                    errors.append(f"Parameter '{param_name}' is too short")
                if "max_length" in validation_rules and len(value) > validation_rules["max_length"]:
                    errors.append(f"Parameter '{param_name}' is too long")
                    
            if isinstance(value, (int, float)):
                if "min_value" in validation_rules and value < validation_rules["min_value"]:
                    errors.append(f"Parameter '{param_name}' is below minimum value")
                if "max_value" in validation_rules and value > validation_rules["max_value"]:
                    errors.append(f"Parameter '{param_name}' is above maximum value")
                    
        return errors