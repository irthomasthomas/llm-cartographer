import os
import re
import json
import hashlib
import time
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set, Literal
import textwrap
import tempfile

import click
import llm
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.emoji import Emoji
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from tqdm import tqdm
from colorama import Fore, Style, init

init(autoreset=True)  # Initialize colorama

# Initialize rich console for fancy output
console = Console()

# Constants
DEFAULT_EXCLUDE_PATTERNS = [
    "node_modules", ".git", "__pycache__", "*.pyc", "*.pyo", "*.pyd", 
    "*.so", "*.dll", "*.exe", "*.bin", "*.obj", "*.o", "*.a", "*.lib", 
    "*.dylib", "*.ncb", "*.sdf", "*.suo", "*.pdb", "*.idb", "venv", 
    "env", ".env", ".venv", ".pytest_cache", ".mypy_cache", ".ruff_cache", 
    "build", "dist", "*.egg-info", "*.egg", ".tox", ".nox", ".coverage",
    ".DS_Store", "*.min.js", "*.min.css", "*.map", "package-lock.json",
    "yarn.lock", ".vscode", ".idea", "*.swp", "*.swo", ".ipynb_checkpoints",
    "debug", "target", "vendor"
]

# Maximum file size in bytes (default 100KB)
DEFAULT_MAX_FILE_SIZE = 100 * 1024  

# Extensions to consider as text files
TEXT_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.html', '.htm', '.css', '.scss', 
    '.sass', '.less', '.md', '.rst', '.txt', '.yaml', '.yml', '.toml', '.ini',
    '.json', '.xml', '.sh', '.bat', '.ps1', '.R', '.kt', '.swift', '.m', 
    '.mm', '.pl', '.pm', '.sql', '.graphql', '.lua', '.ex', '.exs', '.erl',
    '.elm', '.clj', '.scala', '.dart', '.vue', '.svelte', '.sol', '.pde',
    '.proto', '.groovy', '.jl', '.cf', '.tf', '.kt', '.kts'
}

# File patterns that likely contain project configuration/metadata
IMPORTANT_FILES = [
    'README*', 'LICENSE*', 'CONTRIBUTING*', 'CHANGELOG*', 'package.json',
    'setup.py', 'pyproject.toml', 'Makefile', 'CMakeLists.txt', 'Dockerfile',
    'docker-compose.yml', '.gitignore', '.github/workflows/*.yml', '.gitlab-ci.yml',
    'requirements.txt', 'Cargo.toml', 'Gemfile', 'build.gradle', 'pom.xml',
    'tsconfig.json', 'vite.config.*', 'webpack.config.*', 'rollup.config.*',
    'jest.config.*', 'cypress.config.*', 'tailwind.config.*'
]

# Analysis modes with descriptions
ANALYSIS_MODES = {
    "overview": "Provide a high-level overview of the codebase structure and purpose",
    "components": "Focus on identifying and explaining the main components and modules",
    "architecture": "Analyze the architectural patterns and system organization",
    "flows": "Identify key data and control flows through the system"
}

# Diagram formats
DIAGRAM_FORMATS = ["graphviz", "mermaid", "plantuml"]

