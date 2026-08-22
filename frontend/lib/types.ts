export type Client = {
  id: string;
  firm_id: string;
  business_name: string;
  legal_name: string;
  gstin: string;
  state: string;
  business_type: string;
  filing_frequency: "monthly" | "quarterly";
  contact_name: string;
  whatsapp_phone: string;
  preferred_language: string;
  whatsapp_consent: boolean;
  assigned_preparer_id?: string;
  reviewer_id?: string;
  demo_scenario?: string;
  created_at?: string;
};

export type GSTApplication = {
  id: string;
  firm_id: string;
  client_id: string;
  application_type?: string;
  financial_year: string;
  period_label: string;
  period_start: string;
  period_end: string;
  due_date?: string;
  filing_frequency: string;
  status: string;
  assigned_preparer_id?: string;
  reviewer_id?: string;
  client?: Client;
  arn?: string;
  filing_date?: string;
  final_notes?: string;
  created_at?: string;
};

export type Requirement = {
  id: string;
  application_id: string;
  requirement_type: string;
  label: string;
  required: boolean;
  status: string;
  created_at?: string;
};

export type PublicUploadRequirement = {
  id: string;
  label: string;
  required: boolean;
  status: string;
  upload_status: "pending" | "uploaded";
  processing_status: string | null;
};

export type PublicUploadContext = {
  firm: {name: string};
  client: {business_name: string};
  application: {period_label: string; due_date?: string | null};
  checklist: PublicUploadRequirement[];
  allowed_extensions: string[];
  maximum_size_mb: number;
};

export type DocumentRecord = {
  id: string;
  application_id: string;
  requirement_id?: string;
  original_name: string;
  mime_type?: string;
  file_size?: number;
  document_type?: string | null;
  processing_status: string;
  source: string;
  created_at: string;
  signed_url?: string;
};

export type Extraction = {
  id: string;
  document_id: string;
  document_type: string;
  raw_text?: string;
  structured_data: Record<string, unknown>;
  original_structured_data?: Record<string, unknown>;
  field_confidences?: Record<string, number>;
  overall_confidence?: number;
  provider?: string;
  model_name?: string;
  review_status: string;
  review_notes?: string;
};

export type Finding = {
  id: string;
  finding_type: string;
  severity: string;
  message: string;
  details?: Record<string, unknown>;
  status: string;
  document_id?: string;
  invoice_record_id?: string;
};

export type ReconciliationItem = {
  id: string;
  match_status: string;
  match_score: number;
  purchase_invoice_id?: string;
  gstr2b_invoice_id?: string;
  differences?: Record<string, unknown>;
};

export type ReconciliationResult = {
  id?: string;
  status?: string;
  summary: Record<string, number>;
  items: ReconciliationItem[];
};

export type Reminder = {
  id: string;
  draft_message: string;
  approved_message?: string;
  status: string;
  upload_url?: string;
  provider?: string;
  reminder_type?: "initial_document_request" | "missing_document_reminder";
  reminder_needed?: boolean;
  requires_connection?: boolean;
  message?: string;
  demo_session_id?: string | null;
};

export type DocumentCollectionStatus = {
  required_count: number;
  received_count: number;
  missing_count: number;
  progress_percent: number;
  workflow_status:
    | "not_started"
    | "documents_requested"
    | "partially_received"
    | "documents_complete";
  requirements: Requirement[];
  base_application_id: string;
  effective_application_id: string;
};

export type Citation = {
  title: string;
  section?: string;
  page?: string | number;
  source_url?: string;
};

export type AuditEvent = {
  id: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  metadata?: Record<string, unknown>;
  before_data?: Record<string, unknown>;
  after_data?: Record<string, unknown>;
  created_at: string;
  user_id?: string;
};
