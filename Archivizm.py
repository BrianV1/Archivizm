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
    QComboBox, QProgressBar, QLineEdit, QDialog, QCheckBox, QDialogButtonBox
)

CONFIG_FILE = "config.json"

# Utility class to collect device information
class DeviceInfoCollector:
    @staticmethod
    def collect_device_info(device):
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
                    device_info["Access Restrictions"] = "Zip Drive"

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
                    items = os.listdir(partition.mountpoint)
                    num_files = sum(1 for item in items if os.path.isfile(os.path.join(partition.mountpoint, item)))
                    dir_count = sum(1 for item in items if os.path.isdir(os.path.join(partition.mountpoint, item)))
                    device采访["Top-Level Content Overview"] = {"Files": num_files, "Directories": dir_count}
                except Exception:
                    pass

                file_types = {}
                max_files = 20000
                count = 0
                try:
                    for root, _, files in os.walk(partition.mountpoint):
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
                except Exception:
                    pass
                return device_info
        return None

    @staticmethod
    def guess_device_type(partition):
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

# Manages configuration settings
class ConfigManager:
    def __init__(self, config_file):
        self.config_file = config_file
        self.working_directory = self.load_working_directory()

    def load_working_directory(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    return config.get("working_directory")
            except Exception:
                return None
        return None

    def save_working_directory(self, directory):
        try:
            with open(self.config_file, "w") as f:
                json.dump({"working_directory": directory}, f)
            self.working_directory = directory
        except Exception:
            pass

    def get_working_directory(self):
        return self.working_directory

    def set_working_directory(self, directory):
        self.working_directory = directory
        self.save_working_directory(directory)

# Handles live monitoring of devices
class DeviceMonitor:
    def __init__(self, table_widget):
        self.table_widget = table_widget
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_table)

    def start_monitoring(self):
        self.timer.start(5000)  # Update every 5 seconds
        self.update_table()

    def stop_monitoring(self):
        self.timer.stop()

    def update_table(self):
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
        try:
            return psutil.disk_usage(device).total > 0
        except (PermissionError, FileNotFoundError, OSError):
            return False

# Handles viewing detailed device information
class DeviceViewer:
    def __init__(self, output_widget):
        self.output_widget = output_widget

    def view_device(self, device):
        info = DeviceInfoCollector.collect_device_info(device)
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

        num_files = info.get("Number of Files")
        file_types = info.get("File Types")

        if num_files is not None and isinstance(file_types, dict):
            output.append("  File Types Breakdown:")
            output.append(f"  Files Scanned: {num_files}\n")

            # Header
            output.append(f"{'Count':<6} | {'Extension'}")
            output.append(f"{'-'*6} | {'-'*15}")

            # Rows
            for ext, cnt in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
                output.append(f"{cnt:<6} | {ext}")

        else:
            output.append("File Types Breakdown: Not available")

        self.output_widget.setText("\n".join(output))

