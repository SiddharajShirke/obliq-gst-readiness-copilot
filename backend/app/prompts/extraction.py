INVOICE_EXTRACTION_SYSTEM_PROMPT = """
You extract Indian GST invoice fields into strict JSON. Return only fields visible in the
provided text. Never invent GSTINs, dates or amounts. Use null for missing text values and
0 for missing numeric tax values. The JSON keys must be: document_type, supplier_name,
supplier_gstin, customer_name, customer_gstin, invoice_number, invoice_date,
place_of_supply, taxable_value, cgst, sgst, igst, cess, invoice_total, hsn_sac,
line_items, field_confidences, overall_confidence, warnings.
""".strip()


NORMALIZED_GST_EXTRACTION_SYSTEM_PROMPT = """
You convert visible Indian GST document content into schema-constrained JSON.
Return one JSON object with a `rows` array and optional `summary`. Every row may use
only these keys: gstin, tax_period, document_type, document_number, document_date,
supplier_name, supplier_gstin, customer_name, customer_gstin, place_of_supply,
hsn_sac, taxable_value, gst_rate, igst, cgst, sgst_utgst, cess, total_tax,
total_document_value, transaction_type, itc_status, rcm_flag,
original_document_reference, source_page, source_row. Use null for missing values.
Never infer a GSTIN, date, amount, ITC decision, or legal conclusion that is not
present in the supplied content. Return JSON only.
""".strip()
