import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import {
  ArrowRight, ClipboardList, CloudUpload,
  FileText, HeartPulse, LayoutDashboard, LoaderCircle, LogIn, LogOut, Mic, Send,
  ShieldCheck, Stethoscope, UserRound, Users, Workflow, Search, CheckCircle2
} from 'lucide-react';
import { API_BASE, formatError, pretty, request } from './api';
import {
  describeUploadResult
} from './documentUi';
import {
  belongsToConsultation,
  confirmDraftSummary,
  documentVerifyOptions,
  emptyWorkspace,
  formatTimestamp,
  isMissingSummaryMessage,
  parseDashboardDocuments,
  parseDraftSummary,
  parseTimelineEvents,
  stripSummaryPrefix,
  summaryReviewOptions,
  verificationLabel,
  type DashboardWorkspace,
  type DraftSummary,
} from './dashboardData';

type Dict = Record<string, any>;
type Patient = { id: string; full_name?: string; date_of_birth?: string | null; created_at?: string };
type Consultation = { id: string; patient_id: string; language?: string; status?: string; created_at?: string };
type DocumentRecord = {
  id: string; filename?: string; processing_status?: string; verification_status?: string;
  page_count?: number; extraction_method?: string; entities?: any[]; text?: string;
  error_message?: string | null; created_at?: string; verified_by_user_id?: string;
  verified_at?: string; verification_notes?: string;
};
type Tab = 'patient' | 'dashboard';
type IntakeStep = 'lookup' | 'start_consult' | 'chat' | 'upload';