# Custom dialog for selecting device info elements to export
class ElementSelectionDialog(QDialog):
    def __init__(self, elements, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Elements to Export")
        self.layout = QVBoxLayout()
        self.checkboxes = []

        for element in elements:
            checkbox = QCheckBox(element)
            self.checkboxes.append(checkbox)
            self.layout.addWidget(checkbox)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)
        self.setLayout(self.layout)

    def get_selected_elements(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

# Handles exporting device information with spaCy matching
class Exporter:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.nlp = spacy.load("en_core_web_lg")

    def export_device(self, device, parent_widget):
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
            for key in selected_keys:
                value = info[key]
                key_doc = self.nlp(key)
                best_match = None
                best_score = 0
                for col in column_names:
                    col_doc = self.nlp(str, Nortecol)
                    score = key_doc.similarity(col_doc)
                    if score > best_score:
                        best_score = score
                        best_match = col
                        matched_scores[col] = score
                if best_match and best_score >= matched_scores.get(best_match, 0):
                    export_data[best_match] = value
                else:
                    # If no match or low score, add as new column
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
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self._result_all_hashes = {}  # Store all file hashes

    def md5(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5()
                while chunk := f.read(8192):
                    file_hash.update(chunk)
                return file_hash.hexdigest(), file_path
        except Exception:
            return None, file_path

    def run(self):
        hashes = {}
        duplicates = {}
        file_paths = []

        # Scan all files in the directory
        for root, _, files in os.walk(self.directory):
            for file in files:
                file_paths.append(os.path.join(root, file))

        total_files = len(file_paths)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {executor.submit(self.md5, fp): fp for fp in file_paths}
            processed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                processed += 1
                self.progress.emit(int((processed / total_files) * 100))
                file_hash, file_path = future.result()
                if file_hash:
                    if file_hash in hashes:
                        duplicates[file_hash] = [file_path] + duplicates.get(file_hash, [])
                    else:
                        hashes[file_hash] = file_path

            # Populate both duplicates and non-duplicates
            for file_hash in duplicates:
                duplicates[file_hash].append(hashes[file_hash])

        # Store all file hashes for later use (including unique files)
        self._result_all_hashes = hashes

        self.finished.emit(duplicates)

# Handles finding duplicate files
class DuplicateFinder:
    def __init__(self, combo_box, dir_input, btn_browse, btn_find,
                 progress_bar, table_widget, filter_dropdown, parent_widget):
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

    def browse_directory(self):
        device = self.combo_box.currentText()
        mountpoint = next((p.mountpoint for p in psutil.disk_partitions() if p.device == device), None)
        if mountpoint:
            directory = QFileDialog.getExistingDirectory(self.parent_widget, "Select Directory", mountpoint)
            if directory:
                self.dir_input.setText(directory)

    def find_duplicates(self):
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
        # Get current mode from the dropdown
        mode = self.filter_dropdown.currentText()

        # Use the appropriate data based on the selected mode
        data_to_display = self.duplicates_only if mode == "Duplicates Only" else self.all_file_hashes

        self.table_widget.setRowCount(len(data_to_display))

        # Fill table with data
        for i, (hash_value, files) in enumerate(data_to_display.items()):
            self.table_widget.setItem(i, 0, QTableWidgetItem(hash_value))
            self.table_widget.setItem(i, 1, QTableWidgetItem("; ".join(files)))

# Main application-white
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Device Monitor App")
        self.setGeometry(100, 100, 1000, 700)
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.init_tabs()

    def init_tabs(self):
        self.tab_monitor = QWidget()
        self.tab_view = QWidget()
        self.tab_export = QWidget()
        self.tab_dupes = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_monitor, "Monitor")
        self.tabs.addTab(self.tab_view, "View Device")
        self.tabs.addTab(self.tab_export, "Export")
        self.tabs.addTab(self.tab_dupes, "Duplicates")
        self.tabs.addTab(self.tab_settings, "Settings")

        self.init_monitor_tab()
        self.init_view_tab()
        self.init_export_tab()
        self.init_duplicates_tab()
        self.init_settings_tab()

    def init_monitor_tab(self):
        layout = QVBoxLayout()
        device_table = QTableWidget()
        device_table.setColumnCount(4)
        device_table.setHorizontalHeaderLabels(["Device", "Type", "Filesystem", "Size"])
        layout.addWidget(device_table)
        self.tab_monitor.setLayout(layout)

        self.device_monitor = DeviceMonitor(device_table)
        self.device_monitor.start_monitoring()

    def init_view_tab(self):
        layout = QVBoxLayout()
        device_combo = QComboBox()
        self.update_device_combo(device_combo)
        btn_view_device = QPushButton("View Selected Device Info")
        console_output = QTextEdit()
        console_output.setReadOnly(True)
        font = QFont("Courier New")  # You can try "Consolas", "Monaco", or "Liberation Mono"
        font.setStyleHint(QFont.Monospace)
        console_output.setFont(font)

        layout.addWidget(device_combo)
        layout.addWidget(btn_view_device)
        layout.addWidget(console_output)
        self.tab_view.setLayout(layout)

        self.device_viewer = DeviceViewer(console_output)
        btn_view_device.clicked.connect(lambda: self.device_viewer.view_device(device_combo.currentText()))

    def update_device_combo(self, combo_box):
        combo_box.clear()
        partitions = psutil.disk_partitions()
        for partition in partitions:
            combo_box.addItem(partition.device)

    def init_export_tab(self):
        layout = QVBoxLayout()
        export_combo = QComboBox()
        self.update_device_combo(export_combo)
        btn_export = QPushButton("Export Device Info to Spreadsheet")
        layout.addWidget(export_combo)
        layout.addWidget(btn_export)
        self.tab_export.setLayout(layout)

        self.exporter = Exporter(self.config_manager)
        btn_export.clicked.connect(lambda: self.exporter.export_device(export_combo.currentText(), self))

    def init_duplicates_tab(self):
        layout = QVBoxLayout()
        dupe_combo = QComboBox()
        self.update_device_combo(dupe_combo)
        dir_input = QLineEdit()
        dir_input.setPlaceholderText("Enter or select a directory")
        btn_browse_dir = QPushButton("Browse")
        btn_find_dupes = QPushButton("Find Duplicate Files")
        dupe_progress = QProgressBar()
        filter_dropdown = QComboBox()
        filter_dropdown.addItems(["Duplicates Only", "All Files"])  # Default: show duplicates
        layout.addWidget(filter_dropdown)

        dupe_table = QTableWidget()
        dupe_table.setColumnCount(2)
        dupe_table.setHorizontalHeaderLabels(["Hash", "Files"])

        h_layout = QHBoxLayout()
        h_layout.addWidget(dupe_combo)
        h_layout.addWidget(dir_input)
        h_layout.addWidget(btn_browse_dir)
        layout.addLayout(h_layout)
        layout.addWidget(btn_find_dupes)
        layout.addWidget(dupe_progress)
        layout.addWidget(dupe_table)
        self.tab_dupes.setLayout(layout)

        self.duplicate_finder = DuplicateFinder(
            dupe_combo, dir_input, btn_browse_dir, btn_find_dupes,
            dupe_progress, dupe_table, filter_dropdown, self)

    def init_settings_tab(self):
        layout = QVBoxLayout()
        btn_set_directory = QPushButton("Set Working Directory")
        dir_label = QLabel(f"Current Directory: {self.config_manager.get_working_directory() or 'Not set'}")
        layout.addWidget(btn_set_directory)
        layout.addWidget(dir_label)
        layout.addStretch()
        self.tab_settings.setLayout(layout)

        btn_set_directory.clicked.connect(lambda: self.set_working_directory(dir_label))

    def set_working_directory(self, dir_label):
        directory = QFileDialog.getExistingDirectory(self, "Select Working Directory")
        if directory:
            self.config_manager.set_working_directory(directory)
            dir_label.setText(f"Current Directory: {directory}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
