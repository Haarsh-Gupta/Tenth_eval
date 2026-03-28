import os
from PIL import Image, ImageDraw, ImageFont
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
    
    # Note: For virtual sheets, coordinates would need to be calculated based on text position.
    # However, since the LLM gives coordinates for the *image*, this is tricky.
    # For now, we'll just show the text and the feedback.
    # Alternatively, we just save this as a 'sheet' and let draw_marks interpret it if we had pixel coords.
    
    img.save(output_path)
    return output_path

def draw_marks_on_image(image_path: str, annotations: List[Dict[str, Any]], marks_awarded: int, total_marks: int, output_path: Optional[str] = None) -> Optional[str]:
    """
    Draws circles, highlights, and suggestion boxes on the student's answer sheet.
    """
    if not os.path.exists(image_path):
        return None
        
    img = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    width, height = img.size
    
    # Try to load font - increase size for readability
    try:
        font_size = max(20, int(height/50))
        # Try a few common fonts
        for font_name in ["arial.ttf", "DejaVuSans.ttf", "Verdana.ttf"]:
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except:
                continue
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
        
    # 1. Draw Annotations
    for i, ann in enumerate(annotations):
        coords = ann.get("coordinates")
        if not coords or len(coords) != 4:
            continue
            
        style = ann.get("marking_style", "circle")
        issue_type = ann.get("issue_type", "content_error")
        suggestion = ann.get("suggestion")
        
        # Scale normalized coordinates (0-1000) to pixel coordinates
        ymin, xmin, ymax, xmax = coords
        left = xmin * width / 1000
        top = ymin * height / 1000
        right = xmax * width / 1000
        bottom = ymax * height / 1000
        
        # Choose color based on issue type
        if issue_type == "wrong_sentence":
            color = (255, 0, 0, 180) # Strong Red
            fill_color = (255, 0, 0, 60)
            style = "highlight"
        elif issue_type == "spelling":
            color = (255, 50, 50, 255) # Light Red
            fill_color = (255, 0, 0, 0)
            style = "circle"
        elif issue_type == "grammar":
            color = (255, 165, 0, 255) # Orange
            fill_color = (255, 165, 0, 30)
            style = "underline"
        else:
            color = (255, 0, 0, 255) # Default Red
            fill_color = (255, 0, 0, 20)

        thickness = max(3, int(width / 500))
        
        if style == "circle":
            draw_overlay.ellipse([left, top, right, bottom], outline=color, width=thickness)
        elif style == "cross":
            draw_overlay.line([left, top, right, bottom], fill=color, width=thickness)
            draw_overlay.line([left, bottom, right, top], fill=color, width=thickness)
        elif style == "underline":
            draw_overlay.line([left, bottom, right, bottom], fill=color, width=thickness)
        elif style == "tick":
            mid_x = (left + right) / 2
            draw_overlay.line([left, (top+bottom)/2, mid_x, bottom], fill=(0, 200, 0, 255), width=thickness)
            draw_overlay.line([mid_x, bottom, right, top], fill=(0, 200, 0, 255), width=thickness)
        elif style == "highlight":
            draw_overlay.rectangle([left, top, right, bottom], fill=fill_color, outline=color, width=2)
        
        # Suggestions with "teacher's note" style
        if suggestion:
            text_x = right + 20
            text_y = top - 10
            
            # Position suggestion note carefully
            if text_x > width - 200: 
                text_x = left - 220
                if text_x < 0: text_x = 10
            
            note_content = f"Teacher suggests: {suggestion}"
            # Word wrap the note if it's too long
            import textwrap
            wrapped_note = "\n".join(textwrap.wrap(note_content, width=25))
            
            # Draw line connecting note to the error
            draw_overlay.line([(left+right)/2, top, (text_x if text_x > right else text_x+200), text_y+10], 
                             fill=(255, 0, 0, 150), width=1)
            
            # Draw suggestion note with premium style
            text_bbox = draw_overlay.textbbox((text_x, text_y), wrapped_note, font=font)
            # Add padding to bbox
            padded_bbox = [text_bbox[0]-5, text_bbox[1]-5, text_bbox[2]+5, text_bbox[3]+5]
            draw_overlay.rectangle(padded_bbox, fill=(255, 255, 220, 240), outline=(255, 0, 0, 255), width=1)
            draw_overlay.text((text_x, text_y), wrapped_note, fill=(180, 0, 0, 255), font=font)

    # Combine overlay with original image
    combined = Image.alpha_composite(img, overlay)
    img = combined.convert("RGB")
    draw = ImageDraw.Draw(img)

    # 2. Draw Final Marks (Top Right)
    mark_text = f"Marks: {marks_awarded}/{total_marks}"
    draw.text((width - 300, 50), mark_text, fill=(255, 0, 0), font=font, stroke_width=1, stroke_fill=(255,255,255))
    
    # 3. Save
    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_marked{ext}"
        
    img.save(output_path)
    return output_path
