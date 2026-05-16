import json
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QToolBar,
    QPushButton, QFileDialog, QMessageBox, QSplitter,
    QApplication, QStatusBar, QFrame, QTabWidget, QInputDialog,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction

from ui.inputs_panel import InputsPanel
from ui.results_panel import ResultsPanel
from ui.saved_plans_panel import SavedPlansPanel, save_plan
from ui.cheat_sheet import open_cheat_sheet
from core.gpx_parser import parse_gpx, build_segments, assign_surface
from core.optimizer import optimize_pacing
from core.fit_export import export_power_course, export_zwift_zwo

CONFIG_DIR = Path.home() / '.cyclingpacer'
CONFIG_PATH = CONFIG_DIR / 'config.json'

TOOLBAR_BTN = """
    QPushButton {
        background: transparent; border: none; padding: 4px 10px;
        font-size: 12px; color: #555;
    }
    QPushButton:hover { color: #222; background: #e8e8e8; border-radius: 4px; }
    QPushButton:disabled { color: #bbb; }
"""

TOGGLE_ACTIVE = """
    QPushButton {
        background: #4CAF50; color: white; border: none;
        padding: 3px 10px; font-size: 11px; font-weight: bold; border-radius: 3px;
    }
"""
TOGGLE_INACTIVE = """
    QPushButton {
        background: #e0e0e0; color: #666; border: none;
        padding: 3px 10px; font-size: 11px; border-radius: 3px;
    }
    QPushButton:hover { background: #d0d0d0; }
"""


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
        self.setStyleSheet("QMainWindow { background: #f2f2f2; }")

        self._gpx_path = None
        self._trackpoints = None
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
        toolbar.setStyleSheet("""
            QToolBar {
                background: #fafafa;
                border-bottom: 1px solid #ddd;
                spacing: 2px;
                padding: 2px 8px;
            }
        """)
        self.addToolBar(toolbar)

        self.open_btn = QPushButton("Open GPX")
        self.open_btn.setStyleSheet(TOOLBAR_BTN)
        self.open_btn.clicked.connect(self._open_gpx)
        toolbar.addWidget(self.open_btn)

        self.run_btn_toolbar = QPushButton("Run")
        self.run_btn_toolbar.setStyleSheet(TOOLBAR_BTN)
        self.run_btn_toolbar.clicked.connect(self._run_optimizer)
        self.run_btn_toolbar.setEnabled(False)
        toolbar.addWidget(self.run_btn_toolbar)

        self.save_btn = QPushButton("Save Plan")
        self.save_btn.setStyleSheet(TOOLBAR_BTN)
        self.save_btn.clicked.connect(self._save_plan)
        self.save_btn.setEnabled(False)
        toolbar.addWidget(self.save_btn)

        toolbar.addSeparator()

        self.export_fit_btn = QPushButton("Export FIT")
        self.export_fit_btn.setStyleSheet(TOOLBAR_BTN)
        self.export_fit_btn.clicked.connect(self._export_fit)
        self.export_fit_btn.setEnabled(False)
        toolbar.addWidget(self.export_fit_btn)

        self.export_zwo_btn = QPushButton("Export ZWO")
        self.export_zwo_btn.setStyleSheet(TOOLBAR_BTN)
        self.export_zwo_btn.clicked.connect(self._export_zwo)
        self.export_zwo_btn.setEnabled(False)
        toolbar.addWidget(self.export_zwo_btn)

        self.print_btn = QPushButton("Print Cheat Sheet")
        self.print_btn.setStyleSheet(TOOLBAR_BTN)
        self.print_btn.clicked.connect(self._print_cheat_sheet)
        self.print_btn.setEnabled(False)
        toolbar.addWidget(self.print_btn)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Segmented unit toggle
        toggle_frame = QFrame()
        toggle_layout = QHBoxLayout(toggle_frame)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(1)

        self.metric_btn = QPushButton("Metric")
        self.imperial_btn = QPushButton("Imperial")
        self.metric_btn.clicked.connect(lambda: self._set_units(True))
        self.imperial_btn.clicked.connect(lambda: self._set_units(False))
        self._update_toggle_style(True)

        toggle_layout.addWidget(self.metric_btn)
        toggle_layout.addWidget(self.imperial_btn)
        toolbar.addWidget(toggle_frame)

    def _update_toggle_style(self, metric):
        self.metric_btn.setStyleSheet(TOGGLE_ACTIVE if metric else TOGGLE_INACTIVE)
        self.imperial_btn.setStyleSheet(TOGGLE_INACTIVE if metric else TOGGLE_ACTIVE)

    def _set_units(self, metric):
        self._update_toggle_style(metric)
        self.inputs_panel.set_units(metric)
        self.results_panel.set_metric(metric)

    def _build_central(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.inputs_panel = InputsPanel()
        self.inputs_panel.run_requested.connect(self._run_optimizer)
        self.inputs_panel.setMinimumWidth(280)
        self.inputs_panel.setMaximumWidth(380)
        splitter.addWidget(self.inputs_panel)

        # Tab widget for Pacer / Saved Plans
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #f2f2f2;
            }
            QTabBar::tab {
                background: #e8e8e8;
                border: none;
                padding: 8px 24px;
                font-size: 12px;
                font-weight: bold;
                color: #666;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #f2f2f2;
                color: #333;
            }
            QTabBar::tab:hover:!selected {
                background: #ddd;
            }
        """)

        self.results_panel = ResultsPanel()
        self.tabs.addTab(self.results_panel, "Pacer")

        self.saved_plans_panel = SavedPlansPanel()
        self.saved_plans_panel.plan_loaded.connect(self._on_plan_loaded)
        self.tabs.addTab(self.saved_plans_panel, "Saved Plans")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        splitter.addWidget(self.tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    def _on_tab_changed(self, index):
        if index == 1:
            self.saved_plans_panel.refresh()

    def _build_statusbar(self):
        self.statusbar = QStatusBar()
        self.statusbar.setStyleSheet("QStatusBar { background: #fafafa; border-top: 1px solid #ddd; color: #888; font-size: 11px; }")
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Open a GPX file to get started")

    def _open_gpx(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open GPX File", "", "GPX Files (*.gpx);;All Files (*)")
        if not path:
            return

        try:
            self._trackpoints = parse_gpx(path)
            self._gpx_path = path
            self._rebuild_segments()
            self.run_btn_toolbar.setEnabled(True)
            self.tabs.setCurrentIndex(0)

            if self._segments and self._segments[0].get('elevation_m', 0) > 0:
                self.inputs_panel.altitude_spin.setValue(self._segments[0]['elevation_m'])

        except Exception as e:
            QMessageBox.critical(self, "GPX Error", f"Failed to parse GPX file:\n{str(e)}")

    def _rebuild_segments(self):
        if not self._trackpoints:
            return
        params = self.inputs_panel.get_params()
        self._segments = build_segments(self._trackpoints, params['segment_length_m'])
        self._segments = assign_surface(self._segments)

        filename = os.path.basename(self._gpx_path)
        total_km = sum(s['distance_m'] for s in self._segments) / 1000
        self.statusbar.showMessage(f"Loaded {filename}: {len(self._segments)} segments, {total_km:.1f} km")

    def _run_optimizer(self):
        if not self._trackpoints:
            QMessageBox.warning(self, "No Course", "Please open a GPX file first.")
            return

        self._rebuild_segments()
        params = self.inputs_panel.get_params()

        if params['default_surface']:
            from core.physics import load_surfaces
            surfaces = load_surfaces()
            crr = surfaces.get(params['default_surface'], 0.006)
            for seg in self._segments:
                seg['surface'] = params['default_surface']
                seg['crr'] = crr

        self.run_btn_toolbar.setEnabled(False)
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

        self.run_btn_toolbar.setEnabled(True)
        self.inputs_panel.run_btn.setEnabled(True)
        self.export_fit_btn.setEnabled(True)
        self.export_zwo_btn.setEnabled(True)
        self.print_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        self.statusbar.showMessage("Optimization complete")
        self._save_config()

    def _on_optimizer_error(self, msg):
        self.run_btn_toolbar.setEnabled(True)
        self.inputs_panel.run_btn.setEnabled(True)
        self.statusbar.showMessage("Optimization failed")
        QMessageBox.critical(self, "Optimizer Error", f"Optimization failed:\n{msg}")

    def _save_plan(self):
        if not self._result:
            return
        default_name = os.path.splitext(os.path.basename(self._gpx_path or 'Plan'))[0]
        name, ok = QInputDialog.getText(self, "Save Pacing Plan", "Plan name:", text=default_name)
        if not ok or not name.strip():
            return

        params = self.inputs_panel.get_params()
        filepath = save_plan(name.strip(), self._result, params, self._gpx_path or '')
        self.statusbar.showMessage(f"Plan saved: {name.strip()}")

    def _on_plan_loaded(self, plan):
        result = plan.get('result', {})
        params = plan.get('params', {})
        ftp = params.get('ftp_w', 200)

        self._result = result
        self._gpx_path = plan.get('gpx_path', '')
        self.results_panel.update_results(result, ftp)

        self.export_fit_btn.setEnabled(True)
        self.export_zwo_btn.setEnabled(True)
        self.print_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        self.tabs.setCurrentIndex(0)
        self.statusbar.showMessage(f"Loaded plan: {plan.get('name', 'Untitled')}")

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

    def _print_cheat_sheet(self):
        if not self._result:
            return
        params = self.inputs_panel.get_params()
        name = os.path.splitext(os.path.basename(self._gpx_path or 'Course'))[0]
        open_cheat_sheet(self._result, params, name)

    def _save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        state = self.inputs_panel.get_state()
        with open(CONFIG_PATH, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH) as f:
                    state = json.load(f)
                if state.get('units') == 'imperial':
                    self._set_units(False)
                self.inputs_panel.set_state(state)
            except Exception:
                pass

    def closeEvent(self, event):
        self._save_config()
        super().closeEvent(event)
