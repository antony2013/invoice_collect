import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  Image,
  Alert,
  ActivityIndicator,
  TextInput,
  ScrollView,
} from "react-native";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as Print from "expo-print";
import { File, Paths } from "expo-file-system";
import { uploadInvoice } from "../api";
import { ScanPage } from "../types";

type Props = {
  pages: ScanPage[];
  onDone: () => void;
  onCancel: () => void;
};

const MAX_LONG_EDGE = 1800;
const JPEG_QUALITY = 0.9;
const PDF_WIDTH = 595;
const PDF_HEIGHT = 842;

function rotateLabel(rotation: number): string {
  return `${rotation}°`;
}

async function generatePdf(images: { uri: string; rotation: number; width: number; height: number }[]) {
  const pageHtml: string[] = [];
  for (const img of images) {
    const context = ImageManipulator.manipulate(img.uri);
    if (img.rotation !== 0) {
      context.rotate(img.rotation);
    }
    const swapped = img.rotation % 180 !== 0;
    const w = swapped ? img.height : img.width;
    const h = swapped ? img.width : img.height;
    if (Math.max(w, h) > MAX_LONG_EDGE) {
      if (w >= h) {
        context.resize({ width: MAX_LONG_EDGE, height: null });
      } else {
        context.resize({ width: null, height: MAX_LONG_EDGE });
      }
    }
    const imageRef = await context.renderAsync();
    const result = await imageRef.saveAsync({
      format: SaveFormat.JPEG,
      compress: JPEG_QUALITY,
      base64: true,
    });
    pageHtml.push(
      `<div style="page-break-after: always;" class="page"><img src="data:image/jpeg;base64,${result.base64}" alt="" /></div>`
    );
  }

  const html = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      @page { size: A4; margin: 0; }
      html, body { margin: 0; padding: 0; }
      .page { text-align: center; }
      img { width: 100%; height: auto; display: block; }
    </style>
  </head>
  <body>
    ${pageHtml.join("\n    ")}
  </body>
</html>`;

  const { uri } = await Print.printToFileAsync({
    html,
    width: PDF_WIDTH,
    height: PDF_HEIGHT,
  });
  return uri;
}

export default function ScanReviewScreen({ pages, onDone, onCancel }: Props) {
  const [items, setItems] = useState<ScanPage[]>(pages);
  const [notes, setNotes] = useState("");
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState("");

  const handleRotate = (id: string) => {
    setItems((prev) =>
      prev.map((p) =>
        p.id === id ? { ...p, rotation: (p.rotation + 90) % 360 } : p
      )
    );
  };

  const handleDelete = (id: string) => {
    setItems((prev) => prev.filter((p) => p.id !== id));
  };

  const handleCreate = async () => {
    if (items.length === 0) {
      Alert.alert("Error", "Add at least one page first.");
      return;
    }
    setProcessing(true);
    try {
      setProgress("Optimizing pages...");
      const pdfUri = await generatePdf(items);

      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const fileName = `invoice-scan-${ts}.pdf`;
      const dest = new File(Paths.cache, fileName);
      await new File(pdfUri).copy(dest);

      setProgress("Uploading...");
      await uploadInvoice(dest.uri, fileName, notes || undefined);

      Alert.alert("Uploaded", "Your scanned invoice (PDF) has been uploaded.", [
        { text: "OK", onPress: onDone },
      ]);
    } catch (e: any) {
      Alert.alert("Upload Failed", e.message);
    } finally {
      setProcessing(false);
      setProgress("");
    }
  };

  const renderPage = ({ item, index }: { item: ScanPage; index: number }) => (
    <View style={styles.pageCard}>
      <View style={styles.pageImgWrap}>
        <Image
          source={{ uri: item.uri }}
          style={[
            styles.pageImg,
            item.rotation !== 0 && {
              transform: [{ rotate: `${item.rotation}deg` }],
            },
          ]}
          resizeMode="contain"
        />
        <View style={styles.pageNumBadge}>
          <Text style={styles.pageNumText}>{index + 1}</Text>
        </View>
      </View>
      <View style={styles.pageActions}>
        <TouchableOpacity
          style={styles.pageActionBtn}
          onPress={() => handleRotate(item.id)}
          disabled={processing}
        >
          <Text style={styles.pageActionText}>Rotate {rotateLabel(item.rotation)}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.pageActionBtn, styles.deleteBtn]}
          onPress={() => handleDelete(item.id)}
          disabled={processing}
        >
          <Text style={styles.deleteText}>Delete</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <TouchableOpacity onPress={onCancel} disabled={processing}>
          <Text style={styles.cancelText}>Cancel</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Review Pages</Text>
        <View style={{ width: 60 }} />
      </View>

      {items.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>No pages left.</Text>
          <Text style={styles.emptyHint}>Go back to add pages, or cancel.</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          numColumns={2}
          columnWrapperStyle={styles.column}
          contentContainerStyle={styles.grid}
          renderItem={renderPage}
        />
      )}

      <View style={styles.footer}>
        <Text style={styles.label}>Notes (optional)</Text>
        <TextInput
          style={styles.input}
          value={notes}
          onChangeText={setNotes}
          placeholder="Add any notes about this invoice..."
          multiline
          numberOfLines={2}
          textAlignVertical="top"
          editable={!processing}
        />
        <TouchableOpacity
          style={[
            styles.uploadBtn,
            (items.length === 0 || processing) && styles.uploadBtnDisabled,
          ]}
          onPress={handleCreate}
          disabled={items.length === 0 || processing}
        >
          {processing ? (
            <View style={styles.processingWrap}>
              <ActivityIndicator color="#fff" />
              <Text style={styles.processingText}>
                {progress || "Processing..."}
              </Text>
            </View>
          ) : (
            <Text style={styles.uploadBtnText}>
              {items.length > 0
                ? `Create PDF & Upload (${items.length} page${items.length === 1 ? "" : "s"})`
                : "Create PDF & Upload"}
            </Text>
          )}
        </TouchableOpacity>
      </View>
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
    fontSize: 18,
    fontWeight: "600",
    color: "#fff",
  },
  cancelText: {
    color: "#93C5FD",
    fontSize: 15,
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
  grid: {
    padding: 12,
    paddingBottom: 20,
  },
  column: {
    gap: 12,
    marginBottom: 12,
  },
  pageCard: {
    flex: 1,
    backgroundColor: "#fff",
    borderRadius: 12,
    overflow: "hidden",
  },
  pageImgWrap: {
    width: "100%",
    height: 180,
    backgroundColor: "#F3F4F6",
  },
  pageImg: {
    width: "100%",
    height: "100%",
  },
  pageNumBadge: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: "rgba(17,24,39,0.75)",
    borderRadius: 12,
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  pageNumText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "700",
  },
  pageActions: {
    flexDirection: "row",
  },
  pageActionBtn: {
    flex: 1,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: "#EFF6FF",
  },
  pageActionText: {
    color: "#2563EB",
    fontSize: 13,
    fontWeight: "600",
  },
  deleteBtn: {
    backgroundColor: "#FEF2F2",
  },
  deleteText: {
    color: "#EF4444",
    fontSize: 13,
    fontWeight: "600",
  },
  footer: {
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 28,
  },
  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#374151",
    marginBottom: 6,
  },
  input: {
    backgroundColor: "#F9FAFB",
    borderWidth: 1,
    borderColor: "#D1D5DB",
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    marginBottom: 12,
    minHeight: 60,
    color: "#111827",
  },
  uploadBtn: {
    backgroundColor: "#059669",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
  },
  uploadBtnDisabled: {
    opacity: 0.5,
  },
  uploadBtnText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  processingWrap: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  processingText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
});