import rpyc
from rpyc.utils.server import ThreadedServer # Or ForkingServer
import sys
import signal
from process_logic import ProcessLogic

# Global variable to hold the server instance for signal handling
server_instance = None

class NodeService(rpyc.Service):
    """RPyC Service exposing process logic methods."""

    def __init__(self, process_logic_instance):
        self.logic = process_logic_instance
        # Make logic methods accessible via 'exposed_' prefix
        self.exposed_receive_message = self.logic.receive_message
        self.exposed_local_event = self.logic.local_event
        self.exposed_get_state = self.logic.get_state
        self.exposed_send_message = self.logic.send_message # Expose the combined send
        self.exposed_shutdown = self.logic.shutdown # Allow remote shutdown trigger

    # No need to expose _get_connection or _log_event

    def on_connect(self, conn):
        # Code that runs when a connection is created
        # (from another node or the GUI)
        print(f"[Node {self.logic.id+1} Service] Connection established from {conn._channel.stream.sock.getpeername()}")
        pass

    def on_disconnect(self, conn):
        # Code that runs when a connection is closed
        print(f"[Node {self.logic.id+1} Service] Connection closed from {conn._channel.stream.sock.getpeername()}")
        # Maybe close cached connections related to this peer if needed?
        pass


def signal_handler(sig, frame):
    """Handles Ctrl+C or termination signals gracefully."""
    global server_instance
    print("\nSignal received, shutting down node server...")
    if server_instance:
        # Try to tell logic to clean up connections
        try:
            # Access the service, then the logic instance
             if hasattr(server_instance, 'service_instance') and server_instance.service_instance:
                 server_instance.service_instance.logic.shutdown()
        except Exception as e:
             print(f"Error during logic shutdown: {e}")

        # Close the server
        try:
            server_instance.close() # Closes the listener socket
            print("Server closed.")
        except Exception as e:
            print(f"Error closing server: {e}")
    sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python node.py <node_id> <total_nodes> <base_port>")
        sys.exit(1)

    try:
        node_id = int(sys.argv[1])
        total_nodes = int(sys.argv[2])
        base_port = int(sys.argv[3])
    except ValueError:
        print("Error: node_id, total_nodes, and base_port must be integers.")
        sys.exit(1)

    my_port = base_port + node_id

    print(f"--- Starting Node {node_id+1} (ID: {node_id}) ---")
    print(f"Total Nodes: {total_nodes}")
    print(f"Listening on Port: {my_port}")

    # Create the logic instance
    process_logic = ProcessLogic(node_id, total_nodes, base_port)

    # Create the RPyC service, passing the logic instance
    node_service = NodeService(process_logic)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # Handle termination signal

    # Start the RPyC server
    try:
        # ThreadedServer allows multiple concurrent requests
        server = ThreadedServer(
            node_service,
            port=my_port,
            protocol_config={
                'allow_public_attrs': True, # Allows GUI to call exposed methods
                'sync_request_timeout': 30, # Timeout for requests (seconds)
            }
        )
        server_instance = server # Store globally for signal handler
        server_instance.service_instance = node_service # Store service for shutdown
        print(f"[Node {node_id+1}] Server started successfully.")
        server.start() # This blocks until the server is stopped
    except OSError as e:
         print(f"[Node {node_id+1}] Error starting server on port {my_port}: {e}")
         print("The port might be in use. Try a different base_port or check running processes.")
         sys.exit(1)
    except Exception as e:
        print(f"[Node {node_id+1}] An unexpected error occurred: {e}")
        sys.exit(1)

    # Code here is reached only after server.close() or server.start() fails
    print(f"[Node {node_id+1}] Server loop finished.")