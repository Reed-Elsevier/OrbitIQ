import { useEffect, useMemo, useState } from 'react';

type CheckStatus = 'pass' | 'warning' | 'fail';

type Check = {
  code: string;
  status: CheckStatus;
  title: string;
  details: string;
};

type AiAnalysis = {
  summary: string;
  risk_level: string;
  recommendation: string;
  reasons: string[];
  evidence: string[];
  questions_for_analyst: string[];
};

type AnalysisResponse = {
  invoice: Record<string, any>;
  supplier: Record<string, any>;
  po: Record<string, any> | null;
  exceptions: Array<Record<string, any>>;
  checks: Check[];
  ai_analysis: AiAnalysis;
  recommendation: string;
  decision_story: string[];
  available_invoice_ids: string[];
  data_source: string;
  ai_enabled: boolean;
};

const MOCK_ANALYSIS: AnalysisResponse = {
  invoice: {
    invoice_id: 'INV-1001',
    supplier_name: 'Northwind Industrial',
    gross_amount: 18750,
    due_date: '2026-10-12',
    po_id: 'PO-8812',
    status: 'pending',
  },
  supplier: {
    supplier_id: 'SUP-201',
    supplier_name: 'Northwind Industrial',
    risk_band: 'medium',
    exception_history: 3,
  },
  po: {
    po_id: 'PO-8812',
    po_amount: 17500,
    status: 'approved',
  },
  exceptions: [
    {
      exception_id: 'EX-9901',
      type: 'Price mismatch',
      description: 'Invoice exceeds the approved PO amount by 7%.',
      severity: 'medium',
    },
  ],
  checks: [
    { code: 'PO_VALID', status: 'pass', title: 'PO validated', details: 'PO exists and aligns closely with invoice value.' },
    { code: 'PO_AMOUNT_EXCEEDED', status: 'warning', title: 'PO amount mismatch', details: 'Invoice amount exceeds approved PO by 7%.' },
    { code: 'EXISTING_EXCEPTION', status: 'warning', title: 'Existing exception', details: 'Exception already exists for this invoice.' },
  ],
  ai_analysis: {
    summary: 'Invoice follows standard PO logic but exceeds the approved value by a narrow margin, so a human should review before release.',
    risk_level: 'medium',
    recommendation: 'REVIEW',
    reasons: ['PO amount mismatch', 'Supplier has recurring exception signals'],
    evidence: ['INV-1001', 'PO-8812'],
    questions_for_analyst: ['Was the PO amended after invoice issuance?', 'Should this be routed to a specialist approver?'],
  },
  recommendation: 'REVIEW',
  decision_story: [
    'Invoice loaded',
    'PO and supplier context retrieved',
    'Exception history checked',
    'Deterministic checks executed',
    'AI evidence review completed',
    'Manual review required before release',
  ],
  available_invoice_ids: ['INV-1001', 'INV-1002', 'INV-1003', 'INV-1004', 'INV-1005'],
  data_source: 'synthetic demo fixtures',
  ai_enabled: false,
};

const statusStyleMap: Record<CheckStatus, { label: string; className: string }> = {
  pass: { label: 'PASS', className: 'status-pass' },
  warning: { label: 'WARN', className: 'status-warning' },
  fail: { label: 'FAIL', className: 'status-fail' },
};

