import React, { useCallback, useRef, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  Image,
  Alert,
  ActivityIndicator,
} from "react-native";
import { CameraView, CameraType, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { ScanPage } from "../types";

type Props = {
  onDone: (pages: ScanPage[]) => void;
  onCancel: () => void;
};

const FLASH_MODES: Array<"off" | "on" | "auto"> = ["off", "on", "auto"];

function getImageSize(uri: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    Image.getSize(
      uri,
      (width, height) => resolve({ width, height }),
      (err) => reject(err)
    );
  });
}

export default function ScanScreen({ onDone, onCancel }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [facing, setFacing] = useState<CameraType>("back");
  const [flash, setFlash] = useState<"off" | "on" | "auto">("off");
  const [pages, setPages] = useState<ScanPage[]>([]);
  const [capturing, setCapturing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);

  const addPages = useCallback((uris: { uri: string; width: number; height: number }[]) => {
    setPages((prev) => [
      ...prev,
      ...uris.map((u) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        uri: u.uri,
        width: u.width,
        height: u.height,
        rotation: 0,
      })),
    ]);
  }, []);

  const handleCapture = useCallback(async () => {
    if (!cameraReady || capturing) return;
    setCapturing(true);
    try {
      const photo = await cameraRef.current?.takePictureAsync({ quality: 1 });
      if (photo) {
        addPages([{ uri: photo.uri, width: photo.width, height: photo.height }]);
      }
    } catch (e: any) {
      Alert.alert("Error", e.message || "Failed to capture photo.");
    } finally {
      setCapturing(false);
    }
  }, [cameraReady, capturing, addPages]);

  const handleImport = useCallback(async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission needed",
        "Photo library permission is required to add existing images."
      );
      return;
    }
    setImporting(true);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 1,
        allowsMultipleSelection: true,
        selectionLimit: 10,
      });
      if (!result.canceled && result.assets.length > 0) {
        const sized: { uri: string; width: number; height: number }[] = [];
        for (const asset of result.assets) {
          try {
            const dims = await getImageSize(asset.uri);
            sized.push({ uri: asset.uri, ...dims });
          } catch {
            sized.push({ uri: asset.uri, width: 1000, height: 1400 });
          }
        }
        addPages(sized);
      }
    } catch (e: any) {
      Alert.alert("Error", e.message || "Failed to import images.");
    } finally {
      setImporting(false);
    }
  }, [addPages]);

  const toggleFlash = useCallback(() => {
    setFlash((f) => FLASH_MODES[(FLASH_MODES.indexOf(f) + 1) % FLASH_MODES.length]);
  }, []);

  const toggleFacing = useCallback(() => {
    setFacing((c) => (c === "back" ? "front" : "back"));
  }, []);

  if (!permission) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color="#2563EB" />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centered}>
        <Text style={styles.permText}>
          Camera access is needed to scan invoice pages.
        </Text>
        <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
          <Text style={styles.permBtnText}>Grant Camera Access</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.permCancel} onPress={onCancel}>
          <Text style={styles.permCancelText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <TouchableOpacity onPress={onCancel} style={styles.headerBtn}>
          <Text style={styles.headerBtnText}>Cancel</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Scan Invoice</Text>
        <TouchableOpacity
          onPress={() => onDone(pages)}
          style={styles.headerBtn}
          disabled={pages.length === 0}
        >
          <Text
            style={[
              styles.headerBtnText,
              styles.doneText,
              pages.length === 0 && styles.doneTextDisabled,
            ]}
          >
            Done
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.cameraWrap}>
        <CameraView
          ref={cameraRef}
          style={styles.camera}
          facing={facing}
          flash={flash}
          onCameraReady={() => setCameraReady(true)}
        />
        <View style={styles.pageCountBadge}>
          <Text style={styles.pageCountText}>{pages.length} page{pages.length === 1 ? "" : "s"}</Text>
        </View>
      </View>

      <View style={styles.thumbStrip}>
        {pages.length === 0 ? (
          <Text style={styles.thumbHint}>Captured pages appear here</Text>
        ) : (
          <FlatList
            data={pages}
            keyExtractor={(item) => item.id}
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.thumbList}
            renderItem={({ item, index }) => (
              <View style={styles.thumbWrap}>
                <Image source={{ uri: item.uri }} style={styles.thumb} />
                <Text style={styles.thumbIndex}>{index + 1}</Text>
              </View>
            )}
          />
        )}
      </View>

      <View style={styles.controls}>
        <TouchableOpacity style={styles.sideBtn} onPress={toggleFacing}>
          <Text style={styles.sideBtnText}>Flip</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.captureBtn, (capturing || !cameraReady) && styles.captureBtnDisabled]}
          onPress={handleCapture}
          disabled={capturing || !cameraReady}
        >
          {capturing ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <View style={styles.captureInner} />
          )}
        </TouchableOpacity>
        <TouchableOpacity style={styles.sideBtn} onPress={toggleFlash}>
          <Text style={styles.sideBtnText}>
            {flash === "off" ? "Flash" : flash === "on" ? "On" : "Auto"}
          </Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity
        style={[styles.importBtn, importing && styles.importBtnDisabled]}
        onPress={handleImport}
        disabled={importing}
      >
        {importing ? (
          <ActivityIndicator color="#2563EB" />
        ) : (
          <Text style={styles.importBtnText}>Add from Gallery</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#000",
  },
  centered: {
    flex: 1,
    backgroundColor: "#F0F4F8",
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
  },
  permText: {
    fontSize: 15,
    color: "#374151",
    textAlign: "center",
    marginBottom: 20,
  },
  permBtn: {
    backgroundColor: "#2563EB",
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 14,
    marginBottom: 12,
  },
  permBtnText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
  permCancel: {
    padding: 8,
  },
  permCancelText: {
    color: "#6B7280",
    fontSize: 14,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#1A1A2E",
    paddingTop: 52,
    paddingBottom: 12,
    paddingHorizontal: 16,
  },
  headerBtn: {
    minWidth: 72,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#fff",
  },
  headerBtnText: {
    color: "#93C5FD",
    fontSize: 15,
  },
  doneText: {
    color: "#4ADE80",
    fontWeight: "600",
  },
  doneTextDisabled: {
    color: "#4B5563",
  },
  cameraWrap: {
    flex: 1,
  },
  camera: {
    flex: 1,
  },
  pageCountBadge: {
    position: "absolute",
    top: 16,
    left: 16,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
    zIndex: 1,
  },
  pageCountText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "600",
  },
  thumbStrip: {
    backgroundColor: "#111827",
    height: 96,
    justifyContent: "center",
  },
  thumbHint: {
    color: "#6B7280",
    fontSize: 12,
    textAlign: "center",
  },
  thumbList: {
    paddingHorizontal: 12,
    alignItems: "center",
  },
  thumbWrap: {
    marginRight: 10,
  },
  thumb: {
    width: 56,
    height: 72,
    borderRadius: 6,
    backgroundColor: "#1F2937",
  },
  thumbIndex: {
    color: "#9CA3AF",
    fontSize: 10,
    textAlign: "center",
    marginTop: 2,
  },
  controls: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    backgroundColor: "#111827",
    paddingVertical: 16,
    paddingHorizontal: 24,
  },
  sideBtn: {
    padding: 12,
  },
  sideBtnText: {
    color: "#E5E7EB",
    fontSize: 14,
    fontWeight: "600",
  },
  captureBtn: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    borderColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
  },
  captureBtnDisabled: {
    opacity: 0.4,
  },
  captureInner: {
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: "#fff",
  },
  importBtn: {
    backgroundColor: "#fff",
    paddingVertical: 14,
    alignItems: "center",
  },
  importBtnDisabled: {
    opacity: 0.6,
  },
  importBtnText: {
    color: "#2563EB",
    fontSize: 15,
    fontWeight: "600",
  },
});