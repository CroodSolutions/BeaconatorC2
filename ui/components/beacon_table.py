from PyQt6.QtWidgets import (QTableView, QHeaderView, QSizePolicy)
from PyQt6.QtCore import (pyqtSignal, QAbstractTableModel, Qt, QModelIndex, QVariant, QTimer)
from PyQt6.QtGui import QFont, QFontDatabase, QColor
from utils import FontManager
from typing import List, Dict, Any

class BeaconTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._beacons: List[Dict[str, Any]] = []
        self._headers = ["Beacon ID", "Computer Name", "Status", "Last Check-in"]
        
    def rowCount(self, parent=QModelIndex()):
        return len(self._beacons)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._beacons):
            return QVariant()
            
        beacon = self._beacons[index.row()]
        column = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return beacon.get('beacon_id', '')
            elif column == 1:
                return beacon.get('computer_name', '')
            elif column == 2:
                return beacon.get('status', '')
            elif column == 3:
                return beacon.get('last_checkin', '')
        elif role == Qt.ItemDataRole.BackgroundRole and column == 2:
            status = beacon.get('status', '')
            if status == 'online':
                return QColor('#44e349')
            else:
                return QColor('#e34444')
                
        return QVariant()
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return QVariant()
    
    def update_beacons(self, beacons: List[Dict[str, Any]]):
        self.beginResetModel()
        # Convert agent keys to beacon keys for compatibility
        self._beacons = []
        for beacon in beacons:
            converted_beacon = {
                'beacon_id': beacon.get('beacon_id', beacon.get('beacon_id', '')),
                'computer_name': beacon.get('computer_name', ''),
                'status': beacon.get('status', ''),
                'last_checkin': beacon.get('last_checkin', '')
            }
            self._beacons.append(converted_beacon)
        self.endResetModel()
    
    def get_beacon_id(self, row: int) -> str:
        if 0 <= row < len(self._beacons):
            return self._beacons[row].get('beacon_id', '')
        return ''

class BeaconTableWidget(QTableView):
    beacon_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._selected_beacon_id = None
        self._column_widths_cached = False
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._resize_columns_to_contents)
        
        # Create and set model
        self.model = BeaconTableModel()
        self.setModel(self.model)
        
        self.setup_table()
        
        # Set fixed size constraints to prevent dynamic resizing
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            FontManager().add_relative_font_widget(self, 0)
        except:
            pass

    def setup_table(self):
        # Font is already set by FontManager in __init__, no need to override it
        # If FontManager wasn't available, Qt will use system default which is fine
            
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        
        # Configure headers
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verticalHeader().setVisible(False)
        
        # Connect selection signal
        self.selectionModel().selectionChanged.connect(self.on_selection_changed)
        
        # Preserve original styling with bold headers
        base_style = self.styleSheet()
        style = """
            QTableView::item:selected {
                background-color: #e3f2fd;
                color: black;  
            }
            QTableView::item:selected:focus {
                background-color: #e3f2fd;
                color: black;
            }
            QHeaderView::section {
                font-weight: bold;
            }
        """
        self.setStyleSheet(base_style + style)

    def update_beacons(self, beacons: list):
        current_selection = self.selected_beacon_id
        
        # Disable updates during bulk operation
        self.setUpdatesEnabled(False)
        
        # Update model data
        self.model.update_beacons(beacons)
        
        # Restore selection if beacon still exists
        if current_selection:
            for row in range(self.model.rowCount()):
                if self.model.get_beacon_id(row) == current_selection:
                    self.selectRow(row)
                    break
        
        # Always resize columns to content for proper display
        self._update_timer.start(50)  # 50ms delay to batch updates
        
        self.setUpdatesEnabled(True)
    
    def _resize_columns_to_contents(self):
        """Resize columns to fit content properly"""
        self.resizeColumnsToContents()
        
        # Keep last column stretched but ensure others fit content
        header = self.horizontalHeader()
        for i in range(header.count() - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(header.count() - 1, QHeaderView.ResizeMode.Stretch)

    def on_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            new_beacon_id = self.model.get_beacon_id(row)
            
            # If clicking the same row again, don't change anything
            if new_beacon_id == self.selected_beacon_id:
                return
                
            self.selected_beacon_id = new_beacon_id
            self.beacon_selected.emit(self.selected_beacon_id)

    def highlight_selected_row(self):
        """Optimized selection highlighting using CSS instead of manual iteration"""
        # The CSS styling in setup_table() handles selection highlighting efficiently
        # No need for manual row iteration - Qt handles this automatically
        pass
    
    
    @property
    def selected_beacon_id(self):
        """Get the currently selected beacon ID"""
        return self._selected_beacon_id
        
    @selected_beacon_id.setter
    def selected_beacon_id(self, value):
        """Set the currently selected beacon ID"""
        self._selected_beacon_id = value