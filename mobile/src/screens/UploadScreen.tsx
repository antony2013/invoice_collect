import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { uploadInvoice } from "../api";

type Props = {
  onDone: () => void;
  onCancel: () => void;
  onScan: () => void;
};

export default function UploadScreen({ onDone, onCancel, onScan }: Props) {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [uploading, setUploading] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);

  async function openCamera() {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission needed",
        "Camera permission is required to take a photo."
      );
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      quality: 0.85,
      allowsEditing: false,
      exif: false,
    });

    if (!result.canceled && result.assets[0]) {
      setImageUri(result.assets[0].uri);
      setPreviewVisible(true);
    }
  }

  async function openGallery() {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission needed",
        "Photo library permission is required to pick an image."
      );
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      quality: 0.85,
      allowsEditing: false,
      exif: false,
      mediaTypes: ["images"],
    });

    if (!result.canceled && result.assets[0]) {
      setImageUri(result.assets[0].uri);
      setPreviewVisible(true);
    }
  }

  async function handleUpload() {
    if (!imageUri) {
      Alert.alert("Error", "Please take or select an invoice photo first.");
      return;
    }
    setUploading(true);
    try {
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const fileName = `invoice-${ts}.jpg`;
      await uploadInvoice(imageUri, fileName, notes || undefined);
      Alert.alert("Uploaded", "Your invoice has been uploaded successfully.", [
        { text: "OK", onPress: onDone },
      ]);
    } catch (e: any) {
      Alert.alert("Upload Failed", e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <TouchableOpacity onPress={onCancel}>
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Upload Invoice</Text>
          <View style={{ width: 60 }} />
        </View>

        <View style={styles.body}>
          {previewVisible && imageUri ? (
            <View style={styles.previewWrap}>
              <Image source={{ uri: imageUri }} style={styles.preview} />
              <TouchableOpacity
                style={styles.retakeBtn}
                onPress={() => {
                  setImageUri(null);
                  setPreviewVisible(false);
                }}
              >
                <Text style={styles.retakeText}>Retake</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.captureArea}>
              <Text style={styles.captureHint}>
                Take a photo or choose from gallery
              </Text>
              <View style={styles.captureButtons}>
                <TouchableOpacity
                  style={styles.captureBtn}
                  onPress={openCamera}
                >
                  <Text style={styles.captureBtnText}>Camera</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.captureBtn, styles.captureBtnAlt]}
                  onPress={openGallery}
                >
                  <Text style={[styles.captureBtnText, styles.captureBtnAltText]}>
                    Gallery
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          <TouchableOpacity style={styles.scanBtn} onPress={onScan}>
            <Text style={styles.scanBtnText}>Scan Multiple Pages</Text>
            <Text style={styles.scanBtnHint}>
              Capture several photos with the camera and combine them into one
              PDF file
            </Text>
          </TouchableOpacity>

          <Text style={styles.label}>Notes (optional)</Text>
          <TextInput
            style={styles.input}
            value={notes}
            onChangeText={setNotes}
            placeholder="Add any notes about this invoice..."
            multiline
            numberOfLines={3}
            textAlignVertical="top"
          />

          <TouchableOpacity
            style={[
              styles.uploadBtn,
              (!imageUri || uploading) && styles.uploadBtnDisabled,
            ]}
            onPress={handleUpload}
            disabled={!imageUri || uploading}
          >
            {uploading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.uploadBtnText}>Upload Invoice</Text>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#F0F4F8",
  },
  scroll: {
    flexGrow: 1,
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
  body: {
    padding: 20,
    flex: 1,
  },
  captureArea: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 32,
    alignItems: "center",
    borderWidth: 2,
    borderColor: "#D1D5DB",
    borderStyle: "dashed",
    marginBottom: 24,
  },
  captureHint: {
    fontSize: 14,
    color: "#6B7280",
    marginBottom: 16,
  },
  captureButtons: {
    flexDirection: "row",
    gap: 12,
  },
  captureBtn: {
    backgroundColor: "#2563EB",
    borderRadius: 10,
    paddingHorizontal: 24,
    paddingVertical: 14,
  },
  captureBtnText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 15,
  },
  captureBtnAlt: {
    backgroundColor: "#fff",
    borderWidth: 1.5,
    borderColor: "#2563EB",
  },
  captureBtnAltText: {
    color: "#2563EB",
  },
  previewWrap: {
    backgroundColor: "#fff",
    borderRadius: 12,
    overflow: "hidden",
    marginBottom: 24,
  },
  preview: {
    width: "100%",
    aspectRatio: 3 / 4,
    resizeMode: "contain",
    backgroundColor: "#F3F4F6",
  },
  retakeBtn: {
    padding: 14,
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
  },
  retakeText: {
    color: "#EF4444",
    fontWeight: "600",
    fontSize: 14,
  },
  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#374151",
    marginBottom: 6,
  },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D1D5DB",
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    marginBottom: 20,
    minHeight: 80,
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
  scanBtn: {
    backgroundColor: "#2563EB",
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    alignItems: "center",
  },
  scanBtnText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  scanBtnHint: {
    color: "#BFDBFE",
    fontSize: 12,
    marginTop: 4,
    textAlign: "center",
  },
});
