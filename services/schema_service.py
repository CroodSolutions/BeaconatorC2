"""
Schema Service for dynamic beacon module loading
Handles parsing and validation of beacon module schemas
"""

import yaml
import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class SchemaCacheEntry:
    """Cache entry for schema file data"""
    raw_data: Dict[str, Any]
    file_mtime: float
    parsed_schema: Optional['BeaconSchema'] = None

class SchemaCache:
    """Smart caching system for schema files with automatic invalidation"""
    
    def __init__(self):
        self._cache: Dict[str, SchemaCacheEntry] = {}
    
    def get_raw_data(self, schema_file: str, schema_path: Path) -> Dict[str, Any]:
        """Get raw YAML data for a schema file with caching and invalidation"""
        # Get current file modification time
        try:
            current_mtime = os.path.getmtime(schema_path)
        except OSError:
            # File doesn't exist or can't be accessed
            if schema_file in self._cache:
                del self._cache[schema_file]
            return {}
        
        # Check if we have cached data
        if schema_file in self._cache:
            cached_entry = self._cache[schema_file]
            if cached_entry.file_mtime == current_mtime:
                # Cache hit - file hasn't changed
                return cached_entry.raw_data
            else:
                # File changed - invalidate cache
                del self._cache[schema_file]
        
        # Cache miss or invalidated - read and parse file
        try:
            with open(schema_path, 'r', encoding='utf-8') as file:
                raw_data = yaml.safe_load(file)
            
            # Store in cache
            self._cache[schema_file] = SchemaCacheEntry(
                raw_data=raw_data,
                file_mtime=current_mtime
            )
            
            return raw_data
            
        except Exception:
            # If file read fails, return empty dict
            return {}
    
    def get_module_data(self, schema_file: str, schema_path: Path, 
                       category_name: str, module_name: str) -> Dict[str, Any]:
        """Get specific module data from cached schema"""
        raw_data = self.get_raw_data(schema_file, schema_path)
        
        # Navigate to the specific module data
        categories_data = raw_data.get('categories', {})
        category_data = categories_data.get(category_name, {})
        modules_data = category_data.get('modules', {})
        module_data = modules_data.get(module_name, {})
        
        return module_data
    
    def invalidate(self, schema_file: str = None):
        """Invalidate cache for specific file or all files"""
        if schema_file:
            self._cache.pop(schema_file, None)
        else:
            self._cache.clear()
    
    def update_module_cache(self, schema_file: str, schema_path: Path, 
                           category_name: str, module_name: str, new_module_data: dict):
        """Update cached data for a specific module without full file reload"""
        # Get current cached data
        cached_data = self.get_raw_data(schema_file, schema_path)
        
        # Update the specific module in cached data
        if 'categories' not in cached_data:
            cached_data['categories'] = {}
        
        if category_name not in cached_data['categories']:
            cached_data['categories'][category_name] = {}
        
        if 'modules' not in cached_data['categories'][category_name]:
            cached_data['categories'][category_name]['modules'] = {}
        
        # Update the specific module
        cached_data['categories'][category_name]['modules'][module_name] = new_module_data
        
        # Update the cache entry (the file modification time will be updated when file is written)
        if schema_file in self._cache:
            self._cache[schema_file].raw_data = cached_data

class ParameterType(Enum):
    """Supported parameter types for module inputs"""
    TEXT = "text"
    TEXTAREA = "textarea"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    FILE = "file"
    DIRECTORY = "directory"

@dataclass
class ParameterValidation:
    """Validation rules for parameters"""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    
    def validate(self, value: Any, param_type: ParameterType) -> tuple[bool, str]:
        """Validate a parameter value against the validation rules"""
        try:
            if param_type in [ParameterType.TEXT, ParameterType.TEXTAREA]:
                if self.min_length and len(str(value)) < self.min_length:
                    return False, f"Minimum length is {self.min_length} characters"
                if self.max_length and len(str(value)) > self.max_length:
                    return False, f"Maximum length is {self.max_length} characters"
                if self.pattern and not re.match(self.pattern, str(value)):
                    return False, "Invalid format"
                    
            elif param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
                num_value = float(value) if param_type == ParameterType.FLOAT else int(value)
                if self.min_value is not None and num_value < self.min_value:
                    return False, f"Minimum value is {self.min_value}"
                if self.max_value is not None and num_value > self.max_value:
                    return False, f"Maximum value is {self.max_value}"
                    
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid {param_type.value} value"