function Label({ children }: { children: ReactNode }) { return <label className="field-label">{children}</label>; }
function JsonPanel({ value }: { value: unknown }) { return <pre className="json-panel">{typeof value === 'string' ? value : pretty(value)}</pre>; }
function StatusPill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'good' | 'warn' | 'neutral' | 'bad' }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export default function App() {
  const [tab, setTab] = useState<Tab>('patient');
  const [apiState, setApiState] = useState<'checking' | 'online' | 'offline'>('checking');
  const [token, setToken] = useState('');
  const [user, setUser] = useState<Dict | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginBusy, setLoginBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const busyRef = useRef<string | null>(null);

  // --- Wizard State ---
  const [intakeStep, setIntakeStep] = useState<IntakeStep>('lookup');

  // --- Patient & Consultation States ---
  const [patientName, setPatientName] = useState('');
  const [dob, setDob] = useState('');
  const [hasConsent, setHasConsent] = useState(false);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [language, setLanguage] = useState('en');
  const [consultation, setConsultation] = useState<Consultation | null>(null);

  // --- Search States ---
  const [searchName, setSearchName] = useState('');
  const [searchDob, setSearchDob] = useState('');
  const [searchResults, setSearchResults] = useState<Patient[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // --- AI Chat States ---
  const [chatMessages, setChatMessages] = useState<{ role: 'ai' | 'user'; text: string }[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [chatComplete, setChatComplete] = useState(false);

  // --- Dashboard States ---
  const [workspace, setWorkspace] = useState<DashboardWorkspace | null>(null);
  const dashboardSerial = useRef(0);
  const dashboardLoadedFor = useRef<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentDetail, setDocumentDetail] = useState<DocumentRecord | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [correctionDraft, setCorrectionDraft] = useState<{ summaryId: string; cc: string; hpi: string; notes: string; } | null>(null);

  const activeConsultationId = consultation?.id || '';
  const activeWorkspace = workspace?.consultationId === activeConsultationId ? workspace : null;
  const visibleSummary = activeWorkspace?.summary ?? null;

  const report = useCallback((kind: 'success' | 'error' | 'info', text: string) => setNotice({ kind, text }), []);
  const run = useCallback(async <T,>(key: string, action: () => Promise<T>): Promise<T | undefined> => {
    if (busyRef.current) return undefined;
    busyRef.current = key;
    setBusy(key);
    try {
      return await action();
    } catch (error) {
      report('error', formatError(error));
      return undefined;
    } finally {
      busyRef.current = null;
      setBusy(null);
    }
  }, [report]);

  useEffect(() => {
    let alive = true;
    request('/health').then(() => { if (alive) setApiState('online'); }).catch(() => { if (alive) setApiState('offline'); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (visibleSummary) {
      setCorrectionDraft({
        summaryId: visibleSummary.summary_id,
        cc: visibleSummary.chief_complaint,
        hpi: visibleSummary.history_of_present_illness,
        notes: '',
      });
    } else {
      setCorrectionDraft(null);
    }
  }, [visibleSummary?.summary_id]);

  const login = async (event: FormEvent) => {
    event.preventDefault();
    setLoginBusy(true);
    try {
      const { data } = await request<Dict>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      const newToken = String(data.access_token || '');
      if (!newToken) throw new Error('Login response did not contain an access token.');
      const me = await request<Dict>('/api/v1/auth/me', {}, newToken);
      setToken(newToken); setUser(me.data); setPassword('');
      report('success', 'Signed in.');
    } catch (error) { report('error', formatError(error)); }
    finally { setLoginBusy(false); }
  };

  const logout = () => { 
    setToken(''); setUser(null); setNotice({ kind: 'info', text: 'Signed out.' }); 
    setIntakeStep('lookup'); setPatient(null); setConsultation(null);
  };

  // --- WIZARD STEP 1: LOOKUP ---
  const createPatient = async (event: FormEvent) => {
    event.preventDefault();
    if (!hasConsent) { report('error', 'You must confirm patient consent before creating the record.'); return; }
    const payload = { full_name: patientName.trim(), date_of_birth: dob || null, consent_confirmed: true };
    await run('create-patient', async () => {
      const { data } = await request<Patient>('/api/v1/patients', { method: 'POST', body: JSON.stringify(payload) }, token);
      setPatient(data);
      setHasConsent(false); setPatientName(''); setDob('');
      setIntakeStep('start_consult');
      report('success', 'Patient created. Please start a consultation.');
    });
  };

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!searchName.trim()) return;
    setIsSearching(true);
    try {
      let url = `/api/v1/patients/search?name=${encodeURIComponent(searchName)}`;
      if (searchDob) url += `&dob=${searchDob}`;
      const { data } = await request<Patient[]>(url, {}, token);
      setSearchResults(data);
      if (data.length === 0) report('info', 'No patients found matching that name/DOB.');
    } catch (err) {
      report('error', formatError(err));
    } finally {
      setIsSearching(false);
    }
  };

  const selectPatient = (p: Patient) => {
    setPatient(p);
    setIntakeStep('start_consult');
  };

  // --- WIZARD STEP 2: START CONSULT ---
  const startConsultation = async () => {
    if (!patient) return;
    await run('create-consultation', async () => {
      const { data } = await request<Consultation>('/api/v1/consultations', { method: 'POST', body: JSON.stringify({ patient_id: patient.id, language }) }, token);
      setConsultation(data); setWorkspace(null); dashboardLoadedFor.current = null;
      setChatMessages([{ role: 'ai', text: `Hello ${patient.full_name}! I am Nurse Amma. Please tell me what brings you in today.` }]);
      setChatComplete(false);
      setIntakeStep('chat');
      report('success', 'Consultation started. You can begin the chat.');
    });
  };

  // --- WIZARD STEP 3: AI CHAT ---
  const sendChatMessage = async () => {
    if (!chatInput.trim() || !activeConsultationId) return;
    const userText = chatInput.trim();
    
    const newHistory = [
      ...chatMessages.map((msg) => ({ role: msg.role === 'ai' ? 'assistant' : 'user', content: msg.text })),
      { role: 'user', content: userText }
    ];

    setChatMessages((prev) => [...prev, { role: 'user', text: userText }]);
    setChatInput('');

    await run('chat-send', async () => {
      try {
        const { data } = await request<any>(
          `/api/v1/consultations/${encodeURIComponent(activeConsultationId)}/dynamic-intake`,
          { method: 'POST', body: JSON.stringify({ consultation_id: activeConsultationId, language: language, chat_history: newHistory }) },
          token
        );
        const aiText = data.next_question || data.status || "Data recorded. Please continue.";
        setChatMessages((prev) => [...prev, { role: 'ai', text: aiText }]);
        
        if (data.status === 'EMERGENCY_ESCALATION') {
           report('error', 'EMERGENCY: ' + aiText);
        } else if (data.extracted_data?.is_complete) {
           setChatComplete(true);
           report('success', 'AI has collected enough history.');
        }
      } catch (error) {
        setChatMessages((prev) => [...prev, { role: 'ai', text: "Sorry, I had trouble connecting to the AI service." }]);
      }
    });
  };

  const startListening = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) { report('error', 'Your browser does not support speech recognition. Please use Chrome or Edge.'); return; }
    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = language === 'ta' ? 'ta-IN' : language === 'hi' ? 'hi-IN' : 'en-US';
      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event: any) => { setChatInput(event.results[0][0].transcript); setIsListening(false); };
      recognition.onerror = (event: any) => { setIsListening(false); report('error', `Mic error: ${event.error}. Check permissions.`); };
      recognition.start();
    } catch (err) { report('error', 'Could not start microphone.'); }
  };

  // --- WIZARD STEP 4: UPLOAD ---
  const uploadDocument = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedFile || !activeConsultationId) return;

    await run('upload-document', async () => {
      setUploadProgress('Uploading and extracting…');
      try {
        const form = new FormData();
        form.append('file', selectedFile);
        const { data } = await request<DocumentRecord>(
          `/api/v1/consultations/${encodeURIComponent(activeConsultationId)}/documents`,
          { method: 'POST', body: form },
          token,
        );
        setSelectedFile(null);
        report('success', describeUploadResult(data));
      } catch (error) {
        throw error;
      } finally {
        setUploadProgress(null);
      }
    });
  };

  const finishIntake = () => {
    setTab('dashboard');
    loadDashboardWorkspace(activeConsultationId);
  };

  // --- DASHBOARD FUNCTIONS ---
  const applySummaryToWorkspace = (consultationId: string, next: DraftSummary | null, state: DashboardWorkspace['summaryState'], error?: string) => {
    setWorkspace((current) => {
      if (!current || current.consultationId !== consultationId) return current;
      return { ...current, summary: next, summaryState: state, summaryError: error };
    });
  };

  const loadDashboardWorkspace = async (requestedId: string) => {
    if (!requestedId) return;
    const serial = dashboardSerial.current + 1;
    dashboardSerial.current = serial;
    dashboardLoadedFor.current = requestedId;
    setWorkspace(emptyWorkspace(requestedId));

    const result = await run('dashboard-consultation', async () => {
      const details = (await request<Consultation>(`/api/v1/consultations/${encodeURIComponent(requestedId)}`, {}, token)).data;
      if (serial !== dashboardSerial.current) return null;

      const [patientResult, summaryResult, documentResult, timelineResult] = await Promise.allSettled([
        request<Patient>(`/api/v1/patients/${encodeURIComponent(details.patient_id)}`, {}, token),
        request<unknown>(`/api/v1/consultations/${encodeURIComponent(requestedId)}/summary`, {}, token),
        request<Dict>(`/api/v1/consultations/${encodeURIComponent(requestedId)}/documents`, {}, token),
        request<unknown>(`/api/v1/consultations/${encodeURIComponent(requestedId)}/timeline`, {}, token),
      ]);
      if (serial !== dashboardSerial.current) return null;

      const next: DashboardWorkspace = {
        consultationId: requestedId, loadState: 'ready', consultation: details, patient: null,
        summary: null, summaryState: 'missing', documents: [], timeline: [], timelineState: 'idle',
      };

      if (patientResult.status === 'fulfilled') next.patient = patientResult.value.data;
      else next.patientError = formatError(patientResult.reason);

      if (summaryResult.status === 'fulfilled') {
        const parsed = parseDraftSummary(summaryResult.value.data);
        if (parsed && belongsToConsultation(parsed.consultation_id, requestedId)) {
          next.summary = parsed; next.summaryState = 'loaded';
        } else {
          next.summaryState = 'error'; next.summaryError = 'The saved summary did not match this consultation.';
        }
      } else {
        const message = formatError(summaryResult.reason);
        if (isMissingSummaryMessage(message)) next.summaryState = 'missing';
        else { next.summaryState = 'error'; next.summaryError = message; }
      }

      if (documentResult.status === 'fulfilled') next.documents = parseDashboardDocuments(documentResult.value.data, requestedId);
      else next.documentsError = formatError(documentResult.reason);

      if (timelineResult.status === 'fulfilled') {
        next.timeline = parseTimelineEvents(timelineResult.value.data);
        next.timelineState = 'loaded';
      } else {
        next.timelineState = 'error'; next.timelineError = formatError(timelineResult.reason);
      }

      return next;
    });

    if (serial !== dashboardSerial.current) return;
    if (result && result.consultation) {
      setWorkspace(result);
      report('success', 'Doctor workspace loaded.');
    }
  };

  const generateSummary = async () => {
    if (!activeConsultationId) return;
    const result = await run('generate-summary', async () => {
      const { data, status } = await request<unknown>(`/api/v1/consultations/${encodeURIComponent(activeConsultationId)}/summary`, { method: 'POST' }, token);
      let saved = confirmDraftSummary(status, data);
      try {
        const refreshed = await request<unknown>(`/api/v1/consultations/${encodeURIComponent(activeConsultationId)}/summary`, {}, token);
        const latest = parseDraftSummary(refreshed.data);
        if (latest) saved = latest;
      } catch { /* */ }
      return saved;
    });

    if (result) {
      applySummaryToWorkspace(activeConsultationId, result, 'loaded');
      report('success', `Draft summary saved.`);
    }
  };

  const reviewSummaryAction = async (summaryId: string, newStatus: string) => {
    const notes = reviewNotes[summaryId]?.trim() || null;
    const summaryUuid = stripSummaryPrefix(summaryId);
    await run(`review-summary-${summaryId}-${newStatus}`, async () => {
      const { data } = await request<unknown>(`/api/v1/summaries/${encodeURIComponent(summaryUuid)}/review`, { method: 'POST', body: JSON.stringify({ status: newStatus, notes }) }, token);
      const parsed = parseDraftSummary(data);
      if (parsed) applySummaryToWorkspace(activeConsultationId, parsed, 'loaded');
      setReviewNotes((prev) => { const n = { ...prev }; delete n[summaryId]; return n; });
      report('success', `Summary marked: ${newStatus.replace(/_/g, ' ')}.`);
    });
  };

  const correctSummaryAction = async (summaryId: string) => {
    if (!correctionDraft || !visibleSummary) return;
    const payload: Dict = { notes: correctionDraft.notes.trim() || null };
    if (correctionDraft.cc !== visibleSummary.chief_complaint) payload.chief_complaint = correctionDraft.cc;
    if (correctionDraft.hpi !== visibleSummary.history_of_present_illness) payload.history_of_present_illness = correctionDraft.hpi;
    if (!payload.chief_complaint && !payload.history_of_present_illness) {
      report('error', 'Change at least one field before applying a correction.');
      return;
    }
    const summaryUuid = stripSummaryPrefix(summaryId);
    await run(`correct-summary-${summaryId}`, async () => {
      const { data } = await request<unknown>(`/api/v1/summaries/${encodeURIComponent(summaryUuid)}`, { method: 'PATCH', body: JSON.stringify(payload) }, token);
      const parsed = parseDraftSummary(data);
      if (parsed) applySummaryToWorkspace(activeConsultationId, parsed, 'loaded');
      report('success', 'Summary correction persisted.');
    });
  };

  const getDocument = async (id: string) => {
    const result = await run(`get-document-${id}`, async () => (await request<DocumentRecord>(`/api/v1/documents/${encodeURIComponent(id)}`, {}, token)).data);
    if (result) { setDocumentDetail(result); }
  };

  const verifyDocumentAction = async (documentId: string, newStatus: string) => {
    await run(`verify-document-${documentId}-${newStatus}`, async () => {
      const { data } = await request<DocumentRecord>(
        `/api/v1/documents/${encodeURIComponent(documentId)}/verify`,
        { method: 'POST', body: JSON.stringify({ status: newStatus, notes: null }) },
        token,
      );
      setDocumentDetail((current) => (current && current.id === documentId ? { ...current, ...data } : current));
      report('success', `Document verification recorded: ${newStatus}.`);
    });
  };

  const logoutButton = user && <button className="ghost-button small" onClick={logout}><LogOut size={15} /> Sign out</button>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><HeartPulse size={24} /></div><div><div className="brand-title">Nurse Amma</div><div className="brand-subtitle">CARE WORKSPACE</div></div></div>
        <div className="side-section-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button onClick={() => { if(confirm('Are you sure? You will lose current session.')) { setTab('patient'); setIntakeStep('lookup'); } }} className={`nav-item ${tab === 'patient' ? 'active' : ''}`}><UserRound size={18} /><span>New Patient Intake</span></button>
          <button onClick={() => setTab('dashboard')} className={`nav-item ${tab === 'dashboard' ? 'active' : ''}`} disabled={!activeConsultationId}><LayoutDashboard size={18} /><span>Doctor Dashboard</span></button>
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-note"><ShieldCheck size={17} /><div><strong>Privacy first</strong><p>Use synthetic records. Clinical findings remain unverified until reviewed.</p></div></div>
        <div className="sidebar-footer">Academic prototype · v0.1</div>
      </aside>

      <main className="main-area">
        <header className="topbar"><div><div className="eyebrow">NURSE AMMA / INTEGRATED WORKSPACE</div><h1>{tab === 'patient' ? 'Patient Intake' : 'Doctor Dashboard'}</h1></div><div className="topbar-actions"><span className={`connection ${apiState}`}><span className="dot" />{apiState === 'online' ? 'API reachable' : 'API offline'}</span>{logoutButton}</div></header>

        {notice && <div className={`notice notice-${notice.kind}`} role="status"><span>{notice.text}</span><button onClick={() => setNotice(null)}>×</button></div>}

        {!token ? (
          <section className="login-layout">
            <div className="welcome-panel"><div className="welcome-icon"><Stethoscope size={28} /></div><span className="kicker">PRE-CONSULTATION CARE</span><h2>One connected view of the patient's story.</h2></div>
            <form className="card login-card" onSubmit={login}><div className="card-heading"><div className="icon-chip"><LogIn size={19} /></div><div><h2>Sign in</h2></div></div><div className="field"><Label>Email</Label><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div><div className="field"><Label>Password</Label><input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div><button className="primary-button full" disabled={loginBusy}>{loginBusy ? <LoaderCircle className="spin" size={17} /> : <LogIn size={17} />} Sign in</button></form>
          </section>
        ) : (
          <>
            {tab === 'patient' && (
              <div className="content-grid patient-grid">
                
                {intakeStep === 'lookup' && (
                  <>
                    <section className="card">
                      <div className="card-heading"><div className="icon-chip"><UserRound size={18} /></div><div><h2>Create New Patient</h2></div></div>
                      <form onSubmit={createPatient} className="form-stack">
                        <div className="field"><Label>Full name</Label><input value={patientName} onChange={(e) => setPatientName(e.target.value)} placeholder="Synthetic Patient" required /></div>
                        <div className="field"><Label>Date of birth</Label><input type="date" value={dob} onChange={(e) => setDob(e.target.value)} /></div>
                        <div style={{ display: 'flex', gap: '8px', margin: '4px 0' }}>
                          <input type="checkbox" id="consent" checked={hasConsent} onChange={(e) => setHasConsent(e.target.checked)} />
                          <label htmlFor="consent" style={{ fontSize: '11px', cursor: 'pointer' }}>I confirm consent is granted.</label>
                        </div>
                        <button className="primary-button" disabled={busy !== null || !hasConsent}>{busy === 'create-patient' ? <LoaderCircle className="spin" size={16} /> : <Users size={16} />} Create Patient</button>
                      </form>
                    </section>

                    <section className="card">
                      <div className="card-heading"><div className="icon-chip"><Search size={18} /></div><div><h2>Find Existing Patient</h2></div></div>
                      <form onSubmit={handleSearch} className="form-stack">
                        <div className="field"><Label>Patient Name</Label><input value={searchName} onChange={(e) => setSearchName(e.target.value)} placeholder="e.g. John" required /></div>
                        <div className="field"><Label>Date of Birth (optional)</Label><input type="date" value={searchDob} onChange={(e) => setSearchDob(e.target.value)} /></div>
                        <button className="secondary-button" disabled={isSearching}>{isSearching ? <LoaderCircle className="spin" size={16} /> : <Search size={16} />} Search Database</button>
                      </form>
                      {searchResults.length > 0 && (
                        <div className="document-list" style={{ marginTop: '16px' }}>
                          {searchResults.map(p => (
                            <div key={p.id} className="document-row" style={{ cursor: 'pointer' }} onClick={() => selectPatient(p)}>
                              <div className="document-info"><strong>{p.full_name}</strong><span>DOB: {p.date_of_birth || 'Unknown'}</span></div>
                              <button className="text-button">Select</button>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  </>
                )}

                {intakeStep === 'start_consult' && patient && (
                  <section className="card span-two">
                    <div className="card-heading"><div className="icon-chip"><ClipboardList size={18} /></div><div><h2>Patient Selected: {patient.full_name}</h2></div></div>
                    <div className="detail-line"><span>Patient ID</span><code>{patient.id}</code></div>
                    <div className="field" style={{ marginTop: '20px' }}>
                      <Label>Language</Label>
                      <select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="en">English</option><option value="ta">Tamil</option><option value="hi">Hindi</option></select>
                    </div>
                    <button className="primary-button full" style={{ marginTop: '20px' }} onClick={startConsultation} disabled={busy !== null}>
                      {busy === 'create-consultation' ? <LoaderCircle className="spin" size={16} /> : <ArrowRight size={16} />} Start Consultation
                    </button>
                  </section>
                )}

                {intakeStep === 'chat' && (
                  <section className="card span-two">
                    <div className="card-heading"><div className="icon-chip"><Stethoscope size={18} /></div><div><h2>AI Clinical History Assistant</h2></div></div>
                    <div className="chat-container">
                      <div className="chat-messages">
                        {chatMessages.map((msg, idx) => <div key={idx} className={`chat-bubble ${msg.role}`}>{msg.text}</div>)}
                      </div>
                      <div className="chat-input-area">
                        {chatComplete ? (
                          <div style={{ display: 'flex', width: '100%', justifyContent: 'center' }}>
                            <button className="primary-button" style={{ maxWidth: '300px' }} onClick={() => setIntakeStep('upload')}><ArrowRight size={18} /> Proceed to Document Upload</button>
                          </div>
                        ) : (
                          <>
                            <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendChatMessage()} placeholder="Type response..." disabled={busy === 'chat-send'} />
                            <button type="button" className={`mic-button ${isListening ? 'recording' : ''}`} onClick={startListening} disabled={busy === 'chat-send'}><Mic size={20} /></button>
                            <button type="button" className="primary-button" onClick={sendChatMessage} disabled={!chatInput.trim() || busy === 'chat-send'}>{busy === 'chat-send' ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}</button>
                          </>
                        )}
                      </div>
                    </div>
                  </section>
                )}

                {intakeStep === 'upload' && (
                  <section className="card span-two">
                    <div className="card-heading"><div className="icon-chip"><CloudUpload size={18} /></div><div><h2>Upload Medical Documents</h2><p>Do you have any prescriptions, lab reports, or images to upload?</p></div></div>
                    <form className="form-stack" onSubmit={uploadDocument}>
                      <label className="drop-zone">
                        <CloudUpload size={25} />
                        <strong>{selectedFile?.name || 'Choose a PDF or image'}</strong>
                        <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} />
                      </label>
                      <div className="button-row">
                        <button className="primary-button" disabled={busy !== null || !selectedFile}>{busy === 'upload-document' ? <LoaderCircle className="spin" size={16} /> : <CloudUpload size={16} />} Upload Document</button>
                        <button className="secondary-button" type="button" onClick={finishIntake}><CheckCircle2 size={16} /> Skip & Go to Dashboard</button>
                      </div>
                    </form>
                    {uploadProgress && <div className="notice notice-info">{uploadProgress}</div>}
                  </section>
                )}
              </div>
            )}

            {tab === 'dashboard' && (
              <div className="dashboard-layout">
                {!activeWorkspace ? (
                  <div className="empty-state">Loading dashboard...</div>
                ) : (
                  <div className="dashboard-cards">
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                      <section className="card">
                        <div className="card-heading"><div className="icon-chip"><ClipboardList size={18} /></div><div><h2>Patient Context</h2></div></div>
                        <div className="detail-line"><span>Name</span><strong>{activeWorkspace.patient?.full_name || '—'}</strong></div>
                        <div className="detail-line"><span>Patient ID</span><code>{activeWorkspace.patient?.id || '—'}</code></div>
                      </section>

                      <section className="card">
                        <div className="card-heading"><div className="icon-chip"><FileText size={18} /></div><div><h2>Documents</h2></div></div>
                        <button className="secondary-button" style={{ marginBottom: '12px' }} onClick={() => loadDashboardWorkspace(activeConsultationId)}>Refresh Docs</button>
                        <div className="document-list">
                          {activeWorkspace.documents.map(doc => (
                            <div key={doc.id} className="document-row">
                              <div className="document-info"><strong>{doc.filename}</strong></div>
                              <button className="text-button" onClick={() => getDocument(doc.id)}>View</button>
                            </div>
                          ))}
                        </div>
                      </section>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                      <section className="card">
                        <div className="card-heading"><div className="icon-chip"><FileText size={18} /></div><div><h2>Draft Summary</h2></div></div>
                        <button className="primary-button" onClick={generateSummary} disabled={busy !== null}>Generate Summary</button>
                        {visibleSummary && (
                          <div className="clinical-summary" style={{ marginTop: '16px' }}>
                            <div className="summary-status-row"><StatusPill tone={verificationLabel(visibleSummary.review_status).tone}>{visibleSummary.review_status}</StatusPill></div>
                            <div className="summary-section"><h3 className="subheading">Chief Complaint</h3><p>{visibleSummary.chief_complaint}</p></div>
                            <div className="summary-section"><h3 className="subheading">HPI</h3><p>{visibleSummary.history_of_present_illness}</p></div>
                          </div>
                        )}
                      </section>

                      <section className="card">
                        <div className="card-heading"><div className="icon-chip"><ShieldCheck size={18} /></div><div><h2>Clinical Review</h2></div></div>
                        {visibleSummary && (
                          <>
                            {summaryReviewOptions(visibleSummary.review_status).length > 0 && (
                              <div className="form-stack">
                                <div className="field"><Label>Notes</Label><textarea rows={2} value={reviewNotes[visibleSummary.summary_id] || ''} onChange={e => setReviewNotes({...reviewNotes, [visibleSummary.summary_id]: e.target.value})} placeholder="Reason for review..." /></div>
                                <div className="button-row">
                                  {summaryReviewOptions(visibleSummary.review_status).map(status => (
                                    <button key={status} className={status === 'approved' ? 'primary-button' : 'secondary-button'} onClick={() => reviewSummaryAction(visibleSummary.summary_id, status)} disabled={busy !== null}>{status.replace(/_/g, ' ')}</button>
                                  ))}
                                </div>
                              </div>
                            )}
                            {correctionDraft && correctionDraft.summaryId === visibleSummary.summary_id && (
                              <div style={{ marginTop: '16px', borderTop: '1px solid #eee', paddingTop: '16px' }}>
                                <div className="field"><Label>Correct Chief Complaint</Label><textarea rows={2} value={correctionDraft.cc} onChange={e => setCorrectionDraft({...correctionDraft, cc: e.target.value})} /></div>
                                <button className="primary-button" onClick={() => correctSummaryAction(visibleSummary.summary_id)} disabled={busy !== null}>Apply Correction</button>
                              </div>
                            )}
                          </>
                        )}
                      </section>

                      <section className="card">
                        <div className="card-heading"><div className="icon-chip"><Workflow size={18} /></div><div><h2>Timeline</h2></div></div>
                        <div className="document-list">
                          {activeWorkspace.timeline.map(e => (
                            <div className="document-row" key={e.event_id}>
                              <div className="document-info"><strong>{e.title}</strong><span>{formatTimestamp(e.occurred_at)}</span></div>
                            </div>
                          ))}
                        </div>
                      </section>
                    </div>

                  </div>
                )}
              </div>
            )}

            {documentDetail && (
              <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
                <section className="card" style={{ width: '80%', maxHeight: '90%', overflowY: 'auto' }}>
                  <div className="card-heading">
                    <div className="icon-chip"><FileText size={18} /></div>
                    <div><h2>{documentDetail.filename}</h2></div>
                    <button className="text-button" onClick={() => setDocumentDetail(null)}>Close</button>
                  </div>
                  
                  {Array.isArray(documentDetail.entities) && documentDetail.entities.length > 0 && documentDetail.entities[0]?.prescribed_medications?.length > 0 && (
                    <>
                      <h3 className="subheading" style={{ color: '#0b6a5f' }}>💊 Extracted Prescriptions (AI)</h3>
                      <div className="metric-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                        {documentDetail.entities[0].prescribed_medications.map((med: any, i: number) => (
                          <div key={i} className="metric">
                            <small>{med.drug_name || 'Unknown Drug'}</small>
                            <strong>{med.dosage || 'No dosage'}</strong>
                            <span style={{ fontSize: '12px', color: '#666' }}>{med.frequency || 'No frequency'}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {documentVerifyOptions(documentDetail.verification_status || '').length > 0 && (
                    <div className="button-row" style={{ marginTop: '16px' }}>
                      {documentVerifyOptions(documentDetail.verification_status || '').map((nextStatus) => (
                        <button
                          key={nextStatus}
                          type="button"
                          className={nextStatus === 'verified' ? 'primary-button' : 'secondary-button'}
                          disabled={busy !== null}
                          onClick={() => verifyDocumentAction(documentDetail.id, nextStatus)}
                        >
                          {busy === `verify-document-${documentDetail.id}-${nextStatus}` ? <LoaderCircle className="spin" size={14} /> : <ShieldCheck size={14} />}
                          Mark {nextStatus.replace(/_/g, ' ')}
                        </button>
                      ))}
                    </div>
                  )}

                  <h3 className="subheading">Raw Extracted Entities</h3>
                  <JsonPanel value={documentDetail.entities || []} />
                </section>
              </div>
            )}
          </>
        )}

        <footer className="app-footer"><span>© Nurse Amma · Academic prototype</span><span><span className={`dot ${apiState}`} /> {API_BASE}</span><span>Clinical content is not a diagnosis. Human review is required.</span></footer>
      </main>
    </div>
  );
}