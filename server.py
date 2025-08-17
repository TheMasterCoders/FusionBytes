import os
import json
from flask import Flask, jsonify, request
import time
import threading
import logging

app = Flask(__name__)

with open("server.json", "r") as f:
    config = json.load(f)

# Global in-memory state for chat and moderation
CHAT_LOG = []
MUTED_USERS = {}
BANNED_USERS = {}
KICKED_USERS = []

# A dictionary to hold mission data, loaded from files
MISSIONS = {}

# The shared, authoritative file system
file_system = {
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

# --- User Data Persistence ---
def get_user_data_path(username):
    return os.path.join("cloud_saves", f"{username}.json")

def save_user_data(username, data):
    if not os.path.exists("cloud_saves"):
        os.makedirs("cloud_saves")
    path = get_user_data_path(username)
    try:
        with open(path, "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        print(f"Error saving user data: {e}")
        return False

# Function to load mission data from the missions directory
def load_missions():
    missions_dir = "missions"
    if not os.path.exists(missions_dir):
        print("Server: 'missions' directory not found.")
        return

    for filename in os.listdir(missions_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(missions_dir, filename)
            try:
                with open(filepath, "r") as f:
                    mission_data = json.load(f)
                    MISSIONS[mission_data["id"]] = mission_data
                print(f"Server: Loaded mission '{mission_data['title']}' from '{filename}'")
            except Exception as e:
                print(f"Server: Failed to load mission from '{filename}': {e}")

# --- Server-Side Command Handling ---
SERVER_COMMANDS = {
    "echo": "Echoes back the arguments provided",
    "chat": "Sends a message to all connected players",
    "hack": "Attempts to solve a mission or hack a system",
    "ls": "Lists files in the current directory",
    "cd": "Changes the current directory",
    "cat": "Displays the content of a file",
    "missions": "Lists all available missions and their status"
}

def get_current_directory_object(location):
    """Navigates the file system tree to the player's current location."""
    current_dir = file_system
    for part in location:
        if isinstance(current_dir, dict) and part in current_dir:
            current_dir = current_dir[part]
        else:
            return None # Should not happen with valid locations
    return current_dir

def handle_server_command(command, args, username):
    # Fetch player data to get their current location
    player_path = get_user_data_path(username)
    if not os.path.exists(player_path):
        return {"status": "error", "message": "User data not found. Please relog."}
    with open(player_path, "r") as f:
        player_data = json.load(f)
    
    player_location = player_data.get("location", ["root", "home", "user"])
    
    if username in MUTED_USERS:
        return {"status": "error", "message": "You are muted and cannot use the chat command."}
    if username in BANNED_USERS:
        return {"status": "error", "message": "You are banned."}

    if command == "echo":
        return {"status": "success", "message": " ".join(args)}

    if command == "chat":
        message = " ".join(args)
        CHAT_LOG.append({"sender": username, "message": message, "timestamp": time.time()})
        return {"status": "success", "message": "Message sent."}
    
    if command == "hack":
        if len(args) < 2:
            return {"status": "error", "message": "Usage: hack <mission_id> <password>"}

        mission_id = args[0]
        password = args[1]
        
        mission = MISSIONS.get(mission_id)
        
        if not mission:
            return {"status": "error", "message": "Mission not found."}
        
        # Check if the mission has already been completed
        if mission.get("completed", False):
            return {"status": "success", "message": "Mission already completed."}

        if password == mission["solution"]:
            mission["completed"] = True
            return {"status": "success", "message": f"SUCCESS! Mission '{mission['title']}' completed. {mission['reward']}"}
        else:
            return {"status": "error", "message": "Incorrect password. Access denied."}
    if command == "ls":
        current_dir = get_current_directory_object(player_location)
        if not current_dir or not isinstance(current_dir, dict):
            return {"status": "error", "message": "Error accessing directory."}
        
        output = "Files and folders in this directory:\n"
        output += "\n".join([f" - {item}" for item in current_dir.keys()])
        return {"status": "success", "message": output}

    if command == "cd":
        if not args:
            return {"status": "error", "message": "Usage: cd <directory>"}
        
        target = args[0]
        new_location = player_location[:]
        
        if target == "..":
            if len(new_location) > 1:
                new_location.pop()
            else:
                return {"status": "error", "message": "You can't go back any further."}
        else:
            current_dir = get_current_directory_object(player_location)
            if current_dir is not None and target in current_dir and isinstance(current_dir[target], dict):
                new_location.append(target)
            else:
                return {"status": "error", "message": f"cd: no such file or directory: {target}"}

        player_data["location"] = new_location
        save_user_data(username, player_data)
        
        return {"status": "success", "message": "Directory changed."}

    if command == "cat":
        if not args:
            return {"status": "error", "message": "Usage: cat <file>"}
        
        file_name = args[0]
        current_dir = get_current_directory_object(player_location)
        
        if current_dir is not None and file_name in current_dir and isinstance(current_dir[file_name], str):
            content = current_dir[file_name]
            return {"status": "success", "message": content}
        else:
            return {"status": "error", "message": f"cat: {file_name}: No such file or directory"}
    
    # New: Logic for the missions command
    if command == "missions":
        output = "--- Missions ---\n"
        if not MISSIONS:
            output += "No missions available.\n"
        else:
            for mission_id, mission_details in MISSIONS.items():
                status = "COMPLETED" if mission_details.get("completed", False) else "IN PROGRESS"
                output += f"ID: {mission_id}\n"
                output += f"Title: {mission_details['title']}\n"
                output += f"Status: {status}\n"
                output += f"Description: {mission_details['description']}\n"
                output += "---\n"
        return {"status": "success", "message": output.strip()}

    else:
        return {"status": "error", "message": f"Command '{command}' not found on server."}

# --- API Endpoints ---
@app.route("/check_command", methods=["POST"])
def check_command():
    data = request.get_json()
    command = data.get("command")
    args = data.get("args", [])
    username = data.get("username")
    if command in SERVER_COMMANDS:
        response = handle_server_command(command, args, username)
        return jsonify(response)
    return jsonify({"status": "error", "message": f"Command '{command}' not found on server."})

@app.route("/check_username", methods=["POST"])
def check_username():
    data = request.get_json()
    username = data.get("username")
    if os.path.exists(get_user_data_path(username)):
        return jsonify({"is_available": False})
    else:
        return jsonify({"is_available": True})

@app.route("/register_user", methods=["POST"])
def register_user():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"status": "error", "message": "Username not provided."}), 400

    if os.path.exists(get_user_data_path(username)):
        print(f"Server: HEY GUYS SOME IDIOT JUST TRIED TO MAKE {username} BUT THEY ALREADY EXIST LMAOOO")
        return jsonify({"status": "error", "message": "User already exists."}), 409

    initial_data = {"username": username, "progress": "fresh_start", "location": ["root", "home", "user"]}
    if save_user_data(username, initial_data):
        print(f"Server: [NEW USER] created: {username}")
        return jsonify({"status": "success", "message": "User created."})
    else:
        return jsonify({"status": "error", "message": "Failed to create user."}), 500

@app.route("/reconnect", methods=["POST"])
def log_reconnection():
    data = request.get_json()
    username = data.get("username")
    if username:
        print(f"Server: User {username} reconnected.")
        return jsonify({"status": "success", "message": "Reconnection logged."})
    return jsonify({"status": "error", "message": "Username not provided."}), 400

@app.route("/save", methods=["POST"])
def save_progress():
    data = request.get_json()
    username = data.get("username")
    save_data = data.get("data")
    if not username:
        return jsonify({"status": "error", "message": "Username not provided."}), 400

    print(f"Server: Saving client {username}'s game...")
    if save_user_data(username, save_data):
        print("Server: Done!")
        return jsonify({"status": "success", "message": "Progress saved to server."})
    else:
        return jsonify({"status": "error", "message": "Failed to save progress on server."}), 500

@app.route("/disconnect", methods=["POST"])
def log_disconnect():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"status": "error", "message": "Username not provided."}), 400

    print(f"Server: Client {username} disconnected. Reason: disconnect command used")
    return jsonify({"status": "success", "message": "Disconnect logged."})

