// MainActivity.kt
package org.pax.wallet

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var core: WalletCore
    private lateinit var tvAddress: TextView
    private lateinit var tvBalance: TextView
    private lateinit var etSeed: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        core = WalletCore()

        tvAddress = findViewById(R.id.address_label)
        tvBalance = findViewById(R.id.balance_label)
        etSeed = findViewById(R.id.et_seed)

        findViewById<Button>(R.id.btn_new_wallet).setOnClickListener {
            createNewWallet()
        }

        findViewById<Button>(R.id.btn_balance).setOnClickListener {
            updateBalance()
        }

        findViewById<Button>(R.id.btn_import).setOnClickListener {
            importWallet()
        }
    }

    private fun createNewWallet() {
        try {
            // Chiamata al core Rust
            val seed = core.generate_seed()
            val address = core.derive_address(seed, 0) // 0 = XRP, 1 = XLM

            tvAddress.text = "Indirizzo: $address"
            etSeed.setText(seed)

            Toast.makeText(this, "✅ Wallet creato!", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Toast.makeText(this, "❌ Errore: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun updateBalance() {
        try {
            val address = tvAddress.text.toString().replace("Indirizzo: ", "")
            if (address == "---") {
                Toast.makeText(this, "Crea prima un wallet", Toast.LENGTH_SHORT).show()
                return
            }

            val balance = core.get_balance(address, "testnet")
            tvBalance.text = "Saldo: $balance XRP"
        } catch (e: Exception) {
            Toast.makeText(this, "❌ Errore: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun importWallet() {
        val seed = etSeed.text.toString()
        if (seed.isEmpty()) {
            Toast.makeText(this, "Inserisci il seed", Toast.LENGTH_SHORT).show()
            return
        }

        try {
            val address = core.derive_address(seed, 0)
            tvAddress.text = "Indirizzo: $address"
            Toast.makeText(this, "✅ Wallet importato!", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Toast.makeText(this, "❌ Seed non valido", Toast.LENGTH_SHORT).show()
        }
    }
}