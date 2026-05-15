import json
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QToolBar,
    QPushButton, QFileDialog, QMessageBox, QProgressDialog, QSplitter,
    QApplication, QStatusBar, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction

from ui.inputs_panel import InputsPanel
from ui.results_panel import ResultsPanel
from ui.cheat_sheet import open_cheat_sheet
from core.gpx_parser import parse_gpx, build_segments, assign_surface
from core.optimizer import optimize_pacing
from core.fit_export import export_power_course, export_zwift_zwo

CONFIG_DIR = Path.home() / '.cyclingpacer'
CONFIG_PATH = CONFIG_DIR / 'config.json'


class OptimizerWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, segments, rider, env, ftp_w, target_if, min_power, max_power):
        super().__init__()
        self.segments = segments
        self.rider = rider
        self.env = env
        self.ftp_w = ftp_w
        self.target_if = target_if
        self.min_power = min_power
        self.max_power = max_power

    def run(self):
        try:
            result = optimize_pacing(
                self.segments, self.rider, self.env,
                self.ftp_w, self.target_if, self.min_power, self.max_power,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CyclingPacer")
        self.setMinimumSize(1200, 700)

        self._gpx_path = None
        self._segments = None
        self._result = None
        self._worker = None

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._load_config()

    def _build_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.open_action = QAction("Open GPX", self)
        self.open_action.triggered.connect(self._open_gpx)
        toolbar.addAction(self.open_action)

        self.run_action = QAction("Run", self)
        self.run_action.triggered.connect(self._run_optimizer)
        self.run_action.setEnabled(False)
        toolbar.addAction(self.run_action)

        toolbar.addSeparator()

        self.export_fit_action = QAction("Export FIT", self)
        self.export_fit_action.triggered.connect(self._export_fit)
        self.export_fit_action.setEnabled(False)
        toolbar.addAction(self.export_fit_action)

        self.export_zwo_action = QAction("Export ZWO", self)
        self.export_zwo_action.triggered.connect(self._export_zwo)
        self.export_zwo_action.setEnabled(False)
        toolbar.addAction(self.export_zwo_action)

        self.print_action = QAction("Print Cheat Sheet", self)
        self.print_action.triggered.connect(self._print_cheat_sheet)
        self.print_action.setEnabled(False)
        toolbar.addAction(self.print_action)

        toolbar.addSeparator()

        self.units_combo = QComboBox()
        self.units_combo.addItems(["Metric", "Imperial"])
        self.units_combo.currentTextChanged.connect(self._on_units_changed)
        toolbar.addWidget(self.units_combo)

    def _build_central(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.inputs_panel = InputsPanel()
        self.inputs_panel.run_requested.connect(self._run_optimizer)
        self.inputs_panel.setMinimumWidth(280)
        self.inputs_panel.setMaximumWidth(400)
        splitter.addWidget(self.inputs_panel)

        self.results_panel = ResultsPanel()
        splitter.addWidget(self.results_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    def _build_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Open a GPX file to get started")

    def _open_gpx(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open GPX File", "", "GPX Files (*.gpx);;All Files (*)")
        if not path:
            return

        try:
            points = parse_gpx(path)
            params = self.inputs_panel.get_params()
            self._segments = build_segments(points, params['segment_length_m'])
            self._segments = assign_surface(self._segments)
            self._gpx_path = path

            filename = os.path.basename(path)
            self.statusbar.showMessage(f"Loaded {filename}: {len(self._segments)} segments, {sum(s['distance_m'] for s in self._segments)/1000:.1f} km")
            self.run_action.setEnabled(True)

            if self._segments and self._segments[0].get('elevation_m', 0) > 0:
                self.inputs_panel.altitude_spin.setValue(self._segments[0]['elevation_m'])

        except Exception as e:
            QMessageBox.critical(self, "GPX Error", f"Failed to parse GPX file:\n{str(e)}")

    def _run_optimizer(self):
        if not self._segments:
            QMessageBox.warning(self, "No Course", "Please open a GPX file first.")
            return

        params = self.inputs_panel.get_params()

        if params['default_surface']:
            from core.physics import load_surfaces
            surfaces = load_surfaces()
            crr = surfaces.get(params['default_surface'], 0.006)
            for seg in self._segments:
                seg['surface'] = params['default_surface']
                seg['crr'] = crr

        self.run_action.setEnabled(False)
        self.inputs_panel.run_btn.setEnabled(False)
        self.statusbar.showMessage("Optimizing...")

        self._worker = OptimizerWorker(
            self._segments, params['rider'], params['env'],
            params['ftp_w'], params['target_if'],
            params['min_power_w'], params['max_power_w'],
        )
        self._worker.finished.connect(self._on_optimizer_done)
        self._worker.error.connect(self._on_optimizer_error)
        self._worker.start()

    def _on_optimizer_done(self, result):
        self._result = result
        params = self.inputs_panel.get_params()
        self.results_panel.update_results(result, params['ftp_w'])

        self.run_action.setEnabled(True)
        self.inputs_panel.run_btn.setEnabled(True)
        self.export_fit_action.setEnabled(True)
        self.export_zwo_action.setEnabled(True)
        self.print_action.setEnabled(True)

        status = "Optimization complete"
        if not result['solver_success']:
            status += " (heuristic fallback)"
        self.statusbar.showMessage(status)
        self._save_config()

    def _on_optimizer_error(self, msg):
        self.run_action.setEnabled(True)
        self.inputs_panel.run_btn.setEnabled(True)
        self.statusbar.showMessage("Optimization failed")
        QMessageBox.critical(self, "Optimizer Error", f"Optimization failed:\n{msg}")

    def _export_fit(self):
        if not self._result:
            return
        name = os.path.splitext(os.path.basename(self._gpx_path or 'course'))[0]
        path, _ = QFileDialog.getSaveFileName(self, "Export FIT", f"{name}.fit", "FIT Files (*.fit)")
        if path:
            try:
                export_power_course(self._result, name, path)
                self.statusbar.showMessage(f"FIT exported to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _export_zwo(self):
        if not self._result:
            return
        name = os.path.splitext(os.path.basename(self._gpx_path or 'course'))[0]
        path, _ = QFileDialog.getSaveFileName(self, "Export ZWO", f"{name}.zwo", "ZWO Files (*.zwo)")
        if path:
            try:
                export_zwift_zwo(self._result, path)
                self.statusbar.showMessage(f"ZWO exported to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _on_units_changed(self, text):
        metric = text == "Metric"
        self.inputs_panel.set_units(metric)
        self.results_panel.set_metric(metric)

    def _print_cheat_sheet(self):
        if not self._result:
            return
        params = self.inputs_panel.get_params()
        params['temperature_c'] = self.inputs_panel.temp_spin.value()
        name = os.path.splitext(os.path.basename(self._gpx_path or 'Course'))[0]
        open_cheat_sheet(self._result, params, name)

    def _save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        state = self.inputs_panel.get_state()
        state['units'] = 'metric' if self.inputs_panel.is_metric else 'imperial'
        with open(CONFIG_PATH, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH) as f:
                    state = json.load(f)
                if state.get('units') == 'imperial':
                    self.units_combo.setCurrentText("Imperial")
                self.inputs_panel.set_state(state)
            except Exception:
                pass

    def closeEvent(self, event):
        self._save_config()
        super().closeEvent(event)
