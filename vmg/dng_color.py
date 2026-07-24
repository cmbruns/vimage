import numpy
from enum import IntEnum
from numpy.typing import NDArray


class LightSource(IntEnum):
    UNKNOWN = 0
    DAYLIGHT = 1
    FLUORESCENT = 2
    TUNGSTEN = 3  # Incandescent light
    FLASH = 4
    FINE_WEATHER = 9
    CLOUDY_WEATHER = 10
    SHADE = 11
    DAYLIGHT_FLUORESCENT = 12        # D 5700 - 7100K
    DAY_WHITE_FLUORESCENT = 13       # N 4600 - 5400K
    COOL_WHITE_FLUORESCENT = 14      # W 3900 - 4500K
    WHITE_FLUORESCENT = 15           # WW 3200 - 3700K
    WARM_WHITE_FLUORESCENT = 16      # I 2600 - 3000K
    STANDARD_LIGHT_A = 17
    STANDARD_LIGHT_B = 18
    STANDARD_LIGHT_C = 19
    D55 = 20
    D65 = 21
    D75 = 22
    D50 = 23
    ISO_STUDIO_TUNGSTEN = 24
    OTHER = 255


# 1. Map standard DNG Illuminant tags to their exact nominal Kelvin temperatures
# Reference: DNG Spec Chapter 6 (CalibrationIlluminant tags)
illuminant_temps = {
    LightSource.DAYLIGHT: 6504,
    LightSource.TUNGSTEN: 2856,
    LightSource.STANDARD_LIGHT_A: 2856,  # Standard Illuminant A
    LightSource.STANDARD_LIGHT_B: 4874,  # Standard Illuminant B
    LightSource.STANDARD_LIGHT_C: 6774,  # Standard Illuminant C
    LightSource.D55: 5503,  # D55
    LightSource.D65: 6504,  # D65
    LightSource.D75: 7504,  # D75
    LightSource.D50: 5003,  # D50
}


def calculate_dng_t(
        as_shot_neutral,
        color_matrix1: NDArray,
        color_matrix2: NDArray,
        illuminant1: LightSource = LightSource.STANDARD_LIGHT_A,
        illuminant2: LightSource = LightSource.D65,
):
    """
    Calculates the DNG matrix interpolation weight 't' from AsShotNeutral.

    Parameters:
      as_shot_neutral: list or numpy.array of 3 floats, e.g., [0.52, 1.0, 0.63]
      color_matrix1:   3x3 numpy.array representing ColorMatrix1 (Tungsten)
      color_matrix2:   3x3 numpy.array representing ColorMatrix2 (Daylight)
      illuminant1:     DNG tag integer for CalibrationIlluminant1 (Default: 17 = Standard Illuminant A)
      illuminant2:     DNG tag integer for CalibrationIlluminant2 (Default: 21 = D65)
    """

    temp1 = illuminant_temps.get(illuminant1, 2856)
    temp2 = illuminant_temps.get(illuminant2, 6504)

    # 2. Derive a generic, un-white-balanced Camera-to-XYZ matrix
    # DNG spec defines ColorMatrix as XYZ -> Camera. We use its inverse.
    # We use a base blend of CM1 and CM2 just to calculate a valid local proxy spatial environment.
    cm_base = (color_matrix1 + color_matrix2) / 2.0
    cam_to_xyz = numpy.linalg.inv(cm_base)

    # 3. Project the AsShotNeutral raw channel scaling into CIE XYZ space
    # (AsShotNeutral is inverted to represent white balance multipliers)
    wb_gains = 1.0 / numpy.array(as_shot_neutral)
    xyz = numpy.dot(cam_to_xyz, wb_gains)

    # 4. Convert XYZ to CIE xy chromaticity coordinates
    xyz_sum = xyz[0] + xyz[1] + xyz[2]
    if xyz_sum == 0:
        return 0.5  # Fail-safe midpoint if data evaluates to zero
    x = xyz[0] / xyz_sum
    y = xyz[1] / xyz_sum

    # 5. McCamy's Cubic Approximation to find Correlated Color Temperature (CCT)
    # Convert xy to CIE 1960 uv landscape vectors
    u = (4.0 * x) / (-2.0 * x + 12.0 * y + 3.0)
    v = (6.0 * y) / (-2.0 * x + 12.0 * y + 3.0)

    # Epicenter of the chromatic adaptation path
    n = (u - 0.3320) / (v - 0.1858)
    cct_as_shot = -449.0 * (n ** 3) + 3525.0 * (n ** 2) - 6823.3 * n + 5524.07

    # Bound the evaluated temperature logically
    cct_as_shot = numpy.clip(cct_as_shot, 2000, 12000)

    # 6. Calculate 't' using inverse temperatures (Mired scale) per DNG rules
    mired_as_shot = 1.0 / cct_as_shot
    mired_1 = 1.0 / temp1
    mired_2 = 1.0 / temp2

    # Guard against division by zero if both illuminants are identical
    if mired_1 == mired_2:
        return 0.0

    t = (mired_as_shot - mired_1) / (mired_2 - mired_1)

    # Clamp t tightly between [0.0, 1.0] per Adobe specification framework
    return float(numpy.clip(t, 0.0, 1.0))
