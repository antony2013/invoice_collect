import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from "react-native";
import { getMyInvoice, getOrgInvoice, downloadFile, downloadOrgFile } from "../api";
import { Invoice, User } from "../types";
import { loadUser } from "../storage";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";

type Props = {
  invoiceId: string;
  onBack: () => void;
  onEdit?: (id: string) => void;
};

const STATUS_COLORS: Record<string, string> = {
  PENDING: "#F59E0B",
  PROCESSING: "#3B82F6",
  COMPLETED: "#10B981",
  REVIEW: "#8B5CF6",
  CANCELLED: "#EF4444",
};

export default function InvoiceDetailScreen({ invoiceId, onBack, onEdit }: Props) {
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [isWorker, setIsWorker] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const user: User | null = await loadUser();
        const worker = user?.role === "OWNER" || user?.role === "STAFF";
        setIsWorker(worker);
        const data = worker
          ? await getOrgInvoice(invoiceId)
          : await getMyInvoice(invoiceId);
        setInvoice(data);
      } catch (e: any) {
        Alert.alert("Error", e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [invoiceId]);

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
          <Text style={styles.backLink}>Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  async function handleDownload(fileId: string, fileName: string) {
    try {
      const uri = isWorker
        ? await downloadOrgFile(invoiceId, fileId)
        : await downloadFile(invoiceId, fileId);
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri);
      } else {
        Alert.alert("Saved", `File saved to ${uri}`);
      }
    } catch (e: any) {
      Alert.alert("Download failed", e.message);
    }
  }

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {invoice.invoice_number}
        </Text>
        {isWorker && onEdit ? (
          <TouchableOpacity onPress={() => onEdit(invoiceId)}>
            <Text style={styles.editText}>Edit</Text>
          </TouchableOpacity>
        ) : (
          <View style={{ width: 40 }} />
        )}
      </View>

      <ScrollView contentContainerStyle={styles.body}>
        <View style={styles.statusRow}>
          <Text style={styles.label}>Status</Text>
          <View
            style={[
              styles.badge,
              { backgroundColor: STATUS_COLORS[invoice.status] || "#9CA3AF" },
            ]}
          >
            <Text style={styles.badgeText}>{invoice.status}</Text>
          </View>
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Client</Text>
          <Text style={styles.value}>{invoice.client_name}</Text>
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Date</Text>
          <Text style={styles.value}>{invoice.invoice_date}</Text>
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Amount</Text>
          <Text style={styles.amount}>
            {invoice.currency} {invoice.total_amount}
          </Text>
        </View>

        {invoice.notes ? (
          <View style={styles.field}>
            <Text style={styles.label}>Notes</Text>
            <Text style={styles.value}>{invoice.notes}</Text>
          </View>
        ) : null}

        {invoice.assigned_to_name ? (
          <View style={styles.field}>
            <Text style={styles.label}>Assigned to</Text>
            <Text style={styles.value}>{invoice.assigned_to_name}</Text>
          </View>
        ) : null}

        {invoice.files && invoice.files.length > 0 && (
          <View style={{ marginTop: 16 }}>
            <Text style={[styles.label, { marginBottom: 10 }]}>Files</Text>
            {invoice.files.map((f) => (
              <TouchableOpacity
                key={f.id}
                style={styles.fileCard}
                onPress={() => handleDownload(f.id, f.original_name)}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.fileName} numberOfLines={1}>
                    {f.original_name}
                  </Text>
                  <Text style={styles.fileSize}>
                    {f.content_type} &middot;{" "}
                    {f.size_bytes > 1024 * 1024
                      ? `${(f.size_bytes / 1024 / 1024).toFixed(1)} MB`
                      : `${(f.size_bytes / 1024).toFixed(0)} KB`}
                  </Text>
                </View>
                <Text style={styles.downloadLink}>Open</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {invoice.items && invoice.items.length > 0 && (
          <View style={{ marginTop: 16 }}>
            <Text style={[styles.label, { marginBottom: 10 }]}>Items</Text>
            {invoice.items.map((it) => (
              <View key={it.id} style={styles.itemRow}>
                <Text style={{ flex: 1, color: "#374151" }}>
                  {it.description}
                </Text>
                <Text style={{ color: "#6B7280", marginLeft: 8 }}>
                  {it.quantity} x {it.unit_price}
                </Text>
                <Text
                  style={{ fontWeight: "600", marginLeft: 8, color: "#111827" }}
                >
                  {it.amount}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#F0F4F8",
  },
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
    fontSize: 16,
    fontWeight: "600",
    color: "#fff",
    flex: 1,
    textAlign: "center",
    marginHorizontal: 8,
  },
  backText: {
    color: "#93C5FD",
    fontSize: 15,
  },
  editText: {
    color: "#93C5FD",
    fontSize: 15,
    fontWeight: "600",
  },
  body: {
    padding: 20,
    paddingBottom: 40,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    marginLeft: 10,
  },
  badgeText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "600",
  },
  field: {
    marginBottom: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
    color: "#6B7280",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  value: {
    fontSize: 15,
    color: "#111827",
  },
  amount: {
    fontSize: 20,
    fontWeight: "700",
    color: "#111827",
  },
  fileCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#E5E7EB",
  },
  fileName: {
    fontSize: 14,
    fontWeight: "500",
    color: "#111827",
  },
  fileSize: {
    fontSize: 12,
    color: "#9CA3AF",
    marginTop: 2,
  },
  downloadLink: {
    color: "#2563EB",
    fontWeight: "600",
    fontSize: 13,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 8,
    padding: 12,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: "#E5E7EB",
  },
  emptyText: {
    fontSize: 15,
    color: "#6B7280",
    marginBottom: 8,
  },
  backLink: {
    color: "#2563EB",
    fontSize: 14,
    fontWeight: "500",
  },
});
