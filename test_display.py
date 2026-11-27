import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


class Panel:
    def __init__(self):
        self.windows = []
        self.selected = []
        self.pixels = bytearray()
        self.spi = SimpleNamespace(write=self.pixels.extend)

    def _window(self, *rect):
        self.windows.append(rect)

    def cs(self, level):
        self.selected.append(level)

    def dc(self, level):
        pass


class RenderTest(unittest.TestCase):
    def test_menu_writes_composed_pixels_once_including_growth(self):
        from device.panel import menu
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = bytes(i % 251 for i in range(240*240*2))
            status = b's' * (480*32)
            buttons = b'b' * (480*48)
            for name, data in [('pose0', image), ('status', status), ('buttons', buttons),
                               ('growth-label', b'_' * (480*20)),
                               ('growth-digits', b''.join(bytes([i])*400 for i in range(11)))]:
                (root/(name+'.rgb')).write_bytes(data)
            panel = Panel()
            menu(panel, directory+'/', 'pose0', 'status', 'buttons', 12.5)
            expected = bytearray(image + status + buttons)
            for row in range(219,239):
                start = row*480
                expected[start:start+480] = b'_'*480
                expected[start+96:start+176] = b'\1'*20 + b'\2'*20 + bytes([10])*20 + b'\5'*20
            self.assertEqual(panel.windows, [(0,0,239,319)])
            self.assertEqual(panel.selected, [0,1])
            self.assertEqual(panel.pixels, expected)

    def test_neutral_pose_restores_only_pet_even_from_full_width_source(self):
        from device.panel import restore
        with tempfile.TemporaryDirectory() as directory:
            image = bytes(i % 251 for i in range(480*240))
            path = Path(directory)/'pose0.rgb'
            path.write_bytes(image)
            panel = Panel()
            restore(panel,str(path))
            self.assertEqual(panel.windows, [(58,41,181,179)])
            self.assertEqual(panel.pixels, b''.join(image[r*480+116:r*480+364] for r in range(41,180)))

    def test_truncated_frame_releases_bus(self):
        from device.panel import present
        panel = Panel()
        with self.assertRaises(ValueError):
            present(panel,0,0,2,2,[b'1234'])
        self.assertEqual(panel.selected, [0,1])