@app.route("/get_chat_messages", methods=["GET"])
def get_chat_messages():
    return jsonify({"messages": CHAT_LOG})

@app.route("/get_new_chat_messages", methods=["GET"])
def get_new_chat_messages():
    last_timestamp = float(request.args.get("last_timestamp", 0))
    new_messages = [msg for msg in CHAT_LOG if msg["timestamp"] > last_timestamp]
    return jsonify({"messages": new_messages})

@app.route("/check_kick", methods=["POST"])
def check_kick():
    data = request.get_json()
    username = data.get("username")
    if username in KICKED_USERS:
        KICKED_USERS.remove(username)
        return jsonify({"should_kick": True})
    return jsonify({"should_kick": False})

@app.route("/get_commands", methods=["GET"])
def get_commands():
    return jsonify({"commands": SERVER_COMMANDS})
    
@app.route("/get_user_state", methods=["POST"])
def get_user_state():
    data = request.get_json()
    username = data.get("username")
    player_path = get_user_data_path(username)
    if not os.path.exists(player_path):
        return jsonify({"status": "error", "message": "User data not found."})
    with open(player_path, "r") as f:
        player_data = json.load(f)
    
    location = player_data.get("location", ["root", "home", "user"])
    location_str = "~" if location == ["root", "home", "user"] else "/".join(location)
    return jsonify({"status": "success", "location": location_str})

