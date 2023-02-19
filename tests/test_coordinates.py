import unittest

from PySide6.QtCore import QPoint

from vmg.coordinate import WindowPos


class TestCoordinates(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_window_pos(self):
        wp = WindowPos(1, 2)
        qp = QPoint(1, 2)
        wp2 = WindowPos.from_qpoint(qp)
        self.assertEqual(1, wp2.x)


if __name__ == '__main__':
    unittest.main()
