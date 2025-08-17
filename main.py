import os
import json
import time
import requests
import threading
import sys

# --- Game State ---
class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.is_connected = False
        self.timeout = 5  # Timeout in seconds

    def connect(self, username):
        print("Connecting to server...")
        try:
            response = requests.post(
                f"http://{self.host}:{self.port}/reconnect",
                json={"username": username},
                timeout=self.timeout
            )
            if response.status_code == 200:
                self.is_connected = True
                print("Connected!")
            else:
                self.is_connected = False
                print("Timeout. Server down or not connected to internet?")
                print("System: You can still play locally.")
        except requests.exceptions.RequestException:
            self.is_connected = False
            print("Timeout. Server down or not connected to internet?")
            print("System: You can still play locally.")

    def disconnect(self, player):
        if self.is_connected:
            print("Disconnecting from server...")
            try:
                url = f"http://{self.host}:{self.port}/disconnect"
                requests.post(url, json={"username": player.username}, timeout=self.timeout)
            except requests.exceptions.RequestException:
                pass

            player.save_progress_local()
            self.is_connected = False
            print("Disconnected.")
        else:
            print("Already disconnected.")

# New: The local file system for offline play
LOCAL_FS = {
    "root": {
        "home": {
            "user": {
                "documents": {
                    "mission1.txt": "Welcome, agent. Your first mission is to gain access to the 'Alpha' server. We believe the password is 'hunter2'. You can use the 'hack' command to submit a solution.",
                },
                "bin": {}
            }
        },
        "etc": {}
    }
}

# New: The local missions dictionary for offline play
LOCAL_MISSIONS = {
    "mission_01": {
        "title": "The First Byte",
        "description": "Welcome, agent. Your first mission is to gain access to the 'Alpha' server. The server is locked with a simple password. We believe the password is 'hunter2'.",
        "solution": "hunter2",
        "reward": "Access granted to the 'Alpha' server.",
        "completed": False
    }
}

class Player:
    def __init__(self, username):
        self.username = username
        self.last_chat_timestamp = 0
        self.is_kicked = False
        self.location = ["root", "home", "user"] # New: Player's local location

    def save_progress_local(self):
        if not os.path.exists("saves"):
            os.makedirs("saves")
        save_path = os.path.join("saves", f"{self.username}.json")
        print(f"Saving progress for {self.username} locally...")
        with open(save_path, "w") as f:
            json.dump({"username": self.username, "progress": "some_data", "location": self.location}, f)
        print("Done.")

# --- Command Handling ---
LOCAL_COMMANDS = ["save", "connect", "disconnect", "help", "exit", "chat_history"]

def show_help(server):
    print("Available commands:")
    print("\n--- Local Commands ---")
    for command in LOCAL_COMMANDS:
        print(f" - {command}")
        
    if server.is_connected:
        try:
            response = requests.get(f"http://{server.host}:{server.port}/get_commands", timeout=server.timeout)
            server_commands = response.json().get("commands", {})
            print("\n--- Server Commands ---")
            for command, description in server_commands.items():
                print(f" - {command}: {description}")
        except requests.exceptions.RequestException:
            print("\n--- Server Commands ---")
            print("Failed to retrieve server commands.")

def get_current_directory_object_local(location):
    """Navigates the local file system tree to the player's current location."""
    current_dir = LOCAL_FS
    for part in location:
        if isinstance(current_dir, dict) and part in current_dir:
            current_dir = current_dir[part]
        else:
            return None
    return current_dir

def handle_local_commands(command, args, player):
    """Handles commands when the server is not connected."""
    if command == "ls":
        current_dir = get_current_directory_object_local(player.location)
        if not current_dir or not isinstance(current_dir, dict):
            return "Error accessing directory."
        
        output = "Files and folders in this directory:\n"
        output += "\n".join([f" - {item}" for item in current_dir.keys()])
        return output

    if command == "cd":
        if not args:
            return "Usage: cd <directory>"
        
        target = args[0]
        new_location = player.location[:]
        
        if target == "..":
            if len(new_location) > 1:
                new_location.pop()
            else:
                return "You can't go back any further."
        else:
            current_dir = get_current_directory_object_local(player.location)
            if target in current_dir and isinstance(current_dir[target], dict):
                new_location.append(target)
            else:
                return f"cd: no such file or directory: {target}"

        player.location = new_location
        return "Directory changed."

    if command == "cat":
        if not args:
            return "Usage: cat <file>"
        
        file_name = args[0]
        current_dir = get_current_directory_object_local(player.location)
        
        if file_name in current_dir and isinstance(current_dir[file_name], str):
            return current_dir[file_name]
        else:
            return f"cat: {file_name}: No such file or directory"
    
    if command == "chat":
        return "Chat is only available when connected to the server."

    if command == "hack":
        if not args:
            return "Usage: hack <password>"
        
        password = args[0]
        mission = LOCAL_MISSIONS.get("mission_01")
        
        if not mission:
            return "Mission not found."
        
        if mission.get("completed", False):
            return "Mission already completed."

        if password == mission["solution"]:
            mission["completed"] = True
            return f"SUCCESS! Mission '{mission['title']}' completed. {mission['reward']} (Progress will not be saved on the server.)"
        else:
            return "Incorrect password. Access denied."

def check_command_server(command, args, player, server):
    if not server.is_connected:
        return {"status": "error", "message": "Not connected to server."}

    try:
        url = f"http://{server.host}:{server.port}/check_command"
        payload = {"command": command, "args": args, "username": player.username}
        response = requests.post(url, json=payload, timeout=server.timeout)
        return response.json()
    except requests.exceptions.RequestException:
        server.is_connected = False
        return {"status": "error", "message": "Server connection lost."}

