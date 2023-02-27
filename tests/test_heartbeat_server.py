import unittest
import unittest.mock as mock

from src.heartbeat_server import HeartbeatServer


class TestHeartbeatServer(unittest.TestCase):

    def setUp(self):
        self.server = HeartbeatServer()

    def tearDown(self):
        try:
            self.server._safe_exit()
        except:
            pass

    def test_unpack_heartbeat_packet(self):
        bytes_ = b'\x00\x01A\xd8\xff\x06\xfb\xaa<M\x00\x16\xd6"'
        
        res_type, res_pid, res_timestamp, res_ident = self.server._unpack(bytes_)
        
        self.assertEqual(1, res_type)
        self.assertEqual(1496610, res_pid)
        self.assertEqual(1677466606.6599305, res_timestamp)
        self.assertEqual(None, res_ident)

    def test_unpack_register_packet(self):
        bytes_ = b'\x00\x02A\xd8\xff\x08a\xccY\x16\x00\x16\xdc 1498144\x00\x00\x00\x00\x00'
        
        res_type, res_pid, res_timestamp, res_ident = self.server._unpack(bytes_)
        
        self.assertEqual(2, res_type)
        self.assertEqual(1498144, res_pid)
        self.assertEqual(1677468039.1929374, res_timestamp)
        self.assertEqual("1498144", res_ident)

    def test_unpack_deregister_packet(self):
        bytes_ = b'\x00\x03A\xd8\xff\t\x95\xa1\x85\x06\x00\x16\xddm'
        
        res_type, res_pid, res_timestamp, res_ident = self.server._unpack(bytes_)
        
        self.assertEqual(3, res_type)
        self.assertEqual(1498477, res_pid)
        self.assertEqual(1677469270.523744, res_timestamp)

    def test_handle_request_calls_heartbeat(self):
        bytes_ = b'\x00\x01A\xd8\xff\x06\xfb\xaa<M\x00\x16\xd6"'
        request = (bytes_, 0000)
        with mock.patch("src.heartbeat_server.HeartbeatServer._heartbeat"):
            server = HeartbeatServer()
            server.handle_request(request)
            server._heartbeat.assert_called()
            server._safe_exit()

    def test_handle_request_calls_register(self):
        bytes_ = b'\x00\x02A\xd8\xff\x08a\xccY\x16\x00\x16\xdc 1498144\x00\x00\x00\x00\x00'
        request = (bytes_, 0000)
        with mock.patch("src.heartbeat_server.HeartbeatServer._register"):
            server = HeartbeatServer()
            server.handle_request(request)
            server._register.assert_called()
            server._safe_exit()

    def test_handle_request_calls_deregister(self):
        bytes_ = b'\x00\x03A\xd8\xff\t\x95\xa1\x85\x06\x00\x16\xddm'
        request = (bytes_, 0000)
        with mock.patch("src.heartbeat_server.HeartbeatServer._deregister"):
            server = HeartbeatServer()
            server.handle_request(request)
            server._deregister.assert_called()
            server._safe_exit()

    def test_heartbeat_records_data(self):
        pid, timestamp, ident = 9999, 1111, "test"
        
        self.server._heartbeat(pid, timestamp, ident)
        
        self.assertIn(pid, self.server.clients)
        self.assertEqual(self.server.clients[pid]["last_heartbeat"], timestamp)
        self.assertEqual(self.server.clients[pid]["process_name"], ident)

    def test_register_records_client(self):
        pid, timestamp, ident = 9999, 1111, "test"
        
        self.server._register(pid, timestamp, ident)
        
        self.assertIn(pid, self.server.clients)
        self.assertEqual(self.server.clients[pid]["last_heartbeat"], timestamp)
        self.assertEqual(self.server.clients[pid]["process_name"], ident)

    def test_register_overwrites_existing_client(self):
        pid, timestamp, ident = 9999, 1111, "test"
        
        self.server._heartbeat(pid, timestamp, ident)
        self.server._register(9999, 2222, "test")

        self.assertEqual(self.server.clients[pid]["last_heartbeat"], 2222)
        self.assertEqual(self.server.clients[pid]["process_name"], ident)

    def test_deregister_removes_client(self):
        pid, timestamp, ident = 9999, 1111, "test"
        
        self.server._register(pid, timestamp, ident)
        self.assertIn(pid, self.server.clients)
        
        self.server._deregister(pid, timestamp, ident)
        self.assertNotIn(pid, self.server.clients)

    def test_request_hook_notifies_missed_heartbeat(self):
        with mock.patch("src.heartbeat_server.HeartbeatServer.notify"):
            server = HeartbeatServer()
            server.clients[9999] = {"process_name": "test", 
                                    "last_heartbeat": 1111}
            server.request_hook()
            server.notify.assert_called()
            server._safe_exit()
        