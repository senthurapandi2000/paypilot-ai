
import { useEffect, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

function App() {
  const [backend, setBackend] = useState("Checking...");
  const [paypal, setPaypal] = useState("Not tested");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/health`)
      .then((res) => res.json())
      .then((data) =>
        setBackend(data.status === "online" ? "Online" : "Offline")
      )
      .catch(() => setBackend("Offline"));
  }, []);

  async function testPayPal() {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch(`${API}/api/paypal/check`);
      const data = await response.json();

      setPaypal(data.connected ? "Connected" : "Failed");
      setMessage(data.message);
    } catch {
      setPaypal("Failed");
      setMessage("Cannot reach the backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="navbar">
        <h2>PayPilot <span>AI</span></h2>
        <div className="sandbox">SANDBOX MODE</div>
      </header>

      <main className="container">
        <div className="hero">
          <p className="eyebrow">AI-POWERED PAYMENT OPERATIONS</p>
          <h1>Smarter payments.<br /><span>Powered by AI.</span></h1>
          <p>
            Your intelligent assistant for managing invoices,
            understanding transactions, and automating payments.
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

            <button onClick={testPayPal} disabled={loading}>
              {loading ? "Testing..." : "Test PayPal Connection"}
            </button>
            <p role="status">{message}</p>
          </div>

          <div className="card">
            <h2>Project Progress</h2>
            <p>✓ FastAPI Backend</p>
            <p>✓ React Application</p>
            <p>✓ PayPal Sandbox Authentication</p>
            <p>◯ AI Agent Integration</p>
            <p>◯ Invoice Automation</p>
            <p>◯ Cloud Deployment</p>
          </div>
        </div>

        <h2 className="section-title">Upcoming Features</h2>
        <div className="features">
          <div className="card">
            <h3>AI Invoice Assistant</h3>
            <p>Create invoices through conversations.</p>
          </div>
          <div className="card">
            <h3>Payment Intelligence</h3>
            <p>Understand transaction activity.</p>
          </div>
          <div className="card">
            <h3>Agentic Workflows</h3>
            <p>Automate tasks with human approval.</p>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