def handle_command(command, args, player, server):
    if command in LOCAL_COMMANDS:
        if command == "save":
            if server.is_connected:
                url = f"http://{server.host}:{server.port}/save"
                try:
                    requests.post(url, json={"username": player.username, "data": {"progress": "some_data", "location": player.location}}, timeout=server.timeout)
                    print("Saving progress to server...")
                    print("Done!")
                except requests.exceptions.RequestException:
                    print("Server connection lost, saving locally instead.")
                    player.save_progress_local()
            else:
                player.save_progress_local()
            return

        if command == "connect":
            if not server.is_connected:
                server.connect(player.username)
            else:
                print("Already connected to the server.")
            return

        if command == "disconnect":
            server.disconnect(player)
            return

        if command == "help":
            show_help(server)
            return

        if command == "exit":
            sys.exit()

        if command == "chat_history":
            if server.is_connected:
                url = f"http://{server.host}:{server.port}/get_chat_messages"
                try:
                    response = requests.get(url, timeout=server.timeout)
                    messages = response.json().get("messages", [])
                    print("\n--- Chat History ---")
                    for msg in messages:
                        print(f"[{msg['sender']}]: {msg['message']}")
                    print("--- End History ---\n")
                except requests.exceptions.RequestException:
                    print("Failed to get chat history.")
            else:
                print("Not connected to server.")
            return
    
    # New: Logic for handling commands based on server connection status
    if server.is_connected:
        response = check_command_server(command, args, player, server)
        if response["status"] == "success":
            print(response["message"])
        else:
            print(response["message"])
    else:
        # Handle server-side commands locally if disconnected
        if command in ["ls", "cd", "cat", "chat", "hack"]:
            message = handle_local_commands(command, args, player)
            print(message)
        else:
            print(f"Command '{command}' not found. You are not connected to the server.")

def poll_for_messages(server, player):
    while True:
        if player.is_kicked:
            print("\n!!! You have been disconnected by the server. !!!")
            sys.exit()

        if server.is_connected:
            try:
                kick_response = requests.post(f"http://{server.host}:{server.port}/check_kick", json={"username": player.username})
                if kick_response.json()["should_kick"]:
                    player.is_kicked = True
                    continue
                
                url = f"http://{server.host}:{server.port}/get_new_chat_messages"
                response = requests.get(url, params={"last_timestamp": player.last_chat_timestamp})
                new_messages = response.json().get("messages", [])
                
                if new_messages:
                    print("\n--- New Message ---")
                    for msg in new_messages:
                        print(f"[{msg['sender']}]: {msg['message']}")
                    print("-------------------")
                    player.last_chat_timestamp = new_messages[-1]["timestamp"]
            except requests.exceptions.RequestException:
                pass
        time.sleep(3)

def main():
    with open("server.json", "r") as f:
        config = json.load(f)

    server = Server(config["host"], config["port"])
    print("Welcome to FusionBytes!")

    save_files = []
    if os.path.exists("saves"):
        save_files = [f.replace(".json", "") for f in os.listdir("saves") if f.endswith(".json")]

    username = ""
    player = None

    if save_files:
        print("Existing users found:")
        for i, name in enumerate(save_files):
            print(f" - {i+1}. {name}")
        print("Enter 'new' to create a new user.")

        while not username:
            choice = input("Enter the number of the user to load, or 'new': ")
            if choice.lower() == "new":
                while not username:
                    username_input = input("Set your user name! ")
                    if os.path.exists(os.path.join("saves", f"{username_input}.json")):
                        print(f"User '{username_input}' already exists locally. Please try a different one.")
                    else:
                        try:
                            response = requests.post(f"http://{server.host}:{server.port}/check_username", json={"username": username_input})
                            if response.json()["is_available"]:
                                username = username_input
                                player = Player(username)
                                player.save_progress_local()
                                print(f"You are now {username}!")
                                break
                            else:
                                print(f"User '{username_input}' is already taken on the server. Please try a different one.")
                        except requests.exceptions.RequestException:
                            print("Server connection failed. Cannot check for remote username. Please try again later.")
                            break
            else:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(save_files):
                        username = save_files[index]
                        player = Player(username)
                        with open(os.path.join("saves", f"{username}.json"), "r") as f:
                            save_data = json.load(f)
                            player.location = save_data.get("location", ["root", "home", "user"])
                        print(f"You are now {username}!")
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Invalid input. Please enter a number or 'new'.")
    else:
        while not username:
            username_input = input("Set your user name! ")
            if os.path.exists(os.path.join("saves", f"{username_input}.json")):
                print(f"User '{username_input}' already exists locally. Please try a different one.")
            else:
                try:
                    response = requests.post(f"http://{server.host}:{server.port}/check_username", json={"username": username_input})
                    if response.json()["is_available"]:
                        username = username_input
                        player = Player(username)
                        player.save_progress_local()
                        print(f"You are now {username}!")
                        break
                    else:
                        print(f"User '{username_input}' is already taken on the server. Please try a different one.")
                except requests.exceptions.RequestException:
                    print("Server connection failed. Cannot check for remote username. Please try again later.")

    server.connect(username)
    
    message_thread = threading.Thread(target=poll_for_messages, args=(server, player), daemon=True)
    message_thread.start()

    while True:
        try:
            if player.is_kicked:
                time.sleep(1)
                continue
            
            # The prompt now dynamically updates based on the player's location
            location_string = "~" if player.location == ["root", "home", "user"] else "/".join(player.location)
            user_input = input(f"{username}@{location_string}> ")
            
            parts = user_input.split(" ")
            command = parts[0]
            args = parts[1:]
            handle_command(command, args, player, server)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()