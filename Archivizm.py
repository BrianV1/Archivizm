import os
import sys
import json
import psutil
from psutil._common import bytes2human
import hashlib
import concurrent.futures
import pandas as pd
import spacy
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog,
    QComboBox, QProgressBar, QLineEdit, QDialog, QCheckBox, QDialogButtonBox,
    QHeaderView, QMessageBox, QSizePolicy
)
import subprocess
import tempfile
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

# Set default font size for the application
DEFAULT_FONT_SIZE = 10

CONFIG_FILE = "config.json"

class DeviceInfoCollector:
    """
    Utility class for collecting detailed information about a device or directory.

    This class provides static methods to gather information about storage devices, including
    filesystem details, disk usage, I/O counters, and file format identification using Siegfried
    or lightweight scanning.
    """

    @staticmethod
    def collect_device_info(device, use_siegfried=True, directory=None):
        """
        Collects comprehensive information about a specified device or directory.

        Gathers details such as mountpoint, filesystem type, disk usage, I/O counters, and file
        format information. Uses Siegfried for file format identification if enabled, otherwise
        performs lightweight extension-based scanning.

        @param device: The device path (e.g., '/dev/sda1') to analyze.
        @param use_siegfried: Boolean indicating whether to use Siegfried for file format identification.
        @param directory: Optional directory path to scan instead of the device's mountpoint.
        @return: A dictionary containing device information or None if the device is not found.
        """
        device_info = {}
        partitions = psutil.disk_partitions()
        for partition in partitions:
            if partition.device == device:
                device_info["Mountpoint"] = partition.mountpoint
                device_info["Filesystem Type"] = partition.fstype
                device_info["Mount Options"] = partition.opts
                device_type = DeviceInfoCollector.guess_device_type(partition)
                device_info["Device Type"] = device_type

                if device_type == "CD/DVD":
                    device_info["Access Restrictions"] = "DVD Reader"
                elif device_type == "Floppy":
                    device_info["Access Restrictions"] = "Floppy Drive"
                elif device_type == "Zip Disk":
                    device_info["Access Restrictions"] = "Zip Disk"

                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    device_info["Total Size"] = bytes2human(usage.total)
                    device_info["Used Size"] = bytes2human(usage.used)
                    device_info["Free Size"] = bytes2human(usage.free)
                    device_info["Usage Percent"] = f"{usage.percent}%"
                except Exception:
                    pass

                try:
                    statvfs = os.statvfs(partition.mountpoint)
                    device_info["Filesystem Statistics"] = {
                        "Block Size": f"{statvfs.f_frsize} bytes",
                        "Total Blocks": statvfs.f_blocks,
                        "Free Blocks": statvfs.f_bfree,
                        "Available Blocks": statvfs.f_bavail,
                        "Inodes Total": statvfs.f_files,
                        "Inodes Free": statvfs.f_ffree,
                        "Inodes Available": statvfs.f_favail
                    }
                except Exception:
                    pass

                io_counters = psutil.disk_io_counters(perdisk=True)
                device_key = partition.device.replace("/dev/", "")
                if device_key in io_counters:
                    counters = io_counters[device_key]
                    device_info["Disk I/O Counters"] = {
                        "Read Count": counters.read_count,
                        "Read Bytes": bytes2human(counters.read_bytes),
                        "Read Time": f"{counters.read_time} ms"
                    }

                try:
                    scan_path = directory if directory else partition.mountpoint
                    items = os.listdir(scan_path)
                    num_files = sum(1 for item in items if os.path.isfile(os.path.join(scan_path, item)))
                    dir_count = sum(1 for item in items if os.path.isdir(os.path.join(scan_path, item)))
                    device_info["Top-Level Content Overview"] = {"Files": num_files, "Directories": dir_count}
                except Exception:
                    pass

                # File format identification
                scan_path = directory if directory else partition.mountpoint
                if scan_path and os.path.exists(scan_path):
                    if use_siegfried:
                        # Determine Siegfried binary based on OS
                        os_name = platform.system().lower()
                        if os_name == 'windows':
                            binary_name = 'sf.exe'
                        elif os_name == 'linux' or os_name == 'darwin':  # Darwin is macOS
                            binary_name = 'sf'
                        else:
                            device_info["Siegfried Status"] = f"Unsupported OS: {os_name}"
                            return device_info

                        siegfried_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Siegfried', binary_name)
                        if not os.path.exists(siegfried_path):
                            device_info["Siegfried Status"] = f"Siegfried binary '{binary_name}' not found at {siegfried_path}"
                            return device_info
                        if not os.access(siegfried_path, os.X_OK):
                            device_info["Siegfried Status"] = f"Siegfried binary '{binary_name}' at {siegfried_path} is not executable"
                            return device_info

                        try:
                            # Collect up to 20000 file paths
                            max_files = 20000
                            count = 0
                            file_paths = []
                            for root, _, files in os.walk(scan_path):
                                for file in files:
                                    count += 1
                                    full_path = os.path.join(root, file)
                                    file_paths.append(full_path)
                                    if count >= max_files:
                                        break
                                if count >= max_files:
                                    break

                            if file_paths:
                                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp:
                                    temp.write('\n'.join(file_paths))
                                temp_path = temp.name

                                cmd = [siegfried_path, '-json', '-f', temp_path]
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                if result.returncode != 0:
                                    device_info["Siegfried Error"] = f"Command failed with return code {result.returncode}: {result.stderr}"
                                    os.unlink(temp_path)
                                    return device_info
                                    
                                json_data = json.loads(result.stdout)
                                
                                formats = {}
                                scanned_files = len(json_data.get('files', []))
                                for file_entry in json_data.get('files', []):
                                    for match in file_entry.get('matches', []):
                                        if match.get('ns') == 'pronom':
                                            fmt = match.get('id')
                                            formats[fmt] = formats.get(fmt, 0) + 1
                                            break
                                
                                os.unlink(temp_path)
                                
                                if formats:
                                    device_info["Scanned Files"] = scanned_files
                                    device_info["File Formats"] = formats
                            else:
                                device_info["Siegfried Status"] = "No files found to scan"
                        except Exception as e:
                            device_info["Siegfried Exception"] = str(e)
                    else:
                        # Lightweight file type scanning
                        try:
                            file_types = {}
                            count = 0
                            max_files = 20000
                            
                            for root, _, files in os.walk(scan_path):
                                for file in files:
                                    count += 1
                                    ext = os.path.splitext(file)[1].lower()
                                    if ext == '':
                                        ext = 'no_extension'
                                    file_types[ext] = file_types.get(ext, 0) + 1
                                    
                                    if count >= max_files:
                                        break
                                if count >= max_files:
                                    break
                            
                            device_info["Scanned Files"] = count
                            device_info["File Types"] = file_types
                        except Exception as e:
                            device_info["Lightweight Scan Error"] = str(e)
                return device_info
        return None

    @staticmethod
    def guess_device_type(partition):
        """
        Determines the type of a storage device based on its properties.

        Analyzes the device path, filesystem type, and mount options to classify
        the device as CD/DVD, Floppy, Zip Disk, or Regular Storage.

        @param partition: A psutil partition object containing device details.
        @return: A string indicating the device type (e.g., 'CD/DVD', 'Regular Storage').
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
        return "Regular Storage"

class ConfigManager:
    """
    Manages configuration settings for the application.

    Handles loading, saving, and updating configuration data stored in a JSON file,
    including the working directory and duplicates table column visibility settings.
    """

    def __init__(self, config_file):
        """
        Initializes the ConfigManager with a specified configuration file.

        Loads the configuration from the file or initializes with default settings
        if the file does not exist or is corrupted.

        @param config_file: The path to the configuration JSON file.
        """
        self.config_file = config_file
        self.default_config = {
            "working_directory": None,
            "duplicates_table_columns": {
                "File Name": True,
                "Hash": True,
                "Location": True
            }
        }
        self.config = self.load_config()

    def load_config(self):
        """
        Loads configuration from the JSON file.

        If the file exists, it merges the loaded configuration with default settings.
        If the file is missing or corrupted, it creates a new file with default settings.

        @return: A dictionary containing the configuration settings.
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)
                    # Merge with default config to ensure all keys exist
                    config = self.default_config.copy()
                    config.update(loaded_config)
                    return config
            except Exception:
                # If file is corrupted, use default and save it
                self.save_config(self.default_config)
                return self.default_config.copy()
        else:
            # Create config file with defaults
            self.save_config(self.default_config)
            return self.default_config.copy()

    def save_config(self, config=None):
        """
        Saves configuration to the JSON file.

        @param config: Optional dictionary to save; if None, saves the current configuration.
        """
        if config is None:
            config = self.config
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def get_working_directory(self):
        """
        Retrieves the current working directory from the configuration.

        @return: The working directory path as a string, or None if not set.
        """
        return self.config.get("working_directory")

    def set_working_directory(self, directory):
        """
        Sets and saves the working directory in the configuration.

        @param directory: The directory path to set as the working directory.
        """
        self.config["working_directory"] = directory
        self.save_config()

    def get_duplicates_table_columns(self):
        """
        Retrieves the visibility settings for duplicates table columns.

        @return: A dictionary mapping column names to their visibility (True/False).
        """
        return self.config.get("duplicates_table_columns", self.default_config["duplicates_table_columns"])

    def set_duplicates_table_columns(self, columns):
        """
        Sets and saves the visibility settings for duplicates table columns.

        @param columns: A dictionary mapping column names to their visibility (True/False).
        """
        self.config["duplicates_table_columns"] = columns
        self.save_config()

