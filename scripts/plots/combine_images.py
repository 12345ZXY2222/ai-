
from PIL import Image
import os

def combine_images():
    base_dir = "/home/peirm/ai模拟平台/论文/experiment_results_v2/extracted_from_pdf"
    output_path = "/home/peirm/ai模拟平台/论文/experiment_results_v2/wang_original_fig6.png"
    
    # Assuming p7_0, p7_1, p7_2, p7_3 correspond to a, b, c, d
    # Order in PDF extraction is usually Z-order or content stream order. 
    # Often Top-Left -> Top-Right -> Bottom-Left -> Bottom-Right for figures.
    
    img_names = [f"wang_extracted_p7_{i}.png" for i in range(4)]
    images = []
    
    for name in img_names:
        path = os.path.join(base_dir, name)
        if os.path.exists(path):
            images.append(Image.open(path))
        else:
            print(f"Missing {name}")
            return

    if not images:
        print("No images found")
        return

    # Assume 2x2 grid
    w, h = images[0].size
    # Ensure all are same size (resize to first one)
    images = [img.resize((w, h)) for img in images]
    
    # Create canvas
    grid_w = w * 2
    grid_h = h * 2
    combined = Image.new("RGB", (grid_w, grid_h), "white")
    
    combined.paste(images[0], (0, 0))      # TL
    combined.paste(images[1], (w, 0))      # TR
    combined.paste(images[2], (0, h))      # BL
    combined.paste(images[3], (w, h))      # BR
    
    combined.save(output_path)
    print(f"Combined image saved to {output_path}")

if __name__ == "__main__":
    combine_images()
