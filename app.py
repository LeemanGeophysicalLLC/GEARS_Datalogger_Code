import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import csv
import time
import threading
import json
import requests
from datetime import datetime
import random

DEV_MODE = False
SEND_TELEMETRY = True
DATA_DIR = os.path.expanduser("~/Desktop/data")
CHANNELS = ["AIN0", "AIN1", "AIN2", "AIN3"]
THINGSBOARD_HOST = "http://thingsboard.cloud"  # Replace if using local instance

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

# Load ThingsBoard access token
if SEND_TELEMETRY:
    try:
        with open("config.json") as f:
            config = json.load(f)
            ACCESS_TOKEN = config["access_token"]
            TB_URL = f"{THINGSBOARD_HOST}/api/v1/{ACCESS_TOKEN}/telemetry"
    except Exception as e:
        print(f"[Warning] Could not load ThingsBoard token: {e}")
        SEND_TELEMETRY = False

class DataLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GEARS LabJack Logger")
        self.root.configure(bg="#333333")
        self.running = False
        self.logged_rows = 0
        self.selected_channels = []
        self.voltage_entries = {}
        self.channel_buttons = {}
        self.create_widgets()
        self.update_voltage_display()

    def create_widgets(self):
        default_font = ("Helvetica", 14)

        main_frame = tk.Frame(self.root, bg="#333333")
        main_frame.pack(padx=10, pady=10)

        left_frame = tk.Frame(main_frame, bg="#333333")
        left_frame.grid(row=0, column=0, sticky="n")

        right_frame = tk.Frame(main_frame, bg="#333333")
        right_frame.grid(row=0, column=1, padx=40, sticky="n")

        tk.Label(left_frame, text="Select Channels to Log:", font=("Helvetica", 16, "bold"), fg="white", bg="#333333").pack(anchor="w")
        self.channel_states = {}
        for ch in CHANNELS:
            self.channel_states[ch] = False
            btn = tk.Button(left_frame, text=ch, font=("Helvetica", 18), width=10,
                            command=lambda ch=ch: self.toggle_channel(ch),
                            bg="#004400", fg="black", activeforeground="black")
            btn.pack(pady=5)
            self.channel_buttons[ch] = btn

        tk.Label(left_frame, text="Logging Rate:", font=("Helvetica", 16, "bold"), fg="white", bg="#333333").pack(anchor="w", pady=(10, 0))
        self.rate_var = tk.StringVar(value="1 Hz (1 sec)")
        rate_menu = ttk.Combobox(left_frame, textvariable=self.rate_var, values=list(LOGGING_RATES.keys()), state="readonly", font=default_font)
        rate_menu.pack(anchor="w", padx=10, pady=(0, 10))

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
            anchor="w",
            bg="#333333"
        )
        self.filename_label.pack(pady=(0, 10))

        tk.Label(right_frame, text="Live Voltage Readings:", font=("Helvetica", 16, "bold"), fg="white", bg="#333333").pack(anchor="w")
        for ch in CHANNELS:
            row = tk.Frame(right_frame, bg="#333333")
            row.pack(anchor="w", pady=2)
            tk.Label(row, text=ch + ":", width=6, anchor="w", font=default_font, fg="white", bg="#333333").pack(side="left")
            ent = tk.Entry(row, width=10, justify="right", font=default_font)
            ent.insert(0, "N/A")
            ent.config(state="readonly")
            ent.pack(side="left")
            self.voltage_entries[ch] = ent

        self.start_button = tk.Button(right_frame, text="Start Logging", command=self.toggle_logging, font=default_font, bg="#eeeeee", fg="black")
        self.start_button.pack(pady=(20, 10))

        self.exit_button = tk.Button(right_frame, text="Exit", command=self.root.quit, font=default_font, bg="#eeeeee", fg="black")
        self.exit_button.pack()

    def toggle_channel(self, ch):
        if self.running:
            return
        self.channel_states[ch] = not self.channel_states[ch]
        btn = self.channel_buttons[ch]
        btn.config(bg="#00cc00" if self.channel_states[ch] else "#004400")
        self.root.focus_set()

    def toggle_logging(self):
        if not self.running:
            self.start_logging()
        else:
            self.stop_logging()

    def start_logging(self):
        self.selected_channels = [ch for ch, state in self.channel_states.items() if state]
        if not self.selected_channels:
            messagebox.showerror("No Channels Selected", "Please select at least one analog input to log.")
            return

        self.running = True
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
        self.logged_rows = 0
        self.status_label.config(text="Not Logging", bg="red")
        self.filename_label.config(text="")
        if hasattr(self, 'log_fp'):
            self.log_fp.close()

    def get_next_log_filename(self):
        existing = [f for f in os.listdir(DATA_DIR) if f.startswith("log") and f.endswith(".csv")]
        nums = [int(f[3:-4]) for f in existing if f[3:-4].isdigit()]
        next_num = max(nums) + 1 if nums else 1
        return os.path.join(DATA_DIR, f"log{next_num}.csv")

    def send_to_thingsboard(self, voltages, timestamp):
        if not SEND_TELEMETRY:
            return
        payload = {"timestamp": timestamp}
        for i, ch in enumerate(["AIN0", "AIN1", "AIN2", "AIN3"]):
            if ch in voltages and isinstance(voltages[ch], float):
                payload[f"ain{i}"] = voltages[ch]
        try:
            requests.post(TB_URL, json=payload, timeout=2)
        except Exception as e:
            print(f"[Warning] Telemetry error: {e}")

    def logging_loop(self):
        interval = LOGGING_RATES[self.rate_var.get()]
        while self.running:
            timestamp = datetime.now().isoformat()
            voltages = self.read_voltages()
            row = [timestamp] + [voltages[ch] for ch in self.selected_channels]
            self.csv_writer.writerow(row)
            self.send_to_thingsboard(voltages, timestamp)
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
            val = voltages.get(ch, "N/A") if self.channel_states[ch] else "N/A"
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
