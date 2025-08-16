import os
import json
import time
import requests

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

# A simple representation of a file system
file_system = {
    "root": {
        "home": {
            "user": {
                "documents": {
                    "mission1.txt": "Welcome to the game! Your first mission is to find the 'access_code' file."
                },
                "bin": {}
            }
        },
        "etc": {}
    }
}

class Player:
    def __init__(self, username):
        self.username = username
        self.current_directory = file_system["root"]["home"]["user"]
        self.location = ["root", "home", "user"]

    def get_current_location(self):
        return "~" if self.location == ["root", "home", "user"] else "/" + "/".join(self.location)

    def save_progress_local(self):
        if not os.path.exists("saves"):
            os.makedirs("saves")
        save_path = os.path.join("saves", f"{self.username}.json")
        print(f"Saving progress for {self.username} locally...")
        with open(save_path, "w") as f:
            json.dump({"username": self.username, "progress": "some_data"}, f)
        print("Done.")

# --- Command Handling ---
LOCAL_COMMANDS = ["ls", "cd", "cat", "save", "connect", "disconnect", "help", "exit"]

def show_help():
    print("Available commands:")
    for command in LOCAL_COMMANDS:
        print(f" - {command}")

def check_command_server(command, args, player, server):
    if not server.is_connected:
        return {"status": "error", "message": "Not connected to server."}

    try:
        url = f"http://{server.host}:{server.port}/check_command"
        payload = {"command": command, "args": args}
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
                    requests.post(url, json={"username": player.username, "data": {"progress": "some_data"}}, timeout=server.timeout)
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
            show_help()
            return

        if command == "exit":
            raise SystemExit

    if command == "ls":
        print("Files and folders in this directory:")
        for item in player.current_directory:
            print(f" - {item}")
        return
    
    if command == "cd":
        if not args:
            print("Usage: cd <directory>")
            return
        target = args[0]
        if target == "..":
            if len(player.location) > 1:
                player.location.pop()
                player.current_directory = file_system
                for part in player.location:
                    player.current_directory = player.current_directory[part]
            else:
                print("You can't go back any further.")
            return
        if target in player.current_directory and isinstance(player.current_directory[target], dict):
            player.location.append(target)
            player.current_directory = player.current_directory[target]
            return
        else:
            print(f"cd: no such file or directory: {target}")
            return
    
    if command == "cat":
        if not args:
            print("Usage: cat <file>")
            return
        file_name = args[0]
        if file_name in player.current_directory and isinstance(player.current_directory[file_name], str):
            print(player.current_directory[file_name])
            return
        else:
            print(f"cat: {file_name}: No such file or directory")
            return

    response = check_command_server(command, args, player, server)
    if response["status"] == "success":
        print(response["message"])
    else:
        print(response["message"])

def main():
    with open("server.json", "r") as f:
        config = json.load(f)

    server = Server(config["host"], config["port"])
    print("Welcome to FusionBytes!")
    
    # Check for existing saves
    save_files = []
    if os.path.exists("saves"):
        save_files = [f.replace(".json", "") for f in os.listdir("saves") if f.endswith(".json")]

    username = ""
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
                    # Check for local save first
                    if os.path.exists(os.path.join("saves", f"{username_input}.json")):
                        print(f"User '{username_input}' already exists locally. Please try a different one.")
                    else:
                        # Now check with the server
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
            else:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(save_files):
                        username = save_files[index]
                        player = Player(username)
                        print(f"You are now {username}!")
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Invalid input. Please enter a number or 'new'.")
    else:
        while not username:
            username_input = input("Set your user name! ")
            # Check for local save first
            if os.path.exists(os.path.join("saves", f"{username_input}.json")):
                print(f"User '{username_input}' already exists locally. Please try a different one.")
            else:
                # Now check with the server
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

    while True:
        try:
            user_input = input(f"{player.username}@fusionbytes> ")
            parts = user_input.split(" ")
            command = parts[0]
            args = parts[1:]
            handle_command(command, args, player, server)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()