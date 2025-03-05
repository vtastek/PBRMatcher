import os
import locale
import ctypes
import cv2
import tkinter as tk
import numpy as np
import time


from tkinter import Label, Entry, Button, Listbox, END, Frame, ttk, font, messagebox
from PIL import Image, ImageTk


import modules.api_operations as api_ops

from modules.constants import TARGET_FOLDER, OVERLAY_FOLDER, FILE_CONFIG
from modules.api_operations import fetch_api_data
from modules.thumbnail_operations import fetch_thumbnail
from modules.utility_functions import translate_texture_path, center_window, get_key_by_name
from modules.database_operations import save_database
from modules.glClass import AppOgl
from modules.texture_operations import TextureOperations
from modules.download_manager import DownloadManager



# Enable DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI awareness
    scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100  # Get scaling factor
except AttributeError:
    scale_factor = 1  # Default if unsupported


class TextureTagger:
    def __init__(self, root, db):
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        self.root = root
        self.root.title("Morrowind PBR Texture Project")
        self.db = db
        self.all_assets = api_ops.fetch_api_data("https://api.polyhaven.com/assets?type=textures")

        self.selected_slot = None

        
 

      
        self.texture_paths = self.get_texture_paths()
        self.filtered_texture_paths = self.texture_paths
        self.filtered_texture_names = [os.path.basename(texture_path).replace("textures\\", "") for texture_path in self.filtered_texture_paths]
        self.filtered_texture_names_set = set(self.filtered_texture_names)
        self.root.bind("<Button-1>", self.global_click_handler)
        self.current_index = self.get_current_index()
        self.current_selection = None
        self.thumbnail_cache = {}
        self.cache_size = 20
        self.thumbnail_data_cache = {}
        self.thumbnail_cache_size = 20
        self.current_thumbnail_index = 0
        self.root.configure(bg="#999999")
        base_width, base_height = 1600, 960
        scaled_width = int(base_width * scale_factor)
        scaled_height = int(base_height * scale_factor)
        self.root.geometry(f"{scaled_width}x{scaled_height}")
        text_font = font.nametofont("TkTextFont")
        button_font = font.nametofont("TkTextFont")
        default_size = text_font.actual("size")
        text_size = text_font.actual("size")
        button_size = text_font.actual("size")
        text_font.configure(size=int(text_size * scale_factor + 1))
        button_font.configure(size=int(text_size * scale_factor))
        default_font = text_font
        center_window(root, scaled_width, scaled_height)
        self.root.resizable(False, False)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.main = Frame(self.root, bg="#999999")
        self.main.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(0, weight=1)
        self.gridA = Frame(self.main, bg="#999999", height=700)
        self.gridA.grid(row=0, column=0, sticky="nsew")
        self.gridA.grid_propagate(False)
        self.main.rowconfigure(0, weight=1)
        self.main.columnconfigure(0, weight=1)

        # Define frames with fixed width and borders for debugging
        self.gridA1 = Frame(self.gridA, width=50, bg="#999999")
        self.gridA2 = Frame(self.gridA)  # Flexible width
        self.gridA3 = Frame(self.gridA, width=900, bg="#999999")  # Fixed 900px
        self.gridA4 = Frame(self.gridA)  # Flexible width
        self.gridA5 = Frame(self.gridA, width=50, bg="#999999")  # Fixed 50px

        # Stop automatic resizing
        self.gridA1.grid_propagate(False)
        self.gridA3.grid_propagate(False)
        self.gridA5.grid_propagate(False)

        # Grid placement
        self.gridA1.grid(column=0, row=0, sticky="ns", padx=5)
        self.gridA2.grid(column=1, row=0, sticky="ns")  # Shares remaining space
        self.gridA3.grid(column=2, row=0, sticky="nsew")
        self.gridA4.grid(column=3, row=0, sticky="ns")  # Shares remaining space
        self.gridA5.grid(column=4, row=0, sticky="ns", padx=5)  # Right-aligned

        # Ensure proper column behavior
        self.gridA.columnconfigure(0, weight=0, minsize=50)
        self.gridA.columnconfigure(1, weight=0, minsize=300)  
        self.gridA.columnconfigure(2, weight=1, minsize=900)
        self.gridA.columnconfigure(3, weight=0, minsize=300)  
        self.gridA.columnconfigure(4, weight=0, minsize=50)


        self.gridB = Frame(self.main, bg="#999999")
        self.gridB.grid(column=0, row=1, sticky="nsew")
        self.gridC = Frame(self.main, bg="#999999")
        self.gridC.grid(column=0, row=2, sticky="nsew")


        self.download_frame = Frame(self.gridA4, padx=5, pady=15)
        self.download_frame.grid(row=0, column=0, pady=10, sticky="n")

        self.progress_bar = ttk.Progressbar(self.download_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_label = ttk.Label(self.download_frame, font=9, text="")
        self.progress_label.grid(row=1, columnspan=3, pady=10)
        self.progress_bar.grid(row=2, columnspan=3, pady=5)

        self.texture_operations = TextureOperations(db, self.all_assets)
        self.download_manager = DownloadManager(db, root, self.progress_bar, self.progress_label, self.all_assets)


        self.main.rowconfigure(1, weight=1)
        self.main.rowconfigure(2, weight=1)
        self.texture_name_label = Label(self.gridA3, text="", font=("Arial", int(7 * scale_factor)), pady=10)
        self.texture_name_label.bind("<Button-1>", self.show_entry)
        self.texture_name_label.pack()
        self.texture_name_label.lift()
        self.default_bg = self.texture_name_label.cget("bg")
        self.entry_container = Frame(self.gridA3)
        self.entry_container.place(relx=0.25, rely=0.01)
        self.entry_container.lift()
        self.rotation_label = ttk.Label(self.gridA2, text="Rotation")
        self.rotation_label.pack(pady=5)
        self.rotation_var = tk.IntVar(value=0)
        self.rotation_slider = tk.Scale(self.gridA2, from_=0, to=270, orient="horizontal", command=self.update_rotation, length=300, width=20, resolution=90, sliderlength=30)
        self.rotation_slider.set(0)
        self.rotation_slider.pack()
        self.rotation_display = ttk.Label(self.gridA2, text="Rotation: 0°")
        self.rotation_display.pack()
        self.rotation_slider.bind("<Button-3>", self.reset_rotation)
        self.rotation_slider.bind("<B1-Motion>", self.snap_rotation)
        self.hue_label = ttk.Label(self.gridA2, text="Hue")
        self.hue_label.pack(pady=5)
        self.hue_var = tk.IntVar(value=0)
        self.hue_slider = tk.Scale(self.gridA2, from_=-180, to=180, orient="horizontal", command=self.update_hue, length=300, width=20, sliderlength=30)
        self.hue_slider.set(0)
        self.hue_slider.pack()
        self.hue_display = ttk.Label(self.gridA2, text="Hue: 0")
        self.hue_display.pack()
        self.hue_slider.bind("<Button-3>", self.reset_hue)
        self.saturation_label = ttk.Label(self.gridA2, text="Saturation")
        self.saturation_label.pack(pady=5)
        self.saturation_var = tk.DoubleVar(value=1.0)
        self.saturation_slider = tk.Scale(self.gridA2, from_=0.0, to=1.0, orient="horizontal", command=self.update_saturation, length=300, width=20, sliderlength=30, resolution=0.01)
        self.saturation_slider.set(1.0)
        self.saturation_slider.pack()
        self.saturation_display = ttk.Label(self.gridA2, text="Saturation: 1.0")
        self.saturation_display.pack()
        self.saturation_slider.bind("<Button-3>", self.reset_saturation)
        self.value_label = ttk.Label(self.gridA2, text="Value")
        self.value_label.pack(pady=5)
        self.value_var = tk.DoubleVar(value=1.0)
        self.value_slider = tk.Scale(self.gridA2, from_=0.0, to=1.0, orient="horizontal", command=self.update_value, length=300, width=20, sliderlength=30, resolution=0.01)
        self.value_slider.set(1.0)
        self.value_slider.pack()
        self.value_display = ttk.Label(self.gridA2, text="Value: 1.0")
        self.value_display.pack()
        self.value_slider.bind("<Button-3>", self.reset_value)
        self.save_hsvr_button = Button(self.gridA2, font=7, text="Save HSVR", command=self.save_hsvr)
        self.save_hsvr_button.pack(pady=10)


        self.label_frame = Frame(self.gridA3, bg="black")
        self.label_frame.pack()


        #app.after(100, app.printContext)


        self.image_label = Label(self.label_frame, bg="black")
        self.image_label.pack(fill="both", padx=10, pady=10)
        self.image_label.bind("<Motion>", self.show_zoom_preview)
        self.image_label.bind("<Leave>", self.hide_zoom_preview)


        # Create a container frame within the main window.
        self.gl_container = tk.Frame(self.image_label, width=2, height=2)
        self.gl_container.pack(fill=tk.BOTH, expand=True)

        # Instantiate the OpenGL frame inside the container.
        self.gl_frame = AppOgl(self.gl_container, width=2, height=2)
        self.gl_frame.pack(fill=tk.BOTH, expand=True)
        self.label_frame.bind("<Button-1>", self.gl_frame.hsv_click)

        # Enable animation
        self.gl_frame.animate = 1
        self.gl_frame.update_idletasks()

        self.previous_button = Button(self.gridA1, font=button_font, width=int(7 * scale_factor), text="Previous", command=self.previous_texture)
        self.previous_button.pack(padx=10, pady=5, expand=True)
        self.next_button = Button(self.gridA5, font=button_font, width=int(7 * scale_factor), text="Next", command=self.next_texture)
        self.next_button.pack(padx=10, pady=5, expand=True)
        
        self.add_all_to_queue_button = Button(self.download_frame, font=7, anchor="center", text="DOWNLOAD ALL", command=self.add_all_to_queue)
        self.add_all_to_queue_button.grid(row=0, column=0, padx=5, pady=10, sticky="nwse")
        self.add_to_queue_button = Button(self.download_frame, font=7, anchor="center", text="Add to Queue", command=self.add_to_queue)
        self.add_to_queue_button.grid(row=0, column=1, padx=5, pady=10, sticky="nwse")
        self.show_queue_button = Button(self.download_frame, font=7, anchor="center", text="Show Queue", command=self.show_queue)
        self.show_queue_button.grid(row=0, column=2, padx=5, pady=10, sticky="nwse")
        

        self.slot_frame = Frame(self.download_frame)
        self.slot_frame.grid(row=3, columnspan=3, pady=5)
          
 

        self.slot_buttons = {}
        slot_names = ["A", "B", "C", "D"]
        for slot in range(4):
            self.slot_frame.grid_columnconfigure(slot, weight=1)
            button = Button(self.slot_frame, text=slot_names[slot], width=5, font=7, command=lambda slot=slot_names[slot]: self.switch_slot(slot))
            button.grid(row=4, column=slot, padx=1, sticky="we")
            self.slot_buttons[slot_names[slot]] = button
        for slot_name, button in self.slot_buttons.items():
            button.grid_remove()
        self.preview_label = Label(self.slot_frame, font=default_font, text="No Preview", bg="gray")
        self.preview_label.grid(row=5, column=0, pady=5, columnspan=3)
        self.root.update_idletasks()
        self.tags_frame = Frame(self.gridA3)
        self.tags_frame.pack()
        self.tags_listbox = Listbox(self.tags_frame, selectmode="multiple", height=5)
        self.tags_listbox.grid(row=0, column=0, padx=10)
        self.buttons_frame = Frame(self.tags_frame)
        self.buttons_frame.grid(row=0, column=1, padx=10)
        self.add_tag_button = Button(self.buttons_frame, font=7, text="Add Tag", command=self.add_tag)
        self.add_tag_button.pack(pady=5)
        self.remove_tag_button = Button(self.buttons_frame, font=7, text="Remove Tag", command=self.remove_tag)
        self.remove_tag_button.pack(pady=5)
        self.tag_entry = Entry(self.gridA3)
        self.tag_entry.bind('<Return>', self.tag_return)
        self.tag_entry.pack(pady=5)
        self.button_frame = Frame(self.gridB)
        self.button_frame.pack()
        self.thumbnail_frame = Frame(self.gridB, width=int(455), height=int(555), bg="black")
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

        self.use_file_config = FILE_CONFIG
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
                    translate_texture_path(path) 
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

        #print(f"Filtered paths count: {len(self.filtered_texture_paths)}")
        #print(f"First few paths: {self.filtered_texture_paths[:3]}")

        #print(f"Current index: {self.current_index}")
        #print(f"Filtered paths length: {len(self.filtered_texture_paths)}")

        if self.use_file_config is False:

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

        

            self.all_frame = Frame(self.button_frame)
            self.all_frame.grid(row=1, column=len(self.button_info) + 1, padx=10)

            self.all_label_tagged = Label(self.all_frame, font=5, text="0", fg="green")
            self.all_label_tagged.pack(side="left")

            Label(self.all_frame, text="/").pack(side="left")

            self.all_label_untagged = Label(self.all_frame, font=5, text="0", fg="red")
            self.all_label_untagged.pack(side="left")

        self.selected_thumbnails_label = Label(self.gridC, text="Selected Thumbnails: 0", font=("Arial", 7))
        self.selected_thumbnails_label.pack(pady=5)

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
    
    def update_rotation(self, event):
        """Update rotation with snap to 90-degree increments"""
        value = int(float(event))
        snapped_value = (value // 90) * 90
        if snapped_value != self.rotation_var.get():
            self.rotation_var.set(snapped_value)
            self.rotation_display.config(text=f"Rotation: {snapped_value}°")
        self.rotation_slider.set(snapped_value)
        self.quick_update_texture(rotation=value)

    def update_hue(self, event):
        value = int(float(event))
        self.hue_var.set(value)
        self.hue_display.config(text=f"Hue: {value}")
        self.quick_update_texture(hue=value)

    def update_saturation(self, event):
        value = round(float(event), 2)
        self.saturation_var.set(value)
        self.saturation_display.config(text=f"Saturation: {value}")
        self.quick_update_texture(saturation=value)

    def update_value(self, event):
        value = round(float(event), 2)
        self.value_var.set(value)
        self.value_display.config(text=f"Value: {value}")
        self.quick_update_texture(value=value)

    def reset_rotation(self, event):
        if event.num == 3:  # Right-click
            event.widget.event_generate('<Button-1>', x=0, y=0)  # Cancel the right-click set
            self.rotation_var.set(0)
            self.rotation_slider.set(0)
            self.rotation_display.config(text="Rotation: 0°")
        return "break"  # Prevent default right-click behavior
    
    def snap_rotation(self, event):
        """Handle visual snapping during drag"""
        value = self.rotation_slider.get()
        snapped_value = (int(value) // 90) * 90
        self.rotation_slider.set(snapped_value)
    
    def reset_hue(self, event):
        if event.num == 3:  # Right-click
            event.widget.event_generate('<Button-1>', x=0, y=0)  # Cancel the right-click set
            self.hue_var.set(0)
            self.hue_display.config(text="Hue: 0")
            self.hue_slider.set(0)
            return "break"

    def reset_saturation(self, event):
        if event.num == 3:  # Right-click
            event.widget.event_generate('<Button-1>', x=0, y=0)  # Cancel the right-click set
            self.saturation_var.set(1.0)
            self.saturation_display.config(text="Saturation: 1.0")
            self.saturation_slider.set(1.0)
            return "break"

    def reset_value(self, event):
        if event.num == 3:  # Right-click
            event.widget.event_generate('<Button-1>', x=0, y=0)  # Cancel the right-click set
            self.value_var.set(1.0)
            self.value_display.config(text="Value: 1.0")
            self.value_slider.set(1.0)
            return "break"
        

    def update_hsvr_settings(self, hsvr_settings, update_texture=True):
        """
        Update all HSVR sliders and displays at once from a settings dictionary
        
        Args:
            hsvr_settings: Dictionary with keys 'hue', 'saturation', 'value', 'rotation'
            update_texture: Whether to update the texture after setting values
        """
        # Update hue
        hue = int(float(hsvr_settings.get("hue", 0)))
        self.hue_var.set(hue)
        self.hue_display.config(text=f"Hue: {hue}")
        self.hue_slider.set(hue)
        
        # Update saturation
        saturation = round(float(hsvr_settings.get("saturation", 1.0)), 2)
        self.saturation_var.set(saturation)
        self.saturation_display.config(text=f"Saturation: {saturation}")
        self.saturation_slider.set(saturation)
        
        # Update value
        value = round(float(hsvr_settings.get("value", 1.0)), 2)
        self.value_var.set(value)
        self.value_display.config(text=f"Value: {value}")
        self.value_slider.set(value)
        
        # Update rotation (with snap to 90 degrees)
        rotation = int(float(hsvr_settings.get("rotation", 0)))
        snapped_rotation = (rotation // 90) * 90
        self.rotation_var.set(snapped_rotation)
        self.rotation_display.config(text=f"Rotation: {snapped_rotation}°")
        self.rotation_slider.set(snapped_rotation)
        
        # Update texture if requested
        if update_texture:
            self.quick_update_texture(
                hue=hue,
                saturation=saturation,
                value=value,
                rotation=snapped_rotation
            )

    def reset_hsvr(self, update_texture=True):
        """
        Reset all HSVR sliders to their default values
        
        Args:
            update_texture: Whether to update the texture after resetting values
        """
        # Reset hue to 0
        self.hue_var.set(0)
        self.hue_display.config(text="Hue: 0")
        self.hue_slider.set(0)
        
        # Reset saturation to 1.0
        self.saturation_var.set(1.0)
        self.saturation_display.config(text="Saturation: 1.0")
        self.saturation_slider.set(1.0)
        
        # Reset value to 1.0
        self.value_var.set(1.0)
        self.value_display.config(text="Value: 1.0")
        self.value_slider.set(1.0)
        
        # Reset rotation to 0
        self.rotation_var.set(0)
        self.rotation_display.config(text="Rotation: 0°")
        self.rotation_slider.set(0)
        
        # Update texture if requested
        if update_texture:
            self.quick_update_texture(
                hue=0,
                saturation=1.0,
                value=1.0,
                rotation=0
            )

    def save_hsvr(self, slot_index=None):
        """Save the current HSVR values to the database for the selected thumbnail"""
        # Get current HSVR values
        hsvr = {
            "rotation": self.rotation_var.get(),
            "hue": self.hue_var.get(),
            "saturation": self.saturation_var.get(),
            "value": self.value_var.get()
        }
        
        print(f"Debug - HSVR values to save: {hsvr}")
        print(f"Debug - Slot index: {slot_index}")
        
        # Get the current texture path
        current_texture = self.filtered_texture_paths[self.current_index]
        print(f"Debug - Current texture path: {current_texture}")
        
        # Check if texture exists in database
        if current_texture not in self.db["textures"]:
            print(f"Error - Texture {current_texture} not found in database")
            return
        
        # Get the selected thumbnails for the current texture
        selected_thumbnails = self.db["textures"][current_texture]["selected_thumbnails"]
        print(f"Debug - Selected thumbnails: {selected_thumbnails}")
        print(f"Debug - Number of selected thumbnails: {len(selected_thumbnails)}")
        
        if len(selected_thumbnails) == 0:
            print("Error - No selected thumbnails found")
            return
        
        if len(selected_thumbnails) > 0:
            slot_index = ord(self.selected_slot) - ord('A')
            print(f"Debug - Slot index: {slot_index}")
            
        if not (0 <= slot_index < len(selected_thumbnails)):
            print(f"Error - Slot index {slot_index} out of range (0-{len(selected_thumbnails)-1 if selected_thumbnails else -1})")
            return
        
        # Update the HSVR values for the selected thumbnail
        thumbnail = selected_thumbnails[slot_index]
        print(f"Debug - Selected thumbnail at slot {slot_index}: {thumbnail}")
        
        # Add HSVR data to the thumbnail if it doesn't exist already
        if "hsvr" not in thumbnail:
            print("Debug - Adding new hsvr field to thumbnail")
            thumbnail["hsvr"] = {}
            
        # Update the HSVR values
        thumbnail["hsvr"] = hsvr
        
        # Save changes to the database
        save_database(self.db)
        
        print(f"Success - Saved HSVR values for '{thumbnail['name']}' at slot {slot_index}")

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

        texture_name = texture_name.replace(".png", "")
        texture_name = f"{texture_name}.png"

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
                self.display_thumbnails()

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
                self.display_thumbnails()
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
        self.display_texture()
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

        if self.use_file_config:
            file_config = self.load_button_config_from_file()
            counts = {name: {"tagged": 0, "untagged": 0, "assigned": 0} for name in self.button_info.keys()}
            
            for button_name, paths in file_config.items():
                total_paths = len(paths)
                for path in paths:
                    translated_path = translate_texture_path(path)
                    if translated_path in self.db["textures"]:
                        tags = self.db["textures"][translated_path].get("tags", [])
                        selected = self.db["textures"][translated_path].get("selected_thumbnails", [])
                        
                        if tags:
                            counts[button_name]["tagged"] += 1
                        if selected:
                            counts[button_name]["assigned"] += 1

                counts[button_name]["untagged"] = total_paths - counts[button_name]["tagged"]
     

            for name, count in counts.items():
                self.label_frames[f"{name}_tagged"].config(text=str(count["tagged"]))
                self.label_frames[f"{name}_untagged"].config(text=str(count["untagged"]))
                self.label_frames[f"{name}_assigned"].config(text=str(count["assigned"]))
        else:

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
        #selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
        selected_thumbnails = [
            thumb["name"]
            for key in self.db["textures"]
            if key.lower() == texture_path.lower()
            for thumb in self.db["textures"][key].get("selected_thumbnails", [])
        ]
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
                thumbnail_name = get_key_by_name(self.all_assets, thumbnail_name)
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
                        #selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
                        selected_thumbnails = [
                            thumb["name"] if isinstance(thumb, dict) else thumb
                            for thumb in self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
                        ]
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

        # Check if the texture_id is already selected
        is_selected = any(item["name"] == texture_id for item in selected_thumbnails)

        if is_selected:
            # Deselect: Remove the dictionary with the matching "name"
            selected_thumbnails[:] = [item for item in selected_thumbnails if item["name"] != texture_id]
            container.config(highlightbackground="gray", highlightthickness=2)
        else:
            # Select: Add a new dictionary with the "name" key
            selected_thumbnails.append({"name": texture_id})
            container.config(highlightbackground="blue", highlightthickness=2)

        # Save changes to the database
        save_database(self.db)
        self.update_counts()

    def next_thumbnails(self):
        # Update the index and display thumbnails
        # Calculate the current page and total pages
        thumbnails_per_page = 5
        total_thumbnails = len(self.get_matching_textures())
        max_index = (total_thumbnails // thumbnails_per_page) * thumbnails_per_page

        self.current_thumbnail_index = min(self.current_thumbnail_index + 5, max_index)

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

    def quick_update_texture(self, rotation=None, hue=None, saturation=None, value=None):
        # If no overlay image is currently loaded, do nothing
        if not hasattr(self, 'overlay_image') or self.overlay_image is None:
            print("No overlay image loaded.")
            return
        
         # Use current values if not specified
        rotation = self.rotation_var.get() if rotation is None else rotation
        hue = self.hue_var.get() if hue is None else hue
        saturation = self.saturation_var.get() if saturation is None else saturation
        value = self.value_var.get() if value is None else value

        self.gl_frame.set_rotation(rotation)
        self.gl_frame.set_hue(hue)
        self.gl_frame.set_saturation(saturation)
        self.gl_frame.set_value(value)
            
    def display_texture(self, entered_texture_name = None, manipulated_overlay_image=None):
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
            #print(f"Filtered paths count: {len(self.filtered_texture_paths)}")
            texture_path = self.filtered_texture_paths[self.current_index]
            

        texture_name = os.path.basename(texture_path)

        # Update the texture name label
        self.texture_name_label.config(text=f"Texture: {texture_name}")

        texture_name_result = texture_name.replace("_result", "")
        self.update_texture_label(texture_name_result)

        #selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
        selected_thumbnails = [
                thumb["name"] if isinstance(thumb, dict) else thumb
                for thumb in self.db["textures"].get(texture_path.lower(), {}).get("selected_thumbnails", [])
            ]
        
        # Change this line:
        selected_thumbnails_data = self.db["textures"].get(texture_path.lower(), {}).get("selected_thumbnails", [])

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

        # Load the zoom image (used as the base image)
        zoom_image = self.texture_operations.load_image(texture_path.lower())
        if zoom_image is None:
            print(f"Failed to load zoom image: \n\n\n\n{texture_path}\n\n\n\n")
            return

        # Set default image
        image = zoom_image
        self.current_zoom_image = zoom_image

        # Validate slot_index before accessing selected_thumbnails
        if slot_index is not None and 0 <= slot_index < len(selected_thumbnails):
            #print("SLOT:", slot_index)
            thumbnail_name = selected_thumbnails[slot_index]
            thumbnail_name = get_key_by_name(self.all_assets, thumbnail_name)
            diff_overlay_path = os.path.join(OVERLAY_FOLDER, f"{thumbnail_name}_overlay.png")
            col_overlay_path = os.path.join(OVERLAY_FOLDER, f"{thumbnail_name}_overlay.png")
            print(diff_overlay_path)
            print(col_overlay_path)

            # Check for existence of overlay images
            overlay_path = None
            if os.path.exists(diff_overlay_path):
                overlay_path = diff_overlay_path
            elif os.path.exists(col_overlay_path):
                overlay_path = col_overlay_path
            if overlay_path is None:
                print(f"No overlay match found for: {thumbnail_name}")
        else:
            overlay_path = None

        display_image = self.prepare_display_image(image)
    
        self.d_width, self.d_height = display_image.size
        
        self.label_frame.config(width=self.d_width, height=self.d_height)
        self.label_frame.pack_propagate(False)  # This prevents the frame from resizing to fit contents
        self.label_frame.pack()
        self.image_label.config(width=self.d_width, height=self.d_height)
        self.image_label.pack_propagate(False)  # This prevents the label from resizing to fit contents
        self.image_label.pack()

        self.gl_frame.set_initial_size(self.d_width, self.d_height)
        self.gl_frame.GL_update_texture(display_image)
        
        if overlay_path:
            overlay_image = self.texture_operations.load_image(overlay_path)
            if overlay_image is not None:
                overlay_image = self.prepare_display_image(overlay_image)
                self.overlay_image = overlay_image
                self.gl_frame.GL_update_texture(overlay_image, 1)
                self.gl_frame.set_mix_ratio(0.5)
            else:
                print(f"Failed to load overlay image: {overlay_path}")
                self.gl_frame.set_mix_ratio(0.0)
        else:
            self.gl_frame.set_mix_ratio(0.0)

        # Check if selected_thumbnail has HSVR settings in the database
        if selected_thumbnails:
            # Map slot (A, B, C, D) to index
            slot_index = ord(self.selected_slot) - ord('A') if self.selected_slot else 0
            
            # Validate slot_index before accessing selected_thumbnails
            if 0 <= slot_index < len(selected_thumbnails):
                thumb = selected_thumbnails[slot_index]
                # If selected_thumbnails is a list of dictionaries as shown in your JSON
                thumb_data = selected_thumbnails_data[slot_index]
                print(f"Debug - Full thumbnail data: {thumb_data}")

                # Check if thumb_data is a dictionary with the expected structure
                if isinstance(thumb_data, dict):
                    thumb_name = thumb_data.get("name", "Unknown")
                    print(f"Debug - Thumbnail name: {thumb_name}")
                    
                    # Get HSVR settings if available
                    if "hsvr" in thumb_data:
                        hsvr_settings = thumb_data["hsvr"]

                        print(f"Debug - HSVR settings found: {hsvr_settings}")
                        # Apply the saved HSVR values
                        self.update_hsvr_settings(thumb_data["hsvr"])

                    else:
                        print("No HSVR settings in thumb_data")
                        # Reset to default values if no HSVR settings found
                        # Use default values
                        default_hsvr = {
                            "hue": 0,
                            "saturation": 1.0,
                            "value": 1.0,
                            "rotation": 0
                        }
                        self.update_hsvr_settings(default_hsvr)
                                    
                        print(f"No HSVR settings found for thumbnail at slot {self.selected_slot}, using defaults")
                else:
                    # Handle the case where thumb_data is already just a string
                    thumb_name = thumb_data
                    print(f"Debug - Thumbnail is just a string: {thumb_name}")
                    print("No HSVR settings available - thumb is not a dictionary")

        # Clear and display tags
        self.tags_listbox.delete(0, END)
        stored_tags = self.db["textures"].get(texture_path.lower(), {}).get("tags", [])
        for tag in stored_tags:
            self.tags_listbox.insert(END, tag)

        # Display thumbnails of related textures
        self.display_thumbnails()

    

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
        display_width, display_height = self.display_image_size
        full_width, full_height = self.full_res_image.size

        # Adjust for potential mirroring or offset
        adjusted_x = event.x * (full_width / display_width)
        adjusted_y = event.y * (full_height / display_height)

        # Apply a small left-side offset (5% of width)
        left_offset = full_width * 0.05
        adjusted_x = max(0, adjusted_x - left_offset)

        # Determine the corresponding coordinates in the full-resolution image
        full_x = int(adjusted_x)
        full_y = int(adjusted_y)

        # Define the size of the zoom preview box
        zoom_box_size = 200  # Fixed size for consistent zoom
        half_box_size = zoom_box_size // 2

        # Create a black background canvas
        zoom_canvas = Image.new('RGBA', (zoom_box_size, zoom_box_size), (0, 0, 0, 255))

        # Calculate the bounding box for cropping
        left = max(0, full_x - half_box_size)
        upper = max(0, full_y - half_box_size)
        right = min(full_width, full_x + half_box_size)
        lower = min(full_height, full_y + half_box_size)

        # Crop the available portion of the image
        try:
            cropped_zoom = self.full_res_image.crop((left, upper, right, lower))
            
            # Calculate offset for placing the cropped image on the black canvas
            canvas_x = max(0, half_box_size - full_x)
            canvas_y = max(0, half_box_size - full_y)
            
            # Paste the cropped image onto the black canvas
            zoom_canvas.paste(cropped_zoom, (canvas_x, canvas_y))
        except Exception as e:
            print(f"Error creating zoom box: {e}")

        # Resize the zoom box for display
        zoom_box = zoom_canvas.resize((300, 300), Image.LANCZOS)
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

    def tag_return(self, event):
        self.add_tag()

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

        total_thumbnails = len(self.get_matching_textures())
        self.current_thumbnail_index = max(self.current_thumbnail_index - 5, 0)

        # Calculate the current page and total pages
        thumbnails_per_page = 5
        current_page = 0
        total_pages = (total_thumbnails // thumbnails_per_page) + (1 if total_thumbnails % thumbnails_per_page > 0 else 0)
        
        # Update the page indicator
        self.page_indicator.config(text=f"{current_page}/{total_pages}")
       
        self.update_pagination()
        self.display_thumbnails()


    

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

        # Reset to the first page
        self.current_thumbnail_index = 0

        self.apply_filters()
        self.update_pagination()
        self.display_thumbnails()


    def add_all_to_queue(self):
        self.download_manager.add_all_to_queue()

    def show_queue(self):
        self.download_manager.show_queue()

    def add_to_queue(self):
        if not self.selected_slot:
            messagebox.showerror("Error", "No slot selected for download.")
            return

        current_texture = self.filtered_texture_paths[self.current_index]
        selected_thumbnails = self.db["textures"].get(current_texture, {}).get("selected_thumbnails", [])
        slot_index = ord(self.selected_slot) - ord('A')
        if slot_index < 0 or slot_index >= len(selected_thumbnails):
            messagebox.showerror("Error", f"No thumbnail found for slot {self.selected_slot}.")
            return

        thumbnail_name = selected_thumbnails[slot_index]
        texture_name_label = os.path.basename(current_texture).replace(".png", "")
        self.download_manager.add_to_queue(current_texture, thumbnail_name, texture_name_label, self.selected_slot)


    

    def update_pagination(self):
        # Get the total number of thumbnails and calculate the total pages
        total_thumbnails = len(self.get_matching_textures())
        thumbnails_per_page = 5
        total_pages = (total_thumbnails // thumbnails_per_page) + (1 if total_thumbnails % thumbnails_per_page > 0 else 0)
        
        # Calculate the current page
        current_page = 0 #(self.current_thumbnail_index // thumbnails_per_page)
        
        # Update the page indicator label
        self.page_indicator.config(text=f"{current_page + 1}/{total_pages}")

    def apply_filters(self):
        """Apply filters based on active buttons and config type"""
        if self.use_file_config:
            # Get paths only from active button categories
            file_button_config = self.load_button_config_from_file()
            if not self.active_buttons:
                self.filtered_texture_paths = [
                    path for paths in file_button_config.values() 
                    for path in paths
                ]
            else:
                self.filtered_texture_paths = [
                    translate_texture_path(path)
                    for button in self.active_buttons
                    for path in file_button_config.get(button, [])
                ]
        else:
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
        texture_path = texture_path.lower()

        # Retrieve tags for the current texture
        texture_key = next((k for k in self.db["textures"] if k.lower() == texture_path), None)
        current_tags = self.db["textures"].get(texture_key, {}).get("tags", [])
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

    