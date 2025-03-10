import os
import shutil
import re

def copy_and_modify_folder(source_folder, target_folder_prefix, num_folders):
    # Ensure the source folder exists
    if not os.path.exists(source_folder):
        print(f"Source folder {source_folder} does not exist.")
        return

    # Create the target folders and copy the contents
    for i in range(1, num_folders + 1):
        target_folder = f"{target_folder_prefix}{i}"

        # Skip if the target folder already exists
        if os.path.exists(target_folder):
            print(f"Target folder {target_folder} already exists. Skipping.")
            continue

        os.makedirs(target_folder, exist_ok=True)

        # Copy the contents of the source folder to the target folder
        for root, dirs, files in os.walk(source_folder):
            relative_path = os.path.relpath(root, source_folder)
            target_root = os.path.join(target_folder, relative_path)
            os.makedirs(target_root, exist_ok=True)

            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(target_root, file)
                shutil.copy2(src_file, dst_file)

                # Modify the content of the file
                with open(dst_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Replace the string with the new value
                modified_content = re.sub(r'"additional_arguments": "--threads 1"', f'"additional_arguments": "--threads {i}"', content)

                # Write the modified content back to the file
                with open(dst_file, 'w', encoding='utf-8') as f:
                    f.write(modified_content)

# Example usage
source_folder = 'm1'
target_folder_prefix = 'm'
num_folders = 20

copy_and_modify_folder(source_folder, target_folder_prefix, num_folders)