class DeviceMonitor:
    """
    Manages live monitoring of storage devices.

    Updates a table widget with real-time information about device partitions,
    including size and access status, using a QTimer for periodic updates.
    """

    def __init__(self, table_widget):
        """
        Initializes the DeviceMonitor with a table widget for displaying device data.

        @param table_widget: QTableWidget to display device information.
        """
        self.table_widget = table_widget
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_table)

    def start_monitoring(self):
        """
        Starts periodic monitoring of devices.

        Updates the table every 5 seconds with current device information.
        """
        self.timer.start(5000)  # Update every 5 seconds
        self.update_table()

    def stop_monitoring(self):
        """
        Stops the periodic monitoring of devices.
        """
        self.timer.stop()

    def update_table(self):
        """
        Updates the table widget with current device information.

        Populates the table with device details such as device path, mount options,
        filesystem type, and total size. Displays 'N/A' for inaccessible devices.
        """
        partitions = psutil.disk_partitions()
        self.table_widget.setRowCount(len(partitions))
        for i, partition in enumerate(partitions):
            if self.get_access(partition.device):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    size = bytes2human(usage.total)
                except Exception:
                    size = "N/A"
                self.table_widget.setItem(i, 0, QTableWidgetItem(partition.device))
                self.table_widget.setItem(i, 1, QTableWidgetItem(partition.opts))
                self.table_widget.setItem(i, 2, QTableWidgetItem(partition.fstype))
                self.table_widget.setItem(i, 3, QTableWidgetItem(size))
            else:
                self.table_widget.setItem(i, 0, QTableWidgetItem(partition.device))
                self.table_widget.setItem(i, 1, QTableWidgetItem("N/A"))
                self.table_widget.setItem(i, 2, QTableWidgetItem("N/A"))
                self.table_widget.setItem(i, 3, QTableWidgetItem("N/A"))

    def get_access(self, device):
        """
        Checks if a device is accessible by attempting to retrieve its disk usage.

        @param device: The device path to check.
        @return: Boolean indicating whether the device is accessible.
        """
        try:
            return psutil.disk_usage(device).total > 0
        except (PermissionError, FileNotFoundError, OSError):
            return False

