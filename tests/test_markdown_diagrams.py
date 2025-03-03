import pytest
import tempfile
import os
import sys
import re
from pathlib import Path
from unittest import mock

# Import directly from the module file
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
from llm_cartographer import CodebaseCartographer

def test_mermaid_diagram_generation():
    """Test Mermaid diagram generation."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        (tempdir_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        # Create output directory
        output_dir = tempdir_path / "output"
        output_dir.mkdir()
        
        # Mock the LLM model to return a diagram
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = """<overview>Test overview</overview>
<diagram>
graph TD
    A[Module A] --> B[Module B]
    A --> C[Module C]
    B --> D[Module D]
    C --> D
</diagram>"""
        
        # Test with Mermaid diagram format
        with mock.patch('llm.get_model', return_value=mock_model):
            cartographer = CodebaseCartographer(
                directory=tempdir,
                max_files=3,
                output=str(output_dir),
                visual=True,
                diagram_format="mermaid"
            )
            
            # Run analysis
            cartographer.analyze_codebase()
            
            # Verify diagram code was extracted
            assert cartographer.diagram_code is not None
            assert "graph TD" in cartographer.diagram_code
            
            # Generate the diagram
            diagram_path = cartographer.generate_diagram()
            
            # Check that the diagram was saved as a markdown file
            assert diagram_path is not None
            assert diagram_path.endswith(".md")
            
            # Verify the markdown file includes mermaid syntax
            with open(diagram_path, 'r') as f:
                content = f.read()
                assert "```mermaid" in content
                assert cartographer.diagram_code in content

def test_plantuml_diagram_generation():
    """Test PlantUML diagram generation."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        (tempdir_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        # Create output directory
        output_dir = tempdir_path / "output"
        output_dir.mkdir()
        
        # Mock the LLM model to return a diagram
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = """<overview>Test overview</overview>
<diagram>
@startuml
package "Core Components" {
  [Component A] as A
  [Component B] as B
}
A --> B
@enduml
</diagram>"""
        
        # Test with PlantUML diagram format
        with mock.patch('llm.get_model', return_value=mock_model):
            cartographer = CodebaseCartographer(
                directory=tempdir,
                max_files=3,
                output=str(output_dir),
                visual=True,
                diagram_format="plantuml"
            )
            
            # Run analysis
            cartographer.analyze_codebase()
            
            # Verify diagram code was extracted
            assert cartographer.diagram_code is not None
            assert "@startuml" in cartographer.diagram_code
            
            # Generate the diagram
            diagram_path = cartographer.generate_diagram()
            
            # Check that the diagram was saved as a markdown file
            assert diagram_path is not None
            assert diagram_path.endswith(".md")
            
            # Verify the markdown file includes plantuml syntax
            with open(diagram_path, 'r') as f:
                content = f.read()
                assert "```plantuml" in content
                assert cartographer.diagram_code in content

def test_markdown_diagram_embedding():
    """Test that markdown diagrams are embedded in the analysis output."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        (tempdir_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        # Create output directory
        output_dir = tempdir_path / "output"
        output_dir.mkdir()
        
        # Mock the LLM model to return a diagram
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = """<overview>Test overview</overview>
<workflows>Test workflows</workflows>
<diagram>
graph TD
    A[Module A] --> B[Module B]
</diagram>"""
        
        # Test with Mermaid diagram format
        with mock.patch('llm.get_model', return_value=mock_model):
            cartographer = CodebaseCartographer(
                directory=tempdir,
                max_files=3,
                output=str(output_dir),
                visual=True,
                diagram_format="mermaid"
            )
            
            # Run analysis
            analysis = cartographer.analyze_codebase()
            
            # Save the output
            cartographer.save_output(analysis)
            
            # Check that the analysis file contains the embedded diagram
            analysis_file = output_dir / "analysis.md"
            with open(analysis_file, 'r') as f:
                content = f.read()
                assert "```mermaid" in content
                assert cartographer.diagram_code in content

def test_invalid_diagram_format():
    """Test handling of invalid diagram format."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Test with invalid diagram format
        with pytest.raises(ValueError, match="Diagram format 'invalid' not recognized"):
            CodebaseCartographer(
                directory=tempdir,
                visual=True,
                diagram_format="invalid"
            )
