from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                            QLabel, QPushButton, QToolBar, QFrame, QInputDialog,
                            QFileDialog, QMessageBox, QListWidget, QDialog, QDialogButtonBox,
                            QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QIcon, QAction, QFont
import time

from services import SchemaService
from services.workflows.workflow_service import WorkflowService
from services.workflows.workflow_engine import WorkflowEngine
from services.workflows.workflow_validator import WorkflowValidator
from database import BeaconRepository
from services.command_processor import CommandProcessor
from .workflow_canvas import WorkflowCanvas


class WorkflowEditor(QWidget):
    """Main workflow editor widget with canvas and property panels"""
    
    workflow_execution_requested = pyqtSignal(str)  # Signal for workflow execution
    
    def __init__(self, schema_service: SchemaService, beacon_repository: BeaconRepository, 
                 command_processor: CommandProcessor):
        super().__init__()
        self.schema_service = schema_service
        self.beacon_repository = beacon_repository
        self.command_processor = command_processor
        
        # Initialize schema management for workflows
        
        self.workflow_service = WorkflowService(schema_service, beacon_repository, command_processor)
        self.workflow_engine = WorkflowEngine(self.workflow_service, schema_service, beacon_repository, command_processor)
        self.workflow_validator = WorkflowValidator(schema_service=schema_service)
        
        self.current_workflow = None
        self.selected_beacon = None
        self.current_execution_id = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the main workflow editor interface"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create toolbar
        self.create_toolbar()
        layout.addWidget(self.toolbar)
        
        # Create main content area with splitters
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Center panel: Workflow canvas (now takes up more space)
        self.create_canvas_panel()
        main_splitter.addWidget(self.canvas_panel)
        
        # Right panel: Properties and execution
        self.create_properties_panel()
        main_splitter.addWidget(self.properties_panel)
        
        # Set splitter proportions (80% : 20% )
        main_splitter.setSizes([800, 200])
        main_splitter.setChildrenCollapsible(False)
        
        layout.addWidget(main_splitter)
        self.setLayout(layout)
        
    def perform_validation(self):
        """Perform workflow validation"""
        if self.canvas:
            nodes = self.canvas.nodes
            connections = self.canvas.connections
            self.workflow_validator.validate_workflow(nodes, connections)
            
    def on_validation_issue_selected(self, issue):
        """Handle validation issue selection"""
        # Navigate to the issue location if it has a node_id
        if issue.node_id:
            for node in self.canvas.nodes:
                if getattr(node, 'node_id', str(id(node))) == issue.node_id:
                    # Select and center the node
                    self.canvas.selected_node = node
                    self.canvas.scene.clearSelection()
                    node.setSelected(True)
                    self.canvas.centerOn(node)
                    break
                    
    def on_validation_fix_requested(self, issue):
        """Handle validation fix request"""
        from PyQt6.QtWidgets import QMessageBox
        
        # For now, just show the suggested fix
        if issue.suggested_fix:
            QMessageBox.information(self, "Suggested Fix", 
                                  f"Issue: {issue.title}\n\nSuggested Fix: {issue.suggested_fix}")
        else:
            QMessageBox.information(self, "No Fix Available", 
                                  "No automatic fix is available for this issue.")
        
    def create_toolbar(self):
        """Create the workflow editor toolbar"""
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        
        # File operations
        new_action = QAction("New Workflow", self)
        new_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
        new_action.triggered.connect(self.new_workflow)
        self.toolbar.addAction(new_action)
        
        open_action = QAction("Open Workflow", self)
        open_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirOpenIcon))
        open_action.triggered.connect(self.open_workflow)
        self.toolbar.addAction(open_action)
        
        save_action = QAction("Save Workflow", self)
        save_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogSaveButton))
        save_action.triggered.connect(self.save_workflow)
        self.toolbar.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogSaveButton))
        save_as_action.triggered.connect(self.save_workflow_as)
        self.toolbar.addAction(save_as_action)
        
        self.toolbar.addSeparator()
        
        # Execution operations
        execute_action = QAction("Execute Workflow", self)
        execute_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaPlay))
        execute_action.triggered.connect(self.execute_workflow)
        self.toolbar.addAction(execute_action)
        
        stop_action = QAction("Stop Execution", self)
        stop_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaStop))
        stop_action.triggered.connect(self.stop_execution)
        stop_action.setEnabled(False)
        self.toolbar.addAction(stop_action)
        
        self.toolbar.addSeparator()
        
        # View operations
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView))
        zoom_in_action.triggered.connect(self.zoom_in)
        self.toolbar.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogListView))
        zoom_out_action.triggered.connect(self.zoom_out)
        self.toolbar.addAction(zoom_out_action)
        
        self.toolbar.addSeparator()
        
        
    def create_canvas_panel(self):
        """Create the center canvas panel for workflow design"""
        self.canvas_panel = QFrame()
        self.canvas_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Canvas header
        header = QLabel("Workflow Canvas")
        header.setStyleSheet("""
            font-weight: bold; 
            padding: 8px; 
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030);
            color: white;
            border-radius: 4px;
        """)
        layout.addWidget(header)
        
        # Create canvas and validation splitter
        canvas_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Create the actual workflow canvas
        self.canvas = WorkflowCanvas(self.schema_service)
        self.canvas.node_selected.connect(self.on_node_selected)
        self.canvas.node_parameters_updated.connect(self.on_node_parameters_updated)
        
        canvas_splitter.addWidget(self.canvas)
        
        layout.addWidget(canvas_splitter)
        
        # Create a default workflow and add a start node
        self.create_default_workflow()
        self.add_start_node()
        
        self.canvas_panel.setLayout(layout)
        
    def create_properties_panel(self):
        """Create the right properties panel for node configuration"""
        self.properties_panel = QFrame()
        self.properties_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        self.properties_panel.setMinimumWidth(180)
        self.properties_panel.setMaximumWidth(300)
        
        layout = QVBoxLayout()
        
        # Properties header
        header = QLabel("Properties")
        header.setStyleSheet("""
            font-weight: bold; 
            padding: 8px; 
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030);
            color: white;
            border-radius: 4px;
        """)
        layout.addWidget(header)
        
        # Placeholder for properties
        self.properties_placeholder = QLabel("Node properties will appear here when a node is selected.")
        self.properties_placeholder.setStyleSheet("padding: 10px; color: #cccccc; background-color: #232323;")
        self.properties_placeholder.setWordWrap(True)
        layout.addWidget(self.properties_placeholder)
        
        # Execution panel
        exec_header = QLabel("Execution")
        exec_header.setStyleSheet("""
            font-weight: bold; 
            padding: 8px; 
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030);
            color: white;
            border-radius: 4px;
            margin-top: 10px;
        """)
        layout.addWidget(exec_header)
        
        self.execution_status_label = QLabel("No workflow execution in progress")
        self.execution_status_label.setStyleSheet("padding: 10px; color: #cccccc; background-color: #232323;")
        self.execution_status_label.setWordWrap(True)
        layout.addWidget(self.execution_status_label)
        
        # Single node execution button
        self.execute_node_btn = QPushButton("Execute Selected Node")
        self.execute_node_btn.setEnabled(False)
        self.execute_node_btn.clicked.connect(self.execute_selected_node)
        self.execute_node_btn.setMinimumWidth(170)
        self.execute_node_btn.setMinimumHeight(35)
        self.execute_node_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        layout.addWidget(self.execute_node_btn)
        
        layout.addStretch()
        self.properties_panel.setLayout(layout)
        
    def create_default_workflow(self):
        """Create a default workflow for immediate use"""
        from datetime import datetime
        
        # Create a default workflow with a timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_name = f"New Workflow - {timestamp}"
        
        self.current_workflow = self.workflow_service.create_workflow(
            default_name, 
            "Workflow created at startup - rename and save as needed"
        )
        print(f"Created default workflow: {self.current_workflow.name}")
        
        # Update window title to show current workflow
        self.update_window_title()
        
    def new_workflow(self):
        """Create a new workflow"""
        # Check if current workflow has unsaved changes
        if self.current_workflow and self._has_unsaved_changes():
            reply = QMessageBox.question(self, "Unsaved Changes", 
                                       "Save current workflow before creating a new one?",
                                       QMessageBox.StandardButton.Yes | 
                                       QMessageBox.StandardButton.No | 
                                       QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Yes:
                if not self.save_workflow():
                    return  # Save was cancelled or failed
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        # Get workflow name and description
        name, ok = QInputDialog.getText(self, "New Workflow", "Enter workflow name:")
        if not ok or not name.strip():
            return
            
        description, ok = QInputDialog.getText(self, "New Workflow", "Enter workflow description (optional):")
        if not ok:
            description = ""
            
        # Create new workflow
        self.current_workflow = self.workflow_service.create_workflow(name.strip(), description.strip())
        
        # Clear canvas
        self.canvas.clear_canvas()
        
        print(f"Created new workflow: {self.current_workflow.name}")
        self.update_window_title()
        
    def update_window_title(self):
        """Update window title to show current workflow name"""
        if hasattr(self, 'parent') and self.parent():
            if self.current_workflow:
                title = f"Workflow Editor - {self.current_workflow.name}"
                self.parent().setWindowTitle(title)
        
    def open_workflow(self):
        """Open an existing workflow"""
        # Check if current workflow has unsaved changes
        if self.current_workflow and self._has_unsaved_changes():
            reply = QMessageBox.question(self, "Unsaved Changes", 
                                       "Save current workflow before opening another?",
                                       QMessageBox.StandardButton.Yes | 
                                       QMessageBox.StandardButton.No | 
                                       QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Yes:
                if not self.save_workflow():
                    return  # Save was cancelled or failed
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        # Show workflow selection dialog
        dialog = WorkflowSelectionDialog(self.workflow_service, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_workflow_id = dialog.get_selected_workflow_id()
            if selected_workflow_id:
                workflow = self.workflow_service.load_workflow(selected_workflow_id)
                if workflow:
                    self.current_workflow = workflow
                    self.load_workflow_to_canvas(workflow)
                    print(f"Opened workflow: {workflow.name}")
                    self.update_window_title()
                else:
                    QMessageBox.warning(self, "Error", "Failed to load selected workflow")
        
    def save_workflow(self):
        """Save the current workflow"""
        if not self.current_workflow:
            QMessageBox.warning(self, "No Workflow", "No workflow to save")
            return False
            
        # Check if this is a default workflow that should be renamed
        if self.current_workflow.name.startswith("New Workflow - "):
            reply = QMessageBox.question(self, "Save Workflow", 
                                       "This appears to be a default workflow. Would you like to give it a proper name?",
                                       QMessageBox.StandardButton.Yes | 
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                name, ok = QInputDialog.getText(self, "Save Workflow", "Enter workflow name:", 
                                              text=self.current_workflow.name)
                if ok and name.strip():
                    self.current_workflow.name = name.strip()
                    
                description, ok = QInputDialog.getText(self, "Save Workflow", "Enter workflow description (optional):", 
                                                     text=self.current_workflow.description)
                if ok:
                    self.current_workflow.description = description.strip()
            
        try:
            # Convert canvas state to workflow format
            self.save_canvas_to_workflow()
            
            # Save workflow
            success = self.workflow_service.save_workflow(self.current_workflow)
            if success:
                QMessageBox.information(self, "Success", f"Workflow '{self.current_workflow.name}' saved successfully")
                print(f"Saved workflow: {self.current_workflow.name}")
                self.update_window_title()
                return True
            else:
                QMessageBox.warning(self, "Error", "Failed to save workflow")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving workflow: {str(e)}")
            return False
        
    def save_workflow_as(self):
        """Save the workflow with a new name"""
        if not self.current_workflow:
            QMessageBox.warning(self, "No Workflow", "No workflow to save")
            return False
            
        # Always prompt for new name and description
        name, ok = QInputDialog.getText(self, "Save Workflow As", "Enter workflow name:", 
                                      text=self.current_workflow.name)
        if not ok or not name.strip():
            return False
            
        description, ok = QInputDialog.getText(self, "Save Workflow As", "Enter workflow description (optional):", 
                                             text=self.current_workflow.description)
        if not ok:
            return False
            
        try:
            # Update workflow details
            old_name = self.current_workflow.name
            self.current_workflow.name = name.strip()
            self.current_workflow.description = description.strip()
            
            # Convert canvas state to workflow format
            self.save_canvas_to_workflow()
            
            # Save workflow
            success = self.workflow_service.save_workflow(self.current_workflow)
            if success:
                QMessageBox.information(self, "Success", f"Workflow saved as '{self.current_workflow.name}'")
                print(f"Saved workflow as: {self.current_workflow.name}")
                self.update_window_title()
                return True
            else:
                # Restore old name on failure
                self.current_workflow.name = old_name
                QMessageBox.warning(self, "Error", "Failed to save workflow")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving workflow: {str(e)}")
            return False
        
    def execute_workflow(self):
        """Execute the current workflow"""
        if not self.current_workflow:
            QMessageBox.warning(self, "No Workflow", "Please create or open a workflow first")
            return
            
        # Ensure workflow is saved with current canvas state
        self.save_canvas_to_workflow()
        
        # Check if workflow has any executable nodes (more than just a start node)
        executable_nodes = [node for node in self.current_workflow.nodes if node.node_type != 'start']
        if not executable_nodes:
            reply = QMessageBox.question(self, "Simple Workflow", 
                                       "This workflow only contains a start node. Would you like to add more nodes before executing?",
                                       QMessageBox.StandardButton.Yes | 
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                return
            
        # Show beacon selection dialog
        dialog = BeaconSelectionDialog(self.beacon_repository, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_beacon_id = dialog.get_selected_beacon_id()
            if selected_beacon_id:
                self.selected_beacon = selected_beacon_id
                self._start_workflow_execution(selected_beacon_id)
        
    def stop_execution(self):
        """Stop workflow execution"""
        if self.current_execution_id:
            success = self.workflow_engine.stop_execution(self.current_execution_id)
            if success:
                self.current_execution_id = None
                self._update_execution_status("Execution stopped by user")
                print("Workflow execution stopped")
            else:
                QMessageBox.warning(self, "Error", "Failed to stop workflow execution")
        else:
            QMessageBox.information(self, "No Execution", "No workflow is currently executing")
            
    def _start_workflow_execution(self, beacon_id: str):
        """Start executing the workflow on the selected beacon"""
        try:
            # Start execution
            execution_id = self.workflow_engine.start_execution(self.current_workflow, beacon_id)
            
            if execution_id:
                self.current_execution_id = execution_id
                
                # Register callback for execution updates
                print(f"Registering execution callback for {execution_id}")
                self.workflow_engine.register_execution_callback(execution_id, self._on_execution_update)
                
                # Update UI to show execution state
                self._update_execution_status(f"Executing workflow on beacon {beacon_id}")
                
                # Enable stop button, disable execute button
                self._set_execution_ui_state(True)
                
                # Start canvas monitoring for visual feedback
                self.canvas.monitor_workflow_execution(execution_id, self.workflow_engine)
                
                print(f"Started workflow execution: {execution_id}")
            else:
                QMessageBox.warning(self, "Execution Failed", "Failed to start workflow execution")
                
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Error starting execution: {str(e)}")
            
    def _on_execution_update(self, context):
        """Handle workflow execution updates"""
        print(f"Workflow execution update: status={context.status.value}, current_node={context.current_node_id}")
        
        # Update execution status display
        status_text = f"Status: {context.status.value}"
        if context.current_node_id:
            status_text += f" (Node: {context.current_node_id})"
            
        self._update_execution_status(status_text)
        
        # Update canvas visual feedback
        self._update_canvas_execution_state(context)
        
        # Check if execution is complete
        if context.status.value in ['completed', 'failed', 'stopped']:
            print(f"Workflow execution completed with status: {context.status.value}")
            self.current_execution_id = None
            self._set_execution_ui_state(False)
            
            if context.status.value == 'completed':
                QMessageBox.information(self, "Execution Complete", "Workflow executed successfully!")
            elif context.status.value == 'failed':
                QMessageBox.warning(self, "Execution Failed", "Workflow execution failed. Check logs for details.")
                
    def _update_execution_status(self, status_text: str):
        """Update the execution status display"""
        print(f"Updating execution status display: {status_text}")
        if hasattr(self, 'execution_status_label'):
            self.execution_status_label.setText(status_text)
            print(f"Status label updated successfully")
        else:
            print("WARNING: execution_status_label not found")
        print(f"Execution Status: {status_text}")
        
    def _update_canvas_execution_state(self, context):
        """Update canvas to show execution progress"""
        # TODO: Implement visual feedback on canvas
        # Could highlight currently executing node, show completion status, etc.
        pass
        
    def _set_execution_ui_state(self, is_executing: bool):
        """Update UI state based on execution status"""
        print(f"Setting execution UI state: is_executing={is_executing}")
        
        # Enable/disable toolbar buttons
        buttons_updated = 0
        for action in self.toolbar.actions():
            if action.text() == "Execute Workflow":
                action.setEnabled(not is_executing)
                buttons_updated += 1
                print(f"Execute Workflow button enabled: {not is_executing}")
            elif action.text() == "Stop Execution":
                action.setEnabled(is_executing)
                buttons_updated += 1
                print(f"Stop Execution button enabled: {is_executing}")
        
        print(f"Updated {buttons_updated} toolbar buttons")
        
    def zoom_in(self):
        """Zoom in on the canvas"""
        self.canvas.zoom_in()
        
    def zoom_out(self):
        """Zoom out on the canvas"""
        self.canvas.zoom_out()
        
    def on_node_selected(self, node):
        """Handle node selection events"""
        if node:
            print(f"Node selected: {node.node_type}")
            self.update_properties_panel(node)
            # Enable execute button for executable nodes (not start/end)
            can_execute = node.node_type not in ['start', 'end']
            self.execute_node_btn.setEnabled(can_execute)
        else:
            print("Node deselected")
            self.clear_properties_panel()
            # Disable execute button when no node is selected
            self.execute_node_btn.setEnabled(False)
            
    def update_properties_panel(self, node):
        """Update the properties panel with node information"""
        # Create detailed node information
        node_info = f"""<b>Node Type:</b> {node.node_type}<br>
<b>Node ID:</b> {node.node_id}<br>
<b>Display Name:</b> {node.get_display_name()}<br>"""
        
        if node.module_info:
            node_info += "<br><b>Module Information:</b><br>"
            for key, value in node.module_info.items():
                node_info += f"• {key}: {value}<br>"
                
        if hasattr(node, 'parameters') and node.parameters:
            node_info += "<br><b>Parameters:</b><br>"
            for key, value in node.parameters.items():
                node_info += f"• {key}: {value}<br>"
        
        # Update the properties placeholder
        self.properties_placeholder.setText(node_info)
        self.properties_placeholder.setTextFormat(Qt.TextFormat.RichText)
        
    def clear_properties_panel(self):
        """Clear the properties panel"""
        self.properties_placeholder.setText("Node properties will appear here when a node is selected.")
        self.properties_placeholder.setTextFormat(Qt.TextFormat.PlainText)
        
    def on_node_parameters_updated(self, node, parameters):
        """Handle node parameter updates"""
        print(f"Node {node.node_type} parameters updated: {parameters}")
        # Update the properties panel to show new parameters
        if self.canvas.selected_node == node:
            self.update_properties_panel(node)
            
    def add_start_node(self):
        """Add a start node for new workflows"""
        # Only add start node if canvas is empty
        if not self.canvas.nodes:
            # Place start node at a reasonable position and center the view on it
            start_position = QPointF(0, 0)  # Center of scene coordinates
            start_node = self.canvas.add_node("start", start_position)
            
            # Center the canvas view on the start node
            self.canvas.centerOn(start_node)
            print(f"Added start node to new workflow at {start_position}")
        
    def save_canvas_to_workflow(self):
        """Convert current canvas state to workflow format"""
        if not self.current_workflow:
            return
            
        from services.workflows.workflow_service import WorkflowNode as ServiceWorkflowNode, WorkflowConnection as ServiceWorkflowConnection
        
        # Convert canvas nodes to service nodes
        workflow_nodes = []
        for canvas_node in self.canvas.nodes:
            workflow_node = ServiceWorkflowNode(
                node_id=canvas_node.node_id,
                node_type=canvas_node.node_type,
                position={'x': canvas_node.scenePos().x(), 'y': canvas_node.scenePos().y()},
                module_info=canvas_node.module_info.copy(),
                parameters=canvas_node.parameters.copy(),
                conditions=[]  # TODO: Implement conditions
            )
            workflow_nodes.append(workflow_node)
            
        # Convert canvas connections to service connections
        workflow_connections = []
        for canvas_connection in self.canvas.connections:
            connection = ServiceWorkflowConnection(
                connection_id=canvas_connection.connection_id,
                source_node_id=canvas_connection.start_node.node_id,
                target_node_id=canvas_connection.end_node.node_id,
                condition=None  # TODO: Implement connection conditions
            )
            workflow_connections.append(connection)
            
        # Update workflow
        self.current_workflow.nodes = workflow_nodes
        self.current_workflow.connections = workflow_connections
        
        # Save schema configuration with workflow
        if hasattr(self.current_workflow, 'metadata'):
            if not self.current_workflow.metadata:
                self.current_workflow.metadata = {}
        else:
            self.current_workflow.metadata = {}
            
        
    def load_workflow_to_canvas(self, workflow):
        """Load workflow from service format to canvas"""
        # Clear existing canvas
        self.canvas.clear_canvas()
        
        # Create nodes
        node_mapping = {}  # Map service node IDs to canvas nodes
        for service_node in workflow.nodes:
            position = QPointF(service_node.position['x'], service_node.position['y'])
            canvas_node = self.canvas.add_node(
                service_node.node_type, 
                position, 
                service_node.module_info
            )
            canvas_node.node_id = service_node.node_id
            canvas_node.parameters = service_node.parameters.copy()
            
            # Update parameter display for action nodes after parameters are loaded
            if hasattr(canvas_node, 'update_parameter_display'):
                canvas_node.update_parameter_display()
                
            node_mapping[service_node.node_id] = canvas_node
            
        # Create connections
        for service_connection in workflow.connections:
            start_node = node_mapping.get(service_connection.source_node_id)
            end_node = node_mapping.get(service_connection.target_node_id)
            
            if start_node and end_node:
                from .workflow_canvas import GuidedWorkflowConnection
                from services.workflows.node_compatibility import ConnectionType
                # Use sequential connection type as default for loaded workflows
                connection = GuidedWorkflowConnection(start_node, end_node, ConnectionType.SEQUENTIAL)
                connection.connection_id = service_connection.connection_id
                self.canvas.scene.addItem(connection)
                self.canvas.connections.append(connection)
                
        # Refresh all connection positions after loading
        self._refresh_connections()
                
    def _refresh_connections(self):
        """Refresh all connection positions and redraw them"""
        for connection in self.canvas.connections:
            connection.update_position()
        
        # Force scene redraw
        self.canvas.scene.update()
                
    def _has_unsaved_changes(self):
        """Check if current workflow has unsaved changes"""
        # TODO: Implement change tracking
        return False  # For now, assume no changes
        
    def execute_selected_node(self):
        """Execute the currently selected node individually"""
        if not self.canvas.selected_node:
            QMessageBox.warning(self, "No Node Selected", "Please select a node to execute")
            return
            
        # Check if we have a selected beacon
        if not self.selected_beacon:
            # Show beacon selection dialog
            dialog = BeaconSelectionDialog(self.beacon_repository, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_beacon_id = dialog.get_selected_beacon_id()
                if selected_beacon_id:
                    self.selected_beacon = selected_beacon_id
                else:
                    return
            else:
                return
                
        # Execute the selected node
        try:
            selected_node = self.canvas.selected_node
            
            # Create a minimal workflow for single node execution
            from services.workflows.workflow_service import Workflow, WorkflowNode as ServiceWorkflowNode, WorkflowConnection as ServiceWorkflowConnection
            
            # Create a start node that connects to the selected node
            start_node = ServiceWorkflowNode(
                node_id=f"start_{int(time.time())}",
                node_type="start",
                position={'x': selected_node.scenePos().x() - 200, 'y': selected_node.scenePos().y()},
                module_info={},
                parameters={},
                conditions=[]
            )
            
            # Convert canvas node to service node format
            service_node = ServiceWorkflowNode(
                node_id=selected_node.node_id,
                node_type=selected_node.node_type,
                position={'x': selected_node.scenePos().x(), 'y': selected_node.scenePos().y()},
                module_info=selected_node.module_info.copy(),
                parameters=selected_node.parameters.copy(),
                conditions=[]
            )
            
            # Create connection from start to selected node
            connection = ServiceWorkflowConnection(
                connection_id=f"conn_start_to_node_{int(time.time())}",
                source_node_id=start_node.node_id,
                target_node_id=service_node.node_id
            )
            
            # Create temporary workflow with start node, target node, and connection
            temp_workflow = Workflow(
                workflow_id=f"temp_single_node_{int(time.time())}_{int(time.time())}",
                name="Single Node Execution",
                description=f"Executing {selected_node.node_type} node",
                nodes=[start_node, service_node],
                connections=[connection]
            )
            
            # Execute using workflow engine
            execution_id = self.workflow_engine.start_execution(temp_workflow, self.selected_beacon)
            
            if execution_id:
                # Register callback for updates
                self.workflow_engine.register_execution_callback(execution_id, self._on_single_node_execution_update)
                
                # Update UI
                self.execute_node_btn.setEnabled(False)
                self.execute_node_btn.setText("Executing...")
                
                # Start canvas monitoring for single node execution
                self.canvas.monitor_workflow_execution(execution_id, self.workflow_engine)
                
                print(f"Started single node execution: {execution_id}")
            else:
                QMessageBox.warning(self, "Execution Failed", "Failed to start node execution")
                
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Error executing node: {str(e)}")
            
    def _on_single_node_execution_update(self, context):
        """Handle single node execution updates"""
        # Check if execution is complete
        if context.status.value in ['completed', 'failed', 'stopped']:
            self.execute_node_btn.setEnabled(True)
            self.execute_node_btn.setText("Execute Selected Node")
    


class BeaconSelectionDialog(QDialog):
    """Dialog for selecting a beacon for workflow execution"""
    
    def __init__(self, beacon_repository: BeaconRepository, parent=None):
        super().__init__(parent)
        self.beacon_repository = beacon_repository
        self.selected_beacon_id = None
        
        self.setWindowTitle("Select Beacon")
        self.setModal(True)
        self.resize(450, 350)
        
        self.setup_ui()
        self.load_beacons()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Select a beacon to execute the workflow on:")
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)
        
        # Beacon list
        self.beacon_list = QListWidget()
        self.beacon_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.beacon_list)
        
        # Status info
        info_label = QLabel("Note: Only online beacons can execute workflows")
        info_label.setStyleSheet("color: #666666; font-style: italic; padding: 5px;")
        layout.addWidget(info_label)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def load_beacons(self):
        """Load available beacons into the list"""
        try:
            beacons = self.beacon_repository.get_all_beacons()
            
            if not beacons:
                self.beacon_list.addItem("No beacons available")
                return
                
            online_count = 0
            for beacon in beacons:
                status_text = "ONLINE" if beacon.status == 'online' else "OFFLINE"
                item_text = f"[{status_text}] {beacon.beacon_id} ({beacon.computer_name})"
                
                if hasattr(beacon, 'last_checkin') and beacon.last_checkin:
                    item_text += f" - Last checkin: {beacon.last_checkin.strftime('%Y-%m-%d %H:%M:%S')}"
                
                from PyQt6.QtWidgets import QListWidgetItem
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, beacon.beacon_id)
                
                # Only enable online beacons
                if beacon.status == 'online':
                    online_count += 1
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    
                self.beacon_list.addItem(item)
                
            if online_count == 0:
                warning_item = QListWidgetItem("WARNING: No online beacons available for execution")
                warning_item.setFlags(warning_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.beacon_list.insertItem(0, warning_item)
                
        except Exception as e:
            self.beacon_list.addItem(f"Error loading beacons: {str(e)}")
            
    def get_selected_beacon_id(self):
        """Get the selected beacon ID"""
        current_item = self.beacon_list.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None


class WorkflowSelectionDialog(QDialog):
    """Dialog for selecting a workflow to open"""
    
    def __init__(self, workflow_service: WorkflowService, parent=None):
        super().__init__(parent)
        self.workflow_service = workflow_service
        self.selected_workflow_id = None
        
        self.setWindowTitle("Open Workflow")
        self.setModal(True)
        self.resize(500, 400)
        
        self.setup_ui()
        self.load_workflows()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Select a workflow to open:")
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)
        
        # Workflow list
        self.workflow_list = QListWidget()
        self.workflow_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.workflow_list)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def load_workflows(self):
        """Load available workflows into the list"""
        try:
            workflows = self.workflow_service.list_workflows()
            
            if not workflows:
                self.workflow_list.addItem("No workflows available")
                return
                
            for workflow_info in workflows:
                item_text = f"{workflow_info['name']} - {workflow_info['description'][:50]}..."
                if len(workflow_info['description']) <= 50:
                    item_text = f"{workflow_info['name']} - {workflow_info['description']}"
                    
                item_text += f" ({workflow_info['node_count']} nodes)"
                
                from PyQt6.QtWidgets import QListWidgetItem
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, workflow_info['workflow_id'])
                self.workflow_list.addItem(item)
                
        except Exception as e:
            self.workflow_list.addItem(f"Error loading workflows: {str(e)}")
            
    def get_selected_workflow_id(self):
        """Get the selected workflow ID"""
        current_item = self.workflow_list.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None
