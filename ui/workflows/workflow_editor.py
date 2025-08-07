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
from .custom_canvas import CustomWorkflowCanvas
from .side_panel import SidePanel, SidePanelMode
from .node_editing_content import NodeEditingContent
from .conditional_editing_content import ConditionalEditingContent
from .set_variable_content import SetVariableEditingContent
from .file_transfer_content import FileTransferEditingContent
from .variables_content import VariablesContent


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
        
        # Create main content area with canvas and sliding panel
        main_container = QHBoxLayout()
        main_container.setContentsMargins(0, 0, 0, 0)
        main_container.setSpacing(0)
        
        # Canvas panel (takes up most space)
        self.create_canvas_panel()
        main_container.addWidget(self.canvas_panel)
        
        # Create unified side panel
        self.side_panel = SidePanel()
        self.side_panel.panel_closed.connect(self.on_side_panel_closed)
        self.side_panel.mode_changed.connect(self.on_side_panel_mode_changed)
        
        # Forward content-specific signals
        self.side_panel.node_updated.connect(self.on_node_parameters_updated)
        self.side_panel.node_deleted.connect(self.on_node_deleted)
        self.side_panel.node_execution_requested.connect(self.execute_single_node)
        self.side_panel.variables_updated.connect(self.on_variables_updated)
        
        main_container.addWidget(self.side_panel)
        
        # Create content widgets
        self.node_editing_content = NodeEditingContent(self.schema_service)
        self.conditional_editing_content = ConditionalEditingContent()
        self.set_variable_editing_content = SetVariableEditingContent()
        self.file_transfer_editing_content = FileTransferEditingContent()
        self.variables_content = VariablesContent()
        
        # Connect content widget signals to side panel
        self.node_editing_content.node_updated.connect(self.side_panel.node_updated.emit)
        self.node_editing_content.node_deleted.connect(self.side_panel.node_deleted.emit)
        self.node_editing_content.node_execution_requested.connect(self.side_panel.node_execution_requested.emit)
        self.node_editing_content.close_requested.connect(self.side_panel.close_panel)
        
        self.conditional_editing_content.node_updated.connect(self.side_panel.node_updated.emit)
        self.conditional_editing_content.node_deleted.connect(self.side_panel.node_deleted.emit)
        self.conditional_editing_content.node_execution_requested.connect(self.side_panel.node_execution_requested.emit)
        self.conditional_editing_content.close_requested.connect(self.side_panel.close_panel)
        
        self.set_variable_editing_content.node_updated.connect(self.side_panel.node_updated.emit)
        self.set_variable_editing_content.node_deleted.connect(self.side_panel.node_deleted.emit)
        self.set_variable_editing_content.node_execution_requested.connect(self.side_panel.node_execution_requested.emit)
        self.set_variable_editing_content.close_requested.connect(self.side_panel.close_panel)
        
        self.file_transfer_editing_content.node_updated.connect(self.side_panel.node_updated.emit)
        self.file_transfer_editing_content.node_deleted.connect(self.side_panel.node_deleted.emit)
        self.file_transfer_editing_content.node_execution_requested.connect(self.side_panel.node_execution_requested.emit)
        self.file_transfer_editing_content.close_requested.connect(self.side_panel.close_panel)
        
        self.variables_content.variables_updated.connect(self.side_panel.variables_updated.emit)
        self.variables_content.close_requested.connect(self.side_panel.close_panel)
        
        # Register content widgets with side panel
        self.side_panel.register_content_widget(
            SidePanelMode.NODE_EDITING, 
            self.node_editing_content, 
            "Node Editor",
            "Configure node parameters and settings"
        )
        self.side_panel.register_content_widget(
            SidePanelMode.CONDITIONAL_EDITING, 
            self.conditional_editing_content, 
            "Condition Editor",
            "Configure conditional logic and parameters"
        )
        self.side_panel.register_content_widget(
            SidePanelMode.SET_VARIABLE_EDITING, 
            self.set_variable_editing_content, 
            "Variable Editor",
            "Configure variable name and value with template support"
        )
        self.side_panel.register_content_widget(
            SidePanelMode.FILE_TRANSFER_EDITING, 
            self.file_transfer_editing_content, 
            "File Transfer Editor",
            "Configure file upload/download operations with template support"
        )
        self.side_panel.register_content_widget(
            SidePanelMode.VARIABLES, 
            self.variables_content, 
            "Variables",
            "Manage workflow variables"
        )
        
        # Create widget to contain the layout
        main_widget = QWidget()
        main_widget.setLayout(main_container)
        layout.addWidget(main_widget)
        self.setLayout(layout)
        
        # Set up canvas integrations after all panels are created
        self.setup_canvas_integrations()
        
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
                    self.canvas.clear_selection()
                    self.canvas.select_node(node)
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
        new_action.setIcon(QIcon("resources/file.svg"))
        new_action.triggered.connect(self.new_workflow)
        self.toolbar.addAction(new_action)
        
        open_action = QAction("Open Workflow", self)
        open_action.setIcon(QIcon("resources/folder.svg"))
        open_action.triggered.connect(self.open_workflow)
        self.toolbar.addAction(open_action)
        
        save_action = QAction("Save Workflow", self)
        save_action.setIcon(QIcon("resources/device-floppy.svg"))
        save_action.triggered.connect(self.save_workflow)
        self.toolbar.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.setIcon(QIcon("resources/folders.svg"))
        save_as_action.triggered.connect(self.save_workflow_as)
        self.toolbar.addAction(save_as_action)
        
        self.toolbar.addSeparator()
        
        # Execution operations
        execute_action = QAction("Execute Workflow", self)
        execute_action.setIcon(QIcon("resources/player-play.svg"))
        execute_action.triggered.connect(self.execute_workflow)
        self.toolbar.addAction(execute_action)
        
        stop_action = QAction("Stop Execution", self)
        stop_action.setIcon(QIcon("resources/cancel.svg"))
        stop_action.triggered.connect(self.stop_execution)
        stop_action.setEnabled(False)
        self.toolbar.addAction(stop_action)

        self.toolbar.addSeparator()
        
        # Variables panel toggle
        self.variables_action = QAction("Variables (0)", self)
        self.variables_action.setIcon(QIcon("resources/cube-plus.svg"))
        self.variables_action.setCheckable(True)
        self.variables_action.triggered.connect(self.toggle_variables_panel)
        self.toolbar.addAction(self.variables_action)
        
        self.toolbar.addSeparator()
        
        # Add execution status to toolbar
        self.execution_status_label = QLabel("No workflow execution in progress")
        self.execution_status_label.setStyleSheet("""
            color: #cccccc; 
            font-size: 11px; 
            padding: 5px 10px;
            background-color: rgba(35, 35, 35, 100);
            border-radius: 3px;
        """)
        self.toolbar.addWidget(self.execution_status_label)
        
        
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
        self.canvas = CustomWorkflowCanvas(self, self.schema_service)
        
        # Set workflow service references for integration
        self.canvas.set_workflow_services(self.workflow_service, self.workflow_engine)
        
        # Connect canvas signals
        self.canvas.node_selected.connect(self.on_node_selected)
        # Don't connect to node_parameters_updated to avoid circular updates
        # The node editing panel already emits node_updated which we handle
        self.canvas.node_deselected.connect(self.on_node_deselected)
        self.canvas.connection_created.connect(self.on_connection_created)
        self.canvas.node_deletion_requested.connect(self.on_node_deleted)
        self.canvas.node_moved.connect(self.on_node_moved)
        
        canvas_splitter.addWidget(self.canvas)
        
        layout.addWidget(canvas_splitter)
        
        # Create a default workflow and add a start node
        self.create_default_workflow()
        self.add_start_node()
        
        self.canvas_panel.setLayout(layout)
        
        
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
        
        # Add start node to new default workflow
        self.add_start_node()
        
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
        
        # Clear canvas and load new workflow
        self.canvas.clear_canvas()
        if self.current_workflow:
            self.load_workflow_to_canvas(self.current_workflow)
            
        # Add start node to new workflow
        self.add_start_node()
        
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
            # Get canvas variables for execution
            canvas_variables = self.canvas.get_all_variables() if hasattr(self.canvas, 'get_all_variables') else {}
            
            # Start execution with canvas variables
            execution_id = self.workflow_engine.start_execution(self.current_workflow, beacon_id, canvas_variables)
            
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
            
            # Create workflow context for parameter editing with canvas variables
            workflow_context = {
                'context': None,  # No execution context during design time
                'current_node': node,
                'workflow_connections': self.canvas.connections if hasattr(self.canvas, 'connections') else [],
                'canvas_variables': self.canvas.get_all_variables() if hasattr(self.canvas, 'get_all_variables') else {},
                'workflow': self.current_workflow  # Keep original workflow for backwards compatibility
            }
            
            # Route to appropriate editing panel based on node type
            if node.node_type == 'condition':
                self.side_panel.show_conditional_editing(node, workflow_context)
            elif node.node_type == 'set_variable':
                self.side_panel.show_set_variable_editing(node, workflow_context)
            elif node.node_type == 'file_transfer':
                self.side_panel.show_file_transfer_editing(node, workflow_context)
            else:
                self.side_panel.show_node_editing(node, workflow_context)
        else:
            print("Node deselected")
            # Close the side panel when no node is selected
            current_mode = self.side_panel.get_current_mode()
            if current_mode in [SidePanelMode.NODE_EDITING, SidePanelMode.CONDITIONAL_EDITING, SidePanelMode.SET_VARIABLE_EDITING, SidePanelMode.FILE_TRANSFER_EDITING]:
                self.side_panel.close_panel()
            
    def on_node_deselected(self):
        """Handle node deselection events"""
        print("Node deselected")
        # Close the side panel when no node is selected
        current_mode = self.side_panel.get_current_mode()
        if current_mode in [SidePanelMode.NODE_EDITING, SidePanelMode.CONDITIONAL_EDITING, SidePanelMode.SET_VARIABLE_EDITING, SidePanelMode.FILE_TRANSFER_EDITING]:
            self.side_panel.close_panel()
            
    def on_node_deleted(self, node):
        """Handle node deletion from the editing panel"""
        try:
            # Remove the node from canvas
            if node in self.canvas.nodes:
                # Remove all connections involving this node
                connections_to_remove = []
                for connection in self.canvas.connections:
                    if connection.start_node == node or connection.end_node == node:
                        connections_to_remove.append(connection)
                
                # Remove connections and node using canvas methods
                for connection in connections_to_remove:
                    self.canvas.remove_connection(connection)
                
                # Remove node using canvas method
                self.canvas.remove_node(node)
                
                # Clear selection
                self.canvas.selected_node = None
                
                print(f"Deleted node: {node.node_type} ({node.node_id})")
                
        except Exception as e:
            print(f"Error deleting node: {e}")
            
    def on_connection_created(self, start_node, end_node):
        """Handle connection creation in canvas"""
        print(f"Connection created: {start_node.node_type} -> {end_node.node_type}")
        
    def on_node_moved(self, node, position):
        """Handle node movement in canvas"""
        # Position updates are handled automatically by the canvas
        pass
            
    def on_side_panel_closed(self):
        """Handle side panel being closed"""
        # Clear node selection in canvas if we were in node editing mode
        if self.canvas.selected_node:
            self.canvas.clear_selection()
        
        # Update toolbar state
        self.variables_action.setChecked(False)
        
    def on_node_parameters_updated(self, node, parameters):
        """Handle node parameter updates"""
        print(f"Node {node.node_type} parameters updated: {parameters}")
        
        # Pass the update to the canvas which handles parameter updates properly
        self.canvas.on_node_parameters_updated(node, parameters)
            
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
            
        # Use custom canvas method to get workflow data
        workflow_data = self.canvas.get_workflow_data()
        if workflow_data:
            nodes = workflow_data.get('nodes', [])
            connections = workflow_data.get('connections', [])
            
            self.current_workflow.nodes = nodes
            self.current_workflow.connections = connections
            
        
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
        
        # Create nodes using template-based approach (same as UI creation)
        node_mapping = {}  # Map service node IDs to canvas nodes
        for service_node in workflow.nodes:
            position = QPointF(service_node.position['x'], service_node.position['y'])
            
            # Get template for this node type to ensure proper initialization
            template = self.canvas.template_registry.get_template(service_node.node_type) if hasattr(self.canvas, 'template_registry') else None
            
            if template:
                # Use template-based creation for proper initialization
                canvas_node = self.canvas.add_node_from_template(
                    template, 
                    position, 
                    service_node.module_info
                )
            else:
                # Fallback to basic node creation if no template found
                canvas_node = self.canvas.add_node(
                    service_node.node_type, 
                    position, 
                    service_node.module_info
                )
            
            if canvas_node:
                # Apply saved node properties
                canvas_node.node_id = service_node.node_id
                canvas_node.parameters = service_node.parameters.copy()
                
                # Ensure proper initialization that might be template-dependent
                # Re-apply any node-type specific initialization after parameters are set
                if service_node.node_type == 'condition':
                    # Ensure condition nodes maintain their square shape
                    size = max(canvas_node.width, canvas_node.height, 120)
                    canvas_node.width = size
                    canvas_node.height = size
                    print(f"DEBUG: Applied square sizing to condition node: {size}x{size}")
                
                # Ensure action points are properly set up after all properties are loaded
                if template and hasattr(canvas_node, '_setup_action_points'):
                    canvas_node._setup_action_points(template)
                    print(f"DEBUG: Set up action points for {service_node.node_type} node")
                
                # Update parameter display for action nodes after parameters are loaded
                if hasattr(canvas_node, 'update_parameter_display'):
                    canvas_node.update_parameter_display()
                
                # Ensure proper visual properties are applied
                if hasattr(canvas_node, 'set_colors_for_type'):
                    canvas_node.set_colors_for_type(service_node.node_type)
                    
                node_mapping[service_node.node_id] = canvas_node
                
                print(f"Loaded node: {service_node.node_id} ({service_node.node_type}) at ({position.x()}, {position.y()}) size: {canvas_node.width}x{canvas_node.height}")
            else:
                print(f"Failed to create node: {service_node.node_id} ({service_node.node_type})")
            
        # Create connections
        for service_connection in workflow.connections:
            start_node = node_mapping.get(service_connection.source_node_id)
            end_node = node_mapping.get(service_connection.target_node_id)
            
            if start_node and end_node:
                # Get connection type from service connection with smart fallback
                saved_connection_type = getattr(service_connection, 'connection_type', None)
                
                # If no saved connection type, detect it based on node types and patterns
                if saved_connection_type is None or saved_connection_type == 'None':
                    connection_type = self._detect_connection_type(start_node, end_node, service_connection)
                    print(f"DEBUG: Detected connection type {connection_type} for {start_node.node_id} -> {end_node.node_id}")
                else:
                    connection_type = saved_connection_type
                    print(f"DEBUG: Using saved connection type {connection_type} for {start_node.node_id} -> {end_node.node_id}")
                
                # Create connection using custom canvas method
                connection = self.canvas.create_connection(
                    start_node, end_node, service_connection.connection_id, connection_type
                )
                if connection:
                    print(f"Loaded connection: {start_node.node_id} -> {end_node.node_id} (type: {connection_type})")
                
    def _detect_connection_type(self, start_node, end_node, service_connection):
        """Detect connection type based on node types and patterns when not explicitly saved"""
        
        # If source is not a condition node, it's a sequential connection
        if start_node.node_type != 'condition':
            return 'sequential'
        
        # For condition nodes, we need to determine if this is true or false branch
        # Strategy: Use node positioning and connection order to determine branch type
        
        # Get all connections from this condition node
        condition_connections = []
        for conn in self.canvas.connections:
            if conn.start_node == start_node:
                condition_connections.append(conn)
        
        # If this is the first connection from condition node (by Y position), likely true branch (right side)
        # If this is below the condition node, likely false branch (bottom)
        start_pos = QPointF(start_node.x, start_node.y)
        end_pos = QPointF(end_node.x, end_node.y)
        
        # Calculate relative position of end node to start node
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        
        # If target is primarily to the right, it's likely a true branch
        # If target is primarily below, it's likely a false branch
        if abs(dx) > abs(dy):  # Horizontal movement dominates
            if dx > 0:  # Moving right
                return 'conditional_true'
            else:  # Moving left (unusual, default to true)
                return 'conditional_true'
        else:  # Vertical movement dominates
            if dy > 0:  # Moving down
                return 'conditional_false'
            else:  # Moving up (unusual, default to true)
                return 'conditional_true'
                
    def _has_unsaved_changes(self):
        """Check if current workflow has unsaved changes"""
        # TODO: Implement change tracking
        return False  # For now, assume no changes
        
    def execute_single_node(self, node):
        """Execute a single node individually"""
        if not node:
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
            selected_node = node
            
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
            
            # Get canvas variables for execution
            canvas_variables = self.canvas.get_all_variables() if hasattr(self.canvas, 'get_all_variables') else {}
            
            # Execute using workflow engine with canvas variables
            execution_id = self.workflow_engine.start_execution(temp_workflow, self.selected_beacon, canvas_variables)
            
            if execution_id:
                # Register callback for updates
                self.workflow_engine.register_execution_callback(execution_id, self._on_single_node_execution_update)
                
                # Update UI - disable execute button in panel
                if self.side_panel.get_current_mode() == SidePanelMode.NODE_EDITING:
                    self.node_editing_content.execute_button.setEnabled(False)
                    self.node_editing_content.execute_button.setText("Executing...")
                
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
            # Re-enable execute button in panel
            if self.side_panel.get_current_mode() == SidePanelMode.NODE_EDITING:
                self.node_editing_content.execute_button.setEnabled(True)
                self.node_editing_content.execute_button.setText("Execute")
                
    def toggle_variables_panel(self):
        """Toggle the variables panel visibility"""
        current_mode = self.side_panel.get_current_mode()
        
        if current_mode == SidePanelMode.VARIABLES:
            # Variables panel is currently shown, close it
            self.side_panel.close_panel()
        else:
            # Show variables panel (this will automatically close node editing if open)
            self.side_panel.show_variables()
            
    def on_variables_updated(self, variables):
        """Handle variables update from panel"""
        # Update toolbar button text with count
        count = len(variables)
        self.variables_action.setText(f"Variables ({count})")
        
        # Variables are already updated in canvas through panel integration
        print(f"Variables updated: {variables}")
        
    def on_side_panel_mode_changed(self, mode: SidePanelMode):
        """Handle side panel mode changes"""
        # Update toolbar state based on mode
        if mode == SidePanelMode.VARIABLES:
            self.variables_action.setChecked(True)
        else:
            self.variables_action.setChecked(False)
        
    def setup_canvas_integrations(self):
        """Set up integrations between canvas and panels"""
        if self.canvas and self.variables_content:
            # Connect variables content to canvas
            self.variables_content.set_canvas(self.canvas)
            
            # Update variables count in toolbar
            if hasattr(self.canvas, 'get_all_variables'):
                variables = self.canvas.get_all_variables()
                count = len(variables)
                self.variables_action.setText(f"Variables ({count})")
    


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
        
    def debug_node_colors(self):
        """Debug method to analyze node colors"""
        if hasattr(self.canvas, 'debug_node_colors'):
            self.canvas.debug_node_colors()
            
    def fix_node_colors(self):
        """Fix any nodes with incorrect colors"""
        print("=== Fixing Node Colors ===")
        if hasattr(self.canvas, 'validate_and_fix_node_colors'):
            fixed_count = self.canvas.validate_and_fix_node_colors()
            return fixed_count
        else:
            print("Canvas fix method not available")
            return 0
