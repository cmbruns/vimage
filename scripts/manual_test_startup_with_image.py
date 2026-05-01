# scripts/manual_test_startup_with_image.py
"""
Manual test: Launch app with image argument and verify display.
Run manually: python scripts/manual_test_startup_with_image.py
"""

import subprocess
import sys
import os

def test_startup_with_image():
    image_path = os.path.join(os.path.dirname(__file__), "..", "test", "images", "hopper_grayscale.jpg")
    cmd = [sys.executable, "-m", "vmg", image_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"App failed: {result.stderr}"
    print("App launched successfully. Manually verify the image displays correctly.")

if __name__ == "__main__":
    test_startup_with_image()