import os
import requests
import threading
import hashlib
import re

from tkinter import messagebox
from urllib.parse import urlparse

from modules.utility_functions import get_key_by_name
from modules.texture_operations import TextureOperations

class DownloadManager:
    def __init__(self, db, root, progress_bar, progress_label, all_assets):
        self.db = db
        self.root = root
        self.progress_bar = progress_bar
        self.progress_label = progress_label
        self.download_queue = []
        self.completed_downloads = []
        self.in_progress = []
        self.currently_downloading = False
        self.all_assets = all_assets
        self.texture_operations = TextureOperations(db, all_assets)


    def add_to_queue(self, current_texture, thumbnail_name, texture_name_label, selected_slot):
        """Add the selected thumbnail and texture label to the download queue."""
        if not selected_slot:
            messagebox.showerror("Error", "No slot selected for download.")
            return

        # Add to the queue
        self.download_queue.append((current_texture, thumbnail_name, texture_name_label))
        #print(f"[DEBUG] Added to queue: path: {current_texture}, Texture: {texture_name_label}, Thumbnail: {thumbnail_name}")
        #print(f"[DEBUG] Current Queue Length: {len(self.download_queue)}")

        # Start processing the queue if idle
        if not self.currently_downloading:
            self.process_queue()

        self.update_progress_label()

    def add_all_to_queue(self):
        """Add all textures and their selected thumbnails to the download queue, with confirmation."""
        if not self.filtered_texture_paths:
            messagebox.showerror("Error", "No textures available to add to the queue.")
            return

        for texture_path in self.filtered_texture_paths:
            #selected_thumbnails = self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])

            selected_thumbnails = [
                thumb["name"] if isinstance(thumb, dict) else thumb
                for thumb in self.db["textures"].get(texture_path, {}).get("selected_thumbnails", [])
            ]

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
        #print(f"[DEBUG] Added all textures to queue. Current Queue Length: {len(self.download_queue)}")

        # Start processing the queue if idle
        if not self.currently_downloading:
            self.process_queue()

        self.update_progress_label()

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
        self.progress_bar["maximum"] = 100

        def smooth_progress_update():
            """Gradually update the progress bar."""
            if self.smoothed_progress < self.actual_progress:
                self.smoothed_progress += (self.actual_progress - self.smoothed_progress) * 0.1
                self.progress_bar["value"] = min(self.smoothed_progress, 100)
            if self.smoothed_progress < 100:
                self.root.after(50, smooth_progress_update)

        smooth_progress_update()
        download_thread = threading.Thread(
            target=self._perform_download, args=(texture_path, thumbnail_name, texture_name_label), daemon=True
        )
        download_thread.start()

    def _perform_download(self, texture_path, thumbnail_name, texture_name_label):
        """Perform the actual download process for a specific texture and thumbnail."""
        try:
            # Download logic here
            pass
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during download: {e}")
        finally:
            self.update_progress_label()
            self.in_progress.remove((texture_path, thumbnail_name, texture_name_label))
            self.completed_downloads.append((texture_path, thumbnail_name, texture_name_label))
            if self.download_queue:
                self.process_queue()
            else:
                self.currently_downloading = False
                messagebox.showinfo("Queue", "All downloads completed.")
                self.update_progress_label()

    def update_progress_label(self):
        """Update the progress label with the current counts of completed, in-progress, and pending downloads."""
        completed_count = len(self.completed_downloads)
        in_progress_count = len(self.in_progress)
        pending_count = len(self.download_queue)
        
        self.progress_label.config(
            text=f"{completed_count} / {pending_count + in_progress_count}"
        )

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
            thumbnail_name = thumbnail_name["name"]            
            print("get key by name line 256: ", thumbnail_name)
            print("ALL ASSETS: ", self.all_assets)
            texture_id_download = get_key_by_name(self.all_assets, thumbnail_name)
            print("texture id:", texture_id_download)
            

            texture_path = os.path.normpath(texture_path.strip())
            texture_name_label = texture_name_label.strip()

            
            # Construct the download URL
            url = f"https://api.polyhaven.com/files/{texture_id_download}"

            print("url: ", url)


            # Create the "staging" folder if it doesn't exist
            if not os.path.exists("staging"):
                os.makedirs("staging")
            
            # Fetch texture metadata
            data = requests.get(url)
            if data.status_code != 200:
                messagebox.showerror("Error", f"Failed to fetch texture metadata for '{thumbnail_name}'. Status code: {data.status_code}")
                return

            # Extract URLs and MD5 checksums
            texture_files = self.extract_files_with_md5(data.json())

            # Filter files based on required file types
            required_files = ["_diffuse_4k.png", "_diff_4k.png", "_color_4k.png", "_nor_dx_4k.png", "_arm_4k.png", "_disp_4k.png", "_height_4k.png"]
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
            self.texture_operations.combine_textures(texture_path, texture_id_download, texture_name_label)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during download: {e}")

        finally:
            try:
                # Update the progress label
                self.update_progress_label()

                # Debug: Check tuple being removed
                normalized_tuple = (texture_path, thumbnail_name, texture_name_label)
                #print("[DEBUG] Trying to remove (normalized):", repr(normalized_tuple))

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
                self.update_progress_label()
                self.completed_downloads = []

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