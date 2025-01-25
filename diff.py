import os
import re

def find_missing_alternatives(folder_path, text_file_path):
    """
    Finds texture names in a text file that have a corresponding base texture
    in a folder, but are missing the "_diffparam" alternative.
    Completely ignores file extensions.

    Args:
        folder_path: Path to the folder containing texture files.
        text_file_path: Path to the text file containing texture names.

    Returns:
        A list of base texture names that are missing their "_diffparam" alternative,
        or None if there's an error reading files.
    """



    try:
        with open(text_file_path, 'r') as f:
            texture_names_from_text = [line.strip().lower() for line in f]  # Lowercase on read
    except FileNotFoundError:
        print(f"Error: Text file '{text_file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error reading text file: {e}")
        return None

    try:
        texture_files_in_folder = [f.lower() for f in os.listdir(folder_path)] # Lowercase folder files immediately
    except FileNotFoundError:
        print(f"Error: Folder '{folder_path}' not found.")
        return None
    except Exception as e:
        print(f"Error reading folder: {e}")
        return None

    missing_alternatives = []

    for texture_name_from_text in texture_names_from_text:
        base_name = os.path.splitext(texture_name_from_text)[0] # remove extension from txt name
        base_found = False
        for file_name in texture_files_in_folder:
            if os.path.splitext(file_name)[0] == base_name: #compare without extension
                base_found = True
                diffparam_name = base_name + "_diffparam"
                diffparam_found = False
                for file_name2 in texture_files_in_folder: #second loop to find the diffparam
                    if os.path.splitext(file_name2)[0] == diffparam_name:
                        diffparam_found = True
                        break
                if not diffparam_found:
                    missing_alternatives.append(base_name)
                break # stop the loop after finding the base
        
    return missing_alternatives

if __name__ == "__main__":
    text_file_path = "terrain_dump.txt"
    folder_path = "staging/textures/"
    
    missing = find_missing_alternatives(folder_path, text_file_path)

    if missing is not None:
        if missing:
            print("Missing _diffparam alternatives:")
            for item in missing:
                print(item)
        else:
            print("No missing _diffparam alternatives found.")