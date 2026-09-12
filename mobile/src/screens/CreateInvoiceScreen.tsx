import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
} from "react-native";
import { createInvoice, listClients } from "../api";
import { Client, InvoiceItemPayload } from "../types";

type Props = {
  onDone: () => void;
  onCancel: () => void;
};

export default function CreateInvoiceScreen({ onDone, onCancel }: Props) {
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().slice(0, 10));
  const [currency, setCurrency] = useState("USD");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<InvoiceItemPayload[]>([
    { description: "", quantity: "1", unit_price: "0" },
  ]);
  const [loadingClients, setLoadingClients] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listClients()
      .then(setClients)
      .catch((e) => Alert.alert("Error", e.message))
      .finally(() => setLoadingClients(false));
  }, []);

  function addItem() {
    setItems([...items, { description: "", quantity: "1", unit_price: "0" }]);
  }

  function removeItem(index: number) {
    if (items.length <= 1) return;
    setItems(items.filter((_, i) => i !== index));
  }

  function updateItem(index: number, field: keyof InvoiceItemPayload, value: string) {
    const updated = [...items];
    updated[index] = { ...updated[index], [field]: value };
    setItems(updated);
  }

  async function handleSubmit() {
    if (!selectedClientId) {
      Alert.alert("Error", "Please select a client");
      return;
    }
    if (!invoiceDate) {
      Alert.alert("Error", "Please enter an invoice date");
      return;
    }
    const validItems = items.filter((it) => it.description.trim());
    if (validItems.length === 0) {
      Alert.alert("Error", "Add at least one item with a description");
      return;
    }

    setSubmitting(true);
    try {
      await createInvoice({
        client_id: selectedClientId,
        invoice_date: invoiceDate,
        currency: currency.toUpperCase() || undefined,
        invoice_number: invoiceNumber || undefined,
        notes: notes || undefined,
        items: validItems.map((it) => ({
          description: it.description.trim(),
          quantity: it.quantity || "1",
          unit_price: it.unit_price || "0",
        })),
      });
      Alert.alert("Created", "Invoice created successfully", [
        { text: "OK", onPress: onDone },
      ]);
    } catch (e: any) {
      Alert.alert("Create Failed", e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.header}>
        <TouchableOpacity onPress={onCancel}>
          <Text style={styles.cancelText}>Cancel</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>New Invoice</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView contentContainerStyle={styles.body}>
        {loadingClients ? (
          <ActivityIndicator style={{ marginTop: 40 }} color="#2563EB" />
        ) : (
          <>
            <Text style={styles.label}>Client *</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
              {clients.map((c) => (
                <TouchableOpacity
                  key={c.id}
                  style={[
                    styles.chip,
                    selectedClientId === c.id && styles.chipActive,
                  ]}
                  onPress={() => setSelectedClientId(c.id)}
                >
                  <Text
                    style={[
                      styles.chipText,
                      selectedClientId === c.id && styles.chipTextActive,
                    ]}
                    numberOfLines={1}
                  >
                    {c.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <View style={styles.row}>
              <View style={{ flex: 1, marginRight: 8 }}>
                <Text style={styles.label}>Date *</Text>
                <TextInput
                  style={styles.input}
                  value={invoiceDate}
                  onChangeText={setInvoiceDate}
                  placeholder="YYYY-MM-DD"
                  keyboardType="numbers-and-punctuation"
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.label}>Currency</Text>
                <TextInput
                  style={styles.input}
                  value={currency}
                  onChangeText={(t) => setCurrency(t.toUpperCase())}
                  maxLength={3}
                  placeholder="USD"
                />
              </View>
            </View>

            <Text style={styles.label}>Invoice # (optional)</Text>
            <TextInput
              style={styles.input}
              value={invoiceNumber}
              onChangeText={setInvoiceNumber}
              placeholder="Auto-generated if blank"
            />

            <Text style={styles.label}>Notes</Text>
            <TextInput
              style={[styles.input, { minHeight: 60 }]}
              value={notes}
              onChangeText={setNotes}
              placeholder="Optional notes"
              multiline
              textAlignVertical="top"
            />

            <Text style={styles.label}>Line Items</Text>
            {items.map((it, i) => (
              <View key={i} style={styles.itemCard}>
                <View style={styles.itemRow}>
                  <TextInput
                    style={[styles.input, { flex: 1, marginRight: 8 }]}
                    value={it.description}
                    onChangeText={(t) => updateItem(i, "description", t)}
                    placeholder="Description *"
                  />
                  {items.length > 1 && (
                    <TouchableOpacity onPress={() => removeItem(i)}>
                      <Text style={styles.removeText}>X</Text>
                    </TouchableOpacity>
                  )}
                </View>
                <View style={styles.itemRow}>
                  <View style={{ flex: 1, marginRight: 8 }}>
                    <Text style={styles.itemMeta}>Qty</Text>
                    <TextInput
                      style={styles.input}
                      value={it.quantity}
                      onChangeText={(t) => updateItem(i, "quantity", t)}
                      keyboardType="numeric"
                    />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemMeta}>Unit Price</Text>
                    <TextInput
                      style={styles.input}
                      value={it.unit_price}
                      onChangeText={(t) => updateItem(i, "unit_price", t)}
                      keyboardType="decimal-pad"
                    />
                  </View>
                </View>
              </View>
            ))}
            <TouchableOpacity style={styles.addBtn} onPress={addItem}>
              <Text style={styles.addBtnText}>+ Add Item</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.submitBtn, submitting && styles.submitBtnDisabled]}
              onPress={handleSubmit}
              disabled={submitting}
            >
              {submitting ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.submitBtnText}>Create Invoice</Text>
              )}
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#F0F4F8" },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 56,
    paddingBottom: 16,
    paddingHorizontal: 20,
    backgroundColor: "#1A1A2E",
  },
  headerTitle: { fontSize: 18, fontWeight: "600", color: "#fff" },
  cancelText: { color: "#93C5FD", fontSize: 15 },
  body: { padding: 20, paddingBottom: 40 },
  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#374151",
    marginBottom: 6,
    marginTop: 8,
  },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D1D5DB",
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    marginBottom: 12,
    color: "#111827",
  },
  row: { flexDirection: "row", marginBottom: 4 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#fff",
    borderWidth: 1.5,
    borderColor: "#D1D5DB",
    marginRight: 8,
  },
  chipActive: { backgroundColor: "#2563EB", borderColor: "#2563EB" },
  chipText: { fontSize: 14, color: "#374151", fontWeight: "500" },
  chipTextActive: { color: "#fff" },
  itemCard: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#E5E7EB",
  },
  itemRow: { flexDirection: "row", alignItems: "center" },
  itemMeta: { fontSize: 11, color: "#6B7280", marginBottom: 2, marginTop: 4 },
  removeText: { color: "#EF4444", fontSize: 16, fontWeight: "700", paddingHorizontal: 6 },
  addBtn: {
    borderWidth: 1.5,
    borderColor: "#2563EB",
    borderStyle: "dashed",
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    marginBottom: 20,
  },
  addBtnText: { color: "#2563EB", fontWeight: "600", fontSize: 14 },
  submitBtn: {
    backgroundColor: "#059669",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 4,
  },
  submitBtnDisabled: { opacity: 0.5 },
  submitBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
