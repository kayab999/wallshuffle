"""EXIF orientation regression: thumbnail-before-transpose must keep geometry.

Cases verified against `ImageOps.exif_transpose` on the same stored files:
reference quadrant mapping (TL/TR/BL/BR) after transpose, for
- JPEG no-EXIF, JPEG EXIF 6 (rotate 90 CW to display), JPEG EXIF 8 (90 CCW),
- PNG equivalent dimensions,
- large JPEG EXIF 6 that forces the in-place BILINEAR thumbnail branch.

If the pipeline skipped `exif_transpose` (or applied it twice) the quadrant
colors would not match these tables. Output files must NOT carry an
orientation tag (pixels are already upright; a tag would double-rotate in the
desktop environment render).
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps

from wallshuffle.wallpaper_manager import WallpaperManager

# Quadrant centers as fractions of the output size.
SAMPLE_FRACTIONS = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)


def _quadrant_image(w, h):
    """800x400: TL red | TR green, BL blue | BR yellow."""
    img = Image.new("RGB", (w, h))
    hw, hh = w // 2, h // 2
    img.paste(RED, (0, 0, hw, hh))
    img.paste(GREEN, (hw, 0, w, hh))
    img.paste(BLUE, (0, hh, hw, h))
    img.paste(YELLOW, (hw, hh, w, h))
    return img


def _save_tagged(img, path, orientation):
    if orientation:
        ex = img.getexif()
        ex[274] = orientation
        img.save(path, exif=ex)
    else:
        img.save(path)


class TestExifOrientation(unittest.TestCase):
    def setUp(self):
        # create_composite_image writes into ~/.config/wallshuffle/temp via
        # expanduser; redirect HOME for the duration of each test.
        self.home = tempfile.mkdtemp(prefix="ws_exif_home_")
        self.env = patch.dict("os.environ", {"HOME": self.home})
        self.env.start()
        os.makedirs(os.path.join(self.home, ".config", "wallshuffle", "temp"), exist_ok=True)
        self.manager = WallpaperManager()
        self.tracked = []  # outputs created, for cleanup

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _assert_geometry(self, stored_path, orientation, monitor, expected):
        out_path = self.manager.create_composite_image(stored_path, [dict(monitor)])
        self.tracked.append(out_path)
        with Image.open(out_path) as out:
            self.assertEqual(out.size, (monitor["width"], monitor["height"]),
                             f"stored {stored_path} monitor {monitor['width']}x{monitor['height']}")
            self.assertNotIn(274, out.getexif(), "upright output must not re-rotate in the DE")
            self.assertTrue(
                ImageOps.exif_transpose(out) is None or out.getexif().get(274, 0) in (0, 1),
                "output pixels must already be upright",
            )
            for (fx, fy), color in zip(SAMPLE_FRACTIONS, expected, strict=True):
                px = out.getpixel((int(out.width * fx), int(out.height * fy)))
                for channel in range(3):
                    self.assertLess(
                        abs(px[channel] - color[channel]), 60,
                        f"quadrant {fx},{fy} of {stored_path}: {px} != {color}",
                    )

    def test_jpeg_without_exif_keeps_identity_geometry(self):
        stored = os.path.join(self.home, "plain.jpg")
        _save_tagged(_quadrant_image(800, 400), stored, 0)
        self._assert_geometry(
            stored, 0, {"x": 0, "y": 0, "width": 200, "height": 100},
            [RED, GREEN, BLUE, YELLOW],
        )

    def test_jpeg_exif6_rotates_90_cw(self):
        stored = os.path.join(self.home, "e6.jpg")
        _save_tagged(_quadrant_image(800, 400), stored, 6)
        # Portrait monitor: exact fit after transpose — full quadrants visible.
        self._assert_geometry(
            stored, 6, {"x": 0, "y": 0, "width": 100, "height": 200},
            [BLUE, RED, YELLOW, GREEN],
        )

    def test_jpeg_exif6_on_landscape_monitor_keeps_mapping(self):
        stored = os.path.join(self.home, "e6b.jpg")
        _save_tagged(_quadrant_image(800, 400), stored, 6)
        # The center crop band lies exactly at the stored top/bottom split, so
        # the quadrant mapping is preserved even in landscape framing.
        self._assert_geometry(
            stored, 6, {"x": 0, "y": 0, "width": 200, "height": 100},
            [BLUE, RED, YELLOW, GREEN],
        )

    def test_jpeg_exif8_rotates_90_ccw(self):
        stored = os.path.join(self.home, "e8.jpg")
        _save_tagged(_quadrant_image(400, 800), stored, 8)
        self._assert_geometry(
            stored, 8, {"x": 0, "y": 0, "width": 200, "height": 100},
            [GREEN, YELLOW, RED, BLUE],
        )

    def test_png_without_exif_is_untouched(self):
        stored = os.path.join(self.home, "plain.png")
        # PNG has no draft() decode shortcut: same dimensions exercise the
        # non-JPEG decode path (uniform behavior).
        _save_tagged(_quadrant_image(800, 400), stored, 0)
        self._assert_geometry(
            stored, 0, {"x": 0, "y": 0, "width": 200, "height": 100},
            [RED, GREEN, BLUE, YELLOW],
        )

    def test_large_jpeg_exif6_survives_thumbnail_branch(self):
        stored = os.path.join(self.home, "e6_big.jpg")
        _save_tagged(_quadrant_image(4000, 2000), stored, 6)
        # 4000x2000 > 2x(800x1600): forces draft()+thumbnail() before transpose.
        self._assert_geometry(
            stored, 6, {"x": 0, "y": 0, "width": 800, "height": 1600},
            [BLUE, RED, YELLOW, GREEN],
        )


if __name__ == "__main__":
    unittest.main()
