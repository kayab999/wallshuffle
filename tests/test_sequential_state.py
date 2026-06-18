import os
import tempfile
import unittest
from unittest.mock import patch

from wallshuffle.sequential_state import folder_state_key, select_sequential_images


class TestSequentialState(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.temp_dir.name, "sequential_state.json")
        self.folder = os.path.join(self.temp_dir.name, "wallpapers")
        os.makedirs(self.folder)
        self.images = [os.path.join(self.folder, f"{index}.jpg") for index in range(5)]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_rotates_through_images(self):
        with patch("wallshuffle.sequential_state.SEQUENTIAL_STATE_FILE", self.state_file):
            first = select_sequential_images(self.images, self.folder, 2)
            second = select_sequential_images(self.images, self.folder, 2)

        self.assertEqual(first, self.images[:2])
        self.assertEqual(second, self.images[2:4])

    def test_folder_state_key_is_stable(self):
        self.assertEqual(folder_state_key(self.folder), folder_state_key(self.folder))


if __name__ == "__main__":
    unittest.main()
