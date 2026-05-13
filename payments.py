"""Telebirr payment helpers."""

from __future__ import annotations

import re
import io
from PIL import Image

# --- Telebirr Security & Validation ---
def validate_telebirr_tx_id(tx_id: str) -> bool:
    """Strictly validates Telebirr transaction ID format to prevent injections."""
    # Assuming Telebirr IDs are strictly alphanumeric, no spaces or special chars
    if not tx_id or not isinstance(tx_id, str):
        return False
    if len(tx_id) < 8 or len(tx_id) > 20: 
        return False
    if not re.match(r"^[A-Z0-9]+$", tx_id.upper()):
        return False
    return True

def is_valid_image(file_bytes: bytes) -> bool:
    """Zero-trust file upload verification: checks the magic bytes/header of the image, preventing malicious executable disguise."""
    try:
        # Load the bytes into Pillow
        image = Image.open(io.BytesIO(file_bytes))
        
        # Must be a standard web image formats
        if image.format not in ['JPEG', 'PNG', 'WEBP']:
            return False
            
        # Optional: verify structural integrity
        image.verify()
        return True
    except Exception:
        return False
