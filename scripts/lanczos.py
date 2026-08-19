"""
Tabulate Lanczos weights so we can hard code them and limit tap count in glsl

Plan:
  Use largest window lacking abs(weights) outside neighborhood > 0.01
  Hard coded weights for best 7x7 lanczos
    red, green, blue at red
    red, green, blue at blue
    red, green, blue at green_in_red_row
    red, green, blue at green_in_blue_row

  Also 5x5

  Also just green, for use with median chroma

  Also chroma math

  
"""

from math import pi, sin
import numpy as np

Float = float  # shut up, PyCharm


def lanczos(x: Float, window: Float, rate: Float) -> Float:
    x = abs(x/rate)  # distance
    window = window/rate
    if x > window:
        return 0.0
    return sinc(x) * sinc(x / window)


def sinc(x) -> Float:
    x *= pi
    return 1.0 if abs(x) < 1e-5 else sin(x) / x


MIN_VALID_WEIGHT = 0.01


def tabulate(
        window: Float,  # Lanczos window in texel units
        nbr: int,  # neighborhood width
):
    tap_count = 0  # Track cells with abs(weight) >= 0.01
    s22 = 2.0**-0.5
    rot45 = np.array([[s22, -s22], [s22, s22]], dtype=np.float32)
    method_name = "LGMC5"  # Lanczos green, median chroma, 5x5 neighborhood

    # 1) Populate in-memory weight array
    GRID_SIZE = 2 * nbr + 1
    weights = np.zeros(shape=(GRID_SIZE, GRID_SIZE), dtype=np.float32)
    for y in range(-nbr, +nbr + 1):
        for x in range(-nbr, +nbr + 1):
            xr, yr = rot45 @ (x, y)
            wx2 = lanczos(xr, window, 2.0**0.5)
            wy2 = lanczos(yr, window, 2.0**0.5)
            w = wx2 * wy2
            if abs(w) >= MIN_VALID_WEIGHT:
                tap_count += 1
            weights[y, x] = w
    print(f"// {tap_count} texels with abs(weight) >= {MIN_VALID_WEIGHT}")
    print(weights)

    # Print valid texel table in GLSL
    for y in range(-nbr, +nbr + 1):
        for x in range(-nbr, +nbr + 1):
            w = weights[y, x]
            if abs(w) >= MIN_VALID_WEIGHT:
                print(f"    ivec2({x}, {y})")

    # Print generic weight table in GLSL
    big_w_count = 0
    print("#define NA")
    print(f"const float {method_name}_G_AT_RB[{tap_count}] = float[{tap_count}](")
    print("  //  ", end="")
    for x in range(-nbr, +nbr + 1):
        print(f"x={x:+d}    ", end="")  # Legend X
    print()
    for y in range(-nbr, +nbr + 1):
        print("    ", end="")
        for x in range(-nbr, +nbr + 1):
            w = weights[y, x]
            delimiter = ","
            if x == nbr and y == nbr:
                delimiter = " "
            if abs(w) >= MIN_VALID_WEIGHT:
                print(f"{w:+.3f}{delimiter} ", end="")  # weight value
            else:
                print(f"{0:+.3f}{delimiter} ", end="")
        print(f"  // y={y:+d}:  ")  # Legend Y
    print(");")


if __name__ == "__main__":
    # Shrink the window until the nbr +-4 is less than 0.01
    # 4.5 -> 0.007; 4.65 -> 0.009; 4.7-> 0.010; 4.8 -> 0.011
    # So for 7x7 neighborhood, use window 4.65 and 37 texels
    # For 5x5 use window 3.1 and 21 texels
    tabulate(window=3.3, nbr=2)
