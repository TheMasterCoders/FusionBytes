import time

# --- Game State ---
class Server:
    def __init__(self):
        self.is_connected = False
        self.timeout = 5  # Timeout in seconds

    def connect(self):
        print("Connecting to server...")
        try:
            time.sleep(self.timeout)
            self.is_connected = False
            print("Timeout. Server down or not connected to internet?")
            print("System: You can still play locally.")
        except KeyboardInterrupt:
            self.is_connected = False
            print("\nConnection attempt interrupted.")
        
    def disconnect(self):
        if self.is_connected:
            print("Disconnecting from server...")
            handle_command("save", [], None, self)
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
                "bin": {
                    "ls": "list directory contents",
                    "cat": "concatenate and print files",
                    "cd": "change directory",
                    "save": "save progress",
                    "connect": "connect to the server",
                    "disconnect": "disconnect from the server"
                }
            }
        },
        "etc": {
            "passwd": "password file"
        }
    }
}

class Player:
    def __init__(self):
        self.current_directory = file_system["root"]["home"]["user"]
        self.location = ["root", "home", "user"]

    def get_current_location(self):
        return "~" if self.location == ["root", "home", "user"] else "/" + "/".join(self.location)

# A global list of built-in commands
LOCAL_COMMANDS = ["ls", "cd", "cat", "save", "connect", "disconnect", "help"]

def show_help():
    print("Available commands:")
    for command in LOCAL_COMMANDS:
        print(f" - {command}")

# --- Command Handling ---
def handle_command(command, args, player, server):
    if command in LOCAL_COMMANDS:
        if command == "save":
            print("Saving progress locally...")
            print("Done.")
            return

        if command == "connect":
            if not server.is_connected:
                server.connect()
            else:
                print("Already connected to the server.")
            return

        if command == "disconnect":
            server.disconnect()
            return
            
        if command == "help":
            show_help()
            return

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

    print(f"Command '{command}' not found locally.")

def main():
    player = Player()
    server = Server()
    
    server.connect()

    while True:
        try:
            user_input = input(f"{'[' + 'user' + ']' + '@' + 'fusionbytes'}:{player.get_current_location()}> ")
            parts = user_input.split(" ")
            command = parts[0]
            args = parts[1:]
            
            handle_command(command, args, player, server)
            
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()