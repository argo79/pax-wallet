package org.pax.wallet

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import com.google.gson.Gson
import com.google.gson.JsonObject
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager
import javax.net.ssl.HttpsURLConnection

// XRPL4J 6.0.0
import org.xrpl.xrpl4j.client.XrplClient
import org.xrpl.xrpl4j.crypto.keys.Seed
import org.xrpl.xrpl4j.crypto.keys.Base58EncodedSecret
import org.xrpl.xrpl4j.crypto.signing.SingleSignedTransaction
import org.xrpl.xrpl4j.crypto.signing.bc.BcSignatureService
import org.xrpl.xrpl4j.model.transactions.Payment
import org.xrpl.xrpl4j.model.transactions.XrpCurrencyAmount
import org.xrpl.xrpl4j.model.transactions.Address
import org.xrpl.xrpl4j.model.transactions.Memo
import org.xrpl.xrpl4j.model.transactions.MemoWrapper
import com.google.common.primitives.UnsignedInteger
import okhttp3.HttpUrl
import java.math.BigDecimal
import java.util.Base64

class XRPManager {

    companion object {
        private const val TAG = "XRPManager"
        private const val MAINNET_URL = "https://s1.ripple.com:51234/"
        private const val TESTNET_URL = "https://s.altnet.rippletest.net:51234/"
    }

    private var useMainnet = false
    private val gson = Gson()
    private val client = createUnsafeClient()
    private lateinit var xrplClient: XrplClient

    init {
        installTrustAllCertificates()
    }

    private fun installTrustAllCertificates() {
        try {
            val trustAllCerts = arrayOf<TrustManager>(object : X509TrustManager {
                override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
            })
            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(null, trustAllCerts, SecureRandom())
            HttpsURLConnection.setDefaultSSLSocketFactory(sslContext.socketFactory)
            HttpsURLConnection.setDefaultHostnameVerifier { _, _ -> true }
            Log.d(TAG, "Trust all certificates installed globally.")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to install trust all certificates", e)
        }
    }

    fun setNetwork(mainnet: Boolean) {
        useMainnet = mainnet
        val httpUrl = HttpUrl.Builder()
            .scheme("https")
            .host(if (mainnet) "s1.ripple.com" else "s.altnet.rippletest.net")
            .port(51234)
            .build()
        xrplClient = XrplClient(httpUrl)
        Log.d(TAG, "Network set to ${if (mainnet) "MAINNET" else "TESTNET"}")
    }

    private fun getServerUrl(): String {
        return if (useMainnet) MAINNET_URL else TESTNET_URL
    }

    private fun createUnsafeClient(): OkHttpClient {
        return try {
            val trustAllCerts = arrayOf<TrustManager>(object : X509TrustManager {
                override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
            })

            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(null, trustAllCerts, SecureRandom())

            OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .sslSocketFactory(sslContext.socketFactory, trustAllCerts[0] as X509TrustManager)
                .hostnameVerifier { _, _ -> true }
                .build()
        } catch (e: Exception) {
            Log.e(TAG, "Error creating unsafe client", e)
            OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .build()
        }
    }

    suspend fun getBalance(address: String): String {
        return withContext(Dispatchers.IO) {
            try {
                val requestBody = """
                    {
                        "method": "account_info",
                        "params": [{
                            "account": "$address",
                            "strict": true,
                            "ledger_index": "current"
                        }]
                    }
                """.trimIndent()

                val body = requestBody.toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(getServerUrl())
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()
                val responseBody = response.body?.string()

                if (responseBody != null) {
                    val json = gson.fromJson(responseBody, JsonObject::class.java)
                    val result = json.getAsJsonObject("result")

                    if (result != null) {
                        val accountData = result.getAsJsonObject("account_data")
                        if (accountData != null) {
                            val balanceDrops = accountData.get("Balance")?.asString ?: "0"
                            return@withContext (balanceDrops.toDouble() / 1_000_000).toString()
                        }
                    }
                }

                "0"
            } catch (e: Exception) {
                Log.e(TAG, "Errore getBalance: ${e.message}")
                "0"
            }
        }
    }

    suspend fun getAccountInfo(address: String): JsonObject? {
        return withContext(Dispatchers.IO) {
            try {
                val requestBody = """
                    {
                        "method": "account_info",
                        "params": [{
                            "account": "$address",
                            "strict": true,
                            "ledger_index": "current"
                        }]
                    }
                """.trimIndent()

                val body = requestBody.toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(getServerUrl())
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()
                val responseBody = response.body?.string()

                if (responseBody != null) {
                    val json = gson.fromJson(responseBody, JsonObject::class.java)
                    json.getAsJsonObject("result")
                } else {
                    null
                }
            } catch (e: Exception) {
                Log.e(TAG, "Errore getAccountInfo: ${e.message}")
                null
            }
        }
    }

    suspend fun getAccountSequence(address: String): Int {
        return withContext(Dispatchers.IO) {
            try {
                val accountInfo = getAccountInfo(address)
                val sequence = accountInfo?.getAsJsonObject("account_data")?.get("Sequence")?.asInt ?: 0
                sequence
            } catch (e: Exception) {
                Log.e(TAG, "Errore getAccountSequence: ${e.message}")
                0
            }
        }
    }

    suspend fun getLastLedgerSequence(): Int {
        return withContext(Dispatchers.IO) {
            try {
                val requestBody = """
                    {
                        "method": "ledger",
                        "params": [{
                            "ledger_index": "validated"
                        }]
                    }
                """.trimIndent()

                val body = requestBody.toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(getServerUrl())
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()
                val responseBody = response.body?.string()

                if (responseBody != null) {
                    val json = gson.fromJson(responseBody, JsonObject::class.java)
                    val result = json.getAsJsonObject("result")
                    val ledgerIndex = result?.getAsJsonObject("ledger")?.get("ledger_index")?.asInt ?: 0
                    return@withContext ledgerIndex + 10
                }

                0
            } catch (e: Exception) {
                Log.e(TAG, "Errore getLastLedgerSequence: ${e.message}")
                0
            }
        }
    }

