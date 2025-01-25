import os
import shutil

def copy_missing_files(source_folder, destination_folder):
    """
    Copies files from the source folder to the destination folder only if they
    are missing in the destination (ignoring file extensions).

    Args:
        source_folder: Path to the source folder.
        destination_folder: Path to the destination folder.
    """

    try:
        source_files = {os.path.splitext(f.lower())[0]: f for f in os.listdir(source_folder)}
    except FileNotFoundError:
        print(f"Error: Source folder '{source_folder}' not found.")
        return
    except Exception as e:
        print(f"Error reading source folder: {e}")
        return

    try:
        os.makedirs(destination_folder, exist_ok=True)  # Create destination if it doesn't exist
        destination_files = {os.path.splitext(f.lower())[0]: f for f in os.listdir(destination_folder)}
    except Exception as e:
        print(f"Error reading/creating destination folder: {e}")
        return

    files_copied = 0
    for base_name, source_filename in source_files.items():
        if base_name not in destination_files:
            source_path = os.path.join(source_folder, source_filename)
            destination_path = os.path.join(destination_folder, source_filename)
            try:
                shutil.copy2(source_path, destination_path)  # copy2 preserves metadata
                print(f"Copied: {source_filename}")
                files_copied += 1
            except Exception as e:
                print(f"Error copying {source_filename}: {e}")

    if files_copied == 0:
        print("No files were copied.")
    else:
        print(f"Copied {files_copied} file(s).")



if __name__ == "__main__":
    source_folder = "staging/textures/"  # Replace with the actual path
    destination_folder = "staging/openmwassets/textures"  # Replace with the actual path

    copy_missing_files(source_folder, destination_folder)