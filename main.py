import os
import json
from tkinter import Tk, Label, Entry, Button, Listbox, END, filedialog
from PIL import Image, ImageTk
import tensorflow as tf
import numpy as np

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

# AI Model Initialization
def load_model():
    model = tf.keras.applications.MobileNetV2(weights="imagenet", include_top=True)
    return model

def classify_image(model, image_path):
    image = tf.keras.preprocessing.image.load_img(image_path, target_size=(224, 224))
    input_arr = tf.keras.preprocessing.image.img_to_array(image)
    input_arr = np.expand_dims(input_arr, axis=0)
    input_arr = tf.keras.applications.mobilenet_v2.preprocess_input(input_arr)
    predictions = model.predict(input_arr)
    decoded = tf.keras.applications.mobilenet_v2.decode_predictions(predictions, top=3)
    return [pred[1] for pred in decoded[0]]  # Return top-3 predicted labels

# GUI
class TextureTagger:
    def __init__(self, root, db, model):
        self.root = root
        self.db = db
        self.model = model
        self.texture_paths = self.get_texture_paths()
        self.current_index = self.get_current_index()
        
        # Set a fixed window size (e.g., 600x600)
        self.root.geometry("1024x1024")
        
        # Bind Enter and Space keys
        self.root.bind("<Return>", self.add_tag_event)  # Enter to add tag
        self.root.bind("<space>", self.next_texture_event)  # Space to go to next texture

        # Prevent window resizing
        self.root.resizable(False, False)
        
        # GUI Elements
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
        for i, path in enumerate(self.texture_paths):
            if path not in self.db["textures"]:
                return i
        return len(self.texture_paths)

    def display_texture(self):
        # Get the current texture path
        texture_path = self.texture_paths[self.current_index]
        
        # Update the label to show the texture path
        self.label.config(text=f"Texture: {os.path.basename(texture_path)}")
        
        # Display the image
        image = Image.open(texture_path)
        image.thumbnail((400, 400))
        photo = ImageTk.PhotoImage(image)
        self.image_label.config(image=photo)
        self.image_label.image = photo

        # Clear the Listbox and display stored tags for the current texture
        self.tags_listbox.delete(0, END)
        stored_tags = []
        if texture_path in self.db["textures"]:
            stored_tags = self.db["textures"][texture_path].get("tags", [])
            for tag in stored_tags:
                index = self.tags_listbox.size()
                self.tags_listbox.insert(END, tag)
                self.tags_listbox.itemconfig(index, {'bg': 'lightgreen'})  # Mark stored tags with green background

        # Get AI suggestions for the current texture
        ai_suggestions = classify_image(self.model, texture_path)
        for tag in ai_suggestions:
            if tag not in stored_tags:  # Avoid duplicates in the Listbox
                index = self.tags_listbox.size()
                self.tags_listbox.insert(END, tag)





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
            texture_path = self.texture_paths[self.current_index]
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
        if self.current_index < len(self.texture_paths) - 1:
            self.save_current_tags()  # Save current texture's tags
            self.current_index += 1
            self.display_texture()
        else:
            self.label.config(text="This is the last texture!")

    def save_current_tags(self):
        texture_path = self.texture_paths[self.current_index]
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
    model = load_model()

    root = Tk()
    app = TextureTagger(root, db, model)
    root.mainloop()
