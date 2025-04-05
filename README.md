# Vector Clock Simulator

a visual tool to show

![Screenshot 2025-04-05 232710](https://github.com/user-attachments/assets/80f3f470-9eb1-4c91-a77b-a6075da81b74)

# 🕒 Vector Clock Simulation

This project is a simulation tool for understanding **vector clocks** in distributed systems. It allows users to visualize and experiment with message-passing and causal relationships across `n` processes (nodes), each with its own interface and terminal session.

## 🔍 Overview

In distributed systems, vector clocks are used to capture **causal ordering** of events. This simulation demonstrates how processes maintain and update their vector clocks through **local events**, **sending**, and **receiving messages**.

## 🚀 Features

- Supports **n independent processes (nodes)**.
- Each node has:
  - A **dedicated terminal** for backend communication.
  - A **separate GUI** for interaction.
- Visual interface to:
  - Trigger **local events**.
  - **Send** messages to other nodes.
  - **Receive** and display incoming messages.
  - View **vector clock updates** in real-time.
  - Track the **event history** of each node.

## 🛠️ How It Works

- **Initialization**: Each node starts with a vector clock `[0, 0, ..., 0]` of size `n`.
- **Local Event**: Increments the node’s own entry in the vector clock.
- **Send Message**: 
  - Increments the sender’s own clock.
  - Sends the message along with the current vector clock.
- **Receive Message**:
  - Merges the incoming vector clock with the local one using element-wise maximum.
  - Increments the local node's own clock entry.
- All actions are logged in the GUI for visibility and learning.

## 📦 Technologies Used

- **Python** for backend and socket communication.
- **Tkinter / CustomTkinter** for GUI interface.
- **Subprocess module** to run and manage backend services for each node.

## 🧪 Example Use Case

1. Launch 3 terminal windows and run a node in each.
2. Start the GUI for each corresponding node.
3. Perform local events and send messages.
4. Observe how vector clocks evolve and capture causality.

![Screenshot 2025-04-05 235136](https://github.com/user-attachments/assets/d9bf1ecb-0b3c-4222-a585-1ebf6a99c6a3)

## ✅ Requirements

- Python 3.x
- `rpyc==6.0.1`
- `customtkinter==5.2.2`

## 📥 Installation (Without virtual environment)

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/vector-clock-simulation.git
   cd vector-clock-simulation
   ```
2. Install required packages using requirements.txt:
      ```bash
   pip install -r requirements.txt
   ```


## 📚 Educational Value

This tool is ideal for students and professionals learning:
- Distributed systems
- Causal consistency
- Event ordering
- Vector clocks in practice

## 📄 License

MIT License

**Happy simulating! 🎉😊**

