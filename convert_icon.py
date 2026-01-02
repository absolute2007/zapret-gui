"""
Converts app.png to app.ico with multiple resolutions for Windows compatibility
"""
from PIL import Image
from pathlib import Path

def convert():
    img_path = Path("app.png")
    if img_path.exists():
        img = Image.open(img_path)
        # Create ICO with multiple sizes
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save("app.ico", format='ICO', sizes=sizes)
        print("✓ Icon converted: app.ico")
    else:
        print("✗ app.png not found! Place the icon file in this directory.")

if __name__ == "__main__":
    convert()
