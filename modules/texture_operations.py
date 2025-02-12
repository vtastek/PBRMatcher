import os
import cv2
import numpy as np
from PIL import Image, ImageTk

from modules.constants import OVERLAY_FOLDER

class TextureOperations:
    def __init__(self, db, all_assets):
        self.db = db
        self.all_assets = all_assets
        self.current_zoom_image = None
        self.current_overlay_image = None

    def load_image(self, image_path):
        """Load and process an image if it exists."""
        if os.path.isfile(image_path):
            image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                print(f"Failed to load image: {image_path}")
                return None

            # Normalize bit depth if needed (for overlays, e.g., 16-bit images)
            if image.dtype == np.uint16:  # 16-bit or 48-bit image
                image = (image / 256).astype(np.uint8)

            # Convert to RGBA
            if image.ndim == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGBA)
            elif image.shape[2] == 3:  # BGR
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)
            elif image.shape[2] == 4:  # BGRA
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)

            return image
        return None
    
    def prepare_display_image(self, image):
        """Resize the image for display while preserving aspect ratio."""
        base_height = 480
        aspect_ratio = image.shape[1] / image.shape[0]
        new_width = int(base_height * aspect_ratio)
        display_image = cv2.resize(image, (new_width, base_height), interpolation=cv2.INTER_LINEAR)

        # Convert to PIL for Tkinter compatibility
        return Image.fromarray(display_image)

    def display_texture(self, texture_path, image_label):
        """Update the texture based on the user input."""
        texture_name = os.path.basename(texture_path)

        # Load the zoom image (used as the base image)
        zoom_image = self.load_image(texture_path)
        if zoom_image is None:
            print(f"Failed to load zoom image: {texture_path}")
            return

        # Set default image
        image = zoom_image
        self.current_zoom_image = zoom_image

        # Prepare the resized version (for display)
        display_image = self.prepare_display_image(image)

        # Display the image
        photo = ImageTk.PhotoImage(display_image)
        image_label.config(image=photo)
        image_label.image = photo


    def preprocess_channels(self, blue_channel, green_channel, red_channel, alpha_channel):
            """
            Prepares the channels for merging by ensuring they have the same size and data type.

            Args:
                blue_channel (numpy.ndarray): Blue channel.
                green_channel (numpy.ndarray): Green channel.
                red_channel (numpy.ndarray): Red channel.
                alpha_channel (numpy.ndarray): Alpha channel.

            Returns:
                tuple: Resized and aligned channels ready for merging.
            """
            # Determine the reference size (use the size of the first channel)
            height, width = blue_channel.shape[:2]

            # Resize all channels to match the reference size
            green_channel = cv2.resize(green_channel, (width, height))
            red_channel = cv2.resize(red_channel, (width, height))
            alpha_channel = cv2.resize(alpha_channel, (width, height))

            # Convert all channels to the same data type (e.g., uint8)
            channels = [blue_channel, green_channel, red_channel, alpha_channel]
            target_dtype = blue_channel.dtype  # Use the dtype of the first channel as reference
            channels = [ch.astype(target_dtype) for ch in channels]

            return tuple(channels)

    def convert_to_8bit_single_channel(self, texture):
        """
        Converts a texture to 8-bit single-channel format.
        
        Args:
            texture (numpy.ndarray): Input texture, can be grayscale or RGB, 
                                    with bit depth 8, 16, 32, or 48.
        Returns:
            numpy.ndarray: 8-bit single-channel texture.
        """

        # Determine the bit depth of the input texture
        if texture.dtype == np.uint8:
            # Already 8-bit, no further conversion needed
            return texture
        elif texture.dtype == np.uint16:
            # Convert 16-bit to 8-bit
            texture = (texture / 256).astype(np.uint8)
        elif texture.dtype in [np.float32, np.float64]:
            # Normalize float textures to 0-255 and convert to 8-bit
            texture = (255 * (texture / np.max(texture))).astype(np.uint8)
        elif texture.dtype == np.int32 or texture.dtype == np.int64:
            # Clip values to 0-255 and convert to 8-bit
            texture = np.clip(texture, 0, 255).astype(np.uint8)
        else:
            raise ValueError(f"Unsupported texture dtype: {texture.dtype}")
        
        return texture

    def combine_textures(self, texture_path, thumbnail_name, texture_name_label):
        """
        Combines texture components into various output textures.
        """
        staging_dir = "staging"
        os.makedirs(staging_dir, exist_ok=True)

        # Normalize texture_name_label and thumbnail_name
        texture_name_label = f"textures\\{texture_name_label}".lower().replace("_result", "")
        down_thumbnail_name = thumbnail_name.lower().replace(" ", "_")

        # Helper function to load an image
        def load_image(file_path):
            if file_path and os.path.exists(file_path):
                return cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            print(f"File not found: {file_path}")
            return None

        # Helper function to find a file
        def find_file(substrings, down_thumbnail_name):
            if isinstance(substrings, str):
                substrings = [substrings]
            for filename in os.listdir(staging_dir):
                filename_casefold = filename.casefold()
                if filename_casefold.startswith(down_thumbnail_name):
                    for substring in substrings:
                        if substring in filename_casefold:
                            return os.path.join(staging_dir, filename)
            return None

        # Load texture files
        arm_file = find_file("_arm_", down_thumbnail_name)
        nor_file = find_file("_nor_", down_thumbnail_name)
        disp_file = find_file(["_disp_", "_height_"], down_thumbnail_name)
        diff_file = find_file(["_diffuse_", "_diff_", "_color_"], down_thumbnail_name)

        arm_texture = load_image(arm_file)
        nor_texture = load_image(nor_file)
        disp_texture = load_image(disp_file)
        diff_texture = load_image(diff_file)

        # Create textures
        self.create_param_texture(texture_name_label, staging_dir, arm_texture)
        self.create_nh_texture(texture_name_label, staging_dir, nor_texture, disp_texture)
        self.process_and_save_diff_textures(texture_name_label, down_thumbnail_name, staging_dir, diff_texture, arm_texture)

    def create_param_texture(self, texture_name_label, staging_dir, arm_texture):
        """Creates and saves the _param texture."""
        if arm_texture is None:
            return
        param_r = self.convert_to_8bit_single_channel(arm_texture[:, :, 0])  # Blue
        param_g = self.convert_to_8bit_single_channel(arm_texture[:, :, 1])  # Green
        param_b = np.full_like(param_g, 128)  # Mid-gray (128)
        param_a = self.convert_to_8bit_single_channel(arm_texture[:, :, 2])  # Red

        # Combine into a single texture
        param_texture = cv2.merge([param_b, param_g, param_r, param_a])
        param_output_path = os.path.join(staging_dir, f"{texture_name_label}_param.png")
        cv2.imwrite(param_output_path, param_texture)
        print(f"Saved param texture: {param_output_path}")

    def create_nh_texture(self, texture_name_label, staging_dir, nor_texture, disp_texture):
        """Creates and saves the _nh texture."""
        if nor_texture is None or disp_texture is None:
            return
        nh_red = self.convert_to_8bit_single_channel(nor_texture[:, :, 2])  # Red
        nh_green = self.convert_to_8bit_single_channel(nor_texture[:, :, 1])  # Green
        nh_blue = self.convert_to_8bit_single_channel(nor_texture[:, :, 0])  # Blue
        nh_alpha = self.convert_to_8bit_single_channel(disp_texture[:, :, 2] if len(disp_texture.shape) == 3 else disp_texture)

        # Combine into a single texture
        nh_texture = cv2.merge([nh_blue, nh_green, nh_red, nh_alpha])
        nh_output_path = os.path.join(staging_dir, f"{texture_name_label}_nh.png")
        cv2.imwrite(nh_output_path, nh_texture)
        print(f"Saved nh texture: {nh_output_path}")

    def is_in_txt(self, filename, filepath="terrain_dump.txt"):
        filename = filename.lower()
        def clean_line(line):
            cleaned = os.path.splitext(line.strip().lower())[0]
            #print(f"Checking line: '{line.strip()}' -> Cleaned: '{cleaned}'")  # Debugging output
            return cleaned
        
        with open(filepath, "r") as file:
            for line in file:
                if clean_line(line) == filename:
                    #print(f"Match found: {filename}")  # Debugging output
                    return True
        #print(f"No match found for: {filename}")  # Debugging output
        return False


    def process_and_save_diff_textures(self, texture_name_label, down_thumbnail_name, staging_dir, diff_texture, arm_texture):
        """
        Processes and saves textures: diffuse (converted to 8-bit), diffparam, overlay (resized), and zoom (original size).
        
        Args:
            texture_name_label (str): Base name for the textures.
            staging_dir (str): Directory to save the textures.
            diff_texture (np.ndarray): The diffuse texture.
            arm_texture (np.ndarray): The ARM texture.
        """
        if diff_texture is None:
            return


        # Convert each channel of the diffuse texture to 8-bit
        d_red = self.convert_to_8bit_single_channel(diff_texture[:, :, 0])  # Red
        d_green = self.convert_to_8bit_single_channel(diff_texture[:, :, 1])  # Green
        d_blue = self.convert_to_8bit_single_channel(diff_texture[:, :, 2])  # Blue
        #print("Converted diffuse texture channels to 8-bit.")

        # Combine the channels into an 8-bit diffuse texture
        diff_texture_8bit = cv2.merge([d_red, d_green, d_blue])

        # Save the diffuse texture
        diff_output_path = os.path.join(staging_dir, f"{texture_name_label}.png")
        cv2.imwrite(diff_output_path, diff_texture_8bit)
        print(f"Saved diffuse texture: {diff_output_path}")

        # Path to the results file (assumes it's in the current working directory)
        results_file_path = f"{texture_name_label}_result.png"

        # Retrieve target size from the results file
        if not os.path.isfile(results_file_path):
            print(f"Error: Results file not found: {results_file_path}")
            return

        # Load the results image to get its size
        results_image = cv2.imread(results_file_path, cv2.IMREAD_UNCHANGED)
        if results_image is None:
            print(f"Error: Failed to load results image: {results_file_path}")
            return

        target_size = (results_image.shape[1], results_image.shape[0])  # (width, height)
        #print(f"Retrieved target size from results file: {target_size}")

        # Check if existing overlay exists and is larger
        overlay_output_path = os.path.join(OVERLAY_FOLDER, f"{down_thumbnail_name}_overlay.png")
        if os.path.isfile(overlay_output_path):
            existing_overlay = cv2.imread(overlay_output_path, cv2.IMREAD_UNCHANGED)
            if existing_overlay is not None and (existing_overlay.shape[0] > target_size[1] or existing_overlay.shape[1] > target_size[0]):
                print(f"Skipping overlay creation: existing overlay is larger than target size")
            else:
                # Save the overlay texture (resized)
                overlay_texture = cv2.resize(diff_texture_8bit, target_size, interpolation=cv2.INTER_LINEAR)
                print("overlay_output_path", overlay_output_path)
                cv2.imwrite(overlay_output_path, overlay_texture)
                print(f"Saved overlay texture: {overlay_output_path}")
        else:
            # Save the overlay texture (resized)
            overlay_texture = cv2.resize(diff_texture_8bit, target_size, interpolation=cv2.INTER_LINEAR)
            print("overlay_output_path", overlay_output_path)
            cv2.imwrite(overlay_output_path, overlay_texture)
            print(f"Saved overlay texture: {overlay_output_path}")


        filename = os.path.basename(texture_name_label).replace(".dds", "")
        filename = filename.replace(".tga", "").lower()



        # If arm_texture is provided, create and save the diffparam texture
        if arm_texture is not None and self.is_in_txt(filename):
            # Convert the green channel of ARM texture to 8-bit for alpha
            d_alpha = self.convert_to_8bit_single_channel(arm_texture[:, :, 1])  # Green (from ARM)

            # Combine diffuse channels with alpha into diffparam texture
            diffparam_texture = cv2.merge([d_red, d_green, d_blue, d_alpha])
            diffparam_output_path = os.path.join(staging_dir, f"{texture_name_label}_diffparam.png")
            
            #print("DIFF: ", texture_name_label)
            cv2.imwrite(diffparam_output_path, diffparam_texture)
            print(f"Saved diffparam texture: {diffparam_output_path}")
