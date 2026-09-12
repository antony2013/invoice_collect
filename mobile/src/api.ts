import { File, Paths } from "expo-file-system";
import {
  Client,
  Invoice,
  InvoiceCreatePayload,
  InvoiceListEnvelope,
  InvoiceUpdatePayload,
  StaffMember,
  TokenResponse,
} from "./types";

let BASE_URL = "http://192.168.1.13:8001/api/v1";
let AUTH_TOKEN: string | null = null;

export function setBaseUrl(url: string) {
  BASE_URL = url.replace(/\/+$/, "");
}

export function getBaseUrl() {
  return BASE_URL;
}

export function setAuthToken(token: string | null) {
  AUTH_TOKEN = token;
}

export function getAuthToken() {
  return AUTH_TOKEN;
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...extra };
  if (AUTH_TOKEN) {
    h["Authorization"] = `Bearer ${AUTH_TOKEN}`;
  }
  return h;
}

export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Login failed (${res.status})`);
  }
  return res.json();
}

export async function getMe(): Promise<TokenResponse["user"]> {
  const res = await fetch(`${BASE_URL}/auth/me`, { headers: headers() });
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json();
}

export async function listMyInvoices(
  page = 1,
  pageSize = 20
): Promise<InvoiceListEnvelope> {
  const res = await fetch(
    `${BASE_URL}/clients/me/invoices?page=${page}&page_size=${pageSize}`,
    { headers: headers() }
  );
  if (!res.ok) throw new Error("Failed to fetch invoices");
  return res.json();
}

export async function getMyInvoice(id: string): Promise<Invoice> {
  const res = await fetch(`${BASE_URL}/clients/me/invoices/${id}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error("Failed to fetch invoice");
  return res.json();
}

export async function uploadInvoice(
  fileUri: string,
  fileName: string,
  notes?: string
): Promise<Invoice> {
  const formData = new FormData();
  const file = new File(fileUri);
  formData.append("upload", file, fileName);
  if (notes) {
    formData.append("notes", notes);
  }

  const res = await fetch(`${BASE_URL}/clients/me/invoices/upload`, {
    method: "POST",
    headers: headers(),
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function downloadFile(
  invoiceId: string,
  fileId: string
): Promise<string> {
  const cacheDir = Paths.cache;
  const destination = new File(cacheDir, `${fileId}.pdf`);
  await File.downloadFileAsync(
    `${BASE_URL}/clients/me/invoices/${invoiceId}/files/${fileId}/download`,
    destination,
    { headers: headers(), idempotent: true }
  );
  return destination.uri;
}

export async function downloadOrgFile(
  invoiceId: string,
  fileId: string
): Promise<string> {
  const cacheDir = Paths.cache;
  const destination = new File(cacheDir, `${fileId}.pdf`);
  await File.downloadFileAsync(
    `${BASE_URL}/invoices/${invoiceId}/files/${fileId}/download`,
    destination,
    { headers: headers(), idempotent: true }
  );
  return destination.uri;
}

export async function listClients(): Promise<Client[]> {
  const res = await fetch(`${BASE_URL}/clients`, { headers: headers() });
  if (!res.ok) throw new Error("Failed to fetch clients");
  return res.json();
}

export async function listStaff(): Promise<StaffMember[]> {
  const res = await fetch(`${BASE_URL}/staff`, { headers: headers() });
  if (!res.ok) throw new Error("Failed to fetch staff");
  return res.json();
}

export async function listAllInvoices(
  statusFilter?: string,
  page = 1,
  pageSize = 50
): Promise<InvoiceListEnvelope> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (statusFilter) params.set("status", statusFilter);
  const res = await fetch(`${BASE_URL}/invoices?${params.toString()}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error("Failed to fetch invoices");
  return res.json();
}

export async function getOrgInvoice(id: string): Promise<Invoice> {
  const res = await fetch(`${BASE_URL}/invoices/${id}`, { headers: headers() });
  if (!res.ok) throw new Error("Failed to fetch invoice");
  return res.json();
}

export async function createInvoice(
  payload: InvoiceCreatePayload
): Promise<Invoice> {
  const res = await fetch(`${BASE_URL}/invoices`, {
    method: "POST",
    headers: { ...headers(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Create failed (${res.status})`);
  }
  return res.json();
}

export async function updateInvoice(
  id: string,
  payload: InvoiceUpdatePayload
): Promise<Invoice> {
  const res = await fetch(`${BASE_URL}/invoices/${id}`, {
    method: "PATCH",
    headers: { ...headers(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Update failed (${res.status})`);
  }
  return res.json();
}

export async function deleteInvoice(id: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/invoices/${id}`, {
    method: "DELETE",
    headers: headers(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Delete failed (${res.status})`);
  }
}
