from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from enum import Enum


class ConnectionType(Enum):
    """Types of connections between nodes"""
    SEQUENTIAL = "sequential"           # Normal flow from one node to next
    CONDITIONAL_TRUE = "conditional_true"   # True branch of condition
    CONDITIONAL_FALSE = "conditional_false" # False branch of condition
    PARALLEL = "parallel"               # Parallel execution branch


@dataclass
class ConnectionOption:
    """Represents a connection option in the menu"""
    node_type: str
    display_name: str
    description: str
    category: str
    icon: Optional[str] = None
    connection_type: ConnectionType = ConnectionType.SEQUENTIAL
    auto_configure: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeCapability:
    """Defines what a node can input/output"""
    data_types: Set[str] = field(default_factory=set)  # Types of data this handles
    requires_input: bool = False                       # Whether this node needs input
    provides_output: bool = False                      # Whether this node provides output
    supports_conditions: bool = False                  # Whether this node can branch
    supports_error_handling: bool = False             # Whether this node can handle errors


class NodeCompatibilityManager:
    """Manages what nodes can connect to what other nodes"""
    
    def __init__(self, schema_service=None, template_registry=None):
        self.schema_service = schema_service
        self.template_registry = template_registry
        self.compatibility_rules: Dict[str, Dict[str, List[str]]] = {}
        self.node_capabilities: Dict[str, NodeCapability] = {}
        self.connection_categories: Dict[str, List[str]] = {}
        
        self._load_default_rules()
        self._load_node_capabilities()
        
        # Try to load custom rules from config file
        config_file = Path("configs/workflow_compatibility.yaml")
        if config_file.exists():
            self.load_custom_rules(config_file)
        
    def _load_default_rules(self):
        """Load default compatibility rules"""
        self.compatibility_rules = {
            "start": {
                "output": [
                    "command_execution",
                    "file_operation", 
                    "condition",
                    "delay",
                    "reconnaissance",
                    "persistence",
                    "lateral_movement"
                ]
            },
            "command_execution": {
                "output": [
                    "command_execution",
                    "file_operation",
                    "condition", 
                    "data_extraction",
                    "persistence",
                    "end"
                ],
            },
            "file_operation": {
                "output": [
                    "command_execution",
                    "file_operation",
                    "data_extraction",
                    "condition",
                    "end"
                ],
            },
            "condition": {
                "true_output": [
                    "command_execution",
                    "file_operation",
                    "persistence", 
                    "lateral_movement",
                    "condition",
                    "end"
                ],
                "false_output": [
                    "alternative_command",
                    "notification",
                    "condition",
                    "end"
                ]
            },
            "delay": {
                "output": [
                    "command_execution",
                    "file_operation",
                    "condition",
                    "reconnaissance",
                    "end"
                ]
            },
            "reconnaissance": {
                "output": [
                    "command_execution",
                    "data_extraction",
                    "condition",
                    "persistence",
                    "lateral_movement",
                    "end"
                ],
            },
            "persistence": {
                "output": [
                    "command_execution",
                    "verification",
                    "condition",
                    "lateral_movement",
                    "end"
                ],
            },
            "lateral_movement": {
                "output": [
                    "command_execution",
                    "reconnaissance",
                    "persistence",
                    "condition",
                    "end"
                ],
            },
            "data_extraction": {
                "output": [
                    "file_operation",
                    "condition",
                    "notification",
                    "end"
                ],
            },
            "notification": {
                "output": [
                    "end"
                ]
            },
        }
        
    def _load_node_capabilities(self):
        """Load node capability definitions"""
        self.node_capabilities = {
            "start": NodeCapability(
                provides_output=True,
                data_types={"workflow_start"}
            ),
            "command_execution": NodeCapability(
                requires_input=True,
                provides_output=True,
                supports_error_handling=True,
                data_types={"command_output", "system_data"}
            ),
            "file_operation": NodeCapability(
                requires_input=True,
                provides_output=True,
                supports_error_handling=True,
                data_types={"file_data", "file_metadata"}
            ),
            "condition": NodeCapability(
                requires_input=True,
                provides_output=True,
                supports_conditions=True,
                data_types={"boolean_result", "condition_data"}
            ),
            "delay": NodeCapability(
                requires_input=True,
                provides_output=True,
                data_types={"timing_data"}
            ),
            "reconnaissance": NodeCapability(
                requires_input=True,
                provides_output=True,
                supports_error_handling=True,
                data_types={"recon_data", "system_info"}
            ),
            "persistence": NodeCapability(
                requires_input=True,
                provides_output=True,
                supports_error_handling=True,
                data_types={"persistence_data", "system_modifications"}
            ),
            "lateral_movement": NodeCapability(
                requires_input=True,
                provides_output=True,
                supports_error_handling=True,
                data_types={"movement_data", "network_access"}
            ),
            "data_extraction": NodeCapability(
                requires_input=True,
                provides_output=True,
                supports_error_handling=True,
                data_types={"extracted_data", "file_data"}
            ),
            "notification": NodeCapability(
                requires_input=True,
                provides_output=True,
                data_types={"notification_data"}
            ),
            "end": NodeCapability(
                requires_input=True,
                data_types={"workflow_end"}
            )
        }
        
    def get_compatible_nodes(self, source_node_type: str, connection_type: str) -> List[str]:
        """Get list of node types that can connect to this source node"""
        compatible_nodes = []
        
        # Get base compatibility rules
        if source_node_type in self.compatibility_rules:
            compatible_nodes.extend(self.compatibility_rules[source_node_type].get(connection_type, []))
        
        # For start nodes, always add generic action node (schema-less approach)
        if source_node_type == "start" and connection_type == "output":
            if "action" not in compatible_nodes:
                compatible_nodes.append("action")
                print(f"DEBUG: Added generic action node (schema-less approach)")
        
        # For any action node, allow connecting to other actions and control flow nodes
        if source_node_type == "action" and connection_type == "output":
            # Always allow connecting to another action node (schema-less approach)
            if "action" not in compatible_nodes:
                compatible_nodes.append("action")
            
            # Also allow control flow nodes
            control_flow_nodes = ["condition", "delay", "end", "notification"]
            for node_type in control_flow_nodes:
                if node_type not in compatible_nodes:
                    compatible_nodes.append(node_type)
        
        print(f"DEBUG: Compatible nodes for {source_node_type} -> {connection_type}: {compatible_nodes}")
        return compatible_nodes
        
    def get_connection_options(self, source_node_type: str, connection_type: str) -> List[ConnectionOption]:
        """Get menu options for a specific connection type"""
        compatible_nodes = self.get_compatible_nodes(source_node_type, connection_type)
        options = []
        
        for node_type in compatible_nodes:
            option = self._create_connection_option(node_type, connection_type)
            if option:
                options.append(option)
                
        # Sort by category and display name
        options.sort(key=lambda x: (x.category, x.display_name))
        return options
        
    def _create_connection_option(self, node_type: str, connection_type: str) -> Optional[ConnectionOption]:
        """Create a connection option for a node type"""
        # Map node types to display information
        node_info = self._get_node_display_info(node_type)
        if not node_info:
            return None
            
        # Determine connection type enum
        conn_type_mapping = {
            "output": ConnectionType.SEQUENTIAL,
            "true_output": ConnectionType.CONDITIONAL_TRUE,
            "false_output": ConnectionType.CONDITIONAL_FALSE,
            "parallel": ConnectionType.PARALLEL
        }
        
        conn_type_enum = conn_type_mapping.get(connection_type, ConnectionType.SEQUENTIAL)
        
        return ConnectionOption(
            node_type=node_type,
            display_name=node_info["display_name"],
            description=node_info["description"],
            category=node_info["category"],
            icon=node_info.get("icon"),
            connection_type=conn_type_enum,
            auto_configure=node_info.get("auto_configure", {})
        )
        
    def _get_node_display_info(self, node_type: str) -> Optional[Dict[str, Any]]:
        """Get display information for a node type"""
        node_display_info = {
            "start": {
                "display_name": "Start",
                "description": "Beginning of workflow",
                "category": "Control Flow",
                "icon": "start"
            },
            "command_execution": {
                "display_name": "Execute Command",
                "description": "Execute system commands on target",
                "category": "Basic Operations",
                "icon": "terminal"
            },
            "file_operation": {
                "display_name": "File Operation",
                "description": "Upload, download, or manipulate files",
                "category": "File Operations",
                "icon": "file"
            },
            "condition": {
                "display_name": "Condition Check",
                "description": "Branch workflow based on conditions",
                "category": "Control Flow", 
                "icon": "branch"
            },
            "delay": {
                "display_name": "Delay",
                "description": "Wait for specified time",
                "category": "Control Flow",
                "icon": "clock"
            },
            "reconnaissance": {
                "display_name": "Reconnaissance", 
                "description": "Gather system information",
                "category": "Information Gathering",
                "icon": "search"
            },
            "persistence": {
                "display_name": "Establish Persistence",
                "description": "Maintain access to target system",
                "category": "Persistence",
                "icon": "anchor"
            },
            "lateral_movement": {
                "display_name": "Lateral Movement",
                "description": "Move to other systems in network",
                "category": "Movement",
                "icon": "network"
            },
            "data_extraction": {
                "display_name": "Extract Data",
                "description": "Collect and extract target data",
                "category": "Data Operations",
                "icon": "download"
            },
            "notification": {
                "display_name": "Send Notification",
                "description": "Send alert or notification",
                "category": "Communication",
                "icon": "bell"
            },
            "end": {
                "display_name": "End",
                "description": "End of workflow",
                "category": "Control Flow",
                "icon": "stop"
            }
        }
        
        return node_display_info.get(node_type)
        
    def can_connect(self, source_node_type: str, target_node_type: str, connection_type: str) -> bool:
        """Validate if connection is allowed"""
        compatible_nodes = self.get_compatible_nodes(source_node_type, connection_type)
        return target_node_type in compatible_nodes
        
    def get_available_connection_types(self, node_type: str) -> List[str]:
        """Get list of connection types available for a node"""
        if node_type not in self.compatibility_rules:
            return []
        return list(self.compatibility_rules[node_type].keys())
        
    def load_custom_rules(self, rules_file: Path):
        """Load custom compatibility rules from YAML file"""
        try:
            with open(rules_file, 'r') as f:
                custom_rules = yaml.safe_load(f)
                
            if 'compatibility_rules' in custom_rules:
                # Merge with existing rules
                for node_type, connections in custom_rules['compatibility_rules'].items():
                    if node_type not in self.compatibility_rules:
                        self.compatibility_rules[node_type] = {}
                    self.compatibility_rules[node_type].update(connections)
                    
            if 'node_capabilities' in custom_rules:
                # Update node capabilities
                for node_type, capability_data in custom_rules['node_capabilities'].items():
                    capability = NodeCapability(
                        data_types=set(capability_data.get('data_types', [])),
                        requires_input=capability_data.get('requires_input', False),
                        provides_output=capability_data.get('provides_output', False),
                        supports_conditions=capability_data.get('supports_conditions', False),
                        supports_error_handling=capability_data.get('supports_error_handling', False)
                    )
                    self.node_capabilities[node_type] = capability
                    
        except Exception as e:
            print(f"Error loading custom rules: {e}")
            
    def get_node_capability(self, node_type: str) -> Optional[NodeCapability]:
        """Get capability information for a node type"""
        return self.node_capabilities.get(node_type)
        
    def validate_workflow_connectivity(self, nodes: List[Dict[str, Any]], 
                                     connections: List[Dict[str, Any]]) -> List[str]:
        """Validate that all connections in a workflow are valid"""
        errors = []
        
        for connection in connections:
            source_type = self._get_node_type_by_id(nodes, connection['source_node_id'])
            target_type = self._get_node_type_by_id(nodes, connection['target_node_id'])
            connection_type = connection.get('connection_type', 'output')
            
            if not self.can_connect(source_type, target_type, connection_type):
                errors.append(
                    f"Invalid connection: {source_type} cannot connect to {target_type} "
                    f"via {connection_type}"
                )
                
        return errors
        
    def _get_node_type_by_id(self, nodes: List[Dict[str, Any]], node_id: str) -> Optional[str]:
        """Helper to get node type by node ID"""
        for node in nodes:
            if node.get('node_id') == node_id:
                return node.get('node_type')
        return None