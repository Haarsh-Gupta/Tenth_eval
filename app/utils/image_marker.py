import os
from PIL import Image, ImageDraw, ImageFont, ImageOps
from typing import List, Dict, Any, Optional, Tuple

def create_virtual_marked_sheet(text: str, annotations: List[Dict[str, Any]], marks_awarded: int, total_marks: int, output_path: str) -> str:
    """
    Creates a 'virtual' answer sheet (white background with text) and draws marks on it.
    This is used when no image is uploaded but text evaluation is requested.
    """
    # Create a blank white image (A4-like aspect ratio)
    width, height = 800, 1100
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Try to load font
    try:
        font = ImageFont.truetype("arial.ttf", 20)
        title_font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        
    # Draw Title and Marks
    draw.text((50, 50), "AI Evaluation Sheet", fill=(0, 0, 0), font=title_font)
    draw.text((width - 250, 50), f"Marks: {marks_awarded}/{total_marks}", fill=(255, 0, 0), font=title_font)
    draw.line([50, 100, width-50, 100], fill=(200, 200, 200), width=2)
    
    # Wrap and draw the student's answer text
    import textwrap
    wrapped_text = textwrap.fill(text, width=70)
    draw.text((50, 150), wrapped_text, fill=(50, 50, 50), font=font)
    
    img.save(output_path)
    return output_path

def draw_marks_on_image(image_path: str, annotations: List[Dict[str, Any]], marks_awarded: int, total_marks: int, output_path: Optional[str] = None) -> Optional[str]:
    """
    Draws yellow highlights on identified errors on the student's answer sheet.
    Suggestions are shown in the feedback JSON, not on the image itself.
    """
    if not os.path.exists(image_path):
        return None
        
    # Use ImageOps.exif_transpose to handle orientation correctly
    try:
        img_orig = Image.open(image_path)
        img = ImageOps.exif_transpose(img_orig).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        return None
        
    width, height = img.size
    overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # 1. Draw Annotations (ONLY HIGHLIGHTS, NO SUGGESTIONS ON IMAGE)
    for i, ann in enumerate(annotations):
        coords = ann.get("coordinates")
        if not coords:
            continue
            
        issue_type = ann.get("issue_type", "content_error")
            
        # Handle dict BoundingBox or fallback to list
        if isinstance(coords, dict):
            ymin = coords.get("ymin", 0)
            xmin = coords.get("xmin", 0)
            ymax = coords.get("ymax", 0)
            xmax = coords.get("xmax", 0)
        elif isinstance(coords, list) and len(coords) == 4:
            ymin, xmin, ymax, xmax = coords
        else:
            continue
            
        # Scale coordinates from 0-1000 normalized to pixel coordinates
        top = (ymin * height) / 1000
        left = (xmin * width) / 1000
        bottom = (ymax * height) / 1000
        right = (xmax * width) / 1000
        
        # SMART PADDING: Gemini is often slightly off on small handwritten words.
        # Add a ~20% safety margin to spelling boxes to comfortably enclose the word.
        if issue_type == "spelling":
            pad_y = (bottom - top) * 0.25
            pad_x = (right - left) * 0.25
            top = max(0, top - pad_y)
            bottom = min(height, bottom + pad_y)
            left = max(0, left - pad_x)
            right = min(width, right + pad_x)
        
        # Consistent Yellow Highlight for everything as per user request
        fill_color = (255, 255, 0, 80)    # Yellow highlight (semi-transparent)
        border_color = (180, 180, 0, 150) # Darker yellow border/outline
        
        # Draw highlight rectangle
        draw_overlay.rectangle([left, top, right, bottom], fill=fill_color, outline=border_color, width=3)

    # Combine overlay with original image
    combined = Image.alpha_composite(img, overlay)
    img = combined.convert("RGB")
    draw = ImageDraw.Draw(img)

    # 2. Draw Final Marks (Top Right) - Standard large style
    mark_text = f"Marks: {marks_awarded}/{total_marks}"
    
    try:
        font_size = max(40, int(height/15))
        for font_name in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
            try:
                large_font = ImageFont.truetype(font_name, font_size)
                break
            except: continue
        else:
            large_font = ImageFont.load_default()
    except:
        large_font = ImageFont.load_default()
        
    try:
        bbox = draw.textbbox((0,0), mark_text, font=large_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except:
        tw, th = 300, 60
        
    m_x, m_y = width - tw - 60, 60
    
    # Backdrop for clarity
    draw.rectangle([m_x - 15, m_y - 15, m_x + tw + 15, m_y + th + 15], fill=(255, 255, 255), outline=(255, 0, 0), width=4)
    draw.text((m_x, m_y), mark_text, fill=(255, 0, 0), font=large_font, stroke_width=2, stroke_fill=(255,255,255))
    
    # 3. Save
    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_marked{ext}"
        
    img.save(output_path)
    return output_path
