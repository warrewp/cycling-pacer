from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QPushButton, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from ui.units import km_to_mi, m_to_ft, kmh_to_mph
import csv


class ElevationPowerChart(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 3), dpi=100)
        self.fig.set_tight_layout(True)
        super().__init__(self.fig)
        self.ax_elev = self.fig.add_subplot(111)
        self.ax_power = self.ax_elev.twinx()
        self._click_callback = None

    def set_click_callback(self, callback):
        self._click_callback = callback
        self.mpl_connect('button_press_event', self._on_click)

    def _on_click(self, event):
        if event.inaxes == self.ax_elev and self._click_callback and event.xdata is not None:
            self._click_callback(event.xdata)

    def plot(self, segments, ftp, metric=True):
        self.ax_elev.clear()
        self.ax_power.clear()

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

        cum_start = [s['cumulative_m'] / 1000 * dist_scale for s in segments]
        widths = [s['distance_m'] / 1000 * dist_scale for s in segments]
        self.ax_elev.bar(cum_start, elevations, width=widths, align='edge',
                         color='#d0d0d0', edgecolor='none', alpha=0.7)
        self.ax_elev.set_xlabel(f'Distance ({dist_unit})')
        self.ax_elev.set_ylabel(f'Elevation ({elev_unit})', color='gray')
        self.ax_elev.tick_params(axis='y', labelcolor='gray')

        colors = []
        for p in powers:
            if p <= ftp * 0.75:
                colors.append('#2ecc71')
            elif p <= ftp * 0.90:
                colors.append('#f39c12')
            else:
                colors.append('#e74c3c')

        for i in range(len(distances) - 1):
            self.ax_power.plot(
                [distances[i], distances[i + 1]],
                [powers[i], powers[i + 1]],
                color=colors[i], linewidth=2,
            )
        if len(distances) == 1:
            self.ax_power.plot(distances, powers, 'o', color=colors[0])

        self.ax_power.set_ylabel('Power (W)', color='#2c3e50')
        self.ax_power.tick_params(axis='y', labelcolor='#2c3e50')

        self.draw()


class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._metric = True
        layout = QVBoxLayout(self)

        self.chart = ElevationPowerChart()
        self.chart.set_click_callback(self._on_chart_click)
        layout.addWidget(self.chart, stretch=3)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self._update_headers()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=3)

        btn_layout = QHBoxLayout()
        self.csv_btn = QPushButton("Export CSV")
        self.csv_btn.clicked.connect(self._export_csv)
        self.csv_btn.setEnabled(False)
        btn_layout.addWidget(self.csv_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 13px; padding: 6px; background: #f7f7f7; border-radius: 4px;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stats_label)

        self._result = None
        self._ftp = 200

    def _update_headers(self):
        d = 'km' if self._metric else 'mi'
        s = 'km/h' if self._metric else 'mph'
        self.table.setHorizontalHeaderLabels([
            '#', f'Distance ({d})', 'Gradient %', 'Surface',
            'Target Power (W)', f'Speed ({s})', 'Segment Time', 'Elapsed',
        ])

    def set_metric(self, metric: bool):
        self._metric = metric
        self._update_headers()
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

        self.chart.plot(segments, ftp, self._metric)

        dist_scale = 1.0 if self._metric else km_to_mi(1.0)
        speed_scale = 3.6 if self._metric else 3.6 * kmh_to_mph(1.0)

        self.table.setRowCount(len(segments))
        for i, seg in enumerate(segments):
            self.table.setItem(i, 0, QTableWidgetItem(str(seg['index'] + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(f"{seg['cumulative_m']/1000 * dist_scale:.2f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{seg['gradient']*100:.1f}"))
            self.table.setItem(i, 3, QTableWidgetItem(seg.get('surface', '')))

            power_item = QTableWidgetItem(f"{seg['power_w']:.0f}")
            p = seg['power_w']
            if p <= ftp * 0.75:
                power_item.setBackground(QColor('#d5f5e3'))
            elif p <= ftp * 0.90:
                power_item.setBackground(QColor('#fdebd0'))
            else:
                power_item.setBackground(QColor('#fadbd8'))
            self.table.setItem(i, 4, power_item)

            self.table.setItem(i, 5, QTableWidgetItem(f"{seg['speed_ms'] * speed_scale:.1f}"))
            self.table.setItem(i, 6, QTableWidgetItem(self._fmt_time(seg['time_s'])))
            self.table.setItem(i, 7, QTableWidgetItem(self._fmt_time(seg['elapsed_s'])))

        total_s = result['total_time_s']
        total_km = sum(s['distance_m'] for s in segments) / 1000
        total_display = total_km * dist_scale
        avg_speed_kmh = total_km / (total_s / 3600) if total_s > 0 else 0
        avg_speed_display = avg_speed_kmh if self._metric else kmh_to_mph(avg_speed_kmh)
        speed_unit = 'km/h' if self._metric else 'mph'

        self.stats_label.setText(
            f"Total Time: {self._fmt_time(total_s)}  |  "
            f"WAP: {result['wap_w']:.0f}W  |  "
            f"ER: {result['intensity_factor']:.2f}  |  "
            f"TLS: {result['tss']:.0f}  |  "
            f"VI: {result['variability_index']:.2f}  |  "
            f"Avg Speed: {avg_speed_display:.1f} {speed_unit}"
        )

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
