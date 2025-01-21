import os
import json
import tkinter as tk
import io
import requests
import threading
import time
from tkinter import Tk, Label, Entry, Button, Listbox, END, Frame
from tkinter import messagebox
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
        self.root.geometry("1600x1024")

        # Prevent window resizing
        self.root.resizable(True, True)

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
            button.grid(row=0, column=index, padx=10)  # Explicitly set the column
            self.buttons[key] = button
        
            # Create a frame for the tagged/untagged labels
            frame = Frame(self.button_frame)
            frame.grid(row=1, column=index, padx=10)  # Match the column index of the button
            self.label_frames[key] = frame
        
            self.label_frames[f"{key}_tagged"] = Label(frame, text="0", fg="green")
            self.label_frames[f"{key}_tagged"].pack(side="left")
        
            Label(frame, text="/").pack(side="left")
        
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
        self.next_thumbnails_button = Button(thumb_button_frame, text="Next Thumbnails", command=self.next_thumbnails)
        self.next_thumbnails_button.grid(row=0, column=1, padx=10)
       



    def update_selected_thumbnails_count(self):
        """Update the count of selected thumbnails for the current texture."""
        # Get the current texture path
        texture_path = self.filtered_texture_paths[self.current_index]

        # Retrieve selected thumbnails for the current texture
        selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])

        # Update the label
        count = len(selected_thumbnails)
        self.selected_thumbnails_label.config(text=f"Selected Thumbnails: {count}")



    def display_thumbnails(self):
        """Display selectable thumbnails of textures from Polyhaven."""
        start_time = time.time()
        print("Starting display_thumbnails...")

        # Clear previous thumbnails
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        print(f"Time to clear thumbnails: {time.time() - start_time:.4f} seconds")

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
                        print(f"Current Texture Path: {texture_path}")
                        print(f"Selected Thumbnails: {selected_thumbnails}")
                        print(f"Checking Texture ID: {texture_id}")
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
        self.display_thumbnails()

    def previous_thumbnails(self):
        """Show the next set of thumbnails."""
        self.current_thumbnail_index = max(self.current_thumbnail_index - 5, 0)
        self.display_thumbnails()


    def update_counts(self):
        """Update the counts for each button and label."""
        counts = {key: {"tagged": 0, "untagged": 0} for key in self.button_info}

        for path in self.texture_paths:
            tags = self.db["textures"].get(path, {}).get("tags", [])
            for key in self.button_info:
                if os.path.basename(path).startswith(key):
                    if tags:
                        counts[key]["tagged"] += 1
                    else:
                        counts[key]["untagged"] += 1

        for key, count in counts.items():
            self.label_frames[f"{key}_tagged"].config(text=str(count["tagged"]))
            self.label_frames[f"{key}_untagged"].config(text=str(count["untagged"]))

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

        self.misc_label_tagged.config(text=str(misc_tagged))
        self.misc_label_untagged.config(text=str(misc_untagged))
        
        # All counts
        all_tagged = sum(
            1 for path in self.texture_paths if self.db["textures"].get(path, {}).get("tags")
        )
        all_untagged = len(self.texture_paths) - all_tagged

        self.all_label_tagged.config(text=str(all_tagged))
        self.all_label_untagged.config(text=str(all_untagged))


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
            self.display_texture()

    def previous_texture(self):
        if self.current_index > 0:
            self.current_index -= 1
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

# Main
if __name__ == "__main__":
    db = load_database()
    root = Tk()
    app = TextureTagger(root, db)
    root.mainloop()