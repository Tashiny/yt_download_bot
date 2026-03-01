"""
Utility helpers.
"""
from __future__ import annotations

import re


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize a string for use as filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip('. ')
    if len(name) > max_length:
        name = name[:max_length]
    return name or "video"


def format_file_size(size_bytes: int) -> str:
    """Format file size to human-readable string."""
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} ГБ"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} МБ"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} КБ"
    return f"{size_bytes} Б"
