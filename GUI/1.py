import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
import random
import threading

# Color definitions
COLORS = {
    "red": "#FF6B6B",
    "green": "#4CAF50",
    "blue": "#2196F3",
    "yellow": "#FFC107",
    "magenta": "#E91E63",
    "cyan": "#00BCD4",
    "white": "#FFFFFF"
}

# MQTT configuration
MQTT_BROKER = "broker.hivemq.com"  # Public broker
MQTT_PORT = 1883
BASE_TOPIC = "jack-chat"
MQTT_USERNAME = "test"  # Can be empty for many public brokers
MQTT_PASSWORD = "test"  # Can be empty for many public brokers

class ChatApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Jack Chat")
        self.master.geometry("800x600")
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Get username and chatroom
        self.username = simpledialog.askstring("Username", "Enter your username:", parent=master)
        if not self.username:
            messagebox.showerror("Error", "Username cannot be empty!")
            master.destroy()
            return
            
        self.chatroom = simpledialog.askstring("Chat Room", "Enter chatroom name to join:", parent=master)
        if not self.chatroom:
            messagebox.showerror("Error", "Chatroom name cannot be empty!")
            master.destroy()
            return
            
        # Choose a color for this user
        color_names = list(COLORS.keys())
        self.my_color = COLORS[random.choice(color_names)]
        
        # Initialize MQTT client
        self.setup_mqtt_client()
        
        # Create GUI elements
        self.create_widgets()
        
        # Connect and subscribe
        self.connect_to_mqtt()
        
    def setup_mqtt_client(self):
        self.client = mqtt.Client()
        self.client.user_data_set({"username": self.username, "chatroom": self.chatroom})
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def create_widgets(self):
        # Chat display area
        self.chat_frame = tk.Frame(self.master)
        self.chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Chat history display with scrollbar
        self.chat_display = scrolledtext.ScrolledText(self.chat_frame, wrap=tk.WORD, bg="#f0f0f0", height=20)
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED)  # Make it read-only
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set(f"Connected as {self.username} in {self.chatroom}")
        self.status_bar = tk.Label(self.master, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Message input area
        self.input_frame = tk.Frame(self.master)
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.message_entry = tk.Entry(self.input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind("<Return>", self.send_message)
        
        self.send_button = tk.Button(self.input_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT)
    
    def connect_to_mqtt(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            # Start mqtt client in a separate thread
            threading.Thread(target=self.client.loop_forever, daemon=True).start()
            
            # Subscribe to the chatroom
            self.chat_topic = f"{BASE_TOPIC}/{self.chatroom}"
            self.client.subscribe(self.chat_topic)
            
            # Send join notification
            join_message = {
                "username": "System",
                "message": f"{self.username} has joined the chat",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            self.client.publish(self.chat_topic, json.dumps(join_message))
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
            self.master.destroy()
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.status_var.set(f"Connected to {MQTT_BROKER} as {self.username} in {self.chatroom}")
        else:
            self.status_var.set(f"Connection failed, code: {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            # Skip messages from self (won't show your own messages twice)
            if payload.get("username") == userdata.get("username") and payload.get("timestamp") == getattr(self, "last_sent_timestamp", None):
                return
                
            # Format message
            timestamp = payload.get("timestamp", "unknown time")
            username = payload.get("username", "unknown user")
            message = payload.get("message", "")
            
            # Determine color for user
            if username == "System":
                tag_name = "system"
            else:
                # Generate a consistent color based on username
                color_names = list(COLORS.keys())
                color_index = sum(ord(c) for c in username) % len(color_names)
                tag_name = f"user_{username}"
                
                # Define tag if it doesn't exist
                try:
                    self.chat_display.tag_config(tag_name, foreground=COLORS[color_names[color_index]])
                except:
                    pass
            
            # Update chat display in the main thread
            self.master.after(0, self.update_chat_display, timestamp, username, message, tag_name)
            
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def update_chat_display(self, timestamp, username, message, tag_name):
        self.chat_display.config(state=tk.NORMAL)
        
        # Auto-scroll if near the bottom
        should_scroll = self.chat_display.yview()[1] > 0.9
        
        # Insert message
        self.chat_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
        self.chat_display.insert(tk.END, f"{username}: ", tag_name)
        self.chat_display.insert(tk.END, f"{message}\n", "message")
        
        # Configure tags if they don't exist yet
        try:
            self.chat_display.tag_config("timestamp", foreground="#777777")
            self.chat_display.tag_config("message", foreground="#000000")
            self.chat_display.tag_config("system", foreground="#FFC107")
        except:
            pass
        
        # Auto-scroll if needed
        if should_scroll:
            self.chat_display.yview_moveto(1.0)
            
        self.chat_display.config(state=tk.DISABLED)
    
    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if not message:
            return
        
        # Clear entry box
        self.message_entry.delete(0, tk.END)
        
        # Handle /exit command
        if message.lower() == "/exit":
            self.on_closing()
            return
        
        # Send message to the chatroom
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.last_sent_timestamp = timestamp
        
        message_payload = {
            "username": self.username,
            "message": message,
            "timestamp": timestamp
        }
        
        # Publish message
        self.client.publish(self.chat_topic, json.dumps(message_payload))
        
    def on_closing(self):
        try:
            # Send leave notification
            leave_message = {
                "username": "System",
                "message": f"{self.username} has left the chat",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            self.client.publish(self.chat_topic, json.dumps(leave_message))
            time.sleep(0.5)  # Give time for message to be sent
            
            # Disconnect
            self.client.disconnect()
        except:
            pass
        
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()