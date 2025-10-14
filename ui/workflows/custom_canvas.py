#!/usr/bin/env python3
"""
Custom workflow canvas using QPainter instead of QGraphicsView.
This implementation aims to provide much better panning and zooming performance.
"""

import math
from typing import List, Optional, Tuple, Dict, Any
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QWheelEvent, QMouseEvent, QPaintEvent

from services.workflows.node_compatibility import NodeCompatibilityManager, ConnectionType
from services.workflows.node_factory import NodeTemplateRegistry, NodeFactory, ConnectionContext
from services.workflows.workflow_service import WorkflowService, WorkflowNode as ServiceWorkflowNode, WorkflowConnection as ServiceWorkflowConnection
from services.workflows.workflow_engine import WorkflowEngine

class ActionPoint:
    """Interactive action point for creating connections"""
    
    def __init__(self, parent_node, point_type: str, position: str, connection_type, label: str = ""):
        self.parent_node = parent_node
        self.point_type = point_type      # "output", "conditional_true", "conditional_false"
        self.position = position          # "right", "bottom_0", "bottom_1"
        self.connection_type = connection_type
        self.label = label
        self.is_hovered = False
        self.is_visible = False
        self.radius = 12  # Set radius before position calculation
        
        # Calculate position on parent node
        self.x, self.y = self._calculate_position()
        
    def _calculate_position(self) -> Tuple[float, float]:
        """Calculate action point position relative to parent node"""
        # Use cached dynamic height if available, otherwise use base height
        dynamic_height = getattr(self.parent_node, '_cached_dynamic_height', self.parent_node.height)
            
        # Offset action points slightly outside the node border to avoid blocking content
        action_point_offset = self.radius + 5  # Radius plus small gap
        
        if self.position == "right":
            return (self.parent_node.x + self.parent_node.width + action_point_offset, 
                   self.parent_node.y + dynamic_height / 2)
        elif self.position == "bottom_0":
            return (self.parent_node.x + self.parent_node.width * 0.3, 
                   self.parent_node.y + dynamic_height + action_point_offset)
        elif self.position == "bottom_1":
            return (self.parent_node.x + self.parent_node.width * 0.7, 
                   self.parent_node.y + dynamic_height + action_point_offset)
        elif self.position == "bottom":
            return (self.parent_node.x + self.parent_node.width / 2, 
                   self.parent_node.y + dynamic_height + action_point_offset)
        else:
            return (self.parent_node.x + self.parent_node.width / 2, 
                   self.parent_node.y + dynamic_height + action_point_offset)
                   
    def update_position(self):
        """Update position when parent node moves"""
        self.x, self.y = self._calculate_position()
        
    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is within action point bounds"""
        distance = math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
        return distance <= self.radius
        
    def get_color(self) -> QColor:
        """Get color based on connection type and hover state"""
        if self.connection_type == ConnectionType.SEQUENTIAL:
            base_color = QColor(100, 150, 255)  # Blue
        elif self.connection_type == ConnectionType.CONDITIONAL_TRUE:
            base_color = QColor(100, 255, 100)  # Green
        elif self.connection_type == ConnectionType.CONDITIONAL_FALSE:
            base_color = QColor(255, 100, 100)  # Red
        else:
            base_color = QColor(150, 150, 150)  # Gray
            
        return base_color.lighter(150) if self.is_hovered else base_color


class WorkflowNode:
    """Enhanced workflow node with schema support and comprehensive functionality"""
    
    def __init__(self, x: float, y: float, width: float = 160, height: float = 100, 
                 title: str = "Node", node_type: str = "action", template=None, module_info: Dict[str, Any] = None):
        # Position and size
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        
        # Node identity and type
        self.title = title
        self.node_type = node_type
        self.template = template
        # Ensure module_info is always a dictionary
        if isinstance(module_info, dict):
            self.module_info = module_info
        else:
            self.module_info = {}
        self.node_id = f"{node_type}_{id(self)}"  # Unique identifier
        
        # Selection and interaction state
        self.selected = False
        self.is_being_dragged = False
        self.ghost_mode = False
        
        # Visual properties - will be set based on node type
        self.border_color = QColor(100, 100, 100)
        self.fill_color = QColor(60, 60, 60)
        self.selected_color = QColor(120, 180, 255)
        self.text_color = QColor(255, 255, 255)
        self.ghost_color = QColor(80, 80, 80, 128)  # Semi-transparent for ghost mode
        
        # Set node type-specific colors
        self._set_node_colors()
        
        # Workflow-specific properties
        self.parameters = {}
        self.execution_status = "idle"  # idle, running, completed, failed
        self.execution_output = ""
        self.connections_in = []   # Incoming connections
        self.connections_out = []  # Outgoing connections
        
        # Action points for connections
        self.action_points: List[ActionPoint] = []
        self._setup_action_points(template)
        
        # Service workflow node for data model compatibility
        self.service_node = None  # Will be set when integrating with workflow service
        
        # Detail level for LOD rendering
        self.detail_level = "full"  # ultra_minimal, minimal, reduced, full
        
        # Performance tracking
        self._last_paint_time = 0.0
        
        # Canvas reference for dynamic sizing
        self.canvas = None
        
    def get_rect(self) -> QRectF:
        """Get the bounding rectangle of this node"""
        # Use cached dynamic height if available, otherwise use base height
        dynamic_height = getattr(self, '_cached_dynamic_height', self.height)
        return QRectF(self.x, self.y, self.width, dynamic_height)
        
    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is inside this node"""
        # Use cached dynamic height if available, otherwise use base height
        dynamic_height = getattr(self, '_cached_dynamic_height', self.height)
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + dynamic_height)
                
    def move_to(self, x: float, y: float):
        """Move the node to a new position"""
        self.x = x
        self.y = y
        self.update_action_points()
        
    def get_display_name(self) -> str:
        """Get the display name for this node"""
        # Ensure module_info is a dictionary
        if self.module_info and isinstance(self.module_info, dict) and 'display_name' in self.module_info:
            return self.module_info['display_name']
        return self.title
        
    def enable_ghost_mode(self):
        """Enable ghost mode for performance during dragging"""
        self.ghost_mode = True
        
    def disable_ghost_mode(self):
        """Disable ghost mode to restore full visuals"""
        self.ghost_mode = False
        
    def set_execution_status(self, status: str, output: str = ""):
        """Update execution status and output"""
        self.execution_status = status
        self.execution_output = output
        
    def add_connection_in(self, connection):
        """Add an incoming connection"""
        if connection not in self.connections_in:
            self.connections_in.append(connection)
            
    def add_connection_out(self, connection):
        """Add an outgoing connection"""
        if connection not in self.connections_out:
            self.connections_out.append(connection)
            
    def remove_connection(self, connection):
        """Remove a connection from this node"""
        if connection in self.connections_in:
            self.connections_in.remove(connection)
        if connection in self.connections_out:
            self.connections_out.remove(connection)
            
    def get_connection_point(self, point_type: str) -> QPointF:
        """Get connection point coordinates for a given type"""
        # Use cached dynamic height if available, otherwise use base height
        dynamic_height = getattr(self, '_cached_dynamic_height', self.height)
            
        if point_type == "output":
            return QPointF(self.x + self.width, self.y + dynamic_height / 2)
        elif point_type == "input":
            return QPointF(self.x, self.y + dynamic_height / 2)
        elif point_type == "error":
            return QPointF(self.x + self.width / 2, self.y + dynamic_height)
        elif point_type == "conditional_true":
            # True connections come from the right side
            return QPointF(self.x + self.width, self.y + dynamic_height / 2)
        elif point_type == "conditional_false" or point_type == "false_output":
            # False connections come from the bottom center
            return QPointF(self.x + self.width / 2, self.y + dynamic_height)
        elif point_type == "top":
            # Top connection point for False connections going into nodes
            return QPointF(self.x + self.width / 2, self.y)
        else:
            return QPointF(self.x + self.width / 2, self.y + dynamic_height / 2)
            
    def set_detail_level(self, level: str):
        """Set the level of detail for rendering"""
        self.detail_level = level
    
    def _set_node_colors(self):
        """Set colors based on node type for better visual differentiation"""
        if self.node_type in ["trigger", "start"]:
            # Purple/violet theme for trigger nodes (automatic capable)
            # Check if this is an automatic trigger
            if hasattr(self, 'parameters') and self.parameters:
                trigger_type = self.parameters.get('trigger_type', 'manual')
                enabled = self.parameters.get('enabled', True)
                
                if trigger_type == 'manual':
                    # Green theme for manual triggers
                    self.fill_color = QColor(40, 80, 40)  # Dark green
                    self.border_color = QColor(60, 120, 60)  # Medium green
                    self.selected_color = QColor(80, 160, 80)  # Light green
                elif enabled:
                    # Purple theme for active automatic triggers
                    self.fill_color = QColor(60, 40, 80)  # Dark purple
                    self.border_color = QColor(90, 60, 120)  # Medium purple
                    self.selected_color = QColor(120, 80, 160)  # Light purple
                else:
                    # Gray theme for disabled automatic triggers
                    self.fill_color = QColor(50, 50, 50)  # Dark gray
                    self.border_color = QColor(80, 80, 80)  # Medium gray
                    self.selected_color = QColor(110, 110, 110)  # Light gray
            else:
                # Default green theme for backward compatibility
                self.fill_color = QColor(40, 80, 40)  # Dark green
                self.border_color = QColor(60, 120, 60)  # Medium green
                self.selected_color = QColor(80, 160, 80)  # Light green
        elif self.node_type == "action":
            # Blue theme for action nodes 
            self.fill_color = QColor(40, 60, 80)  # Dark blue
            self.border_color = QColor(60, 90, 120)  # Medium blue
            self.selected_color = QColor(80, 120, 160)  # Light blue
        elif self.node_type == "condition":
            # Yellow theme for condition nodes
            self.fill_color = QColor(100, 100, 40)  # Dark yellow
            self.border_color = QColor(140, 140, 60)  # Medium yellow
            self.selected_color = QColor(180, 180, 80)  # Light yellow
        elif self.node_type == "end":
            # Red theme for end nodes
            self.fill_color = QColor(80, 40, 40)  # Dark red
            self.border_color = QColor(120, 60, 60)  # Medium red
            self.selected_color = QColor(160, 80, 80)  # Light red
        elif self.node_type == "delay":
            # Purple theme for delay nodes
            self.fill_color = QColor(60, 40, 80)  # Dark purple
            self.border_color = QColor(90, 60, 120)  # Medium purple
            self.selected_color = QColor(120, 80, 160)  # Light purple
        elif self.node_type == "set_variable":
            # Orange theme for set_variable nodes
            self.fill_color = QColor(80, 60, 40)  # Dark orange
            self.border_color = QColor(120, 90, 60)  # Medium orange
            self.selected_color = QColor(160, 120, 80)  # Light orange
        elif self.node_type == "file_transfer":
            # Cyan/Teal theme for file_transfer nodes
            self.fill_color = QColor(40, 80, 80)  # Dark cyan
            self.border_color = QColor(60, 120, 120)  # Medium cyan
            self.selected_color = QColor(80, 160, 160)  # Light cyan
        else:
            # Default gray theme for unknown node types
            self.fill_color = QColor(60, 60, 60)  # Dark gray
            self.border_color = QColor(100, 100, 100)  # Medium gray
            self.selected_color = QColor(120, 120, 120)  # Light gray
        
    def _setup_action_points(self, template=None):
        """Set up action points based on node type and template"""
        self.action_points.clear()
        
        # Ensure template is a proper NodeTemplate object, not ConnectionContext
        if template and hasattr(template, 'get_action_points') and callable(template.get_action_points):
            try:
                # Use template-defined action points
                action_points_config = template.get_action_points()
                for action_point_config in action_points_config:
                    action_point = ActionPoint(
                        self, 
                        action_point_config["type"], 
                        action_point_config["position"], 
                        action_point_config["connection_type"], 
                        action_point_config["label"]
                    )
                    self.action_points.append(action_point)
            except (TypeError, AttributeError, KeyError) as e:
                pass
                # Fall back to default action points
                self._setup_default_action_points()
        else:
            # Use default action points based on node type
            self._setup_default_action_points()
    
    def _setup_default_action_points(self):
        """Set up default action points based on node type"""
        self.action_points.clear()
        
        if self.node_type == "start":
            self.action_points.append(ActionPoint(
                self, "output", "right", ConnectionType.SEQUENTIAL, "Start"
            ))
        elif self.node_type == "end":
            # End nodes don't have output action points
            pass
        elif self.node_type == "condition":
            self.action_points.extend([
                ActionPoint(self, "conditional_true", "right", ConnectionType.CONDITIONAL_TRUE, "True"),
                ActionPoint(self, "conditional_false", "bottom", ConnectionType.CONDITIONAL_FALSE, "False")
            ])
        else:
            # Default action/schema nodes
            self.action_points.append(ActionPoint(
                self, "output", "right", ConnectionType.SEQUENTIAL, "Next"
            ))
            
    def update_action_points(self):
        """Update action point positions when node moves"""
        for action_point in self.action_points:
            action_point.update_position()
            
    def get_action_point_at(self, x: float, y: float) -> Optional[ActionPoint]:
        """Get action point at given coordinates"""
        for action_point in self.action_points:
            if action_point.is_visible and action_point.contains_point(x, y):
                return action_point
        return None
        
    def show_action_points(self):
        """Show action points when node is selected"""
        for action_point in self.action_points:
            action_point.is_visible = True
            
    def hide_action_points(self):
        """Hide action points when node is deselected"""
        for action_point in self.action_points:
            action_point.is_visible = False
            
    def has_connections_from_action_point(self, point_type: str) -> bool:
        """Check if action point already has connections"""
        for connection in self.connections_out:
            if hasattr(connection, 'start_point_type') and connection.start_point_type == point_type:
                return True
        return False
        
    def to_service_node(self) -> 'ServiceWorkflowNode':
        """Convert to service workflow node for backend operations"""
        if not self.service_node:
            self.service_node = ServiceWorkflowNode(
                node_id=self.node_id,
                node_type=self.node_type,
                position={"x": self.x, "y": self.y},
                module_info=self.module_info,
                parameters=self.parameters,
                conditions=[]  # Add empty conditions list
            )
        else:
            # Update position and parameters
            self.service_node.position = {"x": self.x, "y": self.y}
            self.service_node.parameters = self.parameters
            
        return self.service_node
        
    def update_parameter_display(self):
        """Update parameter display when parameters change"""
        # Force refresh of parameter cache if we had one
        # The actual display update happens in the canvas rendering during next paint
        # Clear any cached parameter data to ensure fresh display
        if hasattr(self, '_cached_parameters'):
            delattr(self, '_cached_parameters')
        
        # If this node belongs to a canvas, trigger a repaint
        # The canvas will be updated through the parent's update() call
        
    def get_parameter_summary(self) -> str:
        """Get a brief summary of key module parameters for tooltips"""
        if not hasattr(self, 'parameters') or not self.parameters:
            return "No module parameters configured"
            
        # For action nodes, exclude node configuration from summary
        if self.node_type == "action":
            internal_keys = {"schema_file", "module", "category", "display_name"}
            module_params = {k: v for k, v in self.parameters.items() if k not in internal_keys}
            params_to_show = module_params
        else:
            params_to_show = self.parameters
            
        summary_parts = []
        for key, value in list(params_to_show.items())[:3]:  # Show first 3 module parameters
            if value and str(value).strip():
                summary_parts.append(f"{key}: {str(value)[:20]}")
                
        if len(params_to_show) > 3:
            summary_parts.append(f"... and {len(params_to_show) - 3} more")
            
        return "\n".join(summary_parts) if summary_parts else "No module parameters configured"


