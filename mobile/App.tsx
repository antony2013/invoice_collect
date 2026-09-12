import React, { useState, useEffect, useCallback } from "react";
import { StatusBar } from "expo-status-bar";
import { setAuthToken, setBaseUrl } from "./src/api";
import { loadToken, loadUser, loadUrl, clearToken, clearUser } from "./src/storage";
import { ScanPage, User } from "./src/types";
import LoginScreen from "./src/screens/LoginScreen";
import HomeScreen from "./src/screens/HomeScreen";
import UploadScreen from "./src/screens/UploadScreen";
import InvoiceDetailScreen from "./src/screens/InvoiceDetailScreen";
import CreateInvoiceScreen from "./src/screens/CreateInvoiceScreen";
import EditInvoiceScreen from "./src/screens/EditInvoiceScreen";
import ScanScreen from "./src/screens/ScanScreen";
import ScanReviewScreen from "./src/screens/ScanReviewScreen";

type Screen =
  | "loading"
  | "login"
  | "home"
  | "upload"
  | "create"
  | "scan"
  | { screen: "detail"; id: string }
  | { screen: "edit"; id: string }
  | { screen: "scanReview"; pages: ScanPage[] };

export default function App() {
  const [screen, setScreen] = useState<Screen>("loading");
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    (async () => {
      const url = await loadUrl();
      if (url) setBaseUrl(url);

      const token = await loadToken();
      const storedUser = await loadUser();

      if (token && storedUser) {
        setAuthToken(token);
        setUser(storedUser);
        setScreen("home");
      } else {
        setScreen("login");
      }
    })();
  }, []);

  const onLogin = useCallback(() => {
    loadUser().then((u) => {
      if (u) setUser(u);
      setScreen("home");
    });
  }, []);

  const onLogout = useCallback(() => {
    setScreen("login");
    setUser(null);
  }, []);

  if (screen === "loading") {
    return null;
  }

  if (screen === "login") {
    return (
      <>
        <StatusBar style="light" />
        <LoginScreen onLogin={onLogin} />
      </>
    );
  }

  if (screen === "upload") {
    return (
      <>
        <StatusBar style="light" />
        <UploadScreen
          onDone={() => setScreen("home")}
          onCancel={() => setScreen("home")}
          onScan={() => setScreen("scan")}
        />
      </>
    );
  }

  if (screen === "scan") {
    return (
      <>
        <StatusBar style="light" />
        <ScanScreen
          onCancel={() => setScreen("home")}
          onDone={(pages) => setScreen({ screen: "scanReview", pages })}
        />
      </>
    );
  }

  if (screen === "create") {
    return (
      <>
        <StatusBar style="light" />
        <CreateInvoiceScreen
          onDone={() => setScreen("home")}
          onCancel={() => setScreen("home")}
        />
      </>
    );
  }

  if (typeof screen === "object" && screen.screen === "scanReview") {
    return (
      <>
        <StatusBar style="light" />
        <ScanReviewScreen
          pages={screen.pages}
          onDone={() => setScreen("home")}
          onCancel={() => setScreen("home")}
        />
      </>
    );
  }

  if (typeof screen === "object" && screen.screen === "edit") {
    return (
      <>
        <StatusBar style="light" />
        <EditInvoiceScreen
          invoiceId={screen.id}
          onDone={() => setScreen("home")}
          onBack={() => setScreen({ screen: "detail", id: screen.id })}
        />
      </>
    );
  }

  if (typeof screen === "object" && screen.screen === "detail") {
    return (
      <>
        <StatusBar style="light" />
        <InvoiceDetailScreen
          invoiceId={screen.id}
          onBack={() => setScreen("home")}
          onEdit={(id) => setScreen({ screen: "edit", id })}
        />
      </>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <HomeScreen
        onLogout={onLogout}
        onCapture={() => setScreen("upload")}
        onCreateInvoice={() => setScreen("create")}
        onInvoicePress={(id) => setScreen({ screen: "detail", id })}
      />
    </>
  );
}
