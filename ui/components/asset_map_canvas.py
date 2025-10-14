#!/usr/bin/env python3
"""
Asset map canvas for visualizing beacon connections and network topology.
Based on CustomWorkflowCanvas with simplified functionality and darker theme.
"""

import math
import time
from typing import List, Optional, Dict, Any
from PyQt6.QtWidgets import QWidget, QMenu, QInputDialog
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QWheelEvent, QMouseEvent, QPaintEvent, QIcon, QPixmap, QContextMenuEvent

from services.receivers.base_receiver import ReceiverStatus
from database import BeaconRepository


class AssetNode:
    """Node representing a beacon or network asset on the map"""

    def __init__(self, x: float, y: float, width: float = 64, height: float = 100,
                 title: str = "Asset", node_type: str = "beacon", asset_data: Dict[str, Any] = None,
                 status: str = "online"):
        # Position and size (adjusted for icon-based rendering)
        self.x = x
        self.y = y
        self.icon_size = 48  # Size of the icon
        self.width = width  # Total width including text
        self.height = height  # Total height including icon and text

        # Asset identity
        self.title = title
        self.node_type = node_type  # "beacon", "server", "network", "receiver"
        self.asset_data = asset_data or {}
        self.node_id = f"{node_type}_{id(self)}"
        self.status = status  # "online", "offline", "running", "stopped"

        # Interaction state
        self.selected = False
        self.is_hovered = False

        # Visual properties
        self.text_color = QColor(220, 220, 220)
        self.selected_color = QColor(100, 140, 200)
        self.icon_path = None
        self.icon_pixmap = None

        # Set icon and colors based on node type and status
        self._set_icon_and_colors()

        # Connections
        self.connections_in = []
        self.connections_out = []

    def _set_icon_and_colors(self):
        """Set icon path and colors based on asset type and status"""
        # Set icon based on node type
        if self.node_type == "beacon":
            self.icon_path = "resources/building-broadcast-tower.svg"
            self.text_color = QColor(220, 220, 220)  # Always bright and readable
        elif self.node_type == "receiver":
            self.icon_path = "resources/server-bolt.svg"
            self.text_color = QColor(220, 220, 220)  # Always bright and readable
        elif self.node_type == "server":
            self.icon_path = "resources/server-bolt.svg"
            self.text_color = QColor(220, 220, 220)
        elif self.node_type == "network":
            self.icon_path = "resources/route-square-2.svg"
            self.text_color = QColor(220, 220, 220)
        else:
            self.icon_path = "resources/route-square-2.svg"
            self.text_color = QColor(220, 220, 220)

        # Load the icon
        self._load_icon()

    def _load_icon(self):
        """Load icon from file path - stores QIcon for resolution-independent rendering"""
        if self.icon_path:
            try:
                # Store QIcon instead of pixmap for resolution-independent scaling
                self.icon = QIcon(self.icon_path)
                # Keep pixmap reference for backward compatibility but will regenerate as needed
                self.icon_pixmap = None
            except Exception as e:
                print(f"Failed to load icon {self.icon_path}: {e}")
                self.icon = None
                self.icon_pixmap = None
        else:
            self.icon = None
            self.icon_pixmap = None

    def get_scaled_icon_pixmap(self, size: int) -> 'QPixmap':
        """Get icon pixmap at specified size for crisp rendering at any zoom level"""
        if self.icon:
            return self.icon.pixmap(QSize(size, size))
        return None

    def get_rect(self) -> QRectF:
        """Get the bounding rectangle of this node"""
        return QRectF(self.x, self.y, self.width, self.height)

    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is inside this node"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)

    def move_to(self, x: float, y: float):
        """Move the node to a new position"""
        self.x = x
        self.y = y

    def update_status(self, status: str):
        """Update node status and refresh colors"""
        self.status = status
        self._set_icon_and_colors()

    def get_center(self) -> QPointF:
        """Get the center point of this node (center of icon)"""
        return QPointF(self.x + self.width / 2, self.y + self.icon_size / 2)

    def get_icon_rect(self) -> QRectF:
        """Get the rectangle for the icon (centered horizontally)"""
        icon_x = self.x + (self.width - self.icon_size) / 2
        return QRectF(icon_x, self.y, self.icon_size, self.icon_size)

    def get_connection_point(self, from_point: QPointF) -> QPointF:
        """
        Get the connection point at the edge of the icon background circle

        Args:
            from_point: The point the connection is coming from

        Returns:
            Point at the edge of the icon circle facing the from_point
        """
        center = self.get_center()

        # Calculate angle from center to from_point
        dx = from_point.x() - center.x()
        dy = from_point.y() - center.y()

        if abs(dx) < 0.01 and abs(dy) < 0.01:
            # Points are the same, return center
            return center

        # Calculate distance
        distance = math.sqrt(dx * dx + dy * dy)

        # Normalize direction
        norm_dx = dx / distance
        norm_dy = dy / distance

        # Icon boundary radius - small padding around icon edge
        boundary_radius = self.icon_size / 2 + 5

        # Calculate point at boundary facing from_point
        # We add the normalized direction vector to move from center towards from_point
        boundary_x = center.x() + norm_dx * boundary_radius
        boundary_y = center.y() + norm_dy * boundary_radius

        return QPointF(boundary_x, boundary_y)

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


