import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CyclingPacer")
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QComboBox QAbstractItemView {
            background: #ffffff;
            color: #333;
            selection-background-color: #4CAF50;
            selection-color: #ffffff;
        }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
