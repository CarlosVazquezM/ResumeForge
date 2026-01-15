"""Parser for Job Descriptions."""

from pathlib import Path


def parse_jd(jd_path: Path) -> str:
    """
    Parse job description text from file.
    
    Args:
        jd_path: Path to job description file
        
    Returns:
        Job description text
    """
    with open(jd_path, encoding="utf-8") as f:
        return f.read()
