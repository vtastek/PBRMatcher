import os
import sys
import subprocess
import multiprocessing
import json
import math
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image

SETTINGS_FILE = "settings.json"

def get_texconv_exe_path():
    if getattr(sys, 'frozen', False):  # If running as PyInstaller executable
        return os.path.join(sys._MEIPASS, "texconv.exe")
    return os.path.join(os.path.dirname(__file__), "texconv.exe")  # Fallback for normal Python execution

def get_texdiag_exe_path():
    if getattr(sys, 'frozen', False):  # If running as PyInstaller executable
        return os.path.join(sys._MEIPASS, "texdiag.exe")
    return os.path.join(os.path.dirname(__file__), "texdiag.exe")  # Fallback for normal Python execution

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f).get("folders", [])
        except json.JSONDecodeError:
            return []
    return []

def save_settings(folders):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"folders": folders}, f)

def calculate_expected_mip_levels(width, height):
    """Calculates the expected number of mip levels for a given resolution."""
    return int(math.log2(max(width, height))) + 1

def parse_texdiag_output(info_lines):
    """Parses texdiag output to extract relevant information."""
    keys_of_interest = ["width", "height", "mipLevels", "format"]
    parsed_info = {}

    for line in info_lines:
        for key in keys_of_interest:
            if key in line:
                parts = line.split("=")
                if len(parts) == 2:
                    parsed_info[key.strip()] = parts[1].strip()

    resolution = f"{parsed_info.get('width', '?')}x{parsed_info.get('height', '?')}"
    mipmaps = parsed_info.get("mipLevels", "?")
    format_ = parsed_info.get("format", "?")
    return f"Resolution: {resolution} | Mipmaps: {mipmaps} | Format: {format_}"

def run_texdiag_command(command, file_path):
    """Runs a specified texdiag command on the DDS file and returns parsed output."""
    texdiag_path = get_texdiag_exe_path()

    if not os.path.exists(texdiag_path):
        return "Error: texdiag.exe not found in the script folder."

    try:
        result = subprocess.run(
            [texdiag_path, command, file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            info_lines = output.split("\n")
            parsed_info = parse_texdiag_output(info_lines)
            return parsed_info
        else:
            return result.stderr.strip()

    except Exception as e:
        return f"Error running texdiag: {e}"

def has_all_mipmaps(dds_path):
    """Checks if a DDS file has all mipmaps by comparing with calculated mip levels."""
    output = run_texdiag_command("info", dds_path)
    
    if "Error" in output:
        print(output)
        return False

    try:
        # Extract relevant details
        details = dict(item.split(": ") for item in output.split(" | "))
        width, height = map(int, details["Resolution"].split("x"))
        mip_levels = int(details["Mipmaps"])
        
        # Compare expected and actual mip levels
        expected_mips = calculate_expected_mip_levels(width, height)
        return mip_levels == expected_mips

    except Exception as e:
        print(f"Error parsing texdiag output: {e}")
    
    return False


def convert_image_to_dxt(image_path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    texconv_path = get_texconv_exe_path()
    
    if not os.path.exists(texconv_path):
        print("Error: texconv.exe not found.")
        return
    
    if image_path.lower().endswith(".dds") and has_all_mipmaps(image_path):
        print(f"Skipping {image_path}, already has mipmaps.")
        return
    
    try:
        img = Image.open(image_path)
        if "_spec.png" in image_path.lower():
            img = img.convert("RGBA")
            r, g, b, a = img.split()
            g = Image.eval(g, lambda x: 255 - x)  # Invert green channel
            b = Image.new("L", img.size, 128)  # Set blue channel to 0.5 (128 in 8-bit)
            img = Image.merge("RGBA", (r, g, b, a))
            img.save(image_path)  # Overwrite original image before conversion
        
        dxt_format = "dxt5" if img.mode == "RGBA" else "dxt1"
        img.close()

        output_dir = os.path.dirname(image_path)
        args = [texconv_path, "-m", "0", "-y", "-f", dxt_format.upper(), "-o", output_dir, image_path]
        subprocess.run(args, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        print(f"Converted: {image_path} to {dxt_format.upper()}")
    except Exception as e:
        print(f"Error: {e}")

def process_folder(input_folder):
    valid_extensions = (".png", ".tga", ".dds")
    image_files = []
    for root, _, files in os.walk(input_folder):
        image_files.extend(os.path.join(root, f) for f in files if f.lower().endswith(valid_extensions))
    
    if len(image_files) > 10:
        confirm = messagebox.askyesno("Confirm", f"This will process {len(image_files)} files. Continue?")
        if not confirm:
            return
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(convert_image_to_dxt, image_files)

def select_folder():
    folder = filedialog.askdirectory()
    if folder:
        if folder not in previous_folders:
            previous_folders.insert(0, folder)
            previous_folders[:] = previous_folders[:5]  # Keep only the last 5 folders
            save_settings(previous_folders)
            listbox.insert(0, folder)  # Update listbox immediately
        process_folder(folder)
        messagebox.showinfo("Done", f"Processing complete for: {folder}")

def remove_selected_folder():
    selected = listbox.curselection()
    if selected:
        folder = listbox.get(selected[0])
        previous_folders.remove(folder)
        save_settings(previous_folders)
        listbox.delete(selected[0])

def create_gui():
    global previous_folders, listbox
    previous_folders = load_settings()

    root = tk.Tk()
    root.title("Image to DXT Converter")
    root.geometry("400x300")

    tk.Label(root, text="Select a folder to process images:").pack(pady=10)
    tk.Button(root, text="Browse", command=select_folder).pack(pady=5)

    tk.Label(root, text="Recent Folders:").pack(pady=10)
    listbox = tk.Listbox(root, height=5)
    listbox.pack(fill=tk.BOTH, expand=True)
    
    for folder in previous_folders:
        listbox.insert(tk.END, folder)
    
    def use_selected_folder():
        selected = listbox.curselection()
        if selected:
            folder = listbox.get(selected[0])
            process_folder(folder)
            messagebox.showinfo("Done", f"Processing complete for: {folder}")
    
    tk.Button(root, text="Use Selected", command=use_selected_folder).pack(pady=5)
    tk.Button(root, text="Remove Selected", command=remove_selected_folder).pack(pady=5)
    root.mainloop()

if __name__ == "__main__":
    multiprocessing.freeze_support()  # Prevents recursive launching in PyInstaller 
    create_gui()
