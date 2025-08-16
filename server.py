import os
import json
from flask import Flask, jsonify, request

app = Flask(__name__)

with open("server.json", "r") as f:
    config = json.load(f)

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

# --- Server-Side Command Handling ---
SERVER_COMMANDS = {
    "echo": "Echoes back the arguments provided",
}

def handle_server_command(command, args):
    if command == "echo":
        return {"status": "success", "message": " ".join(args)}
    else:
        return {"status": "error", "message": f"Command '{command}' not found on server."}

# --- API Endpoints ---
@app.route("/check_command", methods=["POST"])
def check_command():
    data = request.get_json()
    command = data.get("command")
    args = data.get("args", [])
    if command in SERVER_COMMANDS:
        response = handle_server_command(command, args)
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
        # New log message for a failed user creation attempt
        print(f"Server: HEY GUYS SOME IDIOT JUST TRIED TO MAKE {username} BUT THEY ALREADY EXIST LMAOOO")
        return jsonify({"status": "error", "message": "User already exists."}), 409
    
    initial_data = {"username": username, "progress": "fresh_start"}
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

if __name__ == "__main__":
    print("Server: Starting up...")
    if not os.path.exists("cloud_saves"):
        os.makedirs("cloud_saves")
    app.run(host=config["host"], port=config["port"], debug=True)