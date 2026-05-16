from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QDoubleSpinBox,
    QComboBox, QSlider, QLabel, QHBoxLayout, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.physics import load_surfaces
from ui.units import kg_to_lb, lb_to_kg, m_to_ft, ft_to_m, kmh_to_mph, mph_to_kmh, c_to_f, f_to_c

PANEL_STYLE = """
    QGroupBox {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-top: 14px;
        padding-top: 18px;
        font-size: 11px;
        font-weight: bold;
        color: #555;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }
    QDoubleSpinBox, QComboBox {
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 3px 6px;
        background: #fafafa;
        font-size: 12px;
    }
    QComboBox QAbstractItemView {
        background: #ffffff;
        selection-background-color: #4CAF50;
        selection-color: #ffffff;
        color: #333;
    }
    QLabel { font-size: 12px; color: #444; }
"""

CDA_PRESETS = {
    'Upright MTB (0.450)': 0.450,
    'Gravel relaxed (0.380)': 0.380,
    'Gravel aggressive (0.320)': 0.320,
    'Road aero (0.260)': 0.260,
    'TT (0.210)': 0.210,
    'Custom': None,
}


class InputsPanel(QWidget):
    run_requested = pyqtSignal()
    units_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metric = True
        self.setStyleSheet(PANEL_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Section label
        header = QLabel("HARDWARE SPECS")
        header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888; letter-spacing: 1px; padding: 4px 0;")
        layout.addWidget(header)

        layout.addWidget(self._build_rider_group())
        layout.addWidget(self._build_bike_group())

        header2 = QLabel("WEATHER & STRATEGY")
        header2.setStyleSheet("font-size: 11px; font-weight: bold; color: #888; letter-spacing: 1px; padding: 8px 0 0 0;")
        layout.addWidget(header2)

        layout.addWidget(self._build_weather_strategy_group())

        self.run_btn = QPushButton("Run Optimizer")
        self.run_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px; padding: 10px; font-weight: bold;
                background: #4CAF50; color: white; border: none; border-radius: 6px;
            }
            QPushButton:hover { background: #43A047; }
            QPushButton:pressed { background: #388E3C; }
            QPushButton:disabled { background: #ccc; color: #888; }
        """)
        self.run_btn.clicked.connect(self.run_requested.emit)
        layout.addWidget(self.run_btn)

        layout.addStretch()

    @property
    def is_metric(self):
        return self._metric

    def set_units(self, metric: bool):
        if metric == self._metric:
            return
        self._metric = metric

        if metric:
            self._convert_spin(self.weight_spin, lb_to_kg, 30, 200, " kg")
            self._convert_spin(self.bike_weight_spin, lb_to_kg, 3, 30, " kg")
            self._convert_spin(self.wind_speed_spin, mph_to_kmh, 0, 100, " km/h")
            self._convert_spin(self.temp_spin, f_to_c, -20, 50, " °C")
            self._convert_spin(self.altitude_spin, ft_to_m, 0, 6000, " m")
        else:
            self._convert_spin(self.weight_spin, kg_to_lb, 66, 440, " lbs")
            self._convert_spin(self.bike_weight_spin, kg_to_lb, 7, 66, " lbs")
            self._convert_spin(self.wind_speed_spin, kmh_to_mph, 0, 62, " mph")
            self._convert_spin(self.temp_spin, c_to_f, -4, 122, " °F")
            self._convert_spin(self.altitude_spin, m_to_ft, 0, 20000, " ft")

        self.units_changed.emit("metric" if metric else "imperial")

    def _convert_spin(self, spin, converter, new_min, new_max, suffix):
        spin.blockSignals(True)
        new_val = converter(spin.value())
        spin.setRange(new_min, new_max)
        spin.setValue(new_val)
        spin.setSuffix(suffix)
        spin.blockSignals(False)

    def _build_rider_group(self):
        group = QGroupBox("Rider")
        form = QFormLayout(group)
        form.setSpacing(6)

        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(30, 200)
        self.weight_spin.setValue(80)
        self.weight_spin.setSuffix(" kg")
        form.addRow("Weight:", self.weight_spin)

        self.ftp_spin = QDoubleSpinBox()
        self.ftp_spin.setRange(50, 600)
        self.ftp_spin.setDecimals(0)
        self.ftp_spin.setValue(200)
        self.ftp_spin.setSuffix(" W")
        form.addRow("FTP:", self.ftp_spin)

        if_layout = QHBoxLayout()
        self.if_slider = QSlider(Qt.Orientation.Horizontal)
        self.if_slider.setRange(60, 95)
        self.if_slider.setValue(75)
        self.if_label = QLabel("0.75 — Moderate")
        self.if_label.setStyleSheet("font-size: 11px; color: #666; min-width: 110px;")
        self.if_slider.valueChanged.connect(self._update_if_label)
        if_layout.addWidget(self.if_slider)
        if_layout.addWidget(self.if_label)
        form.addRow("Target Effort:", if_layout)

        return group

    def _update_if_label(self, val):
        if_val = val / 100
        if if_val < 0.70:
            desc = "Easy"
        elif if_val > 0.85:
            desc = "Hard"
        else:
            desc = "Moderate"
        self.if_label.setText(f"{if_val:.2f} — {desc}")

    def _build_bike_group(self):
        group = QGroupBox("Bike")
        form = QFormLayout(group)
        form.setSpacing(6)

        self.bike_weight_spin = QDoubleSpinBox()
        self.bike_weight_spin.setRange(3, 30)
        self.bike_weight_spin.setValue(9)
        self.bike_weight_spin.setSuffix(" kg")
        form.addRow("System weight:", self.bike_weight_spin)

        self.cda_combo = QComboBox()
        self.cda_combo.addItems(CDA_PRESETS.keys())
        self.cda_combo.setCurrentText('Gravel relaxed (0.380)')
        self.cda_combo.currentTextChanged.connect(self._on_cda_preset)
        form.addRow("CdA:", self.cda_combo)

        self.cda_spin = QDoubleSpinBox()
        self.cda_spin.setRange(0.15, 0.60)
        self.cda_spin.setDecimals(3)
        self.cda_spin.setSingleStep(0.01)
        self.cda_spin.setValue(0.380)
        self.cda_spin.setSuffix(" m²")
        self.cda_spin.setEnabled(False)
        form.addRow("", self.cda_spin)

        self.drivetrain_spin = QDoubleSpinBox()
        self.drivetrain_spin.setRange(0.93, 0.99)
        self.drivetrain_spin.setDecimals(2)
        self.drivetrain_spin.setSingleStep(0.01)
        self.drivetrain_spin.setValue(0.97)
        form.addRow("Drivetrain eff.:", self.drivetrain_spin)

        self.surface_combo = QComboBox()
        surfaces = load_surfaces()
        self.surface_combo.addItems(surfaces.keys())
        self.surface_combo.setCurrentText('gravel_packed')
        form.addRow("Default surface:", self.surface_combo)

        return group

    def _on_cda_preset(self, text):
        val = CDA_PRESETS.get(text)
        if val is not None:
            self.cda_spin.setValue(val)
            self.cda_spin.setEnabled(False)
        else:
            self.cda_spin.setEnabled(True)

    def _build_weather_strategy_group(self):
        group = QGroupBox("")
        form = QFormLayout(group)
        form.setSpacing(6)

        self.wind_speed_spin = QDoubleSpinBox()
        self.wind_speed_spin.setRange(0, 100)
        self.wind_speed_spin.setValue(0)
        self.wind_speed_spin.setSuffix(" km/h")
        form.addRow("Wind speed:", self.wind_speed_spin)

        self.wind_dir_combo = QComboBox()
        self.wind_dir_combo.addItems(["Headwind", "Tailwind", "Crosswind (×0.5 effective)"])
        form.addRow("Wind direction:", self.wind_dir_combo)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(-20, 50)
        self.temp_spin.setValue(20)
        self.temp_spin.setSuffix(" °C")
        form.addRow("Temperature:", self.temp_spin)

        self.altitude_spin = QDoubleSpinBox()
        self.altitude_spin.setRange(0, 6000)
        self.altitude_spin.setDecimals(0)
        self.altitude_spin.setValue(0)
        self.altitude_spin.setSuffix(" m")
        form.addRow("Start altitude:", self.altitude_spin)


        return group

    def get_params(self):
        if self._metric:
            wind_kmh = self.wind_speed_spin.value()
            temp_c = self.temp_spin.value()
            alt_m = self.altitude_spin.value()
            rider_kg = self.weight_spin.value()
            bike_kg = self.bike_weight_spin.value()
        else:
            wind_kmh = mph_to_kmh(self.wind_speed_spin.value())
            temp_c = f_to_c(self.temp_spin.value())
            alt_m = ft_to_m(self.altitude_spin.value())
            rider_kg = lb_to_kg(self.weight_spin.value())
            bike_kg = lb_to_kg(self.bike_weight_spin.value())

        wind_ms = wind_kmh / 3.6
        wind_dir = self.wind_dir_combo.currentText()
        if "Tailwind" in wind_dir:
            wind_ms = -wind_ms
        elif "Crosswind" in wind_dir:
            wind_ms *= 0.5

        from core.physics import air_density
        rho = air_density(temp_c, alt_m)

        return {
            'rider': {
                'mass_kg': rider_kg + bike_kg,
                'cda': self.cda_spin.value(),
                'drivetrain_eff': self.drivetrain_spin.value(),
            },
            'env': {
                'wind_ms': wind_ms,
                'rho': rho,
            },
            'ftp_w': self.ftp_spin.value(),
            'target_if': self.if_slider.value() / 100,
            'min_power_w': 0,
            'max_power_w': None,
            'segment_length_m': 100,
            'default_surface': self.surface_combo.currentText(),
            'temperature_c': temp_c,
        }

    def get_state(self):
        return {
            'units': 'metric' if self._metric else 'imperial',
            'weight': self.weight_spin.value(),
            'ftp': self.ftp_spin.value(),
            'target_if': self.if_slider.value(),
            'bike_weight': self.bike_weight_spin.value(),
            'cda_preset': self.cda_combo.currentText(),
            'cda': self.cda_spin.value(),
            'drivetrain': self.drivetrain_spin.value(),
            'surface': self.surface_combo.currentText(),
            'wind_speed': self.wind_speed_spin.value(),
            'wind_dir': self.wind_dir_combo.currentText(),
            'temperature': self.temp_spin.value(),
            'altitude': self.altitude_spin.value(),
        }

    def set_state(self, state):
        if not state:
            return
        saved_metric = state.get('units', 'metric') == 'metric'
        if not saved_metric:
            self.set_units(False)
        self.weight_spin.setValue(state.get('weight', 80 if self._metric else 176))
        self.ftp_spin.setValue(state.get('ftp', 200))
        self.if_slider.setValue(state.get('target_if', 75))
        self.bike_weight_spin.setValue(state.get('bike_weight', 9 if self._metric else 20))
        self.cda_combo.setCurrentText(state.get('cda_preset', 'Gravel relaxed (0.380)'))
        self.cda_spin.setValue(state.get('cda', 0.380))
        self.drivetrain_spin.setValue(state.get('drivetrain', 0.97))
        self.surface_combo.setCurrentText(state.get('surface', 'gravel_packed'))
        self.wind_speed_spin.setValue(state.get('wind_speed', 0))
        self.wind_dir_combo.setCurrentText(state.get('wind_dir', 'Headwind'))
        self.temp_spin.setValue(state.get('temperature', 20 if self._metric else 68))
        self.altitude_spin.setValue(state.get('altitude', 0))
