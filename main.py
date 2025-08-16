# A simple representation of a file system
file_system = {
    "root": {
        "home": {
            "user": {
                "documents": {
                    "mission1.txt": "Welcome to the game! Your first mission is to find the 'access_code' file."
                },
                "bin": {
                    "ls": "ls command",
                    "cat": "cat command"
                }
            }
        },
        "etc": {
            "passwd": "password file"
        }
    }
}

# The player class to hold state
class Player:
    def __init__(self):
        self.current_directory = file_system["root"]["home"]["user"]
        self.location = ["root", "home", "user"]

    def get_current_location(self):
        return "/" + "/".join(self.location)

# Example usage
player = Player()
print(f"Current directory: {player.get_current_location()}")