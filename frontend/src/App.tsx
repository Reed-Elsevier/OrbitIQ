import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  Bell,
  Building2,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  CircleX,
  ClipboardList,
  Clock3,
  CreditCard,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  Maximize2,
  MoreHorizontal,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

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

type RedTeamReview = {
  status: 'PASS' | 'CHALLENGE';
  recommendation_floor: string;
  summary: string;
  checked_flags: string[];
  challenged_flags: string[];
  source: string;
};

type RedGate = {
  status: 'BLOCK' | 'REVIEW' | 'CLEAR';
  recommendation: string;
  overrode_analyst: boolean;
};

type AnalysisResponse = {
  invoice: Record<string, any>;
  supplier: Record<string, any>;
  po: Record<string, any> | null;
  exceptions: Array<Record<string, any>>;
  invoice_lines?: Array<Record<string, any>>;
  payments?: Array<Record<string, any>>;
  previous_invoices?: Array<Record<string, any>>;
  duplicate_matches?: Array<Record<string, any>>;
  checks: Check[];
  analysis?: AiAnalysis;
  ai_analysis?: AiAnalysis;
  red_team_review?: RedTeamReview;
  red_gate?: RedGate;
  recommendation: string;
  decision_story: string[];
  available_invoice_ids: string[];
  invoice_count?: number;
  data_source: string;
  ai_enabled: boolean;
};

type InvoiceOption = {
  invoice_id: string;
  supplier_name: string;
  gross_amount: number;
  currency: string;
  status: string;
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
  red_team_review: {
    status: 'PASS',
    recommendation_floor: 'REVIEW',
    summary: 'Analyst recommendation meets or exceeds the deterministic control floor.',
    checked_flags: ['PO_AMOUNT_EXCEEDED', 'EXISTING_EXCEPTION'],
    challenged_flags: [],
    source: 'deterministic_control_review',
  },
  red_gate: { status: 'REVIEW', recommendation: 'REVIEW', overrode_analyst: false },
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

type ContextTab = 'all' | 'purchase-order' | 'invoice-lines' | 'history' | 'payments' | 'exceptions';
type DecisionAction = 'Approve' | 'Reject' | 'Escalate';
type DecisionActionCode = 'approve' | 'reject' | 'escalate';
type DemoRole = 'AP Analyst' | 'AP Team Lead' | 'AP Manager';
type WorkspacePage = 'Invoices' | 'Decision Log';
type InvoiceView = 'review' | 'data';
type DecisionRecord = { id: number; invoice_id: string; action: DecisionActionCode; created_at: string };
type DecisionFilter = 'all' | DecisionActionCode;

const CONTEXT_TABS: Array<{ id: ContextTab; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'purchase-order', label: 'Purchase Order' },
  { id: 'invoice-lines', label: 'Invoice Lines' },
  { id: 'history', label: 'History' },
  { id: 'payments', label: 'Payments' },
  { id: 'exceptions', label: 'Exceptions' },
];

const MANUAL_REVIEW_GUIDANCE: Record<string, { lookIn: string; verify: string }> = {
  MISSING_PO: { lookIn: 'Invoice record, Purchase Order', verify: 'Confirm the invoice has an approved purchase order before processing.' },
  PO_NOT_FOUND: { lookIn: 'Invoice record, Purchase Order', verify: 'Locate and verify the referenced purchase order.' },
  PO_AMOUNT_EXCEEDED: { lookIn: 'Invoice amount, Purchase Order amount, Invoice Lines', verify: 'Compare invoiced total and line items against the PO value and scope.' },
  PO_CURRENCY_MISMATCH: { lookIn: 'Invoice record, Purchase Order', verify: 'Confirm both records use the expected currency before comparing amounts.' },
  DUPLICATE_INVOICE: { lookIn: 'Duplicate Matches, Previous Invoices', verify: 'Compare supplier, invoice number, date, and processing status.' },
  NEAR_DUPLICATE: { lookIn: 'Previous Invoices, Invoice Lines', verify: 'Compare invoice number, date, amount, and line items; similarity alone is not proof.' },
  EXISTING_EXCEPTION: { lookIn: 'Exceptions', verify: 'Read the exception resolution and confirm it addresses the current invoice.' },
  BANK_DETAILS_CHANGED: { lookIn: 'Exceptions, Supplier', verify: 'Verify the bank change through an independently trusted supplier contact.' },
  APPROVAL_POLICY_UNVERIFIED: { lookIn: 'Invoice approval level, Supplier approval threshold', verify: 'Confirm the required approver against the organization approval policy.' },
  PAYMENT_STATUS: { lookIn: 'Payments, Invoice status', verify: 'Confirm payment state and amount before taking further action.' },
};

const NAV_ITEMS = [
  { label: 'Dashboard', icon: LayoutDashboard },
  { label: 'Invoices', icon: FileText },
  { label: 'Exceptions', icon: AlertTriangle },
  { label: 'Suppliers', icon: Users },
  { label: 'Decision Log', icon: ClipboardList },
  { label: 'Settings', icon: Settings },
];