class DeviceViewer:
    """
    Handles displaying detailed device information and visualizations.

    Displays device details in a text widget and generates a bar chart of file formats
    or extensions using matplotlib, based on data from DeviceInfoCollector.
    """

    def __init__(self, output_widget, figure, canvas):
        """
        Initializes the DeviceViewer with widgets for output and visualization.

        @param output_widget: QTextEdit widget for displaying textual device information.
        @param figure: Matplotlib Figure object for plotting.
        @param canvas: FigureCanvasQTAgg object for rendering the plot.
        """
        self.output_widget = output_widget
        self.figure = figure
        self.canvas = canvas

    def view_device(self, device, use_siegfried=True, directory=None):
        """
        Displays detailed information and a visualization for a specified device.

        Collects device information using DeviceInfoCollector and displays it in the
        output widget. Generates a bar chart of the top 10 file formats (Siegfried) or
        extensions (lightweight scan).

        @param device: The device path to analyze.
        @param use_siegfried: Boolean indicating whether to use Siegfried for file format identification.
        @param directory: Optional directory path to scan instead of the device's mountpoint.
        """
        info = DeviceInfoCollector.collect_device_info(device, use_siegfried, directory)
        if not info:
            self.output_widget.setText(f"Device {device} not found.")
            return

        output = []
        output.append(f"Device Details: {device}")
        output.append(f"Mountpoint: {info.get('Mountpoint', 'N/A')}")
        output.append(f"Filesystem Type: {info.get('Filesystem Type', 'N/A')}")
        output.append(f"Mount Options: {info.get('Mount Options', 'N/A')}")
        output.append(f"Device Type: {info.get('Device Type', 'N/A')}")
        if "Access Restrictions" in info:
            output.append(f"Access Restrictions: {info['Access Restrictions']}")

        if "Total Size" in info:
            output.append("Disk Usage:")
            output.append(f"  Total: {info['Total Size']}")
            output.append(f"  Used: {info['Used Size']}")
            output.append(f"  Free: {info['Free Size']}")
            output.append(f"  Usage: {info['Usage Percent']}")
        else:
            output.append("Disk Usage: Not available")

        fs_stats = info.get("Filesystem Statistics")
        if isinstance(fs_stats, dict):
            output.append("\nFilesystem Statistics:")
            for key, value in fs_stats.items():
                output.append(f"  {key}: {value}")
        else:
            output.append("Filesystem Statistics: Not available")

        io_counters = info.get("Disk I/O Counters")
        if isinstance(io_counters, dict):
            output.append("Disk I/O Counters:")
            for key, value in io_counters.items():
                output.append(f"  {key}: {value}")
        else:
            output.append("Disk I/O Counters: Not available")

        content = info.get("Top-Level Content Overview")
        if isinstance(content, dict):
            output.append("Top-Level Content Overview:")
            output.append(f"  Files: {content['Files']}, Directories: {content['Directories']}")
        else:
            output.append("Top-Level Content Overview: Not available")

        # File format identification results
        if use_siegfried:
            if "Siegfried Status" in info:
                output.append(f"\nSiegfried: {info['Siegfried Status']}")
            elif "Siegfried Error" in info:
                output.append(f"\nSiegfried Error: {info['Siegfried Error']}")
            elif "Siegfried Exception" in info:
                output.append(f"\nSiegfried Exception: {info['Siegfried Exception']}")
            elif "File Formats" in info and info["File Formats"]:
                formats = info["File Formats"]
                scanned_files = info.get("Scanned Files", 0)
                output.append("\nFile Formats Breakdown (PRONOM):")
                output.append(f"  Files Scanned: {scanned_files}\n")
                output.append(f"{'Count':<6} | {'Format (PUID)'}")
                output.append(f"{'-'*6} | {'-'*30}")
                for fmt, cnt in sorted(formats.items(), key=lambda x: x[1], reverse=True):
                    output.append(f"{cnt:<6} | {fmt}")
                
                # Generate chart
                self.figure.clear()
                ax = self.figure.add_subplot(111)
                top_formats = sorted(formats.items(), key=lambda x: x[1], reverse=True)[:10]
                if top_formats:
                    labels = [f[0] for f in top_formats]
                    counts = [f[1] for f in top_formats]
                    ax.bar(labels, counts)
                    ax.set_xlabel('File Formats (PUID)')
                    ax.set_ylabel('Frequency')
                    ax.set_title('Top File Formats Frequency')
                    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
                    self.figure.tight_layout()
                else:
                    # Display a message when no formats are found
                    ax.text(0.5, 0.5, 'No file formats detected', 
                           horizontalalignment='center', verticalalignment='center',
                           transform=ax.transAxes, fontsize=14)
                    ax.set_axis_off()
                self.canvas.draw()
            else:
                output.append("\nFile Formats Breakdown (PRONOM): Not available")
                # Clear the chart and display a message
                self.figure.clear()
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No file formats data available', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=14)
                ax.set_axis_off()
                self.canvas.draw()
        else:
            # Lightweight file type scanning results
            if "Lightweight Scan Error" in info:
                output.append(f"\nLightweight Scan Error: {info['Lightweight Scan Error']}")
            elif "File Types" in info and info["File Types"]:
                file_types = info["File Types"]
                scanned_files = info.get("Scanned Files", 0)
                output.append("\nFile Types Breakdown (Lightweight):")
                output.append(f"  Files Scanned: {scanned_files}\n")
                output.append(f"{'Count':<6} | {'Extension'}")
                output.append(f"{'-'*6} | {'-'*15}")
                
                for ext, cnt in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
                    output.append(f"{cnt:<6} | {ext}")
                
                # Generate chart for lightweight scan
                self.figure.clear()
                ax = self.figure.add_subplot(111)
                top_extensions = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10]
                if top_extensions:
                    labels = [f[0] for f in top_extensions]
                    counts = [f[1] for f in top_extensions]
                    ax.bar(labels, counts)
                    ax.set_xlabel('File Extensions')
                    ax.set_ylabel('Frequency')
                    ax.set_title('Top File Extensions Frequency')
                    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
                    self.figure.tight_layout()
                else:
                    # Display a message when no extensions are found
                    ax.text(0.5, 0.5, 'No file extensions detected', 
                           horizontalalignment='center', verticalalignment='center',
                           transform=ax.transAxes, fontsize=14)
                    ax.set_axis_off()
                self.canvas.draw()
            else:
                output.append("\nFile Types Breakdown (Lightweight): Not available")
                # Clear the chart and display a message
                self.figure.clear()
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No file types data available', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=14)
                ax.set_axis_off()
                self.canvas.draw()

        self.output_widget.setText("\n".join(output))

