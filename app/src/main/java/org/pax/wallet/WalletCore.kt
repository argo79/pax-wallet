// WalletCore.kt
package org.pax.wallet

class WalletCore {
    companion object {
        init {
            System.loadLibrary("wallet_core")
        }
    }

    // Chiamate alle funzioni Rust del tuo core
    external fun generate_seed(): String
    external fun derive_address(seed: String, crypto_type: Int): String
    external fun get_balance(address: String, network: String): Long
    external fun sign_transaction(seed: String, tx_json: String): String
}