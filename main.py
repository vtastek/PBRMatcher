import os
import json
from tkinter import Tk, Label, Entry, Button, Listbox, END, filedialog, Frame
from PIL import Image, ImageTk
import numpy as np
import tkinter.ttk as ttk

# Initialize or load JSON database
DB_FILE = "db.json"

def load_database():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"textures": {}}

def save_database(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)



# GUI
class TextureTagger:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.texture_paths = self.get_texture_paths()
        self.filtered_texture_paths = self.texture_paths  # For filtering purposes
        self.current_index = self.get_current_index()

        # Set a fixed window size (e.g., 1024x1024)
        self.root.geometry("1600x1024")
        
        # Bind Enter and Space keys
        self.root.bind("<Return>", self.add_tag_event)  # Enter to add tag
        self.root.bind("<space>", self.next_texture_event)  # Space to go to next texture

        # Prevent window resizing
        self.root.resizable(False, False)

        # GUI Elements
        self.resolution_label = Label(root, text="")
        self.resolution_label.pack()

        self.label = Label(root, text="")
        self.label.pack()

        self.image_label = Label(root)
        self.image_label.pack()

        self.tags_listbox = Listbox(root, selectmode="multiple")
        self.tags_listbox.pack()

        self.tag_entry = Entry(root)
        self.tag_entry.pack()
        self.tag_entry.bind("<space>", self.next_texture_event)  # Bind Space key to the Entry widget

        self.add_tag_button = Button(root, text="Add Tag", command=self.add_tag)
        self.add_tag_button.pack()

        # Add Previous and Next buttons
        self.previous_button = Button(root, text="Previous", command=self.previous_texture)
        self.previous_button.pack(side="left", padx=5)

        self.next_button = Button(root, text="Next", command=self.next_texture)
        self.next_button.pack(side="right", padx=5)

        # Add Remove Tag button
        self.remove_tag_button = Button(root, text="Remove Tag", command=self.remove_tag)
        self.remove_tag_button.pack()

        # Create a frame for the togglable buttons
        self.button_frame = Frame(root)
        self.button_frame.pack()

        # Add togglable buttons with tooltips
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
            "tx_metal": "metal",
            "tx_w_": "weapon",
            "tx_wood_": "wood",
            "tx_stone_": "stone"
        }

        self.buttons = {}
        self.active_buttons = set()  # To track active filters
        for key, value in self.button_info.items():
            button = Button(self.button_frame, text=value, command=lambda key=key: self.toggle_button(key))
            button.grid(row=0, column=len(self.buttons), padx=5)
            self.buttons[key] = button

        # Misc button for everything else
        self.misc_button = Button(self.button_frame, text="Misc", command=self.show_all_textures)
        self.misc_button.grid(row=0, column=len(self.buttons), padx=5)

        # Display first texture
        self.display_texture()

    def add_tag_event(self, event=None):
        self.add_tag()  # Trigger the add_tag function on Enter press

    def next_texture_event(self, event=None):
        # Prevent Space key from adding a space to the tag entry
        if self.root.focus_get() == self.tag_entry:
            self.tag_entry.delete(0, END)  # Clear the input box (optional, based on desired behavior)
        self.next_texture()  # Trigger the next_texture function

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

        # Update the label to show the texture path
        self.label.config(text=f"Texture: {os.path.basename(texture_path)}")

        # Load the image
        image = Image.open(texture_path)

        # Get the original resolution
        original_width, original_height = image.size

        # Calculate the new width to maintain the aspect ratio based on a height of 400
        base_height = 400
        aspect_ratio = original_width / original_height
        new_width = int(base_height * aspect_ratio)

        # Resize the image to the new dimensions
        image = image.resize((new_width, base_height))

        # Create a PhotoImage object from the resized image
        photo = ImageTk.PhotoImage(image)

        # Set the image in the label
        self.image_label.config(image=photo)
        self.image_label.image = photo  # Keep a reference to avoid garbage collection

        # Display the original resolution under the image
        resolution_label_text = f"Resolution: {original_width}x{original_height}"
        self.resolution_label.config(text=resolution_label_text)

        # Clear the Listbox and display stored tags for the current texture
        self.tags_listbox.delete(0, END)
        stored_tags = []
        if texture_path in self.db["textures"]:
            stored_tags = self.db["textures"][texture_path].get("tags", [])
            for tag in stored_tags:
                index = self.tags_listbox.size()
                self.tags_listbox.insert(END, tag)
                self.tags_listbox.itemconfig(index, {'bg': 'lightgreen'})  # Mark stored tags with green background


    def toggle_button(self, tag):
        """Toggle the filter for the selected tag and highlight active button."""
        if tag in self.active_buttons:
            self.active_buttons.remove(tag)
            self.buttons[tag].config(bg="lightgray")  # Remove highlight when inactive
        else:
            self.active_buttons.add(tag)
            self.buttons[tag].config(bg="lightblue")  # Highlight active button
        
        # Apply the filtering based on active buttons
        self.apply_filters()

    def apply_filters(self):
        """Apply filters based on active buttons."""
        if self.active_buttons:
            self.filtered_texture_paths = [path for path in self.texture_paths if
                                           any(os.path.basename(path).startswith(tag) for tag in self.active_buttons)]
        else:
            self.filtered_texture_paths = self.texture_paths
        self.current_index = 0  # Reset to the first filtered texture
        self.display_texture()

    def show_all_textures(self):
        """Show all textures"""
        self.active_buttons.clear()  # Clear all filters
        self.filtered_texture_paths = self.texture_paths
        self.current_index = 0
        self.display_texture()
        for button in self.buttons.values():
            button.config(bg="lightgray")  # Reset all buttons to inactive color

    def add_tag(self):
        new_tag = self.tag_entry.get().strip()
        if new_tag:
            # Check if the tag is already in the Listbox
            existing_tags = self.tags_listbox.get(0, END)
            if new_tag not in existing_tags:
                # Add the new tag to the Listbox and select it
                self.tags_listbox.insert(END, new_tag)
                self.tags_listbox.select_set(END)  # Automatically select the newly added tag

            # Clear the input field
            self.tag_entry.delete(0, END)

    def remove_tag(self):
        selected_indices = self.tags_listbox.curselection()
        if selected_indices:
            # Get selected tag
            selected_tag = self.tags_listbox.get(selected_indices[0])

            # Remove the tag from Listbox
            self.tags_listbox.delete(selected_indices[0])

            # Remove tag from the database
            texture_path = self.filtered_texture_paths[self.current_index]
            existing_tags = self.db["textures"].get(texture_path, {}).get("tags", [])
            if selected_tag in existing_tags:
                existing_tags.remove(selected_tag)
                self.db["textures"][texture_path]["tags"] = existing_tags
                save_database(self.db)  # Save updated tags to the database

    def previous_texture(self):
        if self.current_index > 0:
            self.save_current_tags()  # Save current texture's tags
            self.current_index -= 1
            self.display_texture()
        else:
            self.label.config(text="This is the first texture!")

    def next_texture(self):
        if self.current_index < len(self.filtered_texture_paths) - 1:
            self.save_current_tags()  # Save current texture's tags
            self.current_index += 1
            self.display_texture()
        else:
            self.label.config(text="This is the last texture!")

    def save_current_tags(self):
        texture_path = self.filtered_texture_paths[self.current_index]
        selected_tags = [self.tags_listbox.get(i) for i in self.tags_listbox.curselection()]

        # Get existing tags for this texture, if any
        existing_tags = self.db["textures"].get(texture_path, {}).get("tags", [])

        # Merge new tags with existing tags (avoid duplicates)
        merged_tags = list(set(existing_tags + selected_tags))

        # Save updated tags back to the database
        self.db["textures"][texture_path] = {"tags": merged_tags, "status": "tagged"}
        save_database(self.db)


# Main
if __name__ == "__main__":
    db = load_database()
    root = Tk()
    app = TextureTagger(root, db)
    root.mainloop()