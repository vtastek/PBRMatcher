import os
import json
from tkinter import Tk, Label, Entry, Button, Listbox, END, Frame
from PIL import Image, ImageTk

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

        # Set a fixed window size
        self.root.geometry("1600x1024")

        # Prevent window resizing
        self.root.resizable(False, False)

        # GUI Elements
        self.texture_name_label = Label(root, text="", font=("Arial", 14), pady=10)
        self.texture_name_label.pack()

        self.image_label = Label(root)
        self.image_label.pack()

        self.tags_listbox = Listbox(root, selectmode="multiple")
        self.tags_listbox.pack()

        self.tag_entry = Entry(root)
        self.tag_entry.pack()

        self.add_tag_button = Button(root, text="Add Tag", command=self.add_tag)
        self.add_tag_button.pack()

        self.previous_button = Button(root, text="Previous", command=self.previous_texture)
        self.previous_button.pack(side="left", padx=5)

        self.next_button = Button(root, text="Next", command=self.next_texture)
        self.next_button.pack(side="right", padx=5)

        self.remove_tag_button = Button(root, text="Remove Tag", command=self.remove_tag)
        self.remove_tag_button.pack()

        # Create a frame for togglable buttons
        self.button_frame = Frame(root)
        self.button_frame.pack()

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
            "tx_metal": "metal",
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
        base_height = 400
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
        texture_path = self.filtered_texture_paths[self.current_index]
        new_tag = self.tag_entry.get().strip()
        if new_tag:
            existing_tags = self.db["textures"].get(texture_path, {}).get("tags", [])
            if new_tag not in existing_tags:
                existing_tags.append(new_tag)
                self.db["textures"].setdefault(texture_path, {})["tags"] = existing_tags
                save_database(self.db)
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


# Main
if __name__ == "__main__":
    db = load_database()
    root = Tk()
    app = TextureTagger(root, db)
    root.mainloop()