class AssetConnection:
    """Connection between two asset nodes"""

    def __init__(self, start_node: AssetNode, end_node: AssetNode,
                 connection_type: str = "network", label: str = ""):
        self.start_node = start_node
        self.end_node = end_node
        self.connection_type = connection_type  # "network", "c2", "lateral"
        self.label = label

        # Visual properties
        self.color = self._get_color_for_type(connection_type)
        self.width = 2
        self.selected = False

        # Add this connection to nodes
        start_node.add_connection_out(self)
        end_node.add_connection_in(self)

        # Unique identifier
        self.connection_id = f"conn_{id(self)}"

    def _get_color_for_type(self, connection_type: str) -> QColor:
        """Get color based on connection type"""
        if connection_type == "network":
            return QColor(80, 120, 180)  # Blue
        elif connection_type == "c2":
            return QColor(180, 80, 80)  # Red
        elif connection_type == "lateral":
            return QColor(180, 180, 80)  # Yellow
        else:
            return QColor(120, 120, 120)  # Gray

    def get_start_point(self) -> QPointF:
        """Get the connection start point at the edge of the start node"""
        # Get end node center to calculate direction
        end_center = self.end_node.get_center()
        return self.start_node.get_connection_point(end_center)

    def get_end_point(self) -> QPointF:
        """Get the connection end point at the edge of the end node"""
        # Get start node center to calculate direction
        start_center = self.start_node.get_center()
        return self.end_node.get_connection_point(start_center)

    def get_bounding_rect(self) -> QRectF:
        """Get bounding rectangle for this connection"""
        start = self.get_start_point()
        end = self.get_end_point()
        return QRectF(start, end).normalized().adjusted(-10, -10, 10, 10)

    def cleanup(self):
        """Clean up connection references"""
        self.start_node.remove_connection(self)
        self.end_node.remove_connection(self)


