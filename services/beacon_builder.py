"""
Beacon Builder Service

Service wrapper for the BeaconBuilder module, providing integration
with the UI and file system operations.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Import from beacon_builder module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from beacon_builder import BeaconBuilder, ModuleManifest, get_supported_languages


class BeaconBuilderService:
    """
    Service class that wraps BeaconBuilder for UI integration.

    Provides additional functionality like:
    - File saving
    - Schema generation and saving
    - Build history tracking
    - Configuration validation
    """

    def __init__(self):
        self.builder: Optional[BeaconBuilder] = None
        self.current_language: str = ''
        self.build_history: List[Dict] = []

    def set_language(self, language: str) -> bool:
        """
        Set the beacon language and initialize the builder.

        Args:
            language: Language identifier (e.g., 'ahk', 'python')

        Returns:
            True if successful, False otherwise
        """
        try:
            self.builder = BeaconBuilder(language)
            self.current_language = language
            return True
        except Exception as e:
            print(f"Error setting language: {e}")
            return False

    def get_languages(self) -> List[str]:
        """Get list of supported beacon languages"""
        return get_supported_languages()

    def get_modules(self) -> List[Dict]:
        """
        Get available modules for the current language.

        Returns:
            List of module info dicts with id, name, description, category_id, etc.
        """
        if not self.builder:
            return []

        modules = []
        for manifest in self.builder.get_available_modules():
            # Get category_id from manifest schema if available
            category_id = 'other'
            if manifest.schema and isinstance(manifest.schema, dict):
                category_id = manifest.schema.get('category_id', 'other')

            modules.append({
                'id': manifest.id,
                'name': manifest.display_name,
                'description': manifest.description,
                'requires': manifest.requires,
                'provides': manifest.provides,
                'config_options': manifest.config_options,
                'category_id': category_id,
            })
        return modules

    def select_modules(self, module_ids: List[str]):
        """Select modules to include in the beacon"""
        if self.builder:
            self.builder.select_modules(module_ids)

    def get_config_options(self) -> Dict:
        """
        Get all configuration options for selected modules.

        Returns:
            Dict of config options keyed by option name
        """
        if not self.builder:
            return {}

        options = {}

        # Add core config options
        if self.builder._core_manifest:
            for key, opt in self.builder._core_manifest.config_options.items():
                options[key] = opt

        # Add options from selected modules
        resolved = self.builder.resolve_dependencies()
        for manifest in resolved:
            for key, opt in manifest.config_options.items():
                options[key] = opt

        return options

    def validate_config(self, config: Dict) -> List[str]:
        """
        Validate configuration values.

        Args:
            config: Configuration dict

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check required options
        options = self.get_config_options()
        for key, opt in options.items():
            if opt.get('required', False) and key not in config:
                errors.append(f"Missing required config: {key}")

            if key in config:
                # Type validation
                opt_type = opt.get('type', 'string')
                value = config[key]

                if opt_type == 'integer':
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        errors.append(f"Config '{key}' must be an integer")

                elif opt_type == 'string' and not isinstance(value, str):
                    errors.append(f"Config '{key}' must be a string")

        return errors

    def build(self, config: Dict) -> Optional[str]:
        """
        Build the beacon with given configuration.

        Args:
            config: Configuration dict

        Returns:
            Generated beacon code, or None on error
        """
        if not self.builder:
            return None

        # Validate config
        errors = self.validate_config(config)
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        try:
            code = self.builder.build(config)

            # Track build
            self.build_history.append({
                'timestamp': datetime.now().isoformat(),
                'language': self.current_language,
                'modules': self.builder.selected_modules.copy(),
                'config': config.copy(),
                'schema_filename': self.builder.get_schema_filename(),
            })

            return code

        except Exception as e:
            raise RuntimeError(f"Build failed: {e}")

    def get_schema_filename(self) -> str:
        """Get the schema filename generated during the last build"""
        if self.builder:
            return self.builder.get_schema_filename()
        return ""

    def build_and_save_with_schema(self, config: Dict, beacon_output_path: str, schemas_dir: str = None) -> dict:
        """
        Build the beacon and automatically save both the beacon and schema.

        Args:
            config: Configuration dict
            beacon_output_path: Path to save the beacon file
            schemas_dir: Directory to save the schema (defaults to 'schemas/')

        Returns:
            Dict with 'beacon_path', 'schema_path', 'schema_filename'
        """
        if schemas_dir is None:
            # Default to schemas directory relative to project root
            schemas_dir = Path(__file__).parent.parent / 'schemas'

        # Build the beacon
        code = self.build(config)
        if not code:
            raise RuntimeError("Build returned empty code")

        # Save the beacon
        if not self.save_beacon(code, beacon_output_path):
            raise RuntimeError("Failed to save beacon file")

        # Get the schema filename and save schema
        schema_filename = self.get_schema_filename()
        schema_path = Path(schemas_dir) / schema_filename

        if not self.save_schema(str(schema_path)):
            raise RuntimeError("Failed to save schema file")

        return {
            'beacon_path': beacon_output_path,
            'schema_path': str(schema_path),
            'schema_filename': schema_filename,
        }

    def save_beacon(self, code: str, output_path: str) -> bool:
        """
        Save generated beacon code to a file.

        Args:
            code: Generated beacon code
            output_path: Path to save the beacon

        Returns:
            True if successful
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(code)
            return True
        except Exception as e:
            print(f"Error saving beacon: {e}")
            return False

    def generate_schema(self) -> Optional[Dict]:
        """Generate schema for the built beacon"""
        if not self.builder:
            return None

        return self.builder.generate_schema()

    def save_schema(self, output_path: str) -> bool:
        """
        Generate and save schema to a YAML file.

        Args:
            output_path: Path to save the schema

        Returns:
            True if successful
        """
        schema = self.generate_schema()
        if not schema:
            return False

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(schema, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            print(f"Error saving schema: {e}")
            return False

    def get_estimated_size(self) -> int:
        """Get estimated beacon size in bytes"""
        if not self.builder:
            return 0
        return self.builder.get_estimated_size()

    def preview_code(self, config: Dict, max_lines: int = 100) -> str:
        """
        Generate a preview of the beacon code.

        Args:
            config: Configuration dict
            max_lines: Maximum lines to return

        Returns:
            Code preview string
        """
        try:
            code = self.build(config)
            if code:
                lines = code.split('\n')
                if len(lines) > max_lines:
                    return '\n'.join(lines[:max_lines]) + f"\n\n... ({len(lines) - max_lines} more lines)"
                return code
        except Exception as e:
            return f"; Error generating preview: {e}"
        return ""
