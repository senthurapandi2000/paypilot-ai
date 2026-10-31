
import { useState } from "react";
import "./AiInvoiceAssistant.css";

const API = "http://127.0.0.1:8000";

export default function AiInvoiceAssistant({ onCreated }) {
  const [message, setMessage] = useState("");
  const [draftContext, setDraftContext] = useState("");
  const [conversation, setConversation] = useState([]);
  const [preview, setPreview] = useState(null);
  const [approvalId, setApprovalId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  function addMessage(role, text) {
    setConversation((old) => [
      ...old,
      { id: crypto.randomUUID(), role, text }
    ]);
  }

  async function prepareInvoice(event) {
    event.preventDefault();

    const typed = message.trim();
    const instruction = draftContext
     ? `${draftContext}\nAdditional details or corrections: ${typed}`
     : typed;

    if (!typed || busy || approvalId) return;

    if (instruction.length > 1000) {
        setError(
            "This conversation is too long. Refresh the page " +
            "to begin a new invoice."
        );
        return;
    }

    setBusy(true);
    setError("");
    setNotice("");
    setPreview(null);
    addMessage("user", typed);

    try {
      const response = await fetch(`${API}/api/ai/prepare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: instruction })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "AI preparation failed."
        );
      }

      addMessage("assistant", data.message);
      setMessage("");

      if (data.ready) {
        setDraftContext("");
        setPreview(data.preview);
        setApprovalId(data.approval_id);
      } else {
        setDraftContext(instruction);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function approveInvoice() {
    if (!approvalId || busy) return;

    const id = approvalId;
    setBusy(true);
    setError("");

    // Disable further approvals immediately.
    setApprovalId(null);
    setPreview(null);

    try {
      const response = await fetch(`${API}/api/ai/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: id })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Draft creation failed."
        );
      }

      const result = `Sandbox draft created: ${data.invoice_id}`;
      setNotice(result);
      addMessage("assistant", result);

      try {
        await onCreated?.();
      } catch {
        setError(
          "Draft created, but invoice history could not refresh."
        );
      }
    } catch (err) {
      setError(
        `${err.message} Check Invoice History before ` +
        "preparing another invoice."
      );
    } finally {
      setBusy(false);
    }
  }

  async function cancelInvoice() {
    if (!approvalId || busy) return;

    const id = approvalId;

    setPreview(null);
    setApprovalId(null);
    setNotice("Preview discarded.");

    try {
      await fetch(`${API}/api/ai/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: id })
      });
    } catch {
      // Preview expires automatically on the backend.
    }
  }

  return (
    <section className="card ai-panel">
      <div className="ai-heading">
        <div>
          <p className="eyebrow">DAY 3 · AI ASSISTANT</p>
          <h2>PayPilot AI Assistant</h2>
          <p className="ai-muted">
            Describe an invoice in natural language.
            Review it before creating a Sandbox draft.
          </p>
        </div>
        <span className="ai-chip">AI + PayPal</span>
      </div>

      <div className="ai-chat" aria-live="polite">
        <div className="ai-bubble assistant">
          Hi! Tell me the Sandbox buyer email,
          service, quantity and price.
          I'll prepare an invoice for your approval.
        </div>

        {conversation.map((entry) => (
          <div
            key={entry.id}
            className={`ai-bubble ${entry.role}`}
          >
            {entry.text}
          </div>
        ))}
      </div>

      <form className="ai-entry" onSubmit={prepareInvoice}>
        <textarea
          rows="3"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={
            "Create an invoice for buyer@example.com " +
            "for 2 hours of AI consulting at $25 per hour"
          }
          maxLength={1000}
          disabled={busy || Boolean(approvalId)}
          required
        />

        <button
          type="submit"
          disabled={busy || Boolean(approvalId)}
        >
          {busy ? "Processing..." : "Prepare Invoice with AI"}
        </button>
      </form>

      {preview && (
        <div className="ai-preview">
          <h3>Review Your Invoice</h3>
          <p className="ai-muted">
            No PayPal invoice has been created yet.
          </p>

          <div className="ai-detail">
            <span>Customer</span>
            <strong>{preview.customer_email}</strong>
          </div>

          <div className="ai-detail">
            <span>Service</span>
            <strong>{preview.item_name}</strong>
          </div>

          <div className="ai-detail">
            <span>Quantity</span>
            <strong>{preview.quantity}</strong>
          </div>

          <div className="ai-detail">
            <span>Unit price</span>
            <strong>${preview.unit_price}</strong>
          </div>

          <div className="ai-detail">
            <span>Total</span>
            <strong>${preview.total} USD</strong>
          </div>

          <div className="ai-actions">
            <button
              type="button"
              onClick={approveInvoice}
              disabled={busy}
            >
              Approve & Create Draft
            </button>

            <button
              type="button"
              className="ai-cancel"
              onClick={cancelInvoice}
              disabled={busy}
            >
              Cancel
            </button>
          </div>

          <p className="ai-muted">
            Approval expires after 10 minutes.
            This creates a draft only, not a payment.
          </p>
        </div>
      )}

      {notice && (
        <p className="ai-success" role="status">{notice}</p>
      )}

      {error && (
        <p className="invoice-error" role="alert">{error}</p>
      )}
    </section>
  );
}
