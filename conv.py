import os
import subprocess
import multiprocessing
from PIL import Image

def convert_png_to_dxt(png_path):
    """Converts a PNG image to DXT1 or DXT5 format with mipmaps using texconv.
       Format is auto-detected based on alpha channel. Saves the DDS in the same folder.

    Args:
        png_path: Path to the input PNG file.
    """

    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the full path to texconv.exe
    texconv_path = os.path.join(script_dir, "texconv.exe")

    if not os.path.exists(texconv_path):
        print("Error: texconv.exe not found in the same folder as the script.")
        return

    try:
        img = Image.open(png_path)
        dxt_format = "dxt5" if img.mode == "RGBA" else "dxt1"
        img.close()

        # Output to the same directory as the input PNG
        output_dir = os.path.dirname(png_path)
        output_path = os.path.splitext(png_path)[0] + ".dds"
        args = [texconv_path, "-m", "0", "-y", "-f", dxt_format.upper(), "-o", output_dir, png_path]
        subprocess.run(args, check=True)
        print(f"Converted: {png_path} to {dxt_format.upper()}")

    except subprocess.CalledProcessError as e:
        print(f"Error converting {png_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def process_folder(input_folder):
    """Processes all PNG files in a folder using multiprocessing. Saves DDS in the same folder.

    Args:
        input_folder: Path to the input folder containing PNG files.
    """

    png_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith(".png")]

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(convert_png_to_dxt, png_files)

if __name__ == "__main__":
    input_folder = "staging/openmwassets/textures/"  # Replace with your input folder

    process_folder(input_folder)