
import fitz  # PyMuPDF
import os

def extract_images(pdf_path, output_dir):
    doc = fitz.open(pdf_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Opened {pdf_path}, pages: {len(doc)}")
    
    count = 0
    for i in range(len(doc)):
        page = doc[i]
        image_list = page.get_images(full=True)
        
        # print(f"Page {i+1}: {len(image_list)} images")
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Filter small images (icons, etc.)
            if len(image_bytes) < 10000: 
                continue
                
            image_filename = f"wang_extracted_p{i+1}_{img_index}.{image_ext}"
            image_path = os.path.join(output_dir, image_filename)
            
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            
            print(f"Saved {image_path}")
            count += 1
            
    print(f"Total images extracted: {count}")

if __name__ == "__main__":
    pdf_path = "/home/peirm/ai模拟平台/论文/库存管理的比较/2505.18597v1.pdf"
    output_dir = "/home/peirm/ai模拟平台/论文/experiment_results_v2/extracted_from_pdf"
    extract_images(pdf_path, output_dir)
