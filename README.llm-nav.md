# LLM-Optimized Codebase Navigation

This feature enhances llm-cartographer with a specialized output format designed specifically for LLM agents to efficiently navigate codebases.

## Problem Solved

Traditional codebase summaries are designed for human readers and are inefficient for LLM agents:

- They use too many tokens on descriptive text that doesn't help with navigation
- They lack explicit structural links between components
- They emphasize readability over functional navigation

## Features

The LLM-optimized navigation map provides:

- **Import/dependency graphs**: Shows which files import which, making relationships explicit
- **Function/method index**: Maps all functions to their locations with parameter information
- **Entry point identification**: Highlights key entry points to the codebase
- **Navigation paths**: Defines common paths through the codebase for common tasks
- **Compact representation**: Minimizes token usage while maximizing navigational value

## Usage

### CLI Plugin

```bash
llm cartographer /path/to/codebase --llm-nav --nav-format markdown
```

Options:
- `--llm-nav`: Enable the LLM navigation mode
- `--nav-format`: Choose format (markdown, json, or compact)
- `--include-source`: Include source code snippets in the output
- `-o`: Save output to file

### Direct Python Usage

```python
from llm_cartographer import CodebaseCartographer
from llm_cartographer.codebase_navigator import CodebaseNavigator
from pathlib import Path

# First collect data
cartographer = CodebaseCartographer(directory="/path/to/codebase")
collected_data = cartographer.scan_directory()

# Then create the navigator
navigator = CodebaseNavigator(
    directory=Path("/path/to/codebase"),
    collected_data=collected_data,
    include_source=True  # Optional
)

# Generate output
navigation_map = navigator.generate_llm_output(format="json")
```

### Standalone Script

```bash
python -m llm_cartographer.cli_navigator /path/to/codebase -o navigation_map.md
```

## Output Formats

### Markdown

Structured markdown format with sections for key files, functions, classes, and import relationships.
Good for human readability while still being LLM-efficient.

### JSON

Complete structured data including all file relationships, function definitions, and navigation paths.
Best for programmatic usage and most detailed analysis.

### Compact

Ultra-dense format optimized for minimal token usage.
Best for large codebases or when token economy is critical.

## Example

```
# MyProject Navigation Map

## KEY FILES
- `main.py` (Python) - Imports: 5, Imported by: 0
- `utils/helpers.py` (Python) - Imports: 2, Imported by: 8

## ENTRY POINTS
- `main.py` - Matches entry point pattern main\.py$
- `cli.py` - Imports 4 modules but isn't imported by others

## FUNCTION INDEX
- `main.py:run_app(config_path, debug)` - L15
- `utils/database.py:connect(uri, timeout, retry)` - L45

## CLASS INDEX
- `models/user.py:UserManager` extends BaseManager - 12 methods
- `api/endpoints.py:APIRouter` - 8 methods
```

## Benefits for LLM Agents

- **Efficient navigation**: Quickly locate relevant files and functions
- **Relationship understanding**: Grasp how components relate through imports
- **Token economy**: Get more codebase understanding with fewer tokens
- **Structural awareness**: Understand the hierarchical organization
