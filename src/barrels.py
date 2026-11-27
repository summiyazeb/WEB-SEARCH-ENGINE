
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





   