class AssetMapCanvas(QWidget):
    """High-performance canvas for displaying asset maps with pan/zoom support"""

    # Signals
    node_selected = pyqtSignal(object)  # Signal when a node is selected (emits node object)
    node_moved = pyqtSignal(object, QPointF)  # Signal when a node is moved

    def __init__(self, beacon_repository: Optional[BeaconRepository] = None, parent=None):
        super().__init__(parent)

        # Repository reference for command execution
        self.beacon_repository = beacon_repository

        # Canvas data
        self.nodes: List[AssetNode] = []
        self.connections: List[AssetConnection] = []
        self.selected_node: Optional[AssetNode] = None

        # Viewport state
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        # Interaction state
        self.is_panning = False
        self.is_dragging_node = False
        self.last_mouse_pos = QPoint()
        self.drag_start_pos = QPoint()
        self.drag_offset = QPointF()

        # Visual settings - darker theme for asset mapping
        self.background_color = QColor(20, 20, 25)  # Very dark blue-gray
        self.grid_color = QColor(35, 35, 40)  # Slightly lighter for grid
        self.grid_size = 25

        # Dot matrix settings
        self.dot_size = 2
        self.dot_color = QColor(45, 45, 50)  # Subtle dots
        self.dot_opacity = 0.5

        # Performance settings
        self.enable_grid = True
        self.enable_antialiasing = True

        # Paint state flag
        self._is_painting = False

        # Set widget properties
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        # Animation timer for cycling pending command indicator
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update)
        self.animation_timer.start(255)  # Update every 255ms for smooth cycling

    def add_node(self, node_type: str, position: QPointF, title: str = "Asset",
                 asset_data: Dict[str, Any] = None) -> AssetNode:
        """Add a new node to the canvas"""
        # Convert to world coordinates and snap to grid
        world_pos = self.screen_to_world(position)
        snapped_pos = self.snap_to_grid(world_pos)

        # Create node
        node = AssetNode(
            snapped_pos.x(), snapped_pos.y(),
            title=title,
            node_type=node_type,
            asset_data=asset_data
        )

        self.nodes.append(node)
        self.update()
        return node

    def add_connection(self, start_node: AssetNode, end_node: AssetNode,
                      connection_type: str = "network", label: str = "") -> AssetConnection:
        """Add a connection between two nodes"""
        connection = AssetConnection(start_node, end_node, connection_type, label)
        self.connections.append(connection)
        self.update()
        return connection

    def remove_node(self, node: AssetNode):
        """Remove a node and its connections"""
        # Remove all connections involving this node
        connections_to_remove = [c for c in self.connections
                                if c.start_node == node or c.end_node == node]
        for connection in connections_to_remove:
            connection.cleanup()
            self.connections.remove(connection)

        # Remove the node
        if node in self.nodes:
            self.nodes.remove(node)

        if self.selected_node == node:
            self.selected_node = None

        self.update()

    def clear(self):
        """Clear all nodes and connections"""
        self.nodes.clear()
        self.connections.clear()
        self.selected_node = None
        self.update()

    # Coordinate transformation methods
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

    def snap_to_grid(self, pos: QPointF) -> QPointF:
        """Snap position to grid"""
        return QPointF(
            round(pos.x() / self.grid_size) * self.grid_size,
            round(pos.y() / self.grid_size) * self.grid_size
        )

    def get_visible_rect(self) -> QRectF:
        """Get the visible rectangle in world coordinates"""
        top_left = self.screen_to_world(QPointF(0, 0))
        bottom_right = self.screen_to_world(QPointF(self.width(), self.height()))
        return QRectF(top_left, bottom_right)

    # Mouse event handlers
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if event.button() == Qt.MouseButton.MiddleButton:
            # Start panning
            self.is_panning = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

        elif event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on a node
            world_pos = self.screen_to_world(QPointF(event.pos()))
            clicked_node = self.get_node_at(world_pos.x(), world_pos.y())

            if clicked_node:
                # Start dragging node
                self.is_dragging_node = True
                self.selected_node = clicked_node
                self.drag_offset = QPointF(
                    world_pos.x() - clicked_node.x,
                    world_pos.y() - clicked_node.y
                )
                clicked_node.selected = True
                self.node_selected.emit(clicked_node)
                self.update()
            else:
                # Deselect
                if self.selected_node:
                    self.selected_node.selected = False
                    self.selected_node = None
                    self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move"""
        if self.is_panning:
            # Pan the canvas
            delta = event.pos() - self.last_mouse_pos
            self.pan_offset += QPointF(delta.x() / self.zoom_factor,
                                      delta.y() / self.zoom_factor)
            self.last_mouse_pos = event.pos()
            self.update()

        elif self.is_dragging_node and self.selected_node:
            # Drag the node
            world_pos = self.screen_to_world(QPointF(event.pos()))
            new_pos = self.snap_to_grid(QPointF(
                world_pos.x() - self.drag_offset.x(),
                world_pos.y() - self.drag_offset.y()
            ))
            self.selected_node.move_to(new_pos.x(), new_pos.y())
            self.node_moved.emit(self.selected_node, new_pos)
            self.update()
        else:
            # Check for node hover
            world_pos = self.screen_to_world(QPointF(event.pos()))
            hovered_node = self.get_node_at(world_pos.x(), world_pos.y())

            # Update hover state
            for node in self.nodes:
                node.is_hovered = (node == hovered_node)

            if hovered_node:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

        elif event.button() == Qt.MouseButton.LeftButton:
            if self.is_dragging_node:
                self.is_dragging_node = False

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle right-click context menu"""
        if not self.beacon_repository:
            return

        # Convert click position to world coordinates
        world_pos = self.screen_to_world(QPointF(event.pos()))
        clicked_node = self.get_node_at(world_pos.x(), world_pos.y())

        # Only show context menu for beacon nodes
        if clicked_node and clicked_node.node_type == "beacon":
            beacon_id = clicked_node.asset_data.get('beacon_id')
            if beacon_id:
                self._show_beacon_context_menu(event.globalPos(), beacon_id, clicked_node.title)

    def _show_beacon_context_menu(self, pos: QPoint, beacon_id: str, beacon_name: str):
        """Show context menu for beacon node"""
        menu = QMenu(self)

        # Add "Execute Command" action
        execute_action = menu.addAction("Execute Command")

        # Show the menu and get the selected action
        action = menu.exec(pos)

        if action == execute_action:
            self._execute_command_on_beacon(beacon_id, beacon_name)

    def _execute_command_on_beacon(self, beacon_id: str, beacon_name: str):
        """Prompt for and execute a command on the selected beacon"""
        # Show input dialog to get command
        command, ok = QInputDialog.getText(
            self,
            "Execute Command",
            f"Enter command for {beacon_name} ({beacon_id}):",
            text=""
        )

        if ok and command:
            # Queue the command via the beacon repository
            self.beacon_repository.update_beacon_command(beacon_id, command)

            # Update the node's pending_command immediately for visual feedback
            node = self.find_node_by_id(beacon_id, "beacon")
            if node:
                node.asset_data['pending_command'] = command

            # Trigger repaint to show the cycling indicator immediately
            self.update()

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

    def find_node_by_id(self, asset_id: str, node_type: str) -> Optional[AssetNode]:
        """Find a node by its asset ID and type"""
        for node in self.nodes:
            if node.node_type == node_type:
                if node_type == "beacon" and node.asset_data.get('beacon_id') == asset_id:
                    return node
                elif node_type == "receiver" and node.asset_data.get('receiver_id') == asset_id:
                    return node
        return None

    def populate_from_data(self, beacons: list, receivers: list):
        """
        Populate the asset map using receiver lanes with sub-grids layout

        Args:
            beacons: List of Beacon objects from the database
            receivers: List of receiver instances from ReceiverManager
        """
        # Clear existing nodes and connections
        self.clear()

        # Track nodes by their IDs for connection creation
        receiver_nodes = {}
        beacon_nodes = {}

        # Group beacons by receiver_id
        beacons_by_receiver = {}
        unassigned_beacons = []

        for beacon in beacons:
            receiver_id = beacon.receiver_id
            if receiver_id:
                if receiver_id not in beacons_by_receiver:
                    beacons_by_receiver[receiver_id] = []
                beacons_by_receiver[receiver_id].append(beacon)
            else:
                unassigned_beacons.append(beacon)

        # Layout constants
        start_x = 100
        start_y = 150
        receiver_x = start_x
        beacon_start_x = 350
        horizontal_spacing = 200
        vertical_spacing = 150
        group_spacing = 80  # Extra space between receiver groups

        current_y = start_y

        # Process each receiver and its beacons
        for receiver in receivers:
            receiver_id = receiver.receiver_id if hasattr(receiver, 'receiver_id') else str(id(receiver))
            receiver_name = receiver.name if hasattr(receiver, 'name') else f"Receiver {id(receiver)}"

            # Determine status
            status = "running" if hasattr(receiver, 'status') and receiver.status == ReceiverStatus.RUNNING else "stopped"

            # Get receiver type and port
            receiver_type = "Unknown"
            receiver_port = ""
            if hasattr(receiver, 'config') and hasattr(receiver.config, 'receiver_type'):
                if hasattr(receiver.config.receiver_type, 'value'):
                    receiver_type = receiver.config.receiver_type.value.upper()
                else:
                    receiver_type = str(receiver.config.receiver_type).upper()

                if hasattr(receiver.config, 'port'):
                    receiver_port = str(receiver.config.port)

            display_type = f"{receiver_type}: {receiver_port}" if receiver_port else receiver_type

            # Create receiver node
            receiver_node = AssetNode(
                receiver_x, current_y,
                width=140, height=120,
                title=receiver_name,
                node_type="receiver",
                asset_data={
                    'receiver_id': receiver_id,
                    'receiver_type': display_type
                },
                status=status
            )

            self.nodes.append(receiver_node)
            receiver_nodes[receiver_id] = receiver_node

            # Get beacons for this receiver
            receiver_beacons = beacons_by_receiver.get(receiver_id, [])
            beacon_count = len(receiver_beacons)

            # Determine grid columns based on beacon count
            if beacon_count <= 2:
                cols = 1
            elif beacon_count <= 4:
                cols = 2
            elif beacon_count <= 9:
                cols = 3
            else:
                cols = 4

            # Calculate beacon positions in sub-grid
            beacon_grid_y = current_y
            for i, beacon in enumerate(receiver_beacons):
                row = i // cols
                col = i % cols

                beacon_x = beacon_start_x + col * horizontal_spacing
                beacon_y = beacon_grid_y + row * vertical_spacing

                # Create beacon node
                beacon_node = AssetNode(
                    beacon_x, beacon_y,
                    width=120, height=110,
                    title=beacon.computer_name,
                    node_type="beacon",
                    asset_data={
                        'beacon_id': beacon.beacon_id,
                        'ip_address': beacon.ip_address if hasattr(beacon, 'ip_address') else None,
                        'receiver_id': receiver_id,
                        'pending_command': beacon.pending_command if hasattr(beacon, 'pending_command') else None
                    },
                    status=beacon.status
                )

                self.nodes.append(beacon_node)
                beacon_nodes[beacon.beacon_id] = beacon_node

                # Create connection
                connection = AssetConnection(
                    beacon_node,
                    receiver_node,
                    connection_type="c2",
                    label=""
                )
                self.connections.append(connection)

            # Calculate lane height (grid height or minimum)
            if beacon_count > 0:
                rows = (beacon_count + cols - 1) // cols
                lane_height = max(vertical_spacing * rows, 120)
            else:
                lane_height = 120

            # Move Y position down for next receiver group
            current_y += lane_height + group_spacing

        # Handle unassigned beacons (if any) - place them at the bottom
        if unassigned_beacons:
            current_y += group_spacing
            for i, beacon in enumerate(unassigned_beacons):
                beacon_x = beacon_start_x + (i % 3) * horizontal_spacing
                beacon_y = current_y + (i // 3) * vertical_spacing

                beacon_node = AssetNode(
                    beacon_x, beacon_y,
                    width=120, height=110,
                    title=beacon.computer_name,
                    node_type="beacon",
                    asset_data={
                        'beacon_id': beacon.beacon_id,
                        'ip_address': beacon.ip_address if hasattr(beacon, 'ip_address') else None,
                        'receiver_id': None,
                        'pending_command': beacon.pending_command if hasattr(beacon, 'pending_command') else None
                    },
                    status=beacon.status
                )

                self.nodes.append(beacon_node)
                beacon_nodes[beacon.beacon_id] = beacon_node

        self.update()

    def _calculate_receiver_positions(self, count: int) -> List[QPointF]:
        """Calculate positions for receiver nodes in a vertical line"""
        positions = []
        start_x = 100
        start_y = 150
        spacing = 200

        for i in range(count):
            positions.append(QPointF(start_x, start_y + i * spacing))

        return positions

    def _calculate_beacon_positions(self, beacon_count: int, receiver_count: int) -> List[QPointF]:
        """Calculate positions for beacon nodes in a grid layout"""
        positions = []
        start_x = 400
        start_y = 100
        horizontal_spacing = 200
        vertical_spacing = 150

        # Calculate grid dimensions
        cols = max(3, int((beacon_count ** 0.5) + 0.5))
        rows = (beacon_count + cols - 1) // cols  # Ceiling division

        for i in range(beacon_count):
            row = i // cols
            col = i % cols
            x = start_x + col * horizontal_spacing
            y = start_y + row * vertical_spacing
            positions.append(QPointF(x, y))

        return positions

    def refresh_from_data(self, beacons: list, receivers: list):
        """
        Refresh the asset map from updated data without recreating everything

        Args:
            beacons: List of Beacon objects from the database
            receivers: List of receiver instances from ReceiverManager
        """
        # Update existing nodes or add new ones
        existing_beacon_ids = {node.asset_data.get('beacon_id') for node in self.nodes if node.node_type == "beacon"}
        existing_receiver_ids = {node.asset_data.get('receiver_id') for node in self.nodes if node.node_type == "receiver"}

        # Update receiver nodes
        for receiver in receivers:
            receiver_id = receiver.receiver_id if hasattr(receiver, 'receiver_id') else None
            if receiver_id:
                node = self.find_node_by_id(receiver_id, "receiver")
                if node:
                    # Update existing node status - receiver.status is a ReceiverStatus enum
                    new_status = "running" if hasattr(receiver, 'status') and receiver.status == ReceiverStatus.RUNNING else "stopped"
                    if node.status != new_status:
                        node.update_status(new_status)

        # Update beacon nodes
        for beacon in beacons:
            beacon_id = beacon.beacon_id
            node = self.find_node_by_id(beacon_id, "beacon")

            if node:
                # Update existing node
                if node.status != beacon.status:
                    node.update_status(beacon.status)
                # Update IP if changed
                if hasattr(beacon, 'ip_address'):
                    node.asset_data['ip_address'] = beacon.ip_address
                # Update pending command status
                if hasattr(beacon, 'pending_command'):
                    node.asset_data['pending_command'] = beacon.pending_command
            else:
                # New beacon - do a full repopulate
                self.populate_from_data(beacons, receivers)
                return

        # Remove nodes for beacons/receivers that no longer exist
        current_beacon_ids = {beacon.beacon_id for beacon in beacons}
        current_receiver_ids = {receiver.receiver_id if hasattr(receiver, 'receiver_id') else None for receiver in receivers}

        nodes_to_remove = []
        for node in self.nodes:
            if node.node_type == "beacon" and node.asset_data.get('beacon_id') not in current_beacon_ids:
                nodes_to_remove.append(node)
            elif node.node_type == "receiver" and node.asset_data.get('receiver_id') not in current_receiver_ids:
                nodes_to_remove.append(node)

        for node in nodes_to_remove:
            self.remove_node(node)

        self.update()

    def get_node_at(self, x: float, y: float) -> Optional[AssetNode]:
        """Get node at given world coordinates"""
        for node in reversed(self.nodes):  # Check from top to bottom
            if node.contains_point(x, y):
                return node
        return None

    # Paint methods
    def paintEvent(self, event: QPaintEvent):
        """Main paint event"""
        if self._is_painting:
            return

        self._is_painting = True
        painter = QPainter(self)

        # Enable antialiasing
        if self.enable_antialiasing:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        try:
            # Fill background
            painter.fillRect(self.rect(), self.background_color)

            # Draw grid
            if self.enable_grid:
                self._draw_grid(painter)

            # Draw connections
            self._draw_connections(painter)

            # Draw nodes
            self._draw_nodes(painter)

        finally:
            painter.end()
            self._is_painting = False

    def _draw_grid(self, painter: QPainter):
        """Draw the background dot matrix grid"""
        dot_color = QColor(self.dot_color)
        dot_color.setAlphaF(self.dot_opacity)
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.PenStyle.NoPen)

        # Get visible area
        visible_rect = self.get_visible_rect()

        # Calculate grid bounds
        grid_spacing = self.grid_size
        padding = grid_spacing * 2
        start_x = int((visible_rect.left() - padding) / grid_spacing) * grid_spacing
        start_y = int((visible_rect.top() - padding) / grid_spacing) * grid_spacing
        end_x = visible_rect.right() + padding
        end_y = visible_rect.bottom() + padding

        # Calculate dot size based on zoom
        screen_dot_size = max(1.0, self.dot_size * self.zoom_factor)

        if screen_dot_size < 0.5:
            return

        # Draw dots
        widget_rect = QRectF(0, 0, self.width(), self.height())
        dot_radius = screen_dot_size

        y = start_y
        dots_drawn = 0
        max_dots = 10000

        while y <= end_y and dots_drawn < max_dots:
            x = start_x
            while x <= end_x and dots_drawn < max_dots:
                screen_pos = self.world_to_screen(QPointF(x, y))

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

        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_connections(self, painter: QPainter):
        """Draw all connections between nodes"""
        visible_rect = self.get_visible_rect()

        for connection in self.connections:
            # Visibility culling
            conn_rect = connection.get_bounding_rect()
            if not visible_rect.intersects(conn_rect):
                continue

            # Get connection points
            start_point = connection.get_start_point()
            end_point = connection.get_end_point()

            # Convert to screen coordinates
            screen_start = self.world_to_screen(start_point)
            screen_end = self.world_to_screen(end_point)

            # Draw line
            painter.setPen(QPen(connection.color, 2))
            painter.drawLine(screen_start, screen_end)

            # Draw arrow head
            self._draw_arrow_head(painter, screen_start, screen_end)

    def _draw_arrow_head(self, painter: QPainter, start: QPointF, end: QPointF):
        """Draw an arrow head at the end of the connection"""
        dx = end.x() - start.x()
        dy = end.y() - start.y()

        if abs(dx) < 5 and abs(dy) < 5:
            return

        angle = math.atan2(dy, dx)
        arrow_length = 10
        arrow_degrees = math.pi / 6

        arrow_p1 = QPointF(
            end.x() - arrow_length * math.cos(angle - arrow_degrees),
            end.y() - arrow_length * math.sin(angle - arrow_degrees)
        )

        arrow_p2 = QPointF(
            end.x() - arrow_length * math.cos(angle + arrow_degrees),
            end.y() - arrow_length * math.sin(angle + arrow_degrees)
        )

        painter.drawLine(end, arrow_p1)
        painter.drawLine(end, arrow_p2)

    def _draw_nodes(self, painter: QPainter):
        """Draw all nodes as icons with text labels"""
        visible_rect = self.get_visible_rect()

        for node in self.nodes:
            # Visibility culling
            node_rect = node.get_rect()
            if not visible_rect.intersects(node_rect):
                continue

            # Save painter state
            painter.save()

            try:
                # Convert icon rect to screen coordinates
                icon_rect_world = node.get_icon_rect()
                screen_icon_rect = QRectF(
                    self.world_to_screen(icon_rect_world.topLeft()),
                    self.world_to_screen(icon_rect_world.bottomRight())
                )

                # Draw icon (always at full opacity)
                # Render icon at appropriate size based on zoom for crisp rendering
                scaled_icon_size = int(screen_icon_rect.width())
                scaled_pixmap = node.get_scaled_icon_pixmap(scaled_icon_size)

                if scaled_pixmap:
                    center = screen_icon_rect.center()

                    # Draw selection/hover highlight if needed
                    if node.selected or node.is_hovered:
                        # Draw a subtle circle behind the icon
                        highlight_color = node.selected_color if node.selected else QColor(150, 150, 150)
                        highlight_color.setAlpha(100)
                        painter.setBrush(QBrush(highlight_color))
                        painter.setPen(Qt.PenStyle.NoPen)

                        # Draw circle slightly larger than icon
                        highlight_radius = screen_icon_rect.width() / 2 * 1.15
                        painter.drawEllipse(center, highlight_radius, highlight_radius)

                    # Draw the icon at scaled size for crisp rendering
                    painter.drawPixmap(screen_icon_rect.toRect(), scaled_pixmap)

                    # Draw status indicator dot in top-right corner
                    status_dot_radius = max(4, screen_icon_rect.width() * 0.12)
                    status_dot_x = screen_icon_rect.right() - status_dot_radius
                    status_dot_y = screen_icon_rect.top() + status_dot_radius

                    # Determine status color
                    if node.status in ("online", "running"):
                        # Check if there's a pending command for beacons
                        has_pending_command = (node.node_type == "beacon" and
                                             node.asset_data.get('pending_command') is not None and
                                             node.asset_data.get('pending_command') != "")

                        if has_pending_command:
                            # Cycle between green and blue for pending commands
                            # Use time-based cycling for smooth animation
                            cycle_phase = int(time.time() * 2) % 2  # 0 or 1, switches every 0.5 seconds
                            if cycle_phase == 0:
                                status_color = QColor(50, 200, 50)  # Green
                            else:
                                status_color = QColor(50, 150, 255)  # Blue
                        else:
                            status_color = QColor(50, 200, 50)  # Green
                    else:  # offline, stopped
                        status_color = QColor(200, 50, 50)  # Red

                    # Draw the status dot
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(status_color))
                    painter.drawEllipse(QPointF(status_dot_x, status_dot_y),
                                       status_dot_radius, status_dot_radius)

                # Draw text labels below icon
                if self.zoom_factor > 0.3:
                    text_start_y = screen_icon_rect.bottom() + 8

                    # Calculate text area width - wider to accommodate longer names and port info
                    # Make it wide enough for typical names, IPs, and "TCP: 8080" format
                    text_area_width = max(300, screen_icon_rect.width() * 5)

                    # Draw node title - always at full brightness for readability
                    painter.setPen(QPen(node.text_color, 1))
                    title_font = QFont("Montserrat", max(8, int(11 * self.zoom_factor)), QFont.Weight.Bold)
                    painter.setFont(title_font)

                    # Center text area around icon
                    title_rect = QRectF(
                        screen_icon_rect.center().x() - text_area_width / 2,
                        text_start_y,
                        text_area_width,
                        25
                    )
                    painter.drawText(title_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, node.title)

                    # Draw additional info based on node type
                    if self.zoom_factor > 0.5:
                        info_font = QFont("Montserrat", max(7, int(9 * self.zoom_factor)))
                        painter.setFont(info_font)
                        # Use full brightness for info text as well
                        painter.setPen(QPen(node.text_color, 1))

                        info_text = ""
                        if node.node_type == "beacon":
                            # Show IP address for beacons
                            ip_address = node.asset_data.get('ip_address')
                            if ip_address:
                                info_text = ip_address
                        elif node.node_type == "receiver":
                            # Show receiver type for receivers (now includes port)
                            receiver_type = node.asset_data.get('receiver_type', 'Receiver')
                            info_text = receiver_type

                        if info_text:
                            info_rect = QRectF(
                                screen_icon_rect.center().x() - text_area_width / 2,
                                text_start_y + 22,
                                text_area_width,
                                20
                            )
                            painter.drawText(info_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, info_text)

            finally:
                painter.restore()