class WorkflowConnection:
    """Enhanced workflow connection with type support and comprehensive functionality"""
    
    def __init__(self, start_node: WorkflowNode, end_node: WorkflowNode, 
                 connection_type: ConnectionType = ConnectionType.SEQUENTIAL, start_point_type: str = "output", 
                 end_point_type: str = "input"):
        self.start_node = start_node
        self.end_node = end_node
        self.connection_type = connection_type
        self.start_point_type = start_point_type
        self.end_point_type = end_point_type
        
        # Visual properties
        self.color = self._get_color_for_type(connection_type)
        self.width = 2
        self.selected = False
        
        # Add this connection to the nodes
        start_node.add_connection_out(self)
        end_node.add_connection_in(self)
        
        # Unique identifier
        self.connection_id = f"conn_{id(self)}"
        
        # Service connection for data model compatibility
        self.service_connection = None
        
    def _get_color_for_type(self, connection_type: ConnectionType) -> QColor:
        """Get color based on connection type"""
        if connection_type == ConnectionType.SEQUENTIAL:
            return QColor(100, 150, 255)  # Blue
        elif connection_type == ConnectionType.CONDITIONAL_TRUE:
            return QColor(100, 255, 100)  # Green
        elif connection_type == ConnectionType.CONDITIONAL_FALSE:
            return QColor(255, 100, 100)  # Red
        else:
            return QColor(150, 150, 150)  # Gray
        
    def get_start_point(self) -> QPointF:
        """Get the connection start point based on point type"""
        return self.start_node.get_connection_point(self.start_point_type)
        
    def get_end_point(self) -> QPointF:
        """Get the connection end point based on point type"""
        return self.end_node.get_connection_point(self.end_point_type)
        
    def get_bounding_rect(self) -> QRectF:
        """Get bounding rectangle for this connection"""
        start = self.get_start_point()
        end = self.get_end_point()
        return QRectF(start, end).normalized().adjusted(-10, -10, 10, 10)
        
    def cleanup(self):
        """Clean up connection references"""
        self.start_node.remove_connection(self)
        self.end_node.remove_connection(self)
        
        
    def to_service_connection(self) -> 'ServiceWorkflowConnection':
        """Convert to service workflow connection for backend operations"""
        if not self.service_connection:
            # Get connection type value
            connection_type_value = self.connection_type.value if hasattr(self.connection_type, 'value') else str(self.connection_type)
            print(f"DEBUG: Saving connection {self.start_node.node_id} -> {self.end_node.node_id} with type: {connection_type_value}")
            
            self.service_connection = ServiceWorkflowConnection(
                connection_id=self.connection_id,
                source_node_id=self.start_node.node_id,
                target_node_id=self.end_node.node_id,
                condition=None,  # Add condition parameter
                connection_type=connection_type_value
            )
        return self.service_connection