@dataclass
class ModuleParameter:
    """Definition of a module parameter"""
    name: str
    type: ParameterType
    display_name: str
    description: str
    required: bool = True
    default: Any = None
    validation: Optional[ParameterValidation] = None
    choices: Optional[List[str]] = None
    file_filters: Optional[List[str]] = None

@dataclass
class ModuleDocumentation:
    """Module documentation"""
    content: str = ""
    examples: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

@dataclass
class ModuleExecution:
    """Module execution settings"""
    timeout: int = 300
    requires_admin: bool = False
    platform_specific: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModuleUI:
    """Module UI customization"""
    color: str = "default"
    layout: str = "simple"  # simple, advanced, tabbed
    grouping: List[List[str]] = field(default_factory=list)

@dataclass
class Module:
    """Complete module definition"""
    name: str
    display_name: str
    description: str
    command_template: str
    parameters: Dict[str, ModuleParameter] = field(default_factory=dict)
    documentation: ModuleDocumentation = field(default_factory=ModuleDocumentation)
    execution: ModuleExecution = field(default_factory=ModuleExecution)
    ui: ModuleUI = field(default_factory=ModuleUI)
    
    def format_command(self, parameter_values: Dict[str, Any]) -> str:
        """Format the command template with provided parameter values"""
        try:
            # Handle simple parameter substitution
            command = self.command_template
            
            # Replace {param_name} with actual values
            for param_name, value in parameter_values.items():
                if param_name in self.parameters:
                    command = command.replace(f"{{{param_name}}}", str(value))
            
            # Handle comma-separated parameter lists in templates like {param1},{param2}
            if "|{" in command and "}," in command:
                # Extract parameter section
                parts = command.split("|")
                if len(parts) > 1:
                    param_section = parts[-1]
                    # Replace parameters in the section
                    for param_name, value in parameter_values.items():
                        param_section = param_section.replace(f"{{{param_name}}}", str(value))
                    command = "|".join(parts[:-1]) + "|" + param_section
            
            return command
        except Exception as e:
            raise ValueError(f"Failed to format command template: {e}")

@dataclass
class Category:
    """Module category"""
    name: str
    display_name: str
    description: str
    modules: Dict[str, Module] = field(default_factory=dict)

@dataclass
class BeaconInfo:
    """Beacon information"""
    beacon_type: str
    version: str
    description: str
    supported_platforms: List[str] = field(default_factory=list)
    encoding_strategy: str = "plaintext"

@dataclass
class BeaconSchema:
    """Complete beacon schema"""
    schema_version: str
    beacon_info: BeaconInfo
    categories: Dict[str, Category] = field(default_factory=dict)
    
    def get_module(self, category_name: str, module_name: str) -> Optional[Module]:
        """Get a specific module by category and name"""
        category = self.categories.get(category_name)
        if category:
            return category.modules.get(module_name)
        return None
    
    def get_all_modules(self) -> List[tuple[str, str, Module]]:
        """Get all modules as (category_name, module_name, module) tuples"""
        modules = []
        for cat_name, category in self.categories.items():
            for mod_name, module in category.modules.items():
                modules.append((cat_name, mod_name, module))
        return modules

