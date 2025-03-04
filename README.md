# llm-cartographer

A plugin for [Simon Willison's LLM tool](https://github.com/simonw/llm) that automatically maps and describes a codebase or project structure in a way which is token-efficient and ready to be consumed by an LLM.

## Installation

```bash
pip install llm-cartographer
```

Or directly from the repository:

```bash
pip install git+https://github.com/yourusername/llm-cartographer.git
```

## Usage

Basic usage:

```bash
llm cartographer /path/to/your/project
```

This will analyze the project directory and generate a comprehensive description of the codebase structure, which is then processed by an LLM to provide insights.

### Options

```
Options:
  -e, --exclude TEXT             Patterns to exclude (gitignore format)
  --max-files INTEGER            Maximum number of files to analyze (default: 100)
  --max-file-size INTEGER        Maximum file size in bytes (default: 102400)
  -o, --output PATH              Output file path or directory
  -m, --model TEXT               LLM model to use
  --follow-symlinks              Follow symbolic links
  --json                         Output as JSON
  -f, --filter-extension TEXT    Only include files with these extensions
  --cache-dir TEXT               Cache directory path
  --mode [overview|components|architecture|flows]
                                 Analysis mode (default: overview)
  --focus TEXT                   Focus analysis on a specific subdirectory
  --reasoning INTEGER RANGE      Reasoning depth (0-9, where 0=minimal and 9=maximum) (default: 5)
  --visual                       Generate visual diagram of codebase architecture
  --diagram-format [graphviz|mermaid|plantuml]
                                 Format for diagram generation (default: graphviz)
  --llm-nav                      Enable LLM-based codebase navigation
  --help                         Show this message and exit.
```

# Codebase Architecture Diagram

```mermaid
graph LR
    A[CLI] --> B[Core Module]
    B --> C[Directory Scanner]
    B --> D[Map Generator]
    D --Visual Diagram--> E[Visualization Module]
    B --> F[LLM Integration]
    B --> G[Output Formatter]
    G --> H[File Output]

    classDef module fill:#bbf,stroke:#333,stroke-width:1px;
    classDef cli fill:#f96,stroke:#333,stroke-width:1px;
    classDef output fill:#9f6,stroke:#333,stroke-width:1px;

    class A,G,H cli;
    class B,C,D,E,F module;
    class G,H output;
```

### Examples

Analyze current directory with default settings:
```bash
llm cartographer .
```

Analyze a specific project and save results:
```bash
llm cartographer /path/to/project --output analysis.md
```

Analyze only Python files:
```bash
llm cartographer . --filter-extension py
```

Use a specific LLM model:
```bash
llm cartographer . --model gpt-4o
```

Focus on a specific subdirectory:
```bash
llm cartographer . --focus src/core
```

Use component-focused analysis mode:
```bash
llm cartographer . --mode components
```

Increase reasoning depth for more detailed analysis:
```bash
llm cartographer . --reasoning 8
```

Generate a visual diagram of the codebase architecture:
```bash
llm cartographer . --visual
```

Generate a Mermaid diagram (Markdown-compatible):
```bash
llm cartographer . --visual --diagram-format mermaid
```

Generate a PlantUML diagram:
```bash
llm cartographer . --visual --diagram-format plantuml
```

Save output to a directory (creates analysis.md and diagram file):
```bash
llm cartographer . --visual --output ./results
```

## Features

- 🔍 **Comprehensive Analysis**: Scans directory structure, important files, language statistics
- 📊 **Token Efficiency**: Creates a compact representation optimized for LLM consumption
- 🧩 **Component Identification**: Identifies key components and their relationships
- 💡 **Insights**: Provides architectural patterns and code organization insights
- 📝 **Caching**: Caches results to avoid unnecessary re-processing
- 🎯 **Analysis Modes**: Different modes for varying analysis approaches (overview, components, architecture, flows)
- 🔎 **Subdirectory Focus**: Ability to analyze specific subdirectories
- 🧠 **Reasoning Depth**: Control over the level of detail in analysis explanations
- 📈 **Visual Diagrams**: Generate visual representations of codebase architecture using various formats
- 🎨 **Rich Formatting**: Enhanced output using rich library with improved readability
- 📁 **Output Directory**: Support for saving multiple output files to a specified directory
- 📊 **Markdown Diagrams**: Support for Mermaid and PlantUML diagrams that display directly in Markdown
- 🧭 **Codebase Navigation**: Navigate through the codebase using LLM for better understanding and insights

## Analysis Modes

- **overview**: General analysis of the entire codebase structure and functionality
- **components**: Focus on identifying and explaining the main components and modules
- **architecture**: Analysis of architectural patterns and system organization
- **flows**: Identification of key data and control flows through the system

## Diagram Formats

The `--visual` flag generates architecture diagrams in the format specified by `--diagram-format`:

- **graphviz**: Standard DOT format diagrams (requires Graphviz installation for PNG rendering)
- **mermaid**: Markdown-compatible diagrams that render in GitHub, VS Code, and other Markdown viewers
- **plantuml**: UML diagrams that can be rendered with PlantUML tools

### Mermaid Diagrams

When using the Mermaid format, the diagram is embedded directly in the Markdown output and will render automatically on platforms that support Mermaid syntax, such as GitHub, GitLab, and VS Code with the right extensions.

Example of a Mermaid diagram in Markdown:

````
```mermaid
graph TD
    A[Core Module] --> B[Utils]
    A --> C[Database]
    B --> D[External APIs]
    C --> D
```
````

### PlantUML Diagrams

PlantUML diagrams provide more advanced UML capabilities and are saved as Markdown files with PlantUML code blocks:

````
```plantuml
@startuml
package "Core" {
  [Component A] as A
  [Component B] as B
}
A --> B
@enduml
```
````

## How It Works

1. **Scanning**: The plugin scans the directory structure and collects information about files, directories, and languages.
2. **Mapping**: It creates a token-efficient representation of the codebase.
3. **Analysis**: The map is sent to an LLM for analysis of architecture, components, and workflows.
4. **Visualization**: If requested, a diagram of the codebase architecture is generated in the specified format.
5. **Output**: Results are formatted and returned, optionally saved to a file or directory.

## License

Apache License 2.0
