import os
import json
import tkinter as tk
import io
import requests
import threading
import time
import re
import cv2
import numpy as np
import locale
import hashlib
import ctypes
from tkinter import Tk, Label, Entry, Button, Listbox, END, Frame
from tkinter import messagebox, ttk
from tkinter import font
from tkinter import simpledialog, Toplevel
from PIL import Image, ImageTk
from urllib.parse import urlparse

# Enable DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI awareness
    scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100  # Get scaling factor
except AttributeError:
    scale_factor = 1  # Default if unsupported

# Initialize or load JSON database
DB_FILE = "db.json"


import sys

# Global dictionary to track start times of functions
start_times = {}

# Stack to keep track of function call hierarchy
call_stack = []

# Threshold for long-running functions (in seconds)
LONG_FUNCTION_THRESHOLD = 0.004

# Boolean flag to toggle the logging behavior
log_long_functions = True  # Set this to False to log all function calls

def log_function_calls(frame, event, arg):
    """Log all function calls (used when log_long_functions is False)."""
    if event == "call":
        func_name = frame.f_code.co_name
        func_file = frame.f_code.co_filename
        func_line = frame.f_lineno
        print(f"Function {func_name} called in {func_file}:{func_line}")

def profile_function(frame, event, arg):
    """Profile function calls, measure execution time, and log long-running ones."""
    
    if event == "call":
        # Record the start time of the function
        start_times[frame.f_code] = time.perf_counter()
        
        # Push the current function onto the call stack with line number
        call_stack.append((frame.f_code, frame.f_lineno))
    
    elif event == "return":
        # Measure the execution time of the function
        end_time = time.perf_counter()
        start_time = start_times.get(frame.f_code)
        
        if start_time:
            execution_time = end_time - start_time
            if execution_time > LONG_FUNCTION_THRESHOLD:
                # Log long-running functions with indentation based on call depth
                indentation = '  ' * (len(call_stack) - 1)  # Indentation based on call depth
                function_name = frame.f_code.co_name
                function_line = frame.f_lineno
                function_file = frame.f_code.co_filename
                print(f"{indentation}Function '{function_name}' (Line {function_line}, File: {function_file}) "
                      f"took {execution_time:.4f} seconds")
            
            # Clean up by removing the function from the stack
            call_stack.pop()

def set_profiler():
    """Set the profiler based on the log_long_functions flag."""
    if log_long_functions:
        sys.setprofile(profile_function)
    else:
        sys.setprofile(log_function_calls)

# Set the profiler initially
#set_profiler()

def load_database():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            db = json.load(f)

        # Ensure all textures have a selected_thumbnails key
        for texture_path, texture_data in db.get("textures", {}).items():
            texture_data.setdefault("selected_thumbnails", [])

        return db
    return {"textures": {}}


def save_database(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

CACHE_FILE = "api_cache.json"

TARGET_FOLDER = "staging/textures/"  # Replace with the actual folder path
OVERLAY_FOLDER ="staging/overlay/"

def load_api_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_api_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)

def fetch_api_data(url):
    cache = load_api_cache()
    if url in cache:
        return cache[url]  # Return cached response
    
    # Define the headers with the custom User-Agent
    headers = {
        'User-Agent': 'pbrmatcher'
    }
    
    try:
        response = requests.get(url, headers)
        if response.status_code == 200:
            cache[url] = response.json()
            save_api_cache(cache)
            return cache[url]
        else:
            messagebox.showerror("Network Error", f"Failed to fetch data. Status code: {response.status_code}")
    except requests.RequestException as e:
        messagebox.showerror("Network Error", f"An error occurred: {e}")
    
    return None

THUMBNAIL_CACHE_DIR = "thumbnails"

def ensure_thumbnail_cache_dir():
    if not os.path.exists(THUMBNAIL_CACHE_DIR):
        os.makedirs(THUMBNAIL_CACHE_DIR)

def get_cached_thumbnail_path(thumbnail_url):
    ensure_thumbnail_cache_dir()
    # Parse the URL and extract the path
    parsed_url = urlparse(thumbnail_url)
    filename = os.path.basename(parsed_url.path)  # Extract the filename without query parameters
    return os.path.join(THUMBNAIL_CACHE_DIR, filename)