    suspend fun fundTestnet(address: String): String {
        return withContext(Dispatchers.IO) {
            try {
                val body = """{"destination": "$address"}"""
                    .toRequestBody("application/json".toMediaType())

                val request = Request.Builder()
                    .url("https://faucet.altnet.rippletest.net/accounts")
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()
                val responseBody = response.body?.string()

                if (responseBody != null) {
                    val json = gson.fromJson(responseBody, JsonObject::class.java)
                    val txId = json.get("txId")?.asString ?: "N/A"
                    return@withContext txId
                }

                "Errore"
            } catch (e: Exception) {
                Log.e(TAG, "Errore fundTestnet: ${e.message}")
                "Errore: ${e.message}"
            }
        }
    }

    suspend fun getTransactionHistory(address: String, limit: Int = 100): String {
        return withContext(Dispatchers.IO) {
            try {
                val requestBody = """
                    {
                        "method": "account_tx",
                        "params": [{
                            "account": "$address",
                            "ledger_index_min": -1,
                            "ledger_index_max": -1,
                            "limit": $limit,
                            "forward": false
                        }]
                    }
                """.trimIndent()

                val body = requestBody.toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(getServerUrl())
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()
                val responseBody = response.body?.string()

                responseBody ?: """{"error": "No response"}"""
            } catch (e: Exception) {
                Log.e(TAG, "Errore getTransactionHistory: ${e.message}")
                """{"error": "${e.message}"}"""
            }
        }
    }

    // ============================================================
    // METODO CORRETTO PER INVIARE PAGAMENTI CON MEMO
    // ============================================================
    suspend fun sendPayment(
        seedXrp: String,
        account: String,
        destination: String,
        amountXrp: Double,
        memo: String? = null,
        feeDrops: Long = 12,
        sequence: Int,
        lastLedgerSequence: Int
    ): String {
        return withContext(Dispatchers.IO) {
            try {
                Log.d(TAG, "=== INVIO XRP su ${if (useMainnet) "MAINNET" else "TESTNET"} ===")
                Log.d(TAG, "Account: $account -> Destination: $destination")
                Log.d(TAG, "Amount: $amountXrp XRP, Memo: $memo")

                // 1. Deriva chiavi dal seed
                val seed = Seed.fromBase58EncodedSecret(Base58EncodedSecret.of(seedXrp))
                val keyPair = seed.deriveKeyPair()

                // 2. Costruisci la transazione Payment
                val paymentBuilder = Payment.builder()
                    .account(Address.of(account))
                    .amount(XrpCurrencyAmount.ofXrp(BigDecimal.valueOf(amountXrp)))
                    .destination(Address.of(destination))
                    .sequence(UnsignedInteger.valueOf(sequence.toLong()))
                    .fee(XrpCurrencyAmount.ofDrops(feeDrops))
                    .signingPublicKey(keyPair.publicKey())
                    .lastLedgerSequence(UnsignedInteger.valueOf(lastLedgerSequence.toLong()))

                // 3. Aggiungi memo se presente
                if (memo != null && memo.isNotEmpty()) {
                    try {
                        // Codifica il memo in Base64 come da standard XRP
                        val memoBase64 = Base64.getEncoder().encodeToString(memo.toByteArray(Charsets.UTF_8))
                        
                        val memoWrapper = MemoWrapper.builder()
                            .memo(
                                Memo.builder()
                                    .memoData(memoBase64)
                                    .memoFormat("text/plain")
                                    .build()
                            )
                            .build()
                        
                        paymentBuilder.memos(listOf(memoWrapper))
                        Log.d(TAG, "Memo aggiunto: $memo -> $memoBase64")
                    } catch (e: Exception) {
                        Log.e(TAG, "Errore aggiunta memo: ${e.message}")
                        // Continuiamo anche se il memo fallisce
                    }
                }

                val payment = paymentBuilder.build()

                // 4. Firma la transazione
                val signatureService = BcSignatureService()
                val signedPayment: SingleSignedTransaction<Payment> = signatureService.sign(
                    keyPair.privateKey(),
                    payment
                )

                // 5. Invia al network
                val result = xrplClient.submit(signedPayment)

                val response = buildString {
                    appendLine("✅ Inviato su ${if (useMainnet) "MAINNET" else "TESTNET"}!")
                    appendLine("Hash: ${signedPayment.hash()}")
                    appendLine("Engine Result: ${result.engineResult()}")
                    if (result.engineResult() == "tesSUCCESS") {
                        appendLine("✅ Transazione confermata!")
                    } else {
                        appendLine("⚠️ Result: ${result.engineResultMessage()}")
                    }
                    if (memo != null && memo.isNotEmpty()) {
                        appendLine("Memo: $memo")
                    }
                }

                return@withContext response

            } catch (e: Exception) {
                Log.e(TAG, "Errore sendPayment: ${e.message}", e)
                "ERROR: ${e.message}"
            }
        }
    }

    // ============================================================
    // METODO SEMPLIFICATO PER INVIARE PAGAMENTI (senza memo)
    // ============================================================
    suspend fun sendPaymentSimple(
        seedXrp: String,
        account: String,
        destination: String,
        amountXrp: Double,
        feeDrops: Long = 12,
        sequence: Int,
        lastLedgerSequence: Int
    ): String {
        return sendPayment(seedXrp, account, destination, amountXrp, null, feeDrops, sequence, lastLedgerSequence)
    }
}