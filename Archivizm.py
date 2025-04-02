import os
import time
import psutil
from psutil._common import bytes2human
from rich.console import Console
from rich.table import Table
from rich.live import Live
from alive_progress import alive_bar
import hashlib
import concurrent.futures
import questionary
import threading
import spacy
import pandas as pd
import json

CONFIG_FILE = "config.json"

class DeviceMonitor:
    def __init__(self):
        self.console = Console()
        self.live_thread = None
        self.running = False  # Controls the live update loop
        self.working_directory = self.load_working_directory()
        self.nlp = spacy.load("en_core_web_lg")
        self.start_live()

    # --- Working Directory Methods ---
    def load_working_directory(self):
        """Loads the stored working directory from config.json or returns None if not set."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    return config.get("working_directory")
            except Exception as e:
                self.console.print(f"Error loading config: {e}")
        return None

    def save_working_directory(self, directory):
        """Saves the working directory to config.json."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"working_directory": directory}, f)
        except Exception as e:
            self.console.print(f"Error saving config: {e}")

    def set_working_directory(self):
        """Prompts the user to set a working directory for spreadsheet exports."""
        directory = questionary.text("Enter the path to the working spreadsheet directory:").ask()
        if os.path.isdir(directory):
            self.working_directory = directory
            self.save_working_directory(directory)
            self.console.print(f"Working directory set to: {directory}")
        else:
            self.console.print("Invalid directory. Please enter a valid folder path.")

    def select_spreadsheet(self):
        """Allows the user to select a spreadsheet file from the working directory."""
        if not self.working_directory:
            self.set_working_directory()
            if not self.working_directory:
                return None
        files = [f for f in os.listdir(self.working_directory) if f.endswith(('.csv', '.xls', '.xlsx'))]
        if not files:
            self.console.print("No CSV or Excel files found in the working directory.")
            return None
        file_choice = questionary.select("Choose a spreadsheet file:", choices=files).ask()
        return os.path.join(self.working_directory, file_choice)

    # --- Live Update Methods ---
    def device_list(self):
        """Builds and returns a rich Table of all disk partitions."""
        partitions = psutil.disk_partitions()
        table = Table(title="Device List")
        table.add_column("Device", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Filesystem", style="green")
        table.add_column("Size", style="yellow")
        for partition in partitions:
            if self.get_access(partition.device):
                try:
                    usage = psutil.disk_usage(partition.device)
                    size = bytes2human(usage.total)
                except Exception:
                    size = "N/A"
                table.add_row(
                    partition.device,
                    partition.opts,
                    partition.fstype,
                    size
                )
            else:
                table.add_row(partition.device, "N/A", "N/A", "N/A")
        return table

    def update_live(self):
        """Updates the live table continuously until self.running is set to False."""
        with Live(self.device_list(), console=self.console, refresh_per_second=4) as live:
            while self.running:
                live.update(self.device_list())
                time.sleep(0.4)

    def start_live(self):
        """Starts the live update thread."""
        self.running = True
        self.live_thread = threading.Thread(target=self.update_live, daemon=True)
        self.live_thread.start()

    def stop_live(self):
        """Stops the live update thread and waits for it to finish."""
        self.running = False
        if self.live_thread is not None:
            self.live_thread.join()

    # --- Device Info Helper ---
    def collect_device_info(self, device):
        """
        Collects all device information into a dictionary.
        This includes partition details, disk usage, filesystem statistics,
        I/O counters, content overview, and file type information with file count
        and per-extension breakdown as separate elements.
        """
        device_info = {}
        partitions = psutil.disk_partitions()
        for partition in partitions:
            if partition.device == device:
                # Basic Partition Information
                device_info["Mountpoint"] = partition.mountpoint
                device_info["Filesystem Type"] = partition.fstype
                device_info["Mount Options"] = partition.opts
                device_type = self.guess_device_type(partition)
                device_info["Device Type"] = device_type

                # Set Access Restrictions based on device type
                if device_type == "CD/DVD":
                    device_info["Access Restrictions"] = "DVD Reader"
                elif device_type == "Floppy":
                    device_info["Access Restrictions"] = "Floppy Drive"
                elif device_type == "Zip Disk":
                    device_info["Access Restrictions"] = "Zip Drive"

                # Disk Usage Information
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    device_info["Total Size"] = bytes2human(usage.total)
                    device_info["Used Size"] = bytes2human(usage.used)
                    device_info["Free Size"] = bytes2human(usage.free)
                    device_info["Usage Percent"] = f"{usage.percent}%"
                except Exception:
                    device_info["Disk Usage"] = "Not available"

                # Filesystem Statistics using os.statvfs
                try:
                    statvfs = os.statvfs(partition.mountpoint)
                    fs_stats = {
                        "Block Size": f"{statvfs.f_frsize} bytes",
                        "Total Blocks": statvfs.f_blocks,
                        "Free Blocks": statvfs.f_bfree,
                        "Available Blocks": statvfs.f_bavail,
                        "Inodes Total": statvfs.f_files,
                        "Inodes Free": statvfs.f_ffree,
                        "Inodes Available": statvfs.f_favail
                    }
                    device_info["Filesystem Statistics"] = fs_stats
                except Exception as e:
                    device_info["Filesystem Statistics"] = "Not available"

                # Disk I/O Counters
                io_counters = psutil.disk_io_counters(perdisk=True)
                device_key = partition.device.replace("/dev/", "")
                if device_key in io_counters:
                    counters = io_counters[device_key]
                    device_info["Disk I/O Counters"] = {
                        "Read Count": counters.read_count,
                        "Read Bytes": bytes2human(counters.read_bytes),
                        "Read Time": f"{counters.read_time} ms"
                    }
                else:
                    device_info["Disk I/O Counters"] = "Not available"

                # Top-Level Content Overview
                try:
                    items = os.listdir(partition.mountpoint)
                    num_files_overview = sum(1 for item in items if os.path.isfile(os.path.join(partition.mountpoint, item)))
                    dir_count = sum(1 for item in items if os.path.isdir(os.path.join(partition.mountpoint, item)))
                    device_info["Top-Level Content Overview"] = {
                        "Files": num_files_overview,
                        "Directories": dir_count
                    }
                except Exception as e:
                    device_info["Top-Level Content Overview"] = "Not available"

                # File Types Breakdown: separate Number of Files and Breakdown
                file_types = {}
                max_files = 20000
                count = 0
                try:
                    for root, dirs, files in os.walk(partition.mountpoint):
                        for file in files:
                            count += 1
                            ext = os.path.splitext(file)[1].lower() or "No Extension"
                            file_types[ext] = file_types.get(ext, 0) + 1
                            if count >= max_files:
                                break
                        if count >= max_files:
                            break

                    device_info["Number of Files"] = count
                    device_info["File Types"] = file_types

                except Exception as e:
                    device_info["Number of Files"] = "Not available"
                    device_info["File Types"] = "Not available"

                return device_info
        return None

    # --- Device View and Export ---
    def device_view(self, device):
        """Prints detailed information about the specified device using the collected device info."""
        info = self.collect_device_info(device)
        if not info:
            self.console.print(f"[bold red]Device {device} not found.[/bold red]")
            return

        self.console.rule(f"[bold red]Device Details: {device}")
        self.console.print(f"[bold cyan]Mountpoint:[/bold cyan] {info.get('Mountpoint', 'N/A')}")
        self.console.print(f"[bold magenta]Filesystem Type:[/bold magenta] {info.get('Filesystem Type', 'N/A')}")
        self.console.print(f"[bold magenta]Mount Options:[/bold magenta] {info.get('Mount Options', 'N/A')}")
        self.console.print(f"[bold blue]Device Type:[/bold blue] {info.get('Device Type', 'N/A')}")
        if "Access Restrictions" in info:
            self.console.print(f"[bold red]Access Restrictions:[/bold red] {info.get('Access Restrictions')}")
        # Disk Usage
        if "Total Size" in info:
            self.console.print(f"[bold yellow]Disk Usage:[/bold yellow]")
            self.console.print(f"  Total: {info.get('Total Size')}")
            self.console.print(f"  Used:  {info.get('Used Size')}")
            self.console.print(f"  Free:  {info.get('Free Size')}")
            self.console.print(f"  Usage: {info.get('Usage Percent')}")
        else:
            self.console.print(f"[bold yellow]Disk Usage:[/bold yellow] Not available")
        # Filesystem Statistics
        fs_stats = info.get("Filesystem Statistics")
        if isinstance(fs_stats, dict):
            self.console.print(f"[bold green]Filesystem Statistics:[/bold green]")
            for key, value in fs_stats.items():
                self.console.print(f"  {key}: {value}")
        else:
            self.console.print(f"[bold green]Filesystem Statistics:[/bold green] Not available")
        # Disk I/O Counters
        io_counters = info.get("Disk I/O Counters")
        if isinstance(io_counters, dict):
            self.console.print(f"[bold blue]Disk I/O Counters:[/bold blue]")
            for key, value in io_counters.items():
                self.console.print(f"  {key}: {value}")
        else:
            self.console.print(f"[bold blue]Disk I/O Counters:[/bold blue] Not available")
        # Top-Level Content Overview
        content_overview = info.get("Top-Level Content Overview")
        if isinstance(content_overview, dict):
            self.console.print(f"[bold purple]Top-Level Content Overview:[/bold purple]")
            self.console.print(f"  Files: {content_overview.get('Files')}, Directories: {content_overview.get('Directories')}")
        else:
            self.console.print(f"[bold purple]Top-Level Content Overview:[/bold purple] Not available")

        num_files = info.get("Number of Files")
        file_types = info.get("File Types")
        if num_files is not None and isinstance(file_types, dict):
            self.console.print(f"[bold purple]File Types Breakdown:[/bold purple]")
            self.console.print(f"Files Scanned: {num_files}")
            from rich.table import Table
            ft_table = Table(show_header=True, header_style="bold magenta")
            ft_table.add_column("File Extension", style="cyan")
            ft_table.add_column("Count", style="green")
            for ext, cnt in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
                ft_table.add_row(ext, str(cnt))
            self.console.print(ft_table)
        else:
            self.console.print("[bold purple]File Types Breakdown:[/bold purple] Not available")
        self.console.rule()

    def export(self, device):
        """Exports device information to a selected spreadsheet file."""
        info = self.collect_device_info(device)
        if not info:
            self.console.print(f"[bold red]Device {device} not found.[/bold red]")
            return

        # Select spreadsheet file from working directory
        file_path = self.select_spreadsheet()
        if not file_path:
            return

        file_ext = os.path.splitext(file_path)[1].lower()
        try:
            if file_ext == '.csv':
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            self.console.print(f"Error reading file: {e}")
            return

        column_names = list(df.columns)

        # Prompt the user to choose which device info elements to export
        selected_keys = questionary.checkbox(
            "Select elements to export:",
            choices=list(info.keys())
        ).ask()
        self.stop_live()

        export_data = {}
        matched_scores = {}
        for key in selected_keys:
            value = info[key]
            key_doc = self.nlp(key)
            best_match = None
            best_score = 0
            for col in column_names:
                col_doc = self.nlp(str(col))
                score = key_doc.similarity(col_doc)
                print(f"Key: {repr(key)}, Column: {repr(col)}, Score: {repr(score)}")
                time.sleep(0.1)
                if score > best_score:
                    best_score = score
                    best_match = col
                    matched_scores[col] = score
            if best_match and best_score >= matched_scores[best_match]:
                export_data[best_match] = value

        # Build a new row with all spreadsheet columns (unmatched columns get a value of None)
        new_row = {col: export_data.get(col, None) for col in column_names}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        try:
            if file_ext == '.csv':
                df.to_csv(file_path, index=False)
            else:
                df.to_excel(file_path, index=False)
            self.console.print(f"Export successful to {file_path}")
        except Exception as e:
            self.console.print(f"Error writing to file: {e}")

    def get_access(self, device):
        try:
            if psutil.disk_usage(device).total > 0:
                return True
        except (PermissionError, FileNotFoundError, OSError):
            return False
        return False

    def choose_device(self):
        """Prompts the user to choose one or more devices from the list."""
        partitions = psutil.disk_partitions()
        device_choices = [partition.device for partition in partitions]
        selected = questionary.checkbox("Select device(s) to view:", choices=device_choices).ask()
        return selected

    def guess_device_type(self, partition):
        """
        Guesses the device type based on its device name, filesystem type, and mount options.
        Returns a string such as "CD/DVD", "Floppy", "Zip Disk", or "Regular Storage".
        """
        device_lower = partition.device.lower()
        fstype_lower = partition.fstype.lower()
        opts_lower = partition.opts.lower()

        if "cdrom" in opts_lower or "iso9660" in fstype_lower or "cdfs" in fstype_lower or device_lower.startswith("/dev/sr"):
            return "CD/DVD"
        elif device_lower.startswith("/dev/fd"):
            return "Floppy"
        elif "zip" in device_lower:
            return "Zip Disk"
        else:
            return "Regular Storage"

    class DupeCheck:
        def __init__(self, directory):
            self.directory = directory

        def md5(self, file_path):
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

        def find_duplicates(self):
            hashes = {}
            duplicates = {}

            # Walk through the directory to get all files
            file_paths = []

            with alive_bar(title="Scanning Files") as bar:
                for root, _, files in os.walk(self.directory):
                    for file in files:
                        file_paths.append(os.path.join(root, file))
                        bar()  # Update the progress bar for each file found

            print(f"Total files to process: {len(file_paths)}")  # Debugging message to check if files are found

            # Using ThreadPoolExecutor to process files in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Map the MD5 calculation to each file path in parallel
                future_to_file = {executor.submit(self.md5, file_path): file_path for file_path in file_paths}

                # Initialize the progress bar with the number of files to process
                with alive_bar(len(future_to_file), title="Processing Files") as bar:
                    # Ensure the progress bar is updated for each completed task
                    for future in concurrent.futures.as_completed(future_to_file):
                        #print("Task completed")  # Debugging message to show task completion
                        file_hash, file_path = future.result()


                        # Update the progress bar after processing each file
                        bar()

                        # If a valid hash is returned, check for duplicates
                        if file_hash:
                            if file_hash in hashes:
                                duplicates[file_hash] = [file_path] + duplicates.get(file_hash, [])
                            else:
                                hashes[file_hash] = file_path
            for file_hash in duplicates:
                duplicates[file_hash].append(hashes[file_hash])

            return duplicates

    def dupe_finder(self):
        # Get all disk partitions
        partitions = psutil.disk_partitions()

        # List available partitions for the user to select
        device_choices = [partition.device for partition in partitions]

        # Prompt user to select one or more devices
        device_paths = questionary.checkbox("Select device(s) to view:", choices=device_choices).ask()

        def chooseDir(directory):
            return questionary.select("Select directory to search", choices=os.listdir(directory)).ask()

        # Ensure the selected devices exist and walk through the directories
        for device_path in device_paths:
            # Find the mount point for each device
            for partition in partitions:
                print(partition.mountpoint)
                if partition.device == device_path:
                    directory = partition.mountpoint
                    if os.path.exists(directory):
                        try:
                            searching = True
                            while searching:
                                print(f"Directory: {directory}")
                                answer = input("Go to subdirectory (yes/no): ").lower()
                                if answer in ["yes", "no"]:
                                    if answer == "yes":
                                        directory = directory + "/" + chooseDir(directory)
                                    else:
                                        searching = False
                                else:
                                    print("Please answer 'yes' or 'no'.")
                            print(f"Exploring {directory}...")
                            dupeFinder = self.DupeCheck(directory)
                            duplicates = dupeFinder.find_duplicates()
                        except PermissionError:
                            print("PermissionError")
                    else:
                        print(f"{mount_point} does not exist or is not mounted.")
        for hash in duplicates:
            print(duplicates[hash])

    def run(self):
        """
        Main loop:
          - Starts the live table for a few seconds,
          - Stops it to let the user interact with a menu,
          - If a device is chosen, displays its details or exports its data,
          - Then restarts the live view.
        """
        while True:
            action = questionary.select(
                "Choose an action:",
                choices=["View Device", "Export to Spreadsheet", "Set Working Directory", "Find Duplicates", "Exit"]
            ).ask()
            self.stop_live()

            if action == "View Device":
                selected_devices = self.choose_device()
                if selected_devices:
                    for device in selected_devices:
                        self.device_view(device)
                    questionary.text("Press Enter to continue...").ask()
            elif action == "Export to Spreadsheet":
                selected_devices = self.choose_device()
                if selected_devices:
                    for device in selected_devices:
                        self.export(device)
            elif action == "Set Working Directory":
                self.set_working_directory()
            elif action == "Find Duplicates":
                self.dupe_finder()
            elif action == "Exit":
                break

if __name__ == "__main__":
    print("""
  ▒▓██████▓▒  ▒▓███████▓▒   ▒▓██████▓▒  ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒ ▒▓████████▓▒ ▒▓██████████████▓▒
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▓█▓▒  ▒▓█▓▒      ▒▓██▓▒  ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒
 ▒▓████████▓▒ ▒▓███████▓▒  ▒▓█▓▒        ▒▓████████▓▒ ▒▓█▓▒  ▒▓█▓▒ ▓█▓▒  ▒▓█▓▒    ▒▓██▓▒    ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒   ▒▓█▓▓█▓▒   ▒▓█▓▒  ▒▓██▓▒      ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒   ▒▓█▓▓█▓▒   ▒▓█▓▒ ▒▓█▓▒        ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒
 ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒  ▒▓█▓▒  ▒▓██████▓▒  ▒▓█▓▒  ▒▓█▓▒ ▒▓█▓▒    ▒▓██▓▒    ▒▓█▓▒ ▒▓████████▓▒ ▒▓█▓▒  ▒▓█▓▒  ▒▓█▓▒
    """)
    monitor = DeviceMonitor()
    monitor.run()


