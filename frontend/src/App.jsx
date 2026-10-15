
import { useEffect, useRef, useState } from "react";
import "./App.css";

import AiInvoiceAssistant from "./AiInvoiceAssistant";



const API =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

export default function App() {
  const manualRequestId = useRef(null);
  const [demoKey, setDemoKey] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [unlockError, setUnlockError] = useState("");
  const [unlockBusy, setUnlockBusy] = useState(false);
  const [backend, setBackend] = useState("Checking...");
  const [paypal, setPaypal] = useState("Not tested");
  const [message, setMessage] = useState("");
  const [invoices, setInvoices] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    customer_email: "",
    item_name: "AI Consulting Demo",
    quantity: 1,
    unit_price: "49.99"
  });


  function apiFetch(path, options = {}) {
    return fetch(`${API}${path}`, {
      ...options,
      headers: {
        ...options.headers,
        "X-Demo-Key": demoKey
      }
    });
  }

  async function unlockDemo(event) {
    event.preventDefault();

    const candidate = keyInput.trim();

    if (!candidate || unlockBusy) return;

    setUnlockBusy(true);
    setUnlockError("");

    try {
      const response = await fetch(
        `${API}/api/demo/verify`,
        {
          headers: {
            "X-Demo-Key": candidate
          }
        }
      );

      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? "Incorrect demo passphrase."
            : "Demo verification failed. Check the backend."
        );
      }

      setDemoKey(candidate);
      setKeyInput("");

    } catch (err) {
      setUnlockError(err.message);

    } finally {
      setUnlockBusy(false);
    }
  }


  async function loadInvoices() {
    const response = await apiFetch("/api/invoices/list");
    if (!response.ok) {
      throw new Error("Unable to load invoices");
    }

    const data = await response.json();
    setInvoices(data.invoices || []);
  }

  useEffect(() => {
    fetch(`${API}/api/health`)
      .then((r) => r.json())
      .then((data) => setBackend(data.status))
      .catch(() => setBackend("Offline"));

    loadInvoices().catch(() => {
      setError("Could not load existing invoices.");
    });
  }, [demoKey]);

  async function testPayPal() {
    try {
      const response = await apiFetch("/api/paypal/check");
      const data = await response.json();

      setPaypal(data.connected ? "Connected" : "Failed");
      setMessage(data.message);
    } catch {
      setPaypal("Failed");
      setMessage("Backend connection failed.");
    }
  }

  async function createInvoice(e) {
    e.preventDefault();

    if (loading) return;

    const requestId =
      manualRequestId.current || crypto.randomUUID();

    manualRequestId.current = requestId;

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const response = await apiFetch("/api/invoices/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": requestId},
        body: JSON.stringify({
          ...form,
          quantity: Number(form.quantity)
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Invoice creation failed."
        );
      }

      setMessage(`Draft created: ${data.invoice_id}`);

      manualRequestId.current = null;

      await loadInvoices();
    } catch (err) {
      setError(
        `${err.message} Check the invoice list before retrying.`
      );
    } finally {
      setLoading(false);
    }
  }

  function updateField(e) {

    manualRequestId.current = null;

    setForm({
      ...form,
      [e.target.name]: e.target.value
    });
  }


  // Day 5: Sandbox Demo Access
  if (!demoKey) {
    return (
      <div className="app">
        <main
          className="container"
          style={{
            minHeight: "85vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }}
        >
          <section
            className="card invoice-section"
            style={{
              width: "100%",
              maxWidth: "520px",
              textAlign: "center"
            }}
          >
            <h1>PayPilot AI</h1>
            <h2>Sandbox Demo Access</h2>

            <p>
              Enter your private demo passphrase to
              access the AI-powered payment assistant.
            </p>

            <form
              onSubmit={unlockDemo}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "16px",
                marginTop: "24px"
              }}
            >
              <label htmlFor="demo-passphrase">
                Demo Passphrase
              </label>

              <input
                id="demo-passphrase"
                type="password"
                value={keyInput}
                onChange={(e) =>
                  setKeyInput(e.target.value)
                }
                placeholder="Enter demo passphrase"
                autoComplete="off"
                required
              />

              <button
                type="submit"
                disabled={unlockBusy}
              >
                {unlockBusy
                  ? "Verifying..."
                  : "Unlock Sandbox Demo"}
              </button>
            </form>

            {unlockError && (
              <p
                role="alert"
                style={{
                  color: "#ffb4b4",
                  marginTop: "16px"
                }}
              >
                {unlockError}
              </p>
            )}

            <p style={{ marginTop: "24px" }}>
              Sandbox mode only. No real payments.
            </p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="navbar">
        <h2>PayPilot <span>AI</span></h2>
        <div className="sandbox">SANDBOX MODE</div>
      </header>

      <main className="container">
        <div className="hero">
          <p className="eyebrow">
            AI-POWERED PAYMENT OPERATIONS
          </p>
          <h1>
            Smarter payments.
            <br />
            <span>Powered by AI.</span>
          </h1>
          <p>
            Create invoices, manage transactions,
            and automate payment workflows.
          </p>
        </div>

        <div className="dashboard">
          <div className="card">
            <h2>System Overview</h2>
            <div className="status">
              <span>Backend</span>
              <strong>{backend}</strong>
            </div>
            <div className="status">
              <span>PayPal Environment</span>
              <strong>Sandbox</strong>
            </div>
            <div className="status">
              <span>PayPal API</span>
              <strong>{paypal}</strong>
            </div>

            <button onClick={testPayPal}>
              Test PayPal Connection
            </button>
          </div>

          <div className="card">
            <h2>Project Progress</h2>
            <p>✓ React + FastAPI</p>
            <p>✓ PayPal Authentication</p>
            <p>✓ Invoice Listing API</p>
            <p>◯ AI Agent Integration</p>
            <p>◯ Cloud Deployment</p>
          </div>
        </div>


        <AiInvoiceAssistant
          onCreated={loadInvoices}
          demoKey={demoKey}
        />

        <section className="card invoice-section">
          <h2>Create Sandbox Invoice</h2>
          <p>
            Test invoices only. Drafts are not sent
            and do not transfer real money.
          </p>

          <form className="invoice-form" onSubmit={createInvoice}>
            <label>
              Customer Sandbox Email
              <input
                type="email"
                name="customer_email"
                value={form.customer_email}
                onChange={updateField}
                placeholder="Sandbox Personal account email"
                required
              />
            </label>

            <label>
              Item / Service
              <input
                name="item_name"
                value={form.item_name}
                onChange={updateField}
                required
              />
            </label>

            <label>
              Quantity
              <input
                type="number"
                name="quantity"
                min="1"
                max="100"
                step="1"
                value={form.quantity}
                onChange={updateField}
                required
              />
            </label>

            <label>
              Unit Price (USD)
              <input
                type="number"
                name="unit_price"
                min="0.01"
                step="0.01"
                value={form.unit_price}
                onChange={updateField}
                required
              />
            </label>

            <button type="submit" disabled={loading}>
              {loading
                ? "Creating..."
                : "Create Draft Invoice"}
            </button>
          </form>

          {message && <p role="status">{message}</p>}
          {error && (
            <p className="invoice-error" role="alert">
              {error}
            </p>
          )}
        </section>

        <section className="card invoice-section">
          <h2>Invoice History</h2>
          <p>Invoices retrieved from PayPal Sandbox</p>

          <button
            onClick={() =>
              loadInvoices().catch(() =>
                setError("Unable to refresh invoices.")
              )
            }
          >
            Refresh Invoices
          </button>

          {invoices.length === 0 && (
            <p>No invoices loaded.</p>
          )}

          {invoices.map((invoice) => (
            <div className="invoice-row" key={invoice.invoice_id}>
              <div>
                <strong>
                  #{invoice.invoice_number || "Draft"}
                </strong>
                <p>{invoice.invoice_id}</p>
              </div>
              <div>
                <strong>
                  ${invoice.amount} {invoice.currency}
                </strong>
                <p>{invoice.status}</p>
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
