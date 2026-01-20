"""Diff utilities for comparing resume variants."""

from pathlib import Path
import json


def generate_diff(variant1_path: Path, variant2_path: Path) -> str:
    """
    Generate diff between two resume variants.
    
    Supports both directory paths (containing resume.md) and direct file paths.
    
    Args:
        variant1_path: Path to first variant (directory or file)
        variant2_path: Path to second variant (directory or file)
        
    Returns:
        Formatted diff text showing differences
    """
    # Resolve paths - handle both directories and files
    resume1_path = _resolve_resume_path(variant1_path)
    resume2_path = _resolve_resume_path(variant2_path)
    
    if not resume1_path.exists():
        raise FileNotFoundError(f"Resume file not found: {resume1_path}")
    if not resume2_path.exists():
        raise FileNotFoundError(f"Resume file not found: {resume2_path}")
    
    # Read resume content
    resume1_content = resume1_path.read_text(encoding="utf-8")
    resume2_content = resume2_path.read_text(encoding="utf-8")
    
    # Parse resumes into sections
    sections1 = _parse_resume_sections(resume1_content)
    sections2 = _parse_resume_sections(resume2_content)
    
    # Build diff report
    diff_lines = []
    diff_lines.append(f"DIFFERENCES: {variant1_path.name} vs {variant2_path.name}")
    diff_lines.append("─" * 70)
    diff_lines.append("")
    
    # Compare sections
    section_names1 = {s["name"] for s in sections1}
    section_names2 = {s["name"] for s in sections2}
    
    # Added sections
    added_sections = section_names1 - section_names2
    if added_sections:
        diff_lines.append("ADDED SECTIONS:")
        for section_name in sorted(added_sections):
            diff_lines.append(f"+ {section_name}")
        diff_lines.append("")
    
    # Removed sections
    removed_sections = section_names2 - section_names1
    if removed_sections:
        diff_lines.append("REMOVED SECTIONS:")
        for section_name in sorted(removed_sections):
            diff_lines.append(f"- {section_name}")
        diff_lines.append("")
    
    # Compare keywords/phrases
    keywords1 = _extract_keywords(resume1_content)
    keywords2 = _extract_keywords(resume2_content)
    
    added_keywords = keywords1 - keywords2
    removed_keywords = keywords2 - keywords1
    
    if added_keywords:
        diff_lines.append("KEYWORDS ADDED:")
        for keyword in sorted(added_keywords)[:20]:  # Limit to top 20
            count = _count_occurrences(resume1_content, keyword)
            diff_lines.append(f"+ {keyword} (mentioned {count}x)")
        diff_lines.append("")
    
    if removed_keywords:
        diff_lines.append("KEYWORDS REMOVED:")
        for keyword in sorted(removed_keywords)[:20]:  # Limit to top 20
            diff_lines.append(f"- {keyword}")
        diff_lines.append("")
    
    # Compare evidence cards (if available)
    evidence1 = _load_evidence_cards(variant1_path)
    evidence2 = _load_evidence_cards(variant2_path)
    
    if evidence1 or evidence2:
        added_evidence = set(evidence1) - set(evidence2)
        removed_evidence = set(evidence2) - set(evidence1)
        
        if added_evidence or removed_evidence:
            diff_lines.append("EVIDENCE CARDS:")
            if added_evidence:
                diff_lines.append("  Added:")
                for card_id in sorted(added_evidence):
                    diff_lines.append(f"  • {card_id}")
            if removed_evidence:
                diff_lines.append("  Removed:")
                for card_id in sorted(removed_evidence):
                    diff_lines.append(f"  • {card_id}")
            diff_lines.append("")
    
    # Section order comparison
    order1 = [s["name"] for s in sections1]
    order2 = [s["name"] for s in sections2 if s["name"] in section_names1]
    
    if order1 != order2 and len(order1) == len(order2):
        diff_lines.append("SECTIONS REORDERED:")
        diff_lines.append(f"  Original order: {' → '.join(order2)}")
        diff_lines.append(f"  New order: {' → '.join(order1)}")
        diff_lines.append("")
    
    return "\n".join(diff_lines)


def _resolve_resume_path(path: Path) -> Path:
    """
    Resolve path to resume.md file.
    
    If path is a directory, look for resume.md inside it.
    If path is a file, return it directly.
    
    Args:
        path: Directory or file path
        
    Returns:
        Path to resume.md file
    """
    if path.is_dir():
        resume_file = path / "resume.md"
        if resume_file.exists():
            return resume_file
        # Try other common names
        for name in ["resume.txt", "resume"]:
            alt_file = path / name
            if alt_file.exists():
                return alt_file
        raise FileNotFoundError(f"No resume file found in directory: {path}")
    return path


def _parse_resume_sections(content: str) -> list[dict[str, str]]:
    """
    Parse resume markdown into sections.
    
    Args:
        content: Resume markdown content
        
    Returns:
        List of sections with name and content
    """
    sections = []
    current_section = None
    current_content = []
    
    for line in content.split("\n"):
        line_stripped = line.strip()
        
        # Check for markdown heading
        if line_stripped.startswith("#"):
            # Save previous section
            if current_section:
                sections.append({
                    "name": current_section,
                    "content": "\n".join(current_content)
                })
            
            # Start new section
            level = len(line) - len(line.lstrip("#"))
            current_section = line_stripped.lstrip("#").strip()
            current_content = []
        elif current_section:
            current_content.append(line)
    
    # Save last section
    if current_section:
        sections.append({
            "name": current_section,
            "content": "\n".join(current_content)
        })
    
    return sections


def _extract_keywords(content: str) -> set[str]:
    """
    Extract significant keywords/phrases from resume content.
    
    Args:
        content: Resume content
        
    Returns:
        Set of significant keywords (phrases with 2+ words, technical terms)
    """
    import re
    
    # Extract technical terms, metrics, and multi-word phrases
    keywords = set()
    
    # Technical terms (single words that are capitalized or common tech terms)
    tech_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
    tech_matches = re.findall(tech_pattern, content)
    keywords.update(m.lower() for m in tech_matches if len(m.split()) >= 2)
    
    # Metrics and numbers
    metric_pattern = r'\d+[%+\-KMB]?\s+\w+'
    metric_matches = re.findall(metric_pattern, content, re.IGNORECASE)
    keywords.update(m.lower() for m in metric_matches)
    
    # Common technical phrases (2-3 words)
    phrases = re.findall(r'\b\w+\s+\w+(?:\s+\w+)?\b', content.lower())
    # Filter out common stop words and keep meaningful phrases
    stop_words = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'was', 'were'}
    meaningful = [p for p in phrases if not all(w in stop_words for w in p.split())]
    keywords.update(meaningful)
    
    return keywords


def _count_occurrences(content: str, phrase: str) -> int:
    """Count occurrences of phrase in content (case-insensitive)."""
    return content.lower().count(phrase.lower())


def _load_evidence_cards(path: Path) -> list[str]:
    """
    Load evidence card IDs from evidence_used.json if available.
    
    Args:
        path: Directory path containing evidence_used.json
        
    Returns:
        List of evidence card IDs
    """
    if path.is_dir():
        evidence_file = path / "evidence_used.json"
        if evidence_file.exists():
            try:
                with open(evidence_file) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except (json.JSONDecodeError, IOError):
                pass
    return []
