import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
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
    from labjack import ljm
    if not DEV_MODE:
        handle = ljm.openS("T7", "ANY", "ANY")
    else:
        handle = None
except Exception as e:
    handle = None
    print(f"[Warning] Failed to connect to LabJack T7: {e}")
    sys.exit()


class DataLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GEARS LabJack Logger")
        self.running = False
        self.logged_rows = 0
        self.selected_channels = []
        self.voltage_entries = {}
        self.create_widgets()
        self.update_voltage_display()

    def create_widgets(self):
        default_font = ("Helvetica", 14)

        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        left_frame = tk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="n")

        right_frame = tk.Frame(main_frame)
        right_frame.grid(row=0, column=1, padx=40, sticky="n")

        self.check_vars = {}
        tk.Label(left_frame, text="Select Channels to Log:", font=("Helvetica", 16, "bold")).pack(anchor="w")
        for ch in CHANNELS:
            var = tk.BooleanVar()
            cb = tk.Checkbutton(left_frame, text=ch, variable=var, font=default_font)
            cb.pack(anchor="w", padx=10)
            self.check_vars[ch] = var
            cb._widget_ref = cb  # Save reference to enable/disable later
            var._widget_ref = cb

        tk.Label(left_frame, text="Logging Rate:", font=("Helvetica", 16, "bold")).pack(anchor="w", pady=(10, 0))
        self.rate_var = tk.StringVar(value="1 Hz (1 sec)")
        rate_menu = ttk.Combobox(left_frame, textvariable=self.rate_var, values=list(LOGGING_RATES.keys()), state="readonly", font=default_font)
        rate_menu.pack(anchor="w", padx=10, pady=(0, 10))

        self.start_button = tk.Button(left_frame, text="Start Logging", command=self.toggle_logging, font=default_font)
        self.start_button.pack(pady=(0, 10))

        self.exit_button = tk.Button(left_frame, text="Exit", command=self.root.quit, font=default_font)
        self.exit_button.pack(pady=(0, 10))

        self.status_label = tk.Label(
            right_frame,
            text="Not Logging",
            font=("Helvetica", 14, "bold"),
            bg="red",
            fg="white",
            padx=10,
            pady=5,
            relief="sunken",
            width=30,
            anchor="w"
        )
        self.status_label.pack(pady=(0, 10))

        self.filename_label = tk.Label(
            right_frame,
            text="",
            font=("Helvetica", 14),
            fg="white",
            width=40,
            anchor="w"
        )
        self.filename_label.pack(pady=(0, 10))

        tk.Label(right_frame, text="Live Voltage Readings:", font=("Helvetica", 16, "bold")).pack(anchor="w")
        for ch in CHANNELS:
            row = tk.Frame(right_frame)
            row.pack(anchor="w", pady=2)
            tk.Label(row, text=ch + ":", width=6, anchor="w", font=default_font).pack(side="left")
            ent = tk.Entry(row, width=10, justify="right", font=default_font)
            ent.insert(0, "N/A")
            ent.config(state="readonly")
            ent.pack(side="left")
            self.voltage_entries[ch] = ent

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
        self.status_label.config(text="Logging... Rows Logged: 0", bg="green")
        self.logged_rows = 0

        os.makedirs(DATA_DIR, exist_ok=True)
        self.log_file = self.get_next_log_filename()
        self.filename_label.config(text=f"Writing to: {os.path.basename(self.log_file)}")
        self.log_fp = open(self.log_file, "w", newline="")
        self.csv_writer = csv.writer(self.log_fp)
        header = ["timestamp"] + self.selected_channels
        self.csv_writer.writerow(header)

        self.log_thread = threading.Thread(target=self.logging_loop, daemon=True)
        self.log_thread.start()

    def stop_logging(self):
        self.running = False
        self.enable_controls()
        self.logged_rows = 0
        self.status_label.config(text="Not Logging", bg="red")
        self.filename_label.config(text="")
        if hasattr(self, 'log_fp'):
            self.log_fp.close()

    def disable_controls(self):
        for ch in self.check_vars:
            self.check_vars[ch]._widget_ref.config(state="disabled")
        self.start_button.config(text="Stop Logging")
        self.exit_button.config(state="disabled")
        for cb in self.check_vars.values():
            cb.set(cb.get())
        for child in self.root.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, tk.Checkbutton) or isinstance(sub, ttk.Combobox):
                    sub.config(state="disabled")

    def enable_controls(self):
        for ch in self.check_vars:
            self.check_vars[ch]._widget_ref.config(state="normal")
        self.start_button.config(text="Start Logging")
        self.exit_button.config(state="normal")
        for child in self.root.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, tk.Checkbutton) or isinstance(sub, ttk.Combobox):
                    sub.config(state="normal")

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
            self.status_label.config(text=f"Logging... Rows Logged: {self.logged_rows}", bg="green")
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
            val = voltages.get(ch, "N/A") if ch in self.selected_channels else "N/A"
            self.voltage_entries[ch].config(state="normal")
            self.voltage_entries[ch].delete(0, tk.END)
            self.voltage_entries[ch].insert(0, str(val))
            self.voltage_entries[ch].config(state="readonly")
        self.root.after(1000, self.update_voltage_display)


if __name__ == "__main__":
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    app = DataLoggerApp(root)
    root.mainloop()

    if handle and not DEV_MODE:
        ljm.close(handle)
