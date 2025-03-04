import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
import json

class CodebaseNavigator:
    """
    Generates navigational maps of codebases optimized for LLM consumption.
    Focuses on file relationships, function/method indexing, and structural elements
    rather than descriptive summaries.
    """
    
    def __init__(self, 
                 directory: Path,
                 collected_data: Dict[str, Any],
                 focus: Optional[Path] = None,
                 include_source: bool = False,
                 max_source_lines: int = 10):
        """
        Initialize the CodebaseNavigator.
        
        Args:
            directory: Root directory of the codebase
            collected_data: Data collected by CodebaseCartographer
            focus: Focus subdirectory if specified
            include_source: Whether to include source code snippets
            max_source_lines: Maximum number of source lines to include per function
        """
        self.directory = directory
        self.collected_data = collected_data
        self.focus_dir = focus
        self.include_source = include_source
        self.max_source_lines = max_source_lines
        
        # Data structures for navigation info
        self.imports_graph = {}  # Which files import which files
        self.imported_by_graph = {}  # Which files are imported by which files
        self.function_index = {}  # Maps function names to their locations
        self.class_index = {}  # Maps class names to their locations
        self.module_structure = {}  # Hierarchical structure of modules
    
    def analyze_imports(self) -> None:
        """Analyze import relationships between files in the codebase."""
        # Process files from collected data to find import statements
        for file_category in ['important_files', 'file_samples']:
            for rel_path, info in self.collected_data.get(file_category, {}).items():
                if info.get('language') in ['Python', 'JavaScript', 'TypeScript', 'TypeScript (React)', 'JavaScript (React)']:
                    abs_path = self.directory / rel_path
                    self._analyze_file_imports(abs_path, rel_path)
    
    def _analyze_file_imports(self, abs_path: Path, rel_path: str) -> None:
        """
        Analyze imports in a single file.
        
        Args:
            abs_path: Absolute path to the file
            rel_path: Relative path from codebase root
        """
        try:
            # Initialize import tracking for this file
            if rel_path not in self.imports_graph:
                self.imports_graph[rel_path] = set()
            
            # Python file analysis
            if abs_path.suffix == '.py':
                self._analyze_python_imports(abs_path, rel_path)
            
            # JavaScript/TypeScript analysis
            elif abs_path.suffix in ['.js', '.jsx', '.ts', '.tsx']:
                self._analyze_js_ts_imports(abs_path, rel_path)
        
        except Exception as e:
            # Silently continue if import analysis fails for a file
            pass
    
    def _analyze_python_imports(self, abs_path: Path, rel_path: str) -> None:
        """
        Analyze imports in a Python file using AST.
        
        Args:
            abs_path: Absolute path to the file
            rel_path: Relative path from codebase root
        """
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Parse Python code with AST
            tree = ast.parse(content, filename=str(abs_path))
            
            # Track imports
            for node in ast.walk(tree):
                # Regular imports (import x, import x.y)
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imported_module = name.name
                        self._register_python_import(rel_path, imported_module)
                
                # From imports (from x import y)
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    self._register_python_import(rel_path, node.module)
        
        except Exception:
            # Continue if parsing fails
            pass
    
    def _register_python_import(self, importing_file: str, imported_module: str) -> None:
        """
        Register a Python import relationship.
        
        Args:
            importing_file: File that contains the import
            imported_module: Module being imported
        """
        # Convert module name to potential file path (for local imports)
        parts = imported_module.split('.')
        potential_paths = []
        
        # Check for potential local module imports
        for i in range(len(parts)):
            partial_path = '/'.join(parts[:i+1])
            potential_paths.append(f"{partial_path}.py")
            potential_paths.append(f"{partial_path}/__init__.py")
        
        # Register all potential matches in the codebase
        for path in potential_paths:
            if self._file_exists_in_data(path):
                self.imports_graph[importing_file].add(path)
                
                # Register reverse relationship
                if path not in self.imported_by_graph:
                    self.imported_by_graph[path] = set()
                self.imported_by_graph[path].add(importing_file)
    
    def _analyze_js_ts_imports(self, abs_path: Path, rel_path: str) -> None:
        """
        Analyze imports in JavaScript/TypeScript files.
        
        Args:
            abs_path: Absolute path to the file
            rel_path: Relative path from codebase root
        """
        # Simple regex-based import analysis for JS/TS
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Match ES6 imports and requires
            import_patterns = [
                r'import\s+.*?from\s+[\'"](.+?)[\'"]',  # import X from 'path'
                r'import\s+[\'"](.+?)[\'"]',  # import 'path'
                r'require\([\'"](.+?)[\'"]\)'  # require('path')
            ]
            
            for pattern in import_patterns:
                for match in re.findall(pattern, content):
                    self._register_js_ts_import(rel_path, match)
        
        except Exception:
            # Continue if parsing fails
            pass
    
    def _register_js_ts_import(self, importing_file: str, imported_path: str) -> None:
        """
        Register a JavaScript/TypeScript import relationship.
        
        Args:
            importing_file: File that contains the import
            imported_path: Path being imported
        """
        # Skip node_modules and other external imports
        if imported_path.startswith('.'):
            # Resolve the relative import path
            importing_dir = os.path.dirname(importing_file)
            if imported_path.startswith('./'):
                imported_path = imported_path[2:]
            
            # Normalize the path
            if importing_dir:
                resolved_path = os.path.normpath(f"{importing_dir}/{imported_path}")
            else:
                resolved_path = imported_path
            
            # Common extensions to check
            extensions = ['', '.js', '.jsx', '.ts', '.tsx', '/index.js', '/index.jsx', '/index.ts', '/index.tsx']
            
            for ext in extensions:
                potential_path = f"{resolved_path}{ext}"
                if self._file_exists_in_data(potential_path):
                    self.imports_graph[importing_file].add(potential_path)
                    
                    # Register reverse relationship
                    if potential_path not in self.imported_by_graph:
                        self.imported_by_graph[potential_path] = set()
                    self.imported_by_graph[potential_path].add(importing_file)
                    break
    
    def _file_exists_in_data(self, path: str) -> bool:
        """Check if a file exists in the collected data."""
        return (path in self.collected_data.get('important_files', {}) or
                path in self.collected_data.get('file_samples', {}))
    
    def analyze_functions(self) -> None:
        """Analyze function/method definitions across the codebase."""
        # Process files from collected data to find function definitions
        for file_category in ['important_files', 'file_samples']:
            for rel_path, info in self.collected_data.get(file_category, {}).items():
                if info.get('language') == 'Python':
                    abs_path = self.directory / rel_path
                    self._analyze_python_functions(abs_path, rel_path)
                elif info.get('language') in ['JavaScript', 'TypeScript', 'TypeScript (React)', 'JavaScript (React)']:
                    abs_path = self.directory / rel_path
                    self._analyze_js_ts_functions(abs_path, rel_path)
    
    def _analyze_python_functions(self, abs_path: Path, rel_path: str) -> None:
        """
        Extract function and class definitions from Python files.
        
        Args:
            abs_path: Absolute path to the file
            rel_path: Relative path from codebase root
        """
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse Python code with AST
            tree = ast.parse(content, filename=str(abs_path))
            
            # Extract source code lines if needed
            source_lines = content.splitlines() if self.include_source else []
            
            # Track function definitions
            for node in ast.walk(tree):
                # Function definitions
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'file': rel_path,
                        'line': node.lineno,
                        'args': self._get_python_function_args(node),
                        'returns': self._get_python_return_type(node)
                    }
                    
                    # Add source code if requested
                    if self.include_source and node.lineno <= len(source_lines):
                        # Extract function body (limited lines)
                        start_line = node.lineno - 1  # AST uses 1-based indexing
                        end_line = min(start_line + self.max_source_lines, len(source_lines))
                        func_info['source'] = '\n'.join(source_lines[start_line:end_line])
                        if end_line < node.end_lineno:
                            func_info['source'] += '\n    # ...'
                    
                    # Add to function index
                    qualified_name = f"{rel_path}:{node.name}"
                    self.function_index[qualified_name] = func_info
                
                # Class definitions
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'file': rel_path,
                        'line': node.lineno,
                        'methods': [],
                        'bases': [self._get_node_name(base) for base in node.bases]
                    }
                    
                    # Find methods within the class
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_info = {
                                'name': item.name,
                                'line': item.lineno,
                                'args': self._get_python_function_args(item),
                                'returns': self._get_python_return_type(item)
                            }
                            
                            # Add source code if requested
                            if self.include_source and item.lineno <= len(source_lines):
                                # Extract method body (limited lines)
                                start_line = item.lineno - 1
                                end_line = min(start_line + self.max_source_lines, len(source_lines))
                                method_info['source'] = '\n'.join(source_lines[start_line:end_line])
                                if end_line < item.end_lineno:
                                    method_info['source'] += '\n    # ...'
                            
                            class_info['methods'].append(method_info)
                    
                    # Add to class index
                    qualified_name = f"{rel_path}:{node.name}"
                    self.class_index[qualified_name] = class_info
        
        except Exception:
            # Continue if parsing fails
            pass
    
    def _get_python_function_args(self, node: ast.FunctionDef) -> List[Dict[str, str]]:
        """Extract function arguments with type annotations if available."""
        args = []
        for arg in node.args.args:
            arg_info = {'name': arg.arg}
            if arg.annotation:
                arg_info['type'] = self._get_node_name(arg.annotation)
            args.append(arg_info)
        return args
    
    def _get_python_return_type(self, node: ast.FunctionDef) -> Optional[str]:
        """Extract return type annotation if available."""
        if node.returns:
            return self._get_node_name(node.returns)
        return None
    
    def _get_node_name(self, node) -> str:
        """Extract name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._get_node_name(node.value)}[{self._get_node_name(node.slice)}]"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.List):
            return f"[{', '.join(self._get_node_name(elt) for elt in node.elts)}]"
        elif hasattr(node, 'id'):
            return node.id
        elif hasattr(node, 'value'):
            return str(node.value)
        else:
            # Return a simplified representation for complex nodes
            return node.__class__.__name__
    
    def _analyze_js_ts_functions(self, abs_path: Path, rel_path: str) -> None:
        """
        Extract function and class definitions from JavaScript/TypeScript files.
        
        Args:
            abs_path: Absolute path to the file
            rel_path: Relative path from codebase root
        """
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Use regex for simple function detection (not perfect but gives a reasonable approximation)
            source_lines = content.splitlines() if self.include_source else []
            
            # Function patterns
            patterns = [
                # Regular functions
                (r'function\s+(\w+)\s*\(([^)]*)\)', 'function'),
                # Arrow functions with explicit name (const x = (args) => {...})
                (r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>', 'arrow'),
                # Class methods
                (r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*{', 'method'),
                # Class definitions
                (r'class\s+(\w+)(?:\s+extends\s+(\w+))?', 'class')
            ]
            
            line_number = 0
            for line_number, line in enumerate(source_lines, 1):
                for pattern, func_type in patterns:
                    for match in re.finditer(pattern, line):
                        if func_type == 'class':
                            # Class definition
                            class_name = match.group(1)
                            base_class = match.group(2) if match.lastindex >= 2 else None
                            
                            class_info = {
                                'name': class_name,
                                'file': rel_path,
                                'line': line_number,
                                'methods': [],
                                'bases': [base_class] if base_class else []
                            }
                            
                            # Add to class index
                            qualified_name = f"{rel_path}:{class_name}"
                            self.class_index[qualified_name] = class_info
                        else:
                            # Function definition
                            func_name = match.group(1)
                            args_str = match.group(2) if match.lastindex >= 2 else ''
                            
                            # Extract args (simple parsing)
                            args = []
                            for arg in args_str.split(','):
                                arg = arg.strip()
                                if arg:
                                    arg_info = {'name': arg.split(':')[0].strip().split('=')[0].strip()}
                                    args.append(arg_info)
                            
                            func_info = {
                                'name': func_name,
                                'file': rel_path,
                                'line': line_number,
                                'args': args,
                                'type': func_type
                            }
                            
                            # Add source code if requested
                            if self.include_source:
                                # Extract up to max_source_lines
                                start_line = line_number - 1
                                end_line = min(start_line + self.max_source_lines, len(source_lines))
                                func_info['source'] = '\n'.join(source_lines[start_line:end_line])
                                if end_line < len(source_lines):
                                    func_info['source'] += '\n    // ...'
                            
                            # Add to function index
                            qualified_name = f"{rel_path}:{func_name}"
                            self.function_index[qualified_name] = func_info
        
        except Exception:
            # Continue if parsing fails
            pass
    
    def build_module_structure(self) -> None:
        """Build hierarchical structure of modules/directories."""
        directories = self.collected_data.get('directories', {})
        
        # Start with a clean structure
        self.module_structure = {}
        
        # Add all directories
        for path, info in directories.items():
            if path == 'ROOT':
                self.module_structure['/'] = {
                    'type': 'directory',
                    'file_count': info.get('file_count', 0),
                    'children': {}
                }
            else:
                self._add_path_to_structure(path, info)
        
        # Add important files and file samples
        for file_category in ['important_files', 'file_samples']:
            for path in self.collected_data.get(file_category, {}):
                self._add_file_to_structure(path)
    
    def _add_path_to_structure(self, path: str, info: Dict) -> None:
        """Add a directory path to the module structure."""
        parts = path.split('/')
        current = self.module_structure
        
        # Create or navigate through the path
        for i, part in enumerate(parts):
            # Create the parent directories if they don't exist
            if i == 0 and '/' not in current:
                current['/'] = {'type': 'directory', 'children': {}}
            
            if i == len(parts) - 1:
                # This is the target directory
                current.setdefault('/', {}).setdefault('children', {})[part] = {
                    'type': 'directory',
                    'file_count': info.get('file_count', 0),
                    'children': {}
                }
            else:
                # This is a parent directory
                current = current.setdefault('/', {}).setdefault('children', {})
                if part not in current:
                    current[part] = {
                        'type': 'directory',
                        'children': {}
                    }
                current = current[part]
    
    def _add_file_to_structure(self, path: str) -> None:
        """Add a file to the module structure."""
        parts = path.split('/')
        filename = parts[-1]
        dir_parts = parts[:-1]
        
        # Start at root
        current = self.module_structure
        
        # Navigate to the directory
        if not dir_parts:
            # File in root directory
            current.setdefault('/', {}).setdefault('children', {})[filename] = {
                'type': 'file',
                'imports': list(self.imports_graph.get(path, set())),
                'imported_by': list(self.imported_by_graph.get(path, set()))
            }
        else:
            # Navigate through directories
            for part in dir_parts:
                current = current.setdefault('/', {}).setdefault('children', {})
                if part not in current:
                    current[part] = {
                        'type': 'directory',
                        'children': {}
                    }
                current = current[part]
            
            # Add the file to the last directory
            current.setdefault('children', {})[filename] = {
                'type': 'file',
                'imports': list(self.imports_graph.get(path, set())),
                'imported_by': list(self.imported_by_graph.get(path, set()))
            }
    
    def generate_llm_map(self) -> Dict[str, Any]:
        """
        Generate a structured map of the codebase optimized for LLM navigation.
        
        Returns:
            Dictionary with navigation information
        """
        # Analyze imports and functions if not already done
        self.analyze_imports()
        self.analyze_functions()
        self.build_module_structure()
        
        # Build the LLM-optimized map
        llm_map = {
            'project_info': {
                'name': self.collected_data.get('project_info', {}).get('name', 'Unknown'),
                'root_directory': str(self.directory),
                'focus': str(self.focus_dir) if self.focus_dir else None
            },
            'file_structure': self.module_structure,
            'key_files': self._get_key_files(),
            'imports_graph': {k: list(v) for k, v in self.imports_graph.items()},
            'imported_by_graph': {k: list(v) for k, v in self.imported_by_graph.items()},
            'functions': self.function_index,
            'classes': self.class_index,
            'entry_points': self._find_entry_points(),
            'navigation_paths': self._generate_navigation_paths()
        }
        
        return llm_map
    
    def _get_key_files(self) -> Dict[str, Any]:
        """Identify key files with their relative importance."""
        key_files = {}
        
        # Add important files
        for path, info in self.collected_data.get('important_files', {}).items():
            key_files[path] = {
                'language': info.get('language', 'Unknown'),
                'size': info.get('size_bytes', 0),
                'importance': 'high'
            }
        
        # Add other notable files based on import relationships
        for path, imported_by in self.imported_by_graph.items():
            if len(imported_by) > 2 and path not in key_files:  # Files imported by many other files
                file_info = self.collected_data.get('file_samples', {}).get(path, {})
                key_files[path] = {
                    'language': file_info.get('language', 'Unknown'),
                    'size': file_info.get('size_bytes', 0),
                    'importance': 'medium',
                    'imported_by_count': len(imported_by)
                }
        
        return key_files
    
    def _find_entry_points(self) -> Dict[str, Any]:
        """Identify potential entry points to the codebase."""
        entry_points = {}
        
        # Look for common entry point files
        entry_point_patterns = [
            r'main\.py$', r'app\.py$', r'server\.py$', r'cli\.py$',
            r'__main__\.py$', r'index\.js$', r'app\.js$', r'server\.js$'
        ]
        
        for file_category in ['important_files', 'file_samples']:
            for path in self.collected_data.get(file_category, {}):
                for pattern in entry_point_patterns:
                    if re.search(pattern, path):
                        entry_points[path] = {
                            'type': 'file_pattern_match',
                            'reason': f"Matches entry point pattern {pattern}"
                        }
        
        # Files that import many but aren't imported (likely entry points)
        for path, imports in self.imports_graph.items():
            imported_by = self.imported_by_graph.get(path, set())
            if len(imports) > 3 and len(imported_by) == 0:
                entry_points[path] = {
                    'type': 'import_pattern',
                    'reason': f"Imports {len(imports)} modules but isn't imported by others"
                }
        
        return entry_points
    
    def _generate_navigation_paths(self) -> Dict[str, List[str]]:
        """Generate common navigation paths through the codebase."""
        navigation_paths = {
            'module_dependencies': [],
            'inheritance_hierarchies': [],
            'execution_flows': []
        }
        
        # Create module dependency paths based on imports
        for file, imported_by in self.imported_by_graph.items():
            if len(imported_by) > 2:  # Focus on widely used modules
                dependent_modules = list(imported_by)
                navigation_paths['module_dependencies'].append({
                    'core_module': file,
                    'dependent_modules': dependent_modules
                })
        
        # Create class inheritance hierarchies
        classes_by_file = {}
        for qualified_name, class_info in self.class_index.items():
            file_path = class_info['file']
            if file_path not in classes_by_file:
                classes_by_file[file_path] = []
            classes_by_file[file_path].append((qualified_name, class_info))
        
        # Find classes with inheritance relationships
        for file_path, classes in classes_by_file.items():
            for qualified_name, class_info in classes:
                if class_info['bases']:
                    navigation_paths['inheritance_hierarchies'].append({
                        'class': qualified_name,
                        'bases': class_info['bases'],
                        'file': file_path
                    })
        
        # Generate potential execution flows starting from entry points
        for entry_file in self._find_entry_points():
            navigation_paths['execution_flows'].append({
                'entry_point': entry_file,
                'immediate_dependencies': list(self.imports_graph.get(entry_file, []))
            })
        
        return navigation_paths
    
    def generate_llm_output(self, format: str = 'markdown') -> str:
        """
        Generate a token-efficient textual representation for LLM consumption.
        
        Args:
            format: Output format ('markdown', 'json', or 'compact')
            
        Returns:
            String formatted for LLM consumption
        """
        # Generate the structured map data
        llm_map = self.generate_llm_map()
        
        if format == 'json':
            # Return as JSON string
            return json.dumps(llm_map, indent=2)
        
        elif format == 'compact':
            # Generate a very compact representation with minimal whitespace
            return self._generate_compact_representation(llm_map)
        
        else:  # markdown format
            # Generate a markdown representation
            return self._generate_markdown_representation(llm_map)
    
    def _generate_markdown_representation(self, llm_map: Dict[str, Any]) -> str:
        """Generate a markdown representation optimized for LLM consumption."""
        sections = []
        
        # Project information
        project_info = llm_map['project_info']
        sections.append(f"# {project_info['name']} Navigation Map\n")
        
        # Key files section
        key_files = llm_map['key_files']
        if key_files:
            sections.append("## KEY FILES")
            key_files_md = []
            for path, info in sorted(key_files.items(), 
                                    key=lambda x: 0 if x[1]['importance'] == 'high' else 1):
                imports = len(llm_map['imports_graph'].get(path, []))
                imported_by = len(llm_map['imported_by_graph'].get(path, []))
                key_files_md.append(f"- `{path}` ({info['language']}) - " + 
                                   f"Imports: {imports}, Imported by: {imported_by}")
            sections.append("\n".join(key_files_md))
        
        # Entry points section
        entry_points = llm_map['entry_points']
        if entry_points:
            sections.append("## ENTRY POINTS")
            entry_points_md = []
            for path, info in entry_points.items():
                entry_points_md.append(f"- `{path}` - {info['reason']}")
            sections.append("\n".join(entry_points_md))
        
        # Function index section (limit to most important for token efficiency)
        functions = llm_map['functions']
        if functions:
            sections.append("## FUNCTION INDEX")
            functions_md = []
            # Prioritize functions based on complexity (more args = more important)
            sorted_funcs = sorted(
                functions.items(), 
                key=lambda x: len(x[1].get('args', [])),
                reverse=True
            )[:50]  # Limit to top 50 functions by argument count
            
            for qualified_name, func_info in sorted_funcs:
                args_str = ", ".join([a.get('name', '') for a in func_info.get('args', [])])
                functions_md.append(f"- `{qualified_name}({args_str})` - L{func_info['line']}")
                
                # Add source code if available and requested
                if 'source' in func_info:
                    # Add indented source code block
                    source_code = func_info['source']
                    language = func_info['file'].split('.')[-1] if '.' in func_info['file'] else ''
                    functions_md.append(f"  ```{language}\n  {source_code.replace('\n', '\n  ')}\n  ```")
            
            sections.append("\n".join(functions_md))
            
        # Class index section
        classes = llm_map['classes']
        if classes:
            sections.append("## CLASS INDEX")
            classes_md = []
            
            # Sort by number of methods
            sorted_classes = sorted(
                classes.items(),
                key=lambda x: len(x[1].get('methods', [])),
                reverse=True
            )[:30]  # Limit to top 30 classes by method count
            
            for qualified_name, class_info in sorted_classes:
                methods_count = len(class_info.get('methods', []))
                bases = class_info.get('bases', [])
                bases_str = f" extends {', '.join(bases)}" if bases else ""
                classes_md.append(f"- `{qualified_name}`{bases_str} - {methods_count} methods")
                
                # Add method source code if available and requested
                if self.include_source:
                    for method in class_info.get('methods', [])[:3]:  # Limit to top 3 methods
                        if 'source' in method:
                            method_name = method['name']
                            source_code = method['source']
                            language = class_info['file'].split('.')[-1] if '.' in class_info['file'] else ''
                            classes_md.append(f"  - `{method_name}`:")
                            classes_md.append(f"    ```{language}\n    {source_code.replace('\n', '\n    ')}\n    ```")
            
            sections.append("\n".join(classes_md))
        
        # Module dependencies section
        module_deps = llm_map['navigation_paths']['module_dependencies']
        if module_deps:
            sections.append("## MODULE DEPENDENCIES")
            deps_md = []
            
            # Focus on the most widely used modules
            for dep in sorted(module_deps, key=lambda x: len(x['dependent_modules']), reverse=True)[:10]:
                core = dep['core_module']
                dependents = dep['dependent_modules']
                deps_md.append(f"- `{core}` is imported by {len(dependents)} modules")
                # List top 5 dependents
                for d in dependents[:5]:
                    deps_md.append(f"  - `{d}`")
                if len(dependents) > 5:
                    deps_md.append(f"  - ... and {len(dependents) - 5} more")
            
            sections.append("\n".join(deps_md))
        
        # Import relationships section
        imports_graph = llm_map['imports_graph']
        if imports_graph:
            sections.append("## IMPORT RELATIONSHIPS")
            imports_md = []
            
            # Focus on files with the most imports
            top_importers = sorted(
                [(path, imports) for path, imports in imports_graph.items()],
                key=lambda x: len(x[1]),
                reverse=True
            )[:10]
            
            for path, imports in top_importers:
                if imports:  # Only show if the file has imports
                    imports_md.append(f"- `{path}` imports {len(imports)} modules:")
                    # List up to 5 imports
                    for imp in sorted(imports)[:5]:
                        imports_md.append(f"  - `{imp}`")
                    if len(imports) > 5:
                        imports_md.append(f"  - ... and {len(imports) - 5} more")
            
            sections.append("\n".join(imports_md))
        
        return "\n\n".join(sections)
    
    def _generate_compact_representation(self, llm_map: Dict[str, Any]) -> str:
        """Generate a very compact representation with minimal whitespace for token efficiency."""
        parts = []
        
        # Project info (minimal)
        parts.append(f"PROJECT:{llm_map['project_info']['name']}")
        
        # Entry points (most important for navigation)
        entry_points = llm_map['entry_points']
        if entry_points:
            parts.append("ENTRY_POINTS:" + ";".join(entry_points.keys()))
        
        # Key files (just paths)
        key_files = llm_map['key_files']
        if key_files:
            key_file_parts = []
            for path, info in key_files.items():
                imported_by = len(llm_map['imported_by_graph'].get(path, []))
                key_file_parts.append(f"{path}:{info['language']}:{imported_by}")
            parts.append("KEY_FILES:" + ";".join(key_file_parts))
        
        # Import relationships (compact representation)
        imports_graph = llm_map['imports_graph']
        if imports_graph:
            import_parts = []
            # Focus on most important relationships
            for path, imports in imports_graph.items():
                if len(imports) > 2:  # Only include files with multiple imports
                    import_parts.append(f"{path}>[{','.join(sorted(imports)[:5])}]")
            parts.append("IMPORTS:" + ";".join(import_parts[:20]))  # Limit to top 20
        
        # Function index (very compact)
        functions = llm_map['functions']
        if functions:
            func_parts = []
            # Sort by arg count and take top 30
            sorted_funcs = sorted(
                functions.items(),
                key=lambda x: len(x[1].get('args', [])),
                reverse=True
            )[:30]
            
            for name, info in sorted_funcs:
                args = [a.get('name', '') for a in info.get('args', [])]
                func_parts.append(f"{name}({','.join(args)})")
            
            parts.append("FUNCTIONS:" + ";".join(func_parts))
        
        # Class index (compact)
        classes = llm_map['classes']
        if classes:
            class_parts = []
            for name, info in list(classes.items())[:20]:  # Limit to top 20
                methods = [m.get('name', '') for m in info.get('methods', [])]
                class_parts.append(f"{name}[{','.join(methods[:5])}]")
            
            parts.append("CLASSES:" + ";".join(class_parts))
        
        return "\n".join(parts)