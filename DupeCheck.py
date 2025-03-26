import os
import psutil
import questionary
import hashlib
import concurrent.futures
from alive_progress import alive_bar
import time

# Get all disk partitions
partitions = psutil.disk_partitions()
print(partitions)

# List available partitions for the user to select
device_choices = [partition.device for partition in partitions]

# Prompt user to select one or more devices
device_paths = questionary.checkbox("Select device(s) to view:", choices=device_choices).ask()

def md5(file_path):
    """Calculate the MD5 hash of a file."""
    try:
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5()
            while chunk := f.read(8192):  # Read the file in chunks of 8k
                file_hash.update(chunk)
        return file_hash.hexdigest(), file_path
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None, file_path

def find_duplicates(directory):
    hashes = {}
    duplicates = {}

    # Walk through the directory to get all files
    file_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_paths.append(os.path.join(root, file))

    print(f"Total files to process: {len(file_paths)}")  # Debugging message to check if files are found

    # Using ThreadPoolExecutor to process files in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Map the MD5 calculation to each file path in parallel
        future_to_file = {executor.submit(md5, file_path): file_path for file_path in file_paths}

        # Initialize the progress bar with the number of files to process
        with alive_bar(len(future_to_file), title="Processing Files") as bar:
            # Ensure the progress bar is updated for each completed task
            for future in concurrent.futures.as_completed(future_to_file):
                print("Task completed")  # Debugging message to show task completion
                file_hash, file_path = future.result()


                # Update the progress bar after processing each file
                bar()

                # If a valid hash is returned, check for duplicates
                if file_hash:
                    if file_hash in hashes:
                        duplicates[file_hash] = [hashes[file_hash]] + duplicates.get(file_hash, [])
                    else:
                        hashes[file_hash] = file_path

    return duplicates

# Ensure the selected devices exist and walk through the directories
for device_path in device_paths:
    # Find the mount point for each device
    for partition in partitions:
        print(partition.mountpoint)
        if partition.device == device_path:
            mount_point = partition.mountpoint
            if os.path.exists(mount_point):
                print(f"Exploring {mount_point}...")
                file_hashes = find_duplicates(mount_point)
            else:
                print(f"{mount_point} does not exist or is not mounted.")
