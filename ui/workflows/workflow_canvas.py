from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsItem, 
                            QGraphicsRectItem, QGraphicsTextItem, QGraphicsEllipseItem, QMenu,
                            QGraphicsSceneContextMenuEvent)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject
from PyQt6.QtGui import QPen, QBrush, QColor, QPainter, QAction, QPolygonF, QPainterPath, QFont, QLinearGradient

# Guided workflow components are now defined in this file
from services.workflows.node_compatibility import NodeCompatibilityManager
from services.workflows.node_factory import NodeTemplateRegistry, NodeFactory
from services.workflows.node_positioning import NodePositionManager
from services.workflows.connection_features import ConnectionFeatureManager
from services.workflows.performance_manager import WorkflowPerformanceManager


class WorkflowCanvas(QGraphicsView):
    """Canvas for designing workflows with nodes and connections"""
    
    node_selected = pyqtSignal(object)  # Signal when a node is selected
    node_moved = pyqtSignal(object, QPointF)  # Signal when a node is moved
    connection_created = pyqtSignal(object, object)  # Signal when nodes are connected
    node_deletion_requested = pyqtSignal(object)  # Signal when node deletion is requested
    node_parameters_updated = pyqtSignal(object, dict)  # Signal when node parameters are updated
    
    def __init__(self, schema_service=None):
        super().__init__()
        self.schema_service = schema_service
        
        # Initialize guided workflow components
        self.template_registry = NodeTemplateRegistry(schema_service)
        self.compatibility_manager = NodeCompatibilityManager(schema_service, self.template_registry)
        self.node_factory = NodeFactory(self.template_registry, schema_service)
        self.position_manager = NodePositionManager()
        self.connection_feature_manager = ConnectionFeatureManager()
        
        # Initialize performance manager
        self.performance_manager = WorkflowPerformanceManager()
        self.performance_manager.set_canvas(self)
        self.performance_manager.optimize_template_loading(self.template_registry)
        self.performance_manager.optimize_canvas_rendering()
        
        self.setup_canvas()
        self.nodes = []
        self.connections = []
        self.selected_node = None
        
        # Note: Legacy connection mode variables removed - now using guided workflow system
        
    def setup_canvas(self):
        """Initialize the graphics canvas with enhanced features"""
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # Set up canvas properties
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)  # Default to panning
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        
        # Disable drag and drop (using guided creation instead)
        self.setAcceptDrops(False)
        
        # Enable zooming and panning
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Set scene size (large working area)
        self.scene.setSceneRect(-2000, -2000, 4000, 4000)
        
        # Style the canvas
        self.setStyleSheet("""
            QGraphicsView {
                background-color: #2b2b2b;
                border: none;
            }
        """)
        
        # Visual aids for positioning
        self.show_grid = True
        self.show_snap_guides = True
        self.snap_to_grid = True
        
        # Draw grid and guides
        self.draw_enhanced_grid()
        
        # Position preview system
        self.position_preview = None
        
    def draw_enhanced_grid(self):
        """Draw enhanced grid with visual aids"""
        if not self.show_grid:
            return
            
        self._clear_grid_items()
        
        grid_size = self.position_manager.grid_snap_size
        scene_rect = self.scene.sceneRect()
        
        # Create different pen styles for major and minor grid lines
        minor_grid_pen = QPen(QColor(50, 50, 50), 1, Qt.PenStyle.SolidLine)
        major_grid_pen = QPen(QColor(70, 70, 70), 1, Qt.PenStyle.SolidLine)
        
        # Draw vertical lines
        x = scene_rect.left()
        line_count = 0
        while x <= scene_rect.right():
            pen = major_grid_pen if line_count % 4 == 0 else minor_grid_pen
            line = self.scene.addLine(x, scene_rect.top(), x, scene_rect.bottom(), pen)
            line.setZValue(-1000)  # Behind everything
            x += grid_size
            line_count += 1
            
        # Draw horizontal lines
        y = scene_rect.top()
        line_count = 0
        while y <= scene_rect.bottom():
            pen = major_grid_pen if line_count % 4 == 0 else minor_grid_pen
            line = self.scene.addLine(scene_rect.left(), y, scene_rect.right(), y, pen)
            line.setZValue(-1000)  # Behind everything
            y += grid_size
            line_count += 1
            
    def _clear_grid_items(self):
        """Clear existing grid items"""
        # Remove all grid lines (items with very low z-value)
        for item in self.scene.items():
            if hasattr(item, 'zValue') and item.zValue() <= -1000:
                self.scene.removeItem(item)
                
    def draw_grid(self):
        """Legacy grid drawing method - redirects to enhanced version"""
        self.draw_enhanced_grid()
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming"""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        
        # Set up zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
            
        self.scale(zoom_factor, zoom_factor)
        
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        # Check for shift modifier to enable selection mode
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            
            # Handle ActionPoint clicks (these show connection menus)
            if isinstance(item, ActionPoint):
                # Check if this action point can actually create connections
                if item.parent_node.has_connections_from_action_point(item.point_type):
                    # Action point already has connections - treat as node selection instead
                    self.select_node(item.parent_node)
                    return
                else:
                    # Let the ActionPoint handle its own click event first
                    super().mousePressEvent(event)
                    return
            elif isinstance(item, GuidedWorkflowNode):
                self.select_node(item)
            else:
                self.clear_selection()
                
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        # Reset to panning mode after release
        if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mouseReleaseEvent(event)
        
    def add_node(self, node_type: str, position: QPointF, module_info: dict = None):
        """Add a new node to the canvas using guided system"""
        # Get template for this node type
        template = self.template_registry.get_template(node_type)
        
        # Create guided workflow node
        node = GuidedWorkflowNode(node_type, template, module_info)
        node.setPos(position)
        
        # Connect node signals
        node.signals.position_changed.connect(self._on_node_position_changed)
        node.signals.connection_requested.connect(self._on_connection_requested)
        
        self.scene.addItem(node)
        self.nodes.append(node)
        return node
        
    def add_node_from_template(self, template, position: QPointF = None, 
                              connection_context=None):
        """Add a node from a template with auto-positioning"""
        if position is None:
            # Use center of view as default
            view_center = self.viewport().rect().center()
            position = self.mapToScene(view_center)
            
        # Create node data using factory
        node_data = self.node_factory.create_node_from_template(
            template, position, connection_context
        )
        
        # Create the actual node widget
        node = GuidedWorkflowNode(template.node_type, template, node_data.get("module_info", {}))
        node.node_id = node_data["node_id"]
        node.parameters = node_data["parameters"].copy()
        node.setPos(QPointF(node_data["position"]["x"], node_data["position"]["y"]))
        
        # Connect signals
        node.signals.position_changed.connect(self._on_node_position_changed)
        node.signals.connection_requested.connect(self._on_connection_requested)
        
        self.scene.addItem(node)
        self.nodes.append(node)
        return node
        
    def remove_node(self, node):
        """Remove a node from the canvas"""
        if node in self.nodes:
            self.nodes.remove(node)
            self.scene.removeItem(node)
            
    def remove_connection(self, connection):
        """Remove a connection from the canvas"""
        if connection in self.connections:
            self.connections.remove(connection)
            self.scene.removeItem(connection)
            # Cleanup connection from nodes
            connection.cleanup()
            
    def select_node(self, node):
        """Select a node and emit signal"""
        if self.selected_node:
            self.selected_node.set_selected(False)
            
        self.selected_node = node
        node.set_selected(True)
        self.node_selected.emit(node)
        
    def clear_selection(self):
        """Clear node selection"""
        if self.selected_node:
            self.selected_node.set_selected(False)
            self.selected_node = None
            self.node_selected.emit(None)
            
    def _on_node_position_changed(self, node):
        """Handle node position changes"""
        # Update any connections involving this node
        for connection in self.connections:
            if connection.start_node == node or connection.end_node == node:
                connection.update_position()
                
    def _on_connection_requested(self, source_node, action_point, template):
        """Handle connection requests from action points with template"""
        if not template:
            print("No template provided for connection")
            return
            
        try:
            # Calculate position for new node
            existing_node_data = [{"position": {"x": node.scenePos().x(), "y": node.scenePos().y()}, 
                                  "node_type": node.node_type} for node in self.nodes]
            
            position = self.position_manager.calculate_next_position(
                {"position": {"x": source_node.scenePos().x(), "y": source_node.scenePos().y()},
                 "node_type": source_node.node_type},
                action_point.connection_type,
                template,
                existing_node_data
            )
            
            # Create connection context
            from services.workflows.node_factory import ConnectionContext
            connection_context = ConnectionContext(
                source_node_type=source_node.node_type,
                source_node_id=source_node.node_id,
                connection_type=action_point.connection_type,
                source_output_data=source_node.parameters.copy()
            )
            
            # Create the new node using template
            new_node = self.add_node_from_template(template, position, connection_context)
            
            # Create connection between nodes
            connection = GuidedWorkflowConnection(source_node, new_node, action_point.connection_type)
            self.scene.addItem(connection)
            self.connections.append(connection)
            
            # Register connection with nodes
            source_node.add_connection(connection)
            new_node.add_connection(connection)
            
            # Emit signal for external handling
            self.connection_created.emit(source_node, new_node)
            
            print(f"Created connection: {source_node.node_type} -> {new_node.node_type} ({template.display_name}) via {action_point.connection_type.value}")
            
        except Exception as e:
            print(f"Error creating connection: {e}")
            import traceback
            traceback.print_exc()
            
    def show_position_preview(self, source_node, connection_type, template):
        """Show a preview of where the new node will be placed"""
        try:
            # Calculate preview position
            existing_node_data = [{"position": {"x": node.scenePos().x(), "y": node.scenePos().y()}, 
                                  "node_type": node.node_type} for node in self.nodes]
            
            preview_position = self.position_manager.calculate_next_position(
                {"position": {"x": source_node.scenePos().x(), "y": source_node.scenePos().y()},
                 "node_type": source_node.node_type},
                connection_type,
                template,
                existing_node_data
            )
            
            # Remove existing preview
            self.clear_position_preview()
            
            # Create preview node
            self.position_preview = PositionPreviewItem(preview_position, template)
            self.scene.addItem(self.position_preview)
            
        except Exception as e:
            print(f"Error showing position preview: {e}")
            
    def clear_position_preview(self):
        """Clear the position preview"""
        if self.position_preview:
            self.scene.removeItem(self.position_preview)
            self.position_preview = None
            
    def add_snap_guides(self, moving_node):
        """Add visual snap guides when moving nodes"""
        if not self.show_snap_guides:
            return
            
        # Clear existing guides
        self.clear_snap_guides()
        
        moving_pos = moving_node.scenePos()
        guides = []
        
        # Find nearby nodes for alignment
        for node in self.nodes:
            if node == moving_node:
                continue
                
            node_pos = node.scenePos()
            
            # Vertical alignment guide
            if abs(moving_pos.x() - node_pos.x()) < 20:
                guide = self.scene.addLine(
                    node_pos.x(), -2000, node_pos.x(), 2000,
                    QPen(QColor(100, 150, 255, 150), 2, Qt.PenStyle.DashLine)
                )
                guide.setZValue(-500)
                guides.append(guide)
                
            # Horizontal alignment guide
            if abs(moving_pos.y() - node_pos.y()) < 20:
                guide = self.scene.addLine(
                    -2000, node_pos.y(), 2000, node_pos.y(),
                    QPen(QColor(100, 150, 255, 150), 2, Qt.PenStyle.DashLine)
                )
                guide.setZValue(-500)
                guides.append(guide)
                
        self.snap_guides = guides
        
    def clear_snap_guides(self):
        """Clear snap guides"""
        if hasattr(self, 'snap_guides'):
            for guide in self.snap_guides:
                self.scene.removeItem(guide)
            self.snap_guides = []
            
    def zoom_in(self):
        """Zoom in on the canvas"""
        self.scale(1.25, 1.25)
        
    def zoom_out(self):
        """Zoom out on the canvas"""
        self.scale(0.8, 0.8)
        
    def reset_zoom(self):
        """Reset zoom to 100%"""
        self.resetTransform()
        
    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        super().mouseMoveEvent(event)
        
    def contextMenuEvent(self, event):
        """Handle right-click context menu"""
        item = self.itemAt(event.pos())
        if isinstance(item, GuidedWorkflowNode):
            self.show_node_context_menu(item, event.globalPos())
        else:
            super().contextMenuEvent(event)
            
    def show_node_context_menu(self, node, global_pos):
        """Show context menu for a node"""
        menu = QMenu()
        
        # Edit action
        edit_action = QAction("Edit Node", menu)
        edit_action.triggered.connect(lambda: self.edit_node(node))
        menu.addAction(edit_action)
        
        # Configure connections action (if node has connections)
        if hasattr(node, 'connections') and node.connections:
            menu.addSeparator()
            configure_connections_action = QAction("Configure Connections", menu)
            configure_connections_action.triggered.connect(lambda: self.configure_node_connections(node))
            menu.addAction(configure_connections_action)
        
        menu.addSeparator()
        
        # Delete action
        delete_action = QAction("Delete Node", menu)
        delete_action.triggered.connect(lambda: self.delete_node(node))
        menu.addAction(delete_action)
        
        # Show menu
        menu.exec(global_pos)
        
    def configure_node_connections(self, node):
        """Open connection configuration for a node"""
        from .connection_config_dialog import ConnectionConfigDialog
        
        # For demo, configure first connection
        if hasattr(node, 'connections') and node.connections:
            connection = node.connections[0]
            target_node = connection.end_node if connection.start_node == node else connection.start_node
            
            dialog = ConnectionConfigDialog(node, target_node, self.connection_feature_manager, self)
            dialog.connection_configured.connect(self.on_connection_configured)
            dialog.exec()
            
    def on_connection_configured(self, config):
        """Handle connection configuration updates"""
        print(f"Connection configured with: {config}")
        # Update connection with new configuration
        
    def edit_node(self, node):
        """Edit a node using the parameter dialog"""
        from .node_parameter_dialog import NodeParameterDialog
        from services import SchemaService
        from services.workflows.execution_types import ExecutionContext
        
        # Use injected schema service or create new one
        schema_service = self.schema_service or SchemaService()
        
        # Create workflow context for template variables
        workflow_context = self._create_workflow_context(node)
        
        dialog = NodeParameterDialog(node, schema_service, self.template_registry, 
                                   workflow_context, self)
        dialog.parameters_updated.connect(lambda params: self.on_node_parameters_updated(node, params))
        dialog.exec()
        
    def _create_workflow_context(self, node):
        """Create workflow context for template variable support"""
        # Create a minimal execution context for template variable discovery
        from services.workflows.execution_types import ExecutionContext
        
        context = ExecutionContext(
            workflow_id="editor_context",
            beacon_id="editor",
            variables={},
            node_results={},
            execution_log=[],
            status=None
        )
        
        # Get workflow connections for this canvas
        workflow_connections = []
        for connection in self.connections:
            # Convert GuidedWorkflowConnection to WorkflowConnection for template engine
            from services.workflows.workflow_service import WorkflowConnection
            wf_connection = WorkflowConnection(
                connection_id=f"conn_{id(connection)}",
                source_node_id=connection.start_node.node_id,
                target_node_id=connection.end_node.node_id,
                connection_type=connection.connection_type.value if hasattr(connection.connection_type, 'value') else str(connection.connection_type)
            )
            workflow_connections.append(wf_connection)
        
        return {
            'context': context,
            'current_node': node,
            'workflow_connections': workflow_connections
        }
        
    def on_node_parameters_updated(self, node, parameters):
        """Handle node parameter updates"""
        print(f"Parameters updated for {node.node_type}: {parameters}")
        # Update node parameters
        node.parameters.update(parameters)
        # Update parameter display for action nodes
        if hasattr(node, 'update_parameter_display'):
            node.update_parameter_display()
        # Emit signal for external components to handle
        self.node_parameters_updated.emit(node, parameters)
        # Trigger properties panel update if this node is selected
        if self.selected_node == node:
            self.node_selected.emit(node)
        
    def delete_node(self, node):
        """Delete a node and its connections"""
        print(f"Delete node: {node.node_type}")
        
        # Collect all nodes that were connected to this node before deletion
        connected_nodes = set()
        connections_to_remove = [conn for conn in self.connections if conn.start_node == node or conn.end_node == node]
        
        for connection in connections_to_remove:
            # Track nodes that were connected to the node being deleted
            if connection.start_node == node:
                connected_nodes.add(connection.end_node)
            if connection.end_node == node:
                connected_nodes.add(connection.start_node)
            
        # Remove all connections involving this node
        for connection in connections_to_remove:
            self.remove_connection(connection)
            
        # Refresh action points on all nodes that were connected to the deleted node
        for connected_node in connected_nodes:
            if hasattr(connected_node, 'refresh_action_points'):
                connected_node.refresh_action_points()
                print(f"Refreshed action points for {connected_node.node_type} after deleting {node.node_type}")
            
        self.remove_node(node)
        self.node_deletion_requested.emit(node)
        
    def update_node_execution_status(self, node_id: str, status: str, output: str = ""):
        """Update a node's execution status and output"""
        for node in self.nodes:
            if hasattr(node, 'node_id') and node.node_id == node_id:
                print(f"Found node {node_id} in canvas, updating with status '{status}' and output: '{output[:50]}...'")
                if hasattr(node, 'update_output_display'):
                    node.update_output_display(output, status)
                    print(f"Successfully updated output display for node {node_id}")
                else:
                    print(f"Node {node_id} does not have update_output_display method")
                break
        else:
            print(f"Node {node_id} not found in canvas nodes list")
                
    def monitor_workflow_execution(self, execution_id: str, workflow_engine):
        """Start monitoring workflow execution and update nodes in real-time"""
        from PyQt6.QtCore import QTimer
        
        # Store for callback triggering
        self.current_execution_id = execution_id
        self.workflow_engine = workflow_engine
        
        # Create a timer to poll execution status
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(
            lambda: self._check_execution_status(execution_id, workflow_engine)
        )
        self.execution_timer.start(1000)  # Check every second
        
    def _check_execution_status(self, execution_id: str, workflow_engine):
        """Check and update execution status"""
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
            
            # Debug logging
            print(f"Canvas updating node {node_id} with status '{status}' and output length: {len(output)}")
            
            # Only update if we have meaningful output or a final status
            if output or status in ['completed', 'error', 'timeout']:
                self.update_node_execution_status(node_id, status, output)
            
        # Stop monitoring if workflow is complete
        if context.status.value in ['completed', 'failed', 'stopped']:
            print(f"Workflow {execution_id} completed with status: {context.status.value}")
            
            # Manually trigger workflow engine callbacks since they're not being called
            print(f"Manually triggering workflow engine callbacks for {execution_id}")
            workflow_engine._notify_execution_callbacks(execution_id, context)
            
            if hasattr(self, 'execution_timer'):
                self.execution_timer.stop()

    def clear_canvas(self):
        """Clear all nodes and connections from the canvas"""
        # Stop any active execution monitoring
        if hasattr(self, 'execution_timer'):
            self.execution_timer.stop()
            
        # Clear connections first
        for connection in self.connections[:]:
            self.scene.removeItem(connection)
        self.connections.clear()
        
        # Clear nodes
        for node in self.nodes[:]:
            self.scene.removeItem(node)
        self.nodes.clear()
        
        # Clear selection
        self.clear_selection()


