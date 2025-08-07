from typing import List, Dict, Any, Tuple, Set
from PyQt6.QtCore import QPointF
import math
from collections import defaultdict

from .node_compatibility import ConnectionType
from .node_factory import NodeTemplate


class SpatialIndex:
    """Spatial indexing for efficient collision detection with large numbers of nodes"""
    
    def __init__(self, cell_size: float = 300):
        self.cell_size = cell_size  # Size of each spatial grid cell
        self.grid: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
        
    def clear(self):
        """Clear all nodes from the spatial index"""
        self.grid.clear()
        
    def add_node(self, node_data: Dict[str, Any]):
        """Add a node to the spatial index"""
        pos = QPointF(node_data["position"]["x"], node_data["position"]["y"])
        
        # Get node dimensions to determine which cells it occupies
        if node_data.get("node_type", "").startswith(('action', 'schema_')):
            width, height = 200, 140  # Action node size
        else:
            width, height = 140, 90   # Standard node size
            
        # Calculate all grid cells this node occupies
        cells = self._get_cells_for_rect(pos, width, height)
        
        # Add node to all relevant cells
        for cell in cells:
            self.grid[cell].append(node_data)
            
    def get_nearby_nodes(self, position: QPointF, width: float, height: float, 
                        padding: float = 20) -> List[Dict[str, Any]]:
        """Get all nodes that could potentially collide with a rectangle at the given position"""
        # Expand the search area by padding
        search_pos = QPointF(position.x() - padding, position.y() - padding)
        search_width = width + 2 * padding
        search_height = height + 2 * padding
        
        # Get all cells that intersect with the search area
        cells = self._get_cells_for_rect(search_pos, search_width, search_height)
        
        # Collect all nodes from relevant cells (with deduplication)
        nearby_nodes = set()
        for cell in cells:
            for node in self.grid[cell]:
                # Use node_id for deduplication, fallback to id(node) if not available
                node_id = node.get('node_id', id(node))
                nearby_nodes.add((node_id, tuple(sorted(node.items()))))
                
        # Convert back to list of node dicts
        return [dict(node_tuple[1]) for node_tuple in nearby_nodes]
        
    def _get_cells_for_rect(self, position: QPointF, width: float, height: float) -> Set[Tuple[int, int]]:
        """Get all grid cells that a rectangle intersects"""
        cells = set()
        
        # Calculate grid coordinates for corners of the rectangle
        left = int(position.x() // self.cell_size)
        right = int((position.x() + width) // self.cell_size)
        top = int(position.y() // self.cell_size)
        bottom = int((position.y() + height) // self.cell_size)
        
        # Add all cells in the range
        for x in range(left, right + 1):
            for y in range(top, bottom + 1):
                cells.add((x, y))
                
        return cells


class NodePositionManager:
    """Handles intelligent positioning of new nodes"""
    
    def __init__(self):
        # Grid system - all spacing should be multiples of grid size for symmetry
        self.grid_snap_size = 25     # Snap positions to grid (75px for better alignment)
        self.default_spacing_x = 300  # Horizontal spacing between nodes (4 grid units)
        self.default_spacing_y = 150  # Vertical spacing for branches (2 grid units)
        self.collision_padding = 20   # Extra padding to avoid collisions
        
        # Node size constants (matching actual canvas node dimensions)
        self.standard_node_width = 140
        self.standard_node_height = 90
        self.action_node_width = 200
        self.action_node_height = 140
        
        # Spatial indexing for performance optimization
        self.spatial_index = SpatialIndex(cell_size=300)
        self.spatial_index_enabled = True  # Can be disabled for debugging
        
    def get_node_dimensions(self, template: NodeTemplate = None, node_type: str = None) -> Tuple[float, float]:
        """Get actual node dimensions based on template or node type"""
        # Determine node type from template or direct parameter
        if template:
            node_type = template.node_type
        
        if not node_type:
            # Default to standard size if no type specified
            return (self.standard_node_width, self.standard_node_height)
            
        # Action nodes are larger
        if node_type == 'action' or node_type.startswith('schema_') or node_type.startswith('action_'):
            return (self.action_node_width, self.action_node_height)
        else:
            # Standard size for control flow nodes (start, end, condition, delay, etc.)
            return (self.standard_node_width, self.standard_node_height)
    
    def get_node_dimensions_from_data(self, node_data: Dict[str, Any]) -> Tuple[float, float]:
        """Get node dimensions from existing node data"""
        node_type = node_data.get("node_type", "")
        return self.get_node_dimensions(node_type=node_type)
        
    def _ensure_source_distance(self, proposed_position: QPointF, source_node_data: Dict[str, Any],
                               target_template: NodeTemplate) -> QPointF:
        """Ensure minimum distance from source node to prevent intersection"""
        source_pos = QPointF(
            source_node_data["position"]["x"], 
            source_node_data["position"]["y"]
        )
        
        # Get dimensions of both nodes
        source_width, source_height = self.get_node_dimensions_from_data(source_node_data)
        target_width, target_height = self.get_node_dimensions(target_template)
        
        # Calculate minimum safe distance (with extra padding for visual separation)
        min_x_distance = (source_width + target_width) / 2 + self.collision_padding * 2
        min_y_distance = (source_height + target_height) / 2 + self.collision_padding * 2
        
        # Check if current position is too close to source
        actual_x_distance = abs(proposed_position.x() - source_pos.x())
        actual_y_distance = abs(proposed_position.y() - source_pos.y())
        
        if actual_x_distance < min_x_distance and actual_y_distance < min_y_distance:
            # Position is too close to source, need to move it
            dx = proposed_position.x() - source_pos.x()
            dy = proposed_position.y() - source_pos.y()
            
            # If positions are nearly identical, use default direction (right)
            if abs(dx) < 10 and abs(dy) < 10:
                dx = min_x_distance
                dy = 0
            else:
                # Normalize direction and scale to minimum distance
                distance = math.sqrt(dx * dx + dy * dy)
                if distance > 0:
                    scale = max(min_x_distance, min_y_distance) / distance
                    if scale > 1:
                        dx *= scale
                        dy *= scale
            
            # Calculate new position
            new_x = source_pos.x() + dx
            new_y = source_pos.y() + dy
            
            # Snap to grid for clean positioning
            return self._snap_to_grid(QPointF(new_x, new_y))
            
        return proposed_position
        
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
            
        # Snap base position to grid first for clean alignment
        grid_aligned_position = self._snap_to_grid(base_position)
        
        # Ensure minimum distance from source node (prevent intersection)
        source_safe_position = self._ensure_source_distance(grid_aligned_position, source_node_data, target_template)
        
        # Remove source node from collision candidates to avoid double-checking
        other_nodes = [node for node in existing_nodes 
                      if node.get("node_id") != source_node_data.get("node_id")]
        
        # Avoid collisions with other existing nodes (working within grid constraints)
        final_position = self.avoid_collisions(source_safe_position, other_nodes, target_template)
        
        # Ensure final position is still grid-aligned after collision resolution
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
            # True branch goes up and right (symmetric positioning)
            return QPointF(
                source_pos.x() + self.default_spacing_x,
                source_pos.y() - self.grid_snap_size  # 1 grid unit up
            )
        else:  # CONDITIONAL_FALSE
            # False branch goes down and right (symmetric positioning)
            return QPointF(
                source_pos.x() + self.default_spacing_x,
                source_pos.y() + self.grid_snap_size  # 1 grid unit down
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
                        existing_nodes: List[Dict[str, Any]], 
                        target_template: NodeTemplate = None) -> QPointF:
        """Adjust position to avoid overlapping with existing nodes"""
        
        # Get actual node dimensions for the target node
        target_width, target_height = self.get_node_dimensions(target_template)
        
        # Use spatial indexing if enabled and we have enough nodes to benefit
        if self.spatial_index_enabled and len(existing_nodes) > 10:
            return self._avoid_collisions_with_spatial_index(
                proposed_position, existing_nodes, target_width, target_height
            )
        else:
            return self._avoid_collisions_linear(
                proposed_position, existing_nodes, target_width, target_height
            )
    
    def _avoid_collisions_with_spatial_index(self, proposed_position: QPointF,
                                           existing_nodes: List[Dict[str, Any]],
                                           target_width: float, target_height: float) -> QPointF:
        """Collision avoidance using spatial indexing for better performance"""
        
        # Build spatial index from existing nodes
        self.spatial_index.clear()
        for node in existing_nodes:
            self.spatial_index.add_node(node)
        
        max_attempts = 10
        current_position = proposed_position
        
        for attempt in range(max_attempts):
            collision_found = False
            
            # Get only nearby nodes instead of checking all nodes
            nearby_nodes = self.spatial_index.get_nearby_nodes(
                current_position, target_width, target_height, self.collision_padding
            )
            
            for existing_node in nearby_nodes:
                existing_pos = QPointF(
                    existing_node["position"]["x"],
                    existing_node["position"]["y"]
                )
                
                # Get dimensions of existing node
                existing_width, existing_height = self.get_node_dimensions_from_data(existing_node)
                
                if self._positions_collide(current_position, existing_pos, 
                                         target_width, target_height, 
                                         existing_width, existing_height):
                    collision_found = True
                    # Move position to avoid collision
                    current_position = self._resolve_collision(
                        current_position, existing_pos, 
                        target_width, target_height,
                        existing_width, existing_height
                    )
                    break
                    
            if not collision_found:
                break
                
        return current_position
    
    def _avoid_collisions_linear(self, proposed_position: QPointF,
                               existing_nodes: List[Dict[str, Any]],
                               target_width: float, target_height: float) -> QPointF:
        """Original linear collision avoidance for small numbers of nodes"""
        
        max_attempts = 10
        current_position = proposed_position
        
        for attempt in range(max_attempts):
            collision_found = False
            
            for existing_node in existing_nodes:
                existing_pos = QPointF(
                    existing_node["position"]["x"],
                    existing_node["position"]["y"]
                )
                
                # Get dimensions of existing node
                existing_width, existing_height = self.get_node_dimensions_from_data(existing_node)
                
                if self._positions_collide(current_position, existing_pos, 
                                         target_width, target_height, 
                                         existing_width, existing_height):
                    collision_found = True
                    # Move position to avoid collision
                    current_position = self._resolve_collision(
                        current_position, existing_pos, 
                        target_width, target_height,
                        existing_width, existing_height
                    )
                    break
                    
            if not collision_found:
                break
                
        return current_position
        
    def _positions_collide(self, pos1: QPointF, pos2: QPointF, 
                          width1: float, height1: float,
                          width2: float, height2: float) -> bool:
        """Check if two node rectangles would collide using proper rectangle intersection"""
        padding = self.collision_padding
        
        # Calculate rectangle boundaries (pos represents top-left corner)
        # Rectangle 1: from pos1 to pos1 + (width1, height1)
        rect1_left = pos1.x() - padding
        rect1_right = pos1.x() + width1 + padding
        rect1_top = pos1.y() - padding
        rect1_bottom = pos1.y() + height1 + padding
        
        # Rectangle 2: from pos2 to pos2 + (width2, height2)
        rect2_left = pos2.x() - padding
        rect2_right = pos2.x() + width2 + padding
        rect2_top = pos2.y() - padding
        rect2_bottom = pos2.y() + height2 + padding
        
        # Rectangles DON'T collide if one is completely outside the other
        no_collision = (rect1_right <= rect2_left or    # Rect1 is completely to the left of Rect2
                       rect1_left >= rect2_right or     # Rect1 is completely to the right of Rect2
                       rect1_bottom <= rect2_top or     # Rect1 is completely above Rect2
                       rect1_top >= rect2_bottom)       # Rect1 is completely below Rect2
        
        collision = not no_collision
        return collision
                
    def _resolve_collision(self, proposed_pos: QPointF, existing_pos: QPointF,
                          target_width: float, target_height: float,
                          existing_width: float, existing_height: float) -> QPointF:
        """Move proposed position to resolve collision using rectangle boundary separation"""
        
        padding = self.collision_padding
        
        # Calculate current rectangle boundaries
        # Proposed rectangle (target)
        target_left = proposed_pos.x()
        target_right = proposed_pos.x() + target_width
        target_top = proposed_pos.y()
        target_bottom = proposed_pos.y() + target_height
        
        # Existing rectangle
        existing_left = existing_pos.x()
        existing_right = existing_pos.x() + existing_width
        existing_top = existing_pos.y()
        existing_bottom = existing_pos.y() + existing_height
        
        # Calculate how much we need to move in each direction to separate the rectangles
        # Move target rectangle so it doesn't overlap with existing rectangle
        
        # Calculate movement required for each direction
        move_left = existing_left - target_right - padding   # Move target left (negative X)
        move_right = existing_right + padding - target_left  # Move target right (positive X)
        move_up = existing_top - target_bottom - padding     # Move target up (negative Y)
        move_down = existing_bottom + padding - target_top   # Move target down (positive Y)
        
        # Choose the direction that requires the smallest movement
        # Only consider movements that would actually separate the rectangles
        possible_moves = []
        
        if move_left < 0:  # Can move left
            possible_moves.append((abs(move_left), proposed_pos.x() + move_left, proposed_pos.y()))
        if move_right > 0:  # Can move right
            possible_moves.append((move_right, proposed_pos.x() + move_right, proposed_pos.y()))
        if move_up < 0:  # Can move up
            possible_moves.append((abs(move_up), proposed_pos.x(), proposed_pos.y() + move_up))  
        if move_down > 0:  # Can move down
            possible_moves.append((move_down, proposed_pos.x(), proposed_pos.y() + move_down))
        
        if possible_moves:
            # Sort by distance and pick the shortest move
            possible_moves.sort(key=lambda x: x[0])
            distance, new_x, new_y = possible_moves[0]
            return self._snap_to_grid(QPointF(new_x, new_y))
        
        # If no valid moves (shouldn't happen), fall back to moving right
        fallback_x = existing_right + padding
        return self._snap_to_grid(QPointF(fallback_x, proposed_pos.y()))
        
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
        
    def get_optimal_position(self, existing_nodes: List[Any]) -> QPointF:
        """Get an optimal position for a new node when no specific position is provided"""
        
        # Convert existing nodes to the format expected by the position manager
        # Handle both canvas nodes and service nodes
        node_data_list = []
        for node in existing_nodes:
            if hasattr(node, 'x') and hasattr(node, 'y'):
                # Canvas node format
                node_data = {
                    "node_id": getattr(node, 'node_id', str(id(node))),
                    "node_type": getattr(node, 'node_type', 'unknown'),
                    "position": {"x": node.x, "y": node.y}
                }
            elif isinstance(node, dict) and "position" in node:
                # Service node format
                node_data = node
            else:
                # Skip unknown node formats
                continue
            node_data_list.append(node_data)
        
        if not node_data_list:
            # No existing nodes, place at origin
            return QPointF(0, 0)
        
        # Find the rightmost node and place new node to its right
        rightmost_node = max(node_data_list, key=lambda n: n["position"]["x"])
        rightmost_pos = QPointF(rightmost_node["position"]["x"], rightmost_node["position"]["y"])
        
        # Calculate position to the right with proper spacing
        optimal_pos = QPointF(
            rightmost_pos.x() + self.default_spacing_x,
            rightmost_pos.y()
        )
        
        # Avoid collisions with existing nodes
        final_pos = self.avoid_collisions(optimal_pos, node_data_list)
        
        return self._snap_to_grid(final_pos)