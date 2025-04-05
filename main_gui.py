#  ____                      _      _         _  __        _            _      _
# | __ )   ___   _   _  ____(_)  __| |       | |/ /  ___  | |__    ___ | |__  (_)
# |  _ \  / _ \ | | | ||_  /| | / _` |       | ' /  / _ \ | '_ \  / __|| '_ \ | |
# | |_) || (_) || |_| | / / | || (_| |       | . \ | (_) || |_) || (__ | | | || |
# |____/  \___/  \__,_|/___||_| \__,_| _____ |_|\_\ \___/ |_.__/  \___||_| |_||_|
#                                     |_____|

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import subprocess # To start node processes
import rpyc
import time
import atexit # To clean up processes on exit
import sys # To get python executable path
import os

# --- GUI Implementation (VectorClockApp class) ---
class VectorClockApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vector Clock Simulation (RPyC)")
        self.geometry("850x700") # Increased size slightly
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.processes = [] # Will store subprocess handles
        self.connections = [] # Will store RPyC client connections
        self.n_processes = 0
        self.base_port = 18861 # Starting port number (choose one unlikely to be in use)
        self.process_tabs = {}
        self.current_process_index = 0

        # --- Top Frame ---
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=10, padx=10, fill="x")
        # ... (Label, Entry for N, Start, Exit buttons - same as before) ...
        self.label_n = ctk.CTkLabel(self.config_frame, text="Provide the number of processes:")
        self.label_n.pack(side=tk.LEFT, padx=5)
        self.entry_n = ctk.CTkEntry(self.config_frame, width=50)
        self.entry_n.pack(side=tk.LEFT, padx=5)
        self.entry_n.insert(0, "3")
        self.button_start = ctk.CTkButton(self.config_frame, text="Start", command=self.start_simulation)
        self.button_start.pack(side=tk.LEFT, padx=5)
        self.button_exit = ctk.CTkButton(self.config_frame, text="Exit", command=self.shutdown_app) # Use shutdown_app
        self.button_exit.pack(side=tk.LEFT, padx=5)

        # --- Tab View ---
        self.tab_view = None

        # --- Status Bar ---
        self.status_bar = ctk.CTkLabel(self, text="Enter N and click Start.", anchor="w")
        self.status_bar.pack(side=tk.BOTTOM, fill="x", padx=10, pady=5)

        # --- Register cleanup ---
        atexit.register(self.cleanup_processes) # Ensure processes are terminated on exit

    def update_status(self, message):
         # Schedule the update in the main thread
        self.after(0, lambda: self.status_bar.configure(text=message))

    def show_error(self, title, message):
        # Ensure messagebox runs in the main thread
        self.after(0, lambda: messagebox.showerror(title, message))

    def start_simulation(self):
        """Starts the node processes and connects to them."""
        try:
            n = int(self.entry_n.get())
            if n <= 1:
                raise ValueError("Number of processes must be > 1.")
            self.n_processes = n
        except ValueError as e:
            self.show_error("Invalid Input", f"Enter integer > 1.\nError: {e}")
            return

        self.update_status("Starting simulation...")
        self.cleanup_processes() # Clean up any previous run first

        # --- Start Node Processes ---
        python_executable = sys.executable # Path to current python interpreter
        node_script = os.path.join(os.path.dirname(__file__), "node.py") # Path to node.py

        if not os.path.exists(node_script):
             self.show_error("File Not Found", f"Cannot find node script: {node_script}")
             self.update_status("Error: node.py not found.")
             return

        for i in range(self.n_processes):
            port = self.base_port + i
            cmd = [
                python_executable,
                node_script,
                str(i),           # node_id
                str(self.n_processes), # total_nodes
                str(self.base_port)   # base_port
            ]
            try:
                print(f"Starting process {i+1} with command: {' '.join(cmd)}")
                # Use CREATE_NEW_CONSOLE on Windows to see node output easily
                # Use start_new_session=True on Linux/macOS if needed
                creationflags = 0
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NEW_CONSOLE

                proc = subprocess.Popen(cmd, creationflags=creationflags) #, start_new_session=True)
                self.processes.append(proc)
            except Exception as e:
                self.show_error("Process Error", f"Failed to start node P{i+1}: {e}")
                self.cleanup_processes() # Stop any already started
                self.update_status(f"Failed to start P{i+1}.")
                return

        # --- Wait briefly and Connect via RPyC ---
        self.update_status("Waiting for nodes to start...")
        self.connections = [None] * self.n_processes
        time.sleep(2.0 + self.n_processes * 0.3) # Give servers time to start (adjust if needed)

        connection_successful = True
        for i in range(self.n_processes):
            port = self.base_port + i
            try:
                self.update_status(f"Connecting to P{i+1} on port {port}...")
                # Connect with timeout and public attrs allowed
                conn = rpyc.connect("localhost", port, config={"allow_public_attrs": True, "sync_request_timeout": 10})
                # Optional: Ping to verify
                conn.ping(timeout=2)
                self.connections[i] = conn
                print(f"GUI: Successfully connected to P{i+1}")
            except (ConnectionRefusedError, TimeoutError, EOFError, rpyc.core.protocol.PingError) as e:
                self.show_error("Connection Error", f"Failed to connect to P{i+1} on port {port}.\nIs it running?\nError: {e}")
                self.cleanup_processes()
                self.update_status(f"Connection failed to P{i+1}. Simulation aborted.")
                connection_successful = False
                break # Stop trying to connect
            except Exception as e:
                self.show_error("Connection Error", f"Unexpected error connecting to P{i+1} on port {port}: {e}")
                self.cleanup_processes()
                self.update_status(f"Connection failed to P{i+1}. Simulation aborted.")
                connection_successful = False
                break # Stop trying to connect

        if not connection_successful:
            return # Abort if any connection failed

        # --- Create GUI Tabs (if connections successful) ---
        if self.tab_view:
            self.tab_view.destroy()
        self.process_tabs = {}

        self.tab_view = ctk.CTkTabview(self, command=self.on_tab_change)
        self.tab_view.pack(expand=True, fill="both", padx=10, pady=5)

        for i in range(self.n_processes):
            self._create_tab_widgets(i) # Create widgets for process i

        # --- Initial UI Update ---
        if self.n_processes > 0:
            self.tab_view.set(f"P1")
            # Update all tabs initially
            for i in range(self.n_processes):
                self.update_ui_for_process(i) # Fetch initial state
            self.update_status(f"Simulation running with {self.n_processes} processes. View: P1")

    def _create_tab_widgets(self, process_id):
        """Helper to create widgets for a specific tab."""
        process_label = f"P{process_id + 1}"
        tab = self.tab_view.add(process_label)
        self.process_tabs[process_id] = {}

        # --- Layout frames (same as before) ---
        tab_frame = ctk.CTkFrame(tab, fg_color="transparent")
        tab_frame.pack(expand=True, fill="both", padx=5, pady=5)
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_columnconfigure(1, weight=2)
        tab_frame.grid_rowconfigure(1, weight=1)
        control_frame = ctk.CTkFrame(tab_frame)
        control_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew", rowspan=2)
        display_frame = ctk.CTkFrame(tab_frame)
        display_frame.grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="nsew")
        display_frame.grid_rowconfigure(1, weight=1)
        display_frame.grid_rowconfigure(3, weight=1)
        display_frame.grid_columnconfigure(0, weight=1)

        # --- Control Widgets ---
        btn_local = ctk.CTkButton(control_frame, text="Local Event",
                                  command=lambda p_id=process_id: self.handle_local_event(p_id))
        btn_local.pack(pady=10, padx=10, fill="x")
        send_frame = ctk.CTkFrame(control_frame)
        send_frame.pack(pady=10, padx=10, fill="x")
        lbl_message = ctk.CTkLabel(send_frame, text="Message:")
        lbl_message.pack(pady=(5,0))
        entry_message = ctk.CTkEntry(send_frame, placeholder_text="Enter message...")
        entry_message.pack(pady=5, padx=5, fill="x")
        lbl_target = ctk.CTkLabel(send_frame, text="Send to:")
        lbl_target.pack(pady=(5,0))
        target_options = [f"P{j+1}" for j in range(self.n_processes) if j != process_id]
        combo_target = ctk.CTkComboBox(send_frame, values=target_options, state="readonly")
        if target_options: combo_target.set(target_options[0])
        else: combo_target.set("N/A")
        combo_target.pack(pady=5, padx=5, fill="x")
        btn_send = ctk.CTkButton(send_frame, text="Send",
                                 command=lambda p_id=process_id: self.handle_send(p_id))
        btn_send.pack(pady=10, padx=5, fill="x")
        vc_frame = ctk.CTkFrame(control_frame)
        vc_frame.pack(pady=10, padx=10, fill="x")
        lbl_vc = ctk.CTkLabel(vc_frame, text=f"Vector Clock (VC{process_id+1}):")
        lbl_vc.pack()
        txt_vc = ctk.CTkTextbox(vc_frame, height=max(80, self.n_processes * 20), width=100, state="disabled", wrap="none", activate_scrollbars=False)
        txt_vc.pack(pady=5, padx=5, fill="x")

        # --- Display Widgets ---
        lbl_received = ctk.CTkLabel(display_frame, text="Received Messages:")
        lbl_received.grid(row=0, column=0, sticky="w", padx=5, pady=(5,0))
        txt_received = ctk.CTkTextbox(display_frame, height=100, state="disabled", wrap="word")
        txt_received.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        lbl_history = ctk.CTkLabel(display_frame, text=f"History of P{process_id + 1}:")
        lbl_history.grid(row=2, column=0, sticky="w", padx=5, pady=(10,0))
        txt_history = ctk.CTkTextbox(display_frame, state="disabled", wrap="none")
        txt_history.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)

        # --- Store Widget References ---
        self.process_tabs[process_id] = {
            "message_entry": entry_message,
            "target_combo": combo_target,
            "vc_text": txt_vc,
            "received_text": txt_received,
            "history_text": txt_history,
        }

    def on_tab_change(self):
        """Update status when tab changes."""
        if not self.tab_view: return
        selected_tab_name = self.tab_view.get()
        try:
            self.current_process_index = int(selected_tab_name[1:]) - 1
            self.update_status(f"Current view: {selected_tab_name}")
            # Optional: Immediately refresh the view of the selected tab
            # self.update_ui_for_process(self.current_process_index)
        except (IndexError, ValueError, TypeError):
             self.update_status(f"Error identifying tab: {selected_tab_name}")

    def update_ui_for_process(self, process_id):
        """Fetches state via RPyC and updates the GUI for a specific process."""
        if process_id < 0 or process_id >= len(self.connections) or not self.connections[process_id]:
            print(f"GUI: No connection or invalid ID {process_id+1} for UI update.")
            # Optionally disable controls for this tab or show an error state
            return

        conn = self.connections[process_id]
        widgets = self.process_tabs.get(process_id)
        if not widgets:
            print(f"GUI: Widgets not found for process {process_id+1}.")
            return

        try:
            # Call the remote method to get the current state
            state = conn.root.get_state() # This is the RPyC call

            vc = state.get("vc", [])
            history = state.get("history", [])
            received_messages = state.get("received_messages", [])

            # --- Update VC Display ---
            vc_text_widget = widgets.get("vc_text")
            if vc_text_widget:
                vc_text_widget.configure(state="normal")
                vc_text_widget.delete("1.0", tk.END)
                vc_str = "\n".join([f"P{i+1}: {val}" for i, val in enumerate(vc)])
                vc_text_widget.insert("1.0", vc_str)
                vc_text_widget.configure(state="disabled")

            # --- Update History Display ---
            history_text_widget = widgets.get("history_text")
            if history_text_widget:
                history_text_widget.configure(state="normal")
                history_text_widget.delete("1.0", tk.END)
                history_text_widget.insert("1.0", "\n".join(history))
                history_text_widget.see(tk.END)
                history_text_widget.configure(state="disabled")

            # --- Update Received Messages Display ---
            received_text_widget = widgets.get("received_text")
            if received_text_widget:
                received_text_widget.configure(state="normal")
                received_text_widget.delete("1.0", tk.END)
                received_text_widget.insert("1.0", "\n".join(received_messages))
                received_text_widget.see(tk.END)
                received_text_widget.configure(state="disabled")

        except (EOFError, ConnectionResetError, BrokenPipeError, TimeoutError) as e:
            self.show_error(f"RPyC Error P{process_id+1}", f"Connection lost or timed out.\nP{process_id+1} might have crashed.\nError: {e}")
            self.update_status(f"Error communicating with P{process_id+1}. Refresh may fail.")
            # Mark connection as potentially dead?
            self.connections[process_id] = None # Or attempt reconnect later
            # Optionally disable buttons for this tab
        except Exception as e:
            self.show_error(f"RPyC Error P{process_id+1}", f"Failed to get state from P{process_id+1}.\nError: {e}")
            self.update_status(f"Error getting state from P{process_id+1}.")


    def handle_local_event(self, process_id):
        """Sends local event command via RPyC."""
        if process_id < 0 or process_id >= len(self.connections) or not self.connections[process_id]:
            self.show_error("Action Error", f"Cannot perform local event: No connection to P{process_id+1}.")
            return

        conn = self.connections[process_id]
        try:
            self.update_status(f"Sending Local Event command to P{process_id+1}...")
            conn.root.local_event() # RPyC call
            self.update_status(f"Local Event triggered on P{process_id+1}. Updating UI...")
            # Update UI after the action
            self.update_ui_for_process(process_id)
            self.update_status(f"P{process_id + 1} performed local event. View: P{self.current_process_index + 1}")

        except (EOFError, ConnectionResetError, BrokenPipeError, TimeoutError) as e:
             self.show_error(f"RPyC Error P{process_id+1}", f"Connection lost sending local event.\nError: {e}")
             self.connections[process_id] = None
        except Exception as e:
            self.show_error(f"RPyC Error P{process_id+1}", f"Error sending local event command.\nError: {e}")


    def handle_send(self, sender_process_id):
        """Sends 'send message' command via RPyC to the SENDER node."""
        if sender_process_id < 0 or sender_process_id >= len(self.connections) or not self.connections[sender_process_id]:
            self.show_error("Action Error", f"Cannot send: No connection to sender P{sender_process_id+1}.")
            return

        widgets = self.process_tabs.get(sender_process_id)
        if not widgets: return # Should not happen

        message = widgets["message_entry"].get()
        target_str = widgets["target_combo"].get()

        if not message:
            self.show_error("Send Error", "Message cannot be empty.")
            return
        if not target_str or target_str == "N/A":
            self.show_error("Send Error", "Please select a valid target process.")
            return

        try:
            target_process_id = int(target_str[1:]) - 1
            if not (0 <= target_process_id < self.n_processes):
                raise ValueError("Target ID out of range")
        except (IndexError, ValueError) as e:
            self.show_error("Send Error", f"Invalid target format: {target_str}\n{e}")
            return

        sender_conn = self.connections[sender_process_id]
        try:
            self.update_status(f"Sending Send command from P{sender_process_id+1} to P{target_process_id+1}...")
            # RPyC call to the SENDER's service
            success = sender_conn.root.send_message(target_process_id, message)

            if success:
                self.update_status(f"Send successful: P{sender_process_id+1} -> P{target_process_id+1}. Updating UIs...")
                widgets["message_entry"].delete(0, tk.END) # Clear message box on success
                # Update both sender and receiver UIs
                self.update_ui_for_process(sender_process_id)
                self.update_ui_for_process(target_process_id)
                self.update_status(f"P{sender_process_id+1} sent to P{target_process_id+1}. View: P{self.current_process_index + 1}")
            else:
                self.show_error("Send Failed", f"P{sender_process_id+1} reported failure sending to P{target_process_id+1}. Check node console.")
                self.update_status(f"Send failed: P{sender_process_id+1} -> P{target_process_id+1}. Updating sender UI...")
                # Still update sender UI as its clock might have changed even on failure
                self.update_ui_for_process(sender_process_id)


        except (EOFError, ConnectionResetError, BrokenPipeError, TimeoutError) as e:
             self.show_error(f"RPyC Error P{sender_process_id+1}", f"Connection lost during send operation.\nError: {e}")
             self.connections[sender_process_id] = None
             # We don't know if the receiver got it, might need to refresh receiver too if possible
             self.update_ui_for_process(target_process_id)
        except Exception as e:
            self.show_error(f"RPyC Error P{sender_process_id+1}", f"Error during send command.\nError: {e}")
            # Refresh sender UI
            self.update_ui_for_process(sender_process_id)


    def cleanup_processes(self):
        """Terminate running node processes and close connections."""
        print("GUI: Cleaning up connections and processes...")
        # Close RPyC connections
        for i, conn in enumerate(self.connections):
            if conn and not conn.closed:
                 try:
                    # Optionally try to tell node to shut down gracefully
                    # conn.root.shutdown()
                    conn.close()
                    print(f"GUI: Closed connection to P{i+1}")
                 except Exception as e:
                    print(f"GUI: Error closing connection to P{i+1}: {e}")
        self.connections = []

        # Terminate subprocesses
        for i, proc in enumerate(self.processes):
             if proc and proc.poll() is None: # Check if process is still running
                 try:
                    proc.terminate() # Send SIGTERM
                    proc.wait(timeout=1.0) # Wait briefly for termination
                    print(f"GUI: Terminated process P{i+1} (PID: {proc.pid})")
                 except subprocess.TimeoutExpired:
                    print(f"GUI: Process P{i+1} (PID: {proc.pid}) did not terminate quickly, killing.")
                    proc.kill() # Force kill if terminate fails
                 except Exception as e:
                     print(f"GUI: Error terminating process P{i+1}: {e}")
        self.processes = []
        print("GUI: Cleanup finished.")


    def shutdown_app(self):
        """Cleanup and exit the application."""
        self.cleanup_processes()
        self.destroy() # Close the GUI window


# --- Run the Application ---
if __name__ == "__main__":
    # Ensure the logic file exists
    logic_file = os.path.join(os.path.dirname(__file__), "process_logic.py")
    if not os.path.exists(logic_file):
         print(f"ERROR: Cannot find required file '{logic_file}'. Make sure it's in the same directory.")
         sys.exit(1)

    app = VectorClockApp()
    app.mainloop()