class ActionPointSignals(QObject):
    """Signal handler for ActionPoint"""
    connection_requested = pyqtSignal(object, object)  # ActionPoint, ConnectionOption


class ActionPoint(QGraphicsEllipseItem):
    """Interactive + button that shows connection options"""
    
    def __init__(self, parent_node, point_type: str, position: str, 
                 connection_type, label: str = ""):
        super().__init__()
        self.signals = ActionPointSignals()
        self.parent_node = parent_node
        self.point_type = point_type      # "output", "conditional_output", "error_output"
        self.position = position          # "right", "bottom_0", "bottom_right", etc.
        self.connection_type = connection_type
        self.label = label
        self.is_hovered = False
        
        # Set up appearance - larger for easier clicking
        self.setRect(-12, -12, 24, 24)
        
        # Style based on connection type
        self._update_appearance()
        
        # Enable mouse interaction
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Make it a child of the parent node
        self.setParentItem(parent_node)
        
        # Position the action point relative to parent
        self._position_on_parent()
        
        # Create label if provided
        if label:
            self.label_item = QGraphicsTextItem(label, self)
            self.label_item.setFont(QFont("Arial", 8))
            self.label_item.setDefaultTextColor(QColor(255, 255, 255))
            # Disable mouse interaction so events pass through to parent
            self.label_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self.label_item.setAcceptHoverEvents(False)
            self._position_label()
        else:
            self.label_item = None
            
    def _update_appearance(self):
        """Update visual appearance based on connection type"""
        from services.workflows.node_compatibility import ConnectionType
        
        if self.connection_type == ConnectionType.SEQUENTIAL:
            color = QColor(100, 150, 255)  # Blue
            self.setToolTip("Add next step")
        elif self.connection_type == ConnectionType.CONDITIONAL_TRUE:
            color = QColor(100, 255, 100)  # Green  
            self.setToolTip("Add step for true condition")
        elif self.connection_type == ConnectionType.CONDITIONAL_FALSE:
            color = QColor(255, 100, 100)  # Red
            self.setToolTip("Add step for false condition")
        else:
            color = QColor(150, 150, 150)  # Gray
            self.setToolTip("Add connection")
            
        if self.is_hovered:
            color = color.lighter(150)
            pen = QPen(QColor(255, 255, 255), 3)
        else:
            pen = QPen(QColor(0, 0, 0), 2)
            
        self.setBrush(QBrush(color))
        self.setPen(pen)
        
    def _position_on_parent(self):
        """Position the action point on the parent node"""
        parent_rect = self.parent_node.rect()
        
        if self.position == "right":
            # Right side, middle
            self.setPos(parent_rect.width(), parent_rect.height() / 2)
        elif self.position.startswith("bottom"):
            if self.position == "bottom_0":
                # Bottom left for first conditional
                self.setPos(parent_rect.width() * 0.3, parent_rect.height())
            elif self.position == "bottom_1": 
                # Bottom right for second conditional
                self.setPos(parent_rect.width() * 0.7, parent_rect.height())
            elif self.position == "bottom_right":
                # Bottom right corner for error
                self.setPos(parent_rect.width(), parent_rect.height())
            else:
                # Default bottom center
                self.setPos(parent_rect.width() / 2, parent_rect.height())
        else:
            # Default to right side
            self.setPos(parent_rect.width(), parent_rect.height() / 2)
            
    def _position_label(self):
        """Position the label relative to the action point"""
        if not self.label_item:
            return
            
        label_rect = self.label_item.boundingRect()
        
        # Position label based on action point position
        if self.position == "right":
            # Label above and to the right
            self.label_item.setPos(15, -label_rect.height() / 2)
        elif self.position.startswith("bottom"):
            # Label below
            self.label_item.setPos(-label_rect.width() / 2, 15)
        else:
            # Default position
            self.label_item.setPos(15, -label_rect.height() / 2)
            
    def mousePressEvent(self, event):
        """Show connection menu on click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.show_connection_menu()
        super().mousePressEvent(event)
        
    def contextMenuEvent(self, event):
        """Pass context menu events to parent node"""
        # Don't handle context menu events ourselves - pass to parent
        if self.parent_node:
            # Convert event position to parent coordinates and forward
            parent_event = QGraphicsSceneContextMenuEvent()
            parent_event.setPos(self.mapToParent(event.pos()))
            parent_event.setScenePos(event.scenePos())
            parent_event.setScreenPos(event.screenPos())
            parent_event.setModifiers(event.modifiers())
            parent_event.setReason(event.reason())
            self.parent_node.contextMenuEvent(parent_event)
        else:
            super().contextMenuEvent(event)
        
    def show_connection_menu(self):
        """Show enhanced connection menu with templates"""
        # Import here to avoid circular dependency
        try:
            from .connection_menu import ConnectionMenu
        except ImportError:
            print("Could not import ConnectionMenu - using fallback")
            self.signals.connection_requested.emit(self, None)
            return
        
        # Get compatibility manager and template registry from parent canvas
        canvas = self._find_parent_canvas()
        if not canvas or not hasattr(canvas, 'compatibility_manager'):
            print("Canvas or compatibility manager not found")
            self.signals.connection_requested.emit(self, None)
            return
            
        try:
            # Create enhanced connection menu
            menu = ConnectionMenu(
                self.parent_node,
                self,
                canvas.compatibility_manager,
                canvas.template_registry
            )
            
            # Connect the template selection signal
            menu.connection_option_selected.connect(
                lambda template: self.signals.connection_requested.emit(self, template)
            )
            
            # Calculate global position for menu
            action_point_pos = self.scenePos()
            scene_to_view = self.scene().views()[0].mapFromScene(action_point_pos)
            global_pos = self.scene().views()[0].mapToGlobal(scene_to_view)
            
            # Show menu
            menu.exec(global_pos)
            
        except Exception as e:
            print(f"Error showing connection menu: {e}")
            import traceback
            traceback.print_exc()
            # Fallback - emit signal without template
            self.signals.connection_requested.emit(self, None)
                
    def _find_parent_canvas(self):
        """Find the parent canvas widget"""
        if self.scene() and self.scene().views():
            return self.scene().views()[0]
        return None
        
    def hoverEnterEvent(self, event):
        """Handle hover enter"""
        self.is_hovered = True
        self._update_appearance()
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave"""
        self.is_hovered = False
        self._update_appearance()
        super().hoverLeaveEvent(event)
        
    def paint(self, painter, option, widget):
        """Custom paint to draw + symbol"""
        super().paint(painter, option, widget)
        
        # Draw + symbol in center
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        rect = self.rect()
        center = rect.center()
        
        # Horizontal line
        painter.drawLine(
            QPointF(center.x() - 6, center.y()),
            QPointF(center.x() + 6, center.y())
        )
        
        # Vertical line  
        painter.drawLine(
            QPointF(center.x(), center.y() - 6),
            QPointF(center.x(), center.y() + 6)
        )


