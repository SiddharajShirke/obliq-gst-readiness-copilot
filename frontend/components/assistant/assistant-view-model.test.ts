import {describe, expect, it} from "vitest";
import type {AssistantAnswer} from "../../lib/types";
import {buildAssistantViewModel} from "./assistant-view-model";

function answer(overrides: Partial<AssistantAnswer>): AssistantAnswer {
  return {
    answer: "Grounded response",
    citations: [],
    conversation_id: "conversation-1",
    source_types: ["structured_fact"],
    used_application_data: true,
    confidence: 1,
    rows: [],
    tool_trace: [],
    ...overrides,
  };
}

describe("assistant result view model", () => {
  it("formats exact counts and currency extrema", () => {
    const count = buildAssistantViewModel(answer({
      calculation: {operation: "count", value: 24, record_count: 24},
    }));
    const minimum = buildAssistantViewModel(answer({
      calculation: {
        operation: "minimum",
        metric: "invoice_total",
        value: "590.00",
        record_count: 24,
      },
      rows: [{invoice_number: "LOW/001", invoice_total: "590.00"}],
    }));

    expect(count.summary?.value).toBe("24");
    expect(minimum.summary?.value).toContain("₹590.00");
    expect(minimum.table?.columns).toContain("invoice_number");
  });

  it("maps a pending proposal without exposing raw payloads", () => {
    const view = buildAssistantViewModel(answer({
      proposed_action: {
        id: "proposal-1",
        action_type: "mark_reconciliation_reviewed",
        title: "Mark reconciliation reviewed",
        preview: {
          before: {review_status: "pending"},
          after: {review_status: "reviewed"},
        },
        affected_count: 1,
        warnings: ["No data changes until confirmation."],
        expires_at: "2026-08-23T12:00:00Z",
        status: "pending_confirmation",
      },
    }));

    expect(view.action?.id).toBe("proposal-1");
    expect(view.action?.before).toEqual({review_status: "pending"});
    expect(JSON.stringify(view)).not.toContain("evidence_fingerprint");
  });
});
