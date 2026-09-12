import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from "react-native";
import {
  getOrgInvoice,
  updateInvoice,
  deleteInvoice,
} from "../api";
import { Invoice, InvoiceItemPayload } from "../types";
import { loadUser } from "../storage";
import { User } from "../types";

type Props = {
  invoiceId: string;
  onDone: () => void;
  onBack: () => void;
};

const ALLOWED_TRANSITIONS: Record<Invoice["status"], Invoice["status"][]> = {
  PENDING: ["PROCESSING", "CANCELLED"],
  PROCESSING: ["COMPLETED", "REVIEW", "CANCELLED"],
  COMPLETED: ["REVIEW", "CANCELLED"],
  REVIEW: ["PROCESSING", "COMPLETED", "CANCELLED"],
  CANCELLED: [],
};

const STATUS_COLORS: Record<string, string> = {
  PENDING: "#F59E0B",
  PROCESSING: "#3B82F6",
  COMPLETED: "#10B981",
  REVIEW: "#8B5CF6",
  CANCELLED: "#EF4444",
};

export default function EditInvoiceScreen({ invoiceId, onDone, onBack }: Props) {
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [status, setStatus] = useState<Invoice["status"]>("PENDING");
  const [notes, setNotes] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [invoiceDate, setInvoiceDate] = useState("");
  const [items, setItems] = useState<InvoiceItemPayload[]>([]);
  const [isOwner, setIsOwner] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadInvoice = useCallback(async () => {
    try {
      const user = await loadUser();
      setIsOwner(user?.role === "OWNER");
      const inv = await getOrgInvoice(invoiceId);
      setInvoice(inv);
      setStatus(inv.status);
      setNotes(inv.notes || "");
      setCurrency(inv.currency);
      setInvoiceDate(inv.invoice_date);
      setItems(
        inv.items && inv.items.length > 0
          ? inv.items.map((it) => ({
              description: it.description,
              quantity: it.quantity,
              unit_price: it.unit_price,
            }))
          : [{ description: "", quantity: "1", unit_price: "0" }]
      );
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLoading(false);
    }
  }, [invoiceId]);

  useEffect(() => {
    loadInvoice();
  }, [loadInvoice]);

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

  async function handleSave() {
    if (!invoice) return;
    setSaving(true);
    try {
      const validItems = items
        .filter((it) => it.description.trim())
        .map((it) => ({
          description: it.description.trim(),
          quantity: it.quantity || "1",
          unit_price: it.unit_price || "0",
        }));
      await updateInvoice(invoiceId, {
        status,
        notes: notes || undefined,
        currency: currency.toUpperCase() || undefined,
        invoice_date: invoiceDate || undefined,
        items: validItems.length > 0 ? validItems : undefined,
      });
      Alert.alert("Saved", "Invoice updated", [{ text: "OK", onPress: onDone }]);
    } catch (e: any) {
      Alert.alert("Update Failed", e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    Alert.alert(
      "Delete Invoice",
      "Are you sure you want to delete this invoice and its items?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            setDeleting(true);
            try {
              await deleteInvoice(invoiceId);
              onDone();
            } catch (e: any) {
              Alert.alert("Delete Failed", e.message);
            } finally {
              setDeleting(false);
            }
          },
        },
      ]
    );
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563EB" />
      </View>
    );
  }

  if (!invoice) {
    return (
      <View style={styles.center}>
        <Text style={styles.emptyText}>Invoice not found.</Text>
        <TouchableOpacity onPress={onBack}>
          <Text style={styles.linkText}>Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>
          Edit: {invoice.invoice_number}
        </Text>
        {isOwner ? (
          <TouchableOpacity onPress={handleDelete} disabled={deleting}>
            <Text style={styles.deleteText}>
              {deleting ? "..." : "Delete"}
            </Text>
          </TouchableOpacity>
        ) : (
          <View style={{ width: 60 }} />
        )}
      </View>

      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.label}>Status</Text>
        <View style={styles.statusRow}>
          {[status, ...(ALLOWED_TRANSITIONS[status] ?? [])]
            .filter((s, i, arr) => arr.indexOf(s) === i)
            .map((s) => (
              <TouchableOpacity
                key={s}
                style={[
                  styles.statusBtn,
                  {
                    backgroundColor:
                      STATUS_COLORS[s] + (status === s ? "" : "33"),
                  },
                ]}
                onPress={() => setStatus(s)}
              >
                <Text
                  style={[
                    styles.statusBtnText,
                    { color: status === s ? "#fff" : "#374151" },
                  ]}
                >
                  {s}
                </Text>
              </TouchableOpacity>
            ))}
        </View>

        <View style={styles.row}>
          <View style={{ flex: 1, marginRight: 8 }}>
            <Text style={styles.label}>Date</Text>
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

        <Text style={styles.label}>Notes</Text>
        <TextInput
          style={[styles.input, { minHeight: 60 }]}
          value={notes}
          onChangeText={setNotes}
          placeholder="Notes"
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
                placeholder="Description"
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
          style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.saveBtnText}>Save Changes</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#F0F4F8" },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#F0F4F8",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 56,
    paddingBottom: 16,
    paddingHorizontal: 20,
    backgroundColor: "#1A1A2E",
  },
  headerTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: "#fff",
    flex: 1,
    textAlign: "center",
    marginHorizontal: 8,
  },
  backText: { color: "#93C5FD", fontSize: 15 },
  deleteText: { color: "#EF4444", fontSize: 14, fontWeight: "600" },
  body: { padding: 20, paddingBottom: 40 },
  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#374151",
    marginBottom: 6,
    marginTop: 10,
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
  statusRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 8 },
  statusBtn: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    marginRight: 6,
    marginBottom: 6,
  },
  statusBtnText: { fontSize: 12, fontWeight: "600" },
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
  removeText: {
    color: "#EF4444",
    fontSize: 16,
    fontWeight: "700",
    paddingHorizontal: 6,
  },
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
  saveBtn: {
    backgroundColor: "#2563EB",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 4,
  },
  saveBtnDisabled: { opacity: 0.5 },
  saveBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  emptyText: { fontSize: 15, color: "#6B7280", marginBottom: 8 },
  linkText: { color: "#2563EB", fontSize: 14, fontWeight: "500" },
});
