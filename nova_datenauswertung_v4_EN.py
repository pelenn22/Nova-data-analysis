import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog, ttk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import CheckButtons
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import os
import re

class DataPlotterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Data Importer and Plotter")
        self.cycle_data = []
        self.energy_data = []
        self.energy_dens_data = []
        self.voltage_data = []
        self.figures = []
        self.canvases = []
        self.root.protocol("WM_DELETE_WINDOW", sys.exit)
        self.show_efficiency = tk.BooleanVar(value=False)
        self.show_avg_voltage = tk.BooleanVar(value=False)
        self.charge_first = tk.BooleanVar(value=True)

        frame_controls = tk.Frame(root)
        frame_controls.pack(side=tk.TOP, fill=tk.X)

        self.file_listbox = tk.Listbox(frame_controls, selectmode=tk.EXTENDED, exportselection=False, height=10,
                                       width=100)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        self.file_listbox.bind('<<ListboxSelect>>', self.plot_selected_files)

        scrollbar = tk.Scrollbar(frame_controls, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        self.import_button = tk.Button(frame_controls, text="Import files", command=self.load_files)
        self.import_button.pack(pady=5)

        # self.sort_button = tk.Button(frame_controls, text="Sort files", command=self.sort_files_by_number_in_brackets)
        # self.sort_button.pack()
        self.checkbox_charge = tk.Checkbutton(frame_controls, text="Charge first", variable=self.charge_first,
                                              command=self.sort_files_by_number_and_trend)
        self.checkbox_charge.pack()
        self.current_label = tk.Label(frame_controls, text="Current (A)")
        self.current_label.pack()

        self.current_entry = tk.Entry(frame_controls)
        self.current_entry.insert(0, "0.02")
        self.current_entry.pack()
        self.current_entry.bind("<KeyRelease>", self.plot_selected_files)

        self.volume_label = tk.Label(frame_controls, text="Volume (L)")
        self.volume_label.pack()

        self.volume_entry = tk.Entry(frame_controls)
        self.volume_entry.insert(0, "0.02")
        self.volume_entry.pack()
        self.volume_entry.bind("<KeyRelease>", self.plot_selected_files)

        self.show_energy_density = tk.BooleanVar(value=False)
        self.checkbtn = tk.Checkbutton(frame_controls, text="Show energy density", variable=self.show_energy_density,
                                       command=self.plot_selected_files)
        self.checkbtn.pack()

        self.checkbtn_eff = tk.Checkbutton(frame_controls, text="Show Coulombic efficiency",
                                           variable=self.show_efficiency, command=self.toggle_efficiency)
        self.checkbtn_eff.pack()

        self.checkbtn_vol = tk.Checkbutton(frame_controls, text="Show average voltage", variable=self.show_avg_voltage,
                                           command=self.toggle_avg_voltage)
        self.checkbtn_vol.pack()

        self.select_all_button = tk.Button(frame_controls, text="Select all", command=self.toggle_select_all)
        self.select_all_button.pack(pady=5)

        self.export_button = tk.Button(frame_controls, text="Export", command=self.export_data)
        self.export_button.pack(pady=5)

        frame_plots = tk.Frame(root)
        frame_plots.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        for _ in range(3):
            fig, ax = plt.subplots(figsize=(5, 5))
            canvas = FigureCanvasTkAgg(fig, master=frame_plots)
            canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.figures.append(fig)
            self.canvases.append(canvas)

        self.ax4 = self.figures[1].axes[0].twinx()  # twin axis is created only once

        self.files = {}

    def toggle_efficiency(self):
        if self.show_efficiency.get():
            self.show_avg_voltage.set(False)
        self.plot_selected_files()

    def toggle_avg_voltage(self):
        if self.show_avg_voltage.get():
            self.show_efficiency.set(False)
        self.plot_selected_files()

    def load_files(self):
        filenames = filedialog.askopenfilenames(filetypes=[("All files", "*.*")])

        self.file_listbox.delete(0, tk.END)
        self.files.clear()

        max_filename_length = max([len(file) for file in filenames], default=50)
        self.file_listbox.config(width=max_filename_length + 10)

        for file in filenames:
            try:
                with open(file, "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()

                header_index = None
                for i, line in enumerate(lines):
                    if "Corrected time" in line and "Potential" in line:
                        header_index = i
                        break

                df = pd.read_csv(file, sep="\t", encoding="utf-8-sig", skiprows=header_index)
                # File is empty or contains no data rows
                if df.empty or len(df) < 2:
                    messagebox.showerror("Empty file",
                                         f"The file is empty or unusable and will be skipped:\n{file}")
                    continue

                # Optional: Column check
                if 'Time (s)' not in df.columns and 'Corrected time (s)' not in df.columns:
                    messagebox.showerror("Invalid file", f"The file does not contain a valid time column:\n{file}")
                    continue

                self.files[file] = df
                self.file_listbox.insert(tk.END, file)
                if 'Corrected time (s)' not in df.columns and 'Time (s)' in df.columns:
                    # Calculate time differences
                    time_diffs = df['Time (s)'].diff().fillna(0)

                    # Cumulative sum of differences yields "Corrected time"
                    df['Corrected time (s)'] = time_diffs.cumsum()
            except Exception as e:
                messagebox.showerror("Error", f"Error loading file:\n{file}\n\n{e}")

        self.sort_files_by_number_and_trend()

    def sort_files_by_number_and_trend(self):
        if not self.files:
            return

        def extract_number(filename):
            match = re.search(r"\((\d+)\)", os.path.basename(filename))
            return int(match.group(1)) if match else float('0')

        file_infos = []  # List with: (filename, cycle_number, trend)

        for file, df in self.files.items():
            number = extract_number(file)
            if 'WE(1).Potential (V)' in df.columns:
                trend = df['WE(1).Potential (V)'].diff().mean()
            else:
                trend = 0  # If voltage is missing, neutral trend

            file_infos.append((file, number, trend))

        def sort_key(item):
            file, number, trend = item
            trend_sort = 0 if (trend > 0) == self.charge_first.get() else 1
            return (number, trend_sort)

        sorted_files = sorted(file_infos, key=sort_key)

        self.file_listbox.delete(0, tk.END)
        for file, _, _ in sorted_files:
            self.file_listbox.insert(tk.END, file)

    def toggle_select_all(self):
        self.file_listbox.select_set(0, tk.END)
        self.plot_selected_files(None)

    def plot_selected_files(self, event=None):
        selected_indices = self.file_listbox.curselection()
        selected_files = [self.file_listbox.get(i) for i in selected_indices]

        combined_df = pd.DataFrame(columns=['Time (s)', 'WE(1).Potential (V)'])
        cumulative_time = 0

        self.cycle_data = []
        self.energy_data = []
        self.energy_dens_data = []
        self.voltage_data = []

        # Access the axes of the 3 plots
        ax1 = self.figures[0].axes[0]  # First plot
        ax2 = self.figures[1].axes[0]  # Second plot
        ax3 = self.figures[2].axes[0]  # Third plot

        # Right y-axis in the second plot
        ax4 = self.ax4

        # Clear plots
        ax1.clear()
        ax2.clear()
        ax3.clear()
        ax4.clear()
        ax4.cla()

        cycle_number = 1
        last_cycle_type = None

        for file_path in selected_files:
            df = self.files.get(file_path, None)

            if df is not None and 'Corrected time (s)' in df.columns and 'WE(1).Potential (V)' in df.columns:
                df['Time (s)'] = df['Corrected time (s)'] + cumulative_time
                cumulative_time = df['Time (s)'].iloc[-1]
                if 'Time (s)' in df.columns and 'WE(1).Potential (V)' in df.columns:
                    subset = df[['Time (s)', 'WE(1).Potential (V)']].dropna(how='all')
                    if not subset.empty:
                        combined_df = pd.concat([combined_df, subset], ignore_index=True)

                max_time = df['Corrected time (s)'].max()
                if 'WE(1).Current (A)' in df.columns:
                    current = float(df['WE(1).Current (A)'].mean())
                    std_dev = float(df['WE(1).Current (A)'].std())
                    self.current_entry.config(state=tk.NORMAL)  # ensure it is writable
                    self.current_entry.delete(0, tk.END)
                    self.current_entry.insert(0, f"{current:.8f} ± {std_dev:.1e}")
                    self.current_entry.config(state=tk.DISABLED)
                else:
                    current = float(self.current_entry.get())

                capacity_mAh = (max_time * abs(current)) * 1000 / 3600
                avg_voltage = df['WE(1).Potential (V)'].mean()

                power_values = df['WE(1).Potential (V)'] * current  # or use current column
                energy_J = abs(np.trapezoid(power_values, df['Corrected time (s)']))
                energy_mWh = energy_J / 3.6

                vol = float(self.volume_entry.get())
                if vol > 0:
                    energy_density_WhL = energy_mWh / (1000 * vol)
                else:
                    energy_density_WhL = 0

                trend = df['WE(1).Potential (V)'].diff().mean()
                cycle_type = 'Charge' if trend > 0 else 'Discharge'

                if last_cycle_type == 'Discharge' and cycle_type == 'Charge':
                    cycle_number += 1
                last_cycle_type = cycle_type

                self.cycle_data.append((cycle_number, capacity_mAh, cycle_type))
                self.voltage_data.append((cycle_number, avg_voltage, cycle_type))
                self.energy_data.append((cycle_number, energy_mWh, cycle_type))
                self.energy_dens_data.append((cycle_number, energy_density_WhL, cycle_type))

        if not combined_df.empty:
            ax1.plot(combined_df['Time (s)'], combined_df['WE(1).Potential (V)'], label='Merged data')

            ax1.set_xlabel('Time (s)')
            ax1.set_ylabel('WE(1).Potential (V)')
            ax1.set_title('Data plot')
            ax1.legend()
            self.figures[0].tight_layout()
            self.canvases[0].draw()

        for cycle, capacity, label in self.cycle_data:
            color = 'blue' if label == 'Charge' else 'red'
            ax2.scatter(cycle, capacity, color=color,
                        label=label if label not in ax2.get_legend_handles_labels()[1] else "_nolegend_")

        ax2.set_xlabel('Cycle number')
        ax2.set_ylabel('Capacity (mAh)')
        ax2.set_title('Capacity per cycle')
        ax2.legend(loc='best')
        ax2.set_ylim(bottom=0)

        if self.show_efficiency.get():  # Only if checkbox is active
            # Calculate efficiency
            efficiency_x = []
            efficiency_y = []

            # Assumption: data comes in pairs – Charge followed by Discharge
            i = 0
            while i < len(self.cycle_data) - 1:
                cycle1, cap1, label1 = self.cycle_data[i]
                cycle2, cap2, label2 = self.cycle_data[i + 1]

                # Check if correctly paired
                if label1 == 'Charge' and label2 == 'Discharge' and cycle1 == cycle2:
                    charge_cap = cap1
                    discharge_cap = cap2
                    if charge_cap != 0:
                        efficiency = (discharge_cap / charge_cap) * 100
                        efficiency_x.append(cycle1)
                        efficiency_y.append(efficiency)
                    i += 2
                else:
                    i += 1  # If not a correct pair, continue
            ax4.scatter(efficiency_x, efficiency_y, color='green', marker='o', label='Coulombic efficiency')
            ax4.set_ylabel("Coulombic efficiency (%)", color='green', loc='center')
            ax4.yaxis.set_label_position("right")
            ax4.tick_params(axis='y', labelcolor='green')
            ax4.legend(loc='best')

        elif self.show_avg_voltage.get():
            for cycle, voltage, label in self.voltage_data:
                color1 = 'blue' if label == 'Charge' else 'red'
                ax4.scatter(cycle, voltage, color=color1, marker='x',
                            label=label if label not in ax4.get_legend_handles_labels()[1] else "_nolegend_")

            ax4.set_ylabel("Average voltage (V)", color='purple', loc='center')
            ax4.yaxis.set_label_position("right")
            ax4.tick_params(axis='y', labelcolor='purple')
            ax4.legend(loc='best')
        else:
            ax4.set_yticks([])  # leave axis empty
            ax4.set_ylabel("")  # no label

        self.figures[1].tight_layout()
        self.canvases[1].draw()

        if self.show_energy_density.get():
            for cycle, energydens, label in self.energy_dens_data:
                color = 'blue' if label == 'Charge' else 'red'
                ax3.scatter(cycle, energydens, color=color,
                            label=label if label not in ax3.get_legend_handles_labels()[1] else "_nolegend_")
                ax3.set_xlabel('Cycle number')
                ax3.set_ylabel('Energy density (Wh/L)')
                ax3.set_title('Energy density per cycle')
        else:
            for cycle, energy, label in self.energy_data:
                color = 'blue' if label == 'Charge' else 'red'
                ax3.scatter(cycle, energy, color=color,
                            label=label if label not in ax3.get_legend_handles_labels()[1] else "_nolegend_")
                ax3.set_xlabel('Cycle number')
                ax3.set_ylabel('Energy (mWh)')
                ax3.set_title('Energy per cycle')

        ax3.legend()
        self.figures[2].tight_layout()
        self.canvases[2].draw()

    def export_data(self):
        save_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not save_path:
            return

        with open(save_path, 'w') as f:
            f.write("Cycle number\tCharge capacity (mAh)\tDischarge capacity (mAh)\t"
                    "Coulombic efficiency (%)\tCharge energy (mWh)\tDischarge energy (mWh)\t"
                    "Charge voltage (V)\tDischarge voltage (V)\t"
                    "Charge energy density (Wh/L)\tDischarge energy density (Wh/L)\n")

            cycle_data = {}
            for cycle, capacity, cycle_type in self.cycle_data:
                if cycle not in cycle_data:
                    cycle_data[cycle] = {
                        'Charge': None,
                        'Discharge': None,
                        'ChargeEnergy': None,
                        'DischargeEnergy': None,
                        'ChargeVoltage': None,
                        'DischargeVoltage': None,
                        'ChargeEnergyDensity': None,
                        'DischargeEnergyDensity': None
                    }
                cycle_data[cycle][cycle_type] = capacity

            for cycle, energy, cycle_type in self.energy_data:
                if cycle in cycle_data:
                    key = 'ChargeEnergy' if cycle_type == 'Charge' else 'DischargeEnergy'
                    cycle_data[cycle][key] = energy

            for cycle, voltage, cycle_type in self.voltage_data:
                if cycle in cycle_data:
                    key = 'ChargeVoltage' if cycle_type == 'Charge' else 'DischargeVoltage'
                    cycle_data[cycle][key] = voltage

            for cycle, dens, cycle_type in self.energy_dens_data:
                if cycle in cycle_data:
                    key = 'ChargeEnergyDensity' if cycle_type == 'Charge' else 'DischargeEnergyDensity'
                    cycle_data[cycle][key] = dens

            for cycle, data in sorted(cycle_data.items()):
                charge_cap = data['Charge'] or 0
                discharge_cap = data['Discharge'] or 0
                ratio = (discharge_cap / charge_cap * 100) if charge_cap > 0 else 0
                charge_energy = data['ChargeEnergy'] or 0
                discharge_energy = data['DischargeEnergy'] or 0
                charge_v = data['ChargeVoltage'] or 0
                discharge_v = data['DischargeVoltage'] or 0
                charge_dens = data['ChargeEnergyDensity'] or 0
                discharge_dens = data['DischargeEnergyDensity'] or 0

                f.write(f"{cycle}\t{charge_cap:.5f}\t{discharge_cap:.5f}\t{ratio:.2f}\t"
                        f"{charge_energy:.5f}\t{discharge_energy:.5f}\t"
                        f"{charge_v:.5f}\t{discharge_v:.5f}\t"
                        f"{charge_dens:.5f}\t{discharge_dens:.5f}\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = DataPlotterApp(root)
    root.mainloop()