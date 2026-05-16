from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QPushButton, QFileDialog, QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from ui.units import km_to_mi, m_to_ft, kmh_to_mph
import csv


class StatCard(QFrame):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            StatCard {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self._label = QLabel(label)
        self._label.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._value = QLabel("—")
        self._value.setStyleSheet("color: #1a1a1a; font-size: 22px; font-weight: bold;")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value)

    def set_value(self, text):
        self._value.setText(text)


class ElevationPowerChart(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 2.8), dpi=100)
        self.fig.set_facecolor('#f8f8f8')
        self.fig.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.15)
        super().__init__(self.fig)
        self.ax_power = self.fig.add_subplot(111)
        self.ax_power.set_facecolor('#f8f8f8')
        self.ax_elev = self.ax_power.twinx()
        self._click_callback = None

    def set_click_callback(self, callback):
        self._click_callback = callback
        self.mpl_connect('button_press_event', self._on_click)

    def _on_click(self, event):
        if event.inaxes == self.ax_power and self._click_callback and event.xdata is not None:
            self._click_callback(event.xdata)

    def plot(self, segments, ftp, metric=True):
        self.ax_power.clear()
        self.ax_elev.clear()

        if not segments:
            self.draw()
            return

        dist_scale = 1.0 if metric else km_to_mi(1.0)
        elev_scale = 1.0 if metric else m_to_ft(1.0)
        dist_unit = 'km' if metric else 'mi'
        elev_unit = 'm' if metric else 'ft'

        distances = [(s['cumulative_m'] + s['distance_m'] / 2) / 1000 * dist_scale for s in segments]
        elevations = [s['elevation_m'] * elev_scale for s in segments]
        powers = [s['power_w'] for s in segments]

        # Elevation on right axis (background)
        cum_start = [s['cumulative_m'] / 1000 * dist_scale for s in segments]
        widths = [s['distance_m'] / 1000 * dist_scale for s in segments]
        self.ax_elev.bar(cum_start, elevations, width=widths, align='edge',
                         color='#e8e8e8', edgecolor='none', label=f'Elev ({elev_unit})')
        self.ax_elev.tick_params(axis='y', labelsize=8, colors='#bbb')
        self.ax_elev.spines['top'].set_visible(False)
        self.ax_elev.set_ylabel('')

        # Power on left axis (foreground)
        colors = []
        for p in powers:
            if p <= 1:
                colors.append('#90CAF9')
            elif p <= ftp * 0.75:
                colors.append('#4CAF50')
            elif p <= ftp * 0.90:
                colors.append('#FFC107')
            else:
                colors.append('#F44336')

        for i in range(len(distances) - 1):
            self.ax_power.plot(
                [distances[i], distances[i + 1]],
                [powers[i], powers[i + 1]],
                color=colors[i], linewidth=1.5,
            )
        if len(distances) == 1:
            self.ax_power.plot(distances, powers, 'o', color=colors[0])

        # Dummy artists for legend
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        legend_items = [
            Line2D([0], [0], color='#4CAF50', linewidth=2, label='Power (W)'),
            Patch(facecolor='#e8e8e8', edgecolor='none', label=f'Elevation ({elev_unit})'),
        ]
        self.ax_power.legend(handles=legend_items, loc='upper left', fontsize=8,
                             framealpha=0.8, edgecolor='#ddd', fancybox=False)

        self.ax_power.set_ylabel('')
        self.ax_power.set_xlabel(f'Distance ({dist_unit})', fontsize=9, color='#666')
        self.ax_power.tick_params(axis='y', labelsize=8, colors='#333')
        self.ax_power.tick_params(axis='x', labelsize=8, colors='#666')
        self.ax_power.spines['top'].set_visible(False)
        self.ax_power.set_zorder(self.ax_elev.get_zorder() + 1)
        self.ax_power.patch.set_visible(False)

        self.draw()


