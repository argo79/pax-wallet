package org.pax.wallet

import org.pax.wallet.AddressBookManager
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.launch

class HistoryActivity : AppCompatActivity() {

    private lateinit var xrpManager: XRPManager
    private lateinit var container: LinearLayout
    private lateinit var tvPageInfo: TextView
    
    private var address = ""
    private var isMainnet = true
    private var currentPage = 0
    private val pageSize = 10
    private var totalTransactions = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_history)

        xrpManager = XRPManager()
        container = findViewById(R.id.history_container)
        tvPageInfo = findViewById(R.id.tv_page_info)

        address = intent.getStringExtra("address") ?: ""
        isMainnet = intent.getBooleanExtra("isMainnet", true)

        xrpManager.setNetwork(isMainnet)

        findViewById<Button>(R.id.btn_prev).setOnClickListener { 
            if (currentPage > 0) {
                currentPage--
                loadHistory()
            }
        }
        findViewById<Button>(R.id.btn_next).setOnClickListener { 
            if ((currentPage + 1) * pageSize < totalTransactions || currentPage == 0) {
                currentPage++
                loadHistory()
            }
        }
        findViewById<Button>(R.id.btn_back).setOnClickListener { finish() }

        loadHistory()
    }

    private fun loadHistory() {
        lifecycleScope.launch {
            try {
                val rawJson = xrpManager.getTransactionHistory(address, 100)
                val transactions = parseTransactions(rawJson)
                totalTransactions = transactions.size
                displayPage(transactions)
            } catch (e: Exception) {
                Toast.makeText(this@HistoryActivity, "Errore: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun parseTransactions(rawJson: String): List<TransactionInfo> {
        val list = mutableListOf<TransactionInfo>()
        try {
            val gson = Gson()
            val root = gson.fromJson(rawJson, JsonObject::class.java)
            val result = root.getAsJsonObject("result")
            val txs = result?.getAsJsonArray("transactions") ?: return list

            for (txElement in txs) {
                val txObj = txElement.asJsonObject
                val tx = txObj.getAsJsonObject("tx") ?: continue
                val meta = txObj.getAsJsonObject("meta")

                val type = tx.get("TransactionType")?.asString ?: "Unknown"
                val hash = tx.get("hash")?.asString ?: "N/A"
                val account = tx.get("Account")?.asString ?: ""
                val destination = tx.get("Destination")?.asString ?: ""
                val amount = tx.get("Amount")?.asString ?: tx.get("DeliverMax")?.asString ?: "0"
                val fee = tx.get("Fee")?.asString ?: "0"
                val date = tx.get("date")?.asLong ?: 0
                val resultCode = meta?.get("TransactionResult")?.asString ?: ""
                val destinationTag = tx.get("DestinationTag")?.asLong ?: 0

                val memo = extractMemo(tx)

                val amountXrp = try { amount.toDouble() / 1_000_000 } catch (e: Exception) { 0.0 }
                val feeXrp = try { fee.toDouble() / 1_000_000 } catch (e: Exception) { 0.0 }

                val dateStr = if (date > 0) {
                    val dateObj = java.util.Date((date + 946684800) * 1000)
                    java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault()).format(dateObj)
                } else "N/A"

                val isIncoming = destination == address
                val direction = if (isIncoming) "📥 RICEVUTO" else "📤 INVIATO"
                val counterparty = if (isIncoming) account else destination

                list.add(
                    TransactionInfo(
                        hash = hash,
                        type = type,
                        direction = direction,
                        amount = amountXrp,
                        fee = feeXrp,
                        date = dateStr,
                        result = resultCode,
                        from = account,
                        to = destination,
                        counterparty = counterparty,
                        memo = memo,
                        destinationTag = destinationTag
                    )
                )
            }
        } catch (e: Exception) {
            // Ignora errori di parsing
        }
        return list
    }

    private fun extractMemo(tx: JsonObject): String {
        try {
            val memos = tx.getAsJsonArray("Memos") ?: return ""
            if (memos.size() == 0) return ""
            
            val memoObj = memos[0].asJsonObject
            val memo = memoObj.getAsJsonObject("Memo") ?: return ""
            
            val memoData = memo.get("MemoData")?.asString ?: ""
            if (memoData.isNotEmpty()) {
                try {
                    val bytes = hexStringToByteArray(memoData)
                    val decoded = String(bytes, Charsets.UTF_8)
                    return decoded.filter { it.isLetterOrDigit() || it == ' ' || it == '.' || it == ',' || it == '!' || it == '?' }
                } catch (e: Exception) {
                    // Non è hex
                }
            }
            
            val memoFormat = memo.get("MemoFormat")?.asString ?: ""
            if (memoFormat.isNotEmpty()) {
                try {
                    val bytes = hexStringToByteArray(memoFormat)
                    val decoded = String(bytes, Charsets.UTF_8)
                    return decoded.filter { it.isLetterOrDigit() || it == ' ' || it == '.' || it == ',' || it == '!' || it == '?' }
                } catch (e: Exception) {
                    // Non è hex
                }
            }
            
            val memoType = memo.get("MemoType")?.asString ?: ""
            if (memoType.isNotEmpty()) {
                try {
                    val bytes = hexStringToByteArray(memoType)
                    val decoded = String(bytes, Charsets.UTF_8)
                    return decoded.filter { it.isLetterOrDigit() || it == ' ' || it == '.' || it == ',' || it == '!' || it == '?' }
                } catch (e: Exception) {
                    // Non è hex
                }
            }
            
            return ""
        } catch (e: Exception) {
            return ""
        }
    }

    private fun hexStringToByteArray(hex: String): ByteArray {
        val len = hex.length
        val data = ByteArray(len / 2)
        var i = 0
        while (i < len) {
            data[i / 2] = ((Character.digit(hex[i], 16) shl 4) + Character.digit(hex[i + 1], 16)).toByte()
            i += 2
        }
        return data
    }

    private fun displayPage(transactions: List<TransactionInfo>) {
        container.removeAllViews()
        
        val totalPages = if (totalTransactions == 0) 1 else (totalTransactions + pageSize - 1) / pageSize
        tvPageInfo.text = "Pagina ${currentPage + 1} di $totalPages (${totalTransactions} transazioni)"

        val start = currentPage * pageSize
        val end = minOf(start + pageSize, transactions.size)

        if (start >= transactions.size) {
            val emptyText = TextView(this)
            emptyText.text = "Nessuna transazione"
            emptyText.textSize = 16f
            emptyText.setPadding(16, 32, 16, 32)
            container.addView(emptyText)
            return
        }

        for (i in start until end) {
            val tx = transactions[i]
            val card = createTransactionCard(tx)
            container.addView(card)
        }
    }

    private fun showAddToAddressBookDialog(address: String) {
        val addressBookManager = AddressBookManager(this)
        val nameInput = EditText(this).apply { hint = "Nome contatto" }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 16, 48, 16)
            addView(nameInput)
        }
        
        AlertDialog.Builder(this)
            .setTitle("Aggiungi alla rubrica")
            .setMessage("Indirizzo:\n$address")
            .setView(layout)
            .setPositiveButton("Salva") { _, _ ->
                val name = nameInput.text.toString().ifEmpty { address.take(12) }
                if (addressBookManager.saveContact(name, address)) {
                    Toast.makeText(this, "Contatto salvato: $name", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this, "Errore salvataggio", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Annulla", null)
            .show()
    }

    private fun createTransactionCard(tx: TransactionInfo): LinearLayout {
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

        val tvDirection = TextView(this).apply {
            text = tx.direction
            textSize = 14f
            setTypeface(null, android.graphics.Typeface.BOLD)
            setTextColor(if (tx.direction.contains("RICEVUTO")) 0xFF2196F3.toInt() else 0xFFF44336.toInt())
            setTextIsSelectable(true)
        }

        val tvAmount = TextView(this).apply {
            text = "Importo: ${"%.6f".format(tx.amount)} XRP"
            textSize = 14f
            setTextIsSelectable(true)
        }

        val tvCounterparty = TextView(this).apply {
            text = if (tx.direction.contains("RICEVUTO")) "Da: ${tx.counterparty}" else "A: ${tx.counterparty}"
            textSize = 12f
            setTextIsSelectable(true)
            setTextColor(0xFF2196F3.toInt())
            
            setOnClickListener {
                showAddToAddressBookDialog(tx.counterparty)
            }
        }

        val tvMemo = TextView(this).apply {
            text = if (tx.memo.isNotEmpty()) "Memo: ${tx.memo}" else ""
            textSize = 12f
            setTextColor(0xFF666666.toInt())
            setTextIsSelectable(true)
        }

        val tvDate = TextView(this).apply {
            text = tx.date
            textSize = 12f
            setTextColor(0xFF666666.toInt())
            setTextIsSelectable(true)
        }

        val tvFee = TextView(this).apply {
            text = "Fee: ${"%.6f".format(tx.fee)} XRP"
            textSize = 10f
            setTextColor(0xFF999999.toInt())
            setTextIsSelectable(true)
        }

        val tvResult = TextView(this).apply {
            text = "Esito: ${if (tx.result == "tesSUCCESS") "✅ Successo" else "❌ ${tx.result}"}"
            textSize = 12f
            setTextIsSelectable(true)
        }

        val tvHash = TextView(this).apply {
            text = "Hash: ${tx.hash}"
            textSize = 10f
            setTextColor(0xFF999999.toInt())
            setTextIsSelectable(true)
        }

        val tvTag = TextView(this).apply {
            text = if (tx.destinationTag > 0) "Destination Tag: ${tx.destinationTag}" else ""
            textSize = 10f
            setTextColor(0xFF999999.toInt())
            setTextIsSelectable(true)
        }

        card.addView(tvDirection)
        card.addView(tvAmount)
        card.addView(tvCounterparty)
        if (tx.memo.isNotEmpty()) card.addView(tvMemo)
        card.addView(tvDate)
        card.addView(tvFee)
        card.addView(tvResult)
        if (tx.destinationTag > 0) card.addView(tvTag)
        card.addView(tvHash)

        return card
    }
}

data class TransactionInfo(
    val hash: String,
    val type: String,
    val direction: String,
    val amount: Double,
    val fee: Double,
    val date: String,
    val result: String,
    val from: String,
    val to: String,
    val counterparty: String,
    val memo: String,
    val destinationTag: Long
)