# --- Server-Side Admin Commands ---
def handle_server_input():
    while True:
        command = input("SERVER> ").strip().split()
        if not command:
            continue

        cmd = command[0].lower()
        args = command[1:]

        if cmd == "mute" and len(args) == 1:
            username = args[0]
            MUTED_USERS[username] = True
            print(f"SERVER: User {username} has been muted.")
        elif cmd == "unmute" and len(args) == 1:
            username = args[0]
            if username in MUTED_USERS:
                del MUTED_USERS[username]
                print(f"SERVER: User {username} has been unmuted.")
            else:
                print(f"SERVER: User {username} is not muted.")
        elif cmd == "ban" and len(args) == 1:
            username = args[0]
            BANNED_USERS[username] = True
            print(f"SERVER: User {username} has been banned.")
        elif cmd == "unban" and len(args) == 1:
            username = args[0]
            if username in BANNED_USERS:
                del BANNED_USERS[username]
                print(f"SERVER: User {username} has been unbanned.")
            else:
                print(f"SERVER: User {username} is not unbanned.")
        elif cmd == "kick" and len(args) == 1:
            username = args[0]
            if username not in KICKED_USERS:
                KICKED_USERS.append(username)
                print(f"SERVER: User {username} will be disconnected on their next poll.")
            else:
                print(f"SERVER: User {username} is already marked for disconnection.")
        elif cmd == "list_muted":
            print("SERVER: Muted users:", ", ".join(MUTED_USERS.keys()))
        elif cmd == "list_banned":
            print("SERVER: Banned users:", ", ".join(BANNED_USERS.keys()))
        elif cmd == "help":
            print("SERVER: Available commands:")
            print("  mute <username>  - Mutes a user from chatting.")
            print("  unmute <username> - Unmutes a user.")
            print("  ban <username> - Bans a user.")
            print("  unban <username> - Unbans a user.")
            print("  kick <username> - Force-disconnects a user.")
            print("  list_muted - Lists all muted users.")
            print("  list_banned - Lists all banned users.")
        else:
            print("SERVER: Unknown command. Type 'help' for a list of commands.")

if __name__ == "__main__":
    print("Server: Starting up...")
    if not os.path.exists("cloud_saves"):
        os.makedirs("cloud_saves")
    
    # Load missions at startup
    load_missions()

    # Disable Flask logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # Start the admin input thread
    admin_thread = threading.Thread(target=handle_server_input)
    admin_thread.daemon = True
    admin_thread.start()
    
    app.run(host=config["host"], port=config["port"], debug=True)