def fetch_thumbnail(thumbnail_url):
    cache_path = get_cached_thumbnail_path(thumbnail_url)
    if os.path.exists(cache_path):
        return Image.open(cache_path)  # Load from cache

    try:
        response = requests.get(thumbnail_url, stream=True)  # Stream to avoid loading full image in memory
        if response.status_code == 200:
            with open(cache_path, "wb") as f:
                for chunk in response.iter_content(1024):  # Save in chunks
                    f.write(chunk)
            return Image.open(cache_path)
        else:
            print(f"Failed to fetch thumbnail. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
    return None




# GUI
class TextureTagger:
    def __init__(self, root, db):
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        self.root = root
        self.root.title("Morrowind PBR Texture Project")
        self.db = db
        self.texture_paths = self.get_texture_paths()
        self.filtered_texture_paths = self.texture_paths  # For filtering purposes
        
        # Create a separate list for texture names (remove "textures\" prefix)
        self.filtered_texture_names = [
            os.path.basename(texture_path).replace("textures\\", "") for texture_path in self.filtered_texture_paths
        ]
        # Create a set for fast lookup if needed
        self.filtered_texture_names_set = set(self.filtered_texture_names)

        self.root.bind("<Button-1>", self.global_click_handler)


        self.current_index = self.get_current_index()
        self.current_selection = None
     
        self.thumbnail_cache = {}  # Cache to store preloaded thumbnails
        self.cache_size = 20  # Limit the cache size to avoid memory issues

        self.thumbnail_data_cache = {}
        self.thumbnail_cache_size = 20
        
        # Initialize current_thumbnail_index in __init__
        self.current_thumbnail_index = 0

        #self.all_assets = {}
        self.all_assets = fetch_api_data("https://api.polyhaven.com/assets?type=textures")

        self.root.configure(bg="#999999")

        # Set a fixed window size
        #self.root.geometry("1600x960")

        # Scale the window size based on DPI
        base_width, base_height = 1600, 960  # Base size (adjust as needed)
        scaled_width = int(base_width * scale_factor)
        scaled_height = int(base_height * scale_factor)
        self.root.geometry(f"{scaled_width}x{scaled_height}")

        # Retrieve system default fonts dynamically
        #default_font = font.nametofont("TkDefaultFont")
        text_font = font.nametofont("TkTextFont")
        button_font = font.nametofont("TkTextFont")

        # Get actual sizes before modification
        default_size = text_font.actual("size")
        text_size = text_font.actual("size")
        button_size = text_font.actual("size")

        # Scale fonts based on DPI
        text_font.configure(size=int(text_size * scale_factor + 1))
        button_font.configure(size=int(text_size * scale_factor))
        default_font = text_font
        
        self.center_window(scaled_width, scaled_height)
        


        # Prevent window resizing 
        self.root.resizable(False, False)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Create main frame and make it expand
        self.main = Frame(self.root, bg="#999999")
        self.main.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(0, weight=1)

        # Create gridA and make it expand fully
        self.gridA = Frame(self.main, bg="#999999") 
        self.gridA.grid(row=0, column=0, sticky="nsew")  
        self.main.rowconfigure(0, weight=1)
        self.main.columnconfigure(0, weight=1)

        # Add sub-frames inside gridA
        self.gridA1 = Frame(self.gridA, bg="#999999")  # Content-sized
        self.gridA2 = Frame(self.gridA, bg="#999999")  # Expanding
        self.gridA3 = Frame(self.gridA, bg="#999999")  # Centered
        self.gridA4 = Frame(self.gridA, bg="#999999")  # Expanding
        self.gridA5 = Frame(self.gridA, bg="#999999")  # Content-sized

        # Set a fixed width for gridA3 (so it does NOT change with content)
        self.gridA3.grid_propagate(False)  # Prevents resizing to fit content

        # Positioning Frames in a Single Row
        self.gridA1.grid(column=0, row=0, sticky="ns", padx=5)  # No width expansion
        self.gridA2.grid(column=1, row=0, sticky="nsew")  # Expands
        self.gridA3.grid(column=2, row=0, sticky="nsew")  # Centered
        self.gridA4.grid(column=3, row=0, sticky="nsew")  # Expands
        self.gridA5.grid(column=4, row=0, sticky="ns", padx=5)  # No width expansion

        # Configure column weights
        self.gridA.columnconfigure(0, weight=0, minsize=50)  # gridA1: No expansion, min width
        self.gridA.columnconfigure(1, weight=1, minsize=400)  # gridA2: Expands
        self.gridA.columnconfigure(2, weight=2)  # gridA3: Centered (more space)
        self.gridA.columnconfigure(3, weight=1, minsize=400)  # gridA4: Expands
        self.gridA.columnconfigure(4, weight=0, minsize=50)  # gridA5: No expansion, min width

        self.gridA4.columnconfigure(0, weight=1)
        self.gridA4.rowconfigure(0, weight=1)

        # Add gridB and gridC below gridA
        self.gridB = Frame(self.main, bg="#999999")
        self.gridB.grid(column=0, row=1, sticky="nsew")  
        self.gridC = Frame(self.main, bg="#999999")
        self.gridC.grid(column=0, row=2, sticky="nsew")  

        # Allow gridB and gridC to expand
        self.main.rowconfigure(1, weight=1)
        self.main.rowconfigure(2, weight=1)




        # GUI Elements
        self.texture_name_label = Label(self.gridA3, text="", font=("Arial", int(7 * scale_factor)), pady=10)
        self.texture_name_label.bind("<Button-1>", self.show_entry) #bind click
        self.texture_name_label.pack()
        self.texture_name_label.lift()
        self.default_bg = self.texture_name_label.cget("bg")  # Get the current default background

        self.entry_container = Frame(self.gridA3)  # Container for entry and list
        self.entry_container.place(relx=0.25, rely=0.01) #pack the container AFTER the label
        self.entry_container.lift()


        self.label_frame = Frame(self.gridA3, bg="black")
        self.label_frame.pack()
        self.image_label = Label(self.label_frame, bg="black")
        self.image_label.pack(fill="both", padx=10, pady=10)
        self.image_label.bind("<Motion>", self.show_zoom_preview)
        self.image_label.bind("<Leave>", self.hide_zoom_preview)


        self.previous_button = Button(self.gridA1, font=button_font, width=int(7 * scale_factor), text="Previous", command=self.previous_texture)
        self.previous_button.pack(padx=10, pady=5, expand=True)

        self.next_button = Button(self.gridA5, font=button_font, width=int(7 * scale_factor), text="Next", command=self.next_texture)
        self.next_button.pack(padx=10, pady=5, expand=True)

        # Create the download frame and add the button and progress bar
        self.download_frame = Frame(self.gridA4, padx=5, pady=15)
        offset = 16  # Fixed offset from top (y=16)
        relscale = 0.9

        self.download_frame.grid(row=0, column=0, pady=10, sticky="n")  # Middle column, centered at the top


        #self.download_button.grid(row=0, column=0, pady=10)

         # Add "DOWNLOAD ALL" button
        self.add_all_to_queue_button = Button(self.download_frame, font=7, anchor="center", text="DOWNLOAD ALL", command=self.add_all_to_queue)
        self.add_all_to_queue_button.grid(row=0, column=0, padx=5, pady=10, sticky="nwse")


        # Add "Add to Queue" button
        self.add_to_queue_button = Button(self.download_frame, font=7, anchor="center", text="Add to Queue", command=self.add_to_queue)
        self.add_to_queue_button.grid(row=0, column=1, padx=5, pady=10, sticky="nwse")

        # Add "Show Queue" button
        self.show_queue_button = Button(self.download_frame, font=7, anchor="center", text="Show Queue", command=self.show_queue)
        self.show_queue_button.grid(row=0, column=2, padx=5, pady=10, sticky="nwse")

        # Add a Progressbar widget to the GUI
        self.progress_label = ttk.Label(self.download_frame, font=9, text="Completed: 0, In Progress: 0, Pending: 0")
        self.progress_label.grid(row=1, columnspan=3, pady=10)

        self.progress_bar= ttk.Progressbar(self.download_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=2, columnspan=3, pady=5)

        # Queue and Progress Tracking
        self.completed_downloads = []  # To track items in the queue
        self.in_progress = []  # To track items in the queue
        self.download_queue = []  # To track items in the queue
        self.currently_downloading = False  # To track if a download is in progress
        
        # Add frame for slot buttons and preview
        self.slot_frame = Frame(self.download_frame)
        self.slot_frame.grid(row=3, columnspan=3, pady=5)

        self.selected_slot = None
        self.slot_buttons = {}

        # Add buttons for A, B, C, D
        slot_names = ["A", "B", "C", "D"]
        for slot in range(4):
            self.slot_frame.grid_columnconfigure(slot, weight=1)  # Ensure equal column widths
            button = Button(
                self.slot_frame,
                text=slot_names[slot],
                width= 5,
                font=7,
                command=lambda slot=slot_names[slot]: self.switch_slot(slot)
            )

            button.grid(row=4, column=slot, padx=1, sticky="we")  # "we" makes the button stretch horizontally
            self.slot_buttons[slot_names[slot]] = button
        for slot_name, button in self.slot_buttons.items():
            button.grid_remove()  # Hide all buttons initially


        # Add single preview area
        self.preview_label = Label(self.slot_frame, font=default_font, text="No Preview", bg="gray")
        self.preview_label.grid(row=5, column=0, pady=5, columnspan=3)  # Span across all columns for alignment

        self.root.update_idletasks()

        # Create a frame for tags list and buttons
        self.tags_frame = Frame(self.gridA3)
        self.tags_frame.pack()

        self.tags_listbox = Listbox(self.tags_frame, selectmode="multiple", height=5)
        self.tags_listbox.grid(row=0, column=0, padx=10)

        # Add buttons to the right of the tags list
        self.buttons_frame = Frame(self.tags_frame)
        self.buttons_frame.grid(row=0, column=1, padx=10)

        self.add_tag_button = Button(self.buttons_frame, font=7, text="Add Tag", command=self.add_tag)
        self.add_tag_button.pack(pady=5)

        self.remove_tag_button = Button(self.buttons_frame, font=7, text="Remove Tag", command=self.remove_tag)
        self.remove_tag_button.pack(pady=5)

        self.tag_entry = Entry(self.gridA3)
        self.tag_entry.pack(pady=5)

        # Create a frame for togglable buttons
        self.button_frame = Frame(self.gridB)
        self.button_frame.pack()

        # Frame for displaying thumbnails
        self.thumbnail_frame = Frame(self.gridB, width= int(455), height= int(555), bg="black")
        
        self.thumbnail_frame.pack(pady=10)
        self.thumbnail_frame.pack_propagate(False)

        # Add togglable buttons with labels
        self.button_info = {
            "tx_a_": "armor",
            "tx_ac_": "azura's coast",
            "tx_ai_": "ascadian isles",
            "tx_b_": "body",
            "tx_bc_": "bitter coast",
            "tx_bm_": "bloodmoon",
            "tx_c_": "cloth",
            "tx_ex_": "exterior",
            "tx_hlaalu_": "hlaalu",
            "tx_imp_": "imperial",
            "tx_ma_": "molag amur",
            "tx_metal_": "metal",
            "tx_rock_": "rock",
            "tx_w_": "weapon",
            "tx_wood_": "wood",
            "tx_stone_": "stone"
        }

        self.use_file_config = False
        self.original_button_info = self.button_info

        self.buttons = {}
        self.label_frames = {}  # Store frames for each label
        self.active_buttons = set()
  
        
        if self.use_file_config:
            file_button_config = self.load_button_config_from_file()
            if file_button_config:
                # Create button_info with file-based names as keys
                self.button_info = {name: name for name in file_button_config.keys()}
                # Directly set filtered paths from file
                self.filtered_texture_paths = [
                    self.translate_texture_path(path) 
                    for paths in file_button_config.values()
                    for path in paths
                ]
                
                # Ensure we have a valid current_index
                if not self.filtered_texture_paths:
                    self.current_index = -1
                else:
                    self.current_index = 0



        else:
            # Reset to original button_info and texture paths
            self.button_info = self.original_button_info
            self.filtered_texture_paths = self.texture_paths
            self.current_index = 0

        self.create_buttons()

        print(f"Filtered paths count: {len(self.filtered_texture_paths)}")
        print(f"First few paths: {self.filtered_texture_paths[:3]}")

        print(f"Current index: {self.current_index}")
        print(f"Filtered paths length: {len(self.filtered_texture_paths)}")

        self.misc_button = Button(self.button_frame, font=7, text="Misc", command=self.show_all_textures)
        self.misc_button.grid(row=0, column=len(self.button_info), padx=10)
        
        self.misc_frame = Frame(self.button_frame)
        self.misc_frame.grid(row=1, column=len(self.button_info), padx=10)
        
        self.misc_label_tagged = Label(self.misc_frame, font=5, text="0", fg="green")
        self.misc_label_tagged.pack(side="left")
        
        Label(self.misc_frame, text="/").pack(side="left")
        
        self.misc_label_untagged = Label(self.misc_frame, font=5, text="0", fg="red")
        self.misc_label_untagged.pack(side="left")

        self.all_button = Button(self.button_frame, font=7, text="All", command=self.toggle_all_buttons)
        self.all_button.grid(row=0, column=len(self.button_info) + 1, padx=10)

        self.selected_thumbnails_label = Label(self.gridC, text="Selected Thumbnails: 0", font=("Arial", 7))
        self.selected_thumbnails_label.pack(pady=5)

        self.all_frame = Frame(self.button_frame)
        self.all_frame.grid(row=1, column=len(self.button_info) + 1, padx=10)

        self.all_label_tagged = Label(self.all_frame, font=5, text="0", fg="green")
        self.all_label_tagged.pack(side="left")

        Label(self.all_frame, text="/").pack(side="left")

        self.all_label_untagged = Label(self.all_frame, font=5, text="0", fg="red")
        self.all_label_untagged.pack(side="left")

        # Display first texture
        self.display_texture()
        self.update_counts()
        self.create_autocomplete_entry()

        self.texture_name_entry.pack_forget()  # Start hidden
        self.autocomplete_list.pack_forget()  # Start hidden
        self.scrollbar.pack_forget()  # Start hidden



        thumb_button_frame = Frame(self.gridC)
        thumb_button_frame.pack()
   
        self.previous_thumbnails_button = Button(thumb_button_frame, font=7, text="Previous Thumbnails", command=self.previous_thumbnails)
        self.previous_thumbnails_button.grid(row=0, column=0, padx=10)
        # Page indicator label
        self.page_indicator = Label(thumb_button_frame, font=default_font, text="-/-")
        self.page_indicator.grid(row=0, column=1, padx=10)
        self.next_thumbnails_button = Button(thumb_button_frame, font=7, text="Next Thumbnails", command=self.next_thumbnails)
        self.next_thumbnails_button.grid(row=0, column=2, padx=10)
    
    def translate_texture_path(self, file_path):
            """
            Translate file paths from config to match target folder naming
            
            Example:
            'textures/wood1.dds' -> 'tx_wood_result.png'
            """
            # Extract base filename
            base_filename = os.path.basename(file_path)
            
            # Remove extension
            name_without_ext = os.path.splitext(base_filename)[0]
            
            # Convert to target naming convention
            target_filename = f"{name_without_ext}_result.png"
            
            return os.path.join("textures", target_filename)


    def center_window(self, width, height):
        # Get the screen width and height
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Calculate the position of the window
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2) - 25

        # Set the window geometry
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def load_button_config_from_file(self, file_path='texmatch.txt'):
        """
        Load button configurations from a text file.
        
        File format:
        :wood:
        textures/wood1.dds
        textures/wood2.dds
        """
        button_config = {}
        current_button = None

        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(':') and line.endswith(':'):
                        current_button = line[1:-1]
                        button_config[current_button] = []
                    elif current_button and line:
                        button_config[current_button].append(line)

        except FileNotFoundError:
            print(f"Config file {file_path} not found")
            return None

        return button_config

    def update_current_index(self, entered_text):
        """Updates the current index based on the entered texture name and prints it."""
        # Concatenate the entered text with the subfolder prefix
        full_path = f"textures\\{entered_text}"
        
        # Check if the constructed full path exists in the filtered paths
        if full_path in self.filtered_texture_paths:
            self.current_index = self.filtered_texture_paths.index(full_path)
            #print(f"Current index updated to: {self.current_index}")
        else:
            self.current_index = -1  # No match found
            #print(f"No matching texture found for {full_path}. Current index set to -1.")

    def get_texture_paths(self):
        paths = []
        for root, _, files in os.walk("textures"):
            for file in files:
                if file.lower().endswith(("png", "jpg", "jpeg")):
                    paths.append(os.path.join(root, file))
        return paths

    def get_current_index(self):
        for i, path in enumerate(self.filtered_texture_paths):
            if path not in self.db["textures"]:
                return i
        return len(self.filtered_texture_paths)
    
    def update_texture_label(self, texture_name):
        """Change background color if the file exists."""

        # Construct the file path
        file_path = os.path.join(TARGET_FOLDER, texture_name)
        #print("JOIN2: ", file_path)

        # Check if the file exists and update the background color
        if os.path.isfile(file_path):
            self.texture_name_label.config(bg="green")  # Set background to green
        else:
            self.texture_name_label.config(bg=self.default_bg)  # Reset background to default (None)


    def autocomplete(self, entered_text):
        """Filters the texture list based on the entered text"""
        return [name for name in self.filtered_texture_names_set if name.startswith(entered_text)]

    def show_entry(self, event):
        """Show the entry box and autocomplete list."""
        self.entry_container.place(relx=0.25, rely=0.07, height= 400, width= 400)
        self.texture_name_entry.place(x=0, y=15, width=400)
        
        entered_text = self.texture_name_entry.get()

        matches = self.autocomplete(entered_text)
        self.autocomplete_list.delete(0, tk.END)

        if matches:
            # Populate autocomplete list with matches
            for match in matches:
                self.autocomplete_list.insert(tk.END, match)

            list_height = min(len(matches) * 20, 350)  # Adjust item height dynamically
            self.scrollbar.place(x=385.0, y=45.0, width=15, height=list_height)
            self.autocomplete_list.place(relx=0.0, rely=0.1, width=400, height=list_height)
            

        
        self.entry_container.lift()
        self.autocomplete_list.lift()
        self.scrollbar.lift()

        #print("focusentry")
        self.texture_name_entry.focus_set()
        # Ensure focus is consistently set after a short delay
        self.texture_name_entry.after(1, lambda: self.texture_name_entry.focus_set())

    def on_selected(self, event):
        """Handle selection from the autocomplete list."""
        if isinstance(event.widget, Listbox):
            selection = event.widget.curselection()
            if selection:
                selected_texture_name = event.widget.get(selection[0])
                self.current_selection = selected_texture_name  # Update current selection
                #print(f"Selected: {selected_texture_name}")

                self.update_current_index(selected_texture_name)
                self.display_texture(selected_texture_name)
                self.update_pagination()

                # Hide autocomplete and entry box after selection
                self.texture_name_entry.place_forget()
                self.autocomplete_list.place_forget()
                self.entry_container.place_forget()

    def navigate_autocomplete(self, event):
        """Navigate the autocomplete list with arrow keys."""
        if self.autocomplete_list.size() == 0:
            return  # No items to navigate

        # Get current selection
        current_selection = self.autocomplete_list.curselection()
        new_index = None

        if event.keysym == 'Up':
            if current_selection:
                new_index = max(0, current_selection[0] - 1)  # Move up
            else:
                new_index = self.autocomplete_list.size() - 1  # Wrap to last item
        elif event.keysym == 'Down':
            if current_selection:
                new_index = min(self.autocomplete_list.size() - 1, current_selection[0] + 1)  # Move down
            else:
                new_index = 0  # Start from the first item

        if new_index is not None:
            # Update selection and active item
            self.autocomplete_list.selection_clear(0, tk.END)
            self.autocomplete_list.selection_set(new_index)
            self.autocomplete_list.activate(new_index)
            self.autocomplete_list.see(new_index)  # Ensure visibility by scrolling

            # Update the current selection
            self.current_selection = self.autocomplete_list.get(new_index)

    def handle_keyrelease(self, event):
        """Update autocomplete list based on text entered and handle navigation."""
        entered_text = self.texture_name_entry.get()

        # Avoid clearing matches when using arrow keys
        if event.keysym in ['Up', 'Down']:
            return

        matches = self.autocomplete(entered_text)
        self.autocomplete_list.delete(0, tk.END)

        if matches:
            # Populate autocomplete list with matches
            for match in matches:
                self.autocomplete_list.insert(tk.END, match)

            list_height = min(len(matches) * 20, 350)  # Adjust item height dynamically
            self.scrollbar.place(x=385.0, y=45.0, width=15, height=list_height)
            

            self.autocomplete_list.place(relx=0.0, rely=0.1, width=400, height=list_height)
            self.autocomplete_list.lift()
            self.scrollbar.lift()

            # Reset selection to the first match
            self.autocomplete_list.selection_clear(0, tk.END)
            self.autocomplete_list.selection_set(0)
            self.autocomplete_list.activate(0)
            self.current_selection = matches[0]

    def hide_autocomplete_on_focus_out(self, event=None):
        """Hide the entry container, autocomplete list, and entry box on focus out."""
        if self.entry_container.winfo_ismapped():
            focus_widget = self.root.focus_get()  # `root` is your Tkinter root or main window
            if focus_widget not in (self.texture_name_entry, self.autocomplete_list):
                self.shrink_and_hide_autocomplete()

    def on_entry_return(self, event):
        """Handle Enter key press to select the highlighted item in the Listbox."""
        if self.autocomplete_list.size() > 0:  # Ensure the Listbox has items
            current_selection = self.autocomplete_list.curselection()
            if current_selection:  # If an item in the Listbox is highlighted
                selected_texture_name = self.autocomplete_list.get(current_selection[0])
                self.current_selection = selected_texture_name
                #print(f"Selected: {selected_texture_name}")

                self.update_current_index(selected_texture_name)
                self.display_texture(selected_texture_name)
                self.update_pagination()
            else:
                print("No item highlighted in the Listbox.")
        else:
            print("No items in the Listbox to select.")

        # Hide the entry and autocomplete
        self.shrink_and_hide_autocomplete()

    def shrink_and_hide_autocomplete(self):
        """Shrink the autocomplete list to 1x1 size, then hide it."""
        self.autocomplete_list.place_forget()
        self.entry_container.place_forget()
        self.scrollbar.place_forget()
        self.current_selection = None

    def create_autocomplete_entry(self):
        """Create the entry box and autocomplete list."""
        self.entry_container.place(width=200, height=400)
        self.texture_name_entry = ttk.Entry(self.entry_container, width=250, font=7)
        self.texture_name_entry.bind('<KeyRelease>', self.handle_keyrelease)
        self.texture_name_entry.bind('<Return>', self.on_entry_return)
        self.texture_name_entry.bind('<Up>', self.navigate_autocomplete)
        self.texture_name_entry.bind('<Down>', self.navigate_autocomplete)

        #self.texture_name_entry.bind('<FocusOut>', self.hide_autocomplete_on_focus_out)

        self.autocomplete_list = tk.Listbox(self.entry_container, height=10)  # Adjust as needed
        self.scrollbar = tk.Scrollbar(self.entry_container, command=self.autocomplete_list.yview)
        self.autocomplete_list.config(yscrollcommand=self.scrollbar.set)

       


        self.autocomplete_list.bind('<<ListboxSelect>>', self.on_selected)
        #self.autocomplete_list.bind('<FocusOut>', self.hide_autocomplete_on_focus_out)

        self.entry_container.place(relx=0.25, rely=0.07, height= 500, width= 400)
        self.texture_name_entry.place(x=0, y=15, width=400)
        
        entered_text = self.texture_name_entry.get()

        matches = self.autocomplete(entered_text)
        self.autocomplete_list.delete(0, tk.END)

        if matches:
            # Populate autocomplete list with matches
            for match in matches:
                self.autocomplete_list.insert(tk.END, match)

            list_height = min(len(matches) * 20, 350)  # Adjust item height dynamically
             # Place the listbox and scrollbar together
            self.scrollbar.place(x=385.0, y=45.0, width=15, height=list_height)  # Adjusted for proper alignment
            self.autocomplete_list.place(relx=0.0, rely=0.1, width=400, height=list_height)
            self.autocomplete_list.lift()
            self.scrollbar.lift()


    

        # Start shrunk and hidden
        self.shrink_and_hide_autocomplete()
    
    def global_click_handler(self, event):
        """Handle global mouse clicks to hide the autocomplete."""
        widget = event.widget

        # List of widgets that should not trigger hiding
        allowed_widgets = (self.texture_name_entry, self.autocomplete_list, self.texture_name_label)

        # Hide if clicking outside the allowed widgets
        if widget not in allowed_widgets:
            self.shrink_and_hide_autocomplete()


    def switch_slot(self, slot_name):
        self.selected_slot = slot_name
        #print(f"Switched to slot: {slot_name}")  # Debugging
        self.update_selected_thumbnails_count()  # Update preview


    def create_buttons(self):
        for index, (key, value) in enumerate(self.button_info.items()):
            button = Button(self.button_frame, font=7, text=value, command=lambda key=key: self.toggle_button(key))
            button.grid(row=0, column=index, padx=10)
            self.buttons[key] = button

            # Create a frame for the labels
            frame = Frame(self.button_frame)
            frame.grid(row=1, column=index, padx=10)
            self.label_frames[key] = frame

            # Add the 'assigned' label
            self.label_frames[f"{key}_assigned"] = Label(frame, text="0", fg="blue", font=5)
            self.label_frames[f"{key}_assigned"].pack(side="left")

            Label(frame, text="/").pack(side="left")
            
            # Add the 'tagged' label
            self.label_frames[f"{key}_tagged"] = Label(frame, font=5, text="0", fg="green")
            self.label_frames[f"{key}_tagged"].pack(side="left")
            
            Label(frame, text="/").pack(side="left")
            
            # Add the 'untagged' label
            self.label_frames[f"{key}_untagged"] = Label(frame, font=5, text="0", fg="red")
            self.label_frames[f"{key}_untagged"].pack(side="left")
            
    def update_counts(self):
        """Update the counts for each button and label, including 'assigned', handling case differences."""
        counts = {key: {"tagged": 0, "untagged": 0, "assigned": 0} for key in self.button_info}

        #print(f"DEBUG: button_info keys: {list(self.button_info.keys())}")

        for path in self.texture_paths:
            tags = self.db["textures"].get(path, {}).get("tags", [])
            selected_thumbnails = self.db["textures"].get(path, {}).get("selected_thumbnails", [])
            filename_casefold = os.path.basename(path).casefold()  # Normalize to casefold for comparison


            for key in self.button_info:
                key_casefold = key.casefold()  # Normalize key with casefold


                if filename_casefold.startswith(key_casefold):
                    #print(f"DEBUG: Match found - Filename: '{filename_casefold}' matches Key: '{key_casefold}' in ' {key} ")

                    if tags:
                        counts[key]["tagged"] += 1
                    else:
                        counts[key]["untagged"] += 1

                    if selected_thumbnails:
                        counts[key]["assigned"] += 1

        # Update counts on labels
        for key, count in counts.items():
            self.label_frames[f"{key}_tagged"].config(text=str(count["tagged"]))
            self.label_frames[f"{key}_untagged"].config(text=str(count["untagged"]))

            # Update the 'assigned' label dynamically
            if f"{key}_assigned" in self.label_frames:
                self.label_frames[f"{key}_assigned"].config(text=str(count["assigned"]))

        # Misc counts
        misc_tagged = sum(
            1 for path in self.texture_paths
            if not any(os.path.basename(path).lower().startswith(key.lower()) for key in self.button_info)
            and self.db["textures"].get(path, {}).get("tags")
        )
        misc_untagged = sum(
            1 for path in self.texture_paths
            if not any(os.path.basename(path).lower().startswith(key.lower()) for key in self.button_info)
            and not self.db["textures"].get(path, {}).get("tags")
        )
        misc_assigned = sum(
            1 for path in self.texture_paths
            if not any(os.path.basename(path).lower().startswith(key.lower()) for key in self.button_info)
            and self.db["textures"].get(path, {}).get("selected_thumbnails", [])
        )

        self.misc_label_tagged.config(text=str(misc_tagged))
        self.misc_label_untagged.config(text=str(misc_untagged))
        if hasattr(self, "misc_label_assigned"):
            self.misc_label_assigned.config(text=str(misc_assigned))

        # All counts
        all_tagged = sum(
            1 for path in self.texture_paths if self.db["textures"].get(path, {}).get("tags")
        )
        all_untagged = len(self.texture_paths) - all_tagged
        all_assigned = sum(
            1 for path in self.texture_paths
            if self.db["textures"].get(path, {}).get("selected_thumbnails", [])
        )

        self.all_label_tagged.config(text=str(all_tagged))
        self.all_label_untagged.config(text=str(all_untagged))
        if hasattr(self, "all_label_assigned"):
            self.all_label_assigned.config(text=str(all_assigned))

    def update_selected_thumbnails_count(self):
        """Update the count of selected thumbnails for the current texture and adjust slot buttons."""
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Retrieve selected thumbnails for the current texture
        selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
        #print("PATH: ", texture_path)
        #print(f"Selected thumbnails: {selected_thumbnails}")

        # Set a default selected slot if none is set or out of range
        if len(selected_thumbnails) > 0:
            if not self.selected_slot or ord(self.selected_slot) - ord('A') >= len(selected_thumbnails):
                self.selected_slot = 'A'  # Default to the first slot
        else:
            self.selected_slot = None  # Clear selected slot if no thumbnails are available

        # Adjust the slot buttons based on the number of selected thumbnails
        for index, (slot_name, button) in enumerate(self.slot_buttons.items()):
            if index < len(selected_thumbnails):
                # Show the button and update its text
                button.config(text=slot_name, state="normal")
                button.grid()  # Make sure it's visible

                # Highlight the currently selected slot
                if slot_name == self.selected_slot:
                    button.config(bg="lightblue")  # Active color
                else:
                    button.config(bg="SystemButtonFace")  # Default color
            else:
                # Hide the button if there are no thumbnails for this slot
                button.grid_remove()

        # Update the preview for the currently selected slot
        if self.selected_slot and selected_thumbnails:
            # Map slot (A, B, C, D) to index
            slot_index = ord(self.selected_slot) - ord('A')
            if 0 <= slot_index < len(selected_thumbnails):
                thumbnail_name = selected_thumbnails[slot_index]
                thumbnail_name = self.get_key_by_name(self.all_assets, thumbnail_name)
                normalized_name = thumbnail_name.lower().replace(" ", "_")
                thumbnail_path = f"thumbnails\\{normalized_name}.png"
                #print(f"Slot: {self.selected_slot}, Thumbnail path: {thumbnail_path}")

                # Load and display the thumbnail
                if os.path.exists(thumbnail_path):
                    try:
                        image = Image.open(thumbnail_path)

                        # Get current dimensions
                        width, height = image.size

                        # Scale by 1.5x
                        new_width = int(width * 1.5)
                        new_height = int(height * 1.5)

                        # Resize the image
                        image_resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)  # Resizes with high-quality filtering
                        

                        thumb_photo = ImageTk.PhotoImage(image_resized)
                        self.preview_label.config(image=thumb_photo, text="")
                        self.preview_label.image = thumb_photo  # Prevent garbage collection
                    except Exception as e:
                        print(f"Error opening : {e}")
                else:
                    print(f"Thumbnail path not found: {thumbnail_path}")
            else:
                print(f"No thumbnail for slot {self.selected_slot}")
        else:
            # Clear the preview if no slot or no thumbnails
            self.preview_label.config(image='', text="No Preview")
            self.preview_label.image = None

        # Update the label
        count = len(selected_thumbnails)
        self.selected_thumbnails_label.config(text=f"Selected Thumbnails: {count}")


    def display_thumbnails(self):
        """Display selectable thumbnails of textures from Polyhaven."""
        #start_time = time.time()
        #print("Starting display_thumbnails...")

        # Clear previous thumbnails
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        #print(f"Time to clear thumbnails: {time.time() - start_time:.4f} seconds")

        # Get matching textures for the current texture
        matching_textures = self.get_matching_textures()

        # Paginate the thumbnails (show 5 at a time)
        start_index = self.current_thumbnail_index
        end_index = start_index + 5
        paginated_textures = matching_textures[start_index:end_index]
        #print(json.dumps(matching_textures, indent=4))

        if not paginated_textures:
            no_results_label = Label(self.thumbnail_frame, text="No matching thumbnails found.", font=("Arial", int(12 * scale_factor)))
            no_results_label.pack(pady=10)
            self.update_selected_thumbnails_count()
            return

        # Display thumbnails and tags for each matching texture
        for col, texture in enumerate(paginated_textures):
            thumbnail_url = texture.get("thumbnail_url")
            texture_id = texture.get("name")  # Unique ID for the texture
            
            texture_tags = texture.get("tags", [])

            if thumbnail_url:
                try:
                    # Fetch the thumbnail (use caching)
                    thumb_img = fetch_thumbnail(thumbnail_url)
                    if thumb_img:
                        thumb_img.thumbnail((512, 512))  # Adjust thumbnail size for display

                        # Get current dimensions
                        width, height = thumb_img.size

                        # Scale by 1.5x
                        new_width = int(width * 1.5)
                        new_height = int(height * 1.5)

                        # Resize the image
                        thumb_resized = thumb_img.resize((new_width, new_height), Image.Resampling.LANCZOS)  # Resizes with high-quality filtering

                        thumb_photo = ImageTk.PhotoImage(thumb_resized)

                        # Create a fixed-size container for thumbnail and tags
                        thumb_container = Frame(
                            self.thumbnail_frame,
                            borderwidth=2,
                            relief="solid",
                            highlightbackground="gray",
                            highlightthickness=2,
                            bg="black"
                        )
                        
                        thumb_container.grid(row=0, column=col, padx=10, pady=5, sticky="N")
                        thumb_container.grid_propagate(False)  # Prevent resizing

                        # Display the thumbnail image
                        thumb_label = Label(thumb_container, image=thumb_photo, width=400, height=400, bg="black")
                        thumb_label.image = thumb_photo  # Keep reference to prevent garbage collection
                        thumb_label.pack(pady=5)
                      

                        # Display texture tags
                        tags_label = Label(
                            thumb_container,
                            text=", ".join(texture_tags),
                            wraplength=250,  # Ensure text wraps within the container
                            font=("Arial", int(8)),
                            justify="center",
                            height=4
                        )
                        thumb_label.pack(fill=None, expand=False)
                        tags_label.pack(pady=5)

                        # Handle click to select/unselect thumbnail
                        def on_click(event=None, texture_id=texture_id, container=thumb_container):
                            self.toggle_selection(texture_id, container)
                            self.update_selected_thumbnails_count()

                        # Bind click event to the entire container
                        thumb_container.bind("<Button-1>", on_click)
                        thumb_label.bind("<Button-1>", on_click)
                        tags_label.bind("<Button-1>", on_click)

                        # Highlight if already selected
                        texture_path = self.filtered_texture_paths[self.current_index]
                        selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
                        #print(f"Current Texture Path: {texture_path}")
                        #print(f"Selected Thumbnails: {selected_thumbnails}")
                        #print(f"Checking Texture ID: {texture_id}")
                        if texture_id in selected_thumbnails:
                            thumb_container.config(highlightbackground="blue", highlightthickness=2)

                except Exception as e:
                    print(f"Error loading thumbnail from {thumbnail_url}: {e}")
        # Update the selected thumbnails count
        self.update_selected_thumbnails_count()

    def toggle_selection(self, texture_id, container):
        """Toggle selection of a thumbnail for the current texture and update the database."""
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Ensure selected_thumbnails is initialized
        texture_data = self.db["textures"].setdefault(texture_path, {})
        selected_thumbnails = texture_data.setdefault("selected_thumbnails", [])

        if texture_id in selected_thumbnails:
            # Deselect
            selected_thumbnails.remove(texture_id)
            container.config(highlightbackground="gray", highlightthickness=2)
        else:
            # Select
            selected_thumbnails.append(texture_id)
            container.config(highlightbackground="blue", highlightthickness=2)

        # Save changes to the database
        save_database(self.db)
        self.update_counts()

    def next_thumbnails(self):
        # Update the index and display thumbnails
        total_thumbnails = len(self.get_matching_textures())
        self.current_thumbnail_index = min(self.current_thumbnail_index + 5, total_thumbnails - 1)

         # Calculate the current page and total pages
        thumbnails_per_page = 5
        current_page = (self.current_thumbnail_index // thumbnails_per_page) + 1
        total_pages = (total_thumbnails // thumbnails_per_page) + (1 if total_thumbnails % thumbnails_per_page > 0 else 0)
        
        # Update the page indicator
        self.page_indicator.config(text=f"{current_page}/{total_pages}")
        
        self.display_thumbnails()

    def previous_thumbnails(self):
        """Show the next set of thumbnails."""
        total_thumbnails = len(self.get_matching_textures())
        self.current_thumbnail_index = max(self.current_thumbnail_index - 5, 0)

        # Calculate the current page and total pages
        thumbnails_per_page = 5
        current_page = (self.current_thumbnail_index // thumbnails_per_page) + 1
        total_pages = (total_thumbnails // thumbnails_per_page) + (1 if total_thumbnails % thumbnails_per_page > 0 else 0)
        
        # Update the page indicator
        self.page_indicator.config(text=f"{current_page}/{total_pages}")
    
        self.display_thumbnails()


    def display_texture(self, entered_texture_name=None):
        """Update the texture based on the user input."""
        texture_path = None

        # Determine the texture path based on the user input or the current index
        if entered_texture_name is not None:
            for path in self.filtered_texture_paths:
                if os.path.basename(path).startswith(entered_texture_name):
                    texture_path = path
                    break
            if texture_path is None:
                print(f"Texture not found: {entered_texture_name}")
                self.texture_name_label.config(text="Texture: Not Found")
                self.image_label.config(image=None)  # Clear image
                return
        else:
            texture_path = self.filtered_texture_paths[self.current_index]

        texture_name = os.path.basename(texture_path)

        # Update the texture name label
        self.texture_name_label.config(text=f"Texture: {texture_name}")

        texture_name_result = texture_name.replace("_result", "")
        self.update_texture_label(texture_name_result)

        selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])

        # Ensure selected_slot is valid
        if len(selected_thumbnails) > 0:
            if not self.selected_slot or not isinstance(self.selected_slot, str) or len(self.selected_slot) != 1 or ord(self.selected_slot) - ord('A') >= len(selected_thumbnails):
                self.selected_slot = 'A'  # Default to the first slot
        else:
            self.selected_slot = None  # Clear selected slot if no thumbnails are available

        # Calculate slot_index only if self.selected_slot is valid
        if self.selected_slot:
            slot_index = ord(self.selected_slot) - ord('A')
        else:
            slot_index = None  # No valid index

        # Validate slot_index before accessing selected_thumbnails
        if slot_index is not None and 0 <= slot_index < len(selected_thumbnails):
            #print("SLOT:", slot_index)
            thumbnail_name = selected_thumbnails[slot_index]
            thumbnail_name = os.path.basename(thumbnail_name).replace(" ", "_").lower()

            # Construct the full paths for both _diff_overlay and _col_overlay

            thumbnail_name = os.path.basename(thumbnail_name)
            diff_overlay_path = os.path.join(OVERLAY_FOLDER, f"{thumbnail_name}_diff_4k_overlay.png")
            col_overlay_path = os.path.join(OVERLAY_FOLDER, f"{thumbnail_name}_col_4k_overlay.png")

            print(diff_overlay_path)
            print(col_overlay_path)

            # Check for existence of overlay images
            overlay_path = None
            if os.path.exists(diff_overlay_path):
                overlay_path = diff_overlay_path
            elif os.path.exists(col_overlay_path):
                overlay_path = col_overlay_path

            if overlay_path:
                print(f"Using overlay: {overlay_path}")
            else:
                print(f"No overlay match found for: {thumbnail_name}")
        else:
            #print("Invalid slot index or no thumbnails available.")
            overlay_path = None

        # Load the zoom image (used as the base image)
        zoom_image = self.load_image(texture_path)
        if zoom_image is None:
            print(f"Failed to load zoom image: {texture_path}")
            return

        # Load the overlay image if available
        if overlay_path:
            overlay_image = self.load_image(overlay_path)
            if overlay_image is not None:
                # Combine the overlay with the zoom image (as the base)
                image = self.combine_overlay(zoom_image, overlay_image)
            else:
                print(f"Failed to load overlay image: {overlay_path}")
                image = zoom_image
        else:
            image = zoom_image

        # Prepare the resized version (for display)
        display_image = self.prepare_display_image(image)
        self.full_res_image = Image.fromarray(image)
        # Save the display size for zoom preview calculations
        self.display_image_size = display_image.size

        # Display the image
        photo = ImageTk.PhotoImage(display_image)
        self.image_label.config(image=photo)
        self.image_label.image = photo

        # Limit the width, allow overflow
        max_width = 512  # Set your desired maximum width here
        self.image_label.config(width=max_width)

        # Clear and display tags
        self.tags_listbox.delete(0, END)
        stored_tags = self.db["textures"].get(texture_path, {}).get("tags", [])
        for tag in stored_tags:
            self.tags_listbox.insert(END, tag)

        # Display thumbnails of related textures
        self.display_thumbnails()

    def load_image(self, image_path):
        """Load and process an image if it exists."""
        if os.path.isfile(image_path):
            image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                print(f"Failed to load image: {image_path}")
                return None

            # Normalize bit depth if needed (for overlays, e.g., 16-bit images)
            if image.dtype == np.uint16:  # 16-bit or 48-bit image
                image = (image / 256).astype(np.uint8)

            # Convert to RGBA
            if image.ndim == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGBA)
            elif image.shape[2] == 3:  # BGR
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)
            elif image.shape[2] == 4:  # BGRA
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)

            return image
        return None

    def combine_overlay(self, base_image, overlay_image):
        """Combine overlay image with the base image (zoom image)."""
        combined_image = np.copy(base_image)  # Start with the base image (zoom image)
        overlay_y_offset = base_image.shape[0] // 2  # Overlay at 50% vertical position
        combined_image[overlay_y_offset:, :, :] = overlay_image[overlay_y_offset:, :, :]
        return combined_image

    def prepare_display_image(self, image):
        """Resize the image for display while preserving aspect ratio."""
        base_height = 480
        aspect_ratio = image.shape[1] / image.shape[0]
        new_width = int(base_height * aspect_ratio)
        display_image = cv2.resize(image, (new_width, base_height), interpolation=cv2.INTER_LINEAR)

        # Convert to PIL for Tkinter compatibility
        return Image.fromarray(display_image)

    def show_zoom_preview(self, event):
        """Show a zoomed-in preview of the image where the mouse hovers."""
        if not hasattr(self, "full_res_image") or not self.full_res_image:
            return

        # Ensure display size is set
        if not hasattr(self, "display_image_size"):
            print("Display image size not set.")
            return

        # Calculate the mouse position relative to the display image
        # Calculate the mouse position relative to the display image
        display_width, display_height = self.display_image_size
        full_width, full_height = self.full_res_image.size
        x_ratio = full_width / display_width
        y_ratio = full_height / display_height

        # Determine the corresponding coordinates in the full-resolution image
        full_x = int(event.x * x_ratio)
        full_y = int(event.y * y_ratio)

        # Define the size of the zoom preview box
        zoom_box_size = 200  # Fixed size for consistent zoom
        half_box_size = zoom_box_size // 2

        # Adjust to keep the zoom box inside the image boundaries
        left = full_x - half_box_size
        right = full_x + half_box_size
        upper = full_y - half_box_size
        lower = full_y + half_box_size

        # Shift the box if it goes out of bounds
        if left < 0:
            right += abs(left)  # Push right side to maintain size
            left = 0
        if right > full_width:
            left -= (right - full_width)
            right = full_width

        if upper < 0:
            lower += abs(upper)  # Push lower side to maintain size
            upper = 0
        if lower > full_height:
            upper -= (lower - full_height)
            lower = full_height

        # Crop the zoom box from the full-resolution image
        zoom_box = self.full_res_image.crop((left, upper, right, lower))

        # Resize the zoom box for display
        zoom_box = zoom_box.resize((300, 300), Image.LANCZOS)  # High-quality scaling
        zoom_photo = ImageTk.PhotoImage(zoom_box)

        # Create a label to show the zoom preview
        if not hasattr(self, "zoom_label"):
            self.zoom_label = tk.Label(self.root, bg="white", bd=1, relief="solid")

        self.zoom_label.config(image=zoom_photo)
        self.zoom_label.image = zoom_photo
        self.zoom_label.place(x=event.x_root + 10, y=event.y_root + 10)

    def hide_zoom_preview(self, event):
        """Hide the zoom preview when the mouse leaves the image."""
        if hasattr(self, "zoom_label"):
            self.zoom_label.place_forget()

    def next_texture(self):
        if self.current_index < len(self.filtered_texture_paths) - 1:
            self.current_index += 1
            self.update_pagination()
            self.display_texture()

    def previous_texture(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_pagination()
            self.display_texture()

    def add_tag(self):
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]
        
        # Retrieve the input from the tag entry widget
        new_tag = self.tag_entry.get().strip()  # Corrected variable name
        if new_tag:
            # Safely retrieve existing tags or initialize if missing
            texture_data = self.db["textures"].setdefault(texture_path, {})
            existing_tags = texture_data.setdefault("tags", [])
            
            # Add the new tag if it doesn't exist
            if new_tag not in existing_tags:
                existing_tags.append(new_tag)
                
                # Save changes to the database
                save_database(self.db)
                
                # Update the tags displayed in the listbox
                self.tags_listbox.insert(END, new_tag)
        else:
            messagebox.showwarning("Input Error", "Please enter a tag.")
        
        # Refresh counts and UI
        self.update_counts()

    def remove_tag(self):
        texture_path = self.filtered_texture_paths[self.current_index]
        selected_indices = self.tags_listbox.curselection()
        if selected_indices:
            selected_tag = self.tags_listbox.get(selected_indices[0])
            self.tags_listbox.delete(selected_indices[0])

            existing_tags = self.db["textures"].get(texture_path, {}).get("tags", [])
            if selected_tag in existing_tags:
                existing_tags.remove(selected_tag)
                self.db["textures"][texture_path]["tags"] = existing_tags
                save_database(self.db)
        self.update_counts()

    def toggle_button(self, tag):
        """Toggle the filter for the selected tag."""
        if tag in self.active_buttons:
            self.active_buttons.remove(tag)
            self.buttons[tag].config(bg="lightgray")  # Set to inactive color
        else:
            self.active_buttons.add(tag)
            self.buttons[tag].config(bg="lightblue")  # Set to active color

        self.apply_filters()
        self.update_pagination()

    def update_pagination(self):
        # Get the total number of thumbnails and calculate the total pages
        total_thumbnails = len(self.get_matching_textures())
        thumbnails_per_page = 5
        total_pages = (total_thumbnails // thumbnails_per_page) + (1 if total_thumbnails % thumbnails_per_page > 0 else 0)
        
        # Calculate the current page
        current_page = (self.current_thumbnail_index // thumbnails_per_page) + 1
        
        # Update the page indicator label
        self.page_indicator.config(text=f"{current_page}/{total_pages}")

    def apply_filters(self):
        if self.active_buttons:
            self.filtered_texture_paths = [
                path for path in self.texture_paths
                if any(os.path.basename(path).casefold().startswith(tag.casefold()) for tag in self.active_buttons)
            ]
        else:
            self.filtered_texture_paths = self.texture_paths
        
        self.current_index = 0
        self.display_texture()

    def toggle_all_buttons(self):
        """Toggle all filters on or off."""
        if len(self.active_buttons) == len(self.button_info):  # All active, deactivate all
            self.active_buttons.clear()
            for key in self.button_info:
                self.buttons[key].config(bg="lightgray")  # Set all to inactive color
        else:  # Not all active, activate all
            self.active_buttons = set(self.button_info.keys())
            for key in self.button_info:
                self.buttons[key].config(bg="lightblue")  # Set all to active color

        self.apply_filters()

    def show_all_textures(self):
        """Filter and display only miscellaneous textures."""
        # Clear all active buttons first
        self.active_buttons.clear()

        # Update all button colors to inactive
        for button in self.buttons.values():
            button.config(bg="lightgray")

        # Highlight the Misc button
        self.misc_button.config(bg="lightblue")

        # Filter textures that don't match any specific category
        self.filtered_texture_paths = [
            path for path in self.texture_paths
            if not any(os.path.basename(path).startswith(key) for key in self.button_info)
        ]

        # Reset the current index and display the first texture
        self.current_index = 0
        self.display_texture()

    def get_matching_textures(self):
        """Retrieve textures from the Polyhaven API that match the tags of the current texture."""
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Retrieve tags for the current texture
        current_tags = self.db["textures"].get(texture_path, {}).get("tags", [])
        if not current_tags:
            return []  # No tags, no matching textures

        # Fetch all assets from Polyhaven
        all_textures = self.all_assets or fetch_api_data("https://api.polyhaven.com/assets?type=textures")
        if not all_textures:
            return []  # No textures fetched, return empty

        # Filter assets by matching tags and store each texture as an object
        matching_textures = [
            texture  # The whole texture object will be stored, including the 'id' field
            for texture in all_textures.values()
            if any(tag in texture.get("tags", []) for tag in current_tags)
        ]

        return matching_textures



    def add_all_to_queue(self):
        """Add all textures and their selected thumbnails to the download queue, with confirmation."""
        if not self.filtered_texture_paths:
            messagebox.showerror("Error", "No textures available to add to the queue.")
            return

        for texture_path in self.filtered_texture_paths:
            selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])

            # Ensure there are selected thumbnails for the texture
            if not selected_thumbnails:
                print(f"[DEBUG] No thumbnails found for texture: {texture_path}")
                continue

            for slot_index, thumbnail_name in enumerate(selected_thumbnails):
                texture_name_label = os.path.basename(texture_path).replace(".png", "")
                
                # Add to the queue
                self.download_queue.append((texture_path, thumbnail_name, texture_name_label))

        # Confirmation dialog
        confirm = messagebox.askyesno(
            "Confirm Add All",
            f"This will add {len(self.download_queue)} textures to the queue. Do you want to proceed?"
        )
        if not confirm:
            return

        # Print debug information
        print(f"[DEBUG] Added all textures to queue. Current Queue Length: {len(self.download_queue)}")

        # Start processing the queue if idle
        if not self.currently_downloading:
            self.process_queue()

        self.update_progress_label()

    def add_to_queue(self):
        """Add the selected thumbnail and texture label to the download queue."""
        if not self.selected_slot:
            messagebox.showerror("Error", "No slot selected for download.")
            return

        # Get the current texture and thumbnail
        current_texture = self.filtered_texture_paths[self.current_index]
        selected_thumbnails = self.db["textures"].get(current_texture, {}).get("selected_thumbnails", [])

        # Determine the thumbnail name based on the selected slot
        slot_index = ord(self.selected_slot) - ord('A')
        if slot_index < 0 or slot_index >= len(selected_thumbnails):
            messagebox.showerror("Error", f"No thumbnail found for slot {self.selected_slot}.")
            return

        thumbnail_name = selected_thumbnails[slot_index]
        texture_name_label = os.path.basename(current_texture).replace(".png", "")

        # Add to the queue
        self.download_queue.append((current_texture, thumbnail_name, texture_name_label))
        #print(f"[DEBUG] Added to queue: path: {current_texture}, Texture: {texture_name_label}, Thumbnail: {thumbnail_name}")
        #print(f"[DEBUG] Current Queue Length: {len(self.download_queue)}")

        # Start processing the queue if idle
        if not self.currently_downloading:
            self.process_queue()

        self.update_progress_label()

    def show_queue(self):
        """Display the current download queue with progress states and debug information."""
        # Ensure completed_downloads, in_progress, and pending exist
        if not hasattr(self, "completed_downloads"):
            self.completed_downloads = []
        if not hasattr(self, "in_progress"):
            self.in_progress = []
        
        # Debugging information
        total_completed = len(self.completed_downloads)
        total_in_progress = len(self.in_progress)
        total_pending = len(self.download_queue)
        total_items = total_completed + total_in_progress + total_pending

        # Build the queue display
        queue_text = f"Total Items: {total_items} (Completed: {total_completed}, In Progress: {total_in_progress}, Pending: {total_pending})\n\n"

        # Add completed downloads
        queue_text += "Completed:\n"
        if total_completed > 0:
            for texture_path, thumbnail_name, texture_name_label in self.completed_downloads:
                queue_text += f"  - Texture: {texture_name_label}, Thumbnail: {thumbnail_name} [finished]\n"
        else:
            queue_text += "  None\n"

        # Add in-progress item
        queue_text += "\nIn Progress:\n"
        if total_in_progress > 0:
            for texture_path, thumbnail_name, texture_name_label in self.in_progress:
                queue_text += f"  - Texture: {texture_name_label}, Thumbnail: {thumbnail_name} [in progress]\n"
        else:
            queue_text += "  None\n"

        # Add pending items
        queue_text += "\nPending:\n"
        if total_pending > 0:
            for texture_path, thumbnail_name, texture_name_label in self.download_queue:
                queue_text += f"  - Texture: {texture_name_label}, Thumbnail: {thumbnail_name}\n"
        else:
            queue_text += "  None\n"

        # Debugging output
        #print("[DEBUG] Completed Downloads:", self.completed_downloads)
        #print("[DEBUG] In Progress:", self.in_progress)
        #print("[DEBUG] Pending Downloads:", self.download_queue)
        #print(f"[DEBUG] Current Queue Length: {len(self.download_queue)}")
        #print("[DEBUG] Queue Text:", queue_text)

        # Display the queue in a message box
        messagebox.showinfo("Download Queue", queue_text)

    def update_progress_label(self):
        """Update the progress label with the current counts of completed, in-progress, and pending downloads."""
        completed_count = len(self.completed_downloads)
        in_progress_count = len(self.in_progress)
        pending_count = len(self.download_queue)
        
        self.progress_label.config(
            text=f"Completed: {completed_count}, In Progress: {in_progress_count}, Pending: {pending_count}"
        )

    def process_queue(self):
        """Start processing the download queue."""
        if not self.download_queue:
            self.currently_downloading = False  # No more items in the queue
            messagebox.showinfo("Queue", "All downloads completed.")
            return

        # Get the next item from the queue and remove it
        next_item = self.download_queue.pop(0)
        next_texture, next_thumbnail, next_texture_name_label = next_item

        #print("DEBUG", next_texture)

        # Move this item to 'in progress'
        self.in_progress.append(next_item)

        # Start the download for this texture, thumbnail, and texture name label
        self.currently_downloading = True

        self.update_progress_label()  # Update after moving item to in-progress

        self.download_texture(next_texture, next_thumbnail, next_texture_name_label)
        #print("[DEBUG] texture:", next_texture)
        #print("[DEBUG] thumbnail:", next_thumbnail)
        #print("[DEBUG] name label:", next_texture_name_label)

        # Debugging output for current queue state
        #print("[DEBUG] Completed Downloads:", self.completed_downloads)
        #print("[DEBUG] In Progress:", self.in_progress)
        #print("[DEBUG] Pending Downloads:", self.download_queue)


    def download_texture(self, texture_path, thumbnail_name, texture_name_label):
        """Start the download process for a specific texture, thumbnail, and label."""
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 100  # Assume 100 steps for simplicity

        # Reset progress tracking
        self.actual_progress = 0
        self.smoothed_progress = 0

        def smooth_progress_update():
            """Gradually update the progress bar."""
            if self.smoothed_progress < self.actual_progress:
                self.smoothed_progress += (self.actual_progress - self.smoothed_progress) * 0.1
                self.progress_bar["value"] = min(self.smoothed_progress, 100)
            if self.smoothed_progress < 100:
                self.root.after(50, smooth_progress_update)

        # Start smooth progress update
        smooth_progress_update()

        # Start the download in a separate thread
        download_thread = threading.Thread(
            target=self._perform_download, args=(texture_path, thumbnail_name, texture_name_label), daemon=True
        )
        download_thread.start()

    def get_key_by_name(self, dictionary, target_name):
        for key, value in dictionary.items():
            if value.get("name") == target_name:  # Check if the 'name' matches the target
                return key
        return None  # Return None if no match is found
   
    def calculate_md5(self, file_path):
        """Calculate the MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as file:
                for chunk in iter(lambda: file.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except FileNotFoundError:
            return None

    def _perform_download(self, texture_path, thumbnail_name, texture_name_label):
        """Perform the actual download process for a specific texture and thumbnail."""
        try:
            texture_id = thumbnail_name
            texture_id_download = self.get_key_by_name(self.all_assets, thumbnail_name)

            texture_path = os.path.normpath(texture_path.strip())
            texture_name_label = texture_name_label.strip()

            # Construct the download URL
            url = f"https://api.polyhaven.com/files/{texture_id_download}"

            # Create the "staging" folder if it doesn't exist
            if not os.path.exists("staging"):
                os.makedirs("staging")
            
            # Fetch texture metadata
            data = requests.get(url)
            if data.status_code != 200:
                messagebox.showerror("Error", f"Failed to fetch texture metadata for '{texture_id}'. Status code: {data.status_code}")
                return

            # Extract URLs and MD5 checksums
            texture_files = self.extract_files_with_md5(data.json())

            # Filter files based on required file types
            required_files = ["_diff_4k.png", "_color_4k.png", "_nor_dx_4k.png", "_arm_4k.png", "_disp_4k.png", "_height_4k.png"]
            filtered_files = {
                file_info['url']: file_info['md5']
                for file_info in texture_files
                if any(required_file in file_info['url'] for required_file in required_files)
            }

            if not filtered_files:
                messagebox.showerror("Error", f"No valid files to download for '{thumbnail_name}'.")
                return

            # Set the progress bar maximum value
            self.progress_bar["maximum"] = len(filtered_files)

            # Download files
            for idx, (texture_url, md5_hash) in enumerate(filtered_files.items()):
                # Update the progress bar
                self.actual_progress = idx + 1

                # Sanitize the URL to create a valid filename
                sanitized_filename = self.sanitize_filename(texture_url)
                file_path = os.path.join("staging", sanitized_filename)

                # Check if the file already exists and matches the MD5 hash
                if os.path.exists(file_path) and self.calculate_md5(file_path) == md5_hash:
                    print(f"File already exists and matches MD5: {file_path}")
                    continue

                # Download the texture
                response = requests.get(texture_url)
                if response.status_code == 200:
                    with open(file_path, "wb") as file:
                        file.write(response.content)
                else:
                    print(f"Failed to download: {texture_url} (Status: {response.status_code})")

            # Combine the downloaded textures
            self.combine_textures(texture_path, thumbnail_name, texture_name_label)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during download: {e}")

        finally:
            try:
                # Update the progress label
                self.update_progress_label()
                # Debug: Check tuple being removed
                normalized_tuple = (texture_path, thumbnail_name, texture_name_label)
                #print("[DEBUG] Trying to remove (normalized):", repr(normalized_tuple))

                # Debug: Print in-progress list
                #print("[DEBUG] Full In Progress List (normalized):", [repr((os.path.normpath(item[0]), item[1].strip(), item[2].strip())) for item in self.in_progress])

                # Remove from in-progress and add to completed
                if normalized_tuple in self.in_progress:
                    self.in_progress.remove(normalized_tuple)
                    #print("[DEBUG] Successfully removed:", repr(normalized_tuple))
                else:
                    print("[DEBUG] Item not found in in_progress for removal:", repr(normalized_tuple))

                self.completed_downloads.append(normalized_tuple)
                #print("[DEBUG] Added to completed_downloads:", repr(normalized_tuple))
            except Exception as e:
                print(f"[DEBUG] Error during in_progress removal or completion update: {e}")

            # Check if there are more items in the queue
            if self.download_queue:
                # Process the next item in the queue
                self.process_queue()
            else:
                self.currently_downloading = False
                messagebox.showinfo("Queue", "All downloads completed.")

            # Debugging output
            #"[DEBUG] Completed Downloads:", self.completed_downloads)
            #print("[DEBUG] In Progress:", self.in_progress)
            #print("[DEBUG] Pending Downloads:", self.download_queue)

            # Ensure the UI is updated
            self.root.update_idletasks()

    def extract_files_with_md5(self, json_data):
        """Extract URLs and their MD5 hashes from the JSON response."""
        files_with_md5 = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if key == "url" and "md5" in json_data:
                    files_with_md5.append({"url": value, "md5": json_data["md5"]})
                elif isinstance(value, dict) or isinstance(value, list):
                    files_with_md5.extend(self.extract_files_with_md5(value))
        elif isinstance(json_data, list):
            for item in json_data:
                files_with_md5.extend(self.extract_files_with_md5(item))
        return files_with_md5

    def extract_urls(self, json_data):
        """
        Recursively extracts all URLs from the JSON response.
        """
        urls = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if isinstance(value, dict) or isinstance(value, list):
                    # Recursively extract URLs from nested dictionaries/lists
                    urls.extend(self.extract_urls(value))
                elif isinstance(value, str) and value.startswith("http"):
                    # Check if the value is a URL and add it to the list
                    urls.append(value)
        elif isinstance(json_data, list):
            for item in json_data:
                urls.extend(self.extract_urls(item))
        return list(set(urls))  # Remove duplicates by converting to a set and back to a list

    def sanitize_filename(self, url):
        """
        Sanitizes the URL to make it a valid filename by replacing invalid characters.
        """
        # Parse the URL to get the path part (this removes query parameters, etc.)
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)  # Get the filename from the URL path
        
        # Replace invalid characters with underscores
        sanitized_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

        return sanitized_filename

    def preprocess_channels(self, blue_channel, green_channel, red_channel, alpha_channel):
        """
        Prepares the channels for merging by ensuring they have the same size and data type.

        Args:
            blue_channel (numpy.ndarray): Blue channel.
            green_channel (numpy.ndarray): Green channel.
            red_channel (numpy.ndarray): Red channel.
            alpha_channel (numpy.ndarray): Alpha channel.

        Returns:
            tuple: Resized and aligned channels ready for merging.
        """
        # Determine the reference size (use the size of the first channel)
        height, width = blue_channel.shape[:2]

        # Resize all channels to match the reference size
        green_channel = cv2.resize(green_channel, (width, height))
        red_channel = cv2.resize(red_channel, (width, height))
        alpha_channel = cv2.resize(alpha_channel, (width, height))

        # Convert all channels to the same data type (e.g., uint8)
        channels = [blue_channel, green_channel, red_channel, alpha_channel]
        target_dtype = blue_channel.dtype  # Use the dtype of the first channel as reference
        channels = [ch.astype(target_dtype) for ch in channels]

        return tuple(channels)

    def convert_to_8bit_single_channel(self, texture):
        """
        Converts a texture to 8-bit single-channel format.
        
        Args:
            texture (numpy.ndarray): Input texture, can be grayscale or RGB, 
                                    with bit depth 8, 16, 32, or 48.
        Returns:
            numpy.ndarray: 8-bit single-channel texture.
        """

        # Determine the bit depth of the input texture
        if texture.dtype == np.uint8:
            # Already 8-bit, no further conversion needed
            return texture
        elif texture.dtype == np.uint16:
            # Convert 16-bit to 8-bit
            texture = (texture / 256).astype(np.uint8)
        elif texture.dtype in [np.float32, np.float64]:
            # Normalize float textures to 0-255 and convert to 8-bit
            texture = (255 * (texture / np.max(texture))).astype(np.uint8)
        elif texture.dtype == np.int32 or texture.dtype == np.int64:
            # Clip values to 0-255 and convert to 8-bit
            texture = np.clip(texture, 0, 255).astype(np.uint8)
        else:
            raise ValueError(f"Unsupported texture dtype: {texture.dtype}")
        
        return texture

    def combine_textures(self, texture_path, thumbnail_name, texture_name_label):
        """
        Combines texture components into various output textures.
        """
        staging_dir = "staging"
        os.makedirs(staging_dir, exist_ok=True)

        # Normalize texture_name_label and thumbnail_name
        texture_name_label = f"textures\\{texture_name_label}".lower().replace("_result", "")
        down_thumbnail_name = thumbnail_name.lower().replace(" ", "_")

        # Helper function to load an image
        def load_image(file_path):
            if file_path and os.path.exists(file_path):
                return cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            print(f"File not found: {file_path}")
            return None

        # Helper function to find a file
        def find_file(substrings, down_thumbnail_name):
            if isinstance(substrings, str):
                substrings = [substrings]
            for filename in os.listdir(staging_dir):
                filename_casefold = filename.casefold()
                if filename_casefold.startswith(down_thumbnail_name):
                    for substring in substrings:
                        if substring in filename_casefold:
                            return os.path.join(staging_dir, filename)
            return None

        # Load texture files
        arm_file = find_file("_arm_", down_thumbnail_name)
        nor_file = find_file("_nor_", down_thumbnail_name)
        disp_file = find_file(["_disp_", "_height_"], down_thumbnail_name)
        diff_file = find_file(["_diff_", "_color_"], down_thumbnail_name)

        arm_texture = load_image(arm_file)
        nor_texture = load_image(nor_file)
        disp_texture = load_image(disp_file)
        diff_texture = load_image(diff_file)

        # Create textures
        self.create_param_texture(texture_name_label, staging_dir, arm_texture)
        self.create_nh_texture(texture_name_label, staging_dir, nor_texture, disp_texture)
        self.process_and_save_diff_textures(texture_name_label, staging_dir, diff_texture, arm_texture)

    def create_param_texture(self, texture_name_label, staging_dir, arm_texture):
        """Creates and saves the _param texture."""
        if arm_texture is None:
            return
        param_r = self.convert_to_8bit_single_channel(arm_texture[:, :, 0])  # Blue
        param_g = self.convert_to_8bit_single_channel(arm_texture[:, :, 1])  # Green
        param_b = np.full_like(param_g, 128)  # Mid-gray (128)
        param_a = self.convert_to_8bit_single_channel(arm_texture[:, :, 2])  # Red

        # Combine into a single texture
        param_texture = cv2.merge([param_b, param_g, param_r, param_a])
        param_output_path = os.path.join(staging_dir, f"{texture_name_label}_param.png")
        cv2.imwrite(param_output_path, param_texture)
        print(f"Saved param texture: {param_output_path}")

    def create_nh_texture(self, texture_name_label, staging_dir, nor_texture, disp_texture):
        """Creates and saves the _nh texture."""
        if nor_texture is None or disp_texture is None:
            return
        nh_red = self.convert_to_8bit_single_channel(nor_texture[:, :, 2])  # Red
        nh_green = self.convert_to_8bit_single_channel(nor_texture[:, :, 1])  # Green
        nh_blue = self.convert_to_8bit_single_channel(nor_texture[:, :, 0])  # Blue
        nh_alpha = self.convert_to_8bit_single_channel(disp_texture[:, :, 2] if len(disp_texture.shape) == 3 else disp_texture)

        # Combine into a single texture
        nh_texture = cv2.merge([nh_blue, nh_green, nh_red, nh_alpha])
        nh_output_path = os.path.join(staging_dir, f"{texture_name_label}_nh.png")
        cv2.imwrite(nh_output_path, nh_texture)
        print(f"Saved nh texture: {nh_output_path}")

    def process_and_save_diff_textures(self, texture_name_label, staging_dir, diff_texture, arm_texture):
        """
        Processes and saves textures: diffuse (converted to 8-bit), diffparam, overlay (resized), and zoom (original size).
        
        Args:
            texture_name_label (str): Base name for the textures.
            staging_dir (str): Directory to save the textures.
            diff_texture (np.ndarray): The diffuse texture.
            arm_texture (np.ndarray): The ARM texture.
        """
        if diff_texture is None:
            return


        # Convert each channel of the diffuse texture to 8-bit
        d_red = self.convert_to_8bit_single_channel(diff_texture[:, :, 0])  # Red
        d_green = self.convert_to_8bit_single_channel(diff_texture[:, :, 1])  # Green
        d_blue = self.convert_to_8bit_single_channel(diff_texture[:, :, 2])  # Blue
        #print("Converted diffuse texture channels to 8-bit.")

        # Combine the channels into an 8-bit diffuse texture
        diff_texture_8bit = cv2.merge([d_red, d_green, d_blue])

        # Save the diffuse texture
        diff_output_path = os.path.join(staging_dir, f"{texture_name_label}.png")
        cv2.imwrite(diff_output_path, diff_texture_8bit)
        print(f"Saved diffuse texture: {diff_output_path}")

        # Path to the results file (assumes it's in the current working directory)
        results_file_path = f"{texture_name_label}_result.png"

        # Retrieve target size from the results file
        if not os.path.isfile(results_file_path):
            print(f"Error: Results file not found: {results_file_path}")
            return

        # Load the results image to get its size
        results_image = cv2.imread(results_file_path, cv2.IMREAD_UNCHANGED)
        if results_image is None:
            print(f"Error: Failed to load results image: {results_file_path}")
            return

        target_size = (results_image.shape[1], results_image.shape[0])  # (width, height)
        print(f"Retrieved target size from results file: {target_size}")

        # Save the overlay texture (resized)
        overlay_texture = cv2.resize(diff_texture_8bit, target_size, interpolation=cv2.INTER_LINEAR)
        overlay_name_path = os.path.basename(texture_name_label)
        overlay_output_path = os.path.join(OVERLAY_FOLDER, f"{overlay_name_path}_overlay.png")
        cv2.imwrite(overlay_output_path, overlay_texture)
        print(f"Saved overlay texture: {overlay_output_path}")

        # If arm_texture is provided, create and save the diffparam texture
        if arm_texture is not None:
            # Convert the green channel of ARM texture to 8-bit for alpha
            d_alpha = self.convert_to_8bit_single_channel(arm_texture[:, :, 1])  # Green (from ARM)

            # Combine diffuse channels with alpha into diffparam texture
            diffparam_texture = cv2.merge([d_red, d_green, d_blue, d_alpha])
            diffparam_output_path = os.path.join(staging_dir, f"{texture_name_label}_diffparam.png")
            cv2.imwrite(diffparam_output_path, diffparam_texture)
            print(f"Saved diffparam texture: {diffparam_output_path}")



# Main
if __name__ == "__main__":
    db = load_database()
    root = Tk()
    app = TextureTagger(root, db)
    root.mainloop()

