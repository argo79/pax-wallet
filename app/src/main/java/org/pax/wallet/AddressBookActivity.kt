package org.pax.wallet

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

class AddressBookActivity : AppCompatActivity() {

    private lateinit var addressBookManager: AddressBookManager
    private lateinit var container: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_address_book)

        addressBookManager = AddressBookManager(this)
        container = findViewById(R.id.contacts_container)

        findViewById<Button>(R.id.btn_add_contact).setOnClickListener {
            showAddContactDialog()
        }
        findViewById<Button>(R.id.btn_back).setOnClickListener {
            finish()
        }

        loadContacts()
    }

    private fun loadContacts() {
        container.removeAllViews()
        val contacts = addressBookManager.getContacts()

        if (contacts.isEmpty()) {
            val emptyText = TextView(this)
            emptyText.text = "Nessun contatto. Aggiungi il primo!"
            emptyText.textSize = 16f
            emptyText.setPadding(16, 32, 16, 32)
            container.addView(emptyText)
            return
        }

        for (contact in contacts) {
            val card = createContactCard(contact)
            container.addView(card)
        }
    }

    private fun createContactCard(contact: Contact): LinearLayout {
        val card = LinearLayout(this)
        card.orientation = LinearLayout.VERTICAL
        card.setPadding(16, 16, 16, 16)
        card.layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            setMargins(8, 8, 8, 8)
        }
        card.setBackgroundColor(0xFFFFFFFF.toInt())
        card.elevation = 2f

        val tvName = TextView(this).apply {
            text = contact.name
            textSize = 16f
            setTypeface(null, android.graphics.Typeface.BOLD)
        }

        val tvAddress = TextView(this).apply {
            text = contact.address
            textSize = 12f
            setTextColor(0xFF666666.toInt())
            setTextIsSelectable(true)
        }

        val tvCrypto = TextView(this).apply {
            text = "${contact.crypto} - ${if (contact.isMainnet) "MAINNET" else "TESTNET"}"
            textSize = 12f
            setTextColor(0xFF999999.toInt())
        }

        card.addView(tvName)
        card.addView(tvAddress)
        card.addView(tvCrypto)

        // Clic singolo = invia a questo contatto
        card.setOnClickListener {
            val intent = Intent()
            intent.putExtra("address", contact.address)
            setResult(RESULT_OK, intent)
            finish()
        }

        // Clic lungo = menu opzioni
        card.setOnLongClickListener {
            showContactOptions(contact)
            true
        }

        return card
    }

    private fun showAddContactDialog() {
        val nameInput = EditText(this).apply { hint = "Nome contatto" }
        val addressInput = EditText(this).apply { hint = "Indirizzo XRP" }
        
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 16, 48, 16)
            addView(nameInput)
            addView(addressInput)
        }

        AlertDialog.Builder(this)
            .setTitle("Aggiungi contatto")
            .setView(layout)
            .setPositiveButton("Salva") { _, _ ->
                val name = nameInput.text.toString().ifEmpty { "Contatto" }
                val address = addressInput.text.toString().trim()
                if (address.isNotEmpty()) {
                    addressBookManager.saveContact(name, address)
                    loadContacts()
                    Toast.makeText(this, "Contatto salvato!", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this, "Indirizzo vuoto", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Annulla", null)
            .show()
    }

    private fun showContactOptions(contact: Contact) {
        val options = arrayOf("Invia XRP", "Rinomina", "Elimina")
        AlertDialog.Builder(this)
            .setTitle(contact.name)
            .setItems(options) { _, which ->
                when (which) {
                    0 -> {
                        val intent = Intent()
                        intent.putExtra("address", contact.address)
                        setResult(RESULT_OK, intent)
                        finish()
                    }
                    1 -> showRenameDialog(contact)
                    2 -> showDeleteDialog(contact)
                }
            }
            .setNegativeButton("Annulla", null)
            .show()
    }

    private fun showRenameDialog(contact: Contact) {
        val nameInput = EditText(this).apply { setText(contact.name) }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 16, 48, 16)
            addView(nameInput)
        }
        AlertDialog.Builder(this)
            .setTitle("Rinomina contatto")
            .setView(layout)
            .setPositiveButton("Salva") { _, _ ->
                val newName = nameInput.text.toString().ifEmpty { contact.name }
                addressBookManager.renameContact(contact.id, newName)
                loadContacts()
            }
            .setNegativeButton("Annulla", null)
            .show()
    }

    private fun showDeleteDialog(contact: Contact) {
        AlertDialog.Builder(this)
            .setTitle("Elimina contatto")
            .setMessage("Eliminare '${contact.name}'?")
            .setPositiveButton("Elimina") { _, _ ->
                addressBookManager.deleteContact(contact.id)
                loadContacts()
                Toast.makeText(this, "Contatto eliminato", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("Annulla", null)
            .show()
    }
}