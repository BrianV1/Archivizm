import os
import time
import psutil
from psutil._common import bytes2human
from rich.console import Console
from rich.table import Table
from rich.live import Live
import questionary
import threading
import spacy
import numpy
#python -m spacy download en_core_web_lg


class DeviceMonitor:
    def __init__(self):
        self.console = Console()
        self.live_thread = None
        self.running = False  # Controls the live update loop

    def get_access(self, device):
        try:
            if psutil.disk_usage(device).total > 0:
                return True
        except (PermissionError, FileNotFoundError, OSError):
            return False
        return False

    def device_list(self):
        """Builds and returns a rich Table of all disk partitions."""
        partitions = psutil.disk_partitions()
        table = Table(title="Device List")
        # Define columns with some color styling
        table.add_column("Device", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Filesystem", style="green")
        table.add_column("Size", style="yellow")
        # Add a row per partition
        for partition in partitions:
            if self.get_access(partition.device):
                usage = psutil.disk_usage(partition.device)
                table.add_row(
                    partition.device,
                    partition.opts,
                    partition.fstype,
                    bytes2human(usage.total)
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


    def device_view(self, device):
        """Prints detailed information about the specified device in an organized manner,
        including an expanded content overview that lists file types found on the device."""
        partitions = psutil.disk_partitions()
        found = False

        for partition in partitions:
            if partition.device == device:
                found = True
                # Try to obtain disk usage from the mountpoint.
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                except Exception:
                    usage = None

                self.console.rule(f"[bold red]Device Details: {partition.device}")

                # Basic Partition Information
                self.console.print(f"[bold cyan]Mountpoint:[/bold cyan] {partition.mountpoint}")
                self.console.print(f"[bold magenta]Filesystem Type:[/bold magenta] {partition.fstype}")
                self.console.print(f"[bold magenta]Mount Options:[/bold magenta] {partition.opts}")

                # Device Type Guess
                device_type = self.guess_device_type(partition)
                self.console.print(f"[bold blue]Device Type:[/bold blue] {device_type}")

                # Disk Usage Information
                if usage:
                    self.console.print(f"[bold yellow]Disk Usage:[/bold yellow]")
                    self.console.print(f"  Total: {bytes2human(usage.total)}")
                    self.console.print(f"  Used:  {bytes2human(usage.used)} ({usage.percent}%)")
                    self.console.print(f"  Free:  {bytes2human(usage.free)}")
                else:
                    self.console.print(f"[bold yellow]Disk Usage:[/bold yellow] Not available")

                # Filesystem Statistics using os.statvfs
                try:
                    statvfs = os.statvfs(partition.mountpoint)
                    self.console.print(f"[bold green]Filesystem Statistics:[/bold green]")
                    self.console.print(f"  Block Size: {statvfs.f_frsize} bytes")
                    self.console.print(f"  Total Blocks: {statvfs.f_blocks}")
                    self.console.print(f"  Free Blocks: {statvfs.f_bfree}")
                    self.console.print(f"  Available Blocks: {statvfs.f_bavail}")
                    self.console.print(
                        f"  Inodes - Total: {statvfs.f_files}, Free: {statvfs.f_ffree}, Available: {statvfs.f_favail}"
                    )
                except Exception as e:
                    self.console.print(f"[bold green]Filesystem Statistics:[/bold green] Not available")

                # Disk I/O Counters (if available)
                io_counters = psutil.disk_io_counters(perdisk=True)
                device_key = partition.device.replace("/dev/", "")
                if device_key in io_counters:
                    counters = io_counters[device_key]
                    self.console.print(f"[bold blue]Disk I/O Counters:[/bold blue]")
                    self.console.print(f"  Read Count:  {counters.read_count}")
                    #self.console.print(f"  Write Count: {counters.write_count}")
                    self.console.print(f"  Read Bytes:  {bytes2human(counters.read_bytes)}")
                    #self.console.print(f"  Write Bytes: {bytes2human(counters.write_bytes)}")
                    self.console.print(f"  Read Time:   {counters.read_time} ms")
                    #self.console.print(f"  Write Time:  {counters.write_time} ms")
                else:
                    self.console.print(f"[bold blue]Disk I/O Counters:[/bold blue] Not available for this device.")

                # Expanded Content Overview
                try:
                    # Top-level content overview (only list immediate children)
                    items = os.listdir(partition.mountpoint)
                    file_count = sum(
                        1 for item in items if os.path.isfile(os.path.join(partition.mountpoint, item))
                    )
                    dir_count = sum(
                        1 for item in items if os.path.isdir(os.path.join(partition.mountpoint, item))
                    )
                    self.console.print(f"[bold purple]Top-Level Content Overview:[/bold purple]")
                    self.console.print(f"  Files: {file_count} | Directories: {dir_count}")

                    # File Types Breakdown: Walk the file tree (up to a sample limit)
                    file_types = {}
                    max_files = 20000  # limit the scan for performance reasons
                    count = 0
                    for root, dirs, files in os.walk(partition.mountpoint):
                        for file in files:
                            count += 1
                            ext = os.path.splitext(file)[1].lower() or "No Extension"
                            file_types[ext] = file_types.get(ext, 0) + 1
                            if count >= max_files:
                                break
                        if count >= max_files:
                            break

                    if file_types:
                        self.console.print(f"[bold purple]File Types Breakdown (out of {count} files):[/bold purple]")
                        # Create a table to display the file type counts.
                        from rich.table import Table
                        ft_table = Table(show_header=True, header_style="bold magenta")
                        ft_table.add_column("File Extension", style="cyan")
                        ft_table.add_column("Count", style="green")
                        for ext, cnt in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
                            ft_table.add_row(ext, str(cnt))
                        self.console.print(ft_table)
                    else:
                        self.console.print(f"[bold purple]File Types Breakdown:[/bold purple] Not available")
                except Exception as e:
                    self.console.print(f"[bold purple]Content Overview:[/bold purple] Not available ({e})")

                self.console.rule()
                break

        if not found:
            self.console.print(f"[bold red]Device {device} not found.[/bold red]")

    def export(self, device):
        # Todo, use spaCY to find similarity between device specs and Spreadsheet column headers
        # Create a dictionary of device info names matched with specs
        #
        # Use this for reference:
        # nlp=spacy.load("en_core_web_lg")
        # sentence1 = "I love pizza"
        # sentence2 = "I adore hamburgers"
        # doc1 = nlp(sentence1)
        # doc2 = nlp(sentence2)
        # similarity_score =doc1.similarity(doc2)

        column_names = #import this from spreadhseet file

        device_info = {}
        partitions = psutil.disk_partitions()
        for partition in partitions:
            if partition.device == device:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                except Exception:
                    usage = None

                device_info["Mountpoint"] = partition.mountpoint
                device_info["Filesystem Type"] = partition.fstype
                device_info["Mount Options"] = partition.opts
                device_info["Device Type"] = self.guess_device_type(partition)

                if usage:
                    device_info["Total Size"] = bytes2human(usage.total)
                    device_info["Used Space"] = bytes2human(usage.used)
                    device_info["Free Space"] = bytes2human(usage.free)
                # You can add more device-specific information here if needed.
                break




    def run(self):
        """
        Main loop:
          - Starts the live table for a few seconds,
          - Stops it to let the user interact with a menu,
          - If a device is chosen, displays its details,
          - Then restarts the live view.
        """
        while True:
            # Start the live table display in a background thread.
            self.start_live()
            # Present the user with a menu.
            action = questionary.select(
                "Choose an action:",
                choices=["View Device", "Export to Spreadsheet", "Exit"]
            ).ask()
            #Stop live once user input
            self.stop_live()

            if action == "View Device":
                selected_devices = self.choose_device()
                if selected_devices:
                    for device in selected_devices:
                        self.device_view(device)
                    # Wait for user acknowledgement before resuming live display.
                    questionary.text("Press Enter to continue...").ask()
            elif action == "Export to Spreadsheet":
                selected_devices = self.choose_device()
                if selected_devices:
                    for device in selected_devices:
                        self.export(device)
            elif action == "Exit":
                break

if __name__ == "__main__":
    # Print the fancy header
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
