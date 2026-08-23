"use client";

import {AlertsDashboard} from "@/components/alerts/alerts-dashboard";
import {PageHeader} from "@/components/dashboard/page-header";

export default function AlertsPage() {
  return <><PageHeader eyebrow="CA REVIEW" title="Alerts Dashboard" description="Dynamic validation and reconciliation evidence with read-only AI explanations."/><AlertsDashboard/></>;
}