class CodebaseCartographer:
    """Main class that handles codebase analysis and mapping."""
    
    def __init__(self, 
                 directory: str, 
                 exclude: List[str] = None,
                 max_files: int = 100,
                 max_file_size: int = DEFAULT_MAX_FILE_SIZE,
                 max_map_tokens: int = 6000,
                 output: Optional[str] = None,
                 model: str = None,
                 follow_symlinks: bool = False,
                 cache_dir: Optional[str] = None,
                 json_format: bool = False,
                 filter_extensions: Optional[List[str]] = None,
                 mode: str = "overview",
                 focus: Optional[str] = None,
                 reasoning: int = 5,
                 visual: bool = False,
                 diagram_format: str = "graphviz"):
        """
        Initialize the CodebaseCartographer.
        
        Args:
            directory: Path to the project directory to analyze
            exclude: Patterns to exclude (in .gitignore format)
            max_files: Maximum number of files to analyze
            max_file_size: Maximum file size in bytes
            max_map_tokens: Maximum tokens for the codebase map
            output: Output file path or directory
            model: LLM model to use
            follow_symlinks: Whether to follow symbolic links
            cache_dir: Cache directory path
            json_format: Whether to output as JSON
            filter_extensions: Only include files with these extensions
            mode: Analysis mode (overview, components, architecture, flows)
            focus: Focus analysis on a specific subdirectory
            reasoning: Depth of reasoning (0-9)
            visual: Generate visual diagram of codebase architecture
            diagram_format: Format for diagram generation (graphviz, mermaid, plantuml)
        """
        self.directory = Path(directory).resolve()
        if not self.directory.exists():
            raise ValueError(f"Directory '{directory}' does not exist")
        
        self.exclude_patterns = exclude or DEFAULT_EXCLUDE_PATTERNS
        self.pathspec = PathSpec.from_lines(GitWildMatchPattern, self.exclude_patterns)
        
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.max_map_tokens = max_map_tokens
        
        # Process output path - could be a file or directory
        self.output_path = Path(output) if output else None
        self.output_is_dir = False
        if self.output_path:
            if self.output_path.is_dir() or (not self.output_path.exists() and not self.output_path.suffix):
                self.output_is_dir = True
                self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.model_name = model or "gpt-4o" 
        self.follow_symlinks = follow_symlinks
        self.json_format = json_format
        self.filter_extensions = set(filter_extensions) if filter_extensions else None
        
        # New parameters
        if mode not in ANALYSIS_MODES:
            raise ValueError(f"Mode '{mode}' not recognized. Available modes: {', '.join(ANALYSIS_MODES.keys())}")
        self.mode = mode
        
        # Focus subdirectory
        if focus:
            self.focus = Path(focus)
            if not (self.directory / self.focus).exists():
                raise ValueError(f"Focus directory '{focus}' does not exist within '{directory}'")
            self.focus_dir = (self.directory / self.focus).resolve()
        else:
            self.focus = None
            self.focus_dir = None
            
        # Reasoning depth
        if not 0 <= reasoning <= 9:
            raise ValueError("Reasoning depth must be between 0 and 9")
        self.reasoning = reasoning
        
        # Visual diagram generation
        self.visual = visual
        
        # Diagram format
        if diagram_format not in DIAGRAM_FORMATS:
            raise ValueError(f"Diagram format '{diagram_format}' not recognized. Available formats: {', '.join(DIAGRAM_FORMATS)}")
        self.diagram_format = diagram_format
        
        # Initialize cache dir
        if cache_dir:
            self.cache_dir = Path(cache_dir).resolve()
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "llm-cartographer-cache"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to get the model
        try:
            self.model = llm.get_model(self.model_name)
        except Exception as e:
            console.print(f"[red]Error loading model {self.model_name}: {e}")
            console.print(f"[yellow]Available models: {', '.join(llm.get_model_names())}")
            raise

        # Statistics for reporting
        self.stats = {
            "total_files": 0,
            "analyzed_files": 0,
            "skipped_files": 0,
            "total_lines": 0,
            "languages": {},
            "start_time": time.time()
        }
        
        # Data collected during analysis
        self.collected_data = {
            "project_info": {},
            "directories": {},
            "important_files": {},
            "file_samples": {},
            "language_stats": {},
            "dependencies": {}
        }
        
        # Store diagram code if visual is enabled
        self.diagram_code = None

    def is_excluded(self, path: Path) -> bool:
        """Check if a path should be excluded based on patterns."""
        rel_path = str(path.relative_to(self.directory))
        
        # Check gitignore-style patterns
        if self.pathspec.match_file(rel_path):
            return True
        
        # Check file size limits
        if path.is_file() and path.stat().st_size > self.max_file_size:
            return True
            
        # Check extension filter
        if self.filter_extensions and path.is_file() and path.suffix not in self.filter_extensions:
            return True
            
        return False

    def is_important_file(self, path: Path) -> bool:
        """Check if a file is an 'important' file based on patterns."""
        filename = path.name
        rel_path = str(path.relative_to(self.directory))
        
        for pattern in IMPORTANT_FILES:
            if '*' in pattern:
                # Handle wildcard pattern
                base_pattern = pattern.replace('*', '')
                if filename.startswith(base_pattern) or filename.endswith(base_pattern):
                    return True
            elif '/' in pattern:
                # Handle path pattern
                if re.match(pattern.replace('*', '.*'), rel_path):
                    return True
            else:
                # Exact match
                if filename == pattern:
                    return True
                
        return False

    def is_text_file(self, path: Path) -> bool:
        """Determine if a file is a text file."""
        # Check extension
        if path.suffix.lower() in TEXT_EXTENSIONS:
            return True
            
        # Try to read the first 4KB as text
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                sample = f.read(4096)
                # Check for null bytes which indicate binary
                if ' ' in sample:
                    return False
                return True
        except Exception:
            return False

    def get_language_from_extension(self, extension: str) -> str:
        """Map file extensions to programming languages."""
        extension = extension.lower()
        
        extension_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript (React)',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript (React)',
            '.java': 'Java',
            '.c': 'C',
            '.cpp': 'C++',
            '.cc': 'C++',
            '.h': 'C/C++ Header',
            '.hpp': 'C++ Header',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.html': 'HTML',
            '.htm': 'HTML',
            '.css': 'CSS',
            '.scss': 'SCSS',
            '.sass': 'Sass',
            '.less': 'Less',
            '.md': 'Markdown',
            '.rst': 'reStructuredText',
            '.json': 'JSON',
            '.xml': 'XML',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.toml': 'TOML',
            '.ini': 'INI',
            '.sh': 'Shell Script',
            '.bash': 'Bash Script',
            '.zsh': 'Zsh Script',
            '.bat': 'Batch File',
            '.ps1': 'PowerShell',
            '.sql': 'SQL',
            '.r': 'R',
            '.kt': 'Kotlin',
            '.swift': 'Swift',
            '.dart': 'Dart',
            '.vue': 'Vue',
            '.svelte': 'Svelte',
            '.graphql': 'GraphQL',
            '.proto': 'Protocol Buffers',
            '.lua': 'Lua',
            '.ex': 'Elixir',
            '.exs': 'Elixir Script',
            '.erl': 'Erlang',
            '.elm': 'Elm',
            '.clj': 'Clojure',
            '.scala': 'Scala',
            '.pl': 'Perl',
            '.pm': 'Perl Module',
            '.tf': 'Terraform',
            '.sol': 'Solidity',
            '.jl': 'Julia',
        }
        
        return extension_map.get(extension, f"Unknown ({extension})")

    def scan_directory(self) -> Dict[str, Any]:
        """
        Scan the directory and collect information about the codebase.
        
        Returns:
            Dictionary with collected data
        """
        # If focus is set, adjust the starting directory
        scan_root = self.focus_dir if self.focus_dir else self.directory
        
        console.print(Panel(f"🔍 Scanning directory: {scan_root}", 
                           title="[bold blue]Analysis Started",
                           border_style="blue"))
        
        # Find all files
        all_files = []
        for root, dirs, files in os.walk(scan_root, followlinks=self.follow_symlinks):
            root_path = Path(root)
            
            # Apply directory exclusions in-place
            dirs[:] = [d for d in dirs if not self.is_excluded(root_path / d)]
            
            for file in files:
                file_path = root_path / file
                if not self.is_excluded(file_path):
                    all_files.append(file_path)
        
        self.stats["total_files"] = len(all_files)
        
        # Prioritize important files and get a good distribution of file types
        important_files = [f for f in all_files if self.is_important_file(f)]
        other_files = [f for f in all_files if f not in important_files]
        
        # Group by extension to ensure representation from various file types
        file_by_extension = {}
        for file in other_files:
            ext = file.suffix
            if ext not in file_by_extension:
                file_by_extension[ext] = []
            file_by_extension[ext].append(file)
        
        # Compile the list of files to analyze 
        prioritized_files = important_files.copy()
        
        # If filter_extensions is specified, prioritize those files
        if self.filter_extensions:
            filtered_files = [f for f in other_files if f.suffix in self.filter_extensions]
            remaining_files = [f for f in other_files if f.suffix not in self.filter_extensions]
            
            # Take as many filtered files as possible within max_files limit
            filtered_to_take = min(len(filtered_files), self.max_files - len(prioritized_files))
            prioritized_files.extend(filtered_files[:filtered_to_take])
            
            # If we still have space, add files from other extensions
            if len(prioritized_files) < self.max_files:
                # Add representative files from each extension type
                num_per_extension = max(1, (self.max_files - len(prioritized_files)) // (len(file_by_extension) or 1))
                for ext, files in file_by_extension.items():
                    if ext not in self.filter_extensions:
                        prioritized_files.extend(files[:num_per_extension])
                        if len(prioritized_files) >= self.max_files:
                            break
        else:
            # Regular prioritization (same as before)
            # Add representative files from each extension type
            num_per_extension = max(1, (self.max_files - len(important_files)) // (len(file_by_extension) or 1))
            for ext, files in file_by_extension.items():
                prioritized_files.extend(files[:num_per_extension])
                if len(prioritized_files) >= self.max_files:
                    break
                
        # If we still have space, add more files
        if len(prioritized_files) < self.max_files:
            remaining_files = [f for f in other_files if f not in prioritized_files]
            prioritized_files.extend(remaining_files[:self.max_files - len(prioritized_files)])
        
        # Limit to max_files
        files_to_analyze = prioritized_files[:self.max_files]
        
        # Collect project info
        self.collected_data["project_info"] = self.get_project_info()
        
        # Analyze files with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[bold]{task.completed}/{task.total}"),
            console=console
        ) as progress:
            task = progress.add_task("[yellow]Analyzing files...", total=len(files_to_analyze))
            
            for file_path in files_to_analyze:
                try:
                    self.analyze_file(file_path)
                    self.stats["analyzed_files"] += 1
                except Exception as e:
                    self.stats["skipped_files"] += 1
                    console.print(f"[red]Error analyzing {file_path}: {e}")
                
                progress.update(task, advance=1, description=f"[yellow]Analyzing {self.stats['analyzed_files']}/{len(files_to_analyze)} files")
        
        # Generate language statistics
        self.collected_data["language_stats"] = {
            lang: {"files": count, "percentage": count / max(1, self.stats["analyzed_files"]) * 100} 
            for lang, count in self.stats["languages"].items()
        }
        
        # Get directory structure
        self.collected_data["directories"] = self.analyze_directory_structure()
        
        # Collect dependency info
        self.collected_data["dependencies"] = self.analyze_dependencies()
        
        # Add focus information if applicable
        if self.focus:
            self.collected_data["focus"] = str(self.focus)
        
        # Add scan statistics
        self.collected_data["statistics"] = {
            "total_files": self.stats["total_files"],
            "analyzed_files": self.stats["analyzed_files"],
            "skipped_files": self.stats["skipped_files"],
            "total_lines": self.stats["total_lines"],
            "scan_duration_seconds": time.time() - self.stats["start_time"]
        }
        
        return self.collected_data

    def analyze_file(self, file_path: Path) -> None:
        """
        Analyze a single file and add its information to the collected data.
        
        Args:
            file_path: Path to the file to analyze
        """
        rel_path = str(file_path.relative_to(self.directory))
        
        # Skip if file is too large
        if file_path.stat().st_size > self.max_file_size:
            return
            
        # Get file info
        extension = file_path.suffix
        language = self.get_language_from_extension(extension)
        
        # Update language stats
        if language in self.stats["languages"]:
            self.stats["languages"][language] += 1
        else:
            self.stats["languages"][language] = 1
        
        # Get file content (for text files only)
        content = ""
        if self.is_text_file(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    self.stats["total_lines"] += len(lines)
                    
                    # Get a representative sample of the file
                    if len(lines) > 20:
                        # Get first 10 and last 10 lines
                        content = ''.join(lines[:10] + ['...\n'] + lines[-10:])
                    else:
                        content = ''.join(lines)
            except Exception as e:
                content = f"Error reading file: {e}"
        else:
            content = "[Binary file]"
            
        # Store file info in the appropriate category
        file_info = {
            "path": rel_path,
            "language": language,
            "size_bytes": file_path.stat().st_size,
            "lines": content.count('\n') + 1,
            "sample": content[:2000] if len(content) > 2000 else content  # Limit sample size
        }
        
        if self.is_important_file(file_path):
            self.collected_data["important_files"][rel_path] = file_info
        else:
            self.collected_data["file_samples"][rel_path] = file_info

    def analyze_directory_structure(self) -> Dict[str, Any]:
        """
        Analyze the directory structure of the codebase.
        
        Returns:
            Dictionary with directory structure information
        """
        directories = {}
        
        # Determine the root for directory analysis
        dir_root = self.focus_dir if self.focus_dir else self.directory
        
        for root, dirs, files in os.walk(dir_root, followlinks=self.follow_symlinks):
            root_path = Path(root)
            if self.is_excluded(root_path):
                continue
                
            # Calculate relative path - relative to focus_dir if focus is set
            if self.focus_dir:
                if root_path == self.focus_dir:
                    rel_path = 'ROOT'
                else:
                    rel_path = str(root_path.relative_to(self.focus_dir))
            else:
                rel_path = str(root_path.relative_to(self.directory))
                if rel_path == '.':
                    rel_path = 'ROOT'
                
            # Count files by type
            file_types = {}
            file_count = 0
            
            for file in files:
                file_path = root_path / file
                if not self.is_excluded(file_path):
                    file_count += 1
                    ext = file_path.suffix
                    language = self.get_language_from_extension(ext)
                    if language in file_types:
                        file_types[language] += 1
                    else:
                        file_types[language] = 1
            
            # Only add directories that contain files
            if file_count > 0 or dirs:
                directories[rel_path] = {
                    "file_count": file_count,
                    "subdirectory_count": len(dirs),
                    "file_types": file_types
                }
                
        return directories

    def get_project_info(self) -> Dict[str, Any]:
        """
        Get general project information.
        
        Returns:
            Dictionary with project information
        """
        project_root = self.focus_dir if self.focus_dir else self.directory
        
        project_info = {
            "name": project_root.name,
            "directory": str(project_root),
            "git_info": self.get_git_info()
        }
        
        if self.focus:
            project_info["focus"] = str(self.focus)
        
        # Look for README
        readme_files = list(project_root.glob("README*"))
        if readme_files:
            try:
                with open(readme_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Truncate if too long
                    max_readme = 3000  # About 750 tokens
                    project_info["readme"] = (
                        content[:max_readme] + "..." if len(content) > max_readme else content
                    )
            except Exception as e:
                project_info["readme_error"] = str(e)
                
        return project_info

    def get_git_info(self) -> Dict[str, Any]:
        """
        Get Git repository information.
        
        Returns:
            Dictionary with Git information
        """
        git_info = {}
        git_dir = self.directory / ".git"
        
        if not git_dir.exists():
            return {"has_git": False}
            
        git_info["has_git"] = True
        
        try:
            # Get remote info
            remotes = self.run_git_command(["git", "remote", "-v"])
            if remotes:
                git_info["remotes"] = remotes
                
            # Get current branch
            branch = self.run_git_command(["git", "branch", "--show-current"])
            if branch:
                git_info["current_branch"] = branch
                
            # Get latest commit
            commit = self.run_git_command(["git", "log", "-1", "--pretty=format:%h - %s (%ar) by %an"])
            if commit:
                git_info["latest_commit"] = commit
                
            # Get top 5 contributors
            contributors = self.run_git_command(["git", "shortlog", "-sn", "--no-merges", "HEAD"])
            if contributors:
                git_info["top_contributors"] = [
                    line.strip() for line in contributors.split('\n')[:5]
                ]
                
        except Exception as e:
            git_info["error"] = str(e)
            
        return git_info

    def analyze_dependencies(self) -> Dict[str, Any]:
        """
        Analyze project dependencies.
        
        Returns:
            Dictionary with dependency information
        """
        dependencies = {}
        project_root = self.focus_dir if self.focus_dir else self.directory
        
        # Check for package.json (Node.js)
        package_json = project_root / "package.json"
        if package_json.exists() and package_json.is_file():
            try:
                with open(package_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    deps = {}
                    if "dependencies" in data:
                        deps["dependencies"] = data["dependencies"]
                    if "devDependencies" in data:
                        deps["devDependencies"] = data["devDependencies"]
                    dependencies["javascript"] = deps
            except Exception as e:
                dependencies["javascript_error"] = str(e)
                
        # Check for requirements.txt (Python)
        requirements_txt = project_root / "requirements.txt"
        if requirements_txt.exists() and requirements_txt.is_file():
            try:
                with open(requirements_txt, 'r', encoding='utf-8') as f:
                    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    dependencies["python"] = requirements
            except Exception as e:
                dependencies["python_error"] = str(e)
                
        # Check for pyproject.toml (Python)
        pyproject_toml = project_root / "pyproject.toml"
        if pyproject_toml.exists() and pyproject_toml.is_file():
            try:
                with open(pyproject_toml, 'r', encoding='utf-8') as f:
                    content = f.read()
                    dependencies["python_pyproject"] = content
            except Exception as e:
                dependencies["python_pyproject_error"] = str(e)
                
        # Check for Cargo.toml (Rust)
        cargo_toml = project_root / "Cargo.toml"
        if cargo_toml.exists() and cargo_toml.is_file():
            try:
                with open(cargo_toml, 'r', encoding='utf-8') as f:
                    content = f.read()
                    dependencies["rust"] = content
            except Exception as e:
                dependencies["rust_error"] = str(e)
        
        # Check for pom.xml (Java/Maven)
        pom_xml = project_root / "pom.xml"
        if pom_xml.exists() and pom_xml.is_file():
            try:
                with open(pom_xml, 'r', encoding='utf-8') as f:
                    content = f.read()
                    dependencies["java"] = content
            except Exception as e:
                dependencies["java_error"] = str(e)
                
        # Check for build.gradle (Java/Gradle)
        build_gradle = project_root / "build.gradle"
        if build_gradle.exists() and build_gradle.is_file():
            try:
                with open(build_gradle, 'r', encoding='utf-8') as f:
                    content = f.read()
                    dependencies["java_gradle"] = content
            except Exception as e:
                dependencies["java_gradle_error"] = str(e)
                
        return dependencies

    def run_git_command(self, command: List[str]) -> str:
        """
        Run a git command and return its output.
        
        Args:
            command: Command to run as a list of strings
            
        Returns:
            Command output as string
        """
        import subprocess
        
        try:
            result = subprocess.run(
                command, 
                cwd=self.directory, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    def generate_map(self) -> str:
        """
        Generate a token-efficient map of the codebase for LLM consumption.
        
        Returns:
            String representation of the codebase map
        """
        console.print(Panel("🧠 Generating codebase map...",
                           title="[bold blue]Processing",
                           border_style="blue"))
        
        # Calculate cache key based on collected data and model
        data_hash = hashlib.md5(json.dumps(self.collected_data, sort_keys=True).encode()).hexdigest()
        cache_key = f"map_{data_hash}_{self.max_map_tokens}_{self.model_name}_{self.mode}_{self.reasoning}_{self.visual}_{self.diagram_format}"
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Check cache
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    console.print(Panel("✅ Using cached codebase map", 
                                      title="[bold green]Cache Hit",
                                      border_style="green"))
                    return cache_data["map"]
            except Exception as e:
                console.print(Panel(f"⚠️ Cache read error: {e}", 
                                   title="[bold yellow]Cache Warning",
                                   border_style="yellow"))
        
        # Convert collected data to a compact representation for LLM consumption
        map_data = {}
        
        # Project name and basic info
        map_data["project"] = self.collected_data["project_info"].get("name", "Unknown")
        
        # Focus information if applicable
        if "focus" in self.collected_data["project_info"]:
            map_data["focus"] = self.collected_data["project_info"]["focus"]
        
        # Git information (if available)
        git_info = self.collected_data["project_info"].get("git_info", {})
        if git_info.get("has_git", False):
            map_data["git"] = {
                "remote": git_info.get("remotes", ""),
                "branch": git_info.get("current_branch", ""),
                "latest_commit": git_info.get("latest_commit", "")
            }
        
        # README summary
        if "readme" in self.collected_data["project_info"]:
            map_data["readme_summary"] = self.collected_data["project_info"]["readme"]
        
        # Directory structure (simplified)
        directories = {}
        for path, info in self.collected_data["directories"].items():
            if path == "ROOT":
                path = "/"
            directories[path] = {
                "files": info["file_count"],
                "main_types": sorted(
                    info["file_types"].items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:3]  # Top 3 file types
            }
        map_data["directories"] = directories
        
        # Language statistics
        map_data["languages"] = {
            lang: {"files": info["files"], "percent": round(info["percentage"], 1)} 
            for lang, info in self.collected_data["language_stats"].items()
        }
        
        # Important files (with samples)
        important_files = {}
        for path, info in self.collected_data["important_files"].items():
            important_files[path] = {
                "language": info["language"],
                "sample": info["sample"]
            }
        map_data["important_files"] = important_files
        
        # Representative file samples
        file_samples = {}
        # Limit the number of samples to keep the map concise
        sample_count = min(15, len(self.collected_data["file_samples"]))
        sample_keys = sorted(self.collected_data["file_samples"].keys())[:sample_count]
        
        for path in sample_keys:
            info = self.collected_data["file_samples"][path]
            file_samples[path] = {
                "language": info["language"],
                "sample": info["sample"]
            }
        map_data["file_samples"] = file_samples
        
        # Dependencies
        map_data["dependencies"] = self.collected_data["dependencies"]
        
        # Statistics
        map_data["stats"] = self.collected_data["statistics"]
        
        # Analysis mode and reasoning depth
        map_data["analysis_mode"] = self.mode
        map_data["reasoning_depth"] = self.reasoning
        
        # Visual diagram request
        if self.visual:
            map_data["visual_diagram"] = {
                "requested": True,
                "format": self.diagram_format
            }
        
        # Convert to a structured string representation
        map_str = self.map_to_string(map_data)
        
        # Cache the result
        try:
            with open(cache_file, 'w') as f:
                json.dump({"map": map_str}, f)
        except Exception as e:
            console.print(Panel(f"⚠️ Cache write error: {e}", 
                              title="[bold yellow]Cache Warning",
                              border_style="yellow"))
        
        return map_str

    def map_to_string(self, map_data: Dict[str, Any]) -> str:
        """
        Convert the map data to a structured string representation.
        
        Args:
            map_data: Dictionary with map data
            
        Returns:
            String representation of the map
        """
        sections = []
        
        # Project section
        project_section = [
            "# PROJECT OVERVIEW",
            f"Project: {map_data['project']}"
        ]
        
        # Focus information
        if "focus" in map_data:
            project_section.append(f"Focus: {map_data['focus']}")
        
        # Analysis mode and reasoning depth
        project_section.append(f"Analysis mode: {map_data['analysis_mode']}")
        project_section.append(f"Reasoning depth: {map_data['reasoning_depth']}")
        
        # Visual diagram request
        if "visual_diagram" in map_data:
            diagram_info = map_data["visual_diagram"]
            project_section.append(f"Visual diagram: Requested (Format: {diagram_info['format']})")
            
        # Git info
        if "git" in map_data:
            git = map_data["git"]
            project_section.extend([
                f"Repository: {git.get('remote', 'N/A')}",
                f"Branch: {git.get('branch', 'N/A')}",
                f"Latest commit: {git.get('latest_commit', 'N/A')}"
            ])
            
        sections.append("\n".join(project_section))
        
        # README summary
        if "readme_summary" in map_data:
            sections.append(
                "# README SUMMARY\n" + 
                textwrap.fill(map_data["readme_summary"], width=80)
            )
        
        # Directory structure
        dir_section = ["# DIRECTORY STRUCTURE"]
        for path, info in sorted(map_data["directories"].items()):
            types_str = ", ".join(f"{t[0]}:{t[1]}" for t in info["main_types"]) if info["main_types"] else ""
            dir_section.append(f"{path}: {info['files']} files ({types_str})")
        sections.append("\n".join(dir_section))
        
        # Language statistics
        lang_section = ["# LANGUAGES"]
        for lang, info in sorted(map_data["languages"].items(), key=lambda x: x[1]["files"], reverse=True):
            lang_section.append(f"{lang}: {info['files']} files ({info['percent']}%)")
        sections.append("\n".join(lang_section))
        
        # Important files
        if map_data["important_files"]:
            imp_section = ["# IMPORTANT FILES"]
            for path, info in sorted(map_data["important_files"].items()):
                imp_section.append(f"## {path} ({info['language']})")
                sample = info['sample']
                if len(sample) > 500:
                    sample = sample[:247] + "...\n[content truncated]\n..." + sample[-247:]
                imp_section.append(f"```\n{sample}\n```")
            sections.append("\n".join(imp_section))
        
        # File samples
        if map_data["file_samples"]:
            sample_section = ["# FILE SAMPLES"]
            for path, info in sorted(map_data["file_samples"].items()):
                sample_section.append(f"## {path} ({info['language']})")
                sample = info['sample']
                if len(sample) > 300:
                    sample = sample[:147] + "...\n[content truncated]\n..." + sample[-147:]
                sample_section.append(f"```\n{sample}\n```")
            sections.append("\n".join(sample_section))
        
        # Dependencies
        if map_data["dependencies"]:
            dep_section = ["# DEPENDENCIES"]
            
            # JavaScript dependencies
            if "javascript" in map_data["dependencies"]:
                js_deps = map_data["dependencies"]["javascript"]
                dep_section.append("## JavaScript")
                if "dependencies" in js_deps:
                    dep_section.append("### Production")
                    deps_list = [f"{k}: {v}" for k, v in js_deps["dependencies"].items()]
                    dep_section.append(", ".join(deps_list[:10]) + ("..." if len(deps_list) > 10 else ""))
                if "devDependencies" in js_deps:
                    dep_section.append("### Development")
                    deps_list = [f"{k}: {v}" for k, v in js_deps["devDependencies"].items()]
                    dep_section.append(", ".join(deps_list[:10]) + ("..." if len(deps_list) > 10 else ""))
            
            # Python dependencies
            if "python" in map_data["dependencies"]:
                py_deps = map_data["dependencies"]["python"]
                dep_section.append("## Python")
                dep_section.append(", ".join(py_deps[:10]) + ("..." if len(py_deps) > 10 else ""))
                
            # Other dependencies (just note their presence)
            other_deps = [k for k in map_data["dependencies"].keys() 
                         if k not in ["javascript", "python"] and not k.endswith("_error")]
            if other_deps:
                dep_section.append(f"## Other: {', '.join(other_deps)}")
                
            sections.append("\n".join(dep_section))
        
        # Statistics
        stats = map_data["stats"]
        stats_section = [
            "# STATISTICS",
            f"Total files: {stats['total_files']}",
            f"Analyzed files: {stats['analyzed_files']}",
            f"Total lines of code: {stats['total_lines']}",
            f"Scan duration: {stats['scan_duration_seconds']:.2f} seconds"
        ]
        sections.append("\n".join(stats_section))
        
        return "\n\n" + "\n\n".join(sections)

    def analyze_codebase(self) -> str:
        """
        Analyze the codebase using LLM.
        
        Returns:
            Analysis results as string
        """
        # First collect data
        self.scan_directory()
        
        # Generate codebase map
        codebase_map = self.generate_map()
        
        # Calculate cache key based on collected map and model
        map_hash = hashlib.md5(codebase_map.encode()).hexdigest()
        cache_key = f"analysis_{map_hash}_{self.model_name}_{self.mode}_{self.reasoning}_{self.visual}_{self.diagram_format}"
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Check cache
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    console.print(Panel("✅ Using cached analysis results", 
                                      title="[bold green]Cache Hit",
                                      border_style="green"))
                    
                    # If visual diagram was requested and exists in cache, store it
                    if self.visual and "diagram_code" in cache_data:
                        self.diagram_code = cache_data["diagram_code"]
                        
                    return cache_data["analysis"]
            except Exception as e:
                console.print(Panel(f"⚠️ Cache read error: {e}", 
                                   title="[bold yellow]Cache Warning",
                                   border_style="yellow"))
        
        console.print(Panel("🧠 Analyzing codebase with LLM...", 
                          title="[bold blue]AI Analysis",
                          border_style="blue"))
        
        # Prepare system prompt based on analysis mode
        system_prompts = {
            "overview": """You are a codebase analysis expert. Your task is to analyze the provided codebase structure and information, 
and provide a concise, insightful overview that would help a developer understand the project quickly.

Your analysis should include:
1. A brief overview of what the project is and does
2. The architecture and main components
3. Key technologies and dependencies
4. Code organization patterns
5. Suggestions or recommendations (optional)

Be concise and focus on the most important aspects. Look for patterns in the directory structure, key files, and code samples.
""",
            "components": """You are a codebase analysis expert. Your task is to analyze the provided codebase structure and information,
and identify the key components and modules of the project and their responsibilities.

Your analysis should focus on:
1. Breaking down the codebase into logical components
2. Explaining the purpose and behavior of each component
3. Identifying relationships between components
4. Understanding the design patterns used

Provide a detailed component breakdown with clear explanations of what each part does.
""",
            "architecture": """You are a codebase architecture expert. Your task is to analyze the provided codebase structure and information,
and explain the architectural patterns and system organization.

Your analysis should focus on:
1. The high-level architectural style (e.g., MVC, microservices, layered)
2. System boundaries and separations of concerns
3. How different parts of the system interact
4. Architectural decisions and their implications
5. Evaluating architectural strengths and weaknesses

Provide a detailed breakdown of the architectural patterns and explain how they work together.
""",
            "flows": """You are a codebase analysis expert. Your task is to analyze the provided codebase structure and information,
and identify key data and control flows through the system.

Your analysis should focus on:
1. How data moves through the system
2. Main execution paths and control flows
3. Key entry points and exit points
4. How components communicate and interact
5. Identifying any bottlenecks or critical paths

Provide a clear explanation of the system's flows with examples where possible.
"""
        }
        
        system_prompt = system_prompts.get(self.mode, system_prompts["overview"])
        
        # Add reasoning depth instructions
        reasoning_instructions = {
            0: "Provide only the most concise, summarized analysis with minimal explanation.",
            1: "Keep explanations brief and focus only on the most important observations.",
            2: "Offer a streamlined analysis with limited supporting details.",
            3: "Balance conciseness with some supporting explanation where needed.",
            4: "Provide a moderately detailed analysis with key reasoning included.",
            5: "Balance detail and brevity, with clear reasoning for important insights.",
            6: "Include detailed explanations and reasoning for your key observations.",
            7: "Provide thorough explanations with detailed reasoning and examples.",
            8: "Deliver comprehensive analysis with in-depth reasoning and multiple examples.",
            9: "Offer the most detailed, thorough analysis possible with extensive reasoning."
        }
        
        system_prompt += f"\n\nReasoning depth: {reasoning_instructions[self.reasoning]}"
        
        # Add visual diagram instructions based on the diagram format
        if self.visual:
            if self.diagram_format == "graphviz":
                system_prompt += """

If a visual diagram is requested, include a section in your response with a Graphviz DOT format diagram that represents the codebase architecture. The diagram should:
1. Show key components and their relationships
2. Use appropriate node shapes (boxes, ovals, etc.) for different types of components
3. Use descriptive labels
4. Group related components when appropriate
5. Use directed edges to show data/control flow or dependencies
6. Include a simple color scheme to categorize components

Provide the diagram code in a section marked with <diagram>...</diagram> tags. Use the DOT language for the diagram.
Example:
<diagram>
digraph G {
  rankdir=LR;
  node [shape=box, style=filled, color=lightblue];
  
  // Components
  A [label="Component A"];
  B [label="Component B"];
  
  // Relationships
  A -> B [label="uses"];
}
</diagram>
"""
            elif self.diagram_format == "mermaid":
                system_prompt += """

If a visual diagram is requested, include a section in your response with a Mermaid diagram that represents the codebase architecture. The diagram should:
1. Show key components and their relationships
2. Use appropriate node shapes and styles for different types of components
3. Use descriptive labels
4. Group related components when appropriate
5. Use directed edges to show data/control flow or dependencies
6. Use colors to categorize components where appropriate

Provide the diagram code in a section marked with <diagram>...</diagram> tags. Use the Mermaid language for the diagram.
Example:
<diagram>
graph LR
    A[Component A] --> B[Component B]
    A --> C[Component C]
    B --> D[Component D]
    C --> D
    
    classDef core fill:#f9f,stroke:#333,stroke-width:2px;
    classDef util fill:#bbf,stroke:#333,stroke-width:1px;
    
    class A,B core;
    class C,D util;
</diagram>

Make sure to use the correct Mermaid syntax for the diagram type (flowchart, sequence, class, etc.) that best represents the architecture.
"""
            elif self.diagram_format == "plantuml":
                system_prompt += """

If a visual diagram is requested, include a section in your response with a PlantUML diagram that represents the codebase architecture. The diagram should:
1. Show key components and their relationships
2. Use appropriate UML notation for different types of components
3. Use descriptive labels
4. Group related components when appropriate
5. Use directed edges to show data/control flow or dependencies
6. Use colors or stereotypes to categorize components where appropriate

Provide the diagram code in a section marked with <diagram>...</diagram> tags. Use the PlantUML language for the diagram.
Example:
<diagram>
@startuml
package "Core Components" {
  [Component A] as A
  [Component B] as B
}

package "Utilities" {
  [Component C] as C
  [Component D] as D
}

A --> B
A --> C
B --> D
C --> D
@enduml
</diagram>

Choose the appropriate PlantUML diagram type (component, class, sequence, etc.) that best represents the architecture.
"""
        
        # Prepare the prompt based on diagram format
        if self.visual:
            if self.diagram_format == "mermaid":
                diagram_section = """
<diagram>
// Create a Mermaid diagram (flowchart, class diagram, etc.) that visualizes 
// the architecture and component relationships
// Use appropriate node shapes, colors, and edge labels
graph LR
  // Your diagram code here
</diagram>
"""
            elif self.diagram_format == "plantuml":
                diagram_section = """
<diagram>
// Create a PlantUML diagram that visualizes the architecture and component relationships
// Use appropriate UML notation, colors, and stereotypes
@startuml
  // Your diagram code here
@enduml
</diagram>
"""
            else:  # graphviz as default
                diagram_section = """
<diagram>
// Create a GraphViz DOT diagram that visualizes the architecture and component relationships
// Use appropriate node shapes, colors, and edge labels
digraph G {
  // Your diagram code here
}
</diagram>
"""
                
            prompt = f"""Analyze this codebase based on the structured information below:

{codebase_map}

Provide your analysis in the following format:

<overview>
Brief overview of the project purpose and functionality
</overview>

<architecture>
Key architectural patterns and components
</architecture>

<components>
Main modules/components and their responsibilities
</components>

<workflows>
How data and control flow through the system
</workflows>

{diagram_section}

<recommendations>
Optional suggestions for improvements or areas to explore
</recommendations>

Keep your analysis concise and focused on the most important aspects of the codebase.
For the diagram, create a clear visualization of the architecture that shows the main components and their relationships.
"""
        else:
            prompt = f"""Analyze this codebase based on the structured information below:

{codebase_map}

Provide your analysis in the following format:

<overview>
Brief overview of the project purpose and functionality
</overview>

<architecture>
Key architectural patterns and components
</architecture>

<components>
Main modules/components and their responsibilities
</components>

<workflows>
How data and control flow through the system
</workflows>

<recommendations>
Optional suggestions for improvements or areas to explore
</recommendations>

Keep your analysis concise and focused on the most important aspects of the codebase.
"""
        
        # Get analysis from LLM
        response = self.model.prompt(prompt, system=system_prompt).text()
        
        # Extract diagram code if present
        if self.visual:
            diagram_match = re.search(r'<diagram>(.*?)</diagram>', response, re.DOTALL)
            if diagram_match:
                self.diagram_code = diagram_match.group(1).strip()
                
                # For Mermaid and PlantUML, clean up the code blocks
                if self.diagram_format in ["mermaid", "plantuml"]:
                    # Remove the markdown code block markers if present
                    self.diagram_code = re.sub(r'^```(mermaid|plantuml)\s*\n', '', self.diagram_code)
                    self.diagram_code = re.sub(r'\n```\s*$', '', self.diagram_code)
        
        # Cache the result
        try:
            cache_data = {"analysis": response}
            if self.visual and self.diagram_code:
                cache_data["diagram_code"] = self.diagram_code
                
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            console.print(Panel(f"⚠️ Cache write error: {e}", 
                               title="[bold yellow]Cache Warning",
                               border_style="yellow"))
            
        return response

    def generate_diagram(self) -> Optional[str]:
        """
        Generate a visual diagram based on the selected format.
        
        Returns:
            Path to the generated diagram file or None if generation failed
        """
        if not self.diagram_code:
            console.print(Panel("⚠️ No diagram code available to generate visual", 
                              title="[bold yellow]Diagram Error",
                              border_style="yellow"))
            return None
            
        # Determine the file extension and generation method based on format
        if self.diagram_format == "graphviz":
            return self._generate_graphviz_diagram()
        elif self.diagram_format == "mermaid":
            return self._generate_markdown_diagram("mermaid")
        elif self.diagram_format == "plantuml":
            return self._generate_markdown_diagram("plantuml")
        else:
            console.print(Panel(f"⚠️ Unsupported diagram format: {self.diagram_format}", 
                              title="[bold yellow]Diagram Error",
                              border_style="yellow"))
            return None

    def _generate_graphviz_diagram(self) -> Optional[str]:
        """
        Generate a visual diagram using Graphviz.
        
        Returns:
            Path to the generated diagram file or None if generation failed
        """
        # Check if Graphviz is installed
        graphviz_available = shutil.which("dot") is not None
        
        if not graphviz_available:
            console.print(Panel("⚠️ Graphviz not found. Install Graphviz to generate visual diagrams.",
                              title="[bold yellow]Graphviz Missing",
                              border_style="yellow"))
            
            # Save the diagram code to a file so the user can use it later
            if self.output_is_dir:
                dot_file = self.output_path / "diagram.dot"
            else:
                # If no output directory is specified, save in the current directory
                dot_file = Path("diagram.dot")
                
            try:
                with open(dot_file, 'w') as f:
                    f.write(self.diagram_code)
                console.print(Panel(f"💾 Diagram code saved to {dot_file}\nYou can generate the image with: dot -Tpng {dot_file} -o diagram.png",
                                  title="[bold blue]Diagram Code Saved",
                                  border_style="blue"))
                return str(dot_file)
            except Exception as e:
                console.print(Panel(f"❌ Error saving diagram code: {e}",
                                  title="[bold red]Error",
                                  border_style="red"))
                return None
        
        # Determine the output file path
        if self.output_is_dir:
            diagram_file = self.output_path / "diagram.png"
        elif self.output_path:
            # Use the output path directory but with .png extension
            diagram_file = self.output_path.with_suffix(".png")
        else:
            # Default to the current directory
            diagram_file = Path("diagram.png")
            
        # Save the DOT code to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as tmp:
            tmp.write(self.diagram_code)
            tmp_path = tmp.name
            
        try:
            # Try to generate the diagram using the command line tool
            import subprocess
            result = subprocess.run(
                ["dot", "-Tpng", tmp_path, "-o", str(diagram_file)],
                capture_output=True,
                text=True,
                check=True
            )
            
            console.print(Panel(f"✅ Diagram generated and saved to {diagram_file}",
                              title="[bold green]Diagram Generated",
                              border_style="green"))
            return str(diagram_file)
        except Exception as e:
            console.print(Panel(f"❌ Error generating diagram: {e}",
                              title="[bold red]Diagram Error",
                              border_style="red"))
            
            # Save the DOT file as a fallback
            dot_file = diagram_file.with_suffix(".dot")
            try:
                with open(dot_file, 'w') as f:
                    f.write(self.diagram_code)
                console.print(Panel(f"💾 Diagram code saved to {dot_file}",
                                  title="[bold blue]Diagram Code Saved",
                                  border_style="blue"))
                return str(dot_file)
            except Exception as nested_e:
                console.print(Panel(f"❌ Error saving diagram code: {nested_e}",
                                  title="[bold red]Error",
                                  border_style="red"))
            return None
        finally:
            # Clean up the temporary file
            try:
                os.unlink(tmp_path)
            except:
                pass

    def _generate_markdown_diagram(self, format_type: str) -> Optional[str]:
        """
        Generate a Markdown-compatible diagram (Mermaid or PlantUML).
        
        Args:
            format_type: Either "mermaid" or "plantuml"
            
        Returns:
            Path to the generated Markdown file or None if generation failed
        """
        # Determine the output file path
        if self.output_is_dir:
            markdown_file = self.output_path / "diagram.md"
        elif self.output_path:
            # Use the output path directory but with .md extension
            markdown_file = self.output_path.with_suffix(".md")
        else:
            # Default to the current directory
            markdown_file = Path("diagram.md")
        
        # Create the markdown content with the diagram
        diagram_header = f"# Codebase Architecture Diagram\n\n"
        
        if format_type == "mermaid":
            markdown_content = f"{diagram_header}```mermaid\n{self.diagram_code}\n```\n"
        else:  # plantuml
            markdown_content = f"{diagram_header}```plantuml\n{self.diagram_code}\n```\n"
        
        # Add notes about viewing the diagram
        if format_type == "mermaid":
            markdown_content += """
## Viewing Instructions

This diagram uses [Mermaid](https://mermaid-js.github.io/mermaid/), which is supported by:

- GitHub markdown (directly viewable in GitHub repositories)
- VS Code with the Markdown Preview Mermaid Support extension
- Most modern Markdown editors
- Online at [Mermaid Live Editor](https://mermaid.live/)
"""
        else:  # plantuml
            markdown_content += """
## Viewing Instructions

This diagram uses [PlantUML](https://plantuml.com/), which can be viewed:

- With a PlantUML plugin for your IDE (like VS Code's PlantUML extension)
- By installing the PlantUML server locally
- Online at [PlantUML Web Server](http://www.plantuml.com/plantuml/uml/)
"""
        
        # Save the markdown file
        try:
            with open(markdown_file, 'w') as f:
                f.write(markdown_content)
            console.print(Panel(f"✅ Markdown diagram saved to {markdown_file}",
                              title=f"[bold green]{format_type.capitalize()} Diagram Generated",
                              border_style="green"))
            return str(markdown_file)
        except Exception as e:
            console.print(Panel(f"❌ Error saving markdown diagram: {e}",
                              title="[bold red]Error",
                              border_style="red"))
            return None

    def save_output(self, content: str) -> None:
        """
        Save analysis results to output file or directory.
        
        Args:
            content: Content to save
        """
        if not self.output_path:
            return
            
        try:
            if self.output_is_dir:
                output_file = self.output_path / "analysis.md"
            else:
                output_file = self.output_path
                
            # Add diagram embed to markdown if using markdown diagram formats
            if self.visual and self.diagram_code and self.diagram_format in ["mermaid", "plantuml"]:
                # Check if the analysis already has a diagram section
                if not re.search(r'<diagram>.*?</diagram>', content, re.DOTALL):
                    # Insert the diagram immediately after the workflows section
                    workflow_pattern = r'(</workflows>)'
                    
                    if self.diagram_format == "mermaid":
                        diagram_insert = '\n\n## Architecture Diagram\n\n```mermaid\n' + self.diagram_code + '\n```\n'
                    else:  # plantuml
                        diagram_insert = '\n\n## Architecture Diagram\n\n```plantuml\n' + self.diagram_code + '\n```\n'
                    
                    content = re.sub(workflow_pattern, r'\1' + diagram_insert, content)
                else:
                    # If a diagram section already exists, replace it with the markdown formatted diagram
                    diagram_pattern = r'<diagram>(.*?)</diagram>'
                    if self.diagram_format == "mermaid":
                        diagram_replacement = '\n\n## Architecture Diagram\n\n```mermaid\n' + self.diagram_code + '\n```\n'
                    else:  # plantuml
                        diagram_replacement = '\n\n## Architecture Diagram\n\n```plantuml\n' + self.diagram_code + '\n```\n'
                    
                    content = re.sub(diagram_pattern, diagram_replacement, content, flags=re.DOTALL)
                
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            console.print(Panel(f"✅ Analysis saved to {output_file}",
                              title="[bold green]Output Saved",
                              border_style="green"))
        except Exception as e:
            console.print(Panel(f"❌ Error saving analysis: {e}",
                              title="[bold red]Error",
                              border_style="red"))

    def display_summary(self, analysis: str) -> None:
        """
        Display a formatted summary of the analysis using rich library.
        
        Args:
            analysis: The full analysis text
        """
        # Create layout for rich display
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body")
        )
        
        # Header with project name and stats
        project_name = self.collected_data["project_info"].get("name", "Unknown")
        stats = self.collected_data["statistics"]
        
        header_text = f"[bold blue]📊 Analysis of [green]{project_name}[/green] | " + \
                     f"[cyan]{stats['analyzed_files']}[/cyan] files | " + \
                     f"[cyan]{stats['total_lines']}[/cyan] lines of code | " + \
                     f"Mode: [yellow]{self.mode}[/yellow]"
        
        layout["header"].update(Panel(header_text, border_style="blue"))
        
        # Extract sections from the analysis
        sections = {}
        for section in ["overview", "architecture", "components", "workflows", "recommendations"]:
            pattern = f"<{section}>(.*?)</{section}>"
            match = re.search(pattern, analysis, re.DOTALL)
            sections[section] = match.group(1).strip() if match else ""
        
        # Create a table for the body content
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Section", style="dim")
        table.add_column("Content")
        
        # Add table rows with emojis for each section
        section_emojis = {
            "overview": "🔍",
            "architecture": "🏗️",
            "components": "🧩",
            "workflows": "🔄",
            "recommendations": "💡"
        }
        
        section_titles = {
            "overview": "Overview",
            "architecture": "Architecture",
            "components": "Components",
            "workflows": "Workflows",
            "recommendations": "Recommendations"
        }
        
        # Add each section to the table
        for section, content in sections.items():
            if content:
                emoji = section_emojis.get(section, "")
                title = section_titles.get(section, section.capitalize())
                # Truncate content for display if too long
                display_content = content
                if len(display_content) > 500:
                    display_content = display_content[:497] + "..."
                table.add_row(f"{emoji} {title}", display_content)
        
        layout["body"].update(table)
        
        # Show diagram info if applicable
        if self.visual and self.diagram_code:
            diagram_format_display = {
                "graphviz": "Graphviz DOT",
                "mermaid": "Mermaid",
                "plantuml": "PlantUML"
            }.get(self.diagram_format, self.diagram_format.capitalize())
            
            diagram_info = Panel(
                f"[bold green]✅ {diagram_format_display} diagram generated" + 
                (" and saved" if self.output_path else ""),
                title="[bold blue]Diagram",
                border_style="green"
            )
            print()  # Add some spacing
            console.print(diagram_info)
        
        # Print the layout
        console.print(layout)
        
        # Add information about saved files
        if self.output_path:
            output_info = []
            if self.output_is_dir:
                output_info.append(f"📂 Output directory: [bold cyan]{self.output_path}[/bold cyan]")
                output_info.append(f"   └─ Analysis: [cyan]{self.output_path}/analysis.md[/cyan]")
                if self.visual:
                    if self.diagram_format == "graphviz":
                        output_info.append(f"   └─ Diagram: [cyan]{self.output_path}/diagram.png[/cyan]")
                    else:
                        output_info.append(f"   └─ Diagram: [cyan]{self.output_path}/diagram.md[/cyan]")
            else:
                output_info.append(f"📄 Analysis saved to: [bold cyan]{self.output_path}[/bold cyan]")
                if self.visual:
                    if self.diagram_format == "graphviz":
                        diagram_path = self.output_path.with_suffix(".png")
                        output_info.append(f"📊 Diagram saved to: [bold cyan]{diagram_path}[/bold cyan]")
                    else:
                        diagram_path = self.output_path.with_suffix(".md")
                        output_info.append(f"📊 Diagram saved to: [bold cyan]{diagram_path}[/bold cyan]")
            
            print()  # Add some spacing
            console.print("\n".join(output_info))

    def run(self) -> str:
        """
        Run the full codebase analysis process.
        
        Returns:
            Analysis results as string
        """
        try:
            # Perform codebase analysis
            analysis = self.analyze_codebase()
            
            # Generate diagram if requested
            if self.visual and self.diagram_code:
                self.generate_diagram()
                
            # Save output
            if self.output_path:
                self.save_output(analysis)
            
            # Display summary with rich formatting
            self.display_summary(analysis)
                
            if self.json_format:
                # Extract sections
                sections = {}
                for section in ["overview", "architecture", "components", "workflows", "recommendations"]:
                    pattern = f"<{section}>(.*?)</{section}>"
                    match = re.search(pattern, analysis, re.DOTALL)
                    sections[section] = match.group(1).strip() if match else ""
                
                # Add diagram code if present
                if self.diagram_code:
                    sections["diagram"] = {
                        "format": self.diagram_format,
                        "code": self.diagram_code
                    }
                    
                return json.dumps(sections, indent=2)
            
            return analysis
            
        except Exception as e:
            console.print(Panel(f"❌ Error during analysis: {e}",
                             title="[bold red]Error",
                             border_style="red"))
            raise

# Register the LLM plugin command
from llm_cartographer.codebase_navigator import CodebaseNavigator

@llm.hookimpl
def register_commands(cli):
    @cli.command(name="cartographer")
    @click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=".")
    @click.option("--exclude", "-e", multiple=True, help="Patterns to exclude (gitignore format)")
    @click.option("--max-files", type=int, default=100, help="Maximum number of files to analyze")
    @click.option("--max-file-size", type=int, default=DEFAULT_MAX_FILE_SIZE, help="Maximum file size in bytes")
    @click.option("--output", "-o", type=click.Path(), help="Output file path or directory")
    @click.option("--model", "-m", help="LLM model to use")
    @click.option("--follow-symlinks", is_flag=True, help="Follow symbolic links")
    @click.option("--json", is_flag=True, help="Output as JSON")
    @click.option("--filter-extension", "-f", multiple=True, help="Only include files with these extensions")
    @click.option("--cache-dir", help="Cache directory path")
    @click.option("--mode", type=click.Choice(list(ANALYSIS_MODES.keys())), default="overview",
                  help="Analysis mode (overview, components, architecture, flows)")
    @click.option("--focus", help="Focus analysis on a specific subdirectory")
    @click.option("--reasoning", type=click.IntRange(0, 9), default=5, 
                  help="Reasoning depth (0-9, where 0=minimal and 9=maximum)")
    @click.option("--visual", is_flag=True, help="Generate visual diagram of codebase architecture")
    @click.option("--diagram-format", type=click.Choice(DIAGRAM_FORMATS), default="graphviz",
                  help="Format for diagram generation (graphviz, mermaid, plantuml)")
    @click.option("--llm-nav", is_flag=True, help="Generate LLM-optimized navigation structure")
    @click.option("--nav-format", type=click.Choice(['markdown', 'json', 'compact']), default='markdown',
                  help="Format for LLM navigation output")
    @click.option("--include-source", is_flag=True, 
                  help="Include source code snippets for functions and methods in navigation output")
    def cartographer(directory, exclude, max_files, max_file_size, output, model, follow_symlinks, 
                    json, filter_extension, cache_dir, mode, focus, reasoning, visual, diagram_format,
                    llm_nav, nav_format, include_source):
        """Map and analyze a codebase or project structure."""
        try:
            filter_extensions = set(f".{ext.lstrip('.')}" for ext in filter_extension) if filter_extension else None
            
            analyzer = CodebaseCartographer(
                directory=directory,
                exclude=exclude or None,
                max_files=max_files,
                max_file_size=max_file_size,
                output=output,
                model=model,
                follow_symlinks=follow_symlinks,
                cache_dir=cache_dir,
                json_format=json,
                filter_extensions=filter_extensions,
                mode=mode,
                focus=focus,
                reasoning=reasoning,
                visual=visual,
                diagram_format=diagram_format
            )
            
            # If LLM navigation is requested, generate that instead of regular analysis
            if llm_nav:
                # First scan the directory to collect data
                collected_data = analyzer.scan_directory()
                
                # Create the navigator
                focus_dir = analyzer.focus_dir if analyzer.focus else None
                navigator = CodebaseNavigator(
                    directory=analyzer.directory,
                    collected_data=collected_data,
                    focus=focus_dir,
                    include_source=include_source
                )
                
                # Generate the navigation output
                nav_output = navigator.generate_llm_output(format=nav_format)
                
                # Save or display the output
                if output:
                    if analyzer.output_is_dir:
                        output_file = Path(output) / f"navigation.{nav_format}"
                    else:
                        output_file = Path(output)
                    
                    with open(output_file, 'w') as f:
                        f.write(nav_output)
                    console.print(f"[green]Navigation output saved to: {output_file}")
                
                # Print the output if JSON format or explicitly requested
                if json or not output:
                    click.echo(nav_output)
            else:
                # Regular analysis flow
                result = analyzer.run()
                if json:
                    click.echo(result)
            
        except Exception as e:
            console.print(f"[bold red]Error: {e}")
            raise click.Abort()
