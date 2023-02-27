import json
import logging
import os
import socket
import struct
import sys
import threading
import time

logger = logging.getLogger(__name__)

FREQ_DEF = 5 # Default Heartbeat Rate: 5 seconds


class HeartbeatClient:

    def __init__(self, destination, id=None, rate=FREQ_DEF, verbose=False):
        """Constructor.

        Args:
            destination (str): Destination sockets addressed.
            id (str, optional): Process identifier. Defaults to None.
            rate (int, optional): Outgoing heartbeat rate. Defaults to FREQ_DEF.
            verbose (bool, optional): Verbose log output.
        """
        self._socket = socket.socket(family=socket.AF_UNIX,
                                     type=  socket.SOCK_DGRAM)

        self._condition = threading.Condition()
        
        self.__pid = os.getpid()
        self._shutdown = False

        if id is None:
            id = str(self.__pid)

        self.destination = destination
        self.id = id
        self.rate = rate
        self.verbose = verbose

    def run(self):
        """Start the client and serve forever."""
        self._connect()

        if self.id:
            self.register()

        if self.verbose:
            logger.info(f"Starting Client | {self.__pid} | {self.id}") 

        while not self._shutdown:
            try:
                self._send(packet_type=1)
                time.sleep(FREQ_DEF)
            except KeyboardInterrupt:
                self._safe_exit()

        with self._condition:
            self._condition.notify_all()

    def shutdown(self):
        """Gracefully shutdown the client.
        
        Must be called in a different thread of execution than `run`.
        """
        if self.verbose:
            logger.info(f"Shutting Down Client | {self.__pid} | {self.id}") 

        with self._condition:
            self._shutdown = True
            self._condition.wait()
            self._safe_exit()

    def _connect(self):
        """Create and bind socket."""
        self._socket.connect(self.destination)
        
        # Bind socket to abstract namespace
        self._socket.bind("")
    
    def register(self):
        """Register the client with the server."""
        if self.verbose:
            logger.info(f"Registering Client | {self.__pid} | {self.id}")

        if len(self.id) <= 12:
            self._send(packet_type=2)
        else:
            raise ValueError("id exceeds maximum character limit.")
    
    def deregister(self):
        """Deregister the client with the server."""
        if self.verbose:
            logger.info(f"Deregistering Client | {self.__pid} | {self.id}") 

        self._send(packet_type=3)
    
    def _send(self, packet_type):
        """Create and send heartbeat to destination.

        Packet Types:
            1: Heartbeat
            2: Register
            3: Deregister

        Args:
            packet_type (int): Packet type. Either 1, 2, or 3.
        """
        signed_packet = self._sign_packet(type_=packet_type)
        
        if self._handle_packet_size(signed_packet):
            self._socket.send(signed_packet)
            
            if self.verbose:
                logger.info(f"Successfully Sent Packet | {self.__pid} | {self.id} | {packet_type} | {signed_packet}") 
        else:
            logger.warning("Invalid Packet: ", signed_packet)

    def _sign_packet(self, type_):
        """Sign the outgoing UDP packet.

        Types:
            1: heartbeat
            2: register
            3: deregister

        Heartbeat and Deregister packet's are 14 bytes.
        
        *Register packets are 26 bytes - and optionally include a custom
        identifier if `self.id` is defined: a string of size 0 < num chars <= 12.

        -------- ------------------------ ------------------------ ------------------------------------------
        | Type |     Unix Timestamp     |    Process ID (pid)    |       *REGISTER ONLY: Identifier        |
        -------- ------------------------ ------------------------ ------------------------------------------
        1-2 Bytes        8 Bytes                   4 Bytes                         *12 Bytes

        Args:
            type_ (str): Either "heartbeat", "register", or "deregister".
        """
        register = True if type_ == 2 else False
        
        packet = bytearray(26) if register else bytearray(14)

        unix_t = time.time()
        print(type_, unix_t, self.__pid, self.id)

        type_bytes = struct.pack(">b", type_)
        time_bytes = struct.pack(">d", unix_t)
        # On a 64-bit system, max PID size is 4194304 (2 ** 22), so this will 
        # always fit into 4 bytes.    
        pid_bytes = struct.pack(">i", self.__pid)

        # Populate bytearray
        packet[1:2] = type_bytes
        packet[2:10] = time_bytes
        packet[10:14] = pid_bytes

        if register:
            ident_bytes = struct.pack("12s", self.id.encode("UTF-8")) 
            packet[14:26] = ident_bytes

        return packet

    def _handle_packet_size(self, packet):
        """Length bytes packet <= 26 bytes.

        Args:
            packet (bytes): UDP Packet.

        Returns:
            bool: True/False.
        """
        return len(packet) <= 26

    def _safe_exit(self):
        """Gracefully Exit.

        Tests:
            - After calling safe exit (with just shutdown), calls to socket.rcvfrom() returned None, but
            the file descriptor wasn't automatically released, so calls to rcvfrom still went through.
        """
        self.deregister()
        self._socket.shutdown(socket.SHUT_RDWR)
        self._socket.close()

        if self.verbose:
            logger.info(f"Successfully Shut Down | {self.__pid} | {self.id} |")
