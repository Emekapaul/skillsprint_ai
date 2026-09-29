import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Loader2,
  LockKeyhole,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  Users,
  XCircle,
} from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://localhost:5000/api";

type DocumentRow = {
  document_id: string;
  title: string | null;
  filename: string | null;
  file_type: string | null;
  version: string;
  status: string;
  file_hash: string | null;
  page_count: number;
  source_parts: number;
  chunks: number;
  prompt_injection_flags: number;
  effective_date?: string | null;
  document_type?: string | null;
};
type DocumentChunk = {
  document_id: string;
  chunk_id: string;
  version: string;
  section_id: string;
  heading: string | null;
  location: string;
  page: number | null;
  text: string;
  prompt_injection_flags: string[];
};

type DocumentDetail = DocumentRow & {
  chunks: DocumentChunk[];
};
type Requirement = {
  requirement_id: string;
  role: string;
  title: string;
  category: string;
  mandatory: boolean;
  priority: string;
  source: {
    document_id: string;
    document_version: string;
    section_id: string;
    location: string;
  };
  requirement_text: string;
  competency?: string | null;
  assessment_required?: boolean | null;
  due_stage?: string | null;
  origin?: string;
};
type Plan = {
  plan_id: string;
  role: string;
  employee_id: string;
  modules: unknown[];
  tasks: unknown[];
  quiz: unknown[];
};
type Validation = {
  status: string;
  coverage_score: number;
  traceability_score: number;
  mandatory_total: number;
  mandatory_covered: number;
  missing_requirement_ids: string[];
  unsupported_requirement_ids: string[];
  duplicate_requirement_ids: string[];
  findings: {
    code: string;
    severity: string;
    message: string;
    requirement_id?: string;
  }[];
};

type Dashboard = {
  documents: number;
  active_documents?: number;
  obsolete_documents?: number;
  roles: number;
  requirements: number;
  plans: number;
  validated_plans: number;
};

