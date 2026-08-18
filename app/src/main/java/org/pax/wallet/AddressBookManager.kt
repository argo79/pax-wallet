package org.pax.wallet

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

data class Contact(
    val id: String,
    val name: String,
    val address: String,
    val crypto: String = "XRP",
    val isMainnet: Boolean = true,
    val createdAt: Long
)

class AddressBookManager(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("pax_address_book", Context.MODE_PRIVATE)
    private val contactsKey = "contacts_json"

    fun getContacts(): List<Contact> {
        return try {
            val json = prefs.getString(contactsKey, null) ?: return emptyList()
            val jsonArray = JSONArray(json)
            val contacts = mutableListOf<Contact>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                contacts.add(
                    Contact(
                        id = obj.optString("id", java.util.UUID.randomUUID().toString()),
                        name = obj.optString("name", "Contatto ${i + 1}"),
                        address = obj.getString("address"),
                        crypto = obj.optString("crypto", "XRP"),
                        isMainnet = obj.optBoolean("isMainnet", true),
                        createdAt = obj.getLong("createdAt")
                    )
                )
            }
            contacts
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun saveContact(name: String, address: String, crypto: String = "XRP", isMainnet: Boolean = true): Boolean {
        return try {
            val contacts = getContacts().toMutableList()
            val existing = contacts.find { it.address == address }
            if (existing != null) {
                val index = contacts.indexOf(existing)
                contacts[index] = existing.copy(name = name, crypto = crypto, isMainnet = isMainnet)
            } else {
                contacts.add(
                    Contact(
                        id = java.util.UUID.randomUUID().toString(),
                        name = name,
                        address = address,
                        crypto = crypto,
                        isMainnet = isMainnet,
                        createdAt = System.currentTimeMillis()
                    )
                )
            }
            saveAll(contacts)
            true
        } catch (e: Exception) {
            false
        }
    }

    fun deleteContact(id: String): Boolean {
        return try {
            val contacts = getContacts().toMutableList()
            val updated = contacts.filter { it.id != id }
            if (updated.size == contacts.size) return false
            saveAll(updated)
            true
        } catch (e: Exception) {
            false
        }
    }

    fun renameContact(id: String, newName: String): Boolean {
        return try {
            val contacts = getContacts().toMutableList()
            val index = contacts.indexOfFirst { it.id == id }
            if (index < 0) return false
            contacts[index] = contacts[index].copy(name = newName)
            saveAll(contacts)
            true
        } catch (e: Exception) {
            false
        }
    }

    fun getContactByAddress(address: String): Contact? {
        return getContacts().find { it.address == address }
    }

    private fun saveAll(contacts: List<Contact>) {
        val jsonArray = JSONArray()
        for (contact in contacts) {
            val obj = JSONObject()
            obj.put("id", contact.id)
            obj.put("name", contact.name)
            obj.put("address", contact.address)
            obj.put("crypto", contact.crypto)
            obj.put("isMainnet", contact.isMainnet)
            obj.put("createdAt", contact.createdAt)
            jsonArray.put(obj)
        }
        prefs.edit().putString(contactsKey, jsonArray.toString()).apply()
    }
}