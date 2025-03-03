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

def test_visual_parameter():
    """Test that visual parameter is correctly handled."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        (tempdir_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        # Mock the LLM model to return a diagram
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = """<overview>Test overview</overview>
<diagram>
digraph G {
  rankdir=LR;
  node [shape=box, style=filled, color=lightblue];
  A -> B;
}
</diagram>"""
        
        # Test with visual parameter
        with mock.patch('llm.get_model', return_value=mock_model):
            cartographer = CodebaseCartographer(
                directory=tempdir,
                max_files=3,
                visual=True
            )
            
            # Run analysis
            cartographer.analyze_codebase()
            
            # Verify diagram code was extracted
            assert cartographer.diagram_code is not None
            assert "digraph G" in cartographer.diagram_code
            
            # Check that the model was called with visual instructions
            system_arg = mock_model.prompt.call_args[1]["system"]
            prompt_arg = mock_model.prompt.call_args[0][0]
            assert "visual diagram" in system_arg.lower()
            assert "<diagram>" in prompt_arg

def test_output_directory():
    """Test that --output can specify a directory."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        (tempdir_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        # Create output directory
        output_dir = tempdir_path / "output"
        output_dir.mkdir()
        
        # Mock the LLM model
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = "<overview>Test overview</overview>"
        
        # Test with output directory
        with mock.patch('llm.get_model', return_value=mock_model):
            cartographer = CodebaseCartographer(
                directory=tempdir,
                max_files=3,
                output=str(output_dir)
            )
            
            # Verify directory is detected correctly
            assert cartographer.output_is_dir == True
            
            # Run analysis and save output
            analysis = cartographer.analyze_codebase()
            cartographer.save_output(analysis)
            
            # Check that analysis.md exists in the output directory
            analysis_file = output_dir / "analysis.md"
            assert analysis_file.exists()
            
            # Verify content was written
            content = analysis_file.read_text()
            assert "<overview>Test overview</overview>" in content

def test_visual_output_directory():
    """Test that visual diagrams are saved in the output directory."""
    with tempfile.TemporaryDirectory() as tempdir:
        tempdir_path = Path(tempdir)
        (tempdir_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        # Create output directory
        output_dir = tempdir_path / "output"
        output_dir.mkdir()
        
        # Mock the LLM model to return a diagram
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = """<overview>Test overview</overview>
<diagram>
digraph G {
  rankdir=LR;
  node [shape=box];
  A -> B;
}
</diagram>"""
        
        # Mock subprocess.run for the diagram generation
        with mock.patch('llm.get_model', return_value=mock_model):
            with mock.patch('subprocess.run') as mock_run:
                # Configure mock to return success
                mock_run.return_value.returncode = 0
                
                # Mock shutil.which to pretend graphviz is installed
                with mock.patch('shutil.which', return_value='/usr/bin/dot'):
                    cartographer = CodebaseCartographer(
                        directory=tempdir,
                        max_files=3,
                        output=str(output_dir),
                        visual=True
                    )
                    
                    # Run analysis
                    cartographer.analyze_codebase()
                    cartographer.generate_diagram()
                    
                    # Check that subprocess.run was called with the correct arguments
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args[0] == "dot"  # Command
                    assert args[1] == "-Tpng"  # Output format
                    assert args[3] == "-o"  # Output flag
                    assert str(output_dir / "diagram.png") in args[4]  # Output path
                    
def test_filter_extension_prioritization():
    """Test that filter_extension prioritizes specified extensions."""
    with tempfile.TemporaryDirectory() as tempdir:
        tempdir_path = Path(tempdir)
        
        # Create different file types
        (tempdir_path / "file1.py").write_text("# Python file")
        (tempdir_path / "file2.py").write_text("# Another Python file")
        (tempdir_path / "file1.js").write_text("// JavaScript file")
        (tempdir_path / "file2.js").write_text("// Another JavaScript file")
        
        # Mock the LLM model
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = "<overview>Test overview</overview>"
        
        # Test with filter-extension focusing on Python files
        with mock.patch('llm.get_model', return_value=mock_model):
            cartographer = CodebaseCartographer(
                directory=tempdir,
                max_files=2,  # Only allow 2 files to be analyzed
                filter_extensions=[".py"]  # Only Python files
            )
            
            # Run scan
            cartographer.scan_directory()
            
            # Get all analyzed files
            all_files = list(cartographer.collected_data["file_samples"].keys())
            
            # All analyzed files should be Python files
            assert all(f.endswith(".py") for f in all_files)
            assert len(all_files) == 2
