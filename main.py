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
from tkinter import Tk, Label, Entry, Button, Listbox, END, Frame
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
from urllib.parse import urlparse

# Initialize or load JSON database
DB_FILE = "db.json"

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
        self.current_index = self.get_current_index()
     
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
        self.root.geometry("1600x960")

        self.center_window(1600, 960)


        # Prevent window resizing
        self.root.resizable(False, False)

        self.main = Frame(root)
        self.main.configure(bg="#999999")
        self.main.pack()

        # GUI Elements
        self.texture_name_label = Label(self.main, text="", font=("Arial", 7), pady=10)
        self.texture_name_label.pack()
        self.default_bg = self.texture_name_label.cget("bg")  # Get the current default background


        self.label_frame = Frame(self.main, bg="black")
        self.label_frame.pack()
        self.image_label = Label(self.label_frame, bg="black")
        self.image_label.pack(fill="both", padx=100, pady=10)

        self.previous_button = Button(self.main, width=10, text="Previous", command=self.previous_texture)
        self.previous_button.place(relx=0.0, rely=0.1, anchor="nw", x=5)
        self.previous_button.place(relheight=0.1) 
        #self.previous_button.pack(side="left", padx=5)

        self.next_button = Button(self.main, width=10, text="Next", command=self.next_texture)
        self.next_button.place(relx=1.0, rely=0.1, anchor="ne", x=-5)
        self.next_button.place(relheight=0.1) 
        #self.next_button.pack(side="right", padx=5)

        # Create the download frame and add the button and progress bar
        self.download_frame = Frame(self.main)
        offset = 16  # Fixed offset from top (y=16)
        relscale = 0.9

        self.download_frame.place(relx=relscale, rely=0.0, anchor="ne", y=offset)

        #self.download_button = Button(self.download_frame, text="Download Texture", command=self.download_texture)
        #self.download_button.grid(row=0, column=0, pady=10)

        # Add "Add to Queue" button
        self.add_to_queue_button = Button(self.download_frame, text="Add to Queue", command=self.add_to_queue)
        self.add_to_queue_button.grid(row=0, column=0, pady=10)

        # Add "Show Queue" button
        self.show_queue_button = Button(self.download_frame, text="Show Queue", command=self.show_queue)
        self.show_queue_button.grid(row=0, column=0, pady=10, sticky="E")

        # Add a Progressbar widget to the GUI
        self.progress_label = ttk.Label(self.download_frame, text="Completed: 0, In Progress: 0, Pending: 0")
        self.progress_label.grid(row=1, column=0, pady=10)

        self.progress_bar_dummy= ttk.Progressbar(self.download_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar_dummy.grid(row=2, column=0, pady=5)

        # Queue and Progress Tracking
        self.completed_downloads = []  # To track items in the queue
        self.in_progress = []  # To track items in the queue
        self.download_queue = []  # To track items in the queue
        self.currently_downloading = False  # To track if a download is in progress
        
        # Add frame for slot buttons and preview
        self.slot_frame = Frame(self.download_frame)
        self.slot_frame.grid(row=3, column=0, pady=5)

        self.selected_slot = None
        self.slot_buttons = {}

        # Add buttons for A, B, C, D
        slot_names = ["A", "B", "C", "D"]
        for slot in range(4):
            self.slot_frame.grid_columnconfigure(slot, weight=1)  # Ensure equal column widths
            button = Button(
                self.slot_frame,
                text=slot_names[slot],
                width=5,
                command=lambda slot=slot_names[slot]: self.switch_slot(slot)
            )

            button.grid(row=4, column=slot, padx=1, sticky="we")  # "we" makes the button stretch horizontally
            self.slot_buttons[slot_names[slot]] = button
        for slot_name, button in self.slot_buttons.items():
            button.grid_remove()  # Hide all buttons initially


        # Add single preview area
        self.preview_label = Label(self.slot_frame, text="No Preview", bg="gray")
        self.preview_label.grid(row=5, column=0, pady=5, columnspan=4)  # Span across all columns for alignment

        self.root.update_idletasks()


        self.progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
        frame_x = self.root.winfo_width() * relscale  # 90% of root's width
        
        # Adjust for the "ne" anchor
        frame_x -= self.download_frame.winfo_width()  # Align by the right edge

        # Add the progress bar's position inside the frame
        dummy_x = frame_x + self.progress_bar_dummy.winfo_x()
        dummy_y = offset + self.progress_bar_dummy.winfo_y()

        # Place the root-level progress bar at the calculated position
        self.progress_bar.place(x=dummy_x, y=dummy_y, width=self.progress_bar_dummy.winfo_width())

        # Create a frame for tags list and buttons
        self.tags_frame = Frame(self.main)
        self.tags_frame.pack()

        self.tags_listbox = Listbox(self.tags_frame, selectmode="multiple", height=5)
        self.tags_listbox.grid(row=0, column=0, padx=10)

        # Add buttons to the right of the tags list
        self.buttons_frame = Frame(self.tags_frame)
        self.buttons_frame.grid(row=0, column=1, padx=10)

        self.add_tag_button = Button(self.buttons_frame, text="Add Tag", command=self.add_tag)
        self.add_tag_button.pack(pady=5)

        self.remove_tag_button = Button(self.buttons_frame, text="Remove Tag", command=self.remove_tag)
        self.remove_tag_button.pack(pady=5)

        self.tag_entry = Entry(self.main)
        self.tag_entry.pack()

        # Create a frame for togglable buttons
        self.button_frame = Frame(self.main)
        self.button_frame.pack()

        # Frame for displaying thumbnails
        self.thumbnail_frame = Frame(self.main, width=300, height=360, bg="black")
        
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

        self.buttons = {}
        self.label_frames = {}  # Store frames for each label
        self.active_buttons = set()
  
        for index, (key, value) in enumerate(self.button_info.items()):
            button = Button(self.button_frame, text=value, command=lambda key=key: self.toggle_button(key))
            button.grid(row=0, column=index, padx=10)
            self.buttons[key] = button

            # Create a frame for the labels
            frame = Frame(self.button_frame)
            frame.grid(row=1, column=index, padx=10)
            self.label_frames[key] = frame

            # Add the 'assigned' label
            self.label_frames[f"{key}_assigned"] = Label(frame, text="0", fg="blue")
            self.label_frames[f"{key}_assigned"].pack(side="left")

            Label(frame, text="/").pack(side="left")
            
            # Add the 'tagged' label
            self.label_frames[f"{key}_tagged"] = Label(frame, text="0", fg="green")
            self.label_frames[f"{key}_tagged"].pack(side="left")
            
            Label(frame, text="/").pack(side="left")
            
            # Add the 'untagged' label
            self.label_frames[f"{key}_untagged"] = Label(frame, text="0", fg="red")
            self.label_frames[f"{key}_untagged"].pack(side="left")


        self.misc_button = Button(self.button_frame, text="Misc", command=self.show_all_textures)
        self.misc_button.grid(row=0, column=len(self.button_info), padx=10)
        
        self.misc_frame = Frame(self.button_frame)
        self.misc_frame.grid(row=1, column=len(self.button_info), padx=10)
        
        self.misc_label_tagged = Label(self.misc_frame, text="0", fg="green")
        self.misc_label_tagged.pack(side="left")
        
        Label(self.misc_frame, text="/").pack(side="left")
        
        self.misc_label_untagged = Label(self.misc_frame, text="0", fg="red")
        self.misc_label_untagged.pack(side="left")

        self.all_button = Button(self.button_frame, text="All", command=self.toggle_all_buttons)
        self.all_button.grid(row=0, column=len(self.button_info) + 1, padx=10)

        self.selected_thumbnails_label = Label(self.main, text="Selected Thumbnails: 0", font=("Arial", 12))
        self.selected_thumbnails_label.pack(pady=5)

        self.all_frame = Frame(self.button_frame)
        self.all_frame.grid(row=1, column=len(self.button_info) + 1, padx=10)

        self.all_label_tagged = Label(self.all_frame, text="0", fg="green")
        self.all_label_tagged.pack(side="left")

        Label(self.all_frame, text="/").pack(side="left")

        self.all_label_untagged = Label(self.all_frame, text="0", fg="red")
        self.all_label_untagged.pack(side="left")

        # Display first texture
        self.display_texture()
        self.update_counts()

        thumb_button_frame = Frame(self.main)
        thumb_button_frame.pack()
   
        self.previous_thumbnails_button = Button(thumb_button_frame, text="Previous Thumbnails", command=self.previous_thumbnails)
        self.previous_thumbnails_button.grid(row=0, column=0, padx=10)
        # Page indicator label
        self.page_indicator = Label(thumb_button_frame, text="-/-")
        self.page_indicator.grid(row=0, column=1, padx=10)
        self.next_thumbnails_button = Button(thumb_button_frame, text="Next Thumbnails", command=self.next_thumbnails)
        self.next_thumbnails_button.grid(row=0, column=2, padx=10)
       
       



    def switch_slot(self, slot_name):
        self.selected_slot = slot_name
        #print(f"Switched to slot: {slot_name}")  # Debugging
        self.update_selected_thumbnails_count()  # Update preview

    def center_window(self, width, height):
        # Get the screen width and height
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Calculate the position of the window
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2) - 25

        # Set the window geometry
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
    def update_selected_thumbnails_count(self):
        """Update the count of selected thumbnails for the current texture and adjust slot buttons."""
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Retrieve selected thumbnails for the current texture
        selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
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
                        image.thumbnail((256, 256))  # Resize for display
                        thumb_photo = ImageTk.PhotoImage(image)
                        self.preview_label.config(image=thumb_photo, text="")
                        self.preview_label.image = thumb_photo  # Prevent garbage collection
                    except Exception as e:
                        print(f"Error opening thumbnail: {e}")
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


        self.update_counts()

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
            no_results_label = Label(self.thumbnail_frame, text="No matching thumbnails found.", font=("Arial", 12))
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
                        thumb_img.thumbnail((256, 256))  # Adjust thumbnail size for display
                        thumb_photo = ImageTk.PhotoImage(thumb_img)

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
                        thumb_label = Label(thumb_container, image=thumb_photo, bg="black")
                        thumb_label.image = thumb_photo  # Keep reference to prevent garbage collection
                        thumb_label.pack(pady=5)
                      

                        # Display texture tags
                        tags_label = Label(
                            thumb_container,
                            text=", ".join(texture_tags),
                            wraplength=250,  # Ensure text wraps within the container
                            font=("Arial", 8),
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

        # Check if the file exists and update the background color
        if os.path.isfile(file_path):
            self.texture_name_label.config(bg="green")  # Set background to green
        else:
            self.texture_name_label.config(bg=self.default_bg)  # Reset background to default (None)

    def display_texture(self):
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Update the texture name label
        texture_name = os.path.basename(texture_path)
        self.texture_name_label.config(text=f"Texture: {texture_name}")

        texture_name_result = texture_name.replace("_result", "")
       
        self.update_texture_label(texture_name_result)

        #print(f"DEBUG: Filtered texture paths: {self.filtered_texture_paths}")
        #print(f"DEBUG: Current index: {self.current_index}")

        # Load the image
        image = Image.open(texture_path)

        # Calculate resized dimensions
        base_height = 300
        aspect_ratio = image.width / image.height
        new_width = int(base_height * aspect_ratio)
        image = image.resize((new_width, base_height))

        photo = ImageTk.PhotoImage(image)
        self.image_label.config(image=photo)
        self.image_label.image = photo

        # Clear and display tags
        self.tags_listbox.delete(0, END)
        stored_tags = self.db["textures"].get(texture_path, {}).get("tags", [])
        for tag in stored_tags:
            self.tags_listbox.insert(END, tag)
        
        # Display thumbnails of related textures
        self.display_thumbnails()


    def toggle_button(self, tag):
        """Toggle the filter for the selected tag."""
        if tag in self.active_buttons:
            self.active_buttons.remove(tag)
            self.buttons[tag].config(bg="lightgray")  # Set to inactive color
        else:
            self.active_buttons.add(tag)
            self.buttons[tag].config(bg="lightblue")  # Set to active color

        self.apply_filters()
        self.update_counts()
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
        self.update_counts()


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

        # Update counts
        self.update_counts()

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

        #print("DEBUGVVVVV", next_texture)

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
   
    def _perform_download(self, texture_path, thumbnail_name, texture_name_label):
        """Perform the actual download process for a specific texture and thumbnail."""
        try:
            
            # Normalize thumbnail name for use in URLs
            #thumbnail_name_url = self.get_key_by_name(self.all_assets, thumbnail_name)

            #thumbnail_name_url = thumbnail_name.lower().replace(" ", "_")
            #thumbnail_name = thumbnail_name.lower().replace(" ", "_")
            texture_id = thumbnail_name

            texture_id_download = self.get_key_by_name(self.all_assets, thumbnail_name)

            texture_path = os.path.normpath(texture_path.strip())
            texture_name_label = texture_name_label.strip()
            #thumbnail_name = thumbnail_name.strip()

            # Construct the download URL
            url = f"https://api.polyhaven.com/files/{texture_id_download}"

            # Create the "staging" folder if it doesn't exist
            if not os.path.exists("staging"):
                os.makedirs("staging")

            #print(thumbnail_name)
            
            # Fetch texture metadata
            data = requests.get(url)
            if data.status_code != 200:
                messagebox.showerror("Error", f"Failed to fetch texture metadata for '{texture_id}'. Status code: {data.status_code}")
                return
            
      

            # Extract URLs for downloading texture files
            texture_urls = self.extract_urls(data.json())

            # Filter URLs to include only "_4k.png" files, excluding unnecessary files
            filtered_urls = [
                texture_url for texture_url in texture_urls
                if texture_url.endswith("_4k.png") and "_gl_" not in texture_url and "_spec_" not in texture_url and
                "_bump_" not in texture_url and "_mask_" not in texture_url and "_ao_" not in texture_url and "_rough_" not in texture_url
            ]

            # Check if there are files to download
            if not filtered_urls:
                messagebox.showerror("Error", f"No valid files to download for '{thumbnail_name}'.")
                return

            # Set the progress bar maximum value
            self.progress_bar["maximum"] = len(filtered_urls)

            # Download files
            for idx, texture_url in enumerate(filtered_urls):
                # Update the progress bar
                self.actual_progress = idx + 1

                # Sanitize the URL to create a valid filename
                sanitized_filename = self.sanitize_filename(texture_url)

                # Download the texture
                response = requests.get(texture_url)
                if response.status_code == 200:
                    file_path = os.path.join("staging", sanitized_filename)
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
        # If the texture has multiple channels (e.g., RGB), convert to grayscale
        if len(texture.shape) == 3 and texture.shape[2] > 1:
            texture = cv2.cvtColor(texture, cv2.COLOR_BGR2GRAY)
        
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
        staging_dir = "staging"

        texture_name_label = f"textures\\{texture_name_label}"
        texture_name_label = texture_name_label.lower().replace("_result", "")

        # Check if there is a selected slot
        thumbnail_name = self.get_key_by_name(self.all_assets, thumbnail_name)

        down_thumbnail_name = thumbnail_name.lower().replace(" ", "_")  # Normalize thumbnail name

        #print(f"Selected slot: {self.selected_slot}, Thumbnail: {down_thumbnail_name}")

        # Helper function to find a file containing a specific substring for the thumbnail
        def find_file(substrings): # Changed line 1: Now accepts a list of substrings
            for substring in substrings: # Changed line 2: Iterates through substrings
                for filename in os.listdir(staging_dir):
                    filename_casefold = filename.casefold()
                    if down_thumbnail_name in filename_casefold and substring in filename_casefold and filename_casefold.endswith(".png"):
                        return os.path.join(staging_dir, filename_casefold)

            print(f"No file found for thumbnail '{down_thumbnail_name}' and substrings '{substrings}'") # Updated print statement for clarity
            return None

        # Helper function to load an image
        def load_image(file_path):
            if file_path and os.path.exists(file_path):

                #with Image.open(file_path) as img:
                    # Print general image information
                    #print(f"Image Format: {img.format}")
                    #print(f"Image Size: {img.size}")
                    #print(f"Image Mode: {img.mode}")

                    # Print PNG metadata (stored in img.info)
                    #print("\nPNG Metadata:")
                    #for key, value in img.info.items():
                    #    print(f"{key}: {value}")

                    # Print Exif metadata if available
                    #if hasattr(img, "_getexif") and img._getexif() is not None:
                    #    print("\nExif Metadata:")
                    #    exif_data = img._getexif()
                    #    for tag, value in exif_data.items():
                    #        tag_name = Image.ExifTags.TAGS.get(tag, tag)
                    #        print(f"{tag_name}: {value}")
                    #else:
                    #    print("\nNo Exif metadata found.")
                
            
                return cv2.imread(file_path, cv2.IMREAD_UNCHANGED)  # Load with alpha if available
            else:
                print(f"File not found: {file_path}")
                return None

        # Search for files
        arm_file = find_file("_arm_")
        nor_file = find_file("_nor_")
        disp_file = find_file(["_disp_", "_height_"])
        diff_file = find_file(["_diff_", "_color_"])

        # Create the first texture: {texture_name_label}_param.png
        arm_texture = load_image(arm_file)

        if arm_texture is not None:
            # Extract the blue channel from the ARM texture
            red_channel = arm_texture[:, :, 0]  # Blue channel from the ARM texture
            red_channel = self.convert_to_8bit_single_channel(red_channel)
            # Handle single-channel or multi-channel roughness texture
            green_channel = arm_texture[:, :, 1]  # Blue channel from the ARM texture
            
            blue_channel = np.full_like(green_channel, 128)  # 0.5 gray (128 in 8-bit)
            alpha_channel = arm_texture[:, :, 2]  # Blue channel from the ARM texture

            red_channel = self.convert_to_8bit_single_channel(red_channel)
            green_channel = self.convert_to_8bit_single_channel(green_channel)
            blue_channel = self.convert_to_8bit_single_channel(blue_channel)
            alpha_channel = self.convert_to_8bit_single_channel(alpha_channel)
 
            # Ensure all channels have the same dimensions
            alpha_channel = cv2.resize(alpha_channel, (blue_channel.shape[1], blue_channel.shape[0]))

            # Ensure all channels have the same data type
            alpha_channel = alpha_channel.astype(blue_channel.dtype)

            param_texture = cv2.merge([blue_channel, green_channel, red_channel, alpha_channel])

            # Save the param texture
            texture_name_label = texture_name_label.lower().replace(".png", "")

            param_output_path = os.path.join(staging_dir, f"{texture_name_label}_param.png")
            os.makedirs(staging_dir, exist_ok=True)
            cv2.imwrite(param_output_path, param_texture)
            print(f"Saved param {param_output_path}")

        # Create the second texture: {texture_name_label}_nh.png
        nor_texture = load_image(nor_file)
        disp_texture = load_image(disp_file)

        disp_texture = self.convert_to_8bit_single_channel(disp_texture)

        if nor_texture is not None and disp_texture is not None:
            # Use the normal map for RGB and displacement for alpha
            blue, green, red = cv2.split(nor_texture)[:3]  # Ignore alpha channel if present

            red = self.convert_to_8bit_single_channel(red)
            green = self.convert_to_8bit_single_channel(green)
            blue = self.convert_to_8bit_single_channel(blue)
                
            alpha_channel = disp_texture
 
            # Ensure all channels have the same dimensions
            alpha_channel = cv2.resize(alpha_channel, (blue.shape[1], blue.shape[0]))

            # Ensure all channels have the same data type
            alpha_channel = alpha_channel.astype(blue.dtype)

            # Merge channels into a single RGBA image
            nh_texture = cv2.merge([blue, green, red, alpha_channel])

            # Save the nh texture
            nh_output_path = os.path.join(staging_dir, f"{texture_name_label}_nh.png")
            os.makedirs(staging_dir, exist_ok=True)
            cv2.imwrite(nh_output_path, nh_texture)
            print(f"Saved nh {nh_output_path}")


        # Create the third texture: {texture_name_label}.png
        diff_texture = load_image(diff_file)
        #print(diff_texture[0, 0])  # Print the pixel at (0, 0)

        if diff_texture is not None:
            # Save the diff texture directly
            diff_output_path = os.path.join(staging_dir, f"{texture_name_label}.png")
            os.makedirs(staging_dir, exist_ok=True)
            success = cv2.imwrite(diff_output_path, diff_texture)
            print(f"Saved diff {diff_output_path}")

            if not success:
                print(f"Failed to write the texture to {diff_output_path}")

        # Dynamically resolve the path to terrain_dump.txt
        base_dir = os.path.dirname(DB_FILE)
        terrain_dump_path = os.path.join(base_dir, "terrain_dump.txt")

        # Check if texture_name_label is an LTEX record
        def is_ltex_record(label):
            label = os.path.basename(label)  # Extract only the filename

            # Remove the extension
            #label = os.path.splitext(label)[0]  # Remove the file extension
            #print(label)
            if os.path.exists(terrain_dump_path):
                with open(terrain_dump_path, 'r') as file:
                    for line in file:
                        line_no_ext = os.path.splitext(line.strip())[0]  # Remove extension and whitespace
                        if line_no_ext and label.lower() in line_no_ext.lower():
                            return True
            return False

        ltex_name = os.path.basename(texture_name_label)
        ltex_name = ltex_name.lower()
        #if is_ltex_record(ltex_name):
        #    print("terrain: ", ltex_name)
        #else:
        #    print("not terrain: ", ltex_name)

        

        if diff_texture is not None and arm_texture is not None and is_ltex_record(ltex_name):
            
            d_red_channel = diff_texture[:, :, 0]  # Red channel
            d_green_channel = diff_texture[:, :, 1]  # Green channel
            d_blue_channel = diff_texture[:, :, 2]  # Blue channel
            d_alpha_channel = arm_texture[:, :, 1]           # Alpha channel

            d_blue_channel = self.convert_to_8bit_single_channel(d_blue_channel)
            d_green_channel = self.convert_to_8bit_single_channel(d_green_channel)
            d_red_channel = self.convert_to_8bit_single_channel(d_red_channel)


            # Ensure all channels have the same dimensions
            d_alpha_channel = cv2.resize(d_alpha_channel, (d_blue_channel.shape[1], d_blue_channel.shape[0]))

            # Ensure all channels have the same data type
            d_alpha_channel = alpha_channel.astype(d_blue_channel.dtype)

            # Merge RGB from diff_texture and Alpha from rough_texture
            diffparam_texture = cv2.merge([d_red_channel, d_green_channel, d_blue_channel, d_alpha_channel])

            #print(diffparam_texture[0, 0])  # Print the pixel at (0, 0)

            # Save the diffparam texture
            diffparam_output_path = os.path.join(staging_dir, f"{texture_name_label}_diffparam.png")
            os.makedirs(staging_dir, exist_ok=True)
            cv2.imwrite(diffparam_output_path, diffparam_texture)
            print(f"Saved diffparam {diffparam_output_path}")

        #messagebox.showinfo("Successfully created PARAM AND NORM textures for ", f"Texture '{texture_name_label}")


# Main
if __name__ == "__main__":
    db = load_database()
    root = Tk()
    app = TextureTagger(root, db)
    root.mainloop()