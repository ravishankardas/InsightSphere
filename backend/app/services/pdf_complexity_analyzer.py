"""
Smart PDF Complexity Analyzer - ROBUST VERSION
Automatically detects PDF layout complexity with improved error handling
"""
import PyPDF2 # type: ignore
from io import BytesIO
from typing import Dict, Tuple
import re


def analyze_pdf_complexity(pdf_bytes: bytes) -> Dict:
    """
    Analyze PDF to determine layout complexity
    
    Returns dict with:
    - complexity_score: 0-100 (higher = more complex)
    - recommended_mode: "text", "fast", or "full"
    - has_images: boolean
    - has_tables: boolean estimate
    - page_count: int
    - text_density: float (chars per page)
    """
    
    try:
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        page_count = len(pdf_reader.pages)
        total_chars = 0
        has_images_likely = False
        has_tables_likely = False
        
        # Sample first 3 pages for analysis (or all if < 3)
        sample_size = min(3, page_count)
        
        for i in range(sample_size):
            try:
                page = pdf_reader.pages[i]
                
                # Extract text
                text = page.extract_text() or ""
                total_chars += len(text)
                
                # Check for images - ROBUST VERSION
                if not has_images_likely:
                    has_images_likely = _check_for_images(page)
                
                # Heuristic: Check for table-like patterns
                if not has_tables_likely:
                    has_tables_likely = _check_for_tables(text)
                    
            except Exception as e:
                print(f"Warning: Could not analyze page {i+1}: {e}")
                continue
        
        # Calculate metrics
        text_density = total_chars / sample_size if sample_size > 0 else 0
        
        # Calculate complexity score (0-100)
        complexity_score = _calculate_complexity_score(
            has_images_likely,
            has_tables_likely,
            text_density,
            page_count
        )
        
        # Recommend mode based on complexity
        if complexity_score < 30:
            recommended_mode = "text"  # Simple text document
        elif complexity_score < 60:
            recommended_mode = "fast"  # Moderate complexity
        else:
            recommended_mode = "full"  # Complex document
        
        return {
            "complexity_score": complexity_score,
            "recommended_mode": recommended_mode,
            "has_images": has_images_likely,
            "has_tables": has_tables_likely,
            "page_count": page_count,
            "text_density": text_density,
            "analysis": _get_analysis_description(complexity_score, has_images_likely, has_tables_likely)
        }
        
    except Exception as e:
        print(f"Error analyzing PDF: {e}")
        # Return safe defaults if analysis fails
        return {
            "complexity_score": 30,
            "recommended_mode": "fast",
            "has_images": False,
            "has_tables": False,
            "page_count": 1,
            "text_density": 1000,
            "analysis": "Unable to analyze - using safe defaults"
        }


def _check_for_images(page) -> bool:
    """
    Robustly check if a page has images
    Handles PyPDF2's IndirectObject quirks
    """
    try:
        resources = page.get('/Resources')
        if not resources:
            return False
        
        # Handle indirect objects
        if hasattr(resources, 'get_object'):
            resources = resources.get_object()
        
        if not resources or '/XObject' not in resources:
            return False
        
        xobjects = resources['/XObject']
        
        # Handle indirect objects
        if hasattr(xobjects, 'get_object'):
            xobjects = xobjects.get_object()
        
        # Check if it's a dict-like object
        if not hasattr(xobjects, 'keys'):
            return False
        
        # Iterate through XObjects
        for obj_key in xobjects.keys():
            try:
                xobj = xobjects[obj_key]
                
                # Handle indirect objects
                if hasattr(xobj, 'get_object'):
                    xobj = xobj.get_object()
                
                # Check if it's an image
                subtype = xobj.get('/Subtype') if hasattr(xobj, 'get') else None
                if subtype == '/Image':
                    return True
                    
            except Exception:
                # Skip problematic objects
                continue
        
        return False
        
    except Exception:
        # If detection fails, assume no images
        return False