class ElementSelectionDialog(QDialog):
    """
    A dialog for selecting device information elements to export.

    Displays a list of checkboxes for each available element, allowing the user to
    choose which elements to include in an export operation.
    """

    def __init__(self, elements, parent=None):
        """
        Initializes the dialog with a list of elements as checkboxes.

        @param elements: List of element names to display as checkboxes.
        @param parent: Optional parent widget for the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Select Elements to Export")
        self.layout = QVBoxLayout()
        self.checkboxes = []

        for element in elements:
            checkbox = QCheckBox(element)
            checkbox.setFont(QFont("Arial", DEFAULT_FONT_SIZE))
            self.checkboxes.append(checkbox)
            self.layout.addWidget(checkbox)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)
        self.setLayout(self.layout)

    def get_selected_elements(self):
        """
        Retrieves the list of selected elements.

        @return: A list of strings representing the names of selected elements.
        """
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class Exporter:
    """
    Handles exporting device information to a spreadsheet.

    Uses spaCy to match device information keys to spreadsheet columns and supports
    exporting to CSV or Excel files.
    """

    def __init__(self, config_manager):
        """
        Initializes the Exporter with a configuration manager and loads the spaCy model.

        @param config_manager: ConfigManager instance for accessing the working directory.
        """
        self.config_manager = config_manager
        try:
            self.nlp = spacy.load("en_core_web_lg")
        except OSError:
            # Show a message if the spaCy model is not available
            QMessageBox.warning(None, "spaCy Model Missing", 
                               "The spaCy model 'en_core_web_lg' is not installed. "
                               "Please install it with: python -m spacy download en_core_web_lg")
            self.nlp = None

    def export_device(self, device, parent_widget):
        """
        Exports selected device information to a spreadsheet file.

        Prompts the user to select elements to export and a file location, then uses spaCy
        to match keys to existing spreadsheet columns or creates new ones.

        @param device: The device path to export information for.
        @param parent_widget: The parent widget for displaying dialogs and status messages.
        """
        if not self.nlp:
            parent_widget.statusBar().showMessage("spaCy model not available. Cannot export.", 5000)
            return
            
        info = DeviceInfoCollector.collect_device_info(device)
        if not info:
            parent_widget.statusBar().showMessage(f"Device {device} not found.", 5000)
            return

        # Prompt user to select elements to export
        dialog = ElementSelectionDialog(list(info.keys()), parent_widget)
        if dialog.exec_() == QDialog.Rejected:
            return
        selected_keys = dialog.get_selected_elements()
        if not selected_keys:
            parent_widget.statusBar().showMessage("No elements selected for export.", 5000)
            return

        # Select spreadsheet file
        working_directory = self.config_manager.get_working_directory()
        if not working_directory:
            working_directory = QFileDialog.getExistingDirectory(parent_widget, "Select Working Directory")
            if not working_directory:
                return
            self.config_manager.set_working_directory(working_directory)

        file_path = QFileDialog.getSaveFileName(parent_widget, "Save Spreadsheet", working_directory, "CSV (*.csv);;Excel (*.xlsx)")[0]
        if not file_path:
            return

        try:
            # Read existing spreadsheet or create a new one
            if os.path.exists(file_path):
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)
            else:
                df = pd.DataFrame()
            column_names = list(df.columns) if not df.empty else []

            # Match selected keys to spreadsheet columns using spaCy
            export_data = {}
            matched_scores = {}
            col_docs = {col: self.nlp(col) for col in column_names}

            for key in selected_keys:
                value   = info[key]
                key_doc = self.nlp(key)
                best_match = None
                best_score = 0

                for col, col_doc in col_docs.items():
                    score = key_doc.similarity(col_doc)
                    if score > best_score:
                        best_score  = score
                        best_match  = col

                # If it's a good match, map to that column; otherwise add a new one
                if best_match and best_score >= matched_scores.get(best_match, 0):
                    export_data[best_match] = value
                    matched_scores[best_match] = best_score
                else:
                    export_data[key] = value
                    if key not in column_names:
                        column_names.append(key)

            # Build new row with all spreadsheet columns
            new_row = {col: export_data.get(col, None) for col in column_names}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            # Save to file
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=False)
            else:
                df.to_excel(file_path, index=False)
            parent_widget.statusBar().showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            parent_widget.statusBar().showMessage(f"Error exporting: {e}", 5000)

class DuplicateFinderThread(QThread):
    """
    A thread for finding duplicate files in a directory using MD5 hashing.

    Runs in the background to compute file hashes and identify duplicates, emitting
    progress and result signals.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)

    def __init__(self, directory):
        """
        Initializes the thread with a directory to scan for duplicates.

        @param directory: The directory path to scan for duplicate files.
        """
        super().__init__()
        self.directory = directory
        self._result_all_hashes = {}  # Store all file hashes

    def md5(self, file_path):
        """
        Computes the MD5 hash of a file.

        Reads the file in chunks to handle large files efficiently.

        @param file_path: The path to the file to hash.
        @return: A tuple containing the MD5 hash (string) and file path, or (None, file_path) if an error occurs.
        """
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5()
                while chunk := f.read(8192):
                    file_hash.update(chunk)
                return file_hash.hexdigest(), file_path
        except Exception:
            return None, file_path

    def run(self):
        """
        Executes the duplicate file search in the specified directory.

        Scans all files, computes their MD5 hashes in parallel, and identifies duplicates.
        Emits progress signals during processing and a finished signal with the duplicates dictionary.
        """
        hashes = {}
        duplicates = {}
        file_paths = []

        # Scan all files in the directory
        for root, _, files in os.walk(self.directory):
            for file in files:
                file_paths.append(os.path.join(root, file))

        total_files = len(file_paths)
        if total_files == 0:
            self.finished.emit({})
            return
            
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {executor.submit(self.md5, fp): fp for fp in file_paths}
            processed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                processed += 1
                self.progress.emit(int((processed / total_files) * 100))
                file_hash, file_path = future.result()
                if file_hash:
                    if file_hash in hashes:
                        if file_hash in duplicates:
                            duplicates[file_hash].append(file_path)
                        else:
                            duplicates[file_hash] = [hashes[file_hash], file_path]
                    else:
                        hashes[file_hash] = file_path

        # Store all file hashes for later use (including unique files)
        self._result_all_hashes = hashes

        self.finished.emit(duplicates)