class GuidedWorkflowNodeSignals(QObject):
    """Signal handler for GuidedWorkflowNode"""
    position_changed = pyqtSignal(object)
    connection_requested = pyqtSignal(object, object, object)  # node, action_point, connection_option


class GuidedWorkflowNode(QGraphicsRectItem):
    """Enhanced workflow node with guided connection points"""
    
    def __init__(self, node_type: str, template=None, module_info: dict = None):
        super().__init__()
        self.signals = GuidedWorkflowNodeSignals()
        self.node_type = node_type
        self.template = template
        self.module_info = module_info or {}
        self.node_id = f"{node_type}_{id(self)}"
        self.is_selected = False
        self.parameters = {}
        self.connections = []
        self.action_points = {}
        self.detail_level = "high"  # For performance optimization
        
        # Node appearance - variable size based on node type
        if self.node_type == 'action' or self.node_type.startswith('schema_') or self.node_type.startswith('action_'):
            # Action nodes are larger to show parameters and output
            self.setRect(0, 0, 200, 140)
        else:
            # Standard size for other nodes
            self.setRect(0, 0, 140, 90)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                     QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                     QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        # Create node label
        self.label = QGraphicsTextItem(self.get_display_name(), self)
        self.label.setPos(10, 10)
        # Disable mouse interaction so events pass through to parent
        self.label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.label.setAcceptHoverEvents(False)
        
        # Create parameter and output display for action nodes
        self.parameter_display = None
        self.output_display = None
        self.execution_status = None
        
        if self.node_type == 'action' or self.node_type.startswith('schema_') or self.node_type.startswith('action_'):
            self.setup_action_node_display()
        
        # Set up action points based on template
        self.setup_action_points()
        
        self.update_appearance()
        
        # Ensure node is selectable and interactive
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        
    def setup_action_node_display(self):
        """Set up parameter and output display for action nodes"""
        # Parameters section with improved readability
        self.parameter_display = QGraphicsTextItem("Parameters:\n(not configured)", self)
        self.parameter_display.setPos(10, 35)
        self.parameter_display.setTextWidth(180)
        param_font = QFont("Arial", 9, QFont.Weight.Bold)
        self.parameter_display.setFont(param_font)
        self.parameter_display.setDefaultTextColor(QColor(50, 50, 50))  # Dark text for better contrast
        # Disable mouse interaction so events pass through to parent
        self.parameter_display.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.parameter_display.setAcceptHoverEvents(False)
        
        # Output section with improved readability
        self.output_display = QGraphicsTextItem("Output:\n(pending execution)", self)
        self.output_display.setPos(10, 85)
        self.output_display.setTextWidth(180)
        output_font = QFont("Consolas", 8)  # Monospace font for output
        self.output_display.setFont(output_font)
        self.output_display.setDefaultTextColor(QColor(80, 80, 80))  # Slightly lighter for output
        # Disable mouse interaction so events pass through to parent
        self.output_display.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.output_display.setAcceptHoverEvents(False)
        
        # Update parameter display if parameters exist
        self.update_parameter_display()
        
    def update_parameter_display(self):
        """Update the parameter display with current parameters"""
        if not self.parameter_display:
            return
            
        if self.parameters:
            # Show key parameters (filter out workflow-specific ones)
            display_params = {k: v for k, v in self.parameters.items() 
                            if k not in {'schema_file', 'category', 'module'} and v}
            
            if display_params:
                param_text = "Parameters:\n"
                for key, value in list(display_params.items())[:3]:  # Show max 3 params
                    param_text += f"• {key}: {str(value)[:20]}{'...' if len(str(value)) > 20 else ''}\n"
                if len(display_params) > 3:
                    param_text += f"...and {len(display_params) - 3} more"
            else:
                param_text = "Parameters:\n(using defaults)"
        else:
            param_text = "Parameters:\n(not configured)"
            
        self.parameter_display.setPlainText(param_text)
        
    def update_output_display(self, output: str, status: str = "completed"):
        """Update the output display with execution results"""
        if not self.output_display:
            return
            
        if output:
            # Improved text truncation with word wrapping
            max_chars = 200  # Increased limit
            if len(output) > max_chars:
                # Try to break at word boundaries
                truncated = output[:max_chars]
                last_space = truncated.rfind(' ')
                if last_space > max_chars - 50:  # If space is reasonably close to end
                    truncated = truncated[:last_space]
                display_output = truncated + "..."
            else:
                display_output = output
            
            # Format with better line breaks
            lines = display_output.split('\n')
            if len(lines) > 4:  # Limit to 4 lines
                display_output = '\n'.join(lines[:4]) + '\n...'
                
            output_text = f"Output ({status}):\n{display_output}"
        else:
            output_text = f"Output:\n({status})"
            
        self.output_display.setPlainText(output_text)
        
        # Improved color scheme with better contrast
        if status == "completed":
            self.output_display.setDefaultTextColor(QColor(34, 139, 34))  # Forest green
        elif status == "error" or status == "failed":
            self.output_display.setDefaultTextColor(QColor(178, 34, 34))  # Dark red
        elif status == "running":
            self.output_display.setDefaultTextColor(QColor(255, 140, 0))  # Orange
        else:
            self.output_display.setDefaultTextColor(QColor(80, 80, 80))  # Dark gray

    def get_display_name(self):
        """Get the display name for this node"""
        if self.template and hasattr(self.template, 'display_name'):
            return self.template.display_name
        elif self.module_info and 'display_name' in self.module_info:
            return self.module_info['display_name']
        return self.node_type.replace('_', ' ').title()
        
    def setup_action_points(self):
        """Create action points based on template or node type"""
        if self.template:
            action_point_configs = self.template.get_action_points()
        else:
            # Default action points for nodes without templates
            action_point_configs = self._get_default_action_points()
            
        for config in action_point_configs:
            # Skip creating action points that already have connections
            if self.has_connections_from_action_point(config["type"]):
                continue
                
            action_point = ActionPoint(
                self,
                config["type"],
                config["position"],
                config["connection_type"],
                config.get("label", "")
            )
            
            # Connect signals
            action_point.signals.connection_requested.connect(
                lambda ap, co: self.signals.connection_requested.emit(self, ap, co)
            )
            
            self.action_points[config["type"]] = action_point
            
    def _get_default_action_points(self):
        """Get default action points for nodes without templates"""
        from services.workflows.node_compatibility import ConnectionType
        
        if self.node_type == "start":
            return [{
                "type": "output",
                "position": "right", 
                "connection_type": ConnectionType.SEQUENTIAL,
                "label": "Start"
            }]
        elif self.node_type == "end":
            return []  # End nodes don't have outputs
        elif self.node_type == "condition":
            return [
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
            ]
        else:
            # Default nodes have only output (removed error connection)
            return [
                {
                    "type": "output",
                    "position": "right",
                    "connection_type": ConnectionType.SEQUENTIAL,
                    "label": "Next"
                }
            ]
            
    def set_selected(self, selected: bool):
        """Update node selection state"""
        self.is_selected = selected
        self.update_appearance()
        
        # Show/hide action points based on selection
        self._toggle_action_points_visibility(selected)
        
    def _toggle_action_points_visibility(self, visible: bool):
        """Show or hide action points"""
        for action_point in self.action_points.values():
            action_point.setVisible(visible)
            if action_point.label_item:
                action_point.label_item.setVisible(visible)
                
    def update_appearance(self):
        """Update node visual appearance based on type and state"""
        if self.node_type == "start":
            color = QColor(76, 175, 80)  # Green
        elif self.node_type == "end":
            color = QColor(244, 67, 54)  # Red  
        elif self.node_type == "condition":
            color = QColor(255, 193, 7)  # Yellow
        else:
            color = QColor(33, 150, 243)  # Blue
            
        if self.is_selected:
            pen = QPen(QColor(255, 255, 255), 3)
            color = color.lighter(120)
        else:
            pen = QPen(QColor(0, 0, 0), 2)
            
        brush = QBrush(color)
        self.setPen(pen)
        self.setBrush(brush)
        
        # Update label color
        if self.is_selected:
            self.label.setDefaultTextColor(QColor(255, 255, 255))
        else:
            self.label.setDefaultTextColor(QColor(0, 0, 0))
            
    def itemChange(self, change, value):
        """Handle item changes, especially position changes"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            self.signals.position_changed.emit(self)
        return super().itemChange(change, value)
        
    def paint(self, painter, option, widget):
        """Custom paint method for rounded rectangles and improved styling"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get current colors from update_appearance
        pen = self.pen()
        brush = self.brush()
        
        # Calculate corner radius based on node type
        if self.node_type in ["start", "end"]:
            corner_radius = 15  # More rounded for start/end nodes
        else:
            corner_radius = 8   # Slightly rounded for action nodes
            
        rect = self.rect()
        
        # Draw drop shadow for depth
        shadow_offset = 2
        shadow_rect = rect.adjusted(shadow_offset, shadow_offset, shadow_offset, shadow_offset)
        shadow_color = QColor(0, 0, 0, 50)  # Semi-transparent black
        painter.setBrush(QBrush(shadow_color))
        painter.setPen(QPen(shadow_color, 0))
        painter.drawRoundedRect(shadow_rect, corner_radius, corner_radius)
        
        # Draw main node with gradient
        if brush.color().isValid():
            # Create subtle gradient
            gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
            base_color = brush.color()
            gradient.setColorAt(0, base_color.lighter(110))
            gradient.setColorAt(1, base_color.darker(110))
            painter.setBrush(QBrush(gradient))
        else:
            painter.setBrush(brush)
            
        painter.setPen(pen)
        painter.drawRoundedRect(rect, corner_radius, corner_radius)
        
    def add_connection(self, connection):
        """Add a connection that involves this node"""
        if connection not in self.connections:
            self.connections.append(connection)
            # Only refresh action points if this is an outgoing connection
            if connection.start_node == self:
                self.refresh_action_points()
            
    def remove_connection(self, connection):
        """Remove a connection that involves this node"""
        if connection in self.connections:
            self.connections.remove(connection)
            # Only refresh action points if this was an outgoing connection
            if connection.start_node == self:
                self.refresh_action_points()
            
    def refresh_action_points(self):
        """Refresh action points based on current connections"""
        # Store current selection state and interaction flags
        was_selected = self.is_selected
        interaction_flags = self.flags()
        
        # Clear existing action points properly
        for action_point in self.action_points.values():
            # Remove from parent first to maintain hierarchy
            action_point.setParentItem(None)
            if action_point.scene():
                action_point.scene().removeItem(action_point)
        self.action_points.clear()
        
        # Recreate action points
        self.setup_action_points()
        
        # Restore interaction flags to preserve event handling
        self.setFlags(interaction_flags)
        
        # Restore visibility based on selection state
        if was_selected:
            self._toggle_action_points_visibility(True)
            
        # Ensure Z-order is preserved for proper event handling
        self.setZValue(self.zValue())
            
    def get_action_point(self, point_type: str):
        """Get action point by type"""
        return self.action_points.get(point_type)
        
    def has_connections_from_action_point(self, action_point_type: str) -> bool:
        """Check if this action point already has connections"""
        # Check if this node has any outgoing connections for the given action point type
        for connection in self.connections:
            if connection.start_node == self:
                # This is an outgoing connection from this node
                if hasattr(connection, 'connection_type') and action_point_type == "output":
                    # For "output" action points, check for sequential connections
                    from services.workflows.node_compatibility import ConnectionType
                    if connection.connection_type == ConnectionType.SEQUENTIAL:
                        return True
        return False
        
    def set_detail_level(self, level: str):
        """Set detail level for performance optimization"""
        self.detail_level = level
        
        if level == "low":
            # Hide action points and detailed labels when zoomed out
            for action_point in self.action_points.values():
                action_point.setVisible(False)
            # Use simplified label
            if hasattr(self, 'label'):
                self.label.setPlainText(self.node_type[:3].upper())
                
        elif level == "medium":
            # Show some details but simplified
            for action_point in self.action_points.values():
                action_point.setVisible(self.is_selected)
            if hasattr(self, 'label'):
                self.label.setPlainText(self.get_display_name()[:10])
                
        else:  # high detail
            # Show all details
            for action_point in self.action_points.values():
                action_point.setVisible(self.is_selected)
            if hasattr(self, 'label'):
                self.label.setPlainText(self.get_display_name())
                
        self.update()


