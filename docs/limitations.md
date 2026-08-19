# Prototype Limitations

- No direct GST Portal, ASP or GSP integration
- No automatic filing, DSC/EVC signing or tax payment
- No final ITC eligibility or liability decision
- Simplified GSTR-2B input format and matching rules
- OCR quality depends on local Tesseract or configured vision model
- Mock AI fixtures cover known demonstration files
- No malware scanner or document content-disarm pipeline
- No resilient background queue; processing occurs in-request
- No enterprise secret manager, key rotation or production Meta onboarding
- No real-time statutory deadline synchronization
- No CI/CD, autoscaling, multi-region operation or production observability
- Minimal tests focused on core workflow logic
- Public hosted demo must use synthetic data only

## Production next steps

A real system would add audited GST integrations, encrypted secrets management, asynchronous job queues, antivirus scanning, model evaluation, formal authorization review, deadline-rule versioning, observability, backups, rate limiting, security testing, and professional compliance validation.
