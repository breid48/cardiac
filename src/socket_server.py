"""
A Unix Domain Socket (UDS) is a bidirectional communication socket
for communicating between processes on the same operating system/machine. 

SOCK_DGRAM / AF_UNIX  : Datagram oriented, UDP-like.

UNIX domain sockets only perform a subset of normal socket operations (like no routing); which 
makes them faster and lighter than IP sockets.

Binding to the File System:

After creatin a UNIX domain socket, it MUST be bound to a unique file path (rather than an IP and port).
A file descriptor is created which points to the "file".

Naming Conventions:

Emacs' name scheme, e.g. "/tmp/bar1000/what_the_socket_is_for", where "bar" is the application name again.

Advantage of using /tmp/ - dangling sockets will be automatically removed at boot. (IE: If the server crashes,
you won't be able to restart the socket server without first removing the socket file. This won't happen if its stored
in /tmp/.)
"""
import logging
import os
import secrets
import selectors
import socket
import sys
import threading

logger = logging.getLogger(__name__)

if not hasattr(socket, "AF_UNIX"):
    sys.exit("unix or unix-like system required.")

BASE_PATH = "/tmp/"
BASE_DIR = "unx_ss"
BASE_IDENT = "server"


class UnixSocketServer:
    """Base class representing a Unix socket server.

    Attributes:
        timeout (int): Socket read timeout.
        path (str): Socket bind path.
        bufsize (int): Socket maximum read size.
    """
    def __init__(self, timeout, bufsize, path=None, bind=True):
        """Initialize the server.

        Args:
            timeout (int, optional): Socket read timeout. Defaults to TMO_DEF.
            bufsize (int, optional): Socket maximum read size. Defaults to BUF_DEF.
            path (str, optional): Socket's local address. Defaults to None.
            bind (bool, optional): Bind the socket on server creation. Defaults to True.

        """
        self._socket = socket.socket(family=socket.AF_UNIX,
                                     type=  socket.SOCK_DGRAM)

        self._selector = selectors.SelectSelector()
        self._condition = threading.Condition()

        self._shutdown = False

        self.timeout = timeout
        self.bufsize = bufsize
        self.path = path

        if bind:
            self._bind_local()
    
    def path(self):
        """Get the socket's local address.

        Returns:
            str: Socket's local address.
        """
        return self.path

    def serve(self):
        """Serve until a signal is recieved to the process or
        a shutdown request is received.

        *Must be run in another thread.
        """
        self._selector.register(self, selectors.EVENT_READ)
        
        try:
            while not self._shutdown:
                # Blocks until socket is readable
                events = self._selector.select(self.timeout)

                if self._shutdown:
                    break
                
                if events:
                    request = self.get_request()
                    self.handle_request(request)
                    
                self.request_hook()

            # Unblock shutdown thread.
            with self._condition:
                self._condition.notify_all()
        
        except KeyboardInterrupt:
            self._safe_exit()
    
    def shutdown(self):
        """Gracefully shutdown the server and free all associated resources.
        
        *Must be called in a seperate thread from where `serve` is running.
        """
        with self._condition:
            self._shutdown = True
            self._condition.wait() # Block until shutdown completes
            self._safe_exit()

    def get_request(self):
        """Read from the stream.

        `recvfrom` is a blocking call, however this method
        is not intended to block. It's expected that the socket
        is ready to be read from before this method is called.
        """
        return self._socket.recvfrom(self.bufsize)

    def handle_request(self, request):
        """Handle request."""
        pass

    def request_hook(self):
        """Handle events after listening."""
        pass

    def _bind_local(self):
        """Bind the socket to a local directory.
        
        If `path` is None, a directory is automatically
        generated in /tmp/ using the following convention:

        (Inspired by Emacs)

        "/<BASE_PATH>/<BASE_DIR>/<BASE_IDENT>.<hash>", where:

        `hash` - 6 byte hash

        """
        if not self._socket:
            raise Exception("cannot bind a socket that hasn't been created.") # Edit
        
        path = self.path

        if not path:
            dir_path = os.path.join(BASE_PATH, BASE_DIR)

            if not os.path.isdir(dir_path):
                os.mkdir(dir_path)

            ident = f"{BASE_IDENT}.{secrets.token_urlsafe(nbytes=6)}"
            
            self.path = path = os.path.join(dir_path, ident)

        if os.path.exists(path):
            # Try unlinking before binding
            # Ref: https://svnweb.freebsd.org/base/head/usr.sbin/syslogd/syslogd.c?revision=291328&view=markup#l565
            os.unlink(path)

        self._socket.bind(path)
    
    def fileno(self):
        """Return the sockets file descriptor.
        
        Required for use with selectors.SelectSelector().
        """
        return self._socket.fileno()
    
    def _safe_exit(self):
        """Cleanup resources and gracefully exit the server.
        
        `shutdown` does not completely terminate the connection, it sends a FIN call to
        the other socket, which indicates to the other socket to terminate additional writes.
        The file descriptor is NOT released with `shutdown`.

        `close` releases all resources associated with the socket, including the file descriptor.
        """
        self._socket.shutdown(socket.SHUT_RDWR) # Block reading & writing.
        self._socket.close()
        self._cleanup()

    def _cleanup(self):
        """Remove the bound socket file."""
        if self.path:
            os.unlink(self.path)
