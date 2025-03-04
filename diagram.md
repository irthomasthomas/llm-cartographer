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

## Viewing Instructions

This diagram uses [Mermaid](https://mermaid-js.github.io/mermaid/), which is supported by:

- GitHub markdown (directly viewable in GitHub repositories)
- VS Code with the Markdown Preview Mermaid Support extension
- Most modern Markdown editors
- Online at [Mermaid Live Editor](https://mermaid.live/)