class CustomWorkflowCanvas(QWidget):
    """High-performance custom workflow canvas using QPainter with full workflow support"""
    
    # PyQt6 Signals - matching original WorkflowCanvas
    node_selected = pyqtSignal(object)  # Signal when a node is selected
    node_deselected = pyqtSignal()  # Signal when nodes are deselected
    node_moved = pyqtSignal(object, QPointF)  # Signal when a node is moved
    connection_created = pyqtSignal(object, object)  # Signal when nodes are connected
    node_deletion_requested = pyqtSignal(object)  # Signal when node deletion is requested
    node_parameters_updated = pyqtSignal(object, dict)  # Signal when node parameters are updated
    variable_updated = pyqtSignal(str, object)  # Signal when a workflow variable is updated
    variable_removed = pyqtSignal(str)  # Signal when a workflow variable is removed
    variables_cleared = pyqtSignal()  # Signal when all variables are cleared
    
    def __init__(self, parent=None, schema_service=None):
        super().__init__(parent)
        self.schema_service = schema_service
        
        # Initialize workflow components if available
        if schema_service:
            self.template_registry = NodeTemplateRegistry(schema_service)
            self.compatibility_manager = NodeCompatibilityManager(schema_service, self.template_registry)
            self.node_factory = NodeFactory(self.template_registry, schema_service)
            
            # Initialize workflow service integration
            self.workflow_service = None  # Will be set by parent editor
            self.workflow_engine = None   # Will be set by parent editor
            
            pass
        else:
            self.template_registry = None
            self.compatibility_manager = None
            self.node_factory = None
            self.workflow_service = None
            self.workflow_engine = None
            pass
        
        # Canvas state
        self.nodes: List[WorkflowNode] = []
        self.connections: List[WorkflowConnection] = []
        self.selected_node: Optional[WorkflowNode] = None
        self.workflow_variables: Dict[str, Any] = {}  # Workflow-global variables
        
        # Viewport state
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        
        # Interaction state
        self.is_panning = False
        self.is_dragging_node = False
        self.is_selecting = False  # Selection rectangle mode
        self.last_mouse_pos = QPoint()
        self.drag_start_pos = QPoint()
        self.drag_offset = QPointF()  # Offset between click point and primary node position
        self.drag_node_offsets = {}  # Dictionary to store offsets for all selected nodes
        self.hovered_action_point = None
        
        # Selection rectangle
        self.selection_start = QPointF()
        self.selection_end = QPointF()
        self.selected_nodes: List[WorkflowNode] = []  # Support multiple selection
        
        # Current workflow state
        self.current_workflow = None
        self.execution_id = None
        
        # Visual settings
        self.background_color = QColor(45, 45, 45)
        self.grid_color = QColor(60, 60, 60)
        self.grid_size = 25  # Unified grid size (changed from 20 to match positioning system)
        
        # Dot matrix settings
        self.dot_size = 2  # Radius of grid dots in pixels
        self.dot_color = QColor(70, 70, 70)  # Slightly lighter than grid_color for subtlety
        self.dot_opacity = 0.7  # Opacity for subtle but visible guidance
        
        # Performance settings
        self.enable_grid = True
        self.enable_antialiasing = True
        
        
        # Paint state flag to prevent recursion
        self._is_painting = False
        
        # Set widget properties
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        
    def set_workflow_services(self, workflow_service, workflow_engine):
        """Set workflow service references (called by WorkflowEditor)"""
        self.workflow_service = workflow_service
        self.workflow_engine = workflow_engine
        
    def add_node(self, node_type: str, position: QPointF, module_info: dict = None) -> WorkflowNode:
        """Add a new node to the canvas (WorkflowEditor interface)"""
        # Convert QPointF position to world coordinates and snap to grid
        world_pos = self.screen_to_world(position)
        snapped_pos = self.snap_to_grid(world_pos)
        
        # Get template for node type
        template = self.template_registry.get_template(node_type)
        if not template:
            # Create a basic node if no template found
            node = WorkflowNode(snapped_pos.x(), snapped_pos.y(), title=node_type.title(), node_type=node_type)
        else:
            # Create node from template
            node_data = self.node_factory.create_node_from_template(template, snapped_pos)
            node = WorkflowNode(
                snapped_pos.x(), snapped_pos.y(), 
                title=template.display_name, 
                node_type=node_type
            )
            node.node_id = node_data["node_id"]
            node.parameters = node_data["parameters"]
            
            # Add sample parameters for demo purposes if none exist
            if not node.parameters and node.node_type == "action":
                node.parameters = {
                    "schema_file": "python_beacon.yaml",  # Node config (won't show in badges)
                    "module": "system_info",              # Node config (won't show in badges)
                    "category": "recon",                  # Node config (won't show in badges)
                    "target": "192.168.1.100",           # Module parameter (will show)
                    "timeout": "30",                      # Module parameter (will show)
                    "verbose": True                       # Module parameter (will show)
                }
            elif not node.parameters and node.node_type == "condition":
                node.parameters = {
                    "condition_type": "contains",
                    "condition_value": "success",
                    "case_sensitive": False
                }
            elif not node.parameters and node.node_type == "delay":
                node.parameters = {
                    "delay_seconds": 5,
                    "delay_type": "fixed"
                }
                
            # Ensure module_info from node_data is a dictionary
            if isinstance(node_data["module_info"], dict):
                node.module_info = node_data["module_info"]
            else:
                node.module_info = {}
            
        # Set module_info if provided and it's a dictionary
        if module_info and isinstance(module_info, dict):
            node.module_info = module_info
            
        # Setup action points for the node
        if template:
            node._setup_action_points(template)
        else:
            node._setup_default_action_points()
            
        # Set canvas reference for dynamic sizing
        node.canvas = self
        
        self.nodes.append(node)
        self.update()
        return node
        
    def centerOn(self, node):
        """Center the view on a node (compatibility method)"""
        if node:
            # Calculate the center position for the node
            node_world_pos = QPointF(node.x, node.y)
            
            # Calculate canvas center
            canvas_center = QPointF(self.width() / 2, self.height() / 2)
            
            # Calculate the required pan offset to center the node
            # We want: world_to_screen(node_world_pos) = canvas_center
            # So: (node_world_pos + pan_offset) * zoom_factor = canvas_center
            # Therefore: pan_offset = canvas_center / zoom_factor - node_world_pos
            
            target_pan_offset = QPointF(
                canvas_center.x() / self.zoom_factor - node_world_pos.x(),
                canvas_center.y() / self.zoom_factor - node_world_pos.y()
            )
            
            # Update pan offset to center on node
            self.pan_offset = target_pan_offset
            
            self.update()
        
    def add_connection(self, start_node: WorkflowNode, end_node: WorkflowNode, 
                      connection_type: str = "default") -> WorkflowConnection:
        """Add a connection between two nodes"""
        connection = WorkflowConnection(start_node, end_node, connection_type)
        self.connections.append(connection)
        self.connection_created.emit(start_node, end_node)
        self.update()
        return connection
        
    def create_connection(self, start_node: WorkflowNode, end_node: WorkflowNode, 
                         connection_id: str = None, connection_type: str = "sequential") -> WorkflowConnection:
        """Create a connection between two nodes with optional connection_id (for loading workflows)"""
        # Convert string connection type to ConnectionType enum
        if isinstance(connection_type, str):
            type_mapping = {
                "sequential": ConnectionType.SEQUENTIAL,
                "conditional_true": ConnectionType.CONDITIONAL_TRUE,
                "conditional_false": ConnectionType.CONDITIONAL_FALSE,
                "parallel": ConnectionType.PARALLEL,
                "default": ConnectionType.SEQUENTIAL  # Legacy fallback
            }
            connection_type_enum = type_mapping.get(connection_type.lower(), ConnectionType.SEQUENTIAL)
        else:
            connection_type_enum = connection_type
        
        # Determine appropriate start and end point types based on connection type
        if connection_type_enum == ConnectionType.CONDITIONAL_TRUE:
            start_point_type = "conditional_true"
            end_point_type = "input"
        elif connection_type_enum == ConnectionType.CONDITIONAL_FALSE:
            start_point_type = "conditional_false"
            end_point_type = "top"  # Conditional false connections connect to top of target node
        else:
            start_point_type = "output"
            end_point_type = "input"
            
        connection = WorkflowConnection(start_node, end_node, connection_type_enum, 
                                      start_point_type, end_point_type)
        
        # Set custom connection ID if provided (used when loading saved workflows)
        if connection_id:
            connection.connection_id = connection_id
            
        self.connections.append(connection)
        self.connection_created.emit(start_node, end_node)
        self.update()
        return connection
        
    def add_node_from_template(self, template, position: QPointF = None, 
                              module_info: Dict[str, Any] = None, 
                              connection_context=None) -> Optional[WorkflowNode]:
        """Add a node using a workflow template"""
        if not self.node_factory or not template:
            return None
            
        # Validate that template is actually a NodeTemplate, not ConnectionContext
        if not hasattr(template, 'node_type') or not hasattr(template, 'display_name'):
            pass
            return None
            
        try:
            # Calculate position based on connection context or use default
            if position is None:
                if connection_context and hasattr(connection_context, 'source_node_id'):
                    # Find source node for positioning
                    source_node = None
                    for node in self.nodes:
                        if node.node_id == connection_context.source_node_id:
                            source_node = node
                            break
                    
                    if source_node:
                        position = self._calculate_new_node_position(
                            source_node, 
                            connection_context.connection_type,
                            template
                        )
                    else:
                        position = QPointF(300, 150)  # Default fallback
                else:
                    # No connection context - place at default location
                    position = QPointF(0, 0) if not self.nodes else QPointF(300, 150)
                
            # Position is already in world coordinates from our positioning system
            # Snap to grid for consistent alignment
            world_pos = self.snap_to_grid(position)
            
            # Get node type from template
            node_type = getattr(template, 'node_type', 'action')
            title = getattr(template, 'display_name', 'Template Node')
            
            node = WorkflowNode(
                world_pos.x(), world_pos.y(),
                title=title,
                node_type=node_type,
                template=template,
                module_info=module_info or {}
            )
            
            # Make conditional nodes square for proper diamond rendering
            if node_type == "condition":
                # Use the larger dimension to ensure diamond fits properly
                original_width, original_height = node.width, node.height
                size = max(node.width, node.height, 120)  # Minimum 120px for text
                node.width = size
                node.height = size
            
            # Setup action points for the node
            if template:
                node._setup_action_points(template)
            else:
                node._setup_default_action_points()
                
            # Set canvas reference for dynamic sizing
            node.canvas = self
            
            self.nodes.append(node)
            self.update()
            return node
            
        except Exception as e:
            pass
            return None
            
    def select_node(self, node: WorkflowNode):
        """Select a specific node"""
        # Clear previous selection
        if self.selected_node:
            self.selected_node.selected = False
            self.selected_node.hide_action_points()
            
        # Select new node
        self.selected_node = node
        if node:
            node.selected = True
            node.show_action_points()
            # Only emit node_selected signal for editable nodes (not End nodes)
            # Trigger/Start nodes are now editable, End nodes are not
            if node.node_type != 'end':
                self.node_selected.emit(node)
        else:
            self.node_deselected.emit()
            
        self.update()
        
    def clear_selection(self):
        """Clear all node selections"""
        if self.selected_node:
            self.selected_node.selected = False
            self.selected_node.hide_action_points()
        self.selected_node = None
        
        # Clear multi-node selection as well
        self.selected_nodes = []
        
        self.node_deselected.emit()
        self.update()
        
    def remove_node(self, node: WorkflowNode):
        """Remove a node and its connections"""
        if node not in self.nodes:
            return
            
        # Remove all connections involving this node
        connections_to_remove = []
        for connection in self.connections:
            if connection.start_node == node or connection.end_node == node:
                connections_to_remove.append(connection)
                
        for connection in connections_to_remove:
            self.remove_connection(connection)
            
        # Remove the node
        self.nodes.remove(node)
        
        # Clear selection if this node was selected
        if self.selected_node == node:
            self.selected_node = None
            self.node_deselected.emit()
            
        self.update()
        
    def remove_connection(self, connection: WorkflowConnection):
        """Remove a connection"""
        if connection in self.connections:
            connection.cleanup()  # Clean up node references
            self.connections.remove(connection)
            self.update()
            
    def delete_node(self, node: WorkflowNode):
        """Delete a node (emits deletion signal first)"""
        self.node_deletion_requested.emit(node)
        self.remove_node(node)
        
    def update_node_execution_status(self, node_id: str, status: str, output: str = ""):
        """Update execution status for a node"""
        for node in self.nodes:
            if node.node_id == node_id:
                node.set_execution_status(status, output)
                self.update()
                break
                
    def on_node_parameters_updated(self, node: WorkflowNode, parameters: Dict[str, Any]):
        """Handle node parameter updates"""
        # Update node parameters
        node.parameters = parameters
        
        # Update parameter display cache
        if hasattr(node, 'update_parameter_display'):
            node.update_parameter_display()
        
        # Automatically fix any node color issues that may have occurred
        # This prevents the issue where parameter updates cause color bleeding
        self.validate_and_fix_node_colors()
        
        # Emit signal for external listeners
        self.node_parameters_updated.emit(node, parameters)
        
        # Force canvas repaint to show updated parameters
        # The action points will be updated during the next paint event
        # to avoid recursion issues with dynamic height calculations
        self.update()
        
    def clear_canvas(self):
        """Clear all nodes and connections"""
        # Clean up all connections first
        for connection in self.connections[:]:  # Copy to avoid modification during iteration
            connection.cleanup()
            
        self.nodes.clear()
        self.connections.clear()
        self.selected_node = None
        self.workflow_variables.clear()
        self.variables_cleared.emit()
        self.update()
    
    # Variable Management Methods
    def set_variable(self, name: str, value: Any) -> None:
        """Set or update a workflow variable"""
        self.workflow_variables[name] = value
        self.variable_updated.emit(name, value)
        self.update()  # Refresh display in case variables are shown
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a workflow variable value"""
        return self.workflow_variables.get(name, default)
    
    def get_all_variables(self) -> Dict[str, Any]:
        """Get all workflow variables"""
        return self.workflow_variables.copy()
    
    def remove_variable(self, name: str) -> bool:
        """Remove a workflow variable"""
        if name in self.workflow_variables:
            del self.workflow_variables[name]
            self.variable_removed.emit(name)
            self.update()  # Refresh display in case variables are shown
            return True
        return False
    
    def clear_variables(self) -> None:
        """Clear all workflow variables"""
        self.workflow_variables.clear()
        self.variables_cleared.emit()
        self.update()
    
    def update_variables(self, variables: Dict[str, Any]) -> None:
        """Bulk update workflow variables"""
        for name, value in variables.items():
            self.workflow_variables[name] = value
            self.variable_updated.emit(name, value)
        self.update()
        
    def world_to_screen(self, world_pos: QPointF) -> QPointF:
        """Convert world coordinates to screen coordinates"""
        return QPointF(
            (world_pos.x() + self.pan_offset.x()) * self.zoom_factor,
            (world_pos.y() + self.pan_offset.y()) * self.zoom_factor
        )
        
    def screen_to_world(self, screen_pos: QPointF) -> QPointF:
        """Convert screen coordinates to world coordinates"""
        return QPointF(
            screen_pos.x() / self.zoom_factor - self.pan_offset.x(),
            screen_pos.y() / self.zoom_factor - self.pan_offset.y()
        )
        
    def get_visible_rect(self) -> QRectF:
        """Get the world rectangle that's currently visible"""
        top_left = self.screen_to_world(QPointF(0, 0))
        bottom_right = self.screen_to_world(QPointF(self.width(), self.height()))
        return QRectF(top_left, bottom_right)
        
    def snap_to_grid(self, position: QPointF) -> QPointF:
        """Snap position to the nearest grid point for consistent alignment"""
        grid_size = self.grid_size
        
        snapped_x = round(position.x() / grid_size) * grid_size
        snapped_y = round(position.y() / grid_size) * grid_size
        
        return QPointF(snapped_x, snapped_y)
        
    def find_node_at_position(self, world_pos: QPointF) -> Optional[WorkflowNode]:
        """Find the node at the given world position"""
        for node in reversed(self.nodes):  # Check from top to bottom
            if node.contains_point(world_pos.x(), world_pos.y()):
                return node
        return None
        
    def paintEvent(self, event: QPaintEvent):
        """Custom paint event for high-performance rendering with performance monitoring"""
        # Prevent recursive painting
        if self._is_painting:
            return
            
        self._is_painting = True
        
        painter = QPainter(self)
        
        # Enable antialiasing if requested
        if self.enable_antialiasing:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
        try:
            # Fill background
            painter.fillRect(self.rect(), self.background_color)
            
            # Draw grid if enabled
            if self.enable_grid:
                self._draw_grid(painter)
                
            # Draw connections first (behind nodes)
            self._draw_connections(painter)
            
            # Draw nodes
            self._draw_nodes(painter)
            
            # Draw selection rectangle if active
            if self.is_selecting:
                self._draw_selection_rectangle(painter)
            
            # Draw action points for selected node
            if self.selected_node:
                self._draw_action_points(painter, self.selected_node)
            
        finally:
            painter.end()
            self._is_painting = False
            
            
    def _draw_grid(self, painter: QPainter):
        """Draw the background dot matrix grid"""
        # Set up dot drawing properties
        dot_color = QColor(self.dot_color)
        dot_color.setAlphaF(self.dot_opacity)
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.PenStyle.NoPen)  # No outline for dots
        
        # Get visible area
        visible_rect = self.get_visible_rect()
        
        # Calculate grid bounds with some padding to avoid edge artifacts
        grid_spacing = self.grid_size
        padding = grid_spacing * 2
        start_x = int((visible_rect.left() - padding) / grid_spacing) * grid_spacing
        start_y = int((visible_rect.top() - padding) / grid_spacing) * grid_spacing
        end_x = visible_rect.right() + padding
        end_y = visible_rect.bottom() + padding
        
        # Calculate dot size based on zoom level for better visibility
        screen_dot_size = max(1.0, self.dot_size * self.zoom_factor)
        
        # Only draw dots if they will be visible (performance optimization)
        if screen_dot_size < 0.5:
            return
        
        # Enhanced performance: Calculate drawing bounds in screen space to reduce coordinate conversions
        widget_rect = QRectF(0, 0, self.width(), self.height())
        dot_radius = screen_dot_size
        
        # Draw dots at grid intersections with optimized boundary checking
        y = start_y
        dots_drawn = 0
        max_dots = 10000  # Prevent excessive dot rendering at extreme zoom levels
        
        while y <= end_y and dots_drawn < max_dots:
            x = start_x
            while x <= end_x and dots_drawn < max_dots:
                # Convert world coordinates to screen coordinates
                screen_pos = self.world_to_screen(QPointF(x, y))
                
                # Enhanced viewport culling: check if dot (including radius) is within visible area
                dot_bounds = QRectF(
                    screen_pos.x() - dot_radius,
                    screen_pos.y() - dot_radius,
                    dot_radius * 2,
                    dot_radius * 2
                )
                
                if widget_rect.intersects(dot_bounds):
                    painter.drawEllipse(
                        int(screen_pos.x() - dot_radius),
                        int(screen_pos.y() - dot_radius),
                        int(dot_radius * 2),
                        int(dot_radius * 2)
                    )
                    dots_drawn += 1
                
                x += grid_spacing
            y += grid_spacing
        
        # Reset brush after drawing dots to avoid affecting subsequent drawings
        painter.setBrush(Qt.BrushStyle.NoBrush)
            
    def _draw_connections(self, painter: QPainter):
        """Draw all connections between nodes"""
        visible_rect = self.get_visible_rect()
        
        for connection in self.connections:
            # Get connection points
            start_point = connection.get_start_point()
            end_point = connection.get_end_point()
            
            # Use the connection's bounding rect which includes margins
            # This ensures straight connections (zero width/height) are properly handled
            conn_rect = connection.get_bounding_rect()
            if not visible_rect.intersects(conn_rect):
                continue
                
            # Convert to screen coordinates
            screen_start = self.world_to_screen(start_point)
            screen_end = self.world_to_screen(end_point)
            
            # Draw bezier curve connection
            painter.setPen(QPen(connection.color, 2))
            self._draw_bezier_connection(painter, screen_start, screen_end, connection.connection_type)
            
    def _draw_bezier_connection(self, painter: QPainter, start: QPointF, end: QPointF, connection_type=None):
        """Draw a curved connection between two points using QPainterPath"""
        from PyQt6.QtGui import QPainterPath
        import math
        
        # Special handling for False connections from conditional nodes (vertical routing)
        if connection_type == ConnectionType.CONDITIONAL_FALSE:
            # Create vertical connection like horizontal ones but rotated 90 degrees
            dy = end.y() - start.y()
            offset = 15  # Pixels to go straight before curving
            
            # Use the actual start point now that connection points are working correctly
            compensated_start = start
            
            # For very small distances, draw straight line
            if abs(dy) < 10:
                painter.drawLine(compensated_start, end)
                self._draw_arrow_head(painter, compensated_start, end)
                return
            
            # Create a bezier curve using QPainterPath (vertical version of horizontal logic)
            path = QPainterPath()
            path.moveTo(compensated_start)
            
            # Calculate offset points - go straight down for 'offset' pixels before curving
            # Start offset: move vertically from compensated start
            start_offset = QPointF(compensated_start.x(), compensated_start.y() + offset)
            
            # End offset: move vertically towards end (negative offset since we're approaching from above)
            end_offset = QPointF(end.x(), end.y() - offset)
            
            # Draw straight line from compensated start to start_offset
            path.lineTo(start_offset)
            
            # Calculate control points for smooth curve between offset points
            remaining_dy = end_offset.y() - start_offset.y()
            control1 = QPointF(start_offset.x(), start_offset.y() + remaining_dy * 0.5)
            control2 = QPointF(end_offset.x(), end_offset.y() - remaining_dy * 0.5)
            
            # Create the bezier curve between offset points
            path.cubicTo(control1, control2, end_offset)
            
            # Draw straight line from end_offset to end
            path.lineTo(end)
            
            # Draw the complete path
            painter.drawPath(path)
            
            # Draw arrow head pointing down at the end
            self._draw_arrow_head(painter, end_offset, end)
            return
        
        # Standard horizontal connection logic for other connection types
        dx = end.x() - start.x()
        offset = 15  # Pixels to go straight before curving
        
        # For very small distances or straight vertical lines, draw straight line  
        if abs(dx) < 10:
            painter.drawLine(start, end)
            self._draw_arrow_head(painter, start, end)
            return
        
        # Create a bezier curve using QPainterPath
        path = QPainterPath()
        path.moveTo(start)
        
        # Calculate offset points - go straight for 'offset' pixels before curving
        # Start offset: move horizontally from start
        start_offset = QPointF(start.x() + offset, start.y())
        
        # End offset: move horizontally towards end (negative offset since we're approaching from left)
        end_offset = QPointF(end.x() - offset, end.y())
        
        # Draw straight line from start to start_offset
        path.lineTo(start_offset)
        
        # Calculate control points for smooth curve between offset points
        remaining_dx = end_offset.x() - start_offset.x()
        control1 = QPointF(start_offset.x() + remaining_dx * 0.5, start_offset.y())
        control2 = QPointF(end_offset.x() - remaining_dx * 0.5, end_offset.y())
        
        # Create the bezier curve between offset points
        path.cubicTo(control1, control2, end_offset)
        
        # Draw straight line from end_offset to end
        path.lineTo(end)
        
        # Draw the complete path
        painter.drawPath(path)
        
        # Draw arrow head at the end
        self._draw_arrow_head(painter, start, end)
    
    def _draw_arrow_head(self, painter, start: QPointF, end: QPointF):
        """Draw an arrow head at the end of the connection"""
        import math
        from PyQt6.QtGui import QPen
        
        # Calculate connection direction
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        
        # Don't draw arrow for very short connections
        if abs(dx) < 5 and abs(dy) < 5:
            return
        
        # Determine arrow angle based on connection type
        if abs(dx) < 10:  # Vertical connection
            # Arrow points in the direction the connection is coming from
            if dy > 0:  # Connection going down
                angle = math.pi / 2  # 90 degrees (pointing down)
            else:  # Connection going up
                angle = -math.pi / 2  # -90 degrees (pointing up)
        else:
            # Horizontal connections - arrow always points right (into the node)
            angle = 0  # 0 degrees (pointing right)
        
        arrow_length = 12
        arrow_degrees = math.pi / 6  # 30 degrees
        
        # Calculate arrow points based on fixed angle
        arrow_p1 = QPointF(
            end.x() - arrow_length * math.cos(angle - arrow_degrees),
            end.y() - arrow_length * math.sin(angle - arrow_degrees)
        )
        
        arrow_p2 = QPointF(
            end.x() - arrow_length * math.cos(angle + arrow_degrees),
            end.y() - arrow_length * math.sin(angle + arrow_degrees)
        )
        
        # Draw arrow as simple lines
        painter.drawLine(end, arrow_p1)
        painter.drawLine(end, arrow_p2)
            
    def _draw_nodes(self, painter: QPainter):
        """Draw all nodes"""
        visible_rect = self.get_visible_rect()
        
        for node in self.nodes:
            # Visibility culling
            node_rect = node.get_rect()
            if not visible_rect.intersects(node_rect):
                continue
            
            # Save painter state before drawing each node to prevent color bleeding
            painter.save()
            
            try:
                # Calculate dynamic node height based on parameter display needs
                dynamic_height = self._calculate_dynamic_node_height(node)
                
                # Cache the dynamic height on the node for use by connection points and action points
                node._cached_dynamic_height = dynamic_height
                
                # Convert to screen coordinates using dynamic height
                screen_rect = QRectF(
                    self.world_to_screen(QPointF(node.x, node.y)),
                    self.world_to_screen(QPointF(node.x + node.width, node.y + dynamic_height))
                )
                
                # Choose colors based on selection
                if node.selected:
                    fill_color = node.selected_color
                    border_color = node.selected_color.lighter(150)
                else:
                    fill_color = node.fill_color
                    border_color = node.border_color
                    
                # Draw node background and shape
                painter.setPen(QPen(border_color, 2))
                
                if node.node_type == "condition":
                    # Draw diamond shape for conditional nodes
                    from PyQt6.QtGui import QPainterPath
                    
                    # Make diamond square by using smaller dimension
                    diamond_size = min(screen_rect.width(), screen_rect.height())
                    center_x = screen_rect.center().x()
                    center_y = screen_rect.center().y()
                    half_size = diamond_size / 2
                    
                    # Define diamond points using square dimensions (top, right, bottom, left)
                    diamond_path = QPainterPath()
                    diamond_path.moveTo(center_x, center_y - half_size)  # Top point
                    diamond_path.lineTo(center_x + half_size, center_y)  # Right point
                    diamond_path.lineTo(center_x, center_y + half_size)  # Bottom point
                    diamond_path.lineTo(center_x - half_size, center_y)  # Left point
                    diamond_path.closeSubpath()  # Close the diamond
                    
                    # Fill and draw the diamond
                    painter.fillPath(diamond_path, fill_color)
                    painter.drawPath(diamond_path)
                else:
                    # Draw rectangle shape for all other node types
                    painter.fillRect(screen_rect, fill_color)
                    painter.drawRect(screen_rect)
                
                # Calculate layout areas
                title_height = int(screen_rect.height() * 0.3)  # Reduce title to 30% for more parameter space
                module_height = int(screen_rect.height() * 0.15)  # 15% for module name
                param_area_height = screen_rect.height() - title_height - module_height - 20  # Rest for parameters
                
                # Draw node title
                painter.setPen(QPen(node.text_color, 1))
                title_font = QFont("Montserrat", max(8, int(12 * self.zoom_factor)), QFont.Weight.Bold)
                painter.setFont(title_font)
                
                if node.node_type == "condition":
                    # For diamond shapes, center the title in the middle of the diamond
                    title_rect = QRectF(screen_rect.center().x() - screen_rect.width()/4, 
                                       screen_rect.center().y() - 10, 
                                       screen_rect.width()/2, 
                                       20)
                    painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, node.title)
                else:
                    # For rectangular shapes, use the top area for title
                    title_rect = QRectF(screen_rect.x(), screen_rect.y(), screen_rect.width(), title_height)
                    painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, node.title)
                
                # Draw module container with parameters if zoom level is sufficient
                if self.zoom_factor > 0.3 and node.node_type == "action":
                    self._draw_module_container_with_parameters(painter, node, screen_rect, title_height, module_height)
                elif self.zoom_factor > 0.3 and node.node_type != "condition":
                    # For non-action, non-condition nodes, draw parameters without module container
                    # Skip parameter badges for condition nodes since they don't fit well in diamond shape
                    param_start_y = title_height
                    self._draw_parameter_badges(painter, node, screen_rect, param_start_y)
                
                    # Update action point positions when drawing
                    node.update_action_points()
            
            finally:
                # Restore painter state after drawing each node to prevent color bleeding
                painter.restore()
            
    def _draw_module_name(self, painter: QPainter, node: WorkflowNode, node_rect: QRectF, title_height: int, module_height: int):
        """Draw the module name for action nodes"""
        if not hasattr(node, 'parameters') or not node.parameters:
            return
            
        module_name = node.parameters.get('module', '')
        if not module_name:
            return
            
        # Module name styling
        module_font = QFont("Montserrat", max(7, int(10 * self.zoom_factor)), QFont.Weight.Normal)
        painter.setFont(module_font)
        
        # Module name area
        module_rect = QRectF(
            node_rect.x() + 5, 
            node_rect.y() + title_height + 2, 
            node_rect.width() - 10, 
            module_height - 4
        )
        
        # Draw opaque background for module name
        module_bg_color = QColor(45, 45, 45, 200)  # More opaque dark background
        painter.fillRect(module_rect, module_bg_color)
        
        # Draw module name text with better contrast
        painter.setPen(QPen(QColor(220, 220, 220), 1))  # Brighter text for better readability
        painter.drawText(module_rect, Qt.AlignmentFlag.AlignCenter, module_name)
        
    def _draw_module_container_with_parameters(self, painter: QPainter, node: WorkflowNode, node_rect: QRectF, title_height: int, module_height: int):
        """Draw module name container with parameters grouped inside"""
        if not hasattr(node, 'parameters') or not node.parameters:
            return
            
        module_name = node.parameters.get('module', '')
        if not module_name:
            return
            
        # Get important parameters first to calculate container size
        important_params = self._get_important_parameters(node)
        if not important_params:
            # Just draw module name if no parameters
            self._draw_module_name(painter, node, node_rect, title_height, module_height)
            return
            
        # Calculate total container area needed
        badge_height = int(20 * self.zoom_factor)  # Remove minimum, let it scale fully
        badge_margin = int(4 * self.zoom_factor)  # Scale margin too
        param_count = min(len(important_params), 3)  # Max 3 parameters
        
        # Container layout
        module_header_height = module_height
        params_area_height = (badge_height + badge_margin) * param_count + badge_margin
        total_container_height = module_header_height + params_area_height
        
        # Container boundaries with padding
        container_padding = 3
        container_rect = QRectF(
            node_rect.x() + container_padding,
            node_rect.y() + title_height,
            node_rect.width() - (2 * container_padding),
            total_container_height
        )
        
        # Draw container background with rounded corners
        container_bg_color = QColor(55, 55, 55, 220)  # Slightly lighter than node background
        painter.setBrush(QBrush(container_bg_color))
        painter.setPen(QPen(QColor(80, 80, 80), 1))  # Subtle border
        painter.drawRoundedRect(container_rect, 8, 8)
        
        # Draw module header area
        module_header_rect = QRectF(
            container_rect.x() + 2,
            container_rect.y() + 2,
            container_rect.width() - 4,
            module_header_height - 2
        )
        
        # Module header background (slightly different shade)
        module_header_bg = QColor(65, 65, 65, 240)
        painter.setBrush(QBrush(module_header_bg))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRoundedRect(module_header_rect, 6, 6)
        
        # Draw module name text
        module_font = QFont("Montserrat", int(10 * self.zoom_factor), QFont.Weight.Bold)
        painter.setFont(module_font)
        painter.setPen(QPen(QColor(240, 240, 240), 1))  # Bright text
        painter.drawText(module_header_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter, module_name)
        
        # Draw parameters inside container
        self._draw_parameters_in_container(painter, node, container_rect, module_header_height, important_params)
        
    def _draw_parameters_in_container(self, painter: QPainter, node: WorkflowNode, container_rect: QRectF, header_height: int, important_params: List[Tuple[str, Any]]):
        """Draw parameter badges inside the module container"""
        if not important_params:
            return
            
        # Save painter state before badge drawing to prevent color bleeding to other nodes
        painter.save()
        
        # Parameter styling
        badge_font = QFont("SourceCodePro", int(8 * self.zoom_factor))
        badge_height = int(18 * self.zoom_factor)  # Scale fully
        badge_margin = int(3 * self.zoom_factor)  # Scale margin too
        corner_radius = int(8 * self.zoom_factor)  # Scale corner radius
        
        painter.setFont(badge_font)
        
        # Start position for parameters (below module header)
        current_y = container_rect.y() + header_height + badge_margin
        param_area_width = container_rect.width() - 8  # Leave padding on sides
        
        for param_name, param_value in important_params[:6]:  # Allow up to 6 parameters for expansion
            if current_y + badge_height > container_rect.bottom() - badge_margin:
                break  # No more space
                
            # Format parameter text
            param_text = self._format_parameter_text_with_name(param_name, param_value)
            if not param_text:
                continue
                
            # Calculate badge width with padding
            text_width = painter.fontMetrics().horizontalAdvance(param_text)
            badge_width = min(text_width + 12, param_area_width)  # Fit within container
            
            # Center badge horizontally within container
            badge_x = container_rect.x() + (container_rect.width() - badge_width) / 2
            badge_rect = QRectF(badge_x, current_y, badge_width, badge_height)
            
            # Get badge color
            badge_color = self._get_parameter_badge_color(node, param_name, param_value)
            
            # Draw badge with subtle styling to fit container
            painter.setBrush(QBrush(badge_color))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1))  # Softer border for container
            painter.drawRoundedRect(badge_rect, corner_radius, corner_radius)
            
            # Draw parameter text
            text_color = QColor(255, 255, 255) if self._is_dark_color(badge_color) else QColor(40, 40, 40)
            painter.setPen(QPen(text_color, 1))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter, param_text)
            
            current_y += badge_height + badge_margin
            
        # Restore painter state to prevent color bleeding to other nodes
        painter.restore()
            
    def _calculate_dynamic_node_height(self, node: WorkflowNode) -> float:
        """Calculate the dynamic height needed for the node based on its content"""
        base_height = node.height  # Original node height
        
        # Only expand for action nodes with parameters when zoomed in
        if self.zoom_factor <= 0.3 or node.node_type != "action":
            return base_height
            
        if not hasattr(node, 'parameters') or not node.parameters:
            return base_height
            
        module_name = node.parameters.get('module', '')
        if not module_name:
            return base_height
            
        # Simple, direct calculation without calling other methods
        # Count non-internal parameters
        internal_keys = {"schema_file", "module", "category", "display_name"}
        param_count = sum(1 for k, v in node.parameters.items() 
                         if k not in internal_keys and v and str(v).strip())
        
        if param_count == 0:
            return base_height
            
        # Limit to 6 parameters max
        param_count = min(param_count, 6)
        
        # Calculate space requirements
        title_height = base_height * 0.3  # 30% for title
        module_header_height = base_height * 0.15  # 15% for module header
        
        # Calculate parameter area requirements
        badge_height = int(20 * self.zoom_factor)  # Scale fully
        badge_margin = int(3 * self.zoom_factor)  # Scale margin too
        
        params_area_height = (badge_height + badge_margin) * param_count + badge_margin * 2
        container_padding = 6  # Top and bottom padding for container
        action_points_space = 25  # Space for action points at bottom
        
        # Calculate required total height
        required_content_height = title_height + module_header_height + params_area_height + container_padding + action_points_space
        
        # Return the larger of base height or required height
        return max(base_height, required_content_height)
            
    def _draw_parameter_badges(self, painter: QPainter, node: WorkflowNode, node_rect: QRectF, param_start_y: int):
        """Draw parameter badges showing key module parameters (not node configuration)"""
        if not hasattr(node, 'parameters') or not node.parameters:
            return
            
        # Get prioritized module parameters for this node type
        important_params = self._get_important_parameters(node)
        if not important_params:
            return
            
        # Calculate badge area (below module name/title, above action points)
        available_height = node_rect.height() - param_start_y - 25  # Leave space for action points
        
        if available_height < 20:  # Not enough space
            return
            
        # Save painter state before badge drawing to prevent color bleeding to other nodes
        painter.save()
        
        # Badge styling - improved visual design
        badge_font = QFont("SourceCodePro", int(9 * self.zoom_factor))
        badge_height = int(20 * self.zoom_factor)  # Scale fully
        badge_margin = int(4 * self.zoom_factor)  # Scale margin too
        corner_radius = int(10 * self.zoom_factor)  # Scale corner radius
        
        painter.setFont(badge_font)
        
        current_y = node_rect.y() + param_start_y + 5
        
        for param_name, param_value in important_params[:3]:  # Show max 3 parameters
            if current_y + badge_height > node_rect.bottom() - 15:
                break  # No more space
                
            # Format parameter text with parameter name included
            param_text = self._format_parameter_text_with_name(param_name, param_value)
            if not param_text:
                continue
                
            # Calculate badge width with proper padding
            text_width = painter.fontMetrics().horizontalAdvance(param_text)
            badge_width = min(text_width + 16, node_rect.width() - 12)  # More padding, better max width
            
            # Center badge horizontally
            badge_x = node_rect.x() + (node_rect.width() - badge_width) / 2
            badge_rect = QRectF(badge_x, current_y, badge_width, badge_height)
            
            # Get badge color based on parameter status
            badge_color = self._get_parameter_badge_color(node, param_name, param_value)
            
            # Draw badge with proper rounded rectangle (no border artifacts)
            painter.setBrush(QBrush(badge_color))
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1.5))  # Softer border
            painter.drawRoundedRect(badge_rect, corner_radius, corner_radius)
            
            # Draw parameter text with better contrast and proper vertical centering
            text_color = QColor(255, 255, 255) if self._is_dark_color(badge_color) else QColor(50, 50, 50)
            painter.setPen(QPen(text_color, 1))
            
            # Use proper vertical centering with AlignVCenter combined with AlignHCenter
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter, param_text)
            
            current_y += badge_height + badge_margin
            
        # Restore painter state to prevent color bleeding to other nodes
        painter.restore()
            
    def _get_important_parameters(self, node: WorkflowNode) -> List[Tuple[str, Any]]:
        """Get the most important module parameters to display for a node type"""
        if not hasattr(node, 'parameters'):
            return []
            
        important_params = []
        params = node.parameters
        
        # Node type specific parameter prioritization
        if node.node_type == "action":
            # For action nodes, show MODULE parameters (not node configuration)
            # Skip internal node config keys and show actual module parameters
            internal_keys = {"schema_file", "module", "category", "display_name"}
            
            # Get module parameters (everything except internal config)
            module_params = {k: v for k, v in params.items() if k not in internal_keys}
            
            # Prioritize common module parameter names
            priority_keys = ["target", "hostname", "ip", "port", "filename", "path", "command", "url", "username", "password"]
            
            # First add priority parameters if they exist
            for key in priority_keys:
                if key in module_params and module_params[key] and len(important_params) < 6:
                    important_params.append((key, module_params[key]))
            
            # Then add any remaining module parameters
            for key, value in module_params.items():
                if key not in priority_keys and value and len(important_params) < 6:
                    important_params.append((key, value))
                    
        elif node.node_type == "condition":
            # For condition nodes, show condition logic parameters
            priority_keys = ["condition_type", "condition_value", "case_sensitive"]
            for key in priority_keys:
                if key in params and params[key] and len(important_params) < 6:
                    important_params.append((key, params[key]))
                    
        elif node.node_type == "delay":
            # For delay nodes, show timing parameters
            priority_keys = ["delay_seconds", "delay_type"]
            for key in priority_keys:
                if key in params and params[key] and len(important_params) < 6:
                    important_params.append((key, params[key]))
        else:
            # For other nodes, show any available parameters
            for key, value in list(params.items())[:6]:
                if value and len(important_params) < 6:
                    important_params.append((key, value))
                
        return important_params
        
    def _format_parameter_text(self, param_name: str, param_value: Any) -> str:
        """Format module parameter for display in badge"""
        if param_value is None or param_value == "":
            return ""
            
        # Convert value to string and truncate if needed
        value_str = str(param_value)
        
        # Special formatting for common module parameter types
        if param_name in ["filename", "path"]:
            # Show just filename without path
            if "/" in value_str:
                value_str = value_str.split("/")[-1]
                
        elif param_name in ["target", "hostname", "ip"]:
            # Show target addresses as-is
            pass
            
        elif param_name == "port":
            # Show port numbers as-is
            pass
            
        elif param_name == "delay_seconds":
            value_str = f"{value_str}s"
            
        elif param_name == "condition_type":
            # Abbreviate condition types
            type_abbrev = {"contains": "has", "equals": "==", "regex": "re"}
            value_str = type_abbrev.get(value_str, value_str)
            
        elif param_name in ["username", "password"]:
            # Mask sensitive parameters
            if param_name == "password":
                value_str = "*" * min(len(value_str), 6)
            
        # Truncate long values
        max_length = 15
        if len(value_str) > max_length:
            value_str = value_str[:max_length-3] + "..."
            
        # Format as "name: value" or just "value" for some cases
        if param_name in ["target", "hostname", "ip", "filename", "command"]:
            # Show value-only for these important parameters
            return value_str
        else:
            # Show name: value format for others
            return f"{param_name}: {value_str}"
            
    def _format_parameter_text_with_name(self, param_name: str, param_value: Any) -> str:
        """Format module parameter with name for enhanced badge display"""
        if param_value is None or param_value == "":
            return f"{param_name}: (not set)"
            
        # Convert value to string and truncate if needed
        value_str = str(param_value)
        
        # Special formatting for common module parameter types
        if param_name in ["filename", "path"]:
            # Show just filename without path
            if "/" in value_str:
                value_str = value_str.split("/")[-1]
                
        elif param_name in ["target", "hostname", "ip"]:
            # Keep target addresses as-is
            pass
            
        elif param_name == "port":
            # Keep port numbers as-is
            pass
            
        elif param_name == "delay_seconds":
            value_str = f"{value_str}s"
            
        elif param_name == "condition_type":
            # Abbreviate condition types
            type_abbrev = {"contains": "has", "equals": "==", "regex": "re"}
            value_str = type_abbrev.get(value_str, value_str)
            
        elif param_name in ["username", "password"]:
            # Mask sensitive parameters
            if param_name == "password":
                value_str = "*" * min(len(value_str), 6)
            
        # Truncate long values
        max_value_length = 12  # Shorter for name:value format
        if len(value_str) > max_value_length:
            value_str = value_str[:max_value_length-3] + "..."
            
        # Always show as name: value format for clarity
        return f"{param_name}: {value_str}"
        
    def _is_dark_color(self, color: QColor) -> bool:
        """Check if a color is dark (for text contrast)"""
        # Calculate luminance using standard formula
        r, g, b = color.red(), color.green(), color.blue()
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5
            
    def _get_parameter_badge_color(self, node: WorkflowNode, param_name: str, param_value: Any) -> QColor:
        """Get color for module parameter badge based on parameter status"""
        
        # Check if parameter has a value
        if param_value is None or param_value == "":
            return QColor(120, 120, 120, 180)  # Gray for empty
            
        # Color code based on parameter importance for beacon modules
        if param_name in ["target", "hostname", "ip", "command"]:
            # Critical module parameters - green when set
            return QColor(34, 139, 34, 180)  # Green for critical parameters
        elif param_name in ["filename", "path", "url"]:
            # Important file/resource parameters - orange when set
            return QColor(255, 140, 0, 180)  # Orange for file parameters  
        elif param_name in ["username", "password", "port"]:
            # Security/connection parameters - red when set
            return QColor(220, 20, 60, 180)  # Crimson for security parameters
        elif param_name == "condition_value":
            # Condition parameters - purple when set
            return QColor(138, 43, 226, 180)  # Blue violet for condition logic
        else:
            # Optional/other parameters - blue when set  
            return QColor(70, 130, 180, 180)  # Steel blue for optional
            
    def _draw_action_points(self, painter: QPainter, node: WorkflowNode):
        """Draw action points for a selected node"""
        for action_point in node.action_points:
            if not action_point.is_visible:
                continue
                
            # Skip action points that already have connections
            if node.has_connections_from_action_point(action_point.point_type):
                continue
                
            # Convert to screen coordinates
            screen_pos = self.world_to_screen(QPointF(action_point.x, action_point.y))
            
            # Draw action point circle
            color = action_point.get_color()
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255) if action_point.is_hovered else QColor(0, 0, 0), 2))
            
            radius = action_point.radius * self.zoom_factor
            painter.drawEllipse(screen_pos, int(radius), int(radius))
            
            # Draw + symbol
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            half_size = radius * 0.4
            # Horizontal line
            painter.drawLine(
                QPointF(screen_pos.x() - half_size, screen_pos.y()),
                QPointF(screen_pos.x() + half_size, screen_pos.y())
            )
            # Vertical line
            painter.drawLine(
                QPointF(screen_pos.x(), screen_pos.y() - half_size),
                QPointF(screen_pos.x(), screen_pos.y() + half_size)
            )
            
            # Draw label if present
            if action_point.label and self.zoom_factor > 0.7:
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                font = QFont("Montserrat", max(8, int(10 * self.zoom_factor)))
                painter.setFont(font)
                
                # Position label based on action point position
                if action_point.position == "right":
                    label_pos = QPointF(screen_pos.x() + radius + 5, screen_pos.y() - 5)
                else:
                    label_pos = QPointF(screen_pos.x() - 20, screen_pos.y() + radius + 15)
                    
                painter.drawText(label_pos, action_point.label)
                
    def _update_action_points_for_node(self, node: WorkflowNode):
        """Update action point visibility based on connections"""
        for action_point in node.action_points:
            # Hide action points that already have connections
            has_connection = node.has_connections_from_action_point(action_point.point_type)
            if has_connection and action_point.is_visible:
                action_point.is_visible = False
            
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events
        
        Drag behavior: When clicking on a node, we store the offset between the click
        position and the node's position. This ensures the node doesn't jump during
        dragging - the point under the cursor remains under the cursor throughout
        the drag operation. Multiple selected nodes maintain their relative positions.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            world_pos = self.screen_to_world(QPointF(event.position()))
            
            # Check if Shift is held for selection rectangle
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Start selection rectangle
                self.is_selecting = True
                self.selection_start = world_pos
                self.selection_end = world_pos
                self.setCursor(Qt.CursorShape.CrossCursor)
                return
            
            # Check if click is on an action point of the selected node FIRST
            # This needs to happen before node detection since action points are outside node bounds
            if self.selected_node:
                action_point = self.selected_node.get_action_point_at(world_pos.x(), world_pos.y())
                if action_point and action_point.is_visible:
                    self._handle_action_point_click(self.selected_node, action_point)
                    return
            
            # Now check if click is on a node
            clicked_node = self.find_node_at_position(world_pos)
            
            if clicked_node:
                # Check if Ctrl is held for multi-selection
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    # Toggle node selection
                    if clicked_node in self.selected_nodes:
                        self.selected_nodes.remove(clicked_node)
                        clicked_node.selected = False
                        clicked_node.hide_action_points()
                    else:
                        self.selected_nodes.append(clicked_node)
                        clicked_node.selected = True
                    
                    # Update single selected node reference for compatibility
                    self.selected_node = self.selected_nodes[-1] if self.selected_nodes else None
                    if self.selected_node:
                        self.selected_node.show_action_points()
                        # Only emit node_selected signal for editable nodes (not End nodes)
                        # Trigger/Start nodes are now editable, End nodes are not
                        if self.selected_node.node_type != 'end':
                            self.node_selected.emit(self.selected_node)
                    else:
                        self.node_deselected.emit()
                else:
                    # Single node selection - clear previous selection
                    self.clear_selection()
                    self.selected_node = clicked_node
                    self.selected_nodes = [clicked_node]
                    clicked_node.selected = True
                    clicked_node.show_action_points()
                    # Only emit node_selected signal for editable nodes (not End nodes)
                    # Trigger/Start nodes are now editable, End nodes are not
                    if clicked_node.node_type != 'end':
                        self.node_selected.emit(clicked_node)
                
                # Start dragging if not using Ctrl
                if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self.is_dragging_node = True
                    self.drag_start_pos = event.position().toPoint()
                    
                    # Calculate offset between click position and node position
                    # This maintains the relative position during drag
                    node_pos = QPointF(clicked_node.x, clicked_node.y)
                    self.drag_offset = world_pos - node_pos
                    
                    # Store offsets for all selected nodes (for multi-node dragging)
                    self.drag_node_offsets = {}
                    for node in self.selected_nodes:
                        node_world_pos = QPointF(node.x, node.y)
                        self.drag_node_offsets[node] = world_pos - node_world_pos
                
                self.update()
            else:
                # Empty space clicked - start panning
                self.is_panning = True
                self.last_mouse_pos = event.position().toPoint()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                
                
                # Clear selection
                self.clear_selection()
                    
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click for context menu (future feature)
            pass
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events"""
        current_pos = event.position().toPoint()
        
        if self.is_selecting:
            # Update selection rectangle end position
            self.selection_end = self.screen_to_world(QPointF(current_pos))
            self._update_selection_preview()
            self.update()
            
        elif self.is_dragging_node:
            # Drag selected node(s) with grid snapping while maintaining offset
            world_pos = self.screen_to_world(QPointF(current_pos))
            
            # Move all selected nodes while maintaining their relative positions
            if self.selected_nodes and self.drag_node_offsets:
                for node in self.selected_nodes:
                    if node in self.drag_node_offsets:
                        # Apply the specific offset for this node
                        node_offset = self.drag_node_offsets[node]
                        target_pos = world_pos - node_offset
                        snapped_pos = self.snap_to_grid(target_pos)
                        
                        node.move_to(snapped_pos.x(), snapped_pos.y())
                        self.node_moved.emit(node, QPointF(node.x, node.y))
            elif self.selected_node:
                # Fallback for single node (shouldn't normally happen)
                target_pos = world_pos - self.drag_offset
                snapped_pos = self.snap_to_grid(target_pos)
                
                self.selected_node.move_to(snapped_pos.x(), snapped_pos.y())
                self.node_moved.emit(self.selected_node, QPointF(self.selected_node.x, self.selected_node.y))
            
            self.update()
            
        elif self.is_panning:
            # Pan the viewport
            delta = current_pos - self.last_mouse_pos
            self.pan_offset += QPointF(delta.x() / self.zoom_factor, delta.y() / self.zoom_factor)
            self.update()
            
            
        self.last_mouse_pos = current_pos
        
        # Update action point hover states
        if not self.is_dragging_node and not self.is_panning and not self.is_selecting:
            self._update_action_point_hover(current_pos)
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_selecting:
                # Complete selection rectangle
                self._finalize_selection()
                self.is_selecting = False
                self.update()
            elif self.is_dragging_node:
                # Final grid snap to ensure perfect alignment for all selected nodes
                if self.selected_nodes:
                    for node in self.selected_nodes:
                        current_pos = QPointF(node.x, node.y)
                        snapped_pos = self.snap_to_grid(current_pos)
                        node.move_to(snapped_pos.x(), snapped_pos.y())
                        self.node_moved.emit(node, snapped_pos)
                elif self.selected_node:
                    current_pos = QPointF(self.selected_node.x, self.selected_node.y)
                    snapped_pos = self.snap_to_grid(current_pos)
                    self.selected_node.move_to(snapped_pos.x(), snapped_pos.y())
                    self.node_moved.emit(self.selected_node, snapped_pos)
                self.update()
                
            self.is_dragging_node = False
            self.is_panning = False
            self.drag_offset = QPointF()  # Reset drag offset
            self.drag_node_offsets = {}  # Clear all node offsets
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
    def _handle_action_point_click(self, node: WorkflowNode, action_point: ActionPoint):
        """Handle click on an action point to show connection menu"""
        if not self.compatibility_manager or not self.template_registry:
            pass
            return
            
        try:
            # Import connection menu
            from .connection_menu import ConnectionMenu
            
            # Create connection menu
            menu = ConnectionMenu(
                node, action_point, 
                self.compatibility_manager, 
                self.template_registry
            )
            
            # Connect template selection signal
            menu.connection_option_selected.connect(
                lambda template: self._create_connection_from_template(node, action_point, template)
            )
            
            # Show menu at action point location
            screen_pos = self.world_to_screen(QPointF(action_point.x, action_point.y))
            global_pos = self.mapToGlobal(screen_pos.toPoint())
            menu.exec(global_pos)
            
        except ImportError as e:
            pass  # ConnectionMenu not available
        except Exception as e:
            pass  # Error showing connection menu
            
    def _create_connection_from_template(self, source_node: WorkflowNode, action_point: ActionPoint, template):
        """Create a new node and connection from template selection"""
        if not template:
            return
            
        try:
            # Create connection context
            connection_context = ConnectionContext(
                source_node_type=source_node.node_type,
                source_node_id=source_node.node_id,
                connection_type=action_point.connection_type
            )
            
            # Create new node from template with connection context for positioning
            new_node = self.add_node_from_template(template, None, None, connection_context)
            if not new_node:
                pass
                return
                
            # Create connection with proper point types
            start_point_type = action_point.point_type  # Use the action point's type
            # For False connections, connect to the top of the target node
            end_point_type = "top" if action_point.connection_type == ConnectionType.CONDITIONAL_FALSE else "input"
            connection = WorkflowConnection(
                source_node, 
                new_node, 
                action_point.connection_type,
                start_point_type=start_point_type,
                end_point_type=end_point_type
            )
            self.connections.append(connection)
            self.connection_created.emit(source_node, new_node)
            self.update()
                
        except Exception as e:
            pass  # Error creating connection from template
            
    def _update_action_point_hover(self, mouse_pos: QPoint):
        """Update action point hover states based on mouse position"""
        world_pos = self.screen_to_world(QPointF(mouse_pos))
        new_hovered = None
        
        # Check action points of selected node
        if self.selected_node:
            for action_point in self.selected_node.action_points:
                if action_point.is_visible and action_point.contains_point(world_pos.x(), world_pos.y()):
                    new_hovered = action_point
                    break
                    
        # Update hover states
        if new_hovered != self.hovered_action_point:
            if self.hovered_action_point:
                self.hovered_action_point.is_hovered = False
            if new_hovered:
                new_hovered.is_hovered = True
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                
            self.hovered_action_point = new_hovered
            self.update()
    
    def _update_selection_preview(self):
        """Update which nodes would be selected by current selection rectangle"""
        if not self.is_selecting:
            return
            
        # Calculate selection rectangle bounds
        selection_rect = QRectF(
            min(self.selection_start.x(), self.selection_end.x()),
            min(self.selection_start.y(), self.selection_end.y()),
            abs(self.selection_end.x() - self.selection_start.x()),
            abs(self.selection_end.y() - self.selection_start.y())
        )
        
        # Find nodes within selection rectangle
        preview_nodes = []
        for node in self.nodes:
            # Check if node center is within selection rectangle
            node_center = QPointF(node.x + node.width/2, node.y + node.height/2)
            if selection_rect.contains(node_center):
                preview_nodes.append(node)
        
        # Store preview for rendering
        self.selection_preview_nodes = preview_nodes
    
    def _finalize_selection(self):
        """Complete the selection rectangle and select all nodes within it"""
        if not self.is_selecting:
            return
            
        # Calculate final selection rectangle bounds
        selection_rect = QRectF(
            min(self.selection_start.x(), self.selection_end.x()),
            min(self.selection_start.y(), self.selection_end.y()),
            abs(self.selection_end.x() - self.selection_start.x()),
            abs(self.selection_end.y() - self.selection_start.y())
        )
        
        # Select all nodes within rectangle
        newly_selected = []
        for node in self.nodes:
            # Check if node center is within selection rectangle
            node_center = QPointF(node.x + node.width/2, node.y + node.height/2)
            if selection_rect.contains(node_center):
                newly_selected.append(node)
        
        # Update selection
        if newly_selected:
            # Set multi-node selection
            self.selected_nodes = newly_selected
            pass
            
            # Clear previous selection visuals
            if self.selected_node:
                self.selected_node.hide_action_points()
            for node in self.nodes:
                node.selected = False
            
            # Set primary node for editing (first in selection) without clearing multi-selection
            self.selected_node = newly_selected[0]
            self.selected_node.show_action_points()
            # Only emit node_selected signal for editable nodes (not End nodes)
            if self.selected_node.node_type != 'end':
                self.node_selected.emit(self.selected_node)
            
            # Mark all selected nodes as selected for visual feedback
            for node in newly_selected:
                node.selected = True
        
        # Clear preview
        self.selection_preview_nodes = []
    
    def _draw_selection_rectangle(self, painter: QPainter):
        """Draw the selection rectangle while dragging"""
        if not self.is_selecting:
            return
            
        # Convert world coordinates to screen coordinates
        screen_start = self.world_to_screen(self.selection_start)
        screen_end = self.world_to_screen(self.selection_end)
        
        # Calculate rectangle bounds
        x = min(screen_start.x(), screen_end.x())
        y = min(screen_start.y(), screen_end.y())
        width = abs(screen_end.x() - screen_start.x())
        height = abs(screen_end.y() - screen_start.y())
        
        selection_rect = QRectF(x, y, width, height)
        
        # Draw selection rectangle with semi-transparent fill
        selection_color = QColor(100, 150, 255, 50)  # Light blue with transparency
        border_color = QColor(100, 150, 255, 200)    # Darker blue border
        
        painter.setBrush(QBrush(selection_color))
        painter.setPen(QPen(border_color, 2, Qt.PenStyle.DashLine))
        painter.drawRect(selection_rect)
        
        # Highlight nodes that would be selected
        if hasattr(self, 'selection_preview_nodes') and self.selection_preview_nodes:
            highlight_color = QColor(255, 200, 100, 100)  # Orange highlight
            painter.setBrush(QBrush(highlight_color))
            painter.setPen(QPen(QColor(255, 200, 100, 180), 2))
            
            for node in self.selection_preview_nodes:
                # Draw highlight around node
                dynamic_height = self._calculate_dynamic_node_height(node)
                node_screen_pos = self.world_to_screen(QPointF(node.x, node.y))
                highlight_rect = QRectF(
                    node_screen_pos.x() - 3,
                    node_screen_pos.y() - 3,
                    (node.width * self.zoom_factor) + 6,
                    (dynamic_height * self.zoom_factor) + 6
                )
                painter.drawRoundedRect(highlight_rect, 8, 8)
            
    def wheelEvent(self, event: QWheelEvent):
        """Handle zoom with mouse wheel"""
        # Get mouse position for zoom center
        mouse_pos = QPointF(event.position())
        
        # Convert mouse position to world coordinates using current zoom
        world_pos = self.screen_to_world(mouse_pos)
        
        # Calculate new zoom factor
        zoom_delta = event.angleDelta().y() / 1200.0  # Smooth zooming
        new_zoom = self.zoom_factor * (1 + zoom_delta)
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        
        if new_zoom != self.zoom_factor:
            # Calculate new pan offset to keep world_pos under the mouse cursor
            # Formula: screen_pos = (world_pos + pan_offset) * zoom_factor
            # Rearraged: pan_offset = screen_pos / zoom_factor - world_pos
            new_pan_offset = QPointF(
                mouse_pos.x() / new_zoom - world_pos.x(),
                mouse_pos.y() / new_zoom - world_pos.y()
            )
            
            self.zoom_factor = new_zoom
            self.pan_offset = new_pan_offset
            
            self.update()
            
    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key.Key_Delete and self.selected_node:
            # Delete selected node
            self.delete_node(self.selected_node)
        elif event.key() == Qt.Key.Key_F:
            # Fit all nodes in view
            self.fit_all_nodes()
        elif event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            # Zoom in
            self.zoom_in()
        elif event.key() == Qt.Key.Key_Minus:
            # Zoom out
            self.zoom_out()
        elif event.key() == Qt.Key.Key_0:
            # Reset zoom
            self.reset_zoom()
        elif event.key() == Qt.Key.Key_Escape:
            # Clear selection
            self.clear_selection()
            
    def fit_all_nodes(self):
        """Fit all nodes in the viewport"""
        if not self.nodes:
            return
            
        # Calculate bounding box of all nodes
        min_x = min(node.x for node in self.nodes)
        min_y = min(node.y for node in self.nodes)
        max_x = max(node.x + node.width for node in self.nodes)
        max_y = max(node.y + node.height for node in self.nodes)
        
        # Add padding
        padding = 50
        content_width = max_x - min_x + 2 * padding
        content_height = max_y - min_y + 2 * padding
        
        # Calculate zoom to fit
        zoom_x = self.width() / content_width
        zoom_y = self.height() / content_height
        new_zoom = min(zoom_x, zoom_y, self.max_zoom)
        new_zoom = max(new_zoom, self.min_zoom)
        
        # Center the content
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        self.zoom_factor = new_zoom
        self.pan_offset = QPointF(
            self.width() / (2 * new_zoom) - center_x,
            self.height() / (2 * new_zoom) - center_y
        )
        
        self.update()
        
    def zoom_in(self):
        """Zoom in on the canvas"""
        center_point = QPointF(self.width() / 2, self.height() / 2)
        world_center = self.screen_to_world(center_point)
        
        new_zoom = self.zoom_factor * 1.25
        new_zoom = min(new_zoom, self.max_zoom)
        
        if new_zoom != self.zoom_factor:
            self.zoom_factor = new_zoom
            
            # Keep center point stable
            new_world_center = self.screen_to_world(center_point)
            world_delta = new_world_center - world_center
            self.pan_offset -= world_delta
            
            self.update()
            
    def zoom_out(self):
        """Zoom out on the canvas"""
        center_point = QPointF(self.width() / 2, self.height() / 2)
        world_center = self.screen_to_world(center_point)
        
        new_zoom = self.zoom_factor / 1.25
        new_zoom = max(new_zoom, self.min_zoom)
        
        if new_zoom != self.zoom_factor:
            self.zoom_factor = new_zoom
            
            # Keep center point stable
            new_world_center = self.screen_to_world(center_point)
            world_delta = new_world_center - world_center
            self.pan_offset -= world_delta
            
            self.update()
            
    def reset_zoom(self):
        """Reset zoom to 100%"""
        if self.zoom_factor != 1.0:
            center_point = QPointF(self.width() / 2, self.height() / 2)
            world_center = self.screen_to_world(center_point)
            
            self.zoom_factor = 1.0
            
            # Keep center point stable
            new_world_center = self.screen_to_world(center_point)
            world_delta = new_world_center - world_center
            self.pan_offset -= world_delta
            
            self.update()
        
    
        
    def monitor_workflow_execution(self, execution_id: str, workflow_engine):
        """Start monitoring workflow execution and update nodes in real-time"""
        self.execution_id = execution_id
        self.workflow_engine = workflow_engine
        
        # Create timer to poll execution status
        from PyQt6.QtCore import QTimer
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(
            lambda: self._check_execution_status(execution_id, workflow_engine)
        )
        self.execution_timer.start(1000)  # Check every second
        
    def _check_execution_status(self, execution_id: str, workflow_engine):
        """Check and update execution status"""
        try:
            context = workflow_engine.get_execution_status(execution_id)
            if not context:
                if hasattr(self, 'execution_timer'):
                    self.execution_timer.stop()
                return
                
            # Update current node status
            if context.current_node_id:
                self.update_node_execution_status(context.current_node_id, "running")
                
            # Update completed nodes with their results
            for node_id, result in context.node_results.items():
                output = result.get('output', '')
                status = result.get('status', 'completed')
                
                # Only update if we have meaningful output or a final status
                if output or status in ['completed', 'error', 'timeout']:
                    self.update_node_execution_status(node_id, status, output)
                    
            # Stop monitoring if workflow is complete
            if hasattr(context, 'status') and context.status.value in ['completed', 'failed', 'stopped']:
                if hasattr(self, 'execution_timer'):
                    self.execution_timer.stop()
                    
        except Exception as e:
            pass
            
    def get_workflow_data(self):
        """Get workflow data for saving/execution"""
        nodes = []
        connections = []
        
        # Convert canvas nodes to service nodes
        for canvas_node in self.nodes:
            try:
                service_node = canvas_node.to_service_node()
                nodes.append(service_node)
            except Exception as e:
                pass
                continue
        
        # Convert canvas connections to service connections  
        for canvas_connection in self.connections:
            try:
                service_connection = canvas_connection.to_service_connection()
                connections.append(service_connection)
            except Exception as e:
                continue  # Skip invalid connections
        
        return {
            'nodes': nodes,
            'connections': connections
        }
        
        
    def validate_workflow(self):
        """Validate current workflow using workflow validator"""
        if not self.workflow_service:
            return False, "Workflow service not available"
            
        workflow_data = self.get_workflow_data()
        if not workflow_data:
            return False, "No workflow data to validate"
            
        try:
            # Basic validation
            if not workflow_data.nodes:
                return False, "Workflow has no nodes"
                
            # Check for start node
            has_start = any(node.node_type == 'start' for node in workflow_data.nodes)
            if not has_start:
                return False, "Workflow must have a start node"
                
            # Check for unreachable nodes
            # TODO: Implement more comprehensive validation
            
            return True, "Workflow validation passed"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
            
    def validate_and_fix_node_colors(self):
        """Validate and fix any nodes with mismatched node types and colors"""
        fixed_count = 0
        
        for node in self.nodes:
            expected_color = self._get_expected_color_for_node_type(node.node_type)
            if expected_color and node.fill_color != expected_color:
                # Store original color for debugging
                original_color = node.fill_color.name() if hasattr(node.fill_color, 'name') else str(node.fill_color)
                
                # Fix the node colors by calling the node's color setting method
                node._set_node_colors()
                fixed_count += 1
                
                # Verify the fix worked
                if node.fill_color != expected_color:
                    # If _set_node_colors didn't work, manually set the color
                    node.fill_color = expected_color
                    # Also ensure border and selected colors are correct
                    node.border_color = expected_color.lighter(150)
                    node.selected_color = expected_color.lighter(200)
                
        # Only trigger repaint if we actually fixed something to avoid unnecessary redraws
        if fixed_count > 0:
            self.update()  # Trigger repaint
            
        return fixed_count
        
    def _get_expected_color_for_node_type(self, node_type: str) -> QColor:
        """Get the expected fill color for a given node type"""
        if node_type == "start":
            return QColor(40, 80, 40)  # Dark green
        elif node_type == "action":
            return QColor(40, 60, 80)  # Dark blue
        elif node_type == "condition":
            return QColor(100, 100, 40)  # Dark yellow
        elif node_type == "end":
            return QColor(80, 40, 40)  # Dark red
        elif node_type == "delay":
            return QColor(60, 40, 80)  # Dark purple
        elif node_type == "set_variable":
            return QColor(80, 60, 40)  # Dark orange
        elif node_type == "file_transfer":
            return QColor(40, 80, 80)  # Dark cyan
        else:
            return QColor(60, 60, 60)  # Dark gray
            
    def debug_node_colors(self):
        """Debug method to print all node types and colors"""
        for i, node in enumerate(self.nodes):
            expected = self._get_expected_color_for_node_type(node.node_type)
            if expected and node.fill_color != expected:
                pass
                
    # --- Streamlined Node Positioning System ---
    
    def _calculate_new_node_position(self, source_node: WorkflowNode, connection_type, template=None) -> QPointF:
        """Calculate optimal position for new node based on connection type"""
        source_pos = QPointF(source_node.x, source_node.y)
        
        # Default spacing
        default_spacing_x = 300
        default_spacing_y = 200  # Increased for better vertical separation
        
        
        if connection_type == ConnectionType.SEQUENTIAL:
            # Sequential connections go right, horizontally aligned
            target_node_type = getattr(template, 'node_type', 'action') if template else 'action'
            
            # Special case: center-align condition nodes with source nodes
            if target_node_type == "condition":
                # Calculate center alignment for condition node (which is larger/square)
                source_center_y = source_pos.y() + source_node.height / 2
                condition_height = max(source_node.width, source_node.height, 120)  # Condition nodes are square
                target_y = source_center_y - condition_height / 2
                
                new_pos = QPointF(
                    source_pos.x() + default_spacing_x,
                    target_y  # Center-aligned Y position
                )
            else:
                # Standard horizontal alignment for other node types
                new_pos = QPointF(
                    source_pos.x() + default_spacing_x,
                    source_pos.y()  # Keep same Y position for horizontal alignment
                )
        elif connection_type == ConnectionType.CONDITIONAL_TRUE:
            # True branch goes right, horizontally aligned
            new_pos = QPointF(
                source_pos.x() + default_spacing_x,
                source_pos.y()  # Keep same Y position for horizontal alignment
            )
        elif connection_type == ConnectionType.CONDITIONAL_FALSE:
            # False branch goes below, vertically aligned (same X, down by spacing + source height)
            new_pos = QPointF(
                source_pos.x(),  # Same X coordinate for vertical alignment
                source_pos.y() + source_node.height + 50  # Down by node height + padding
            )
        else:
            # Default case - go right
            new_pos = QPointF(
                source_pos.x() + default_spacing_x,
                source_pos.y()
            )
        
        # Avoid basic collisions with existing nodes
        final_pos = self._avoid_basic_collisions(new_pos)
        if final_pos != new_pos:
            pass  # Collision avoidance was applied
        
        return final_pos
    
    def _avoid_basic_collisions(self, proposed_pos: QPointF) -> QPointF:
        """Simple collision avoidance - move right if position is occupied"""
        collision_padding = 20
        max_attempts = 10
        
        for attempt in range(max_attempts):
            collision_found = False
            
            for existing_node in self.nodes:
                existing_pos = QPointF(existing_node.x, existing_node.y)
                
                # Check if positions are too close
                dx = abs(proposed_pos.x() - existing_pos.x())
                dy = abs(proposed_pos.y() - existing_pos.y())
                
                min_distance_x = existing_node.width + collision_padding
                min_distance_y = existing_node.height + collision_padding
                
                if dx < min_distance_x and dy < min_distance_y:
                    # Move right to avoid collision
                    collision_found = True
                    proposed_pos = QPointF(
                        existing_pos.x() + min_distance_x,
                        proposed_pos.y()
                    )
                    break
            
            if not collision_found:
                break
                
        return proposed_pos