function formatMoney(value: unknown, currency = 'USD') {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatDate(value: unknown) {
  if (typeof value !== 'string' || !value) return '—';
  const date = new Date(`${value.slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date);
}

function EvidenceTable({ caption, columns, rows, emptyMessage, rowTones = [] }: { caption: string; columns: string[]; rows: string[][]; emptyMessage: string; rowTones?: Array<'warning' | 'fail' | undefined> }) {
  if (!rows.length) return <div className="empty-evidence">{emptyMessage}</div>;

  return (
    <div className="evidence-table-wrap">
      <table className="evidence-table">
        <caption>{caption}</caption>
        <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, rowIndex) => (
          <tr className={rowTones[rowIndex] ? `evidence-row-${rowTones[rowIndex]}` : undefined} key={`${caption}-${rowIndex}`}>
            {row.map((value, columnIndex) => <td key={`${rowIndex}-${columnIndex}`}>{value || '—'}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function App() {
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('INV0000001');
  const [demoRole, setDemoRole] = useState<DemoRole>('AP Analyst');
  const [analysis, setAnalysis] = useState<AnalysisResponse>(MOCK_ANALYSIS);
  const [invoiceOptions, setInvoiceOptions] = useState<InvoiceOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [apiUnavailable, setApiUnavailable] = useState(false);
  const [contextTab, setContextTab] = useState<ContextTab>('all');
  const [invoiceView, setInvoiceView] = useState<InvoiceView>('review');
  const [searchQuery, setSearchQuery] = useState('');
  const [decisionAction, setDecisionAction] = useState<DecisionAction | null>(null);
  const [decisionSaving, setDecisionSaving] = useState(false);
  const [decisionNotice, setDecisionNotice] = useState('');
  const [decisionNoticeType, setDecisionNoticeType] = useState<'success' | 'error' | 'saving' | null>(null);
  const [activePage, setActivePage] = useState<WorkspacePage>('Invoices');
  const [decisionRecords, setDecisionRecords] = useState<DecisionRecord[]>([]);
  const [decisionLogLoading, setDecisionLogLoading] = useState(false);
  const [decisionLogError, setDecisionLogError] = useState('');
  const [decisionSearch, setDecisionSearch] = useState('');
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>('all');
  const [decisionLogRefresh, setDecisionLogRefresh] = useState(0);

  useEffect(() => {
    let ignore = false;
    const loadInvoice = async () => {
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/invoices/${selectedInvoiceId}/analyze`);
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

  useEffect(() => {
    if (activePage !== 'Invoices') return;

    let ignore = false;
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/invoices?query=${encodeURIComponent(searchQuery)}&limit=25`);
        if (!response.ok) throw new Error('Invoice search unavailable');
        const payload = (await response.json()) as { items: InvoiceOption[] };
        if (!ignore) setInvoiceOptions(payload.items);
      } catch {
        if (!ignore) {
          setInvoiceOptions(MOCK_ANALYSIS.available_invoice_ids.map((invoice_id) => ({
            invoice_id,
            supplier_name: 'Demo supplier',
            gross_amount: 0,
            currency: 'USD',
            status: 'demo',
          })));
        }
      }
    }, 150);

    return () => {
      ignore = true;
      window.clearTimeout(timer);
    };
  }, [activePage, searchQuery]);

  useEffect(() => {
    if (activePage !== 'Decision Log') return;

    let ignore = false;
    const loadDecisions = async () => {
      setDecisionLogLoading(true);
      setDecisionLogError('');
      try {
        const response = await fetch(`${API_BASE_URL}/api/decisions`);
        if (!response.ok) throw new Error('Decision log unavailable');
        const records = (await response.json()) as DecisionRecord[];
        if (!ignore) setDecisionRecords(records);
      } catch {
        if (!ignore) setDecisionLogError('Could not load saved decisions. Check that the API is running.');
      } finally {
        if (!ignore) setDecisionLogLoading(false);
      }
    };

    void loadDecisions();
    return () => { ignore = true; };
  }, [activePage, decisionLogRefresh]);

  const availableInvoiceIds = analysis.available_invoice_ids?.length
    ? analysis.available_invoice_ids
    : MOCK_ANALYSIS.available_invoice_ids;
  const invoice = analysis.invoice;
  const supplier = analysis.supplier;
  const aiAnalysis: AiAnalysis = analysis.analysis ?? analysis.ai_analysis ?? {
    summary: 'AI analysis is unavailable; use the deterministic checks below.',
    risk_level: 'medium',
    recommendation: 'REVIEW',
    reasons: ['Review the deterministic control results.'],
    evidence: [],
    questions_for_analyst: ['Can the approval policy be verified?'],
  };
  const checks = analysis.checks ?? [];
  const exceptions = analysis.exceptions ?? [];
  const manualReviewSignals = checks
    .filter((check) => check.status !== 'pass')
    .map((check) => ({
      ...check,
      lookIn: MANUAL_REVIEW_GUIDANCE[check.code]?.lookIn ?? 'Invoice record and Hard Rule Checks',
      verify: MANUAL_REVIEW_GUIDANCE[check.code]?.verify ?? check.details,
    }));
  if (!analysis.ai_enabled) {
    manualReviewSignals.push({
      code: 'AI_UNAVAILABLE',
      status: 'warning',
      title: 'AI assessment unavailable',
      details: 'The recommendation uses deterministic rules only.',
      lookIn: 'Analyst assessment and Hard Rule Checks',
      verify: 'Review the listed evidence and rule results manually.',
    });
  }
  const currency = invoice.currency ?? 'USD';
  const passedChecks = checks.filter((check) => check.status === 'pass').length;
  const currentIndex = Math.max(0, availableInvoiceIds.indexOf(selectedInvoiceId));
  const recommendation = analysis.recommendation ?? 'REVIEW';
  const recommendationClass = recommendation.toLowerCase().includes('escalate')
    ? 'recommendation-escalate'
    : recommendation.toLowerCase().includes('auto')
      ? 'recommendation-auto'
      : 'recommendation-review';
  const filteredDecisions = decisionRecords.filter((record) => {
    const query = decisionSearch.trim().toLowerCase();
    const matchesSearch = !query || record.invoice_id.toLowerCase().includes(query) || record.action.includes(query);
    return matchesSearch && (decisionFilter === 'all' || record.action === decisionFilter);
  });

  const openDecisionInvoice = (invoiceId: string) => {
    setSelectedInvoiceId(invoiceId);
    setSearchQuery(invoiceId);
    setDecisionAction(null);
    setDecisionNotice('');
    setDecisionNoticeType(null);
    setActivePage('Invoices');
  };

  const selectAdjacentInvoice = (direction: -1 | 1) => {
    const nextIndex = (currentIndex + direction + availableInvoiceIds.length) % availableInvoiceIds.length;
    const nextInvoiceId = availableInvoiceIds[nextIndex];
    setSelectedInvoiceId(nextInvoiceId);
    setSearchQuery(nextInvoiceId);
    setDecisionAction(null);
    setDecisionNotice('');
    setDecisionNoticeType(null);
  };

  const searchInvoice = async () => {
    const query = searchQuery.trim();
    if (!query) return;
    let options = invoiceOptions;
    if (!options.some((option) => option.invoice_id.toLowerCase() === query.toLowerCase())) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/invoices?query=${encodeURIComponent(query)}&limit=25`);
        if (!response.ok) throw new Error('Invoice search unavailable');
        const payload = (await response.json()) as { items: InvoiceOption[] };
        options = payload.items;
        setInvoiceOptions(options);
      } catch {
        options = MOCK_ANALYSIS.available_invoice_ids.map((invoice_id) => ({ invoice_id, supplier_name: 'Demo supplier', gross_amount: 0, currency: 'USD', status: 'demo' }));
      }
    }
    const matchingInvoice = options.find((option) => option.invoice_id.toLowerCase() === query.toLowerCase())
      ?? options[0];
    if (matchingInvoice) {
      setSelectedInvoiceId(matchingInvoice.invoice_id);
      setDecisionAction(null);
      setSearchQuery(matchingInvoice.invoice_id);
      setDecisionNotice('');
      setDecisionNoticeType(null);
    }
  };

  const saveDecision = async (action: DecisionAction) => {
    setDecisionAction(action);
    setDecisionSaving(true);
    setDecisionNoticeType('saving');
    setDecisionNotice('Saving decision...');

    try {
      const response = await fetch(`${API_BASE_URL}/api/invoices/${selectedInvoiceId}/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action.toLowerCase() }),
      });
      if (!response.ok) throw new Error('Decision save failed');
      await response.json();
      setDecisionNoticeType('success');
      setDecisionNotice(`${action} saved to the decision log.`);
    } catch {
      setDecisionNoticeType('error');
      setDecisionNotice('Decision could not be saved. Check that the API is running.');
    } finally {
      setDecisionSaving(false);
    }
  };

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void document.documentElement.requestFullscreen();
    }
  };

  const renderEvidenceCards = () => {
    const show = (tab: ContextTab) => contextTab === 'all' || contextTab === tab;

    return (
      <div className="evidence-grid">
        {show('purchase-order') ? (
          <article className="evidence-card po-card">
            <div className="evidence-card-heading">
              <span className="evidence-icon"><FileText size={17} /></span>
              <h3>Purchase Order</h3>
              <span className="evidence-link">{analysis.po?.po_id ?? 'Not linked'}</span>
            </div>
            {analysis.po ? (
              <>
                <div className="evidence-primary">{formatMoney(analysis.po.po_amount, currency)}</div>
                <div className="evidence-meta">
                  <span>{analysis.po.status ?? 'Status unavailable'}</span>
                  <span className="inline-status status-good"><Check size={12} /> PO record found</span>
                </div>
              </>
            ) : (
              <div className="empty-evidence">No purchase order is linked to this invoice.</div>
            )}
          </article>
        ) : null}

        {show('invoice-lines') ? (
          <article className="evidence-card exceptions-card">
            <div className="evidence-card-heading">
              <span className="evidence-icon"><FileText size={17} /></span>
              <h3>Invoice Lines</h3>
              <span className="count-chip">{analysis.invoice_lines?.length ?? 0}</span>
            </div>
            {analysis.invoice_lines?.length ? (
              <ul className="invoice-line-list">
                {analysis.invoice_lines.slice(0, 4).map((line) => (
                  <li key={line.invoice_line_id}>
                    <span>{line.description}</span>
                    <strong>{Number(line.quantity ?? 0).toLocaleString()} × {formatMoney(line.unit_price, currency)}</strong>
                    <small>{formatMoney(line.line_amount, currency)}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-evidence">No line-item records are available.</div>
            )}
          </article>
        ) : null}

        {show('history') ? (
          <article className="evidence-card">
            <div className="evidence-card-heading">
              <span className="evidence-icon"><History size={17} /></span>
              <h3>Supplier History</h3>
              <span className={`risk-chip risk-${String(supplier.risk_band ?? 'low').toLowerCase()}`}>
                {supplier.risk_band ?? 'No risk band'}
              </span>
            </div>
            <div className="history-metrics">
              <div><strong>{supplier.exception_history ?? 0}</strong><span>Prior exceptions</span></div>
              <div><strong>{formatMoney(supplier.last_invoice_total, currency)}</strong><span>Last invoice total</span></div>
            </div>
            <div className="evidence-meta">Supplier ID {supplier.supplier_id ?? 'unavailable'}</div>
          </article>
        ) : null}

        {show('payments') ? (
          <article className="evidence-card">
            <div className="evidence-card-heading">
              <span className="evidence-icon"><CreditCard size={17} /></span>
              <h3>Payment</h3>
            </div>
            <div className="evidence-primary payment-value">{invoice.payment_status ?? 'No payment status'}</div>
            <div className="evidence-meta">Payment record shown in the invoice fixture</div>
          </article>
        ) : null}

        {show('exceptions') ? (
          <article className="evidence-card exceptions-card">
            <div className="evidence-card-heading">
              <span className="evidence-icon"><AlertTriangle size={17} /></span>
              <h3>Existing Exceptions</h3>
              <span className="count-chip">{exceptions.length}</span>
            </div>
            {exceptions.length ? (
              <ul className="exception-list">
                {exceptions.map((item) => (
                  <li key={item.exception_id ?? item.type}>
                    <span className="exception-name">{item.type}</span>
                    <span className="exception-description">{item.description}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-evidence">No exceptions are attached to this invoice.</div>
            )}
          </article>
        ) : null}
      </div>
    );
  };

  const renderInvoiceDataTables = () => {
    const show = (_tab: string) => true;
    const invoiceCurrency = String(invoice.currency ?? 'USD');
    const duplicateMatches = analysis.duplicate_matches ?? [];
    const issueTone = (codes: string[]): 'warning' | 'fail' | undefined => {
      if (checks.some((check) => codes.includes(check.code) && check.status === 'fail')) return 'fail';
      if (checks.some((check) => codes.includes(check.code) && check.status === 'warning')) return 'warning';
      return undefined;
    };
    const repeatedTone = (count: number, codes: string[]) => Array.from({ length: count }, () => issueTone(codes));

    return (
      <div className="evidence-grid">
        {show('invoice') ? (
          <article className="evidence-card evidence-wide">
            <div className="evidence-card-heading"><span className="evidence-icon"><FileText size={17} /></span><h3>Invoice Record</h3><span className="evidence-link">{invoice.invoice_id}</span></div>
            <EvidenceTable
              caption="Invoice fields used in analysis"
              columns={['Field', 'Value']}
              rows={[
                ['Invoice ID', String(invoice.invoice_id ?? '')], ['Invoice number', String(invoice.invoice_number ?? '')],
                ['Supplier ID', String(invoice.supplier_id ?? '')], ['PO ID', String(invoice.po_id ?? '')],
                ['Invoice date', formatDate(invoice.invoice_date)], ['Due date', formatDate(invoice.due_date)],
                ['Received at', formatDate(invoice.received_at)], ['Net amount', formatMoney(invoice.net_amount, invoiceCurrency)],
                ['Tax amount', formatMoney(invoice.tax_amount, invoiceCurrency)], ['Gross amount', formatMoney(invoice.gross_amount, invoiceCurrency)],
                ['Amount USD', formatMoney(invoice.amount_usd, 'USD')], ['Currency', invoiceCurrency],
                ['Approval level', String(invoice.approval_level ?? '')], ['Channel', String(invoice.channel ?? '')],
                ['OCR confidence', invoice.ocr_confidence == null ? '' : `${Math.round(Number(invoice.ocr_confidence) * 100)}%`],
                ['Processor', String(invoice.processor_employee_id ?? '')], ['Status', String(invoice.status ?? '')],
                ['Payment status', String(invoice.payment_status ?? '')],
              ]}
              rowTones={[
                undefined, undefined, undefined, issueTone(['MISSING_PO', 'PO_NOT_FOUND']), undefined, undefined,
                undefined, undefined, undefined, issueTone(['PO_AMOUNT_EXCEEDED']), undefined, undefined,
                issueTone(['APPROVAL_POLICY_UNVERIFIED']), undefined, undefined, undefined, undefined,
                issueTone(['PAYMENT_STATUS']),
              ]}
              emptyMessage="Invoice fields are unavailable."
            />
          </article>
        ) : null}

        {show('purchase-order') ? (
          <article className="evidence-card po-card">
            <div className="evidence-card-heading"><span className="evidence-icon"><FileText size={17} /></span><h3>Purchase Order</h3><span className="evidence-link">{analysis.po?.po_id ?? 'Not linked'}</span></div>
            <EvidenceTable
              caption="Purchase order fields"
              columns={['Field', 'Value']}
              rows={analysis.po ? [
                ['PO ID', String(analysis.po.po_id ?? '')], ['Supplier ID', String(analysis.po.supplier_id ?? '')],
                ['PO date', formatDate(analysis.po.po_date)], ['Amount', formatMoney(analysis.po.po_amount, String(analysis.po.currency ?? invoiceCurrency))],
                ['Currency', String(analysis.po.currency ?? '')], ['Cost center', String(analysis.po.cost_center_id ?? '')],
                ['Requester', String(analysis.po.requester_employee_id ?? '')], ['Approver', String(analysis.po.approver_employee_id ?? '')],
                ['Status', String(analysis.po.status ?? '')],
              ] : []}
              rowTones={analysis.po ? [issueTone(['PO_NOT_FOUND']), undefined, undefined, issueTone(['PO_AMOUNT_EXCEEDED']), undefined, undefined, undefined, undefined, undefined] : []}
              emptyMessage="No purchase order is linked to this invoice."
            />
          </article>
        ) : null}

        {show('invoice-lines') ? (
          <article className="evidence-card evidence-wide">
            <div className="evidence-card-heading"><span className="evidence-icon"><FileText size={17} /></span><h3>Invoice Lines</h3><span className="count-chip">{analysis.invoice_lines?.length ?? 0}</span></div>
            <EvidenceTable
              caption="Invoice line items"
              columns={['Line ID', 'Invoice ID', 'Line', 'Description', 'Quantity', 'Unit price', 'Line amount', 'GL account', 'Cost center']}
              rows={(analysis.invoice_lines ?? []).map((line) => [
                String(line.invoice_line_id ?? ''), String(line.invoice_id ?? ''), String(line.line_no ?? ''),
                String(line.description ?? ''), Number(line.quantity ?? 0).toLocaleString(),
                formatMoney(line.unit_price, invoiceCurrency), formatMoney(line.line_amount, invoiceCurrency),
                String(line.gl_account ?? ''), String(line.cost_center_id ?? ''),
              ])}
              rowTones={repeatedTone(analysis.invoice_lines?.length ?? 0, ['PO_AMOUNT_EXCEEDED'])}
              emptyMessage="No line-item records are available."
            />
          </article>
        ) : null}

        {show('history') ? (
          <article className="evidence-card evidence-wide">
            <div className="evidence-card-heading"><span className="evidence-icon"><History size={17} /></span><h3>Supplier Record</h3><span className="count-chip">{supplier.exception_history ?? 0} prior exceptions</span></div>
            <EvidenceTable
              caption="Supplier fields used in analysis"
              columns={['Field', 'Value']}
              rows={[
                ['Supplier ID', String(supplier.supplier_id ?? '')], ['Entity ID', String(supplier.entity_id ?? '')],
                ['Name', String(supplier.supplier_name ?? '')], ['Category', String(supplier.category ?? '')],
                ['Country', String(supplier.country ?? '')], ['Payment terms', supplier.payment_terms_days == null ? '' : `${supplier.payment_terms_days} days`],
                ['Risk tier', String(supplier.risk_tier ?? supplier.risk_band ?? '')], ['Preferred', String(supplier.preferred ?? '')],
                ['Onboarded', formatDate(supplier.onboarded_date)], ['Status', String(supplier.status ?? '')],
                ['Exception history', String(supplier.exception_history ?? 0)],
              ]}
              emptyMessage="Supplier details are unavailable."
            />
          </article>
        ) : null}

        {show('history') ? (
          <article className="evidence-card evidence-wide">
            <div className="evidence-card-heading"><span className="evidence-icon"><History size={17} /></span><h3>Previous Invoices</h3><span className="count-chip">{analysis.previous_invoices?.length ?? 0}</span></div>
            <EvidenceTable
              caption="Prior invoices for this supplier"
              columns={['Invoice ID', 'Invoice number', 'Invoice date', 'Gross amount', 'Amount USD', 'Currency', 'Status']}
              rows={(analysis.previous_invoices ?? []).map((item) => [
                String(item.invoice_id ?? ''), String(item.invoice_number ?? ''), formatDate(item.invoice_date),
                formatMoney(item.gross_amount, String(item.currency ?? invoiceCurrency)), formatMoney(item.amount_usd, 'USD'),
                String(item.currency ?? ''), String(item.status ?? ''),
              ])}
              rowTones={repeatedTone(analysis.previous_invoices?.length ?? 0, ['NEAR_DUPLICATE'])}
              emptyMessage="No previous invoices were included in this analysis."
            />
          </article>
        ) : null}

        {show('history') ? (
          <article className="evidence-card evidence-wide">
            <div className="evidence-card-heading"><span className="evidence-icon"><AlertTriangle size={17} /></span><h3>Duplicate Matches</h3><span className="count-chip">{duplicateMatches.length}</span></div>
            <EvidenceTable
              caption="Exact duplicate invoice matches"
              columns={['Invoice ID', 'Invoice number', 'Supplier ID', 'Invoice date', 'Status']}
              rows={duplicateMatches.map((item) => [String(item.invoice_id ?? ''), String(item.invoice_number ?? ''), String(item.supplier_id ?? ''), formatDate(item.invoice_date), String(item.status ?? '')])}
              rowTones={repeatedTone(duplicateMatches.length, ['DUPLICATE_INVOICE'])}
              emptyMessage="No duplicate matches were found."
            />
          </article>
        ) : null}

        {show('payments') ? (
          <article className="evidence-card">
            <div className="evidence-card-heading"><span className="evidence-icon"><CreditCard size={17} /></span><h3>Payments</h3><span className="count-chip">{analysis.payments?.length ?? 0}</span></div>
            <EvidenceTable
              caption="Payment records linked to this invoice"
              columns={['Payment ID', 'Invoice ID', 'Paid at', 'Amount', 'Currency', 'Method', 'Payment run', 'Days vs due']}
              rows={(analysis.payments ?? []).map((payment) => [
                String(payment.payment_id ?? ''), String(payment.invoice_id ?? ''), formatDate(payment.paid_at),
                formatMoney(payment.amount, String(payment.currency ?? invoiceCurrency)),
                String(payment.currency ?? ''), String(payment.method ?? ''), String(payment.payment_run_id ?? ''),
                payment.days_vs_due == null ? '' : String(payment.days_vs_due),
              ])}
              rowTones={repeatedTone(analysis.payments?.length ?? 0, ['PAYMENT_STATUS'])}
              emptyMessage="No payment records are linked to this invoice."
            />
          </article>
        ) : null}

        {show('exceptions') ? (
          <article className="evidence-card evidence-wide">
            <div className="evidence-card-heading"><span className="evidence-icon"><AlertTriangle size={17} /></span><h3>Existing Exceptions</h3><span className="count-chip">{exceptions.length}</span></div>
            <EvidenceTable
              caption="Exception records linked to this invoice"
              columns={['Exception ID', 'Invoice ID', 'Type', 'Raised', 'Resolved', 'Resolver', 'Resolution']}
              rows={exceptions.map((item) => [
                String(item.exception_id ?? ''), String(item.invoice_id ?? ''), String(item.type ?? item.exception_type ?? ''), formatDate(item.raised_at),
                formatDate(item.resolved_at), String(item.resolver_employee_id ?? ''), String(item.resolution ?? item.description ?? ''),
              ])}
              rowTones={repeatedTone(exceptions.length, ['BANK_DETAILS_CHANGED', 'EXISTING_EXCEPTION'])}
              emptyMessage="No exceptions are attached to this invoice."
            />
          </article>
        ) : null}

        {show('exceptions') ? (
          <article className="evidence-card evidence-wide">
            <div className="evidence-card-heading"><span className="evidence-icon"><ShieldCheck size={17} /></span><h3>Rule Checks</h3><span className="count-chip">{checks.length}</span></div>
            <EvidenceTable
              caption="Deterministic checks applied to this invoice"
              columns={['Check', 'Status', 'Details']}
              rows={checks.map((check) => [check.title, statusStyleMap[check.status].label, check.details])}
              rowTones={checks.map((check) => check.status === 'fail' ? 'fail' : check.status === 'warning' ? 'warning' : undefined)}
              emptyMessage="No rule checks are available."
            />
          </article>
        ) : null}
      </div>
    );
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#main-content" aria-label="OrbitIQ home">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span className="brand-copy"><strong>OrbitIQ</strong><small>Smarter invoices.<br />Stronger decisions.</small></span>
        </a>

        <nav className="side-nav" aria-label="Main navigation">
          {NAV_ITEMS.map(({ label, icon: Icon }) => (
              <button
                className={`nav-item${label === activePage ? ' nav-item-active' : ''}`}
                key={label}
                disabled={label !== 'Invoices' && label !== 'Decision Log'}
                aria-current={label === activePage ? 'page' : undefined}
                onClick={() => { if (label === 'Invoices' || label === 'Decision Log') setActivePage(label); }}
              >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
              {label === 'Exceptions' && exceptions.length > 0 ? <span className="nav-count">{exceptions.length}</span> : null}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="footer-orbit" aria-hidden="true" />
          <div className="footer-label">DEMO ENVIRONMENT</div>
          <p>Synthetic invoice records</p>
          <span className={`footer-indicator${apiUnavailable ? ' footer-indicator-offline' : ''}`}><span />{apiUnavailable ? 'API offline' : 'API connected'}</span>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="search-box">
            <Search size={17} />
            <input
              aria-label={activePage === 'Invoices' ? 'Search invoices' : 'Filter decisions'}
              list={activePage === 'Invoices' ? 'invoice-id-options' : undefined}
              placeholder={activePage === 'Invoices' ? 'Search or choose invoice ID...' : 'Filter by invoice or action...'}
              value={activePage === 'Invoices' ? searchQuery : decisionSearch}
              onChange={(event) => {
                const query = event.target.value;
                if (activePage === 'Decision Log') {
                  setDecisionSearch(query);
                  return;
                }
                setSearchQuery(query);
                const matchingInvoice = invoiceOptions.find((option) => option.invoice_id.toLowerCase() === query.trim().toLowerCase());
                if (matchingInvoice) {
                  setSelectedInvoiceId(matchingInvoice.invoice_id);
                  setDecisionAction(null);
                  setDecisionNotice('');
                  setDecisionNoticeType(null);
                }
              }}
              onKeyDown={(event) => { if (event.key === 'Enter' && activePage === 'Invoices') void searchInvoice(); }}
            />
            {activePage === 'Invoices' ? (
              <>
                <datalist id="invoice-id-options">
                  {invoiceOptions.map((option) => <option key={option.invoice_id} value={option.invoice_id}>{option.supplier_name}</option>)}
                </datalist>
                <button aria-label="Select matching invoice" className="search-submit" onClick={() => void searchInvoice()}>
                  <ArrowUpRight size={15} />
                </button>
              </>
            ) : null}
          </div>
          <div className="topbar-actions">
            <button className="icon-button notification-button" aria-label="Notifications">
              <Bell size={18} />
              <span />
            </button>
            <div className="profile-block">
              <span className="profile-avatar">AP</span>
              <span className="profile-copy">
                <select className="profile-role-select" aria-label="Demo role" value={demoRole} onChange={(event) => setDemoRole(event.target.value as DemoRole)}>
                  <option value="AP Analyst">AP Analyst</option>
                  <option value="AP Team Lead">AP Team Lead</option>
                  <option value="AP Manager">AP Manager</option>
                </select>
                <small>Review workspace</small>
              </span>
            </div>
          </div>
        </header>

        <main id="main-content" className="main-content">
          {activePage === 'Invoices' ? <>
          <section className="page-heading">
            <div>
              <div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Invoices</strong></div>
              <h1>Invoice Review</h1>
              <p className="page-subtitle">{supplier.supplier_name ?? invoice.supplier_name ?? 'Supplier'} <span>·</span> {invoice.invoice_id ?? selectedInvoiceId}</p>
            </div>
            <div className="invoice-controls">
              <div className="invoice-view-toggle" role="group" aria-label="Invoice view">
                <button type="button" aria-pressed={invoiceView === 'review'} onClick={() => setInvoiceView('review')}>Review</button>
                <button type="button" aria-pressed={invoiceView === 'data'} onClick={() => setInvoiceView('data')}>Data</button>
              </div>
              <button className="icon-button control-button" aria-label="Previous invoice" onClick={() => selectAdjacentInvoice(-1)}>
                <ChevronLeft size={17} />
              </button>
              <span className="record-position">{currentIndex + 1} of {availableInvoiceIds.length}</span>
              <button className="icon-button control-button" aria-label="Next invoice" onClick={() => selectAdjacentInvoice(1)}>
                <ChevronRight size={17} />
              </button>
              <button className="fullscreen-button" onClick={toggleFullscreen}><Maximize2 size={15} /> Full screen</button>
            </div>
          </section>

          <div className={`data-banner${apiUnavailable ? ' data-banner-warning' : ''}`}>
            <span className="data-banner-dot" />
            <span>{apiUnavailable ? 'API unavailable · showing synthetic fallback' : `Data source · ${analysis.data_source}`}</span>
            <span className="banner-divider" />
            <span>{analysis.ai_enabled ? 'AI analysis connected' : 'AI analysis disabled'}</span>
            {loading ? <span className="loading-label"><span className="loading-spinner" /> Analyzing</span> : null}
          </div>

          {invoiceView === 'review' ? <>
          <section className="metrics-grid" aria-label="Invoice overview">
            <article className="metric-card metric-green">
              <span className="metric-icon"><FileText size={20} /></span>
              <div><span className="metric-label">Invoices in dataset</span><strong className="metric-value">{Number(analysis.invoice_count ?? availableInvoiceIds.length).toLocaleString()}</strong><small>Curated finance records</small></div>
            </article>
            <article className="metric-card metric-amber">
              <span className="metric-icon"><AlertTriangle size={20} /></span>
              <div><span className="metric-label">Open exceptions</span><strong className="metric-value">{exceptions.length.toString().padStart(2, '0')}</strong><small>For selected invoice</small></div>
            </article>
            <article className="metric-card metric-mint">
              <span className="metric-icon"><ShieldCheck size={20} /></span>
              <div><span className="metric-label">Checks passed</span><strong className="metric-value">{passedChecks}<small className="metric-total"> / {checks.length}</small></strong><small>Deterministic controls</small></div>
            </article>
            <article className="metric-card metric-rose">
              <span className="metric-icon"><Gauge size={20} /></span>
              <div><span className="metric-label">Risk level</span><strong className="metric-value metric-risk">{aiAnalysis.risk_level ?? 'Unknown'}</strong><small>Current recommendation</small></div>
            </article>
          </section>

          <section className="review-grid" aria-label="Invoice review panels">
            <article className="surface invoice-panel">
              <div className="panel-heading">
                <div><h2>Invoice Details</h2><span className="panel-kicker">Record overview</span></div>
                <button className="icon-button subtle-button" aria-label="More invoice details"><MoreHorizontal size={18} /></button>
              </div>

              <div className="detail-list">
                <div className="detail-row"><span>Invoice ID</span><strong>{invoice.invoice_id ?? selectedInvoiceId}</strong></div>
                <div className="detail-row"><span>Supplier</span><strong className="detail-supplier"><Building2 size={15} />{supplier.supplier_name ?? invoice.supplier_name ?? 'Unknown supplier'}</strong></div>
                <div className="detail-row"><span>Amount</span><strong className="amount-value">{formatMoney(invoice.gross_amount, currency)}</strong></div>
                <div className="detail-row"><span>Invoice date</span><strong><CalendarDays size={15} />{formatDate(invoice.invoice_date)}</strong></div>
                <div className="detail-row"><span>Due date</span><strong><CalendarDays size={15} />{formatDate(invoice.due_date)}</strong></div>
                <div className="detail-row"><span>PO ID</span><strong className="po-value"><FileText size={15} />{invoice.po_id ?? 'Not linked'}</strong></div>
                <div className="detail-row"><span>Status</span><strong><span className="invoice-status"><span />{invoice.status ?? 'Unknown'}</span></strong></div>
              </div>

              <div className="source-block">
                <div className="source-file-icon"><FileText size={19} /></div>
                <div className="source-file-copy"><strong>Invoice record</strong><span>{invoice.channel ?? 'Structured fixture'}{invoice.ocr_confidence ? ` · OCR ${Math.round(invoice.ocr_confidence * 100)}%` : ''}</span></div>
                <span className="source-badge">DEMO</span>
              </div>
            </article>

            <article className="surface evidence-panel">
              <div className="panel-heading evidence-heading">
                <div><h2>Context &amp; Evidence</h2><span className="panel-kicker">Linked records and supplier context</span></div>
              </div>
              <div className="context-tabs" role="tablist" aria-label="Evidence categories">
                {CONTEXT_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    className={`context-tab${contextTab === tab.id ? ' context-tab-active' : ''}`}
                    role="tab"
                    aria-selected={contextTab === tab.id}
                    onClick={() => setContextTab(tab.id)}
                  >{tab.label}</button>
                ))}
              </div>
              {renderEvidenceCards()}
            </article>

            <aside className="surface recommendation-panel">
              <div className="panel-heading">
                <div><h2>Recommendation</h2><span className="panel-kicker">Policy and evidence outcome</span></div>
                <span className={`analysis-mode${analysis.ai_enabled ? ' mode-active' : ''}`}><Sparkles size={13} />{analysis.ai_enabled ? 'AI' : 'RULES'}</span>
              </div>

              <div className={`recommendation-banner ${recommendationClass}`}>
                <span className="recommendation-symbol">
                  {recommendationClass === 'recommendation-escalate' ? <CircleAlert size={22} /> : recommendationClass === 'recommendation-auto' ? <CircleCheck size={22} /> : <AlertTriangle size={22} />}
                </span>
                <div><strong>{recommendation}</strong><span>{recommendationClass === 'recommendation-auto' ? 'Eligible for analyst approval' : recommendationClass === 'recommendation-escalate' ? 'Escalation required' : 'Requires human review'}</span></div>
              </div>

              <div className="risk-summary">
                <div className="risk-summary-item"><span><Gauge size={16} /> Risk level</span><strong className={`risk-chip risk-${String(aiAnalysis.risk_level ?? 'low').toLowerCase()}`}>{aiAnalysis.risk_level ?? 'Unknown'}</strong></div>
                <div className="risk-summary-item"><span><ClipboardList size={16} /> Data status</span><strong>{analysis.ai_enabled ? 'AI assisted' : 'Rules only'}</strong></div>
              </div>

              <div className="analysis-summary">
                <div className="summary-heading"><Sparkles size={15} /><strong>Analysis summary</strong></div>
                <p>{aiAnalysis.summary}</p>
                {aiAnalysis.reasons?.length ? <ul>{aiAnalysis.reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}
                {aiAnalysis.evidence?.length ? (
                  <div className="evidence-references">
                    <span>Evidence IDs</span>
                    <div>{aiAnalysis.evidence.map((evidenceId) => <code key={evidenceId}>{evidenceId}</code>)}</div>
                  </div>
                ) : null}
              </div>

              <div className="hard-checks">
                <div className="checks-heading"><h3>Hard Rule Checks</h3><span>{passedChecks}/{checks.length} passed</span></div>
                {checks.map((check) => {
                  const Icon = check.status === 'pass' ? CircleCheck : check.status === 'warning' ? CircleAlert : CircleX;
                  return (
                    <div className={`hard-check hard-check-${check.status}`} key={check.code}>
                      <Icon size={15} />
                      <span>{check.title}</span>
                      <strong>{statusStyleMap[check.status].label}</strong>
                    </div>
                  );
                })}
              </div>

              {analysis.red_team_review ? (
                <div className={`red-team-review red-team-${analysis.red_team_review.status.toLowerCase()}`}>
                  <div className="red-team-review-heading">
                    <div><h3>Red-Team Reviewer</h3><span>Independent deterministic control pass</span></div>
                    <strong>{analysis.red_team_review.status}</strong>
                  </div>
                  <p>{analysis.red_team_review.summary}</p>
                  {analysis.red_team_review.challenged_flags.length ? <div className="red-team-flags">Challenged: {analysis.red_team_review.challenged_flags.join(', ')}</div> : null}
                  {analysis.red_gate ? (
                    <div className="red-gate-outcome"><span>Red Gate · {analysis.red_gate.status}</span><strong>{analysis.red_gate.recommendation}</strong></div>
                  ) : null}
                </div>
              ) : null}

              <div className="decision-actions">
                <button className={`decision-button action-approve${decisionAction === 'Approve' ? ' action-selected' : ''}`} aria-pressed={decisionAction === 'Approve'} disabled={decisionSaving} onClick={() => void saveDecision('Approve')}><Check size={16} />Approve</button>
                <button className={`decision-button action-reject${decisionAction === 'Reject' ? ' action-selected' : ''}`} aria-pressed={decisionAction === 'Reject'} disabled={decisionSaving} onClick={() => void saveDecision('Reject')}><CircleX size={16} />Reject</button>
                <button className={`decision-button action-escalate${decisionAction === 'Escalate' ? ' action-selected' : ''}`} aria-pressed={decisionAction === 'Escalate'} disabled={decisionSaving} onClick={() => void saveDecision('Escalate')}><Users size={16} />Escalate</button>
              </div>
              {decisionNotice ? <div className={`action-notice action-notice-${decisionNoticeType}`} role="status" aria-live="polite">{decisionNoticeType === 'success' ? <CircleCheck size={14} /> : <CircleAlert size={14} />}{decisionNotice}</div> : null}
            </aside>
          </section>

          <section className="surface story-panel">
            <div className="story-heading">
              <div><h2>Decision Story</h2><span className="panel-kicker">Analysis path for {invoice.invoice_id ?? selectedInvoiceId}</span></div>
              <span className="story-live"><span /> {loading ? 'Updating' : 'Current record'}</span>
            </div>
            <ol className="timeline">
              {analysis.decision_story.map((step, index) => (
                <li className={`timeline-step${index === analysis.decision_story.length - 1 ? ' timeline-current' : ''}`} key={`${index}-${step}`}>
                  <span className="timeline-marker">{index === analysis.decision_story.length - 1 ? <Clock3 size={16} /> : <Check size={15} />}</span>
                  <span className="timeline-copy"><strong>{step}</strong><small>Step {String(index + 1).padStart(2, '0')}</small></span>
                </li>
              ))}
            </ol>
          </section>

          </> : (
            <section className="invoice-data-view" aria-label="Invoice data and manual checks">
              <section className="surface manual-review-panel" aria-labelledby="manual-review-heading">
                <div className="panel-heading">
                  <div><h2 id="manual-review-heading">Manual Check Signals</h2><span className="panel-kicker">Start with these records before making a decision</span></div>
                  <span className="count-chip">{manualReviewSignals.length} signals</span>
                </div>
                <EvidenceTable
                  caption={`Checks requiring analyst verification for ${invoice.invoice_id ?? selectedInvoiceId}`}
                  columns={['Signal', 'Severity', 'Look in', 'Verify']}
                  rows={manualReviewSignals.map((signal) => [signal.title, statusStyleMap[signal.status].label, signal.lookIn, signal.verify])}
                  rowTones={manualReviewSignals.map((signal) => signal.status === 'fail' ? 'fail' : 'warning')}
                  emptyMessage="No flagged checks. Confirm the recommendation and approval policy before proceeding."
                />
              </section>

              <section className="invoice-data-panel" aria-labelledby="invoice-data-heading">
                <div className="story-heading">
                  <div><h2 id="invoice-data-heading">Source Tables</h2><span className="panel-kicker">Invoice-related records used by the analysis</span></div>
                  <span className="story-live">{invoice.invoice_id ?? selectedInvoiceId}</span>
                </div>
                {renderInvoiceDataTables()}
              </section>
            </section>
          )}

          <footer className="page-footer"><span>OrbitIQ · Invoice Intelligence</span><span>Demo data only · Decisions stored locally</span></footer>
          </> : <>
            <section className="page-heading decision-page-heading">
              <div>
                <div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Decision Log</strong></div>
                <h1>Decision Log</h1>
                <p className="page-subtitle">Saved analyst actions · {decisionRecords.length} total</p>
              </div>
              <button className="fullscreen-button" onClick={() => setDecisionLogRefresh((value) => value + 1)} disabled={decisionLogLoading}>
                <History size={15} /> {decisionLogLoading ? 'Refreshing...' : 'Refresh log'}
              </button>
            </section>

            {decisionLogError ? <div className="log-error" role="alert">{decisionLogError}</div> : null}

            <section className="decision-log-surface surface" aria-label="Saved decisions">
              <div className="decision-log-toolbar">
                <div className="decision-filters" role="group" aria-label="Filter decisions by action">
                  {(['all', 'approve', 'reject', 'escalate'] as DecisionFilter[]).map((filter) => (
                    <button key={filter} className={`decision-filter${decisionFilter === filter ? ' decision-filter-active' : ''}`} aria-pressed={decisionFilter === filter} onClick={() => setDecisionFilter(filter)}>
                      {filter === 'all' ? 'All actions' : filter}
                    </button>
                  ))}
                </div>
                <span className="log-count">{filteredDecisions.length} shown</span>
              </div>

              {decisionLogLoading && !decisionRecords.length ? (
                <div className="log-empty"><span className="loading-spinner" /> Loading decisions...</div>
              ) : filteredDecisions.length ? (
                <div className="decision-table-wrap">
                  <table className="decision-table">
                    <thead><tr><th>Invoice</th><th>Action</th><th>Recorded</th><th>Entry</th><th /></tr></thead>
                    <tbody>
                      {filteredDecisions.map((record) => (
                        <tr key={record.id}>
                          <td><strong className="log-invoice-id">{record.invoice_id}</strong></td>
                          <td><span className={`log-action log-action-${record.action}`}>{record.action}</span></td>
                          <td className="log-timestamp">{formatTimestamp(record.created_at)}</td>
                          <td className="log-entry-id">#{record.id}</td>
                          <td><button className="open-invoice-button" onClick={() => openDecisionInvoice(record.invoice_id)}>Open invoice <ChevronRight size={14} /></button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="log-empty">
                  {decisionRecords.length ? 'No decisions match this filter.' : 'No decisions have been recorded yet.'}
                </div>
              )}
            </section>
            <footer className="page-footer"><span>OrbitIQ · Decision history</span><span>Stored locally in SQLite</span></footer>
          </>}
        </main>
      </div>
    </div>
  );
}

export default App;