class DuplicateFinder:
    """
    Manages the process of finding and displaying duplicate files.

    Provides a UI for selecting a directory, initiating a duplicate search, and displaying
    results in a table. Supports filtering between duplicates and all files.
    """

    def __init__(self, combo_box, dir_input, btn_browse, btn_find,
                 progress_bar, table_widget, filter_dropdown, parent_widget):
        """
        Initializes the DuplicateFinder with UI components.

        @param combo_box: QComboBox for selecting devices.
        @param dir_input: QLineEdit for entering or displaying the directory path.
        @param btn_browse: QPushButton for browsing directories.
        @param btn_find: QPushButton for initiating the duplicate search.
        @param progress_bar: QProgressBar for showing scan progress.
        @param table_widget: QTableWidget for displaying results.
        @param filter_dropdown: QComboBox for filtering between duplicates and all files.
        @param parent_widget: The parent widget (MainWindow) for accessing the status bar and config.
        """
        self.combo_box = combo_box
        self.dir_input = dir_input
        self.btn_browse = btn_browse
        self.btn_find = btn_find
        self.progress_bar = progress_bar
        self.table_widget = table_widget
        self.filter_dropdown = filter_dropdown
        self.parent_widget = parent_widget

        self.all_file_hashes = {}  # Store all files, not just dupes
        self.duplicates_only = {}

        self.btn_browse.clicked.connect(self.browse_directory)
        self.btn_find.clicked.connect(self.find_duplicates)
        self.filter_dropdown.currentIndexChanged.connect(self.update_table_display)
        
        # Apply initial column visibility
        self.apply_column_visibility()

    def apply_column_visibility(self):
        """
        Applies saved column visibility settings to the duplicates table.

        Uses configuration settings to show or hide columns in the table.
        """
        if hasattr(self.parent_widget, 'config_manager'):
            columns_config = self.parent_widget.config_manager.get_duplicates_table_columns()
            
            # Column order: ["File Name", "Hash", "Location"]
            column_indices = {
                "File Name": 0,
                "Hash": 1,
                "Location": 2
            }
            
            for column_name, visible in columns_config.items():
                col_index = column_indices.get(column_name)
                if col_index is not None:
                    if visible:
                        self.table_widget.showColumn(col_index)
                    else:
                        self.table_widget.hideColumn(col_index)

    def browse_directory(self):
        """
        Opens a directory selection dialog initialized to the selected device's mountpoint.

        Sets the selected directory in the dir_input field.
        """
        device = self.combo_box.currentText()
        mountpoint = next((p.mountpoint for p in psutil.disk_partitions() if p.device == device), None)
        if mountpoint:
            directory = QFileDialog.getExistingDirectory(self.parent_widget, "Select Directory", mountpoint)
            if directory:
                self.dir_input.setText(directory)

    def find_duplicates(self):
        """
        Initiates a background thread to find duplicate files in the selected directory.

        Disables the find button during processing and updates the progress bar.
        """
        directory = self.dir_input.text() or next((p.mountpoint for p in psutil.disk_partitions() if p.device == self.combo_box.currentText()), None)
        if not directory or not os.path.exists(directory):
            self.parent_widget.statusBar().showMessage("Invalid directory selected.", 5000)
            return

        self.dupe_thread = DuplicateFinderThread(directory)
        self.dupe_thread.progress.connect(self.progress_bar.setValue)
        self.dupe_thread.finished.connect(self.display_duplicates)
        self.dupe_thread.start()
        self.btn_find.setEnabled(False)

    def display_duplicates(self, duplicates):
        """
        Displays the results of the duplicate file search in the table widget.

        Updates the table with duplicate files or all files based on the filter setting.

        @param duplicates: A dictionary mapping MD5 hashes to lists of duplicate file paths.
        """
        self.duplicates_only = duplicates
        self.all_file_hashes = {}  # key: hash, value: list of files

        for hash_val, files in duplicates.items():
            self.all_file_hashes[hash_val] = files

        # Add in non-duplicate hashes from the scan
        for hash_val, file_path in self.dupe_thread._result_all_hashes.items():
            if hash_val not in self.all_file_hashes:
                self.all_file_hashes[hash_val] = [file_path]

        self.update_table_display()
        self.btn_find.setEnabled(True)
        self.parent_widget.statusBar().showMessage("Duplicate search completed.", 5000)

    def update_table_display(self):
        """
        Updates the table widget to display either duplicate files or all files.

        Populates the table based on the current filter setting in the dropdown.
        """
        # Get current mode from the dropdown
        mode = self.filter_dropdown.currentText()

        # Use the appropriate data based on the selected mode
        data_to_display = self.duplicates_only if mode == "Duplicates Only" else self.all_file_hashes

        # Build a flat list of rows: one row per file
        rows = []
        for hash_value, files in data_to_display.items():
            for file_path in files:
                file_name = os.path.basename(file_path)
                rows.append((file_name, hash_value, file_path))

        # Update table size
        self.table_widget.setRowCount(len(rows))

        # Fill table with rows
        for i, (file_name, hash_value, file_path) in enumerate(rows):
            self.table_widget.setItem(i, 0, QTableWidgetItem(str(file_name)))
            self.table_widget.setItem(i, 1, QTableWidgetItem(str(hash_value)))
            self.table_widget.setItem(i, 2, QTableWidgetItem(str(file_path)))

    def copy_file(self, src_path, dst_path, buffer_size=1024*1024):
        """
        Copies a file from source to destination while preserving metadata.

        Reads and writes in chunks to handle large files efficiently and preserves
        access and modification times.

        @param src_path: Source file path.
        @param dst_path: Destination file path.
        @param buffer_size: Size of the read/write buffer in bytes.
        """
        # Read/write in chunks so you don't blow out memory on large files
        with open(src_path, "rb") as src, open(dst_path, "wb") as dst:
            while True:
                chunk = src.read(buffer_size)
                if not chunk:
                    break
                dst.write(chunk)

        # Preserve original timestamps (access & modification times)
        stat = os.stat(src_path)
        os.utime(dst_path, (stat.st_atime, stat.st_mtime))

    # def create_duplicate_folder(self, duplicates):
    #     """
    #     Creates a directory structure for duplicate files.

    #     Organizes duplicates into subdirectories named by their MD5 hashes under a
    #     'Duplicates' folder in the working directory.

    #     @param duplicates: A dictionary mapping MD5 hashes to lists of duplicate file paths.
    #     """
    #     base_dup_dir = os.path.join(self.parent_widget.config_manager.get_working_directory(),"Duplicates")
    #     os.makedirs(base_dup_dir, exist_ok=True)

    #     for hash_value, files in duplicates.items():
    #         hash_dir = os.path.join(base_dup_dir, hash_value)
    #         os.makedirs(hash_dir, exist_ok=True)

    #         for file_path in files:
    #             try:
    #                 dest = os.path.join(hash_dir, os.path.basename(file_path))
    #                 self.copy_file(file_path, dest)
    #             except Exception as e:
    #                 self.parent_widget.statusBar().showMessage(f"Error copying {file_path}: {e}", 5000)