class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._metric = True
        self.setStyleSheet("background: #f2f2f2;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # --- Stats cards row ---
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self.card_time = StatCard("TOTAL TIME")
        self.card_wap = StatCard("WAP")
        self.card_er = StatCard("IF / ER")
        self.card_tls = StatCard("TLS")
        self.card_vi = StatCard("VI")
        self.card_speed = StatCard("AVG SPEED")
        for card in [self.card_time, self.card_wap, self.card_er, self.card_tls, self.card_vi, self.card_speed]:
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # --- Analysis header + solver status ---
        analysis_row = QHBoxLayout()
        analysis_label = QLabel("ANALYSIS")
        analysis_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #666; letter-spacing: 1px;")
        analysis_row.addWidget(analysis_label)
        analysis_row.addStretch()
        self.solver_label = QLabel("")
        self.solver_label.setStyleSheet("font-size: 11px; color: #888;")
        analysis_row.addWidget(self.solver_label)
        layout.addLayout(analysis_row)

        # --- Chart ---
        self.chart = ElevationPowerChart()
        self.chart.set_click_callback(self._on_chart_click)
        layout.addWidget(self.chart, stretch=3)

        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self._update_headers()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #fafafa;
                gridline-color: #eee;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
            }
            QHeaderView::section {
                background: #f5f5f5;
                border: none;
                border-bottom: 1px solid #ddd;
                padding: 6px;
                font-size: 11px;
                font-weight: bold;
                color: #555;
            }
        """)
        layout.addWidget(self.table, stretch=4)

        # --- Bottom bar ---
        btn_layout = QHBoxLayout()
        self.csv_btn = QPushButton("Export CSV")
        self.csv_btn.setStyleSheet("""
            QPushButton {
                background: #fff; border: 1px solid #ccc; border-radius: 4px;
                padding: 5px 14px; font-size: 12px; color: #444;
            }
            QPushButton:hover { background: #f0f0f0; }
            QPushButton:disabled { color: #bbb; }
        """)
        self.csv_btn.clicked.connect(self._export_csv)
        self.csv_btn.setEnabled(False)
        btn_layout.addWidget(self.csv_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._result = None
        self._ftp = 200

    def _update_headers(self):
        d = 'km' if self._metric else 'mi'
        s = 'km/h' if self._metric else 'mph'
        self.table.setHorizontalHeaderLabels([
            '#', 'Seg', f'Dist ({d})', 'Grade %', 'Surface',
            'Power (W)', f'Speed ({s})', 'Time', 'Elapsed',
        ])

    def set_metric(self, metric: bool):
        self._metric = metric
        self._update_headers()
        speed_unit = 'km/h' if metric else 'mph'
        self.card_speed._label.setText(f"AVG SPEED")
        if self._result:
            self.update_results(self._result, self._ftp)

    def _on_chart_click(self, x_val):
        if not self._result:
            return
        dist_scale = 1.0 if self._metric else km_to_mi(1.0)
        best_row = 0
        best_dist = float('inf')
        for i, seg in enumerate(self._result['segments']):
            mid = (seg['cumulative_m'] + seg['distance_m'] / 2) / 1000 * dist_scale
            d = abs(mid - x_val)
            if d < best_dist:
                best_dist = d
                best_row = i
        self.table.selectRow(best_row)

    def update_results(self, result, ftp):
        self._result = result
        self._ftp = ftp
        segments = result['segments']

        # Update stat cards
        total_s = result['total_time_s']
        total_km = sum(s['distance_m'] for s in segments) / 1000
        avg_speed_kmh = total_km / (total_s / 3600) if total_s > 0 else 0

        self.card_time.set_value(self._fmt_time(total_s))

        self.card_wap.set_value(f"{result['wap_w']:.0f}W")
        self.card_er.set_value(f"{result['intensity_factor']:.2f}")
        self.card_tls.set_value(f"{result['tss']:.0f}")
        self.card_vi.set_value(f"{result['variability_index']:.2f}")

        if self._metric:
            self.card_speed.set_value(f"{avg_speed_kmh:.1f} km/h")
        else:
            self.card_speed.set_value(f"{kmh_to_mph(avg_speed_kmh):.1f} mph")

        # Solver status
        if result['solver_success']:
            self.solver_label.setText("OPTIMIZATION COMPLETE")
            self.solver_label.setStyleSheet("font-size: 11px; color: #4CAF50; font-weight: bold;")
        else:
            self.solver_label.setText("OPTIMIZATION COMPLETE (heuristic fallback)")
            self.solver_label.setStyleSheet("font-size: 11px; color: #FF9800; font-weight: bold;")

        # Chart
        self.chart.plot(segments, ftp, self._metric)

        # Table
        dist_scale = 1.0 if self._metric else km_to_mi(1.0)
        speed_scale = 3.6 if self._metric else 3.6 * kmh_to_mph(1.0)

        self.table.setRowCount(len(segments))
        for i, seg in enumerate(segments):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(str(seg['index'] + 1)))
            self.table.setItem(i, 2, QTableWidgetItem(f"{seg['cumulative_m']/1000 * dist_scale:.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{seg['gradient']*100:.1f}"))
            self.table.setItem(i, 4, QTableWidgetItem(seg.get('surface', '')))

            power_item = QTableWidgetItem(f"{seg['power_w']:.0f}")
            p = seg['power_w']
            if p <= 1:
                power_item.setForeground(QColor('#90CAF9'))
            elif p <= ftp * 0.75:
                power_item.setForeground(QColor('#4CAF50'))
            elif p <= ftp * 0.90:
                power_item.setForeground(QColor('#FF9800'))
            else:
                power_item.setForeground(QColor('#F44336'))
            font = power_item.font()
            font.setBold(True)
            power_item.setFont(font)
            self.table.setItem(i, 5, power_item)

            self.table.setItem(i, 6, QTableWidgetItem(f"{seg['speed_ms'] * speed_scale:.1f}"))
            self.table.setItem(i, 7, QTableWidgetItem(self._fmt_time(seg['time_s'])))
            self.table.setItem(i, 8, QTableWidgetItem(self._fmt_time(seg['elapsed_s'])))

        self.csv_btn.setEnabled(True)

    def _fmt_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h {m:02d}m {s:02d}s"
        return f"{m}m {s:02d}s"

    def _export_csv(self):
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "pacing_plan.csv", "CSV Files (*.csv)")
        if not path:
            return

        dist_scale = 1.0 if self._metric else km_to_mi(1.0)
        speed_scale = 3.6 if self._metric else 3.6 * kmh_to_mph(1.0)
        d = 'km' if self._metric else 'mi'
        s = 'kmh' if self._metric else 'mph'

        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['#', f'Distance_{d}', 'Gradient_%', 'Surface', 'Power_W', f'Speed_{s}', 'Time_s', 'Elapsed_s'])
            for seg in self._result['segments']:
                writer.writerow([
                    seg['index'] + 1,
                    f"{seg['cumulative_m']/1000 * dist_scale:.2f}",
                    f"{seg['gradient']*100:.1f}",
                    seg.get('surface', ''),
                    f"{seg['power_w']:.0f}",
                    f"{seg['speed_ms'] * speed_scale:.1f}",
                    f"{seg['time_s']:.1f}",
                    f"{seg['elapsed_s']:.1f}",
                ])
