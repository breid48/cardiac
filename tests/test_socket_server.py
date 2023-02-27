import unittest
import time
import unittest.mock as mock

from socket import AF_UNIX, SOCK_DGRAM
from threading import Thread

from src.socket_server import UnixSocketServer


class TestSocketServer(unittest.TestCase):

    def setUp(self):
        self.server = UnixSocketServer(timeout=5, bufsize=16, bind=False)
    
    def tearDown(self):
        try:
            self.server._safe_exit()
        except:
            pass

    def test_constructor_sets_timeout(self):
        self.assertEqual(self.server.timeout, 5)
    
    def test_constructor_sets_bufsize(self):
        self.assertEqual(self.server.bufsize, 16)

    def test_constructor_sets_path(self): # Add path?
        self.assertEqual(self.server.path, None)
    
    def test_socket_initialized_with_address_and_family(self):
        with mock.patch("socket.socket") as mock_socket:
            mock_socket.return_value.socket.return_value = None
            server = UnixSocketServer(timeout=5, bufsize=16, bind=True)
        mock_socket.assert_called_with(family=AF_UNIX, type=SOCK_DGRAM)
    
    def test_recvfrom_called_with_bufsize(self):
        with mock.patch("socket.socket") as mock_socket:
            mock_socket.return_value.recvfrom.return_value = 0, 0
            server = UnixSocketServer(timeout=5, bufsize=16, bind=True)
            server.get_request()
        server._socket.recvfrom.assert_called_with(16)
    
    def test_get_request_returns_recvfrom_response(self):
        with mock.patch("socket.socket") as mock_socket:
            mock_socket.return_value.recvfrom.return_value = "arb_bytes", "arb_address"
            server = UnixSocketServer(timeout=5, bufsize=16, bind=True)
            b, a = server.get_request()
        self.assertEqual(b, "arb_bytes")
        self.assertEqual(a, "arb_address")

    def test_bind_default_parameter(self):
        with mock.patch("src.socket_server.UnixSocketServer._bind_local") as mock_bind:
            server = UnixSocketServer(timeout=5, bufsize=16)
            mock_bind.assert_called()
        server._safe_exit()

    def test_bind_false_parameter(self):
        with mock.patch("src.socket_server.UnixSocketServer._bind_local") as mock_bind:
            server = UnixSocketServer(timeout=5, bufsize=16, bind=False)
            mock_bind.assert_not_called()
        server._safe_exit()

    def test_bind_explicit_path(self):
        with mock.patch("socket.socket"):
            server = UnixSocketServer(timeout=5, bufsize=16, path="/simulated/path/to/socket.s")
        server._socket.bind.assert_called_with("/simulated/path/to/socket.s")

    def test_binds_to_generated_path(self):
        with mock.patch("socket.socket"):
            server = UnixSocketServer(timeout=5, bufsize=16)
        bind_path = server.path
        server._socket.bind.assert_called_with(bind_path)

    def test_bind_generated_correct_path(self):
        with mock.patch("socket.socket"):
            server = UnixSocketServer(timeout=5, bufsize=16)
        bind_path = server.path
        self.assertEqual(True, bind_path.startswith("/tmp/unx_ss/server."))

    def test_safe_exit_destroys_fd(self):
        self.server._safe_exit()
        self.assertEqual(-1, self.server.fileno())
    
    def test_cleanup_unlinks_socket_file(self):
        # Mock os.unlink
        # make sure its called with correct path
        # Do one explicit and one implicit path maybe?
        with mock.patch("os.unlink") as mock_unlink:
            server = UnixSocketServer(timeout=5, bufsize=16)
            server._cleanup()
        mock_unlink.assert_called_with(server.path)
        server._socket.close()

    def test_shutdown_blocks(self):
        with mock.patch("threading.Condition.wait"):
            self.assertEqual(self.server._shutdown, False)
            self.server.shutdown()
            self.assertEqual(self.server._shutdown, True)
            self.server._condition.wait.assert_called()

    def test_serve_notifies_blocked_thread(self):
        # Ensure serve wakes up blocked thread when self._shutdown is True
        with mock.patch("threading.Condition.notify_all"):
            self.server._shutdown = True
            self.server.serve()
            self.server._condition.notify_all.assert_called()

    def test_shutdown_releases_block_with_notify(self):
        # More of an integration test?
        pass
    
    def test_safe_exit(self):
        pass