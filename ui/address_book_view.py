"""
Address Book View - Rubrica indirizzi per PAX Wallet GUI
"""

import json
from pathlib import Path
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from .base_view import ListViewWithDetail
from wallet_backend import format_time_ago


class AddressBookView(ListViewWithDetail):
    """View per la gestione della rubrica"""
    
    def __init__(self, main_window):
        self.main = main_window
        super().__init__()
        self.contacts = []
        self.setup_controls()
        self.setup_list()
        self.refresh_contacts()
    
    def setup_controls(self):
        layout = self.controls_layout

        title = QLabel("◈ RUBRICA")
        title.setObjectName("view_title")
        layout.addWidget(title)

        # Legenda
        legend = QLabel("📌 AUTO = contatto automatico dalle transazioni | MANUAL = contatto inserito manualmente")
        legend.setObjectName("status")
        legend.setStyleSheet("color: #8892b0; font-size: 11px;")
        layout.addWidget(legend)

        # Riga 1: Refresh, Cerca, Filtri
        row = QHBoxLayout()

        refresh_btn = QPushButton("◈ AGGIORNA")
        refresh_btn.clicked.connect(self.refresh_contacts)
        row.addWidget(refresh_btn)

        row.addSpacing(10)
        row.addWidget(QLabel("Cerca:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cerca per nome o indirizzo...")
        self.search_input.textChanged.connect(self.search_contacts)
        row.addWidget(self.search_input)

        row.addSpacing(10)
        row.addWidget(QLabel("Ordina:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Nome", "Ultimo uso", "Transazioni"])
        self.sort_combo.setCurrentText("Nome")
        self.sort_combo.currentTextChanged.connect(self.refresh_contacts)
        row.addWidget(self.sort_combo)

        row.addStretch()
        layout.addLayout(row)

        # Riga 2: Bottoni azioni
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("◈ AGGIUNGI")
        self.add_btn.clicked.connect(self.add_contact)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("◈ MODIFICA")
        self.edit_btn.clicked.connect(self.edit_contact)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("◈ ELIMINA")
        self.delete_btn.clicked.connect(self.delete_contact)
        btn_layout.addWidget(self.delete_btn)

        self.fav_btn = QPushButton("◈ PREFERITO")
        self.fav_btn.clicked.connect(self.toggle_favorite)
        btn_layout.addWidget(self.fav_btn)

        # Bottone INVIA
        self.send_btn = QPushButton("◈ INVIA")
        self.send_btn.setStyleSheet("background-color: #00ff41; color: #0a0a0a; font-weight: bold;")
        self.send_btn.clicked.connect(self.send_to_contact)
        btn_layout.addWidget(self.send_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.count_label = QLabel()
        self.count_label.setObjectName("status")
        self.count_label.setWordWrap(True)
        layout.addWidget(self.count_label)

    def setup_list(self):
        self.contact_list = QListWidget()
        self.contact_list.setObjectName("contact_list")
        self.contact_list.setFont(QFont("Courier New", 10))
        self.contact_list.itemClicked.connect(self.on_contact_clicked)
        self.contact_list.setAlternatingRowColors(True)
        self.output_layout.addWidget(self.contact_list)

    def refresh_contacts(self):
        """Aggiorna la lista contatti"""
        if not self.main.backend:
            return

        sort_map = {
            "Nome": "name",
            "Ultimo uso": "last_used",
            "Transazioni": "tx_count"
        }
        sort_by = sort_map.get(self.sort_combo.currentText(), "name")
        search = self.search_input.text().strip() or None

        result = self.main.backend.get_contacts(sort_by=sort_by, search=search)

        if not result.get("success"):
            self.contact_list.clear()
            self.contact_list.addItem(f"❌ {result.get('message', 'Errore')}")
            return

        self.contacts = result.get("contacts", [])
        self.contact_list.clear()

        if not self.contacts:
            self.contact_list.addItem("📭 Nessun contatto in rubrica")
            self.count_label.setText("0 contatti")
            return

        stats = result.get("stats", {})

        # Titoli colonne
        header = f"{'⭐':<3} {'Nome':<22} {'Indirizzo':<40} {'Crypto':<6} {'Fonte':<8} {'TX':<6} {'Ultimo uso'}"
        header_item = QListWidgetItem(header)
        header_item.setData(Qt.UserRole, None)
        header_item.setForeground(QColor("#00ff41"))
        header_item.setBackground(QColor("#0a0a0a"))
        font = QFont("Courier New", 10, QFont.Bold)
        header_item.setFont(font)
        self.contact_list.addItem(header_item)

        # Separatore
        sep = "-" * 110
        sep_item = QListWidgetItem(sep)
        sep_item.setData(Qt.UserRole, None)
        sep_item.setForeground(QColor("#003b00"))
        self.contact_list.addItem(sep_item)

        for c in self.contacts:
            name = c.get("name", "N/A")
            address = c.get("address", "N/A")
            crypto = c.get("crypto", "XRP")
            star = "⭐" if c.get("is_favorite") else "  "
            source = c.get("source", "auto")
            tx_count = c.get("tx_count", 0)
            last_used = c.get("last_used", 0)
            last_str = format_time_ago(last_used) if last_used else "Mai"

            item_text = f"{star:<3} {name[:20]:<22} {address:<40} {crypto:<6} {source[:6]:<8} {tx_count:<6} {last_str}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, c)
            self.contact_list.addItem(item)

        self.count_label.setText(f"{len(self.contacts)} contatti (Totale: {stats.get('total', 0)} | Preferiti: {stats.get('favorites', 0)})")

        self.clear_detail()

    def search_contacts(self):
        """Ricerca contatti in tempo reale"""
        self.refresh_contacts()

    def on_contact_clicked(self, item):
        """Mostra dettaglio contatto"""
        contact = item.data(Qt.UserRole)
        if not contact:
            return

        html = f"""
        <b>📇 DETTAGLIO CONTATTO</b><br><br>
        <b>Nome:</b> {contact.get('name', 'N/A')}<br>
        <b>Indirizzo:</b> {contact.get('address', 'N/A')}<br>
        <b>Crypto:</b> {contact.get('crypto', 'XRP')}<br>
        <b>Network:</b> {contact.get('network', 'mainnet').upper()}<br>
        <b>Fonte:</b> {'✅ Manuale' if contact.get('source') == 'manual' else '🔄 Automatico'}<br>
        <b>Preferito:</b> {'⭐ Sì' if contact.get('is_favorite') else '❌ No'}<br>
        <b>Tags:</b> {', '.join(contact.get('tags', [])) or 'Nessuno'}<br>
        <b>Note:</b> {contact.get('notes', 'Nessuna')}<br>
        <hr>
        <b>Prima transazione:</b> {format_time_ago(contact.get('first_seen', 0))}<br>
        <b>Ultima transazione:</b> {format_time_ago(contact.get('last_used', 0)) or 'Mai'}<br>
        <b>Transazioni:</b> {contact.get('tx_count', 0)}<br>
        """
        self.set_detail_html(html)

    def send_to_contact(self):
        """Invia al contatto selezionato - apre il tab Invia con indirizzo precompilato"""
        current = self.contact_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Errore", "Seleziona un contatto dalla lista")
            return

        contact = current.data(Qt.UserRole)
        if not contact:
            return

        address = contact.get('address', '')
        if not address:
            QMessageBox.warning(self, "Errore", "Indirizzo non valido")
            return

        name = contact.get('name', '')
        crypto = contact.get('crypto', 'XRP')

        # Chiedi conferma
        reply = QMessageBox.question(
            self,
            "Conferma",
            f"Inviare a '{name}' ({crypto})?\n\nIndirizzo: {address}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Vai al tab Invia (indice 1)
            self.main.switch_view(1)

            # Precompila l'indirizzo nel campo address
            if hasattr(self.main, 'send_view'):
                self.main.send_view.address_input.setText(address)
                self.main.send_view.address_input.setFocus()

                # Se il contatto ha un nome, mostralo nello status
                if name:
                    self.main.send_view.status_label.setText(f"📇 Destinatario: {name} ({crypto})")
                else:
                    self.main.send_view.status_label.setText(f"📇 Destinatario: {address[:16]}...")

    def add_contact(self):
        """Aggiungi nuovo contatto"""
        if not self.main.backend:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Aggiungi Contatto")
        dialog.setMinimumWidth(400)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        address_input = QLineEdit()
        address_input.setPlaceholderText("r... o G...")
        form.addRow("Indirizzo:", address_input)

        name_input = QLineEdit()
        name_input.setPlaceholderText("Nome contatto")
        form.addRow("Nome:", name_input)

        crypto_combo = QComboBox()
        crypto_combo.addItems(["XRP", "XLM"])
        form.addRow("Crypto:", crypto_combo)

        network_combo = QComboBox()
        network_combo.addItems(["mainnet", "testnet"])
        form.addRow("Network:", network_combo)

        tags_input = QLineEdit()
        tags_input.setPlaceholderText("tag1, tag2, ...")
        form.addRow("Tags:", tags_input)

        notes_input = QTextEdit()
        notes_input.setMaximumHeight(80)
        form.addRow("Note:", notes_input)

        fav_check = QCheckBox("Preferito")
        form.addRow("", fav_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            address = address_input.text().strip()
            name = name_input.text().strip() or address[:12]
            crypto = crypto_combo.currentText()
            network = network_combo.currentText()
            tags = [t.strip() for t in tags_input.text().split(",") if t.strip()]
            notes = notes_input.toPlainText().strip()
            is_favorite = fav_check.isChecked()

            if not address:
                QMessageBox.warning(self, "Errore", "L'indirizzo è obbligatorio")
                return

            result = self.main.backend.add_contact(
                address, name, crypto, network, tags, notes, is_favorite
            )

            if result.get("success"):
                QMessageBox.information(self, "Successo", "Contatto aggiunto con successo!")
                self.refresh_contacts()
            else:
                QMessageBox.critical(self, "Errore", result.get("message", "Errore sconosciuto"))

    def edit_contact(self):
        """Modifica contatto selezionato"""
        current = self.contact_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Errore", "Seleziona un contatto dalla lista")
            return

        contact = current.data(Qt.UserRole)
        if not contact:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Modifica Contatto")
        dialog.setMinimumWidth(400)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        # Mostra indirizzo (non modificabile)
        address_label = QLabel(contact.get('address', 'N/A'))
        form.addRow("Indirizzo:", address_label)

        name_input = QLineEdit(contact.get('name', ''))
        form.addRow("Nome:", name_input)

        crypto_combo = QComboBox()
        crypto_combo.addItems(["XRP", "XLM"])
        crypto_combo.setCurrentText(contact.get('crypto', 'XRP'))
        form.addRow("Crypto:", crypto_combo)

        tags_input = QLineEdit(', '.join(contact.get('tags', [])))
        tags_input.setPlaceholderText("tag1, tag2, ...")
        form.addRow("Tags:", tags_input)

        notes_input = QTextEdit(contact.get('notes', ''))
        notes_input.setMaximumHeight(80)
        form.addRow("Note:", notes_input)

        fav_check = QCheckBox("Preferito")
        fav_check.setChecked(contact.get('is_favorite', False))
        form.addRow("", fav_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip() or contact.get('address', 'N/A')[:12]
            crypto = crypto_combo.currentText()
            tags = [t.strip() for t in tags_input.text().split(",") if t.strip()]
            notes = notes_input.toPlainText().strip()
            is_favorite = fav_check.isChecked()

            result = self.main.backend.add_contact(
                contact.get('address'),
                name, crypto, None, tags, notes, is_favorite
            )

            if result.get("success"):
                QMessageBox.information(self, "Successo", "Contatto modificato con successo!")
                self.refresh_contacts()
            else:
                QMessageBox.critical(self, "Errore", result.get("message", "Errore sconosciuto"))

    def delete_contact(self):
        """Elimina contatto selezionato"""
        current = self.contact_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Errore", "Seleziona un contatto dalla lista")
            return

        contact = current.data(Qt.UserRole)
        if not contact:
            return

        reply = QMessageBox.question(
            self,
            "Conferma",
            f"Eliminare '{contact.get('name')}' dalla rubrica?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            result = self.main.backend.delete_contact(contact.get('address'))
            if result.get("success"):
                QMessageBox.information(self, "Successo", "Contatto eliminato con successo!")
                self.refresh_contacts()
            else:
                QMessageBox.critical(self, "Errore", result.get("message", "Errore sconosciuto"))

    def toggle_favorite(self):
        """Toggle preferito per contatto selezionato"""
        current = self.contact_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Errore", "Seleziona un contatto dalla lista")
            return

        contact = current.data(Qt.UserRole)
        if not contact:
            return

        result = self.main.backend.toggle_favorite(contact.get('address'))
        if result.get("success"):
            self.refresh_contacts()
            self.status_label.setText("✅ Preferito aggiornato")
        else:
            QMessageBox.critical(self, "Errore", result.get("message", "Errore sconosciuto"))

    def clear_detail(self):
        """Pulisce il dettaglio"""
        self.set_detail_html("Seleziona un contatto per vedere i dettagli")