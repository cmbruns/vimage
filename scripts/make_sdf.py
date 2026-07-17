import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------
INPUT_IMAGE = r"C:\Users\cmbruns\Documents\git\vimage\vmg\images\Hexbig.png"     # your 1-bit atlas
OUTPUT_IMAGE = "output_sdf.png"      # final SDF PNG
DOWNSIZE_TO = (640, 64)              # width, height of final atlas
THRESHOLD = 128                      # threshold for 1-bit conversion
NORMALIZE_DISTANCE = 80.0            # controls SDF contrast
# ------------------------------------------------------------

# 1. Load image and convert to 1-bit mask
img = Image.open(INPUT_IMAGE).convert("L")
arr = np.array(img)

# mask: True = inside glyph, False = outside
mask = arr > THRESHOLD

# 2. Compute Euclidean distance transform
dist_out = distance_transform_edt(~mask)   # distance to nearest glyph pixel
dist_in  = distance_transform_edt(mask)    # distance to nearest background pixel

# Signed distance field
sdf = dist_out - dist_in

# 3. Normalize SDF to [-1, 1]
sdf_norm = sdf / NORMALIZE_DISTANCE
sdf_norm = np.clip(sdf_norm, -1.0, 1.0)

# Convert to 8-bit grayscale
sdf_img = ((sdf_norm * 0.5 + 0.5) * 255).astype(np.uint8)

# 4. Downsize using high-quality resampling
sdf_pil = Image.fromarray(sdf_img)
sdf_pil = sdf_pil.resize(DOWNSIZE_TO, Image.LANCZOS)

# 5. Save final grayscale PNG
sdf_pil.save(OUTPUT_IMAGE)
print("Saved:", OUTPUT_IMAGE)
