"""
Base View - Widget con layout a split per liste con dettaglio
"""

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


class ListViewWithDetail(QWidget):
    """
    Widget base con layout:
      - Top-left: controlli (filtri, pulsanti)
      - Top-right: dettaglio dell'elemento selezionato
      - Bottom: lista/output (QListWidget)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.controls_widget = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_widget)
        self.controls_layout.setAlignment(Qt.AlignTop)
        self.controls_layout.setSpacing(8)

        self.detail_widget = QWidget()
        self.detail_widget.setObjectName("detail_panel")
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setAlignment(Qt.AlignTop)
        self.detail_layout.setSpacing(4)

        self.detail_title = QLabel("📋 DETTAGLIO")
        self.detail_title.setObjectName("detail_title")
        self.detail_title.setFixedHeight(20)  # 🔥 FORZA ALTEZZA A 20 PIXEL!
        self.detail_title.setStyleSheet("padding: 0px; margin: 0px; font-size: 11px;")
        self.detail_layout.addWidget(self.detail_title)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setObjectName("detail_text")
        self.detail_text.setFont(QFont("Courier New", 10))
        self.detail_text.setMinimumHeight(100)
        self.detail_text.setMaximumHeight(180)
        self.detail_layout.addWidget(self.detail_text)

        top_layout.addWidget(self.controls_widget, 2)
        top_layout.addWidget(self.detail_widget, 1)

        self.output_widget = QWidget()
        self.output_layout = QVBoxLayout(self.output_widget)
        self.output_layout.setContentsMargins(0, 0, 0, 0)

        self.splitter.addWidget(top_widget)
        self.splitter.addWidget(self.output_widget)
        self.splitter.setSizes([250, 500])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)

    def set_detail_text(self, text):
        self.detail_text.setPlainText(text)

    def set_detail_html(self, html):
        self.detail_text.setHtml(html)

    def clear_detail(self):
        self.detail_text.clear()