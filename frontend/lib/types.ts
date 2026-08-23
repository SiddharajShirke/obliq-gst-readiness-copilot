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
  display_status?: string;
  workflow_percent?: number;
  effective_application_id?: string;
  ready_for_filing?: boolean;
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
  ready_to_submit_count: number;
  latest_submission_batch: {
    id: string;
    status: string;
    document_count: number;
    completed_count: number;
    failed_count: number;
  } | null;
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

export type GSTRecord = {
  id: string;
  document_id: string;
  invoice_category: string;
  document_type?: string;
  invoice_number?: string | null;
  invoice_date?: string | null;
  supplier_name?: string | null;
  supplier_gstin?: string | null;
  customer_name?: string | null;
  customer_gstin?: string | null;
  taxable_value?: string | number | null;
  igst?: string | number | null;
  cgst?: string | number | null;
  sgst?: string | number | null;
  cess?: string | number | null;
  total_tax?: string | number | null;
  invoice_total?: string | number | null;
  itc_status?: string | null;
  rcm_flag?: boolean | null;
  source_page?: number | null;
  source_row?: number | null;
  source_type?: string | null;
  review_status: string;
  review_eligible?: boolean;
};

export type ExtractionPortfolioScope =
  | "sales_register"
  | "purchase_register"
  | "sales_invoices"
  | "purchase_expense_invoices"
  | "credit_debit_notes"
  | "gst_special_transactions"
  | "combined";

export type ExtractionPortfolioResult = {
  scope: ExtractionPortfolioScope;
  summary: {
    record_count: number;
    taxable_value: string | number;
    total_tax: string | number;
    document_value: string | number;
    approved_count: number;
    needs_review_count: number;
    rcm_count: number;
  };
  records: GSTRecord[];
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
  evidence_context?: {
    issue_summary?: string | null;
    document_name?: string | null;
    document_category?: string | null;
    document_number?: string | null;
    party_name?: string | null;
    party_gstin?: string | null;
    document_date?: string | null;
    taxable_value?: string | number | null;
    igst?: string | number | null;
    cgst?: string | number | null;
    sgst?: string | number | null;
    cess?: string | number | null;
    total_tax?: string | number | null;
    total_document_value?: string | number | null;
    source_page?: number | null;
    source_row?: number | null;
    period_label?: string | null;
    period_start?: string | null;
    period_end?: string | null;
  };
};

export type WorkflowStep = {
  key: string;
  label: string;
  state: "completed" | "current" | "pending" | "disabled";
  progress_percent: number;
};

export type WorkflowProgress = {
  application_id: string;
  application_status: string;
  current_stage: string;
  progress_percent: number;
  steps: WorkflowStep[];
  extraction: {
    record_count: number;
    reviewed_count: number;
    approved_count: number;
    rejected_count: number;
    pending_count: number;
    progress_percent: number;
  };
  validation: {finding_count: number; open_count: number; reviewed_count: number; progress_percent: number};
  reconciliation: {
    run_count: number;
    item_count: number;
    open_count: number;
    review_required_count: number;
    reviewed_count: number;
    progress_percent: number;
    available: boolean;
    status: "not_started" | "in_progress" | "complete";
    export_enabled: boolean;
  };
  readiness: {
    ready_for_filing: boolean;
    ready_for_filing_percent: number;
    main_export_enabled: boolean;
  };
};

export type ValidationCategory = {
  type: string;
  label: string;
  requirement_status: "received" | "missing";
  record_count: number;
  approved_record_count: number;
  pending_record_count: number;
  finding_count: number;
  open_finding_count: number;
  alert_count: number;
  finding_groups: Array<{type: string; label: string; count: number; open_count: number}>;
  findings: Finding[];
  alerts: ReconciliationAlert[];
};

export type ValidationPortfolio = {
  application_id: string;
  summary: {
    category_count: number;
    received_category_count: number;
    record_count: number;
    approved_record_count: number;
    finding_count: number;
    open_finding_count: number;
    alert_count: number;
  };
  categories: ValidationCategory[];
  uncategorized_findings: Finding[];
};

export type ValidationCorrectionProposal = {
  id: string;
  proposal_type: "manual" | "ai";
  status: "proposed" | "applied" | "rejected";
  changes: Array<{
    record_id: string;
    field: string;
    before: unknown;
    after: unknown;
    rationale: string;
  }>;
  rationale?: string | null;
  provider?: string | null;
  model?: string | null;
};

export type ReconciliationItem = {
  id: string;
  match_status: string;
  match_score: number;
  purchase_invoice_id?: string;
  gstr2b_invoice_id?: string;
  differences?: Record<string, unknown>;
  evidence?: {
    books?: Record<string, string | number | boolean | null> | null;
    gstr2b?: Record<string, string | number | boolean | null> | null;
    difference_fields?: string[];
  };
  special_flags?: string[];
  review_status?: string;
};

export type ReconciliationResult = {
  id?: string;
  status?: string;
  summary: Record<string, number>;
  items: ReconciliationItem[];
  review_progress?: WorkflowProgress["reconciliation"];
};

export type AlertExplanation = {
  title: string;
  what_happened: string;
  why_flagged: string;
  what_ca_should_review: string;
  short_summary: string;
};

export type ReconciliationAlert = {
  id: string;
  application_id: string;
  client_id: string;
  reconciliation_item_id?: string | null;
  validation_finding_id?: string | null;
  workflow_area?: string | null;
  alert_category?: string | null;
  client_name?: string;
  tax_period?: string;
  alert_type: string;
  title: string;
  message: string;
  severity: string;
  status: string;
  evidence: {
    books?: Record<string, string | number | boolean | null> | null;
    gstr2b?: Record<string, string | number | boolean | null> | null;
    difference_fields?: string[];
  };
  ai_explanation?: AlertExplanation | null;
  ai_explanation_status: string;
  created_at: string;
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
  workflow: WorkflowProgress;
};

export type Citation = {
  source_type: "structured_fact" | "document" | "reconciliation" | "alert" | "knowledge" | string;
  title: string;
  reference?: string;
  document_id?: string;
  section?: string;
  page?: string | number;
  sheet_name?: string;
  row_start?: number;
  row_end?: number;
  source_url?: string;
};

export type AssistantAnswer = {
  answer: string;
  citations: Citation[];
  conversation_id: string;
  source_types: string[];
  used_application_data: boolean;
  confidence: number;
  calculation?: {
    operation: "count" | "sum" | "minimum" | "maximum" | "average" | string;
    metric?: string | null;
    value?: string | number | null;
    record_count: number;
  } | null;
  rows: Array<Record<string, unknown>>;
  clarification?: string | null;
  proposed_action?: {
    id: string;
    action_type: string;
    title: string;
    preview: Record<string, unknown>;
    affected_count: number;
    warnings: string[];
    expires_at: string;
    status: string;
  } | null;
  tool_trace: Array<{
    tool: string;
    domain: string;
    operation: string;
    row_count: number;
  }>;
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