function App() {
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('INV-1001');
  const [analysis, setAnalysis] = useState<AnalysisResponse>(MOCK_ANALYSIS);
  const [loading, setLoading] = useState(false);
  const [apiUnavailable, setApiUnavailable] = useState(false);

  useEffect(() => {
    let ignore = false;
    const loadInvoice = async () => {
      setLoading(true);
      try {
        const response = await fetch(`http://localhost:8000/api/invoices/${selectedInvoiceId}/analyze`);
        if (!response.ok) {
          throw new Error('Live API unavailable');
        }
        const payload = (await response.json()) as AnalysisResponse;
        if (!ignore) {
          setAnalysis(payload);
          setApiUnavailable(false);
        }
      } catch (error) {
        console.error('Invoice analysis API unavailable; showing demo fixture.', error);
        if (!ignore) {
          setAnalysis(MOCK_ANALYSIS);
          setApiUnavailable(true);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };

    loadInvoice();
    return () => {
      ignore = true;
    };
  }, [selectedInvoiceId]);

  const invoiceSummary = useMemo(
    () => `${analysis.invoice.supplier_name ?? 'Unknown supplier'} • ${analysis.invoice.invoice_id ?? selectedInvoiceId}`,
    [analysis, selectedInvoiceId],
  );

  return (
    <div className="app-shell">
      <div className="topbar">
        <div>
          <div className="eyebrow">OrbitIQ</div>
          <h1>Invoice Intelligence Copilot</h1>
        </div>
        <div className="selector-box">
          <label htmlFor="invoice-select">Invoice</label>
          <select id="invoice-select" value={selectedInvoiceId} onChange={(event) => setSelectedInvoiceId(event.target.value)}>
            {analysis.available_invoice_ids?.map((invoiceId) => (
              <option key={invoiceId} value={invoiceId}>
                {invoiceId}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? <div className="loading-banner">Analyzing invoice…</div> : null}
      <div className="demo-banner">
        {apiUnavailable ? 'API unavailable — showing synthetic demo data.' : `Data: ${analysis.data_source}.`}
        {!analysis.ai_enabled ? ' AI / Bedrock is not connected yet.' : ''}
      </div>

      <div className="dashboard-grid">
        <aside className="panel left-panel">
          <h2>Invoice details</h2>
          <div className="detail-row"><span>Invoice ID</span><strong>{analysis.invoice.invoice_id ?? selectedInvoiceId}</strong></div>
          <div className="detail-row"><span>Supplier</span><strong>{analysis.supplier.supplier_name ?? analysis.invoice.supplier_name ?? '—'}</strong></div>
          <div className="detail-row"><span>Amount</span><strong>${Number(analysis.invoice.gross_amount ?? 0).toLocaleString()}</strong></div>
          <div className="detail-row"><span>Date</span><strong>{analysis.invoice.invoice_date ?? analysis.invoice.due_date ?? '—'}</strong></div>
          <div className="detail-row"><span>PO</span><strong>{analysis.invoice.po_id ?? analysis.po?.po_id ?? '—'}</strong></div>
          <div className="detail-row"><span>Status</span><strong>{analysis.invoice.status ?? 'unknown'}</strong></div>
        </aside>

        <main className="panel center-panel">
          <div className="panel-header">
            <h2>Evidence</h2>
            <span className="badge">{analysis.ai_analysis.risk_level?.toUpperCase() ?? 'LOW'}</span>
          </div>

          <div className="card-grid">
            <section className="info-card">
              <h3>Purchase Order</h3>
              <p><strong>PO ID:</strong> {analysis.po?.po_id ?? 'No PO linked'}</p>
              <p><strong>Amount:</strong> ${Number(analysis.po?.po_amount ?? 0).toLocaleString()}</p>
              <p><strong>Status:</strong> {analysis.po?.status ?? 'not found'}</p>
            </section>

            <section className="info-card">
              <h3>Previous invoices</h3>
              <ul>
                {analysis.supplier.exception_history ? <li>Supplier has {analysis.supplier.exception_history} recent exception signals.</li> : <li>No recent supplier exception history.</li>}
                <li>Latest supplier invoice: {analysis.invoice.supplier_name ?? 'Supplier'}.</li>
              </ul>
            </section>

            <section className="info-card">
              <h3>Exceptions</h3>
              {analysis.exceptions.length ? (
                <ul>
                  {analysis.exceptions.map((item) => (
                    <li key={item.exception_id ?? item.type}>
                      <strong>{item.type}</strong> — {item.description}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No exceptions found.</p>
              )}
            </section>

            <section className="info-card">
              <h3>Payment status</h3>
              <p>{analysis.invoice.payment_status ?? 'No payment record available'}</p>
            </section>
          </div>

          <div className="checks-box">
            <h3>Hard checks</h3>
            <div className="check-list">
              {analysis.checks.map((check) => (
                <div className="check-item" key={check.code}>
                  <span className={`status-pill ${statusStyleMap[check.status].className}`}>
                    {statusStyleMap[check.status].label}
                  </span>
                  <div>
                    <strong>{check.title}</strong>
                    <p>{check.details}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </main>

        <aside className="panel right-panel">
          <h2>Decision</h2>
          <div className="decision-card">
            <div className="decision-header">Risk: <span className="risk-label">{analysis.ai_analysis.risk_level?.toUpperCase() ?? 'LOW'}</span></div>
            <div className="decision-header">Recommendation: <strong>{analysis.recommendation}</strong></div>
            <div className="decision-header">Why:</div>
            <ul>
              {analysis.ai_analysis.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>

          <div className="button-row">
            <button className="approve">APPROVE</button>
            <button className="reject">REJECT</button>
            <button className="escalate">ESCALATE</button>
          </div>
        </aside>
      </div>

      <section className="story-box">
        <h2>Decision Story</h2>
        <ol>
          {analysis.decision_story.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="story-box">
        <h2>Claude Summary</h2>
        <p>{analysis.ai_analysis.summary}</p>
        <div className="question-list">
          {analysis.ai_analysis.questions_for_analyst.map((question) => (
            <div key={question}>{question}</div>
          ))}
        </div>
      </section>

      <div className="mini-label">{invoiceSummary}</div>
    </div>
  );
}

export default App;
