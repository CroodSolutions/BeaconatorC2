"""
Active Workflows Management Widget

Embedded widget for managing workflows with automatic triggers.
Displays in the main workflow editor view instead of a popup dialog.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMessageBox,
    QMenu, QCheckBox, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont
from typing import Optional
from datetime import datetime


class ActiveWorkflowsWidget(QWidget):
    """Widget for managing workflows with automatic triggers"""
    
    # Signals
    workflow_enabled = pyqtSignal(str)  # workflow_id
    workflow_disabled = pyqtSignal(str)  # workflow_id
    return_to_canvas = pyqtSignal()  # Signal to return to canvas view
    
    def __init__(self, trigger_service, workflow_service, workflow_editor, parent=None):
        super().__init__(parent)
        self.trigger_service = trigger_service
        self.workflow_service = workflow_service
        self.workflow_editor = workflow_editor  # Store reference to WorkflowEditor

        self.setup_ui()
        
        # Connect to trigger service signals for live updates
        if self.trigger_service:
            self.trigger_service.trigger_registered.connect(self.on_trigger_registered)
            self.trigger_service.trigger_removed.connect(self.on_trigger_removed)
            self.trigger_service.workflow_triggered.connect(self.on_workflow_triggered)
        
        # Setup refresh timer for updating last triggered times
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_last_triggered_times)
        self.refresh_timer.start(30000)  # Update every 30 seconds
        
    def setup_ui(self):
        """Setup the widget UI"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header with back button
        header_layout = QHBoxLayout()
        
        # Back to canvas button
        back_button = QPushButton("← Back to Canvas")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        back_button.clicked.connect(self.return_to_canvas.emit)
        header_layout.addWidget(back_button)
        
        title_label = QLabel("Active Workflow Management")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.setIcon(QIcon("resources/refresh.svg"))
        refresh_button.clicked.connect(self.load_workflows)
        header_layout.addWidget(refresh_button)
        
        layout.addLayout(header_layout)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Description
        desc_label = QLabel(
            "Manage workflows with automatic triggers. These workflows can execute "
            "automatically based on events like beacon connections, status changes, or schedules."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888; padding: 5px; background-color: #2a2a2a; border-radius: 4px;")
        layout.addWidget(desc_label)
        
        # Workflow table
        self.create_workflow_table()
        layout.addWidget(self.workflow_table)
        
        # Statistics panel
        self.create_statistics_panel()
        layout.addWidget(self.stats_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.enable_all_button = QPushButton("Enable All")
        self.enable_all_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.enable_all_button.clicked.connect(self.enable_all_workflows)
        button_layout.addWidget(self.enable_all_button)
        
        self.disable_all_button = QPushButton("Disable All")
        self.disable_all_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.disable_all_button.clicked.connect(self.disable_all_workflows)
        button_layout.addWidget(self.disable_all_button)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def create_workflow_table(self):
        """Create the workflows table"""
        self.workflow_table = QTableWidget()
        self.workflow_table.setColumnCount(7)
        self.workflow_table.setHorizontalHeaderLabels([
            "Enabled", "Workflow Name", "Trigger Type", "Configuration",
            "Last Triggered", "Trigger Count", "Actions"
        ])
        
        # Configure table
        self.workflow_table.setAlternatingRowColors(False)
        self.workflow_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.workflow_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Set minimum row height to prevent button cutoff
        self.workflow_table.verticalHeader().setDefaultSectionSize(35)

        # Style the table
        self.workflow_table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                gridline-color: #404040;
                color: white;
            }
            QTableWidget::item {
                padding: 5px;
                background-color: #2b2b2b;
            }
            QTableWidget::item:selected {
                background-color: #4a90e2;
            }
            QHeaderView::section {
                background-color: #333;
                color: white;
                padding: 5px;
                border: 1px solid #404040;
                font-weight: bold;
            }
        """)
        
        # Set column widths
        header = self.workflow_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)

        self.workflow_table.setColumnWidth(6, 100)
        
        # Enable context menu
        self.workflow_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.workflow_table.customContextMenuRequested.connect(self.show_context_menu)
        
    def create_statistics_panel(self):
        """Create statistics display panel"""
        self.stats_group = QGroupBox("Statistics")
        self.stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 0.5em;
                color: white;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(10, 10, 10, 10)
        
        # Total workflows
        self.total_label = QLabel("Total Workflows: 0")
        self.total_label.setStyleSheet("color: white;")
        stats_layout.addWidget(self.total_label)
        
        # Active workflows
        self.active_label = QLabel("Active: 0")
        self.active_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        stats_layout.addWidget(self.active_label)
        
        # Inactive workflows
        self.inactive_label = QLabel("Inactive: 0")
        self.inactive_label.setStyleSheet("color: #FFA726; font-weight: bold;")
        stats_layout.addWidget(self.inactive_label)
        
        # Total triggers today
        self.today_label = QLabel("Triggered Today: 0")
        self.today_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        stats_layout.addWidget(self.today_label)
        
        stats_layout.addStretch()
        self.stats_group.setLayout(stats_layout)
        
    def load_workflows(self):
        """Load all workflows with triggers"""
        self.workflow_table.setRowCount(0)
        
        if not self.trigger_service:
            return
            
        # Get all workflows with active triggers
        active_triggers = self.trigger_service.active_triggers
        
        total_count = 0
        active_count = 0
        inactive_count = 0
        today_count = 0
        today = datetime.now().date()
        
        for workflow_id, triggers in active_triggers.items():
            # Load workflow details
            workflow = self.workflow_service.load_workflow(workflow_id)
            if not workflow:
                continue
                
            for trigger_id, trigger_config in triggers.items():
                row = self.workflow_table.rowCount()
                self.workflow_table.insertRow(row)
                
                # Status checkbox
                status_checkbox = QCheckBox()
                status_checkbox.setChecked(trigger_config.enabled)
                status_checkbox.stateChanged.connect(
                    lambda state, wid=workflow_id, tid=trigger_id: 
                    self.toggle_trigger(wid, tid, state == Qt.CheckState.Checked.value)
                )
                self.workflow_table.setCellWidget(row, 0, status_checkbox)
                
                # Workflow name
                name_item = QTableWidgetItem(workflow.name)
                self.workflow_table.setItem(row, 1, name_item)
                
                # Trigger type
                trigger_type = trigger_config.trigger_type.value
                type_item = QTableWidgetItem(trigger_type.replace('_', ' ').title())
                self.workflow_table.setItem(row, 2, type_item)
                
                # Configuration summary
                config_summary = self.get_trigger_config_summary(trigger_config)
                config_item = QTableWidgetItem(config_summary)
                self.workflow_table.setItem(row, 3, config_item)
                
                # Last triggered
                if trigger_config.last_triggered:
                    last_triggered = trigger_config.last_triggered.strftime("%Y-%m-%d %H:%M:%S")
                    if trigger_config.last_triggered.date() == today:
                        today_count += trigger_config.trigger_count
                else:
                    last_triggered = "Never"
                last_item = QTableWidgetItem(last_triggered)
                self.workflow_table.setItem(row, 4, last_item)
                
                # Trigger count
                count_item = QTableWidgetItem(str(trigger_config.trigger_count))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.workflow_table.setItem(row, 5, count_item)
                
                # Actions button
                actions_button = QPushButton("Edit")
                actions_button.setStyleSheet("""
                    QPushButton {
                        background-color: #555;
                        color: white;
                        border: none;
                        padding: 4px 8px;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #666;
                    }
                """)
                actions_button.clicked.connect(
                    lambda checked, wid=workflow_id: self.edit_workflow(wid)
                )
                self.workflow_table.setCellWidget(row, 6, actions_button)
                
                # Update counters
                total_count += 1
                if trigger_config.enabled:
                    active_count += 1
                else:
                    inactive_count += 1
                    
                # Store workflow ID in row for reference
                self.workflow_table.item(row, 1).setData(Qt.ItemDataRole.UserRole, workflow_id)
                self.workflow_table.item(row, 1).setData(Qt.ItemDataRole.UserRole + 1, trigger_id)
        
        # Update statistics
        self.total_label.setText(f"Total Workflows: {total_count}")
        self.active_label.setText(f"Active: {active_count}")
        self.inactive_label.setText(f"Inactive: {inactive_count}")
        self.today_label.setText(f"Triggered Today: {today_count}")
        
    def get_trigger_config_summary(self, trigger_config) -> str:
        """Generate a summary of trigger configuration"""
        trigger_type = trigger_config.trigger_type.value
        filters = trigger_config.filters
        schedule = trigger_config.schedule
        
        if trigger_type == "manual":
            return "Manual trigger only"
        elif trigger_type == "beacon_connection":
            parts = []
            if filters.get('cidr_ranges'):
                parts.append(f"CIDR: {', '.join(filters['cidr_ranges'][:2])}")
            if filters.get('beacon_pattern') and filters['beacon_pattern'] != '*':
                parts.append(f"Pattern: {filters['beacon_pattern']}")
            return ', '.join(parts) if parts else "All beacons"
        elif trigger_type == "beacon_status":
            return f"Status changes"
        elif trigger_type == "scheduled":
            if schedule.get('type') == 'interval':
                return f"Every {schedule.get('interval_minutes', 0)} minutes"
            elif schedule.get('type') == 'cron':
                return f"Cron: {schedule.get('cron_expression', 'N/A')}"
        
        return "Custom configuration"
        
    def toggle_trigger(self, workflow_id: str, trigger_id: str, enabled: bool):
        """Enable or disable a trigger"""
        if workflow_id in self.trigger_service.active_triggers:
            if trigger_id in self.trigger_service.active_triggers[workflow_id]:
                self.trigger_service.active_triggers[workflow_id][trigger_id].enabled = enabled
                
                # Emit appropriate signal
                if enabled:
                    self.workflow_enabled.emit(workflow_id)
                else:
                    self.workflow_disabled.emit(workflow_id)
                    
                # Refresh statistics
                self.load_workflows()
                
    def enable_all_workflows(self):
        """Enable all workflow triggers"""
        for workflow_id, triggers in self.trigger_service.active_triggers.items():
            for trigger_id, config in triggers.items():
                config.enabled = True
        self.load_workflows()
        
    def disable_all_workflows(self):
        """Disable all workflow triggers"""
        for workflow_id, triggers in self.trigger_service.active_triggers.items():
            for trigger_id, config in triggers.items():
                config.enabled = False
        self.load_workflows()
        
    def edit_workflow(self, workflow_id: str):
        """Open workflow for editing"""
        # Load the workflow in the editor (which will also switch to canvas view)
        if self.workflow_editor and hasattr(self.workflow_editor, 'load_workflow_by_id'):
            self.workflow_editor.load_workflow_by_id(workflow_id)
            
    def show_context_menu(self, position):
        """Show context menu for workflow actions"""
        item = self.workflow_table.itemAt(position)
        if not item:
            return
            
        row = item.row()
        workflow_id = self.workflow_table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        trigger_id = self.workflow_table.item(row, 1).data(Qt.ItemDataRole.UserRole + 1)
        
        menu = QMenu()
        
        # Toggle enable/disable
        status_checkbox = self.workflow_table.cellWidget(row, 0)
        if status_checkbox and status_checkbox.isChecked():
            disable_action = menu.addAction("Disable Trigger")
            disable_action.triggered.connect(
                lambda: self.toggle_trigger(workflow_id, trigger_id, False)
            )
        else:
            enable_action = menu.addAction("Enable Trigger")
            enable_action.triggered.connect(
                lambda: self.toggle_trigger(workflow_id, trigger_id, True)
            )
            
        menu.addSeparator()
        
        # Edit workflow
        edit_action = menu.addAction("Edit Workflow")
        edit_action.triggered.connect(lambda: self.edit_workflow(workflow_id))
        
        # Remove trigger
        remove_action = menu.addAction("Remove Trigger")
        remove_action.triggered.connect(
            lambda: self.remove_trigger(workflow_id, trigger_id)
        )
        
        menu.exec(self.workflow_table.mapToGlobal(position))
        
    def remove_trigger(self, workflow_id: str, trigger_id: str):
        """Remove a trigger from a workflow"""
        reply = QMessageBox.question(
            self, 
            "Remove Trigger",
            "Are you sure you want to remove this trigger?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.trigger_service.remove_trigger(workflow_id, trigger_id)
            self.load_workflows()
            
    def on_trigger_registered(self, workflow_id: str, trigger_id: str):
        """Handle new trigger registration"""
        self.load_workflows()
        
    def on_trigger_removed(self, workflow_id: str, trigger_id: str):
        """Handle trigger removal"""
        self.load_workflows()
        
    def on_workflow_triggered(self, workflow_id: str, context: dict):
        """Handle workflow trigger event"""
        # Find the workflow in the table and update its last triggered time
        for row in range(self.workflow_table.rowCount()):
            stored_id = self.workflow_table.item(row, 1).data(Qt.ItemDataRole.UserRole)
            if stored_id == workflow_id:
                # Update last triggered time
                now = datetime.now()
                self.workflow_table.item(row, 4).setText(
                    now.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                # Increment counter
                count_item = self.workflow_table.item(row, 5)
                current_count = int(count_item.text())
                count_item.setText(str(current_count + 1))
                
                # Update today's count
                self.update_statistics()
                break
                
    def update_last_triggered_times(self):
        """Update the display of last triggered times"""
        # This is called periodically to update relative times if needed
        pass
        
    def update_statistics(self):
        """Update the statistics display"""
        # Recalculate and update statistics
        today = datetime.now().date()
        today_count = 0
        
        for workflow_id, triggers in self.trigger_service.active_triggers.items():
            for trigger_id, config in triggers.items():
                if config.last_triggered and config.last_triggered.date() == today:
                    today_count += 1
                    
        self.today_label.setText(f"Triggered Today: {today_count}")