class GuidedWorkflowConnection(QGraphicsItem):
    """Enhanced connection line for guided workflow system"""
    
    def __init__(self, start_node, end_node, connection_type):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.connection_type = connection_type
        self.connection_id = f"guided_conn_{id(self)}"
        
        # Connect to node position change signals
        if hasattr(start_node, 'signals'):
            self.start_node.signals.position_changed.connect(self.update_position)
        if hasattr(end_node, 'signals'):
            self.end_node.signals.position_changed.connect(self.update_position)
        
        # Register this connection with both nodes
        self.start_node.add_connection(self)
        self.end_node.add_connection(self)
        
    def update_position(self):
        """Update connection position when nodes move"""
        self.prepareGeometryChange()
        self.update()
        
    def boundingRect(self):
        """Return the bounding rectangle for this connection"""
        start_pos = self.start_node.scenePos()
        end_pos = self.end_node.scenePos()
        
        # Calculate connection points based on connection type
        start_point, end_point = self._get_connection_points()
        
        # Calculate bounding rectangle with padding
        padding = 15
        left = min(start_point.x(), end_point.x()) - padding
        top = min(start_point.y(), end_point.y()) - padding
        width = abs(end_point.x() - start_point.x()) + 2 * padding
        height = abs(end_point.y() - start_point.y()) + 2 * padding
        
        self.setPos(left, top)
        return QRectF(0, 0, width, height)
        
    def _get_connection_points(self):
        """Get the actual connection points based on connection type and node sizes"""
        start_pos = self.start_node.scenePos()
        end_pos = self.end_node.scenePos()
        
        # Get node dimensions
        start_rect = self.start_node.rect()
        end_rect = self.end_node.rect()
        
        # Start point (varies by connection type)
        if self.connection_type.value == "sequential":
            start_point = start_pos + QPointF(start_rect.width(), start_rect.height() / 2)  # Right side center
        elif self.connection_type.value in ["conditional_true", "conditional_false"]:
            # Bottom connections for conditionals
            if self.connection_type.value == "conditional_true":
                start_point = start_pos + QPointF(start_rect.width() * 0.3, start_rect.height())  # Bottom left
            else:
                start_point = start_pos + QPointF(start_rect.width() * 0.7, start_rect.height())  # Bottom right
        elif self.connection_type.value == "error":
            start_point = start_pos + QPointF(start_rect.width(), start_rect.height())  # Bottom right corner
        else:
            start_point = start_pos + QPointF(start_rect.width(), start_rect.height() / 2)  # Default to right side
            
        # End point (always left side center for input)
        end_point = end_pos + QPointF(0, end_rect.height() / 2)
        
        return start_point, end_point
        
    def paint(self, painter, option, widget):
        """Paint the connection line with styling based on type"""
        start_point, end_point = self._get_connection_points()
        
        # Convert to local coordinates
        item_pos = self.pos()
        start_local = QPointF(start_point.x() - item_pos.x(), start_point.y() - item_pos.y())
        end_local = QPointF(end_point.x() - item_pos.x(), end_point.y() - item_pos.y())
        
        # Choose color and style based on connection type
        if self.connection_type.value == "sequential":
            color = QColor(100, 150, 255)  # Blue
            width = 2
        elif self.connection_type.value == "conditional_true":
            color = QColor(100, 255, 100)  # Green
            width = 2
        elif self.connection_type.value == "conditional_false":
            color = QColor(255, 100, 100)  # Red
            width = 2
        else:
            color = QColor(200, 200, 200)  # Gray
            width = 2
            
        painter.setPen(QPen(color, width))
        
        # Draw curved line for better visual appeal
        self._draw_curved_line(painter, start_local, end_local)
        
        # Draw arrow head
        self._draw_arrow_head(painter, start_local, end_local, color)
        
    def _draw_curved_line(self, painter, start, end):
        """Draw a curved line between points"""
        # Create a bezier curve
        path = QPainterPath()
        path.moveTo(start)
        
        # Calculate control points for curve
        dx = end.x() - start.x()
        control1 = QPointF(start.x() + dx * 0.5, start.y())
        control2 = QPointF(end.x() - dx * 0.5, end.y())
        
        path.cubicTo(control1, control2, end)
        painter.drawPath(path)
        
    def _draw_arrow_head(self, painter, start, end, color):
        """Draw an arrow head at the end of the connection"""
        import math
        
        # Calculate arrow head
        angle = math.atan2((end.y() - start.y()), (end.x() - start.x()))
        
        arrow_length = 12
        arrow_degrees = math.pi / 6
        
        arrow_p1 = QPointF(
            end.x() - arrow_length * math.cos(angle - arrow_degrees),
            end.y() - arrow_length * math.sin(angle - arrow_degrees)
        )
        
        arrow_p2 = QPointF(
            end.x() - arrow_length * math.cos(angle + arrow_degrees),
            end.y() - arrow_length * math.sin(angle + arrow_degrees)
        )
        
        # Draw filled arrow head
        arrow_polygon = QPolygonF([end, arrow_p1, arrow_p2])
        painter.setBrush(QBrush(color))
        painter.drawPolygon(arrow_polygon)
        
    def cleanup(self):
        """Clean up connections when this connection is removed"""
        try:
            if hasattr(self.start_node, 'signals'):
                self.start_node.signals.position_changed.disconnect(self.update_position)
            if hasattr(self.end_node, 'signals'):
                self.end_node.signals.position_changed.disconnect(self.update_position)
        except:
            pass


