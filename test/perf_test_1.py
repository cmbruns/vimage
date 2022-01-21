import cProfile
from pstats import SortKey, Stats
import glob
from OpenGL import GL


def perf_test_1(window):
    images = glob.glob(r"\\diskstation\Public\Pictures\2022\ThetaSunrise\*3.jpg")
    with cProfile.Profile() as p:
        for image in images:
            # print(image)
            window.load_image(image)
            window.repaint()
            # GL.glFlush()
    ps = Stats(p).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats()
