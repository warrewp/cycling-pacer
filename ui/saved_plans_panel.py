import json
import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QMessageBox, QInputDialog, QLabel, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

PLANS_DIR = Path.home() / '.cyclingpacer' / 'plans'


def _ensure_dir():
    PLANS_DIR.mkdir(parents=True, exist_ok=True)


def save_plan(name: str, result: dict, params: dict, gpx_path: str) -> str:
    _ensure_dir()
    slug = name.lower().replace(' ', '_').replace('/', '-')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{slug}_{ts}.json"
    filepath = PLANS_DIR / filename

    plan = {
        'name': name,
        'saved_at': datetime.now().isoformat(),
        'gpx_path': gpx_path,
        'params': params,
        'result': {
            'total_time_s': result['total_time_s'],
            'wap_w': result['wap_w'],
            'intensity_factor': result['intensity_factor'],
            'tss': result['tss'],
            'variability_index': result['variability_index'],
            'mean_power_w': result['mean_power_w'],
            'solver_success': result['solver_success'],
            'solver_message': result['solver_message'],
            'segments': [
                {
                    'index': s['index'],
                    'lat': s['lat'],
                    'lon': s['lon'],
                    'distance_m': s['distance_m'],
                    'cumulative_m': s['cumulative_m'],
                    'elevation_m': s['elevation_m'],
                    'gradient': s['gradient'],
                    'surface': s.get('surface', ''),
                    'crr': s.get('crr', 0.006),
                    'zone_label': s.get('zone_label', 'flat'),
                    'power_w': s['power_w'],
                    'speed_ms': s['speed_ms'],
                    'time_s': s['time_s'],
                    'elapsed_s': s['elapsed_s'],
                }
                for s in result['segments']
            ],
        },
    }

    with open(filepath, 'w') as f:
        json.dump(plan, f, indent=2)

    return str(filepath)


def list_plans() -> list[dict]:
    _ensure_dir()
    plans = []
    for f in sorted(PLANS_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f) as fh:
                data = json.load(fh)
            data['_filepath'] = str(f)
            plans.append(data)
        except Exception:
            continue
    return plans


def load_plan(filepath: str) -> dict:
    with open(filepath) as f:
        return json.load(f)


def delete_plan(filepath: str):
    os.remove(filepath)


class SavedPlansPanel(QWidget):
    plan_loaded = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #f2f2f2;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("SAVED PACING PLANS")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #555; letter-spacing: 1px;")
        header_row.addWidget(title)
        header_row.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #fff; border: 1px solid #ccc; border-radius: 4px;
                padding: 4px 12px; font-size: 12px; color: #444;
            }
            QPushButton:hover { background: #f0f0f0; }
        """)
        self.refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(self.refresh_btn)
        layout.addLayout(header_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'Name', 'Date', 'Distance', 'Total Time', 'WAP', 'ER', 'GPX File',
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
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
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_style = """
            QPushButton {
                background: #fff; border: 1px solid #ccc; border-radius: 4px;
                padding: 6px 16px; font-size: 12px; color: #444;
            }
            QPushButton:hover { background: #f0f0f0; }
            QPushButton:disabled { color: #bbb; }
        """

        self.load_btn = QPushButton("Load Plan")
        self.load_btn.setStyleSheet(btn_style.replace('#fff', '#4CAF50').replace('#444', 'white').replace('#ccc', '#4CAF50').replace('#f0f0f0', '#43A047'))
        self.load_btn.clicked.connect(self._load_selected)
        self.load_btn.setEnabled(False)
        btn_row.addWidget(self.load_btn)

        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setStyleSheet(btn_style)
        self.rename_btn.clicked.connect(self._rename_selected)
        self.rename_btn.setEnabled(False)
        btn_row.addWidget(self.rename_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(btn_style.replace('#fff', '#fff').replace('#ccc', '#e74c3c').replace('#444', '#e74c3c').replace('#f0f0f0', '#fde8e8'))
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setEnabled(False)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._plans = []
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def refresh(self):
        self._plans = list_plans()
        self.table.setRowCount(len(self._plans))

        for i, plan in enumerate(self._plans):
            result = plan.get('result', {})
            segments = result.get('segments', [])
            total_km = sum(s.get('distance_m', 0) for s in segments) / 1000

            self.table.setItem(i, 0, QTableWidgetItem(plan.get('name', 'Untitled')))

            saved_at = plan.get('saved_at', '')
            try:
                dt = datetime.fromisoformat(saved_at)
                date_str = dt.strftime('%b %d, %Y %H:%M')
            except Exception:
                date_str = saved_at[:16]
            self.table.setItem(i, 1, QTableWidgetItem(date_str))

            self.table.setItem(i, 2, QTableWidgetItem(f"{total_km:.1f} km"))

            total_s = result.get('total_time_s', 0)
            h = int(total_s // 3600)
            m = int((total_s % 3600) // 60)
            self.table.setItem(i, 3, QTableWidgetItem(f"{h}h {m:02d}m"))

            self.table.setItem(i, 4, QTableWidgetItem(f"{result.get('wap_w', 0):.0f}W"))
            self.table.setItem(i, 5, QTableWidgetItem(f"{result.get('intensity_factor', 0):.2f}"))

            gpx = os.path.basename(plan.get('gpx_path', ''))
            self.table.setItem(i, 6, QTableWidgetItem(gpx))

        self._on_selection_changed()

    def _on_selection_changed(self):
        has_selection = len(self.table.selectedItems()) > 0
        self.load_btn.setEnabled(has_selection)
        self.rename_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _selected_index(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _on_double_click(self, index):
        self._load_selected()

    def _load_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self._plans):
            return
        plan = self._plans[idx]
        self.plan_loaded.emit(plan)

    def _rename_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self._plans):
            return
        plan = self._plans[idx]
        old_name = plan.get('name', '')
        new_name, ok = QInputDialog.getText(self, "Rename Plan", "New name:", text=old_name)
        if not ok or not new_name.strip():
            return

        filepath = plan['_filepath']
        with open(filepath) as f:
            data = json.load(f)
        data['name'] = new_name.strip()
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        self.refresh()

    def _delete_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self._plans):
            return
        plan = self._plans[idx]
        name = plan.get('name', 'this plan')

        reply = QMessageBox.question(
            self, "Delete Plan",
            f"Delete \"{name}\"? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_plan(plan['_filepath'])
            self.refresh()
