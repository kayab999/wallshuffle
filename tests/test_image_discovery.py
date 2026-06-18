import os
import tempfile
import unittest

from wallshuffle.image_discovery import count_images_in_folder, find_images_in_folder


class TestImageDiscovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        os.makedirs(os.path.join(self.root, "nested"))
        for name in ("a.jpg", "b.png", "skip.txt"):
            with open(os.path.join(self.root, name), "w") as handle:
                handle.write("x")
        with open(os.path.join(self.root, "nested", "c.webp"), "w") as handle:
            handle.write("x")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_non_recursive_discovery(self):
        images = find_images_in_folder(self.root, recursive=False)
        self.assertEqual(sorted(os.path.basename(p) for p in images), ["a.jpg", "b.png"])

    def test_recursive_discovery(self):
        self.assertEqual(len(find_images_in_folder(self.root, recursive=True)), 3)
        self.assertEqual(count_images_in_folder(self.root, recursive=True), 3)


if __name__ == "__main__":
    unittest.main()
