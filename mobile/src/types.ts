export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "OWNER" | "STAFF" | "CLIENT";
  is_active: boolean;
  organization_id: string;
  organization_name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface InvoiceItem {
  id: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
}

export interface InvoiceFile {
  id: string;
  original_name: string;
  content_type: string | null;
  size_bytes: number;
  uploaded_by_name: string | null;
  created_at: string;
}

export interface Invoice {
  id: string;
  client_id: string;
  client_name: string;
  invoice_number: string;
  invoice_date: string;
  status:
    | "PENDING"
    | "PROCESSING"
    | "COMPLETED"
    | "REVIEW"
    | "CANCELLED";
  currency: string;
  total_amount: string;
  assigned_to_id: string | null;
  assigned_to_name: string | null;
  created_at: string;
  notes?: string | null;
  updated_at?: string;
  items?: InvoiceItem[];
  files?: InvoiceFile[];
}

export interface InvoiceListEnvelope {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface InvoiceItemPayload {
  description: string;
  quantity?: string;
  unit_price?: string;
}

export interface InvoiceCreatePayload {
  client_id: string;
  invoice_number?: string;
  invoice_date: string;
  currency?: string;
  notes?: string;
  assigned_to_id?: string | null;
  items?: InvoiceItemPayload[];
}

export interface InvoiceUpdatePayload {
  invoice_date?: string;
  currency?: string;
  notes?: string;
  assigned_to_id?: string | null;
  status?: Invoice["status"];
  items?: InvoiceItemPayload[];
}

export interface Client {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  is_active: boolean;
  account_email: string | null;
}

export interface StaffMember {
  id: string;
  email: string;
  full_name: string;
  role: "STAFF";
  is_active: boolean;
  assigned_invoice_count: number;
}

export interface ScanPage {
  id: string;
  uri: string;
  width: number;
  height: number;
  rotation: number;
}
