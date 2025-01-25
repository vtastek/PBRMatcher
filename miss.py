import os
import shutil

def copy_missing_or_newer_files(source_folder, destination_folder):
    """
    Copies files from the source folder to the destination folder if they are missing
    in the destination or if the source file is newer, even if extensions differ.

    Args:
        source_folder: Path to the source folder.
        destination_folder: Path to the destination folder.
    """

    try:
        # Map files by their base name (ignoring extensions and case) in source
        source_files = {os.path.splitext(f.lower())[0]: f for f in os.listdir(source_folder)}
    except FileNotFoundError:
        print(f"Error: Source folder '{source_folder}' not found.")
        return
    except Exception as e:
        print(f"Error reading source folder: {e}")
        return

    try:
        os.makedirs(destination_folder, exist_ok=True)  # Create destination if it doesn't exist
        # Map files by their base name in destination
        destination_files = {os.path.splitext(f.lower())[0]: f for f in os.listdir(destination_folder)}
    except Exception as e:
        print(f"Error reading/creating destination folder: {e}")
        return

    files_copied = 0
    for base_name, source_filename in source_files.items():
        source_path = os.path.join(source_folder, source_filename)
        destination_file = destination_files.get(base_name)  # Find matching file by base name
        destination_path = os.path.join(destination_folder, destination_file) if destination_file else None

        # Determine if the file needs to be copied
        if not destination_path or not os.path.exists(destination_path):
            # File is missing in the destination folder
            copy_file(source_path, os.path.join(destination_folder, source_filename))
            files_copied += 1
        elif os.path.getmtime(source_path) > os.path.getmtime(destination_path):
            # File exists but is older in the destination folder
            copy_file(source_path, os.path.join(destination_folder, source_filename))
            files_copied += 1

    if files_copied == 0:
        print("No files were copied.")
    else:
        print(f"Copied {files_copied} file(s).")


def copy_file(source_path, destination_path):
    """Copies a single file and handles errors."""
    try:
        shutil.copy2(source_path, destination_path)  # copy2 preserves metadata
        print(f"Copied: {source_path} to {destination_path}")
    except Exception as e:
        print(f"Error copying {source_path}: {e}")


if __name__ == "__main__":
    source_folder = "staging/textures/"  # Replace with the actual path
    destination_folder = "staging/openmwassets/textures"  # Replace with the actual path

    copy_missing_or_newer_files(source_folder, destination_folder)