def _check_for_tables(text: str) -> bool:
    """
    Heuristically check if text contains table-like patterns
    """
    if not text:
        return False
    
    try:
        lines = text.split('\n')
        if len(lines) < 3:
            return False
        
        # Count lines with numbers
        numeric_lines = sum(1 for line in lines if re.search(r'\d+', line))
        
        # If >40% of lines contain numbers, likely has tables
        if numeric_lines / len(lines) > 0.4:
            return True
        
        # Check for tab characters or multiple spaces (common in tables)
        tab_lines = sum(1 for line in lines if '\t' in line or '  ' in line)
        if tab_lines / len(lines) > 0.3:
            return True
        
        return False
        
    except Exception:
        return False


def _calculate_complexity_score(has_images: bool, has_tables: bool, 
                                text_density: float, page_count: int) -> int:
    """Calculate complexity score from detected features"""
    
    complexity_score = 0
    
    # Factor 1: Images (big complexity increase)
    if has_images:
        complexity_score += 40
    
    # Factor 2: Tables (moderate complexity increase)
    if has_tables:
        complexity_score += 30
    
    # Factor 3: Low text density suggests complex layout (images, diagrams)
    if text_density < 1000:  # Very sparse text
        complexity_score += 20
    elif text_density < 2000:  # Moderate text
        complexity_score += 10
    
    # Factor 4: Large documents need more processing
    if page_count > 50:
        complexity_score += 10
    
    # Cap at 100
    return min(100, complexity_score)


def _get_analysis_description(score: int, has_images: bool, has_tables: bool) -> str:
    """Generate human-readable analysis description"""
    parts = []
    
    if score < 30:
        parts.append("Simple text document")
    elif score < 60:
        parts.append("Moderately complex layout")
    else:
        parts.append("Complex document with rich content")
    
    if has_images:
        parts.append("contains images")
    if has_tables:
        parts.append("contains tables")
    
    if not has_images and not has_tables:
        parts.append("text-only")
    
    return " - ".join(parts)


def should_use_multimodal(pdf_bytes: bytes, threshold: int = 30) -> Tuple[bool, str]:
    """
    Quick decision: should we use multimodal processing?
    
    Args:
        pdf_bytes: PDF content
        threshold: Complexity threshold (default 30)
    
    Returns:
        (use_multimodal: bool, reason: str)
    """
    analysis = analyze_pdf_complexity(pdf_bytes)
    
    if analysis["complexity_score"] >= threshold:
        return True, analysis["analysis"]
    else:
        return False, analysis["analysis"]


# Quick presets for different use cases
COMPLEXITY_PRESETS = {
    "speed_first": {
        "threshold": 50,
        "description": "Prioritize speed - use text mode for most documents"
    },
    "balanced": {
        "threshold": 30,
        "description": "Balance speed and quality"
    },
    "quality_first": {
        "threshold": 10,
        "description": "Prioritize quality - use multimodal when possible"
    }
}


def get_recommended_settings(pdf_bytes: bytes, preset: str = "balanced") -> Dict:
    """
    Get recommended processing settings based on PDF complexity
    
    Args:
        pdf_bytes: PDF content
        preset: "speed_first", "balanced", or "quality_first"
    
    Returns:
        Dict with recommended mode and settings
    """
    analysis = analyze_pdf_complexity(pdf_bytes)
    preset_config = COMPLEXITY_PRESETS.get(preset, COMPLEXITY_PRESETS["balanced"])
    
    # Adjust recommendation based on preset
    score = analysis["complexity_score"]
    threshold = preset_config["threshold"]
    
    if score < threshold:
        mode = "text"
        max_images = 0
    elif score < threshold + 30:
        mode = "fast"
        max_images = 2
    else:
        mode = "full"
        max_images = 5
    
    return {
        "mode": mode,
        "max_images": max_images,
        "complexity_score": score,
        "analysis": analysis["analysis"],
        "estimated_time": _estimate_processing_time(analysis["page_count"], mode, max_images)
    }


def _estimate_processing_time(page_count: int, mode: str, max_images: int) -> str:
    """Estimate processing time based on settings"""
    if mode == "text":
        seconds = page_count * 0.1  # ~0.1s per page
    elif mode == "fast":
        seconds = page_count * 1.2 + (max_images * 10)  # ~1.2s per page + 10s per image
    else:  # full
        seconds = page_count * 6 + (max_images * 15)  # ~6s per page + 15s per image
    
    if seconds < 60:
        return f"~{int(seconds)}s"
    else:
        return f"~{int(seconds / 60)}m {int(seconds % 60)}s"