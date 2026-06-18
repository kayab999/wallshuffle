import socket
import unittest

from wallshuffle.app import FrameLengthSocket
from wallshuffle.constants import MAX_IPC_MESSAGE_BYTES


class TestFrameLengthSocket(unittest.TestCase):
    def setUp(self):
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind("\0wallshuffle_test_ipc")
        self.server.listen(1)
        self.client.connect("\0wallshuffle_test_ipc")
        self.conn, _ = self.server.accept()
        self.server_frame = FrameLengthSocket(self.conn)
        self.client_frame = FrameLengthSocket(self.client)

    def tearDown(self):
        self.client.close()
        self.conn.close()
        self.server.close()

    def test_round_trip_message(self):
        self.client_frame.send_message(b"STATUS")
        message = self.server_frame.receive_message()
        self.assertEqual(message, b"STATUS")

    def test_rejects_oversized_incoming_message(self):
        import struct

        oversized = MAX_IPC_MESSAGE_BYTES + 1
        self.client.sendall(struct.pack(">I", oversized))
        message = self.server_frame.receive_message()
        self.assertIsNone(message)


if __name__ == "__main__":
    unittest.main()
