"""Helper functions for verifying pipeline outputs."""

from pathlib import Path
from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from resumeforge.schemas.blackboard import Blackboard


class OutputVerifier:
    """Verifies that all expected output files are created."""
    
    REQUIRED_OUTPUTS = [
        "evidence_used.json",
        "resume.md",
    ]
    
    CONDITIONAL_OUTPUTS = {
        "claim_index.json": lambda b: b.claim_index is not None and len(b.claim_index) > 0,
        "ats_report.json": lambda b: b.ats_report is not None,
        "audit_report.json": lambda b: b.audit_report is not None,
        "resume.docx": lambda b: b.resume_draft is not None,
        "diff_from_base.md": lambda b: (
            b.resume_draft is not None 
            and b.inputs.template_path 
            and Path(b.inputs.template_path).exists()
        ),
    }
    
    @classmethod
    def verify_outputs(cls, output_dir: Path, blackboard: "Blackboard") -> tuple[bool, list[str]]:
        """
        Verify all expected outputs exist.
        
        Args:
            output_dir: Path to output directory
            blackboard: Blackboard state to check conditions against
            
        Returns:
            (all_present, missing_files)
        """
        missing = []
        
        # Check required outputs
        for filename in cls.REQUIRED_OUTPUTS:
            if not (output_dir / filename).exists():
                missing.append(filename)
        
        # Check conditional outputs
        for filename, condition in cls.CONDITIONAL_OUTPUTS.items():
            if condition(blackboard) and not (output_dir / filename).exists():
                missing.append(filename)
        
        return len(missing) == 0, missing
    
    @classmethod
    def verify_json_structure(cls, file_path: Path, expected_keys: list[str]) -> tuple[bool, list[str]]:
        """
        Verify JSON file exists and has expected structure.
        
        Args:
            file_path: Path to JSON file
            expected_keys: List of keys that should be present
            
        Returns:
            (is_valid, missing_keys)
        """
        if not file_path.exists():
            return False, [f"File {file_path} does not exist"]
        
        try:
            with open(file_path) as f:
                data = json.load(f)
            
            # Handle both dict and list cases
            if isinstance(data, list) and len(data) > 0:
                data = data[0]  # Check first item for list case
            
            if not isinstance(data, dict):
                return False, ["JSON root is not an object"]
            
            missing_keys = [key for key in expected_keys if key not in data]
            return len(missing_keys) == 0, missing_keys
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {e}"]
    
    @classmethod
    def verify_docx_exists(cls, file_path: Path) -> bool:
        """
        Verify DOCX file exists and is valid.
        
        Args:
            file_path: Path to DOCX file
            
        Returns:
            True if file exists and appears valid
        """
        if not file_path.exists():
            return False
        
        # Basic check: file exists and has .docx extension
        # Could add more sophisticated validation (e.g., python-docx validation)
        return file_path.suffix == ".docx" and file_path.stat().st_size > 0
    
    @classmethod
    def find_output_dir(cls, base_path: Path) -> Path | None:
        """
        Find the timestamped output directory.
        
        Args:
            base_path: Base output directory path
            
        Returns:
            Path to output directory, or None if not found
        """
        if not base_path.exists():
            return None
        
        # Find most recent directory (by modification time)
        dirs = [d for d in base_path.iterdir() if d.is_dir()]
        if not dirs:
            return None
        
        # Sort by modification time, most recent first
        dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return dirs[0]
