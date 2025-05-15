import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, colorchooser, font
import paho.mqtt.client as mqtt
import json, time, threading, os, pickle
from datetime import datetime
import random

# Color and MQTT configurations
COLORS = {
    "red": "#FF6B6B", "green": "#4AFF65", "blue": "#63B8FF", 
    "yellow": "#FFF07C", "magenta": "#FF5DC8", "cyan": "#00FFFF", "white": "#FFFFFF"
}

MQTT_BROKER, MQTT_PORT = "broker.hivemq.com", 1883
BASE_TOPIC = "jack-chat"
MQTT_USERNAME, MQTT_PASSWORD = "test", "test"
INVITATIONS_FILE = os.path.join(os.path.expanduser("~"), ".jack_chat_invitations.json")
CHATROOMS_FILE = os.path.join(os.path.expanduser("~"), ".jack_chat_rooms.json")

class ChatApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Jack Chat")
        self.master.geometry("900x600")
        self.master.configure(bg="#1E1E1E")
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.menu_visible = False
        
        # Set up initial variables
        self.get_user_info()
        
        # Initialize app components
        self.setup_mqtt_client()
        self.create_widgets()
        self.connect_to_mqtt()
        self.check_pending_invitations()
        
        # Initialize chatroom history
        self.user_chatrooms = self.load_user_chatrooms()
        self.add_chatroom_to_history(self.chatroom)
    
    def get_user_info(self):
        # Get username and chatroom
        self.username = simpledialog.askstring("Username", "Enter your username:", parent=self.master)
        if not self.username:
            messagebox.showerror("Error", "Username cannot be empty!")
            self.master.destroy()
            return
            
        self.chatroom = simpledialog.askstring("Chat Room", "Enter chatroom name to join:", parent=self.master)
        if not self.chatroom:
            messagebox.showerror("Error", "Chatroom name cannot be empty!")
            self.master.destroy()
            return
            
        # Choose a color for this user
        color_names = list(COLORS.keys())
        color_names.remove("white")  # Don't use white
        self.my_color_name = random.choice(color_names)
        self.my_color = COLORS[self.my_color_name]
    
    def setup_mqtt_client(self):
        self.client = mqtt.Client()
        self.client.user_data_set({"username": self.username, "chatroom": self.chatroom})
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.personal_topic = f"{BASE_TOPIC}/invites/{self.username}"
        self.chat_topic = f"{BASE_TOPIC}/{self.chatroom}"
        
    def create_widgets(self):
        # Define fonts
        self.timestamp_font = font.Font(size=10, weight="bold")
        self.username_font = font.Font(size=11, weight="bold")
        self.message_font = font.Font(size=10)
        self.button_font = font.Font(size=10, weight="bold")
        
        # Create layout frames
        self.main_container = tk.Frame(self.master, bg="#1E1E1E")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        self.left_frame = tk.Frame(self.main_container, bg="#1E1E1E")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.right_panel = tk.Frame(self.main_container, bg="#1E1E1E", width=50)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create menu toggle button
        self.menu_button = tk.Button(
            self.right_panel, text="⚙️", font=("Arial", 16), bg="#333333", fg="#FFFFFF",
            activebackground="#444444", relief=tk.FLAT, command=self.toggle_menu
        )
        self.menu_button.pack(side=tk.TOP, pady=10, padx=5)
        
        # Create collapsible menu panel
        self.create_menu_panel()
        
        # Create chat area
        self.create_chat_area()
    
    def create_menu_panel(self):
        self.menu_panel = tk.Frame(self.main_container, bg="#272727", width=200)
        
        # Add settings title
        tk.Label(
            self.menu_panel, text="SETTINGS", bg="#272727", fg="#FFFFFF",
            font=("Arial", 14, "bold"), padx=10, pady=10
        ).pack(fill=tk.X)
        
        # Add separator
        tk.Frame(self.menu_panel, height=2, bg="#444444").pack(fill=tk.X, padx=10)
        
        # Define button styles and create buttons
        button_configs = {
            "Change Username": ("#4CAF50", "#FFFFFF", self.change_username),
            "Change Color": ("#2196F3", "#FFFFFF", self.change_color),
            "Chatrooms": ("#FF9800", "#FFFFFF", self.show_chatrooms_manager),  # Changed from "Change Chatroom"
            "Add User": ("#9C27B0", "#FFFFFF", self.add_user)
        }
        
        for text, (bg, fg, cmd) in button_configs.items():
            self.create_settings_button(text, cmd, (bg, fg))
        
        # Add separator
        tk.Frame(self.menu_panel, height=2, bg="#444444").pack(fill=tk.X, padx=10, pady=10)
        
        # Add exit button
        tk.Button(
            self.menu_panel, text="Exit Chat", command=self.on_closing,
            bg="#FF4444", fg="#FFFFFF", font=self.button_font,
            relief=tk.FLAT, padx=10, pady=8
        ).pack(fill=tk.X, padx=10, pady=10, side=tk.BOTTOM)
    
    def load_user_chatrooms(self):
        """Load user's chatroom history from JSON file"""
        try:
            if os.path.exists(CHATROOMS_FILE):
                with open(CHATROOMS_FILE, 'r') as f:
                    try:
                        chatrooms_data = json.load(f)
                        if self.username in chatrooms_data:
                            return chatrooms_data[self.username]
                    except json.JSONDecodeError:
                        # Handle case of empty or invalid JSON file
                        pass
        except Exception as e:
            print(f"Error loading chatrooms: {e}")
            # If JSON fails, try the legacy pickle format as fallback
            try:
                old_file = os.path.join(os.path.expanduser("~"), ".jack_chat_rooms.pkl")
                if os.path.exists(old_file):
                    with open(old_file, 'rb') as f:
                        chatrooms_data = pickle.load(f)
                        if self.username in chatrooms_data:
                            return chatrooms_data[self.username]
            except:
                pass
        
        return []  # Default to empty list if no history or error
    
    def save_user_chatrooms(self):
        """Save user's chatroom history to JSON file"""
        try:
            chatrooms_data = {}
            if os.path.exists(CHATROOMS_FILE):
                with open(CHATROOMS_FILE, 'r') as f:
                    try:
                        chatrooms_data = json.load(f)
                    except json.JSONDecodeError:
                        # Handle case of empty or invalid JSON file
                        pass
            
            chatrooms_data[self.username] = self.user_chatrooms
            
            with open(CHATROOMS_FILE, 'w') as f:
                json.dump(chatrooms_data, f, indent=4)
        except Exception as e:
            print(f"Error saving chatrooms: {e}")
    
    def add_chatroom_to_history(self, chatroom):
        """Add a chatroom to user's history if not already present"""
        if chatroom not in self.user_chatrooms:
            self.user_chatrooms.append(chatroom)
            self.save_user_chatrooms()
    
    def remove_chatroom_from_history(self, chatroom):
        """Remove a chatroom from user's history"""
        if chatroom in self.user_chatrooms:
            self.user_chatrooms.remove(chatroom)
            self.save_user_chatrooms()
    
    def show_chatrooms_manager(self):
        """Open the chatrooms manager window"""
        # Close the menu panel to avoid cluttering the UI
        if self.menu_visible:
            self.toggle_menu()
        
        # Create chatroom manager window
        chatrooms_window = tk.Toplevel(self.master)
        chatrooms_window.title("Manage Chatrooms")
        chatrooms_window.geometry("500x400")
        chatrooms_window.configure(bg="#1E1E1E")
        
        # Create frame for the content
        content_frame = tk.Frame(chatrooms_window, bg="#1E1E1E")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Add title label
        tk.Label(
            content_frame, 
            text="Your Chatrooms", 
            font=("Arial", 14, "bold"),
            bg="#1E1E1E", 
            fg="#FFFFFF"
        ).pack(pady=(0, 10))
        
        # Current chatroom indicator
        tk.Label(
            content_frame,
            text=f"You are currently in: {self.chatroom}",
            font=("Arial", 11, "italic"),
            bg="#1E1E1E",
            fg="#AAAAAA"
        ).pack(pady=(0, 10))
        
        # Create scrollable frame for chatrooms list
        list_container = tk.Frame(content_frame, bg="#1E1E1E")
        list_container.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Add scrollbar
        scrollbar = tk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create canvas for scrolling
        canvas = tk.Canvas(list_container, bg="#1E1E1E", highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        scrollbar.config(command=canvas.yview)
        canvas.config(yscrollcommand=scrollbar.set)
        
        # Create frame for chatroom entries
        chatrooms_list = tk.Frame(canvas, bg="#1E1E1E")
        chatrooms_list.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Add chatrooms list to canvas
        canvas.create_window((0, 0), window=chatrooms_list, anchor="nw", width=canvas.winfo_reqwidth())
        
        # Populate the list with chatrooms
        for room in self.user_chatrooms:
            room_frame = tk.Frame(chatrooms_list, bg="#242424", padx=10, pady=8)
            room_frame.pack(fill=tk.X, pady=2)
            
            # Room name 
            tk.Label(
                room_frame,
                text=room,
                font=("Arial", 11),
                bg="#242424",
                fg="#FFFFFF" if room != self.chatroom else "#4AFF65",
                width=20,
                anchor="w"
            ).pack(side=tk.LEFT, padx=5)
            
            # Join button (disabled for current room)
            join_btn = tk.Button(
                room_frame,
                text="Join",
                bg="#2196F3",
                fg="#FFFFFF",
                command=lambda r=room: self.join_chatroom(r, chatrooms_window),
                state=tk.DISABLED if room == self.chatroom else tk.NORMAL
            )
            join_btn.pack(side=tk.LEFT, padx=5)
            
            # Remove button (disabled for current room)
            remove_btn = tk.Button(
                room_frame,
                text="Remove",
                bg="#FF5722",
                fg="#FFFFFF",
                command=lambda r=room: self.confirm_remove_chatroom(r, chatrooms_window),
                state=tk.DISABLED if room == self.chatroom else tk.NORMAL
            )
            remove_btn.pack(side=tk.LEFT, padx=5)
        
        # Add buttons for new chatroom
        buttons_frame = tk.Frame(content_frame, bg="#1E1E1E")
        buttons_frame.pack(fill=tk.X, pady=15)
        
        # New chatroom button
        tk.Button(
            buttons_frame,
            text="Add New Chatroom",
            bg="#4CAF50",
            fg="#FFFFFF",
            command=lambda: self.add_new_chatroom(chatrooms_window)
        ).pack(side=tk.LEFT, padx=5)
        
        # Close button
        tk.Button(
            buttons_frame,
            text="Close",
            bg="#555555",
            fg="#FFFFFF",
            command=chatrooms_window.destroy
        ).pack(side=tk.RIGHT, padx=5)
    
    def join_chatroom(self, chatroom, window):
        """Join an existing chatroom from the manager"""
        if chatroom == self.chatroom:
            return  # Already in this room
            
        # Change to the selected chatroom
        self.change_to_chatroom(chatroom)
        window.destroy()  # Close the chatrooms manager
    
    def add_new_chatroom(self, parent_window):
        """Add a new chatroom"""
        new_room = simpledialog.askstring("New Chatroom", 
                                         "Enter name for the new chatroom:", 
                                         parent=parent_window)
        
        if not new_room or not new_room.strip():
            return
            
        # Add to history
        self.add_chatroom_to_history(new_room)
        
        # Ask if user wants to join the new room
        if messagebox.askyesno("Join Room", 
                              f"Chatroom '{new_room}' has been added to your list.\nWould you like to join it now?",
                              parent=parent_window):
            self.change_to_chatroom(new_room)
            parent_window.destroy()  # Close the chatrooms manager
        else:
            # Just refresh the chatrooms manager
            parent_window.destroy()
            self.show_chatrooms_manager()
    
    def confirm_remove_chatroom(self, chatroom, parent_window):
        """Confirm before removing a chatroom"""
        if chatroom == self.chatroom:
            messagebox.showinfo("Cannot Remove", 
                              "You cannot remove the chatroom you're currently in.",
                              parent=parent_window)
            return
            
        if messagebox.askyesno("Confirm Removal", 
                              f"Are you sure you want to remove '{chatroom}' from your list?",
                              parent=parent_window):
            self.remove_chatroom_from_history(chatroom)
            # Refresh the chatrooms manager
            parent_window.destroy()
            self.show_chatrooms_manager()
    
    def create_chat_area(self):
        # Chat display area
        self.chat_frame = tk.Frame(self.left_frame, bg="#1E1E1E")
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        
        # Chat history display with scrollbar
        self.chat_display = scrolledtext.ScrolledText(
            self.chat_frame, wrap=tk.WORD, bg="#121212", fg="#FFFFFF",
            height=20, insertbackground="white", font=self.message_font
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set(f"Connected as {self.username} in {self.chatroom}")
        self.status_bar = tk.Label(
            self.left_frame, textvariable=self.status_var, bd=1, relief=tk.SUNKEN,
            anchor=tk.W, bg="#333333", fg="#AAAAAA"
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Message input area
        self.input_frame = tk.Frame(self.left_frame, bg="#1E1E1E")
        self.input_frame.pack(fill=tk.X, pady=10)
        
        self.message_entry = tk.Entry(
            self.input_frame, bg="#333333", fg="#FFFFFF",
            insertbackground="white", font=("Arial", 11)
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind("<Return>", self.send_message)
        
        self.send_button = tk.Button(
            self.input_frame, text="Send", command=self.send_message,
            bg="#444444", fg="#FFFFFF", activebackground="#666666"
        )
        self.send_button.pack(side=tk.RIGHT, padx=5)
    
    def toggle_menu(self):
        if self.menu_visible:
            self.menu_panel.pack_forget()
            self.menu_visible = False
        else:
            self.menu_panel.pack(side=tk.RIGHT, fill=tk.Y, before=self.right_panel)
            self.menu_visible = True
    
    def create_settings_button(self, text, command, colors):
        bg_color, fg_color = colors
        button = tk.Button(
            self.menu_panel, text=text, command=command, bg=bg_color, fg=fg_color,
            activebackground=self.lighten_color(bg_color), activeforeground=fg_color,
            font=self.button_font, relief=tk.FLAT, padx=10, pady=8, anchor="w", width=16
        )
        button.pack(fill=tk.X, padx=10, pady=5)
        
        # Add hover effect
        button.bind("<Enter>", lambda e, b=button, c=bg_color: b.config(bg=self.lighten_color(c)))
        button.bind("<Leave>", lambda e, b=button, c=bg_color: b.config(bg=c))
        
        return button
    
    def lighten_color(self, hex_color):
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = [min(255, int(c * 1.2)) for c in (r, g, b)]
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def send_system_message(self, message):
        """Utility function to send system messages"""
        msg = {
            "username": "System",
            "message": message,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.client.publish(self.chat_topic, json.dumps(msg))
    
    def add_user(self):
        user_to_add = simpledialog.askstring("Add User", 
                                           "Enter the username of the person you want to invite:", 
                                           parent=self.master)
        if user_to_add and user_to_add.strip():
            # Create and send invitation
            timestamp = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
            
            # System notification to chatroom
            self.send_system_message(f"{self.username} has invited {user_to_add} to join this chatroom")
            
            # Private invitation data
            personal_invite = {
                "type": "invitation",
                "from": self.username,
                "chatroom": self.chatroom,
                "timestamp": timestamp
            }
            
            # Send and store invitation
            private_topic = f"{BASE_TOPIC}/invites/{user_to_add}"
            self.client.publish(private_topic, json.dumps(personal_invite))
            self.store_invitation(user_to_add, personal_invite)
            
            messagebox.showinfo("Invitation Sent", f"An invitation has been sent to {user_to_add}.")
    
    def change_username(self):
        new_username = simpledialog.askstring("Change Username", 
                                             f"Current username: {self.username}\nEnter new username:", 
                                             parent=self.master)
        if new_username and new_username.strip():
            # Notify about name change
            self.send_system_message(f"{self.username} has changed their name to {new_username}")
            
            # Update MQTT subscriptions
            self.client.unsubscribe(self.personal_topic)
            self.username = new_username
            self.client.user_data_set({"username": self.username, "chatroom": self.chatroom})
            self.personal_topic = f"{BASE_TOPIC}/invites/{self.username}"
            self.client.subscribe(self.personal_topic)
            
            # Update UI
            self.status_var.set(f"Connected as {self.username} in {self.chatroom}")
    
    def change_to_chatroom(self, new_chatroom, via_invitation=False):
        # Leave current chatroom
        self.send_system_message(f"{self.username} has left the chat")
        self.client.unsubscribe(self.chat_topic)
        
        # Join new chatroom
        self.chatroom = new_chatroom
        self.client.user_data_set({"username": self.username, "chatroom": self.chatroom})
        self.chat_topic = f"{BASE_TOPIC}/{self.chatroom}"
        self.client.subscribe(self.chat_topic)
        
        # Add to chatroom history
        self.add_chatroom_to_history(new_chatroom)
        
        # Send join notification
        join_msg = f"{self.username} has joined the chat"
        if via_invitation:
            join_msg += " in response to an invitation"
        self.send_system_message(join_msg)
        
        # Update UI
        self.status_var.set(f"Connected as {self.username} in {self.chatroom}")
        
        # Clear chat display
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        join_text = f"--- You have joined {self.chatroom}"
        if via_invitation:
            join_text += " via invitation"
        self.chat_display.insert(tk.END, join_text + " ---\n", "system")
        self.chat_display.config(state=tk.DISABLED)
    
    def change_color(self):
        color_window = tk.Toplevel(self.master)
        color_window.title("Select Your Color")
        color_window.geometry("300x200")
        color_window.configure(bg="#1E1E1E")
        
        # Add color selection interface
        colors = {
            "Red": "#FF6B6B", "Green": "#4AFF65", "Blue": "#63B8FF",
            "Yellow": "#FFF07C", "Magenta": "#FF5DC8", "Cyan": "#00FFFF"
        }
        
        tk.Label(
            color_window, text="Choose your username color:", 
            bg="#1E1E1E", fg="#FFFFFF", font=("Arial", 12)
        ).pack(pady=10)
        
        button_frame = tk.Frame(color_window, bg="#1E1E1E")
        button_frame.pack(pady=10)
        
        for i, (color_name, color_code) in enumerate(colors.items()):
            btn = tk.Button(
                button_frame, text=color_name, bg=color_code,
                fg="#000000" if color_name in ["Yellow", "Cyan", "Green"] else "#FFFFFF",
                width=8, command=lambda c=color_code, n=color_name.lower(): self.set_color(c, n, color_window)
            )
            row, col = divmod(i, 3)
            btn.grid(row=row, column=col, padx=5, pady=5)
        
        tk.Button(
            color_window, text="Custom Color", command=lambda: self.pick_custom_color(color_window),
            bg="#444444", fg="#FFFFFF"
        ).pack(pady=10)
    
    def pick_custom_color(self, window):
        color_code = colorchooser.askcolor(title="Choose a color")
        if color_code and color_code[1]:
            self.set_color(color_code[1], "custom", window)
    
    def set_color(self, color_code, color_name, window):
        self.my_color = color_code
        self.my_color_name = color_name
        
        self.send_system_message(f"{self.username} has changed their color to {color_name}")
        
        tag_name = f"user_{self.username}"
        self.chat_display.tag_config(tag_name, foreground=color_code, font=self.username_font)
        
        window.destroy()
    
    def connect_to_mqtt(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            threading.Thread(target=self.client.loop_forever, daemon=True).start()
            
            # Subscribe to topics
            self.client.subscribe(self.chat_topic)
            self.client.subscribe(self.personal_topic)
            
            # Send join notification
            self.send_system_message(f"{self.username} has joined the chat")
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
            self.master.destroy()
    
    def on_connect(self, client, userdata, flags, rc):
        status = "Connected" if rc == 0 else f"Connection failed, code: {rc}"
        self.status_var.set(f"{status} as {self.username} in {self.chatroom}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            # Handle personal invitations
            if msg.topic == self.personal_topic and payload.get("type") == "invitation":
                self.handle_personal_invitation(payload)
                return
            
            # Regular chat messages
            timestamp = payload.get("timestamp", "unknown time")
            username = payload.get("username", "unknown user")
            message = payload.get("message", "")
            
            # Handle invitation within chat message
            if "invitation" in payload and payload["invitation"].get("to") == self.username:
                invite = payload["invitation"]
                if messagebox.askyesno("Chat Invitation", 
                                      f"You've been invited to join the chatroom '{invite['chatroom']}'.\nWould you like to join?"):
                    self.change_to_chatroom(invite['chatroom'], True)
            
            # Determine message styling
            tag_name = self.get_tag_for_username(username)
            
            # Update chat display
            self.master.after(0, self.update_chat_display, timestamp, username, message, tag_name)
            
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def get_tag_for_username(self, username):
        """Get the appropriate tag for a username"""
        if username == "System":
            return "system"
        elif username in ["jack", "bob"]:
            color = "#FF0000" if username == "jack" else "#008000"
            tag_name = username
            self.chat_display.tag_config(tag_name, foreground=color, font=self.username_font)
            return tag_name
        else:
            # Generate consistent color based on username
            color_names = list(COLORS.keys())
            color_names.remove("white")
            color_index = sum(ord(c) for c in username) % len(color_names)
            tag_name = f"user_{username}"
            try:
                self.chat_display.tag_config(tag_name, foreground=COLORS[color_names[color_index]], font=self.username_font)
            except:
                pass
            return tag_name
    
    def check_pending_invitations(self):
        try:
            if not os.path.exists(INVITATIONS_FILE):
                return
                
            with open(INVITATIONS_FILE, 'r') as f:
                try:
                    stored_invitations = json.load(f)
                except json.JSONDecodeError:
                    return
            
            if self.username not in stored_invitations or not stored_invitations[self.username]:
                return
                
            user_invites = stored_invitations[self.username]
            self.show_invitation_window(user_invites, stored_invitations)
                
        except Exception as e:
            print(f"Error loading stored invitations: {e}")
            # Try legacy format as fallback
            try:
                old_file = os.path.join(os.path.expanduser("~"), ".jack_chat_invitations.pkl")
                if os.path.exists(old_file):
                    with open(old_file, 'rb') as f:
                        stored_invitations = pickle.load(f)
                    
                    if self.username in stored_invitations and stored_invitations[self.username]:
                        user_invites = stored_invitations[self.username]
                        self.show_invitation_window(user_invites, stored_invitations)
                        # Convert to JSON for future use
                        with open(INVITATIONS_FILE, 'w') as f:
                            json.dump(stored_invitations, f, indent=4)
            except:
                pass
    
    def show_invitation_window(self, user_invites, stored_invitations):
        invite_window = tk.Toplevel(self.master)
        invite_window.title("Pending Chat Invitations")
        invite_window.geometry("400x300")
        invite_window.configure(bg="#1E1E1E")
        
        tk.Label(
            invite_window, text="You have pending invitations:",
            bg="#1E1E1E", fg="#FFFFFF", font=("Arial", 12, "bold")
        ).pack(pady=10)
        
        invites_frame = tk.Frame(invite_window, bg="#1E1E1E")
        invites_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        processed_invites = []
        
        for i, invite in enumerate(user_invites):
            # Create invite display panel
            self.create_invitation_panel(invites_frame, invite, processed_invites, i)
        
        # Add close button
        def close_and_save():
            new_invites = [invite for i, invite in enumerate(user_invites) if i not in processed_invites]
            stored_invitations[self.username] = new_invites
            with open(INVITATIONS_FILE, 'w') as f:
                json.dump(stored_invitations, f, indent=4)
            invite_window.destroy()
        
        tk.Button(
            invite_window, text="Close", bg="#555555", fg="#FFFFFF", command=close_and_save
        ).pack(pady=10)
        
        invite_window.protocol("WM_DELETE_WINDOW", close_and_save)
    
    def create_invitation_panel(self, parent, invite, processed_invites, idx):
        invite_frame = tk.Frame(parent, bg="#2A2A2A", padx=10, pady=10)
        invite_frame.pack(fill=tk.X, pady=5)
        
        from_user = invite.get("from", "Someone")
        chatroom = invite.get("chatroom", "unknown")
        timestamp = invite.get("timestamp", "")
        
        tk.Label(
            invite_frame, text=f"From {from_user} to join '{chatroom}'\nSent: {timestamp}",
            bg="#2A2A2A", fg="#FFFFFF", justify=tk.LEFT, anchor="w"
        ).pack(fill=tk.X, pady=5)
        
        buttons_frame = tk.Frame(invite_frame, bg="#2A2A2A")
        buttons_frame.pack(fill=tk.X)
        
        tk.Button(
            buttons_frame, text="Accept", bg="#4CAF50", fg="#FFFFFF",
            command=lambda room=chatroom, i=idx: self.accept_stored_invitation(room, processed_invites, i)
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            buttons_frame, text="Decline", bg="#F44336", fg="#FFFFFF",
            command=lambda i=idx: self.decline_stored_invitation(processed_invites, i)
        ).pack(side=tk.LEFT, padx=5)
    
    def accept_stored_invitation(self, chatroom, processed_invites, idx):
        processed_invites.append(idx)
        self.change_to_chatroom(chatroom, True)
    
    def decline_stored_invitation(self, processed_invites, idx):
        processed_invites.append(idx)
    
    def handle_personal_invitation(self, invite):
        from_user = invite.get("from", "Someone")
        chatroom = invite.get("chatroom", "unknown")
        
        if messagebox.askyesno("Chat Invitation", 
                              f"{from_user} has invited you to join the chatroom '{chatroom}'.\nWould you like to join?"):
            self.change_to_chatroom(chatroom, True)
        
        self.remove_stored_invitation(self.username, chatroom, from_user)
    
    def store_invitation(self, target_user, invitation_data):
        """Store invitation in JSON format"""
        try:
            stored_invitations = {}
            if os.path.exists(INVITATIONS_FILE):
                with open(INVITATIONS_FILE, 'r') as f:
                    try:
                        stored_invitations = json.load(f)
                    except json.JSONDecodeError:
                        # Handle case of empty or invalid JSON file
                        pass
            
            if target_user not in stored_invitations:
                stored_invitations[target_user] = []
                
            stored_invitations[target_user].append(invitation_data)
            
            with open(INVITATIONS_FILE, 'w') as f:
                json.dump(stored_invitations, f, indent=4)
                
        except Exception as e:
            print(f"Error storing invitation: {e}")
    
    def remove_stored_invitation(self, username, chatroom, from_user):
        """Remove invitation from JSON file"""
        try:
            if os.path.exists(INVITATIONS_FILE):
                with open(INVITATIONS_FILE, 'r') as f:
                    try:
                        stored_invitations = json.load(f)
                    except json.JSONDecodeError:
                        return
                
                if username in stored_invitations:
                    stored_invitations[username] = [
                        inv for inv in stored_invitations[username] 
                        if not (inv.get("chatroom") == chatroom and inv.get("from") == from_user)
                    ]
                    
                    with open(INVITATIONS_FILE, 'w') as f:
                        json.dump(stored_invitations, f, indent=4)
        except Exception as e:
            print(f"Error removing stored invitation: {e}")
    
    def update_chat_display(self, timestamp, username, message, tag_name):
        self.chat_display.config(state=tk.NORMAL)
        
        # Auto-scroll if near the bottom
        should_scroll = self.chat_display.yview()[1] > 0.9
        
        # Insert message with formatting
        self.chat_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
        self.chat_display.insert(tk.END, f"{username}: ", tag_name)
        self.chat_display.insert(tk.END, f"{message}\n", "message")
        
        # Configure tags
        self.chat_display.tag_config("timestamp", foreground="#AAAAAA", font=self.timestamp_font)
        self.chat_display.tag_config("message", foreground="#FFFFFF", font=self.message_font)
        self.chat_display.tag_config("system", foreground="#FFC107", font=self.username_font)
        
        # Auto-scroll if needed
        if should_scroll:
            self.chat_display.yview_moveto(1.0)
            
        self.chat_display.config(state=tk.DISABLED)
    
    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if not message:
            return
        
        self.message_entry.delete(0, tk.END)
        
        if message.lower() == "/exit":
            self.on_closing()
            return
        
        # Send message to chatroom
        message_payload = {
            "username": self.username,
            "message": message,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "color": self.my_color
        }
        
        self.client.publish(self.chat_topic, json.dumps(message_payload))
    
    def on_closing(self):
        try:
            self.send_system_message(f"{self.username} has left the chat")
            time.sleep(0.5)  # Give time for message to be sent
            self.client.disconnect()
        except:
            pass
        
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()