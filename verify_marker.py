import os
from PIL import Image
from app.utils.image_marker import draw_marks_on_image

def verify():
    # 1. Create a dummy test image
    img = Image.new("RGB", (1000, 1000), (200, 200, 200))
    img.save("test_input.png")
    
    # 2. Define some annotations
    annotations = [
        {
            "issue_type": "spelling",
            "coordinates": [100, 100, 150, 400], # [ymin, xmin, ymax, xmax]
            "suggestion": "history"
        },
        {
            "issue_type": "wrong_sentence",
            "coordinates": [300, 100, 450, 900],
            "suggestion": "The French Revolution started in 1789."
        }
    ]
    
    # 3. Draw marks
    output_path = draw_marks_on_image(
        image_path="test_input.png",
        annotations=annotations,
        marks_awarded=4,
        total_marks=5,
        output_path="test_output.png"
    )
    
    if output_path and os.path.exists(output_path):
        print(f"✅ Marking successful! Output saved to: {output_path}")
    else:
        print("❌ Marking failed.")

if __name__ == "__main__":
    verify()
