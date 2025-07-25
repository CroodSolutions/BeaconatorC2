"""
Workflow validation and debugging system.
Provides real-time validation, error detection, and debugging tools for workflows.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Any, Tuple
from PyQt6.QtCore import QObject, pyqtSignal


class ValidationLevel(Enum):
    """Severity levels for validation issues"""
    ERROR = "error"       # Workflow cannot execute
    WARNING = "warning"   # Potential issues
    INFO = "info"        # Suggestions for improvement


class ValidationCategory(Enum):
    """Categories of validation issues"""
    CONNECTIVITY = "connectivity"     # Node connections
    PARAMETERS = "parameters"        # Parameter validation
    LOGIC = "logic"                 # Workflow logic
    PERFORMANCE = "performance"      # Performance concerns
    SECURITY = "security"           # Security issues
    SCHEMA = "schema"               # Schema compliance


@dataclass
class ValidationIssue:
    """Represents a validation issue in the workflow"""
    id: str
    level: ValidationLevel
    category: ValidationCategory
    title: str
    description: str
    node_id: Optional[str] = None
    connection_id: Optional[str] = None
    suggested_fix: Optional[str] = None
    line_number: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'level': self.level.value,
            'category': self.category.value,
            'title': self.title,
            'description': self.description,
            'node_id': self.node_id,
            'connection_id': self.connection_id,
            'suggested_fix': self.suggested_fix,
            'line_number': self.line_number
        }


class WorkflowValidator(QObject):
    """Main workflow validation system"""
    
    validation_completed = pyqtSignal(list)  # List of ValidationIssue objects
    issue_added = pyqtSignal(object)        # Single ValidationIssue
    issue_resolved = pyqtSignal(str)        # Issue ID
    
    def __init__(self, compatibility_manager=None, schema_service=None):
        super().__init__()
        self.compatibility_manager = compatibility_manager
        self.schema_service = schema_service
        self.validators = []
        self.current_issues = {}  # issue_id -> ValidationIssue
        
        # Initialize built-in validators
        self._init_validators()
        
    def _init_validators(self):
        """Initialize built-in validators"""
        self.validators = [
            ConnectivityValidator(),
            ParameterValidator(self.schema_service),
            LogicValidator(),
            PerformanceValidator(),
            SecurityValidator(),
            SchemaValidator(self.schema_service)
        ]
        
    def validate_workflow(self, nodes: List, connections: List) -> List[ValidationIssue]:
        """Validate entire workflow and return issues"""
        all_issues = []
        
        # Run each validator
        for validator in self.validators:
            try:
                issues = validator.validate(nodes, connections)
                all_issues.extend(issues)
            except Exception as e:
                # Create validation error issue
                error_issue = ValidationIssue(
                    id=f"validator_error_{validator.__class__.__name__}",
                    level=ValidationLevel.ERROR,
                    category=ValidationCategory.LOGIC,
                    title="Validation Error",
                    description=f"Error in {validator.__class__.__name__}: {str(e)}",
                    suggested_fix="Check validator configuration"
                )
                all_issues.append(error_issue)
                
        # Update current issues
        self._update_issues(all_issues)
        
        # Emit signal
        self.validation_completed.emit(all_issues)
        
        return all_issues
        
    def validate_node(self, node) -> List[ValidationIssue]:
        """Validate a single node"""
        issues = []
        
        for validator in self.validators:
            try:
                node_issues = validator.validate_node(node)
                issues.extend(node_issues)
            except Exception as e:
                print(f"Error validating node with {validator.__class__.__name__}: {e}")
                
        return issues
        
    def validate_connection(self, connection) -> List[ValidationIssue]:
        """Validate a single connection"""
        issues = []
        
        for validator in self.validators:
            try:
                conn_issues = validator.validate_connection(connection)
                issues.extend(conn_issues)
            except Exception as e:
                print(f"Error validating connection with {validator.__class__.__name__}: {e}")
                
        return issues
        
    def _update_issues(self, new_issues: List[ValidationIssue]):
        """Update current issues and emit change signals"""
        new_issue_ids = {issue.id for issue in new_issues}
        old_issue_ids = set(self.current_issues.keys())
        
        # Find resolved issues
        resolved_ids = old_issue_ids - new_issue_ids
        for issue_id in resolved_ids:
            del self.current_issues[issue_id]
            self.issue_resolved.emit(issue_id)
            
        # Find new issues
        for issue in new_issues:
            if issue.id not in self.current_issues:
                self.current_issues[issue.id] = issue
                self.issue_added.emit(issue)
            else:
                # Update existing issue
                self.current_issues[issue.id] = issue
                
    def get_issues_by_level(self, level: ValidationLevel) -> List[ValidationIssue]:
        """Get all issues of a specific level"""
        return [issue for issue in self.current_issues.values() if issue.level == level]
        
    def get_issues_by_category(self, category: ValidationCategory) -> List[ValidationIssue]:
        """Get all issues of a specific category"""
        return [issue for issue in self.current_issues.values() if issue.category == category]
        
    def get_issues_for_node(self, node_id: str) -> List[ValidationIssue]:
        """Get all issues for a specific node"""
        return [issue for issue in self.current_issues.values() if issue.node_id == node_id]
        
    def clear_issues(self):
        """Clear all current issues"""
        for issue_id in list(self.current_issues.keys()):
            del self.current_issues[issue_id]
            self.issue_resolved.emit(issue_id)


class BaseValidator:
    """Base class for workflow validators"""
    
    def validate(self, nodes: List, connections: List) -> List[ValidationIssue]:
        """Validate entire workflow"""
        return []
        
    def validate_node(self, node) -> List[ValidationIssue]:
        """Validate a single node"""
        return []
        
    def validate_connection(self, connection) -> List[ValidationIssue]:
        """Validate a single connection"""
        return []


class ConnectivityValidator(BaseValidator):
    """Validates node connectivity and workflow structure"""
    
    def validate(self, nodes: List, connections: List) -> List[ValidationIssue]:
        issues = []
        
        # Check for orphaned nodes
        connected_nodes = set()
        for conn in connections:
            if hasattr(conn, 'start_node') and hasattr(conn, 'end_node'):
                connected_nodes.add(conn.start_node)
                connected_nodes.add(conn.end_node)
                
        for node in nodes:
            if node not in connected_nodes and len(nodes) > 1:
                if hasattr(node, 'node_type') and node.node_type not in ['start', 'end']:
                    issues.append(ValidationIssue(
                        id=f"orphaned_node_{id(node)}",
                        level=ValidationLevel.WARNING,
                        category=ValidationCategory.CONNECTIVITY,
                        title="Orphaned Node",
                        description=f"Node '{node.get_display_name() if hasattr(node, 'get_display_name') else 'Unknown'}' is not connected to any other nodes",
                        node_id=getattr(node, 'node_id', str(id(node))),
                        suggested_fix="Connect this node to the workflow or remove it"
                    ))
                    
        # Check for missing start/end nodes
        start_nodes = [n for n in nodes if hasattr(n, 'node_type') and n.node_type == 'start']
        end_nodes = [n for n in nodes if hasattr(n, 'node_type') and n.node_type == 'end']
        
        if not start_nodes and len(nodes) > 0:
            issues.append(ValidationIssue(
                id="missing_start_node",
                level=ValidationLevel.ERROR,
                category=ValidationCategory.CONNECTIVITY,
                title="Missing Start Node",
                description="Workflow has no start node",
                suggested_fix="Add a start node to define the workflow entry point"
            ))
            
        if not end_nodes and len(nodes) > 1:
            issues.append(ValidationIssue(
                id="missing_end_node",
                level=ValidationLevel.WARNING,
                category=ValidationCategory.CONNECTIVITY,
                title="Missing End Node",
                description="Workflow has no explicit end node",
                suggested_fix="Add an end node to properly terminate the workflow"
            ))
            
        # Check for cycles
        cycles = self._detect_cycles(nodes, connections)
        for cycle in cycles:
            issues.append(ValidationIssue(
                id=f"cycle_{hash(tuple(cycle))}",
                level=ValidationLevel.WARNING,
                category=ValidationCategory.LOGIC,
                title="Workflow Cycle Detected",
                description=f"Potential infinite loop detected involving nodes: {', '.join(cycle)}",
                suggested_fix="Review workflow logic to prevent infinite loops"
            ))
            
        return issues
        
    def _detect_cycles(self, nodes: List, connections: List) -> List[List[str]]:
        """Detect cycles in the workflow graph"""
        # Build adjacency list
        graph = {}
        for node in nodes:
            node_id = getattr(node, 'node_id', str(id(node)))
            graph[node_id] = []
            
        for conn in connections:
            if hasattr(conn, 'start_node') and hasattr(conn, 'end_node'):
                start_id = getattr(conn.start_node, 'node_id', str(id(conn.start_node)))
                end_id = getattr(conn.end_node, 'node_id', str(id(conn.end_node)))
                if start_id in graph:
                    graph[start_id].append(end_id)
                    
        # DFS to detect cycles
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node_id, path):
            if node_id in rec_stack:
                # Found cycle
                cycle_start = path.index(node_id)
                cycle = path[cycle_start:]
                cycles.append(cycle)
                return
                
            if node_id in visited:
                return
                
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in graph.get(node_id, []):
                dfs(neighbor, path + [neighbor])
                
            rec_stack.remove(node_id)
            
        for node_id in graph:
            if node_id not in visited:
                dfs(node_id, [node_id])
                
        return cycles


class ParameterValidator(BaseValidator):
    """Validates node parameters"""
    
    def __init__(self, schema_service=None):
        self.schema_service = schema_service
        
    def validate_node(self, node) -> List[ValidationIssue]:
        issues = []
        
        # Check if node has required parameters
        if hasattr(node, 'parameters'):
            # Get parameter requirements from template or schema
            required_params = self._get_required_parameters(node)
            
            for param_name in required_params:
                if param_name not in node.parameters or not node.parameters[param_name]:
                    issues.append(ValidationIssue(
                        id=f"missing_param_{id(node)}_{param_name}",
                        level=ValidationLevel.ERROR,
                        category=ValidationCategory.PARAMETERS,
                        title="Missing Required Parameter",
                        description=f"Node '{node.get_display_name() if hasattr(node, 'get_display_name') else 'Unknown'}' is missing required parameter '{param_name}'",
                        node_id=getattr(node, 'node_id', str(id(node))),
                        suggested_fix=f"Set a value for parameter '{param_name}'"
                    ))
                    
        return issues
        
    def _get_required_parameters(self, node) -> List[str]:
        """Get list of required parameter names for a node"""
        # This would integrate with the schema service to get actual requirements
        # For now, return empty list
        return []


class LogicValidator(BaseValidator):
    """Validates workflow logic and flow"""
    
    def validate(self, nodes: List, connections: List) -> List[ValidationIssue]:
        issues = []
        
        # Check for unreachable nodes
        reachable = self._get_reachable_nodes(nodes, connections)
        for node in nodes:
            node_id = getattr(node, 'node_id', str(id(node)))
            if node_id not in reachable and hasattr(node, 'node_type') and node.node_type != 'start':
                issues.append(ValidationIssue(
                    id=f"unreachable_{node_id}",
                    level=ValidationLevel.WARNING,
                    category=ValidationCategory.LOGIC,
                    title="Unreachable Node",
                    description=f"Node '{node.get_display_name() if hasattr(node, 'get_display_name') else 'Unknown'}' cannot be reached from the start node",
                    node_id=node_id,
                    suggested_fix="Add connections to make this node reachable"
                ))
                
        return issues
        
    def _get_reachable_nodes(self, nodes: List, connections: List) -> Set[str]:
        """Get set of nodes reachable from start nodes"""
        # Find start nodes
        start_nodes = [n for n in nodes if hasattr(n, 'node_type') and n.node_type == 'start']
        if not start_nodes:
            return set()
            
        # Build adjacency list
        graph = {}
        for node in nodes:
            node_id = getattr(node, 'node_id', str(id(node)))
            graph[node_id] = []
            
        for conn in connections:
            if hasattr(conn, 'start_node') and hasattr(conn, 'end_node'):
                start_id = getattr(conn.start_node, 'node_id', str(id(conn.start_node)))
                end_id = getattr(conn.end_node, 'node_id', str(id(conn.end_node)))
                if start_id in graph:
                    graph[start_id].append(end_id)
                    
        # BFS from start nodes
        reachable = set()
        queue = [getattr(n, 'node_id', str(id(n))) for n in start_nodes]
        
        while queue:
            node_id = queue.pop(0)
            if node_id in reachable:
                continue
                
            reachable.add(node_id)
            queue.extend(graph.get(node_id, []))
            
        return reachable


class PerformanceValidator(BaseValidator):
    """Validates workflow performance characteristics"""
    
    def validate(self, nodes: List, connections: List) -> List[ValidationIssue]:
        issues = []
        
        # Check for too many nodes
        if len(nodes) > 50:
            issues.append(ValidationIssue(
                id="too_many_nodes",
                level=ValidationLevel.WARNING,
                category=ValidationCategory.PERFORMANCE,
                title="Large Workflow",
                description=f"Workflow has {len(nodes)} nodes, which may impact performance",
                suggested_fix="Consider breaking this into smaller workflows"
            ))
            
        # Check for deeply nested workflows
        max_depth = self._calculate_max_depth(nodes, connections)
        if max_depth > 20:
            issues.append(ValidationIssue(
                id="deep_nesting",
                level=ValidationLevel.WARNING,
                category=ValidationCategory.PERFORMANCE,
                title="Deep Workflow Nesting",
                description=f"Workflow has maximum depth of {max_depth} levels",
                suggested_fix="Consider flattening the workflow structure"
            ))
            
        return issues
        
    def _calculate_max_depth(self, nodes: List, connections: List) -> int:
        """Calculate maximum depth of workflow"""
        # Simplified depth calculation
        return min(len(nodes), 10)  # Placeholder implementation


class SecurityValidator(BaseValidator):
    """Validates workflow security aspects"""
    
    def validate_node(self, node) -> List[ValidationIssue]:
        issues = []
        
        # Check for potentially dangerous operations
        if hasattr(node, 'node_type'):
            dangerous_types = ['file_delete', 'system_command', 'network_scan']
            if node.node_type in dangerous_types:
                issues.append(ValidationIssue(
                    id=f"security_risk_{id(node)}",
                    level=ValidationLevel.WARNING,
                    category=ValidationCategory.SECURITY,
                    title="Potentially Dangerous Operation",
                    description=f"Node type '{node.node_type}' may pose security risks",
                    node_id=getattr(node, 'node_id', str(id(node))),
                    suggested_fix="Review security implications and add appropriate safeguards"
                ))
                
        return issues


class SchemaValidator(BaseValidator):
    """Validates schema compliance"""
    
    def __init__(self, schema_service=None):
        self.schema_service = schema_service
        
    def validate_node(self, node) -> List[ValidationIssue]:
        issues = []
        
        # Validate schema-based nodes
        if (hasattr(node, 'node_type') and 
            node.node_type.startswith('schema_') and 
            self.schema_service):
            
            # Check if schema is available
            if hasattr(node, 'module_info') and 'schema_file' in node.module_info:
                schema_file = node.module_info['schema_file']
                schema = self.schema_service.get_schema(schema_file)
                
                if not schema:
                    issues.append(ValidationIssue(
                        id=f"missing_schema_{id(node)}",
                        level=ValidationLevel.ERROR,
                        category=ValidationCategory.SCHEMA,
                        title="Missing Schema",
                        description=f"Cannot find schema file '{schema_file}' for node",
                        node_id=getattr(node, 'node_id', str(id(node))),
                        suggested_fix="Ensure the schema file is available"
                    ))
                    
        return issues