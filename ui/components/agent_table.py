from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QFont, QFontDatabase, QColor
from utils import FontManager

class AgentTableWidget(QTableWidget):
    agent_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.selected_agent_id = None
        self.setup_table()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        # Try to use FontManager, but don't fail if it's not available
        try:
            FontManager().add_relative_font_widget(self, 0)
        except:
            pass

    def sizeHint(self):
        width = sum([self.horizontalHeader().sectionSize(i) 
                    for i in range(self.columnCount())])
        height = self.verticalHeader().length() + self.horizontalHeader().height()
        
        calculated_width = min(width + 3, 800)  
        return QSize(calculated_width, height)

    def setup_table(self):
        # Try to set font, but use default if not available
        try:
            families = QFontDatabase.families()
            if len(families) > 1:
                self.setFont(QFont(families[1]))
        except:
            pass
            
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Agent ID", "Computer Name", "Status", "Last Check-in"])
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Disable the default selection highlight
        base_style = self.styleSheet()
        style = """
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: black;  
            }
            QTableWidget::item:selected:focus {
                background-color: #e3f2fd;
                color: black;
            }
        """
        self.setStyleSheet(base_style + style)

    def update_agents(self, agents: list):
        current_selection = self.selected_agent_id
        self.setRowCount(0)  # Clear existing rows
        for agent in agents:
            row = self.rowCount()
            self.insertRow(row)
            
            # Add items to the row
            self.setItem(row, 0, QTableWidgetItem(agent['agent_id']))
            self.setItem(row, 1, QTableWidgetItem(agent['computer_name']))
            self.setItem(row, 2, QTableWidgetItem(agent['status']))
            self.setItem(row, 3, QTableWidgetItem(agent['last_checkin']))
            
            # Set status color
            status_item = self.item(row, 2)
            if agent['status'] == 'online':
                status_item.setBackground(QColor('#44e349'))  # Light green
            else:
                status_item.setBackground(QColor('#e34444'))  # Light red
                
            # If this is the selected agent, select the row
            if agent['agent_id'] == current_selection:
                self.selectRow(row)
        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)

    def on_selection_changed(self):
        selected_items = self.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            new_agent_id = self.item(row, 0).text()
            
            # If clicking the same row again, don't change anything
            if new_agent_id == self.selected_agent_id:
                return
                
            self.selected_agent_id = new_agent_id
            self.agent_selected.emit(self.selected_agent_id)

    def highlight_selected_row(self):
        for row in range(self.rowCount()):
            agent_id_item = self.item(row, 0)
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    if agent_id_item.text() == self.selected_agent_id:
                        item.setBackground(QColor('#e3f2fd'))  # Light blue background
                    else:
                        # Reset background but maintain status color in status column
                        if col == 2:  # Status column
                            status = self.item(row, 2).text()
                            color = QColor('#44e349') if status == 'online' else QColor('#e34444')
                            item.setBackground(color)
                        else:
                            item.setBackground(QColor('#878a87'))