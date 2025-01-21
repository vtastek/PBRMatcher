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

        # GUI Elements
        self.texture_name_label = Label(root, text="", font=("Arial", 7), pady=10)
        self.texture_name_label.pack()

        self.label_frame = Frame(root, bg="black")
        self.label_frame.pack()
        self.image_label = Label(self.label_frame, bg="black")
        self.image_label.pack(fill="both", padx=100, pady=10)

        self.previous_button = Button(root, text="Previous", command=self.previous_texture)
        self.previous_button.place(relx=0.0, rely=0.1, anchor="nw", x=5) 
        #self.previous_button.pack(side="left", padx=5)

        self.next_button = Button(root, text="Next", command=self.next_texture)
        self.next_button.place(relx=1.0, rely=0.1, anchor="ne", x=-5) 
        #self.next_button.pack(side="right", padx=5)

        # Create the download frame and add the button and progress bar
        self.download_frame = Frame(root)
        self.download_frame.place(relx=0.9, rely=0.1, anchor="ne", x=-5)

        self.download_button = Button(self.download_frame, text="Download Texture", command=self.download_texture)
        self.download_button.grid(row=0, column=0, pady=10)

        # Add a Progressbar widget to the GUI
        self.progress_label = ttk.Label(self.download_frame, text="Downloading Textures...")
        self.progress_label.grid(row=1, column=0, pady=10)

        self.progress_bar = ttk.Progressbar(self.download_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=2, column=0, pady=5)


        
        # Create a frame for tags list and buttons
        self.tags_frame = Frame(root)
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

        self.tag_entry = Entry(root)
        self.tag_entry.pack()

        # Create a frame for togglable buttons
        self.button_frame = Frame(root)
        self.button_frame.pack()

        # Frame for displaying thumbnails
        self.thumbnail_frame = Frame(root, bg="black")
        self.thumbnail_frame.pack(pady=10)

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

        self.selected_thumbnails_label = Label(self.root, text="Selected Thumbnails: 0", font=("Arial", 12))
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

        thumb_button_frame = Frame(root)
        thumb_button_frame.pack()
   
        self.previous_thumbnails_button = Button(thumb_button_frame, text="Previous Thumbnails", command=self.previous_thumbnails)
        self.previous_thumbnails_button.grid(row=0, column=0, padx=10)
        # Page indicator label
        self.page_indicator = Label(thumb_button_frame, text="-/-")
        self.page_indicator.grid(row=0, column=1, padx=10)
        self.next_thumbnails_button = Button(thumb_button_frame, text="Next Thumbnails", command=self.next_thumbnails)
        self.next_thumbnails_button.grid(row=0, column=2, padx=10)
       


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
        """Update the count of selected thumbnails for the current texture."""
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Retrieve selected thumbnails for the current texture
        selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])

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
        """Update the counts for each button and label, including 'assigned'."""
        counts = {key: {"tagged": 0, "untagged": 0, "assigned": 0} for key in self.button_info}

        for path in self.texture_paths:
            tags = self.db["textures"].get(path, {}).get("tags", [])
            selected_thumbnails = self.db["textures"].get(path, {}).get("selected_thumbnails", [])
            for key in self.button_info:
                if os.path.basename(path).startswith(key):
                    if tags:
                        counts[key]["tagged"] += 1
                    else:
                        counts[key]["untagged"] += 1

                    if selected_thumbnails:  # Check if there are selected thumbnails
                        counts[key]["assigned"] += 1
                        #print("assignedcounted")

        for key, count in counts.items():
            self.label_frames[f"{key}_tagged"].config(text=str(count["tagged"]))
            self.label_frames[f"{key}_untagged"].config(text=str(count["untagged"]))
            
            # Update the 'assigned' label dynamically
            if f"{key}_assigned" in self.label_frames:
                self.label_frames[f"{key}_assigned"].config(text=str(count["assigned"]))

        # Misc counts
        misc_tagged = sum(
            1 for path in self.texture_paths
            if not any(os.path.basename(path).startswith(key) for key in self.button_info)
            and self.db["textures"].get(path, {}).get("tags")
        )
        misc_untagged = sum(
            1 for path in self.texture_paths
            if not any(os.path.basename(path).startswith(key) for key in self.button_info)
            and not self.db["textures"].get(path, {}).get("tags")
        )
        misc_assigned = sum(
            1 for path in self.texture_paths
            if not any(os.path.basename(path).startswith(key) for key in self.button_info)
            and self.db["textures"].get(path, {}).get("selected_thumbnails", [])
        )

        self.misc_label_tagged.config(text=str(misc_tagged))
        self.misc_label_untagged.config(text=str(misc_untagged))
        # Add 'assigned' count for misc
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

    def display_texture(self):
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Update the texture name label
        texture_name = os.path.basename(texture_path)
        self.texture_name_label.config(text=f"Texture: {texture_name}")

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
                if any(os.path.basename(path).startswith(tag) for tag in self.active_buttons)
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

    def download_texture(self):
        # Get the current texture path using the current index
        texture_path = self.filtered_texture_paths[self.current_index]

        # Retrieve selected thumbnails for the current texture from the database
        download_list = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])

        # Check if there are any thumbnails
        if not download_list:
            print(f"No selected thumbnails for texture: {texture_path}")
            messagebox.showerror("Error", f"No selected thumbnails for texture: {texture_path}")
            return

        #print(f"Selected thumbnails for {texture_path}: {download_list}")

        # Create the "staging" folder if it doesn't exist
        if not os.path.exists("staging"):
            os.makedirs("staging")

        # Prepare a list to store all URLs from the download list
        all_urls = []

        # Loop through each item in the download list and extract the URLs
        for texture_id in download_list:
            # Replace spaces with underscores and turn to lowercase
            texture_id = texture_id.replace(" ", "_").lower()

            # Construct the URL for downloading the texture
            url = f"https://api.polyhaven.com/files/{texture_id}"

            try:
                # Make the GET request to fetch texture metadata
                data = requests.get(url)

                # Check if the request was successful
                if data.status_code == 200:
                    #messagebox.showinfo("Success", f"Texture '{texture_id}' exists!")
                    print("success")
                else:
                    messagebox.showerror("Error", f"Failed to fetch texture metadata for '{texture_id}'. Status code: {data.status_code}")
                    continue

                # Extract all URLs under $map from the metadata response
                texture_urls = self.extract_urls(data.json())

                # Filter texture_urls to include only those ending with "_4k.png" and excluding "_gl_"
                filtered_urls = [
                    texture_url for texture_url in texture_urls
                    if texture_url.endswith("_4k.png") and "_gl_" not in texture_url
                ]

                # Add filtered URLs to the list
                all_urls.extend(filtered_urls)

            except requests.exceptions.RequestException as e:
                messagebox.showerror("Error", f"An error occurred while fetching metadata for texture '{texture_id}': {e}")

        # If no valid URLs were found, show an error and return
        if not all_urls:
            messagebox.showerror("Error", "No valid URLs found for selected textures.")
            return

        # Set the progress bar maximum value to the number of valid URLs
        self.progress_bar["maximum"] = len(all_urls)

        # Loop through the filtered URLs and download each texture
        for idx, texture_url in enumerate(all_urls):
            # Update the progress bar for each texture download
            self.progress_bar["value"] = idx + 1  # Update progress bar to current texture
            self.root.update_idletasks()  # Refresh the GUI to reflect progress

            # Sanitize the URL to create a valid filename
            sanitized_filename = self.sanitize_filename(texture_url)

            try:
                # Make the GET request to download the texture file
                response = requests.get(texture_url)

                # Check if the request was successful
                if response.status_code == 200:
                    # Save the texture's data to the "staging" folder using the sanitized filename
                    file_path = os.path.join("staging", sanitized_filename)
                    with open(file_path, "wb") as file:
                        file.write(response.content)
                    #messagebox.showinfo("Success", f"Texture downloaded successfully to 'staging' folder!")
                else:
                    messagebox.showerror("Error", f"Failed to download texture. Status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                messagebox.showerror("Error", f"An error occurred while downloading texture: {e}")

         # Remove '_result' from the texture path
        cleaned_texture_path = texture_path.replace("_result", "")    
        self.combine_textures(cleaned_texture_path)

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

    def combine_textures(self, texture_name_label):
        staging_dir = "staging"

        # Helper function to find a file containing a specific substring
        def find_file(substring):
            for filename in os.listdir(staging_dir):
                if substring in filename and filename.endswith(".png"):
                    return os.path.join(staging_dir, filename)
            return None

        # Helper function to load an image
        def load_image(file_path):
            if file_path and os.path.exists(file_path):
                return cv2.imread(file_path, cv2.IMREAD_UNCHANGED)  # Load with alpha if available
            else:
                print(f"File not found: {file_path}")
                return None

        # Search for files
        arm_file = find_file("_arm_")
        rough_file = find_file("_rough_")
        ao_file = find_file("_ao_")
        nor_file = find_file("_nor_")
        disp_file = find_file("_disp_")
        diff_file = find_file("_diff_")

        # Create the first texture: {texture_name_label}_param.png
        arm_texture = load_image(arm_file)
        rough_texture = load_image(rough_file)
        ao_texture = load_image(ao_file)

        if arm_texture is not None and rough_texture is not None and ao_texture is not None:
            # Extract the blue channel from the ARM texture
            red_channel = arm_texture[:, :, 0]  # Blue channel from the ARM texture
            
            # Handle single-channel or multi-channel roughness texture
            green_channel = rough_texture
            
            blue_channel = np.full_like(green_channel, 128)  # 0.5 gray (128 in 8-bit)
            alpha_channel = ao_texture[:, :, 2]  # Handle single/multi-channel AO
            # BGRA?
            param_texture = cv2.merge([blue_channel, green_channel, red_channel, alpha_channel])

            # Save the param texture
            texture_name_label = texture_name_label.lower().replace(".png", "")

            param_output_path = os.path.join(staging_dir, f"{texture_name_label}_param.png")
            os.makedirs(staging_dir, exist_ok=True)
            cv2.imwrite(param_output_path, param_texture)

        # Create the second texture: {texture_name_label}_nh.png
        nor_texture = load_image(nor_file)
        disp_texture = load_image(disp_file)

        if nor_texture is not None and disp_texture is not None:
            # Use the normal map for RGB and displacement for alpha
            blue, green, red = cv2.split(nor_texture)[:3]  # Ignore alpha channel if present
            if disp_texture.dtype == np.uint16:  # Check if the texture is 16-bit
                #print("Converting red channel from 16-bit to 8-bit...")
                red_channel_16bit = disp_texture[:, :, 2]  # OpenCV stores channels as BGR, so red is at index 2
                alpha_channel = cv2.convertScaleAbs(red_channel_16bit, alpha=(255.0 / 65535.0))
            else:
                #print("Using the red channel as-is (already 8-bit)...")
                alpha_channel = disp_texture[:, :, 2] if len(disp_texture.shape) == 3 else disp_texture

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


        # Create the third texture: {texture_name_label}.png
        diff_texture = load_image(diff_file)

        if diff_texture is not None:
            # Save the diff texture directly
            diff_output_path = os.path.join(staging_dir, f"{texture_name_label}.png")
            os.makedirs(staging_dir, exist_ok=True)
            success = cv2.imwrite(diff_output_path, diff_texture)
            if not success:
                print(f"Failed to write the texture to {diff_output_path}")

        messagebox.showinfo("Successfully created PARAM AND NORM textures for ", f"Texture '{texture_name_label}")



# Main
if __name__ == "__main__":
    db = load_database()
    root = Tk()
    app = TextureTagger(root, db)
    root.mainloop()