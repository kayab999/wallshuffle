import os
import tempfile
import unittest

from wallshuffle.image_discovery import (
    count_images_in_folder,
    find_images_in_folder,
    is_usable_image_path,
)


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

    def test_file_symlink_is_discovered(self):
        """Symlinks to image files must count as wallpapers (hyperlink folders)."""
        real_dir = os.path.join(self.root, "real_store")
        link_dir = os.path.join(self.root, "hyperlinks")
        os.makedirs(real_dir)
        os.makedirs(link_dir)
        real_img = os.path.join(real_dir, "photo.jpg")
        with open(real_img, "wb") as handle:
            handle.write(b"fake-image")
        link_img = os.path.join(link_dir, "alias.jpg")
        os.symlink(real_img, link_img)

        self.assertTrue(is_usable_image_path(link_img))
        non_rec = find_images_in_folder(link_dir, recursive=False)
        rec = find_images_in_folder(link_dir, recursive=True)
        self.assertEqual([os.path.basename(p) for p in non_rec], ["alias.jpg"])
        self.assertEqual([os.path.basename(p) for p in rec], ["alias.jpg"])

    def test_dangling_symlink_is_ignored(self):
        link_dir = os.path.join(self.root, "broken_links")
        os.makedirs(link_dir)
        dangling = os.path.join(link_dir, "gone.jpg")
        os.symlink("/no/such/target/image.jpg", dangling)

        self.assertFalse(is_usable_image_path(dangling))
        self.assertEqual(find_images_in_folder(link_dir, recursive=False), [])
        self.assertEqual(find_images_in_folder(link_dir, recursive=True), [])

    def test_extensionless_symlink_to_image_is_discovered(self):
        real_dir = os.path.join(self.root, "store2")
        link_dir = os.path.join(self.root, "plain_links")
        os.makedirs(real_dir)
        os.makedirs(link_dir)
        real_img = os.path.join(real_dir, "photo.jpg")
        with open(real_img, "wb") as handle:
            handle.write(b"fake-image")
        plain = os.path.join(link_dir, "alias_no_ext")
        os.symlink(real_img, plain)
        self.assertTrue(is_usable_image_path(plain))
        found = find_images_in_folder(link_dir, recursive=False)
        self.assertEqual([os.path.basename(p) for p in found], ["alias_no_ext"])

    def test_directory_symlink_followed_when_recursive(self):
        real_dir = os.path.join(self.root, "elsewhere")
        os.makedirs(real_dir)
        with open(os.path.join(real_dir, "deep.jpg"), "w") as handle:
            handle.write("x")
        wrapper = os.path.join(self.root, "wrapper")
        os.makedirs(wrapper)
        os.symlink(real_dir, os.path.join(wrapper, "portal"))

        self.assertEqual(find_images_in_folder(wrapper, recursive=False), [])
        found = find_images_in_folder(wrapper, recursive=True)
        self.assertEqual([os.path.basename(p) for p in found], ["deep.jpg"])


if __name__ == "__main__":
    unittest.main()
