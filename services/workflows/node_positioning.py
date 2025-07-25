from typing import List, Dict, Any, Tuple
from PyQt6.QtCore import QPointF
import math

from .node_compatibility import ConnectionType
from .node_factory import NodeTemplate


class NodePositionManager:
    """Handles intelligent positioning of new nodes"""
    
    def __init__(self):
        self.default_spacing_x = 200  # Horizontal spacing between nodes
        self.default_spacing_y = 150  # Vertical spacing for branches
        self.collision_padding = 20   # Extra padding to avoid collisions
        self.grid_snap_size = 25      # Snap positions to grid
        
    def calculate_next_position(self, source_node_data: Dict[str, Any], 
                              connection_type: ConnectionType,
                              target_template: NodeTemplate,
                              existing_nodes: List[Dict[str, Any]]) -> QPointF:
        """Calculate optimal position for new node"""
        
        source_pos = QPointF(
            source_node_data["position"]["x"],
            source_node_data["position"]["y"]
        )
        
        # Calculate base position based on connection type
        if connection_type == ConnectionType.SEQUENTIAL:
            base_position = self._calculate_sequential_position(source_pos)
        elif connection_type in [ConnectionType.CONDITIONAL_TRUE, ConnectionType.CONDITIONAL_FALSE]:
            base_position = self._calculate_conditional_position(
                source_pos, connection_type, source_node_data, existing_nodes
            )
        elif connection_type == ConnectionType.PARALLEL:
            base_position = self._calculate_parallel_position(source_pos, existing_nodes)
        else:
            # Default to sequential
            base_position = self._calculate_sequential_position(source_pos)
            
        # Avoid collisions with existing nodes
        final_position = self.avoid_collisions(base_position, existing_nodes)
        
        # Snap to grid
        final_position = self._snap_to_grid(final_position)
        
        return final_position
        
    def _calculate_sequential_position(self, source_pos: QPointF) -> QPointF:
        """Calculate position for sequential (normal flow) connections"""
        return QPointF(
            source_pos.x() + self.default_spacing_x,
            source_pos.y()
        )
        
    def _calculate_conditional_position(self, source_pos: QPointF, 
                                      connection_type: ConnectionType,
                                      source_node_data: Dict[str, Any],
                                      existing_nodes: List[Dict[str, Any]]) -> QPointF:
        """Calculate position for conditional branch connections"""
        
        if connection_type == ConnectionType.CONDITIONAL_TRUE:
            # True branch goes diagonally down-right
            return QPointF(
                source_pos.x() + self.default_spacing_x,
                source_pos.y() + self.default_spacing_y * 0.5
            )
        else:  # CONDITIONAL_FALSE
            # False branch goes diagonally down-right but lower
            return QPointF(
                source_pos.x() + self.default_spacing_x,
                source_pos.y() + self.default_spacing_y * 1.5
            )
            
        
    def _calculate_parallel_position(self, source_pos: QPointF,
                                   existing_nodes: List[Dict[str, Any]]) -> QPointF:
        """Calculate position for parallel execution branches"""
        # Parallel branches go above or below in separate lanes
        
        # Find how many parallel branches already exist
        parallel_count = self._count_parallel_branches(source_pos, existing_nodes)
        
        # Alternate above and below source
        if parallel_count % 2 == 0:
            # Even count: place above
            y_offset = -self.default_spacing_y * ((parallel_count // 2) + 1)
        else:
            # Odd count: place below
            y_offset = self.default_spacing_y * ((parallel_count // 2) + 1)
            
        return QPointF(
            source_pos.x() + self.default_spacing_x,
            source_pos.y() + y_offset
        )
        
    def _count_parallel_branches(self, source_pos: QPointF, 
                               existing_nodes: List[Dict[str, Any]]) -> int:
        """Count existing parallel branches from a source position"""
        count = 0
        
        # Look for nodes in the parallel branch area
        search_x = source_pos.x() + self.default_spacing_x
        search_tolerance = 50  # Tolerance for considering nodes "parallel"
        
        for node in existing_nodes:
            node_pos = QPointF(node["position"]["x"], node["position"]["y"])
            if (abs(node_pos.x() - search_x) < search_tolerance and
                abs(node_pos.y() - source_pos.y()) > self.default_spacing_y * 0.8):
                count += 1
                
        return count
        
    def avoid_collisions(self, proposed_position: QPointF, 
                        existing_nodes: List[Dict[str, Any]]) -> QPointF:
        """Adjust position to avoid overlapping with existing nodes"""
        
        # Standard node size (should match canvas node size)
        node_width = 120
        node_height = 80
        
        max_attempts = 10
        current_position = proposed_position
        
        for attempt in range(max_attempts):
            collision_found = False
            
            for existing_node in existing_nodes:
                existing_pos = QPointF(
                    existing_node["position"]["x"],
                    existing_node["position"]["y"]
                )
                
                if self._positions_collide(current_position, existing_pos, 
                                         node_width, node_height):
                    collision_found = True
                    # Move position to avoid collision
                    current_position = self._resolve_collision(
                        current_position, existing_pos, node_width, node_height
                    )
                    break
                    
            if not collision_found:
                break
                
        return current_position
        
    def _positions_collide(self, pos1: QPointF, pos2: QPointF, 
                          width: float, height: float) -> bool:
        """Check if two node positions would collide"""
        padding = self.collision_padding
        
        return (abs(pos1.x() - pos2.x()) < width + padding and
                abs(pos1.y() - pos2.y()) < height + padding)
                
    def _resolve_collision(self, proposed_pos: QPointF, existing_pos: QPointF,
                          width: float, height: float) -> QPointF:
        """Move proposed position to resolve collision"""
        
        # Calculate direction to move away from collision
        dx = proposed_pos.x() - existing_pos.x()
        dy = proposed_pos.y() - existing_pos.y()
        
        # If positions are too close, use default offset
        if abs(dx) < 10 and abs(dy) < 10:
            dx = width + self.collision_padding
            dy = 0
        
        # Normalize and scale the offset
        distance = math.sqrt(dx * dx + dy * dy)
        if distance > 0:
            # Scale to minimum safe distance
            min_distance = max(width, height) + self.collision_padding
            scale = min_distance / distance
            
            if scale > 1:  # Only move if we need to increase distance
                new_x = existing_pos.x() + dx * scale
                new_y = existing_pos.y() + dy * scale
                return QPointF(new_x, new_y)
                
        return proposed_pos
        
    def _snap_to_grid(self, position: QPointF) -> QPointF:
        """Snap position to grid for cleaner alignment"""
        grid_size = self.grid_snap_size
        
        snapped_x = round(position.x() / grid_size) * grid_size
        snapped_y = round(position.y() / grid_size) * grid_size
        
        return QPointF(snapped_x, snapped_y)
        
    def calculate_optimal_workflow_layout(self, nodes: List[Dict[str, Any]], 
                                        connections: List[Dict[str, Any]]) -> Dict[str, QPointF]:
        """Calculate optimal layout for an entire workflow"""
        
        # This is a more advanced feature for auto-arranging entire workflows
        # For now, return existing positions
        layout = {}
        for node in nodes:
            layout[node["node_id"]] = QPointF(
                node["position"]["x"],
                node["position"]["y"]
            )
        return layout
        
    def suggest_connection_merge_point(self, branch_nodes: List[Dict[str, Any]]) -> QPointF:
        """Suggest where branching paths should merge back together"""
        
        if not branch_nodes:
            return QPointF(0, 0)
            
        # Find the rightmost and average Y position of branch nodes
        max_x = max(node["position"]["x"] for node in branch_nodes)
        avg_y = sum(node["position"]["y"] for node in branch_nodes) / len(branch_nodes)
        
        # Place merge point to the right of all branches
        merge_x = max_x + self.default_spacing_x
        merge_y = avg_y
        
        return QPointF(merge_x, merge_y)
        
    def get_connection_path_points(self, start_pos: QPointF, end_pos: QPointF, 
                                 connection_type: ConnectionType) -> List[QPointF]:
        """Get intermediate points for drawing curved connection paths"""
        
        points = [start_pos]
        
        # Add curve points based on connection type
        if connection_type in [ConnectionType.CONDITIONAL_TRUE, ConnectionType.CONDITIONAL_FALSE]:
            # Add a curve point for conditional connections
            mid_x = start_pos.x() + (end_pos.x() - start_pos.x()) * 0.6
            mid_y = start_pos.y() + (end_pos.y() - start_pos.y()) * 0.3
            points.append(QPointF(mid_x, mid_y))
            
            
        points.append(end_pos)
        return points