class SchemaService:
    """Service for loading and managing beacon schemas"""
    
    def __init__(self, schemas_directory: str = "schemas"):
        self.schemas_directory = Path(schemas_directory)
        self.loaded_schemas: Dict[str, BeaconSchema] = {}
        self.cache = SchemaCache()
        
    def load_schema(self, schema_file: str) -> BeaconSchema:
        """Load a beacon schema from a YAML file with caching"""
        schema_path = self.schemas_directory / schema_file
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
            
        try:
            # Use cached data instead of reading file directly
            data = self.cache.get_raw_data(schema_file, schema_path)
            
            # Parse beacon info (support both beacon_info and agent_info keys for backward compatibility)
            beacon_info_data = data.get('beacon_info', data.get('agent_info', {}))
            beacon_info = BeaconInfo(
                beacon_type=beacon_info_data.get('beacon_type', beacon_info_data.get('agent_type', 'unknown')),
                version=beacon_info_data.get('version', '1.0.0'),
                description=beacon_info_data.get('description', ''),
                supported_platforms=beacon_info_data.get('supported_platforms', []),
                encoding_strategy=beacon_info_data.get('encoding_strategy', 'plaintext')
            )
            
            # Parse categories and modules
            categories = {}
            categories_data = data.get('categories', {})
            
            for cat_name, cat_data in categories_data.items():
                category = Category(
                    name=cat_name,
                    display_name=cat_data.get('display_name', cat_name),
                    description=cat_data.get('description', '')
                )
                
                # Parse modules in this category
                modules_data = cat_data.get('modules', {})
                for mod_name, mod_data in modules_data.items():
                    module = self._parse_module(mod_name, mod_data)
                    category.modules[mod_name] = module
                
                categories[cat_name] = category
            
            schema = BeaconSchema(
                schema_version=data.get('schema_version', '1.0'),
                beacon_info=beacon_info,
                categories=categories
            )
            
            # Cache the loaded schema
            self.loaded_schemas[schema_file] = schema
            return schema
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in schema file {schema_file}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse schema file {schema_file}: {e}")
    
    def _parse_module(self, mod_name: str, mod_data: Dict[str, Any]) -> Module:
        """Parse a module definition from YAML data"""
        # Parse parameters
        parameters = {}
        params_data = mod_data.get('parameters', {})
        
        for param_name, param_data in params_data.items():
            param_type = ParameterType(param_data.get('type', 'text'))
            
            # Parse validation rules
            validation = None
            validation_data = param_data.get('validation', {})
            if validation_data:
                validation = ParameterValidation(
                    min_length=validation_data.get('min_length'),
                    max_length=validation_data.get('max_length'),
                    min_value=validation_data.get('min_value'),
                    max_value=validation_data.get('max_value'),
                    pattern=validation_data.get('pattern')
                )
            
            parameter = ModuleParameter(
                name=param_name,
                type=param_type,
                display_name=param_data.get('display_name', param_name),
                description=param_data.get('description', ''),
                required=param_data.get('required', True),
                default=param_data.get('default'),
                validation=validation,
                choices=param_data.get('choices'),
                file_filters=param_data.get('file_filters')
            )
            parameters[param_name] = parameter
        
        # Parse documentation
        doc_data = mod_data.get('documentation', {})
        documentation = ModuleDocumentation(
            content=doc_data.get('content', ''),
            examples=doc_data.get('examples', []),
            references=doc_data.get('references', [])
        )
        
        # Parse execution settings
        exec_data = mod_data.get('execution', {})
        execution = ModuleExecution(
            timeout=exec_data.get('timeout', 300),
            requires_admin=exec_data.get('requires_admin', False),
            platform_specific=exec_data.get('platform_specific', {})
        )
        
        # Parse UI settings
        ui_data = mod_data.get('ui', {})
        ui = ModuleUI(
            color=ui_data.get('color', 'default'),
            layout=ui_data.get('layout', 'simple'),
            grouping=ui_data.get('grouping', [])
        )
        
        return Module(
            name=mod_name,
            display_name=mod_data.get('display_name', mod_name),
            description=mod_data.get('description', ''),
            command_template=mod_data.get('command_template', ''),
            parameters=parameters,
            documentation=documentation,
            execution=execution,
            ui=ui
        )
    
    def get_schema(self, schema_file: str) -> Optional[BeaconSchema]:
        """Get a loaded schema or load it if not already loaded"""
        if schema_file not in self.loaded_schemas:
            try:
                return self.load_schema(schema_file)
            except Exception:
                return None
        return self.loaded_schemas[schema_file]
    
    def list_available_schemas(self) -> List[str]:
        """List all available schema files in the schemas directory"""
        if not self.schemas_directory.exists():
            return []
        
        return [
            f.name for f in self.schemas_directory.glob("*.yaml") 
            if f.is_file() and not f.name.startswith("SCHEMA_REFERENCE")
        ]
    
    def get_module_yaml_data(self, schema_file: str, category_name: str, module_name: str) -> Dict[str, Any]:
        """Get raw YAML data for a specific module using efficient caching"""
        schema_path = self.schemas_directory / schema_file
        return self.cache.get_module_data(schema_file, schema_path, category_name, module_name)
    
    def validate_schema(self, schema_file: str) -> tuple[bool, List[str]]:
        """Validate a schema file and return any errors"""
        errors = []
        
        try:
            schema = self.load_schema(schema_file)
            
            # Basic validation checks
            if not schema.beacon_info.beacon_type:
                errors.append("Missing beacon_type in beacon_info")
            
            if not schema.categories:
                errors.append("No categories defined")
            
            for cat_name, category in schema.categories.items():
                if not category.modules:
                    errors.append(f"Category '{cat_name}' has no modules")
                
                for mod_name, module in category.modules.items():
                    if not module.command_template:
                        errors.append(f"Module '{mod_name}' missing command_template")
                    
                    # Validate parameter types
                    for param_name, param in module.parameters.items():
                        try:
                            ParameterType(param.type.value)
                        except ValueError:
                            errors.append(f"Invalid parameter type '{param.type}' in module '{mod_name}'")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Failed to load schema: {e}")
            return False, errors