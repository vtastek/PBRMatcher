import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import subprocess
import os

# Global variables to track folder files, current file index, and channel selection
file_list = []
current_file_index = -1
img_display = None
original_img = None
channels_selected = {"R": True, "G": True, "B": True, "A": True}

def apply_channel_mask():
    """Applies the channel mask to the original image and updates the display."""
    global img_display, original_img

    if original_img is None:
        return

    if original_img.mode not in ("RGBA", "RGB"):
        img_filtered = original_img  # Skip filtering for unsupported modes
    else:
        r, g, b, a = original_img.split() if original_img.mode == "RGBA" else (*original_img.split(), None)
        r = r if channels_selected["R"] else Image.new("L", original_img.size, 0)
        g = g if channels_selected["G"] else Image.new("L", original_img.size, 0)
        b = b if channels_selected["B"] else Image.new("L", original_img.size, 0)
        if a:
            a = a if channels_selected["A"] else Image.new("L", original_img.size, 255)  # Replace alpha with full opacity
            img_filtered = Image.merge("RGBA", (r, g, b, a))
        else:
            img_filtered = Image.merge("RGB", (r, g, b))

    # Resize the image for display if needed
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    max_width = min(img_filtered.size[0], screen_width - 50)
    max_height = min(img_filtered.size[1], screen_height - 100)

    img_display_resized = img_filtered.copy()
    if img_filtered.size[0] > max_width or img_filtered.size[1] > max_height:
        scale_factor = min(max_width / img_filtered.size[0], max_height / img_filtered.size[1])
        new_size = (int(img_filtered.size[0] * scale_factor), int(img_filtered.size[1] * scale_factor))
        img_display_resized = img_filtered.resize(new_size, Image.LANCZOS)

    img_display = ImageTk.PhotoImage(img_display_resized)

    # Update the canvas
    canvas.config(width=max_width, height=max_height)
    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=img_display)

def load_dds(file_path=None):
    """Loads a DDS file, displays its info, updates the status bar, and sets the title."""
    global img_display, current_file_index, file_list, original_img

    if file_path is None:
        file_path = filedialog.askopenfilename(
            title="Select a DDS file",
            filetypes=[("DDS files", "*.dds")],
        )

    if not file_path:
        return

    try:
        folder_path = os.path.dirname(file_path)
        file_list = sorted(
            [os.path.normcase(os.path.abspath(os.path.join(folder_path, f))) for f in os.listdir(folder_path) if f.lower().endswith(".dds")]
        )
        file_path = os.path.normcase(os.path.abspath(file_path))
        current_file_index = file_list.index(file_path)

        with Image.open(file_path) as img:
            original_img = img.convert("RGBA")  # Ensure RGBA mode for consistency
            apply_channel_mask()  # Apply the initial channel mask

        # Update status bar and window title
        texdiag_info = run_texdiag_command("info", file_path)
        status_text.set(texdiag_info)
        filename = os.path.basename(file_path)
        root.title(f"{filename} ({current_file_index + 1}/{len(file_list)}) - DDS Viewer with TexDiag")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load DDS file: {e}")

def navigate_files(direction):
    """Navigate to the previous or next DDS file."""
    global current_file_index

    if not file_list:
        return

    current_file_index = (current_file_index + direction) % len(file_list)
    load_dds(file_list[current_file_index])

def toggle_channel(channel):
    """Toggles the selected RGBA channel and refreshes the image display."""
    channels_selected[channel] = not channels_selected[channel]
    apply_channel_mask()

def run_texdiag_command(command, file_path):
    """Runs a specified texdiag command on the DDS file and returns parsed output."""
    texdiag_path = "texdiag.exe"

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

# Create the main Tkinter window
root = tk.Tk()
root.title("DDS Viewer with TexDiag")

# Create a frame for the canvas and buttons
frame = tk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True)

# Canvas to display the image
canvas = tk.Canvas(frame, bg="gray")
canvas.pack(fill=tk.BOTH, expand=True)

# Status bar to show image info
status_text = tk.StringVar()
status_text.set("No file loaded")
status_bar = tk.Label(root, textvariable=status_text, bd=1, relief=tk.SUNKEN, anchor=tk.W)
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

# Menu for file operations
menu = tk.Menu(root)
root.config(menu=menu)

# File menu
file_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Open DDS...", command=load_dds)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# RGBA toggle buttons
channel_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Channels", menu=channel_menu)
for channel in ["R", "G", "B", "A"]:
    channel_menu.add_checkbutton(label=channel, onvalue=True, offvalue=False, command=lambda c=channel: toggle_channel(c))

# Key bindings for left and right arrow keys
root.bind("<Left>", lambda event: navigate_files(-1))
root.bind("<Right>", lambda event: navigate_files(1))

# Run the Tkinter main loop
root.mainloop()