class MainWindow(QMainWindow):
    """
    The main application window.

    Provides a tabbed interface for monitoring devices, viewing detailed information,
    finding duplicates, and configuring settings.
    """

    def __init__(self):
        """
        Initializes the main window with tabs and configuration manager.

        Sets up the UI with a fixed size and initializes all tabs and components.
        """
        super().__init__()
        self.setWindowTitle("Device Monitor App")
        self.setGeometry(100, 100, 659, 800) 
        self.setFixedSize(659, 800)
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Set application-wide font
        font = QFont()
        font.setPointSize(DEFAULT_FONT_SIZE)
        self.setFont(font)
        
        self.init_tabs()
        
        # Apply initial column visibility
        QTimer.singleShot(100, self.apply_column_visibility)

    def init_tabs(self):
        """
        Initializes the tabs for the application.

        Creates tabs for monitoring, file scanning, duplicates, and settings, and
        initializes their respective UI components.
        """
        self.tab_monitor = QWidget()
        self.tab_view = QWidget()
        #self.tab_export = QWidget()
        self.tab_dupes = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_monitor, "Monitor")
        self.tabs.addTab(self.tab_view, "File Scan")
        #self.tabs.addTab(self.tab_export, "Export")
        self.tabs.addTab(self.tab_dupes, "Duplicates")
        self.tabs.addTab(self.tab_settings, "Settings")

        self.init_monitor_tab()
        self.init_view_tab()
        #self.init_export_tab()
        self.init_duplicates_tab()
        self.init_settings_tab()
        
        self.exporter = Exporter(self.config_manager)

    def init_monitor_tab(self):
        """
        Initializes the Monitor tab.

        Sets up a table to display real-time device information and starts the DeviceMonitor.
        """
        layout = QVBoxLayout()
        device_table = QTableWidget()
        device_table.setColumnCount(4)
        device_table.setHorizontalHeaderLabels(["Device", "Type", "Filesystem", "Size"])
        
        # Set font size for table
        font = device_table.font()
        font.setPointSize(DEFAULT_FONT_SIZE)
        device_table.setFont(font)
        
        layout.addWidget(device_table)
        self.tab_monitor.setLayout(layout)

        self.device_monitor = DeviceMonitor(device_table)
        self.device_monitor.start_monitoring()

    def init_view_tab(self):
        """
        Initializes the File Scan tab.

        Sets up a UI for selecting devices, scan methods, and directories, displaying
        results, and exporting data.
        """
        # Create main layout
        main_layout = QVBoxLayout()
        
        # First row: Device selection and scan method
        top_row_layout = QHBoxLayout()
        device_combo = QComboBox()
        device_combo.setFixedWidth(200)
        self.update_device_combo(device_combo)
        
        # Add scan method dropdown
        scan_method_label = QLabel("Scan Method:")
        scan_method_combo = QComboBox()
        scan_method_combo.addItems(["Siegfried", "Lightweight"])
        scan_method_combo.setCurrentText("Siegfried")  # Default to Siegfried
        
        top_row_layout.addWidget(device_combo)
        top_row_layout.addWidget(scan_method_label)
        top_row_layout.addWidget(scan_method_combo)
        top_row_layout.addStretch()
        
        # Second row: Directory selection
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Directory (optional):")
        dir_input = QLineEdit()
        dir_input.setPlaceholderText("Enter or select a directory")
        btn_browse_dir = QPushButton("Browse")
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(dir_input)
        dir_layout.addWidget(btn_browse_dir)
        
        # Third row: View button
        btn_view_device = QPushButton("View Selected Device Info")
        
        # Console output
        console_output = QTextEdit()
        console_output.setReadOnly(True)
        font = QFont("Courier New", DEFAULT_FONT_SIZE)
        console_output.setFont(font)
        
        # Export button
        btn_export = QPushButton("Export Device Info")

        # Create Matplotlib figure and canvas
        self.figure = Figure(figsize=(8, 8))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Add all to main layout
        main_layout.addLayout(top_row_layout)
        main_layout.addLayout(dir_layout)
        main_layout.addWidget(btn_view_device)
        main_layout.addWidget(console_output, 2)
        main_layout.addWidget(self.canvas, 1)
        main_layout.addWidget(btn_export)
        
        self.tab_view.setLayout(main_layout)

        # Connect browse button - FIXED: Move the connection outside the function
        def browse_directory():
            device = device_combo.currentText()
            mountpoint = next((p.mountpoint for p in psutil.disk_partitions() if p.device == device), None)
            if mountpoint:
                directory = QFileDialog.getExistingDirectory(self, "Select Directory", mountpoint)
                if directory:
                    dir_input.setText(directory)
        
        btn_browse_dir.clicked.connect(browse_directory)
        
        self.device_viewer = DeviceViewer(console_output, self.figure, self.canvas)
        
        # Connect view button
        btn_view_device.clicked.connect(lambda: self.device_viewer.view_device(
            device_combo.currentText(),
            scan_method_combo.currentText() == "Siegfried",
            dir_input.text() if dir_input.text() else None
        ))
        
        btn_export.clicked.connect(lambda: self.exporter.export_device(device_combo.currentText(), self))
        
    def update_device_combo(self, combo_box):
        """
        Updates the device selection combo box with current partitions.

        @param combo_box: QComboBox to populate with device paths.
        """
        combo_box.clear()
        partitions = psutil.disk_partitions()
        for partition in partitions:
            combo_box.addItem(partition.device)

    def init_duplicates_tab(self):
        """
        Initializes the Duplicates tab.

        Sets up a UI for selecting devices and directories, finding duplicates, and
        displaying results in a table.
        """
        layout = QVBoxLayout()

        # Top row: Device dropdown and filter dropdown
        top_row_layout = QHBoxLayout()
        dupe_combo = QComboBox()
        dupe_combo.setFixedWidth(200)
        self.update_device_combo(dupe_combo)

        filter_dropdown = QComboBox()
        filter_dropdown.addItems(["Duplicates Only", "All Files"])

        top_row_layout.addWidget(dupe_combo)
        top_row_layout.addWidget(QLabel("View:"))
        top_row_layout.addWidget(filter_dropdown)
        top_row_layout.addStretch()
        # Removed the stretch that was pushing the filter to the right

        # Second row: Directory input and browse button
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Directory (optional):")
        dir_input = QLineEdit()
        dir_input.setPlaceholderText("Enter or select a directory")
        btn_browse_dir = QPushButton("Browse")

        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(dir_input)
        dir_layout.addWidget(btn_browse_dir)

        # Other elements
        btn_find_dupes = QPushButton("Find Duplicate Files")
        dupe_progress = QProgressBar()

        dupe_table = QTableWidget()
        dupe_table.setColumnCount(3)
        dupe_table.setHorizontalHeaderLabels(["File Name", "Hash", "Location"])

        # Set font size for table
        font = dupe_table.font()
        font.setPointSize(DEFAULT_FONT_SIZE)
        dupe_table.setFont(font)

        # set initial column widths
        dupe_table.setColumnWidth(0, 300)
        dupe_table.setColumnWidth(1, 220)
        dupe_table.setColumnWidth(2, 400)
        dupe_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        dupe_table.setSortingEnabled(True)

        # Add all to main layout
        layout.addLayout(top_row_layout)
        layout.addLayout(dir_layout)
        layout.addWidget(btn_find_dupes)
        layout.addWidget(dupe_progress)
        layout.addWidget(dupe_table)

        self.tab_dupes.setLayout(layout)

        self.duplicate_finder = DuplicateFinder(
            dupe_combo, dir_input, btn_browse_dir, btn_find_dupes,
            dupe_progress, dupe_table, filter_dropdown, self)

        #self.duplicate_finder.create_duplicate_folder(self.duplicate_finder.duplicates_only)

    def init_settings_tab(self):
        """
        Initializes the Settings tab.

        Sets up a UI for configuring the working directory and duplicates table column visibility.
        """
        layout = QVBoxLayout()
    
        # Working Directory Section
        working_dir_group = QWidget()
        working_dir_layout = QVBoxLayout(working_dir_group)
        btn_set_directory = QPushButton("Set Working Directory")
        dir_label = QLabel(f"Current Directory: {self.config_manager.get_working_directory() or 'Not set'}")
        working_dir_layout.addWidget(btn_set_directory)
        working_dir_layout.addWidget(dir_label)
        
        # Duplicates Table Columns Section
        columns_group = QWidget()
        columns_layout = QVBoxLayout(columns_group)
        columns_label = QLabel("Duplicates Table Columns:")
        columns_layout.addWidget(columns_label)
        
        # Create checkboxes for each column
        self.column_checkboxes = {}
        columns_config = self.config_manager.get_duplicates_table_columns()
        
        for column_name, visible in columns_config.items():
            checkbox = QCheckBox(column_name)
            checkbox.setChecked(visible)
            checkbox.toggled.connect(self.update_columns_settings)
            self.column_checkboxes[column_name] = checkbox
            columns_layout.addWidget(checkbox)
        
        # Add sections to main layout
        layout.addWidget(working_dir_group)
        layout.addWidget(columns_group)
        layout.addStretch()
        
        self.tab_settings.setLayout(layout)
        btn_set_directory.clicked.connect(lambda: self.set_working_directory(dir_label))

    def update_columns_settings(self):
        """
        Updates column visibility settings when checkboxes are toggled.

        Saves the updated settings to the configuration.
        """
        columns_config = {}
        for column_name, checkbox in self.column_checkboxes.items():
            columns_config[column_name] = checkbox.isChecked()
        
        self.config_manager.set_duplicates_table_columns(columns_config)
        self.apply_column_visibility()

    def apply_column_visibility(self):
        """
        Applies column visibility settings to the duplicates table.

        Shows or hides table columns based on configuration settings.
        """
        if hasattr(self, 'duplicate_finder') and self.duplicate_finder.table_widget:
            columns_config = self.config_manager.get_duplicates_table_columns()
            table = self.duplicate_finder.table_widget
            
            # Column order: ["File Name", "Hash", "Location"]
            column_indices = {
                "File Name": 0,
                "Hash": 1,
                "Location": 2
            }
            
            for column_name, visible in columns_config.items():
                col_index = column_indices.get(column_name)
                if col_index is not None:
                    if visible:
                        table.showColumn(col_index)
                    else:
                        table.hideColumn(col_index)

    def set_working_directory(self, dir_label):
        """
        Sets the working directory via a dialog and updates the UI.

        @param dir_label: QLabel to update with the new directory path.
        """
        directory = QFileDialog.getExistingDirectory(self, "Select Working Directory")
        if directory:
            self.config_manager.set_working_directory(directory)
            dir_label.setText(f"Current Directory: {directory}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont()
    font.setPointSize(DEFAULT_FONT_SIZE)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

