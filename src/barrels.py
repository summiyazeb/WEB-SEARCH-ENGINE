
import json
import os
import tempfile
import threading
from collections import OrderedDict

LETTERS = "abcdefghijklmnopqrstuvwxyz#"

# deciding to which barrel a word should go 
def barrel_key(word):
    #handling "" and Null values , they go to misc barrel
    if word == "" or word is None:
        return "#"
    #Converted to lower because Search engines are case sensitive 
    c = word[0].lower()
    if "a" <= c <= "z":
        return c
    else:
        return "#"





   
class BarrelStore:
    def __init__(self, folder, letters=LETTERS, cache_size=8):
        self.folder = folder
        self.letters = letters
        self.cache_size = cache_size #set to 8 barrels to keep RAM under 2 BG
        
        # creating folder of barrels if not existing
        os.makedirs(folder, exist_ok=True)
        
       # intialized the Cache Object remembring order of barrels loaded
        self._cache = OrderedDict() 
       # Ensuring no two users can acces the cache at the same tim 
        self._cache_lock = threading.RLock()
        
        # Create a separate lock for each letter so that adding doc to z.json does not block search on a.json
        self._locks = {ch: threading.RLock() for ch in letters}
        
        # Ensure all 27 files exist on disk
        # if not then it will create 
        for ch in letters:
            if not os.path.exists(self._path(ch)):
                self._write_atomic(ch, {})

def _path(self, ch):
        # Get the full file path for a specific barrel.
        # os.path.join is used because Windows uses \ and Linux/Mac uses / This makes the code work on any computer
        return os.path.join(self.folder, f"{ch}.json")

    def _read_file(self, ch):
        # opening barrel file from the disk and turninig the JSON text into a dictionary
        # with open(...) which automatically closes the file after reading
        with open(self._path(ch), "r", encoding="utf-8") as f:
            return json.load(f)

    # writing data to the disk 
    def _write_atomic(self, ch, data):
        # Geting the file path 
        path = self._path(ch)
        
        # Create a simple temporary path 
        # coz if system crash the original dta 
        tmp_path = path + ".tmp"
        
        # Write the data to the temporary file first
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
            
        # Replacing the temp file with the actual one 
        os.replace(tmp_path, path)