class PositionPreviewItem(QGraphicsRectItem):
    """Visual preview of where a new node will be placed"""
    
    def __init__(self, position, template=None):
        super().__init__()
        self.template = template
        
        # Set preview appearance based on template type
        if template and hasattr(template, 'node_type'):
            if template.node_type == 'action' or template.node_type.startswith('schema_') or template.node_type.startswith('action_'):
                self.setRect(0, 0, 200, 140)  # Larger for action nodes
            else:
                self.setRect(0, 0, 140, 90)  # Standard size
        else:
            self.setRect(0, 0, 140, 90)  # Default size
            
        # Set position
        self.setPos(QPointF(position["x"], position["y"]))
        self.setOpacity(0.6)
        
        # Style based on template
        if template:
            color = self._get_template_color()
        else:
            color = QColor(100, 100, 100)
            
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.DashLine))
        
        # Add label
        if template and hasattr(template, 'display_name'):
            self.label = QGraphicsTextItem(template.display_name, self)
            self.label.setPos(10, 35)
            self.label.setDefaultTextColor(QColor(255, 255, 255))
            font = self.label.font()
            font.setBold(True)
            self.label.setFont(font)
            # Disable mouse interaction for preview labels
            self.label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self.label.setAcceptHoverEvents(False)
        else:
            self.label = QGraphicsTextItem("New Node", self)
            self.label.setPos(10, 35)
            self.label.setDefaultTextColor(QColor(255, 255, 255))
            # Disable mouse interaction for preview labels
            self.label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self.label.setAcceptHoverEvents(False)
            
        # Set z-value to appear above other items
        self.setZValue(1000)
        
    def _get_template_color(self):
        """Get color for template preview"""
        if hasattr(self.template, 'category'):
            color_map = {
                "Control Flow": QColor(76, 175, 80),     # Green
                "Basic Operations": QColor(33, 150, 243),  # Blue
                "File Operations": QColor(156, 39, 176),   # Purple
                "Information Gathering": QColor(255, 152, 0), # Orange
                "Persistence": QColor(244, 67, 54),        # Red
                "Movement": QColor(96, 125, 139),          # Blue Grey
                "Data Operations": QColor(121, 85, 72),    # Brown
                "Communication": QColor(63, 81, 181),      # Indigo
                "Error Handling": QColor(233, 30, 99)      # Pink
            }
            return color_map.get(self.template.category, QColor(117, 117, 117))
        return QColor(117, 117, 117)  # Default grey