import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import subprocess
import os
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Enable DPI awareness
except AttributeError:
    pass  # Not supported on some older Windows versions


# Global variables to track folder files, current file index, and channel selection
file_list = []
current_file_index = -1
img_display = None
original_img = None
channels_selected = {"R": True, "G": True, "B": True, "A": True}

def center_window(width, height):
    """Centers the window on the screen."""
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2) - 50
    root.geometry(f"{width}x{height}+{x}+{y}")


def apply_channel_mask():
    """Applies the channel mask to the original image and updates the display."""
    global img_display, original_img

    if original_img is None:
        return

    if original_img.mode not in ("RGBA", "RGB"):
        img_filtered = original_img  # Skip filtering for unsupported modes
    else:
        # Split channels
        r, g, b, a = original_img.split() if original_img.mode == "RGBA" else (*original_img.split(), None)
        r = r if channels_selected["R"] else Image.new("L", original_img.size, 0)
        g = g if channels_selected["G"] else Image.new("L", original_img.size, 0)
        b = b if channels_selected["B"] else Image.new("L", original_img.size, 0)

        # Check if a single channel is selected
        active_channels = [ch for ch in ["R", "G", "B", "A"] if channels_selected[ch]]
        if len(active_channels) == 1:
            single_channel = active_channels[0]
            # Use grayscale data of the active channel
            single_channel_data = {"R": r, "G": g, "B": b, "A": a}[single_channel]
            img_filtered = Image.merge("RGBA" if a else "RGB", (single_channel_data,) * 3 + ((a,) if a else ()))
        else:
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
    canvas.config(width=img_display_resized.size[0], height=img_display_resized.size[1])
    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=img_display)

    # Resize the root window to fit the image width and height
    center_window(img_display_resized.size[0], img_display_resized.size[1])


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
    """Toggles the selected RGBA channel, and if only one channel is active, copies it to the others."""
    channels_selected[channel] = channel_vars[channel].get()

    # Check if exactly one RGB channel is selected
    active_channels = [ch for ch in ["R", "G", "B"] if channels_selected[ch]]
    if len(active_channels) == 1:
        active_channel = active_channels[0]

        # Copy the active channel's data to the other channels
        global original_img
        if original_img and original_img.mode in ("RGBA", "RGB"):
            r, g, b, a = original_img.split() if original_img.mode == "RGBA" else (*original_img.split(), None)
            selected_channel_data = {"R": r, "G": g, "B": b}[active_channel]

            # Duplicate the active channel's data to the other channels
            r, g, b = (selected_channel_data, selected_channel_data, selected_channel_data)
            if a:
                original_img = Image.merge("RGBA", (r, g, b, a))
            else:
                original_img = Image.merge("RGB", (r, g, b))

    # Refresh the display with the updated image
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

def update_status_bar_position():
    status_bar_width = root.winfo_width()
    status_bar_height = status_bar.winfo_reqheight()
    status_bar.place(x=0, y=root.winfo_height() - status_bar_height, width=status_bar_width)

# Create the main Tkinter window
root = tk.Tk()
root.title("DDS Viewer with TexDiag")

root.bind("<Configure>", lambda event: update_status_bar_position())


# Create a frame for the canvas and buttons
frame = tk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True)

# Canvas to display the image
canvas = tk.Canvas(frame, bg="gray")
canvas.pack(fill=tk.BOTH, expand=True)

# Status bar to show image info
status_text = tk.StringVar()
status_text.set("No file loaded")
status_bar = tk.Label(root, textvariable=status_text, bd=1, relief="sunken", anchor="w", bg="lightgray")

# Menu for file operations
menu = tk.Menu(root)
root.config(menu=menu)

# File menu
file_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Open DDS...", command=load_dds)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# Create BooleanVars for each channel
channel_vars = {
    "R": tk.BooleanVar(value=True),
    "G": tk.BooleanVar(value=True),
    "B": tk.BooleanVar(value=True),
    "A": tk.BooleanVar(value=True),
}

# RGBA toggle buttons
channel_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Channels", menu=channel_menu)

# Create checkbuttons for each channel
for channel in ["R", "G", "B", "A"]:
    channel_menu.add_checkbutton(
        label=channel,
        variable=channel_vars[channel],
        onvalue=True,
        offvalue=False,
        command=lambda c=channel: toggle_channel(c),
    )

# Key bindings for left and right arrow keys
root.bind("<Left>", lambda event: navigate_files(-1))
root.bind("<Right>", lambda event: navigate_files(1))

# Run the Tkinter main loop
root.mainloop()
