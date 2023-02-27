"""Simple heartbeat server implementation

Capable of handling up to 1000 requests/s.
"""
import json
import logging
import struct
import time

from .socket_server import UnixSocketServer

logger = logging.getLogger(__name__)

# Default interval for heartbeat's to be checked.
#
# Warning: Each subscribed client is expected to send it's heartbeats 
# in an interval bounded by HBT_DEF as it's maximum. However, it is 
# reccomended to set the client's heartbeat frequency signifcantly below
# that of HBT_DEF, to prevent faulty alarms after lost packets. Failure to 
# calibrate the client and server's heartbeat intervals will result 
# in faulty alerts.   
HBT_DEF = 10

# Standard client heartbeat packet size is 14 bytes.
# Registering a new client sends a 26 byte packet. 
HBT_SIZE = 26


class HeartbeatServer(UnixSocketServer):

    def __init__(self, timeout=HBT_DEF, bufsize=HBT_SIZE, path=None, bind=True, verbose=False):
        UnixSocketServer.__init__(self, timeout, bufsize, path, bind)
        
        # {client_pid: {"process_name": x, "last_heartbeat": y}
        self.clients = {}
        
        # Verbose Log Output
        self.verbose = verbose
        
    def notify(self, pid):
        """Handle missed heartbeat. 
        
        Default: Send log message.
        
        Can be overwritten by Subclass / Mixin. This function will
        block the main `serve` method.
        """
        process_name = self.clients[pid]["process_name"]
        timestamp = time.time()

        logger.warning(f"Missed Heartbeat | {pid} | {timestamp} | {process_name}")

    def handle_request(self, request):
        """Handle a new message.

        Args:
            data (bytes): Raw UDP message.
            address (str): Sender's address.
        """
        data, address = request
        
        try:
            struc = self._unpack(data)
            
            _type = struc[0]
            args = struc[1:] # pid, timestamp, process_name

            match _type:
                case 1:
                    self._heartbeat(*args)
                case 2:
                    self._register(*args)
                case 3:
                    self._deregister(*args)
            
        except KeyError: # Maybe don't need this?
            logger.warning(f"Invalid Message | {struc}")

    def _unpack(self, packet):
        """Unpack recieved UDP packet.

        Client UDP packets are expected to adhere to the following schematic, where heartbeat and deregister packets
        are 14 bytes, and register packets are 26 bytes:

        -------- ------------------------ ------------------------ ------------------------------------------
        | Type |     Unix Timestamp     |    Process ID (pid)    |       *REGISTER ONLY: Identifier        |
        -------- ------------------------ ------------------------ ------------------------------------------
        1-2 Bytes        8 Bytes                   4 Bytes                         *12 Bytes

        Args:
            packet (bytes): UDP Packet recieved from `HeartbeatClient`.
        """
        ident = None
        _type = packet[1]
        timestamp = struct.unpack(">d", packet[2:10])[0]
        pid = struct.unpack(">i", packet[10:14])[0]
        
        if _type == 2:
            ident_bytes = struct.unpack("12s", packet[14:26])[0]
            ident = ident_bytes.decode('UTF-8').rstrip("\x00")

        return _type, pid, timestamp, ident
    
    def _heartbeat(self, pid, timestamp, process_name):
        """Process recieved heartbeat.

        Args:
            pid (int): Process ID.
            timestamp (float): UNIX Timestamp.
            process_name (str): Process Identifier.
        """
        if pid in self.clients:
            self.clients[pid]["last_heartbeat"] = timestamp
        else:
            self.clients[pid] = {"process_name": process_name, 
                                "last_heartbeat": timestamp}
        
        if self.verbose:
            process_name = self.clients[pid]["process_name"]
            logger.info(f"Heartbeat | {pid} | {timestamp} | {process_name}")

    def _register(self, pid, timestamp, process_name):
        """Forceably register a new client.

        Args:
            pid (int): Process ID.
            timestamp (float): UNIX Timestamp.
            process_name (str): Process Identifier.
        """
        self.clients[pid] = {"process_name": process_name, 
                            "last_heartbeat": timestamp}
        
        if self.verbose:
            logger.info(f"Registered | {pid} | {timestamp} | {process_name}")

    def _deregister(self, pid, timestamp, process_name):
        """Forceably deregister a client.

        Args:
            pid (int): Process ID.
        """
        process_name = self.clients[pid]["process_name"]
        del self.clients[pid]

        if self.verbose:
            logger.info(f"Deregistered | {pid} | {timestamp} | {process_name}")

    def request_hook(self):
        """Check clients for recent heartbeats."""
        currtime = time.time()
        threshold = currtime - HBT_DEF

        # Copy() instead of blocking.
        clients_cpy = self.clients.copy()

        for client, data in clients_cpy.items():
            last_beat = data["last_heartbeat"]
            if last_beat < threshold:
                self.notify(client)