async function api(path: string, options?: RequestInit) {
  const res = await fetch(`${API}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}

const nav = [
  ["dashboard", "Overview", LayoutDashboard],
  ["documents", "Knowledge Sources", FileText],
  ["requirements", "Requirement Matrix", ClipboardCheck],
  ["generate", "AI Generation", Sparkles],
  ["validate", "Verification", ShieldCheck],
  ["comparison", "AI ↔ Python", BarChart3],
] as const;

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [roles, setRoles] = useState<string[]>([]);
  const [role, setRole] = useState("Customer Support Executive");
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard>({
    documents: 0,
    active_documents: 0,
    obsolete_documents: 0,
    roles: 0,
    requirements: 0,
    plans: 0,
    validated_plans: 0,
  });
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);

  const refresh = async () => {
    const [r, d, stats] = await Promise.all([
      api("/roles"),
      api("/documents"),
      api("/dashboard"),
    ]);
    setRoles(r.roles);
    setDocuments(d.documents);
    setDashboard(stats);
  };

  useEffect(() => {
    refresh().catch((e) => setNotice({ type: "error", text: e.message }));
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setLoading(true);
    setNotice(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setNotice({
        type: "error",
        text: e instanceof Error ? e.message : "Something went wrong",
      });
    } finally {
      setLoading(false);
    }
  };

  const buildMatrix = () =>
    run(async () => {
      const data = await api("/matrix/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      setRequirements(data.requirements);
      setNotice({
        type: "success",
        text: `${data.count} requirements mapped for ${role}.`,
      });
    });

  const generate = (provider = "demo") =>
    run(async () => {
      const data = await api("/onboarding/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role,
          provider,
          employee: {
            employee_id: "EMP-001",
            name: "Demo Employee",
            role,
            department: "Operations",
            experience_level: "Intermediate",
          },
        }),
      });
      setPlan(data.plan);
      setValidation(null);
      setPage("validate");
      setNotice({
        type: "success",
        text: "Structured onboarding plan generated.",
      });
    });

  const validate = () =>
    run(async () => {
      if (!plan) throw new Error("Generate an onboarding plan first.");
      const data = await api("/onboarding/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: plan.plan_id }),
      });
      setValidation(data.validation);
      setPage("validate");
    });

  const pageTitle = useMemo(
    () => nav.find((n) => n[0] === page)?.[1] || "Overview",
    [page],
  );

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={19} />
          </div>
          <div>
            <strong>SkillSprint</strong>
            <span>AI</span>
          </div>
        </div>
        <div className="company-chip">
          <div className="avatar">SS</div>
          <div>
            <b>NovaCore Systems</b>
            <small>Admin workspace</small>
          </div>
        </div>
        <nav>
          {nav.map(([key, label, Icon]) => (
            <button
              key={key}
              className={page === key ? "nav-item active" : "nav-item"}
              onClick={() => setPage(key)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {page === key && <ChevronRight size={15} className="nav-arrow" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="security-mini">
            <LockKeyhole size={16} />
            <div>
              <b>Grounded mode</b>
              <small>Python validation enabled</small>
            </div>
          </div>
          <div className="version">v0.2 • competition build</div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">ONBOARDING INTELLIGENCE</div>
            <h1>{pageTitle}</h1>
          </div>
          <div className="top-actions">
            <div className="role-picker">
              <label>Active role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {roles.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </div>
            <button
              className="icon-btn"
              onClick={() => refresh()}
              title="Refresh"
            >
              <RefreshCw size={18} />
            </button>
            <div className="user-avatar">EM</div>
          </div>
        </header>

        {notice && (
          <div className={`notice ${notice.type}`}>
            {notice.type === "success" ? (
              <CheckCircle2 size={18} />
            ) : notice.type === "error" ? (
              <XCircle size={18} />
            ) : (
              <AlertTriangle size={18} />
            )}
            <span>{notice.text}</span>
          </div>
        )}
        {loading && (
          <div className="loading-line">
            <Loader2 size={15} className="spin" /> Processing request…
          </div>
        )}

        {page === "dashboard" && (
          <DashboardPage
            dashboard={dashboard}
            documents={documents}
            onGo={setPage}
          />
        )}
        {page === "documents" && (
          <DocumentsPage
            documents={documents}
            loading={loading}
            setNotice={setNotice}
          />
        )}
        {page === "requirements" && (
          <RequirementsPage
            role={role}
            requirements={requirements}
            onBuild={buildMatrix}
            loading={loading}
          />
        )}
        {page === "generate" && (
          <GeneratePage
            role={role}
            requirements={requirements}
            onGenerate={generate}
            loading={loading}
          />
        )}
        {page === "validate" && (
          <ValidationPage
            plan={plan}
            validation={validation}
            onValidate={validate}
            onGenerate={() => setPage("generate")}
            loading={loading}
          />
        )}
        {page === "comparison" && <ComparisonPage plan={plan} />}
      </main>
    </div>
  );
}

function DashboardPage({
  dashboard,
  documents,
  onGo,
}: {
  dashboard: Dashboard;
  documents: DocumentRow[];
  onGo: (p: string) => void;
}) {
  return (
    <div className="page-body">
      <section className="hero-card">
        <div>
          <div className="pill">
            <ShieldCheck size={14} /> Source-grounded intelligence
          </div>
          <h2>
            Turn company knowledge into
            <br />
            <em>verified onboarding.</em>
          </h2>
          <p>
            Generate role-specific learning plans from approved documents, then
            independently verify every requirement with deterministic Python
            rules.
          </p>
          <div className="hero-actions">
            <button className="primary" onClick={() => onGo("documents")}>
              Open knowledge sources <ArrowRight size={16} />
            </button>
            <button className="ghost" onClick={() => onGo("validate")}>
              View verification
            </button>
          </div>
        </div>
        <div className="hero-orbit">
          <div className="orbit-ring ring-one"></div>
          <div className="orbit-ring ring-two"></div>
          <div className="core">
            <Sparkles size={32} />
            <span>AI</span>
          </div>
          <div className="float-card fc-one">
            <FileText size={14} /> Policies
          </div>
          <div className="float-card fc-two">
            <ShieldCheck size={14} /> Verified
          </div>
          <div className="float-card fc-three">
            <BookOpenCheck size={14} /> Learning
          </div>
        </div>
      </section>
      <div className="metrics">
        <Metric
          icon={FileText}
          label="Knowledge sources"
          value={dashboard.documents}
          sub="PDF / DOCX"
        />
        <Metric
          icon={Users}
          label="Role matrices"
          value={dashboard.roles}
          sub="mapped roles"
        />
        <Metric
          icon={ClipboardCheck}
          label="Requirements"
          value={dashboard.requirements}
          sub="ground-truth items"
        />
        <Metric
          icon={ShieldCheck}
          label="Validated plans"
          value={dashboard.validated_plans}
          sub="Python checked"
        />
      </div>
      <div className="two-col">
        <section className="panel">
          <div className="panel-head">
            <div>
              <span className="section-label">SYSTEM FLOW</span>
              <h3>How SkillSprint thinks</h3>
            </div>
            <Activity size={18} />
          </div>
          <div className="flow">
            <FlowStep
              n="01"
              title="Ingest"
              text="Extract PDF/DOCX content with source locations."
            />
            <FlowStep
              n="02"
              title="Ground"
              text="Map approved requirements to the selected role."
            />
            <FlowStep
              n="03"
              title="Generate"
              text="Produce structured onboarding JSON with GenAI."
            />
            <FlowStep
              n="04"
              title="Verify"
              text="Independently check coverage, sources and conflicts."
            />
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span className="section-label">KNOWLEDGE HEALTH</span>
              <h3>Source readiness</h3>
            </div>
            <ShieldCheck size={18} />
          </div>
          {documents.slice(0, 5).map((d) => (
            <div className="doc-row" key={d.document_id}>
              <div className="doc-icon">
                <FileText size={16} />
              </div>
              <div className="grow">
                <b>{d.document_id}</b>
                <small>
                  v{d.version} • {d.chunks} chunks
                </small>
              </div>
              <span
                className={d.prompt_injection_flags ? "tag warn" : "tag ok"}
              >
                {d.prompt_injection_flags
                  ? `${d.prompt_injection_flags} flagged`
                  : "clean"}
              </span>
            </div>
          ))}
          {documents.length === 0 && (
            <Empty text="Upload your first company documents." />
          )}
        </section>
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: any;
  label: string;
  value: number | string;
  sub: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-icon">
        <Icon size={18} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{sub}</small>
      </div>
    </div>
  );
}
function FlowStep({
  n,
  title,
  text,
}: {
  n: string;
  title: string;
  text: string;
}) {
  return (
    <div className="flow-step">
      <span>{n}</span>
      <div>
        <b>{title}</b>
        <p>{text}</p>
      </div>
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <FileText size={20} />
      <span>{text}</span>
    </div>
  );
}

function DocumentsPage({
  documents,
  loading,
  setNotice,
}: {
  documents: DocumentRow[];
  loading: boolean;
  setNotice: (n: any) => void;
}) {
  const [files, setFiles] = useState<FileList | null>(null);
  const [version, setVersion] = useState("auto");
  const [selectedDocument, setSelectedDocument] =
    useState<DocumentDetail | null>(null);

  const [detailLoading, setDetailLoading] = useState(false);

  const openDocument = async (documentId: string) => {
    setDetailLoading(true);

    try {
      const data = await api(`/documents/${encodeURIComponent(documentId)}`);

      setSelectedDocument(data.document);
    } catch (e) {
      setNotice({
        type: "error",
        text:
          e instanceof Error ? e.message : "Could not load document details.",
      });
    } finally {
      setDetailLoading(false);
    }
  };

  const upload = async () => {
    if (!files?.length) {
      return setNotice({
        type: "error",
        text: "Choose at least one PDF or DOCX file.",
      });
    }

    const form = new FormData();

    Array.from(files).forEach((file) => {
      form.append("files", file);
    });

    form.append("version", version);

    try {
      const data = await api("/documents/upload", {
        method: "POST",
        body: form,
      });

      setNotice({
        type: "success",
        text: `${data.documents.length} document(s) processed successfully.`,
      });

      // Refresh the current application state without a full browser reload.
      window.location.reload();
    } catch (e) {
      setNotice({
        type: "error",
        text: e instanceof Error ? e.message : "Upload failed",
      });
    }
  };

  return (
    <div className="page-body">
      <section className="panel upload-panel">
        <div className="panel-head">
          <div>
            <span className="section-label">KNOWLEDGE SOURCES</span>
            <h3>Upload approved company documents</h3>
            <p>
              PDF and DOCX are mandatory competition formats. Every extracted
              chunk keeps its document, version, section, and location
              reference.
            </p>
          </div>

          <FileText size={20} />
        </div>

        <label className="dropzone">
          <input
            type="file"
            accept=".pdf,.docx"
            multiple
            onChange={(e) => setFiles(e.target.files)}
          />

          <Upload size={28} />

          <b>Drop files here or click to browse</b>

          <span>PDF / DOCX • up to 20 MB per request</span>
        </label>

        {files?.length ? (
          <div className="selected-files">
            <span className="section-label">SELECTED FILES</span>

            {Array.from(files).map((file) => (
              <div className="doc-row" key={file.name}>
                <div className="doc-icon">
                  <FileText size={16} />
                </div>

                <div className="grow">
                  <b>{file.name}</b>

                  <small>{(file.size / 1024).toFixed(1)} KB</small>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        <div className="form-row">
          <label>
            Document version (use auto to read source metadata)
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="auto"
            />
          </label>

          <button className="primary" disabled={loading} onClick={upload}>
            {loading ? "Processing…" : "Process documents"}

            <ArrowRight size={16} />
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <span className="section-label">INGESTED</span>

            <h3>{documents.length} sources</h3>
          </div>

          <Search size={18} />
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th>
                <th>Version</th>
                <th>Type</th>
                <th>Chunks</th>
                <th>Status</th>
                <th>Security</th>
              </tr>
            </thead>

            <tbody>
              {documents.map((d) => (
                <tr
                  key={d.document_id}
                  className="clickable-row"
                  onClick={() => openDocument(d.document_id)}
                >
                  <td>
                    <div>
                      <b>{d.title || d.document_id}</b>

                      <small>{d.filename || d.document_id}</small>
                    </div>
                  </td>

                  <td>v{d.version}</td>

                  <td>{d.file_type?.replace(".", "").toUpperCase() || "—"}</td>

                  <td>{d.chunks}</td>

                  <td>
                    {d.status === "active" ? (
                      <span className="tag ok">Active</span>
                    ) : (
                      <span className="tag neutral">{d.status}</span>
                    )}
                  </td>

                  <td>
                    {d.prompt_injection_flags ? (
                      <span className="tag warn">
                        {d.prompt_injection_flags} flagged
                      </span>
                    ) : (
                      <span className="tag ok">Clean</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {documents.length === 0 && (
            <Empty text="No documents uploaded yet." />
          )}
        </div>
      </section>

      {documents.length > 0 && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <span className="section-label">SOURCE TRACEABILITY</span>

              <h3>Processing metadata</h3>
            </div>

            <ShieldCheck size={18} />
          </div>

          <div className="metrics four">
            <Metric
              icon={FileText}
              label="Sources"
              value={documents.length}
              sub="ingested documents"
            />

            <Metric
              icon={BookOpenCheck}
              label="Chunks"
              value={documents.reduce((total, d) => total + d.chunks, 0)}
              sub="traceable source chunks"
            />

            <Metric
              icon={Activity}
              label="Source parts"
              value={documents.reduce((total, d) => total + d.source_parts, 0)}
              sub="extracted source sections"
            />

            <Metric
              icon={ShieldCheck}
              label="Security flags"
              value={documents.reduce(
                (total, d) => total + d.prompt_injection_flags,
                0,
              )}
              sub="prompt-injection findings"
            />
          </div>
        </section>
      )}
      {selectedDocument && (
        <section className="panel document-detail-panel">
          <div className="panel-head">
            <div>
              <span className="section-label">SOURCE INSPECTOR</span>

              <h3>{selectedDocument.title || selectedDocument.document_id}</h3>

              <p>{selectedDocument.filename}</p>
            </div>

            <button className="ghost" onClick={() => setSelectedDocument(null)}>
              Close
            </button>
          </div>

          {detailLoading ? (
            <div className="empty-state">
              <p>Loading source chunks…</p>
            </div>
          ) : (
            <>
              <div className="detail-meta">
                <span>
                  <b>Document ID</b>
                  {selectedDocument.document_id}
                </span>

                <span>
                  <b>Version</b>
                  {selectedDocument.version}
                </span>

                <span>
                  <b>Status</b>
                  {selectedDocument.status}
                </span>

                <span>
                  <b>Type</b>
                  {selectedDocument.file_type}
                </span>

                <span>
                  <b>Chunks</b>
                  {selectedDocument.chunks.length}
                </span>

                <span>
                  <b>SHA-256</b>
                  {selectedDocument.file_hash}
                </span>
              </div>

              <div className="chunk-list">
                {selectedDocument.chunks.map((chunk) => (
                  <article className="source-chunk" key={chunk.chunk_id}>
                    <div className="chunk-header">
                      <div>
                        <span className="chunk-id">{chunk.chunk_id}</span>

                        <h4>{chunk.heading || chunk.section_id}</h4>
                      </div>

                      {chunk.prompt_injection_flags.length > 0 ? (
                        <span className="tag warn">Injection flagged</span>
                      ) : (
                        <span className="tag ok">Source clean</span>
                      )}
                    </div>

                    <div className="chunk-location">
                      <span>Section: {chunk.section_id}</span>

                      <span>Location: {chunk.location}</span>

                      {chunk.page !== null && <span>Page: {chunk.page}</span>}
                    </div>

                    <div className="source-text">{chunk.text}</div>

                    {chunk.prompt_injection_flags.length > 0 && (
                      <div className="finding warning">
                        <div>
                          <b>Prompt-injection findings</b>

                          <p>{chunk.prompt_injection_flags.join(", ")}</p>
                        </div>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}

function RequirementsPage({
  role,
  requirements,
  onBuild,
  loading,
}: {
  role: string;
  requirements: Requirement[];
  onBuild: () => void;
  loading: boolean;
}) {
  return (
    <div className="page-body">
      <section className="action-card">
        <div>
          <span className="section-label">ROLE GROUND TRUTH</span>
          <h2>{role}</h2>
          <p>
            Use the independent Role Requirement Matrix when available;
            otherwise derive source-backed candidate requirements from the
            currently ingested documents.
          </p>
        </div>
        <button className="primary" disabled={loading} onClick={onBuild}>
          {loading ? "Building…" : "Build / refresh matrix"}{" "}
          <RefreshCw size={16} />
        </button>
      </section>
      <section className="panel">
        <div className="panel-head">
          <div>
            <span className="section-label">REQUIREMENT MATRIX</span>
            <h3>{requirements.length} mapped requirements</h3>
            {requirements[0]?.origin && (
              <small>
                Source:{" "}
                {requirements[0].origin === "ground_truth"
                  ? "independent ground truth"
                  : "document extraction"}
              </small>
            )}
          </div>
          <ClipboardCheck size={18} />
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Requirement</th>
                <th>Type</th>
                <th>Mandatory</th>
                <th>Priority</th>
                <th>Competency</th>
                <th>Stage</th>
                <th>Assessment</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {requirements.map((r) => (
                <tr key={r.requirement_id}>
                  <td>
                    <code>{r.requirement_id}</code>
                  </td>
                  <td>
                    <b>{r.title}</b>
                    <small>{r.requirement_text}</small>
                  </td>
                  <td>{r.category}</td>
                  <td>
                    {r.mandatory ? (
                      <span className="tag ok">Required</span>
                    ) : (
                      <span className="tag neutral">Optional</span>
                    )}
                  </td>
                  <td>{r.priority}</td>
                  <td>{r.competency || "—"}</td>
                  <td>{r.due_stage || "—"}</td>
                  <td>{r.assessment_required ? "Required" : "—"}</td>
                  <td>
                    {r.source.document_id} / {r.source.section_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {requirements.length === 0 && (
            <Empty text="Build the matrix after uploading source documents." />
          )}
        </div>
      </section>
    </div>
  );
}

function GeneratePage({
  role,
  requirements,
  onGenerate,
  loading,
}: {
  role: string;
  requirements: Requirement[];
  onGenerate: (provider?: string) => void;
  loading: boolean;
}) {
  return (
    <div className="page-body">
      <section className="hero-small">
        <div className="pill">
          <Sparkles size={14} /> Generative AI pipeline
        </div>
        <h2>Generate a personalized onboarding plan.</h2>
        <p>
          The model receives the employee profile, approved requirements and
          source chunks. It must return structured JSON that can be
          independently validated.
        </p>
        <div className="generation-grid">
          <div>
            <span>Selected role</span>
            <b>{role}</b>
          </div>
          <div>
            <span>Ground-truth requirements</span>
            <b>{requirements.length}</b>
          </div>
          <div>
            <span>Generation mode</span>
            <b>Demo / API</b>
          </div>
        </div>
      </section>
      <div className="two-col">
        <section className="panel">
          <div className="panel-head">
            <div>
              <span className="section-label">EMPLOYEE PROFILE</span>
              <h3>Demo employee</h3>
            </div>
            <Users size={18} />
          </div>
          <div className="profile-card">
            <div className="profile-avatar">DE</div>
            <div>
              <b>Demo Employee</b>
              <span>{role}</span>
              <small>Operations • Intermediate • EMP-001</small>
            </div>
          </div>
          <button
            className="primary full"
            disabled={loading || requirements.length === 0}
            onClick={() => onGenerate("demo")}
          >
            Generate with Demo Provider <Sparkles size={16} />
          </button>
          <button
            className="secondary full"
            disabled={loading || requirements.length === 0}
            onClick={() => onGenerate("openai")}
          >
            Generate with OpenAI <ArrowRight size={16} />
          </button>
          {requirements.length === 0 && (
            <p className="hint">Build the Requirement Matrix first.</p>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <span className="section-label">WHAT THE AI RETURNS</span>
              <h3>Structured onboarding intelligence</h3>
            </div>
            <BookOpenCheck size={18} />
          </div>
          <div className="feature-list">
            <Feature icon={BookOpenCheck} title="Learning modules" />
            <Feature
              icon={ClipboardCheck}
              title="Practical tasks & checklists"
            />
            <Feature icon={Activity} title="Role-specific assessments" />
            <Feature
              icon={ShieldCheck}
              title="Source references on mandatory content"
            />
          </div>
          <div className="json-preview">{`{
  "role": "${role}",
  "module_id": "M-001",
  "mandatory": true,
  "source_document_id": "SOP-07",
  "source_section_id": "4.2"
}`}</div>
        </section>
      </div>
    </div>
  );
}
function Feature({ icon: Icon, title }: { icon: any; title: string }) {
  return (
    <div className="feature">
      <Icon size={17} />
      <span>{title}</span>
      <CheckCircle2 size={15} />
    </div>
  );
}

function ValidationPage({
  plan,
  validation,
  onValidate,
  onGenerate,
  loading,
}: {
  plan: Plan | null;
  validation: Validation | null;
  onValidate: () => void;
  onGenerate: () => void;
  loading: boolean;
}) {
  return (
    <div className="page-body">
      {!plan ? (
        <section className="empty-state panel">
          <ShieldCheck size={40} />

          <h2>No plan to verify yet</h2>

          <p>
            Generate a structured onboarding plan, then run the independent
            Python validation pipeline.
          </p>

          <button className="primary" onClick={onGenerate}>
            Go to generation
            <ArrowRight size={16} />
          </button>
        </section>
      ) : (
        <>
          <section className="verification-banner">
            <div>
              <span className="section-label">VERIFICATION CENTER</span>

              <h2>{plan.role}</h2>

              <p>
                {plan.plan_id} • {plan.modules.length} modules •{" "}
                {plan.tasks.length} tasks • {plan.quiz.length} quiz items
              </p>
            </div>

            <button className="primary" disabled={loading} onClick={onValidate}>
              {validation ? "Run validation again" : "Run Python validation"}

              <ShieldCheck size={16} />
            </button>
          </section>

          {validation && (
            <>
              <div className="metrics four">
                <Metric
                  icon={ClipboardCheck}
                  label="Mandatory coverage"
                  value={`${validation.coverage_score}%`}
                  sub={`${validation.mandatory_covered}/${validation.mandatory_total} covered`}
                />

                <Metric
                  icon={ShieldCheck}
                  label="Traceability"
                  value={`${validation.traceability_score}%`}
                  sub="mandatory source refs"
                />

                <Metric
                  icon={AlertTriangle}
                  label="Missing"
                  value={validation.missing_requirement_ids.length}
                  sub="requirements"
                />

                <Metric
                  icon={XCircle}
                  label="Unsupported"
                  value={validation.unsupported_requirement_ids.length}
                  sub="generated IDs"
                />
              </div>

              <section
                className={
                  validation.status === "Verified"
                    ? "status-card verified"
                    : "status-card warning"
                }
              >
                {validation.status === "Verified" ? (
                  <CheckCircle2 size={28} />
                ) : (
                  <AlertTriangle size={28} />
                )}

                <div>
                  <span>FINAL VERIFICATION STATUS</span>

                  <strong>{validation.status}</strong>

                  <p>
                    Generated content is checked against the independent Role
                    Requirement Matrix and source metadata.
                  </p>
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <div>
                    <span className="section-label">FINDINGS</span>

                    <h3>{validation.findings.length} validation findings</h3>
                  </div>

                  <ShieldCheck size={18} />
                </div>

                {validation.findings.length === 0 ? (
                  <Empty text="No validation findings. The plan passed the current rules." />
                ) : (
                  <div className="finding-list">
                    {validation.findings.map((f, i) => (
                      <div className={`finding ${f.severity}`} key={i}>
                        <div className="finding-icon">
                          {f.severity === "error" ? (
                            <XCircle size={16} />
                          ) : (
                            <AlertTriangle size={16} />
                          )}
                        </div>

                        <div>
                          <b>{f.code}</b>

                          <p>{f.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}

function ComparisonPage({ plan }: { plan: Plan | null }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!plan) return;
    setLoading(true);
    api(`/onboarding/comparison?plan_id=${encodeURIComponent(plan.plan_id)}`)
      .then((d) => setRows(d.rows))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [plan]);
  return (
    <div className="page-body">
      <section className="action-card">
        <div>
          <span className="section-label">DUAL-PIPELINE EVIDENCE</span>
          <h2>GenAI ↔ Python comparison</h2>
          <p>
            Compare structured requirements, not exact natural-language wording.
          </p>
        </div>
        <BarChart3 size={28} />
      </section>
      {!plan ? (
        <section className="empty-state panel">
          <BarChart3 size={40} />
          <h2>Generate a plan first</h2>
          <p>
            The comparison engine needs a generated onboarding plan and its role
            matrix.
          </p>
        </section>
      ) : (
        <section className="panel">
          <div className="panel-head">
            <div>
              <span className="section-label">REQUIREMENT-LEVEL RESULTS</span>
              <h3>{loading ? "Loading…" : `${rows.length} comparisons`}</h3>
            </div>
            <RefreshCw size={18} />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Requirement</th>
                  <th>Python expected</th>
                  <th>GenAI present</th>
                  <th>Source valid</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.requirement_id}>
                    <td>
                      <code>{r.requirement_id}</code>
                    </td>
                    <td>{r.python_expected ? "Required" : "Optional"}</td>
                    <td>{r.genai_present ? "Present" : "Missing"}</td>
                    <td>
                      {r.source_valid ? (
                        <span className="tag ok">Valid</span>
                      ) : (
                        <span className="tag warn">Review</span>
                      )}
                    </td>
                    <td>
                      {r.match ? (
                        <span className="tag ok">Match</span>
                      ) : (
                        <span className="tag bad">Mismatch</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
