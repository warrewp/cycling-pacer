import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CyclingPacer")
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QComboBox {
            color: #333;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #666;
            margin-right: 6px;
        }
        QComboBox QAbstractItemView {
            background: #ffffff;
            color: #333;
            selection-background-color: #4CAF50;
            selection-color: #ffffff;
            border: 1px solid #ccc;
        }
        QComboBox QAbstractItemView::item {
            padding: 4px 8px;
            color: #333;
        }
        QComboBox QAbstractItemView::item:selected {
            background: #4CAF50;
            color: #ffffff;
        }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
