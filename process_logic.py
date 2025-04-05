import rpyc # Import rpyc here if needed for type hints or specific exceptions
import time # For potential delays/debugging

class ProcessLogic:
    """Encapsulates the state and logic of a single simulated process."""
    def __init__(self, process_id, n, base_port):
        self.id = process_id         # 0-based internal ID
        self.n = n
        self.vc = [0] * n            # Vector clock initialized to zeros
        self.history = []
        self.received_messages = []
        self.base_port = base_port   # Needed to connect to other nodes
        self.connections = {}      # Cache for connections to other nodes {target_id: connection}
        print(f"[Node {self.id+1}] Initialized. VC: {self.vc}")

    def _log_event(self, event_type, details=""):
        log_entry = f"{event_type}{details}: VC={','.join(map(str, self.vc))}"
        self.history.append(log_entry)
        print(f"[Node {self.id+1}] {log_entry}") # Log on the node's console

    def _get_connection(self, target_id):
        """Establishes or retrieves an RPyC connection to another node."""
        if target_id == self.id:
            print(f"[Node {self.id+1}] Error: Cannot connect to self.")
            return None
        if target_id in self.connections:
            # Basic check if connection seems alive
            try:
                self.connections[target_id].ping(timeout=0.5) # Short timeout ping
                return self.connections[target_id]
            except (EOFError, rpyc.core.protocol.PingError, TimeoutError):
                 print(f"[Node {self.id+1}] Cached connection to {target_id+1} seems dead. Reconnecting.")
                 del self.connections[target_id] # Remove dead connection
            except Exception as e:
                 print(f"[Node {self.id+1}] Error pinging P{target_id+1}: {e}")
                 # Decide whether to remove or keep trying based on exception type
                 del self.connections[target_id]

        target_port = self.base_port + target_id
        try:
            print(f"[Node {self.id+1}] Attempting to connect to P{target_id+1} on port {target_port}...")
            # Allow public attribute access for simplicity here
            conn = rpyc.connect("localhost", target_port, config={"allow_public_attrs": True})
            self.connections[target_id] = conn
            print(f"[Node {self.id+1}] Successfully connected to P{target_id+1}.")
            return conn
        except ConnectionRefusedError:
            print(f"[Node {self.id+1}] Error: Connection refused by P{target_id+1} (port {target_port}). Is it running?")
            return None
        except Exception as e:
            print(f"[Node {self.id+1}] Error connecting to P{target_id+1} (port {target_port}): {e}")
            return None

    # --- Methods intended to be called locally or via RPyC Service ---

    def local_event(self):
        """Handles a local event: increments own clock component."""
        self.vc[self.id] += 1
        self._log_event("Local")
        # No GUI callback needed here; GUI will poll for state

    def receive_message(self, sender_id, message, sender_vc):
        """Handles receiving a message: updates VC based on sender's VC."""
        print(f"[Node {self.id+1}] Received: '{message}' from P{sender_id+1} with VTS {sender_vc}")
        if not isinstance(sender_vc, list) or len(sender_vc) != self.n:
             print(f"[Node {self.id+1}] Error: Received invalid timestamp from P{sender_id+1}. VC: {sender_vc}")
             return # Or raise an error

        # 1. Update own VC by taking the element-wise maximum
        for k in range(self.n):
            self.vc[k] = max(self.vc[k], sender_vc[k])

        # 2. Increment own clock component
        self.vc[self.id] += 1

        # 3. Log and store received message
        received_msg_display = f"P{sender_id + 1}: {message}"
        self.received_messages.append(received_msg_display)
        self._log_event("Rec", f"({sender_id + 1}, '{message}')")

    def send_message(self, target_process_id, message):
        """Handles sending: increments clock, gets timestamp, calls remote receive."""
        if target_process_id < 0 or target_process_id >= self.n or target_process_id == self.id:
            print(f"[Node {self.id+1}] Error: Invalid target P{target_process_id+1}")
            return False # Indicate failure

        print(f"[Node {self.id+1}] Preparing to send '{message}' to P{target_process_id+1}")

        # 1. Increment own clock
        self.vc[self.id] += 1
        timestamp_to_send = list(self.vc) # Send a copy
        self._log_event("Send", f"({target_process_id + 1}, '{message}') PREPARE") # Log before attempting send

        # 2. Connect to target process via RPyC
        target_conn = self._get_connection(target_process_id)

        if not target_conn:
            print(f"[Node {self.id+1}] Failed to connect to P{target_process_id+1}. Send aborted.")
            # Should we revert the clock increment? Depends on desired semantics.
            # For simplicity here, we leave it incremented as the *intent* to send occurred.
            return False

        # 3. Call the remote 'receive_message' method
        try:
            print(f"[Node {self.id+1}] Calling receive_message on P{target_process_id+1}...")
            # Access the 'root' service object on the other side
            # The actual method called on the target is 'exposed_receive_message'
            target_conn.root.receive_message(self.id, message, timestamp_to_send)
            print(f"[Node {self.id+1}] Successfully called receive_message on P{target_process_id+1}.")
            self._log_event("Send", f"({target_process_id + 1}, '{message}') CONFIRMED")
            return True # Indicate success
        except Exception as e:
            print(f"[Node {self.id+1}] Error calling receive_message on P{target_process_id+1}: {e}")
            # Log the send attempt failure
            self._log_event("Send", f"({target_process_id + 1}, '{message}') FAILED")
            return False # Indicate failure

    def get_state(self):
        """Returns the current state for the GUI."""
        # Return copies to prevent accidental modification via RPyC
        return {
            "vc": list(self.vc),
            "history": list(self.history),
            "received_messages": list(self.received_messages)
        }

    def close_connections(self):
        """Closes outgoing RPyC connections."""
        print(f"[Node {self.id+1}] Closing outgoing connections...")
        for target_id, conn in self.connections.items():
            try:
                conn.close()
                print(f"[Node {self.id+1}] Closed connection to P{target_id+1}.")
            except Exception as e:
                print(f"[Node {self.id+1}] Error closing connection to P{target_id+1}: {e}")
        self.connections = {}

    def shutdown(self):
        """Prepare node for shutdown."""
        self.close_connections()
        print(f"[Node {self.id+1}] Shutdown complete.")
        # Note: The server itself is stopped externally