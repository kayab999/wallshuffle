import os
import unittest
from unittest.mock import patch

from wallshuffle.gui_helpers import show_error_dialog


class TestGuiHelpers(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_headless_error_prints_to_stderr(self):
        with patch("builtins.print") as mock_print:
            show_error_dialog("Something failed", parent=None)
        mock_print.assert_called()


if __name__ == "__main__":
    unittest.main()
