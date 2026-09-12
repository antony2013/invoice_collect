import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
} from "react-native";
import { listMyInvoices, listAllInvoices, setAuthToken } from "../api";
import { loadToken, clearToken, clearUser, loadUser } from "../storage";
import { Invoice } from "../types";

type Props = {
  onLogout: () => void;
  onCapture: () => void;
  onCreateInvoice: () => void;
  onInvoicePress: (id: string) => void;
};

const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Pending", value: "PENDING" },
  { label: "Processing", value: "PROCESSING" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Review", value: "REVIEW" },
  { label: "Cancelled", value: "CANCELLED" },
];

export default function HomeScreen({
  onLogout,
  onCapture,
  onCreateInvoice,
  onInvoicePress,
}: Props) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isWorker, setIsWorker] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");

  const fetchInvoices = useCallback(async () => {
    try {
      const token = await loadToken();
      setAuthToken(token);
      const user = await loadUser();
      const worker = user?.role === "OWNER" || user?.role === "STAFF";
      setIsWorker(worker);
      if (worker) {
        const res = await listAllInvoices(statusFilter || undefined);
        setInvoices(res.items);
      } else {
        const res = await listMyInvoices();
        setInvoices(res.items);
      }
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  function handleLogout() {
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Sign Out",
        style: "destructive",
        onPress: async () => {
          await clearToken();
          await clearUser();
          onLogout();
        },
      },
    ]);
  }

  const statusColor = (s: string) => {
    switch (s) {
      case "PENDING":
        return "#F59E0B";
      case "PROCESSING":
        return "#3B82F6";
      case "COMPLETED":
        return "#10B981";
      case "REVIEW":
        return "#8B5CF6";
      case "CANCELLED":
        return "#EF4444";
      default:
        return "#9CA3AF";
    }
  };

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {isWorker ? "All Invoices" : "My Invoices"}
        </Text>
        <TouchableOpacity onPress={handleLogout}>
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>
      </View>

      {isWorker && (
        <View style={styles.filterRow}>
          {STATUS_FILTERS.map((f) => (
            <TouchableOpacity
              key={f.value}
              style={[styles.filterChip, statusFilter === f.value && styles.filterChipActive]}
              onPress={() => setStatusFilter(f.value)}
            >
              <Text
                style={[styles.filterChipText, statusFilter === f.value && styles.filterChipTextActive]}
              >
                {f.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {loading ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>Loading...</Text>
        </View>
      ) : invoices.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>No invoices yet.</Text>
          <Text style={styles.emptyHint}>
            Tap the button below to upload your first invoice.
          </Text>
        </View>
      ) : (
        <FlatList
          data={invoices}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                fetchInvoices();
              }}
            />
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              onPress={() => onInvoicePress(item.id)}
            >
              <View style={styles.cardHeader}>
                <Text style={styles.invNumber} numberOfLines={1}>
                  {item.invoice_number}
                </Text>
                <View
                  style={[
                    styles.badge,
                    { backgroundColor: statusColor(item.status) },
                  ]}
                >
                  <Text style={styles.badgeText}>{item.status}</Text>
                </View>
              </View>
              <Text style={styles.clientName}>{item.client_name}</Text>
              <View style={styles.cardFooter}>
                <Text style={styles.date}>{item.invoice_date}</Text>
                <Text style={styles.amount}>
                  {item.currency} {item.total_amount}
                </Text>
              </View>
            </TouchableOpacity>
          )}
        />
      )}

      <TouchableOpacity
        style={styles.fab}
        onPress={isWorker ? onCreateInvoice : onCapture}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
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
    fontSize: 22,
    fontWeight: "700",
    color: "#fff",
  },
  logoutText: {
    color: "#93C5FD",
    fontSize: 14,
    fontWeight: "500",
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 2,
    gap: 6,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D1D5DB",
  },
  filterChipActive: { backgroundColor: "#2563EB", borderColor: "#2563EB" },
  filterChipText: { fontSize: 12, fontWeight: "500", color: "#374151" },
  filterChipTextActive: { color: "#fff" },
  list: {
    padding: 16,
    paddingBottom: 100,
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  invNumber: {
    fontSize: 15,
    fontWeight: "600",
    color: "#111827",
    flex: 1,
    marginRight: 8,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeText: {
    color: "#fff",
    fontSize: 11,
    fontWeight: "600",
  },
  clientName: {
    fontSize: 13,
    color: "#6B7280",
    marginBottom: 8,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  date: {
    fontSize: 12,
    color: "#9CA3AF",
  },
  amount: {
    fontSize: 14,
    fontWeight: "600",
    color: "#111827",
  },
  empty: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 32,
  },
  emptyText: {
    fontSize: 16,
    color: "#6B7280",
    marginBottom: 4,
  },
  emptyHint: {
    fontSize: 13,
    color: "#9CA3AF",
    textAlign: "center",
  },
  fab: {
    position: "absolute",
    bottom: 32,
    right: 24,
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#2563EB",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#2563EB",
    shadowOpacity: 0.3,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  fabText: {
    color: "#fff",
    fontSize: 32,
    fontWeight: "300",
    marginTop: -2,
  },
});
