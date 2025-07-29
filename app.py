import tkinter as tk
from tkinter import ttk, messagebox
import os
import csv
import time
import threading
from datetime import datetime
import random

# --- CONFIGURATION ---
DEV_MODE = False  # Set to True to simulate LabJack readings
DATA_DIR = os.path.expanduser("~/Desktop/data")
CHANNELS = ["AIN0", "AIN1", "AIN2", "AIN3"]

# Logging intervals in seconds
LOGGING_RATES = {
    "1 Hz (1 sec)": 1,
    "Every 10 sec": 10,
    "Every 30 sec": 30,
    "Every 1 min": 60,
    "Every 5 min": 300,
    "Every 10 min": 600
}

try:
    import ljm
    if not DEV_MODE:
        handle = ljm.openS("T7", "USB", "0")
    else:
        handle = None
except Exception:
    handle = None
    DEV_MODE = True


class DataLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GEARS LabJack Logger")
        self.running = False
        self.logged_rows = 0
        self.selected_channels = []
        self.voltage_labels = {}
        self.create_widgets()
        self.update_voltage_display()

    def create_widgets(self):
        self.check_vars = {}
        tk.Label(self.root, text="Select Channels to Log:").pack(anchor="w", padx=10, pady=(10, 0))
        for ch in CHANNELS:
            var = tk.BooleanVar()
            cb = tk.Checkbutton(self.root, text=ch, variable=var)
            cb.pack(anchor="w", padx=20)
            self.check_vars[ch] = var

        tk.Label(self.root, text="Logging Rate:").pack(anchor="w", padx=10, pady=(10, 0))
        self.rate_var = tk.StringVar(value="1 Hz (1 sec)")
        rate_menu = ttk.Combobox(self.root, textvariable=self.rate_var, values=list(LOGGING_RATES.keys()), state="readonly")
        rate_menu.pack(anchor="w", padx=20, pady=(0, 10))

        self.start_button = tk.Button(self.root, text="Start Logging", command=self.toggle_logging)
        self.start_button.pack(pady=(0, 10))

        self.status_label = tk.Label(self.root, text="Not Logging")
        self.status_label.pack()

        self.voltage_frame = tk.Frame(self.root)
        self.voltage_frame.pack(pady=(10, 10))

        for ch in CHANNELS:
            lbl = tk.Label(self.voltage_frame, text=f"{ch}: N/A")
            lbl.pack()
            self.voltage_labels[ch] = lbl

        self.exit_button = tk.Button(self.root, text="Exit", command=self.root.quit)
        self.exit_button.pack(pady=(10, 10))

    def toggle_logging(self):
        if not self.running:
            self.start_logging()
        else:
            self.stop_logging()

    def start_logging(self):
        self.selected_channels = [ch for ch, var in self.check_vars.items() if var.get()]
        if not self.selected_channels:
            messagebox.showerror("No Channels Selected", "Please select at least one analog input to log.")
            return

        self.running = True
        self.disable_controls()
        self.status_label.config(text="Logging... Rows Logged: 0")
        self.logged_rows = 0

        os.makedirs(DATA_DIR, exist_ok=True)
        self.log_file = self.get_next_log_filename()
        self.log_fp = open(self.log_file, "w", newline="")
        self.csv_writer = csv.writer(self.log_fp)
        header = ["timestamp"] + self.selected_channels
        self.csv_writer.writerow(header)

        self.log_thread = threading.Thread(target=self.logging_loop, daemon=True)
        self.log_thread.start()

    def stop_logging(self):
        self.running = False
        self.enable_controls()
        self.status_label.config(text=f"Stopped. Total Rows Logged: {self.logged_rows}")
        if hasattr(self, 'log_fp'):
            self.log_fp.close()

    def disable_controls(self):
        self.start_button.config(text="Stop Logging")
        for cb in self.check_vars.values():
            cb.set(cb.get())
        for child in self.root.winfo_children():
            if isinstance(child, tk.Checkbutton) or isinstance(child, ttk.Combobox):
                child.config(state="disabled")

    def enable_controls(self):
        self.start_button.config(text="Start Logging")
        for child in self.root.winfo_children():
            if isinstance(child, tk.Checkbutton) or isinstance(child, ttk.Combobox):
                child.config(state="normal")

    def get_next_log_filename(self):
        existing = [f for f in os.listdir(DATA_DIR) if f.startswith("log") and f.endswith(".csv")]
        nums = [int(f[3:-4]) for f in existing if f[3:-4].isdigit()]
        next_num = max(nums) + 1 if nums else 1
        return os.path.join(DATA_DIR, f"log{next_num}.csv")

    def logging_loop(self):
        interval = LOGGING_RATES[self.rate_var.get()]
        while self.running:
            timestamp = datetime.now().isoformat()
            voltages = self.read_voltages()
            row = [timestamp] + [voltages[ch] for ch in self.selected_channels]
            self.csv_writer.writerow(row)
            self.logged_rows += 1
            self.status_label.config(text=f"Logging... Rows Logged: {self.logged_rows}")
            self.log_fp.flush()
            time.sleep(interval)

    def read_voltages(self):
        result = {}
        for ch in self.selected_channels:
            if DEV_MODE:
                result[ch] = round(random.uniform(0, 5), 3)
            else:
                try:
                    v = ljm.eReadName(handle, ch)
                    result[ch] = round(v, 3)
                except:
                    result[ch] = "ERR"
        return result

    def update_voltage_display(self):
        voltages = self.read_voltages()
        for ch in CHANNELS:
            if ch in self.selected_channels:
                self.voltage_labels[ch].config(text=f"{ch}: {voltages.get(ch, 'N/A')}")
            else:
                self.voltage_labels[ch].config(text=f"{ch}: N/A")
        self.root.after(1000, self.update_voltage_display)


if __name__ == "__main__":
    root = tk.Tk()
    app = DataLoggerApp(root)
    root.mainloop()

    if handle and not DEV_MODE:
        ljm.close(handle)
