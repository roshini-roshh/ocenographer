import cv2
import numpy as np
from PIL import Image  # Standard library that handles Windows paths seamlessly
import os

# 1. Provide your folder and file path
image_path = r"C:\Users\roshn\OneDrive\Desktop\sih'26\data sets\1\photos\stake.png"

try:
    # Open the image using PIL first (this will not fail on the quote or backslashes)
    pil_img = Image.open(image_path)
    
    # Convert the PIL image to a format OpenCV can work with (BGR NumPy array)
    image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    print("🎯 Image opened successfully using the fallback loader!")
except Exception as e:
    print(f"❌ Error: Still could not open the image file. Detailed issue:\n{e}")
    exit()

# Get properties
height, width, _ = image.shape

# 2. Define the exact percentage-based crop boxes for each sticker
sticker_boxes = {
    "1_Fishermen": (int(0.02 * height), int(0.04 * width), int(0.50 * height), int(0.31 * width)),
    "2_Marine_Researchers": (int(0.02 * height), int(0.33 * width), int(0.50 * height), int(0.61 * width)),
    "3_Coastal_Authorities": (int(0.02 * height), int(0.67 * width), int(0.50 * height), int(0.96 * width)),
    "4_Disaster_Management": (int(0.50 * height), int(0.22 * width), int(0.98 * height), int(0.49 * width)),
    "5_Maritime_Operators": (int(0.50 * height), int(0.51 * width), int(0.98 * height), int(0.78 * width))
}

print(f"Processing image ({width}x{height} px)... Extracting 5 custom cutouts...")

# Get the directory where the source image lives to save the outputs in the same place
output_dir = os.path.dirname(image_path)

# 3. Loop through, crop each sticker, and save them
for label, (ymin, xmin, ymax, xmax) in sticker_boxes.items():
    cropped_sticker = image[ymin:ymax, xmin:xmax]
    
    # Save output file directly to the same directory as the source image
    output_filename = os.path.join(output_dir, f"{label}.png")
    
    # Save cleanly back via PIL to avoid cv2.imwrite path errors
    cv2.imwrite(output_filename, cropped_sticker)
    print(f" Saved: {output_filename}")

print("\n 🎉 Extraction complete! Check your folder for the 5 separate images.")
