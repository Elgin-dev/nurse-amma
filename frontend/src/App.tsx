import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import {
  Activity, AlertCircle, ArrowRight, BadgeCheck, ClipboardList, CloudUpload,
  FileText, HeartPulse, LayoutDashboard, LoaderCircle, LogIn, LogOut,
  RefreshCw, ShieldCheck, Stethoscope, UserRound, Users, Workflow,
} from 'lucide-react';
import { API_BASE, formatError, pretty, request, schemaProperties, type OpenApiDocument } from './api';
import {
  asStringList,
  asSymptomDetails,
  buildPatientResponsePayload,
  confirmPersistedSubmission,
  csvToList,
  parseJsonObject,
  validateHistorySave,
  type JsonObject,
  type SymptomDetails,
} from './historyPayload';
import {
  asDocumentList,
  describeUploadResult,
  processingTone,
  validateDocumentFile,
  verificationTone,
} from './documentUi';
import {
  belongsToConsultation,
  confirmDraftSummary,
  dashboardTargetId,
  documentVerifyOptions,
  emptyWorkspace,
  formatTimestamp,
  isMissingSummaryMessage,
  parseDashboardDocuments,
  parseDraftSummary,
  parseTimelineEvents,
  redFlagAbsenceNote,
  redFlagReviewOptions,
  sourceLabel,
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
  id: string;
  filename?: string;
  processing_status?: string;
  verification_status?: string;
  page_count?: number;
  extraction_method?: string;
  entities?: unknown[];
  text?: string;
  error_message?: string | null;
  created_at?: string;
  verified_by_user_id?: string;
  verified_at?: string;
  verification_notes?: string;
};
type SavedSubmission = {
  id: string;
  version?: number;
  payload?: JsonObject;
  verification_status?: string;
  source?: string;
};
type Tab = 'patient' | 'records' | 'dashboard';
type DurationUnit = 'hours' | 'days' | 'weeks' | 'months';

const RESPONSES_PATH = '/api/v1/consultations/{consultation_id}/responses';

function Label({ children }: { children: ReactNode }) { return <label className="field-label">{children}</label>; }
function JsonPanel({ value }: { value: unknown }) { return <pre className="json-panel">{typeof value === 'string' ? value : pretty(value)}</pre>; }
function StatusPill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'good' | 'warn' | 'neutral' | 'bad' }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}
function getText(value: unknown, keys: string[]): string {
  if (!value || typeof value !== 'object') return '';
  const obj = value as Dict;
  for (const key of keys) if (typeof obj[key] === 'string' && obj[key].trim()) return obj[key];
  return '';
}

export default function App() {
  const [tab, setTab] = useState<Tab>('patient');
  const [apiState, setApiState] = useState<'checking' | 'online' | 'offline'>('checking');
  const [spec, setSpec] = useState<OpenApiDocument | null>(null);
  const [token, setToken] = useState('');
  const [user, setUser] = useState<Dict | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginBusy, setLoginBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const busyRef = useRef<string | null>(null);

  const [patientName, setPatientName] = useState('');
  const [dob, setDob] = useState('');
  const [hasConsent, setHasConsent] = useState(false);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [patientIdInput, setPatientIdInput] = useState('');
  const [language, setLanguage] = useState('en');
  const [consultation, setConsultation] = useState<Consultation | null>(null);
  const [consultationIdInput, setConsultationIdInput] = useState('');
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [answeredKeys, setAnsweredKeys] = useState<string[]>([]);
  const [questionResult, setQuestionResult] = useState<unknown>(null);
  const [answerText, setAnswerText] = useState('');
  const [durationValue, setDurationValue] = useState('');
  const [durationUnit, setDurationUnit] = useState<DurationUnit>('days');
  const [severity, setSeverity] = useState('');
  const [progression, setProgression] = useState('');
  const [location, setLocation] = useState('');
  const [associatedSymptoms, setAssociatedSymptoms] = useState('');
  const [pastMedicalHistory, setPastMedicalHistory] = useState('');
  const [currentMedications, setCurrentMedications] = useState('');
  const [allergies, setAllergies] = useState('');
  const [responseJson, setResponseJson] = useState('{}');
  const [savedSubmission, setSavedSubmission] = useState<SavedSubmission | null>(null);
  const [workspace, setWorkspace] = useState<DashboardWorkspace | null>(null);
  const dashboardSerial = useRef(0);
  const dashboardLoadedFor = useRef<string | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentDetail, setDocumentDetail] = useState<DocumentRecord | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [correctionDraft, setCorrectionDraft] = useState<{
    summaryId: string;
    cc: string;
    hpi: string;
    notes: string;
  } | null>(null);

  const activeConsultationId = consultationIdInput.trim() || consultation?.id || '';
  const activeWorkspace = workspace?.consultationId === activeConsultationId ? workspace : null;
  const visibleSummary = activeWorkspace?.summary ?? null;
  const activePatientId = patient?.id || patientIdInput.trim();
  const questionComplete = Boolean(questionResult && typeof questionResult === 'object' && (questionResult as Dict).is_complete);
  const questionOptions = Array.isArray((questionResult as Dict | null)?.options)
    ? ((questionResult as Dict).options as unknown[]).filter((item): item is string => typeof item === 'string')
    : [];

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

  const symptomDetailsFromForm = useCallback((): SymptomDetails => {
    const details: SymptomDetails = {};
    const parsedDuration = Number(durationValue);
    if (durationValue.trim() && Number.isInteger(parsedDuration) && parsedDuration > 0) {
      details.duration = { value: parsedDuration, unit: durationUnit };
    }
    if (severity.trim()) details.severity = severity.trim();
    if (progression.trim()) details.progression = progression.trim();
    if (location.trim()) details.location = location.trim();
    return details;
  }, [durationValue, durationUnit, severity, progression, location]);

  const currentHistoryPayload = useCallback((existing?: JsonObject, overrides?: {
    consultationId?: string;
    questionKey?: string;
    questionText?: string;
    answerText?: string;
  }) => {
    const questionKey = overrides?.questionKey ?? getText(questionResult, ['question_key', 'question_id', 'id', 'key']);
    const questionText = overrides?.questionText ?? getText(questionResult, ['question_text', 'question', 'text', 'prompt']);
    const existingDetails = asSymptomDetails(existing?.symptom_details);
    return buildPatientResponsePayload({
      consultationId: overrides?.consultationId ?? activeConsultationId,
      chiefComplaint: chiefComplaint.trim(),
      symptomDetails: { ...existingDetails, ...symptomDetailsFromForm() },
      associatedSymptoms: csvToList(associatedSymptoms).length ? csvToList(associatedSymptoms) : asStringList(existing?.associated_symptoms),
      pastMedicalHistory: csvToList(pastMedicalHistory).length ? csvToList(pastMedicalHistory) : asStringList(existing?.past_medical_history),
      currentMedications: csvToList(currentMedications).length ? csvToList(currentMedications) : asStringList(existing?.current_medications),
      allergies: csvToList(allergies).length ? csvToList(allergies) : asStringList(existing?.allergies),
      questionKey,
      questionText,
      answerText: overrides?.answerText ?? answerText.trim(),
      schemaProperties: schemaProperties(spec, RESPONSES_PATH, 'post'),
      existing,
    });
  }, [
    activeConsultationId, chiefComplaint, symptomDetailsFromForm, associatedSymptoms, pastMedicalHistory,
    currentMedications, allergies, questionResult, answerText, spec,
  ]);

  useEffect(() => {
    let alive = true;
    request('/health').then(() => { if (alive) setApiState('online'); }).catch(() => { if (alive) setApiState('offline'); });
    request<OpenApiDocument>('/openapi.json').then(({ data }) => { if (alive) setSpec(data); }).catch(() => { if (alive) setSpec(null); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!spec) return;
    setResponseJson((current) => {
      const parsed = parseJsonObject(current);
      if (parsed.ok && Object.keys(parsed.value).length > 0) return pretty(currentHistoryPayload(parsed.value));
      return pretty(currentHistoryPayload());
    });
  }, [spec]); // eslint-disable-line react-hooks/exhaustive-deps -- seed templates once the OpenAPI document is available

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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-seed when the summary identity changes
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
      report('success', 'Signed in. The access token is kept in memory for this browser session.');
    } catch (error) { report('error', formatError(error)); }
    finally { setLoginBusy(false); }
  };

  const logout = () => { setToken(''); setUser(null); setNotice({ kind: 'info', text: 'Signed out.' }); };

  const createPatient = async (event: FormEvent) => {
    event.preventDefault();
    if (!hasConsent) {
      report('error', 'You must confirm patient consent before creating the record.');
      return;
    }
    const payload = { full_name: patientName.trim(), date_of_birth: dob || null,consent_confirmed: true };
    const result = await run('create-patient', async () => {
      const { data } = await request<Patient>('/api/v1/patients', { method: 'POST', body: JSON.stringify(payload) }, token);
      
      
      setPatient(data); setPatientIdInput(data.id); setConsultation(null); setConsultationIdInput(''); setDocuments([]); setDocumentDetail(null); setSavedSubmission(null); setWorkspace(null); dashboardLoadedFor.current = null;
      setHasConsent(false); // Reset checkbox after success
      report('success', 'Synthetic patient created and consent recorded.'); return data;
    });
    if (result) setPatientName('');
  };

  const loadPatient = async (event: FormEvent) => {
    event.preventDefault();
    const id = patientIdInput.trim();
    if (!id) { report('error', 'Enter a patient ID.'); return; }
    const result = await run('load-patient', async () => (await request<Patient>(`/api/v1/patients/${encodeURIComponent(id)}`, {}, token)).data);
    if (result) { setPatient(result); report('success', 'Patient record loaded.'); }
  };

  const createConsultation = async (event: FormEvent) => {
    event.preventDefault();
    const patientId = (patient?.id || patientIdInput).trim();
    if (!patientId) { report('error', 'Create or load a patient first.'); return; }
    const result = await run('create-consultation', async () => {
      const { data } = await request<Consultation>('/api/v1/consultations', { method: 'POST', body: JSON.stringify({ patient_id: patientId, language }) }, token);
      setConsultation(data); setConsultationIdInput(data.id); setQuestionResult(null); setAnsweredKeys([]); setAnswerText(''); setDocuments([]); setSavedSubmission(null); setWorkspace(null); dashboardLoadedFor.current = null;
      setResponseJson(pretty(currentHistoryPayload({ consultation_id: data.id }, { consultationId: data.id, questionKey: '', questionText: '', answerText: '' })));
      report('success', 'Consultation created.'); return data;
    });
    if (result) setTab('patient');
  };

  const loadConsultation = async (event: FormEvent) => {
    event.preventDefault();
    const id = consultationIdInput.trim();
    if (!id) { report('error', 'Enter a consultation ID.'); return; }
    const result = await run('load-consultation', async () => (await request<Consultation>(`/api/v1/consultations/${encodeURIComponent(id)}`, {}, token)).data);
    if (result) {
      setConsultation(result); setPatientIdInput(result.patient_id); setConsultationIdInput(result.id);
      try {
        const loadedPatient = await request<Patient>(`/api/v1/patients/${encodeURIComponent(result.patient_id)}`, {}, token);
        setPatient(loadedPatient.data);
      } catch {
        /* Consultation is usable even if the patient record cannot be refreshed separately. */
      }
      report('success', 'Consultation loaded. Use this ID for questions, document upload and summary operations.');
    }
  };

  const getNextQuestion = async () => {
    const lastSavedAnswer = getText(savedSubmission?.payload, ['answer_text', 'answer']).trim();
    if (answerText.trim() && answerText.trim() !== lastSavedAnswer) {
      report('error', 'Save the current patient answer before requesting the next question.');
      return;
    }
    if (!activeConsultationId) { report('error', 'Create or load a consultation first.'); return; }
    if (!chiefComplaint.trim()) { report('error', 'Enter the patient-reported chief complaint first.'); return; }

    const result = await run('next-question', async () => {
      const query = new URLSearchParams();
      query.set('chief_complaint', chiefComplaint.trim());
      answeredKeys.forEach((key) => query.append('answered_keys', key));
      const path = `/api/v1/consultations/${encodeURIComponent(activeConsultationId)}/next-question?${query.toString()}`;
      const { data } = await request<unknown>(path, { method: 'POST' }, token);
      setQuestionResult(data);
      const complete = Boolean(data && typeof data === 'object' && (data as Dict).is_complete);
      report('success', complete
        ? 'This pathway has no further required questions. Review and save the current history snapshot if needed.'
        : "Next clinical question loaded. Enter the patient's answer, then save the response.");
      return data;
    });

    if (result) {
      setAnswerText('');
      const parsed = parseJsonObject(responseJson);
      setResponseJson(pretty(currentHistoryPayload(parsed.ok ? parsed.value : undefined, {
        questionKey: getText(result, ['question_key', 'question_id', 'id', 'key']),
        questionText: getText(result, ['question_text', 'question', 'text', 'prompt']),
        answerText: '',
      })));
    }
  };

  const prepareResponseJson = () => {
    const parsed = parseJsonObject(responseJson);
    const payload = currentHistoryPayload(parsed.ok ? parsed.value : undefined);
    setResponseJson(pretty(payload));
    report('info', 'Response payload prepared from the current form and the history request schema. Confirm it before saving.');
  };

  const saveResponse = async () => {
    const parsed = parseJsonObject(responseJson);
    if (!parsed.ok) { report('error', parsed.error); return; }
    const validation = validateHistorySave({
      consultationId: activeConsultationId,
      chiefComplaint,
      answerText,
      hasQuestion: questionResult !== null,
      questionComplete,
    });
    if (validation) { report('error', validation); return; }

    const payload = currentHistoryPayload(parsed.value);
    setResponseJson(pretty(payload));
    const previousAnswer = answerText;

    const result = await run('save-response', async () => {
      const { data, status } = await request<unknown>(
        `/api/v1/consultations/${encodeURIComponent(activeConsultationId)}/responses`,
        { method: 'POST', body: JSON.stringify(payload) },
        token,
      );
      const saved = confirmPersistedSubmission(status, data);
      setSavedSubmission(saved);
      if (questionResult && !questionComplete) {
        const questionKey = getText(questionResult, ['question_key', 'question_id', 'id', 'key']) || `question-${answeredKeys.length + 1}`;
        setAnsweredKeys((current) => (current.includes(questionKey) ? current : [...current, questionKey]));
      }
      const versionLabel = saved.version ? ` version ${saved.version}` : '';
      const verification = saved.verification_status || 'unverified';
      report('success', `History response saved${versionLabel} (id ${saved.id}). Server source: ${saved.source || 'patient_reported'}; verification: ${verification}.`);
      return saved;
    });

    if (result) {
      setAnswerText(previousAnswer);
      setResponseJson(pretty(payload));
    } else {
      setAnswerText(previousAnswer);
    }
  };

  const refreshDocumentsSilent = async (id: string) => {
    try {
      const { data } = await request<Dict>(`/api/v1/consultations/${encodeURIComponent(id)}/documents`, {}, token);
      setDocuments(asDocumentList(data) as DocumentRecord[]);
    } catch {
      /* Keep the prior list and surface the primary operation result. */
    }
  };

  const refreshTimelineSilent = async (id: string) => {
    try {
      const { data } = await request<unknown>(`/api/v1/consultations/${encodeURIComponent(id)}/timeline`, {}, token);
      const events = parseTimelineEvents(data);
      setWorkspace((current) => current && current.consultationId === id ? { ...current, timeline: events, timelineState: 'loaded' } : current);
    } catch {
      /* Keep the prior timeline if the refresh fails */
    }
  };

  const uploadDocument = async (event: FormEvent) => {
    event.preventDefault();
    const consultationId = (consultationIdInput.trim() || consultation?.id || '').trim();
    const fileError = validateDocumentFile(selectedFile, consultationId);
    if (fileError) { report('error', fileError); return; }
    if (!selectedFile) return;

    const fileToUpload = selectedFile;
    const result = await run('upload-document', async () => {
      setUploadProgress('Uploading and requesting server-side extraction…');
      try {
        const form = new FormData();
        form.append('file', fileToUpload);
        const { data } = await request<DocumentRecord>(
          `/api/v1/consultations/${encodeURIComponent(consultationId)}/documents`,
          { method: 'POST', body: form },
          token,
        );
        setDocumentDetail(data);
        setSelectedFile(null);
        await refreshDocumentsSilent(consultationId);
        await refreshTimelineSilent(consultationId);
        report('success', describeUploadResult(data));
        return data;
      } catch (error) {
        await refreshDocumentsSilent(consultationId);
        throw error;
      } finally {
        setUploadProgress(null);
      }
    });
    if (result) setTab('records');
  };

  const refreshDocuments = async (id = activeConsultationId) => {
    if (!id) { report('error', 'Create or load a consultation first.'); return; }
    const result = await run('list-documents', async () => (await request<Dict>(`/api/v1/consultations/${encodeURIComponent(id)}/documents`, {}, token)).data);
    if (result) {
      const rows = asDocumentList(result) as DocumentRecord[];
      setDocuments(rows);
      report('success', `Loaded ${rows.length} saved document(s).`);
    }
  };

  const getDocument = async (id: string) => {
    const result = await run(`get-document-${id}`, async () => (await request<DocumentRecord>(`/api/v1/documents/${encodeURIComponent(id)}`, {}, token)).data);
    if (result) { setDocumentDetail(result); report('success', 'Document detail loaded. Original binary is not returned by the API.'); }
  };

  const reprocessDocument = async (id: string) => {
    setDocuments((current) => current.map((doc) => (doc.id === id ? { ...doc, processing_status: 'processing' } : doc)));
    setDocumentDetail((current) => (current && current.id === id ? { ...current, processing_status: 'processing' } : current));
    const result = await run(`process-document-${id}`, async () => (
      await request<DocumentRecord>(`/api/v1/documents/${encodeURIComponent(id)}/process`, { method: 'POST' }, token)
    ).data);
    if (result) {
      setDocumentDetail(result);
      if (activeConsultationId) await refreshDocumentsSilent(activeConsultationId);
      if (activeConsultationId) await refreshTimelineSilent(activeConsultationId);
      report('success', describeUploadResult(result));
    } else if (activeConsultationId) {
      await refreshDocumentsSilent(activeConsultationId);
    }
  };

  const applySummaryToWorkspace = (consultationId: string, next: DraftSummary | null, state: DashboardWorkspace['summaryState'], error?: string) => {
    setWorkspace((current) => {
      if (!current || current.consultationId !== consultationId) return current;
      return { ...current, summary: next, summaryState: state, summaryError: error };
    });
  };

  const loadDashboardWorkspace = async (requestedId?: string) => {
    const id = requestedId || dashboardTargetId(consultationIdInput, consultation?.id);
    if (!id) { report('error', 'Load a consultation first.'); return; }
    const serial = dashboardSerial.current + 1;
    dashboardSerial.current = serial;
    dashboardLoadedFor.current = id;
    setWorkspace(emptyWorkspace(id));
    setConsultationIdInput(id);

    const result = await run('dashboard-consultation', async () => {
      const details = (await request<Consultation>(`/api/v1/consultations/${encodeURIComponent(id)}`, {}, token)).data;
      if (serial !== dashboardSerial.current) return null;
      if (!belongsToConsultation(details.id, id)) {
        throw new Error('The consultation returned by the API does not match the requested identifier.');
      }

      const [patientResult, summaryResult, documentResult, timelineResult] = await Promise.allSettled([
        request<Patient>(`/api/v1/patients/${encodeURIComponent(details.patient_id)}`, {}, token),
        request<unknown>(`/api/v1/consultations/${encodeURIComponent(id)}/summary`, {}, token),
        request<Dict>(`/api/v1/consultations/${encodeURIComponent(id)}/documents`, {}, token),
        request<unknown>(`/api/v1/consultations/${encodeURIComponent(id)}/timeline`, {}, token),
      ]);
      if (serial !== dashboardSerial.current) return null;

      const next: DashboardWorkspace = {
        consultationId: id,
        loadState: 'ready',
        consultation: details,
        patient: null,
        summary: null,
        summaryState: 'missing',
        documents: [],
        timeline: [],
        timelineState: 'idle',
      };

      if (patientResult.status === 'fulfilled') {
        next.patient = patientResult.value.data;
      } else {
        next.patientError = formatError(patientResult.reason);
      }

      if (summaryResult.status === 'fulfilled') {
        const parsed = parseDraftSummary(summaryResult.value.data);
        if (parsed && belongsToConsultation(parsed.consultation_id, id)) {
          next.summary = parsed;
          next.summaryState = 'loaded';
        } else {
          next.summaryState = 'error';
          next.summaryError = 'The saved summary did not match this consultation.';
        }
      } else {
        const message = formatError(summaryResult.reason);
        if (isMissingSummaryMessage(message)) {
          next.summaryState = 'missing';
        } else {
          next.summaryState = 'error';
          next.summaryError = message;
        }
      }

      if (documentResult.status === 'fulfilled') {
        next.documents = parseDashboardDocuments(documentResult.value.data, id);
      } else {
        next.documentsError = formatError(documentResult.reason);
      }

      if (timelineResult.status === 'fulfilled') {
        next.timeline = parseTimelineEvents(timelineResult.value.data);
        next.timelineState = 'loaded';
      } else {
        next.timelineState = 'error';
        next.timelineError = formatError(timelineResult.reason);
      }

      return next;
    });

    if (serial !== dashboardSerial.current) return;
    if (!result) {
      setWorkspace((current) => current && current.consultationId === id ? { ...current, loadState: 'error', error: 'Unable to load this consultation.' } : current);
      return;
    }
    if (!result.consultation) {
      const message = 'The consultation response did not include a valid consultation record.';
      setWorkspace({ ...result, loadState: 'error', error: message });
      report('error', message);
      return;
    }

    setWorkspace(result);
    setConsultation(result.consultation);
    setPatientIdInput(result.consultation.patient_id);
    setDocuments(result.documents as DocumentRecord[]);
    if (result.patient) setPatient(result.patient);
    report('success', 'Doctor workspace loaded. Review and verification actions are available for summaries, red flags, and documents.');
  };

  const generateSummary = async () => {
    const id = dashboardTargetId(consultationIdInput, consultation?.id);
    if (!id) { report('error', 'Create or load a consultation first.'); return; }
    const result = await run('generate-summary', async () => {
      const { data, status } = await request<unknown>(
        `/api/v1/consultations/${encodeURIComponent(id)}/summary`,
        { method: 'POST' },
        token,
      );
      let saved = confirmDraftSummary(status, data);
      if (!belongsToConsultation(saved.consultation_id, id)) {
        throw new Error('The generated summary does not belong to the selected consultation.');
      }
      try {
        const refreshed = await request<unknown>(`/api/v1/consultations/${encodeURIComponent(id)}/summary`, {}, token);
        const latest = parseDraftSummary(refreshed.data);
        if (latest && belongsToConsultation(latest.consultation_id, id)) saved = latest;
      } catch {
        /* Keep the POST response when the follow-up GET is unavailable. */
      }
      return saved;
    });

    if (result) {
      applySummaryToWorkspace(id, result, 'loaded');
      await refreshTimelineSilent(id);
      report('success', `Draft summary ${result.summary_id} saved with status ${result.review_status.replace(/_/g, ' ')}. Treat it as a draft, not a clinical decision.`);
    }
  };

  const getSummary = async () => {
    const id = dashboardTargetId(consultationIdInput, consultation?.id);
    if (!id) { report('error', 'Create or load a consultation first.'); return; }
    await run('get-summary', async () => {
      try {
        const { data } = await request<unknown>(`/api/v1/consultations/${encodeURIComponent(id)}/summary`, {}, token);
        const parsed = parseDraftSummary(data);
        if (!parsed) throw new Error('The server did not return a recognizable draft summary.');
        if (!belongsToConsultation(parsed.consultation_id, id)) {
          throw new Error('The saved summary does not belong to the selected consultation.');
        }
        applySummaryToWorkspace(id, parsed, 'loaded');
        report('success', 'Saved draft summary loaded.');
        return parsed;
      } catch (error) {
        const message = formatError(error);
        if (isMissingSummaryMessage(message)) {
          applySummaryToWorkspace(id, null, 'missing');
          report('info', 'No saved clinical summary exists for this consultation yet.');
          return null;
        }
        setWorkspace((current) => (
          current && current.consultationId === id
            ? { ...current, summaryState: 'error', summaryError: message }
            : current
        ));
        throw error;
      }
    });
  };

  const refreshDashboard = async () => {
    await loadDashboardWorkspace();
  };

  const reviewSummaryAction = async (summaryId: string, newStatus: string) => {
    const id = dashboardTargetId(consultationIdInput, consultation?.id);
    if (!id) { report('error', 'Load a consultation first.'); return; }
    const notes = reviewNotes[summaryId]?.trim() || null;
    const summaryUuid = stripSummaryPrefix(summaryId);
    await run(`review-summary-${summaryId}-${newStatus}`, async () => {
      const { data } = await request<unknown>(
        `/api/v1/summaries/${encodeURIComponent(summaryUuid)}/review`,
        { method: 'POST', body: JSON.stringify({ status: newStatus, notes }) },
        token,
      );
      const parsed = parseDraftSummary(data);
      if (!parsed || !belongsToConsultation(parsed.consultation_id, id)) {
        throw new Error('The server did not return a recognizable reviewed summary.');
      }
      applySummaryToWorkspace(id, parsed, 'loaded');
      await refreshTimelineSilent(id);
      setReviewNotes((prev) => {
        const next = { ...prev };
        delete next[summaryId];
        return next;
      });
      report('success', `Summary reviewed: ${newStatus.replace(/_/g, ' ')}. Server confirmed status.`);
    });
  };

  const correctSummaryAction = async (summaryId: string) => {
    if (!correctionDraft || !visibleSummary) return;
    const id = dashboardTargetId(consultationIdInput, consultation?.id);
    if (!id) { report('error', 'Load a consultation first.'); return; }
    const payload: Dict = { notes: correctionDraft.notes.trim() || null };
    if (correctionDraft.cc !== visibleSummary.chief_complaint) payload.chief_complaint = correctionDraft.cc;
    if (correctionDraft.hpi !== visibleSummary.history_of_present_illness) payload.history_of_present_illness = correctionDraft.hpi;
    if (!payload.chief_complaint && !payload.history_of_present_illness) {
      report('error', 'Change at least one field before applying a correction.');
      return;
    }
    const summaryUuid = stripSummaryPrefix(summaryId);
    await run(`correct-summary-${summaryId}`, async () => {
      const { data } = await request<unknown>(
        `/api/v1/summaries/${encodeURIComponent(summaryUuid)}`,
        { method: 'PATCH', body: JSON.stringify(payload) },
        token,
      );
      const parsed = parseDraftSummary(data);
      if (!parsed || !belongsToConsultation(parsed.consultation_id, id)) {
        throw new Error('The server did not return a recognizable corrected summary.');
      }
      applySummaryToWorkspace(id, parsed, 'loaded');
      await refreshTimelineSilent(id);
      report('success', 'Summary correction persisted. Review status reset to pending.');
    });
  };

  const reviewRedFlagAction = async (flagId: string, newStatus: string) => {
    const id = dashboardTargetId(consultationIdInput, consultation?.id);
    if (!id) { report('error', 'Load a consultation first.'); return; }
    await run(`review-flag-${flagId}-${newStatus}`, async () => {
      await request(
        `/api/v1/red-flags/${encodeURIComponent(flagId)}/review`,
        { method: 'POST', body: JSON.stringify({ status: newStatus, notes: null }) },
        token,
      );
      try {
        const { data } = await request<unknown>(`/api/v1/consultations/${encodeURIComponent(id)}/summary`, {}, token);
        const parsed = parseDraftSummary(data);
        if (parsed && belongsToConsultation(parsed.consultation_id, id)) {
          applySummaryToWorkspace(id, parsed, 'loaded');
        }
        await refreshTimelineSilent(id);
      } catch {
        /* Do not mask a successful review if the follow-up GET fails. */
      }
      report('success', `Red flag reviewed: ${newStatus.replace(/_/g, ' ')}.`);
    });
  };

  const verifyDocumentAction = async (documentId: string, newStatus: string) => {
    await run(`verify-document-${documentId}-${newStatus}`, async () => {
      const { data } = await request<DocumentRecord>(
        `/api/v1/documents/${encodeURIComponent(documentId)}/verify`,
        { method: 'POST', body: JSON.stringify({ status: newStatus, notes: null }) },
        token,
      );
      setDocumentDetail((current) => (current && current.id === documentId ? { ...current, ...data } : current));
      setDocuments((current) => current.map((doc) => (doc.id === documentId ? { ...doc, ...data } : doc)));
      await refreshTimelineSilent(activeConsultationId);
      report('success', `Document verification recorded: ${newStatus}.`);
    });
  };

  useEffect(() => {
    if (tab !== 'dashboard' || !token) return;
    const id = dashboardTargetId(consultationIdInput, consultation?.id);
    if (!id) {
      setWorkspace(null);
      dashboardLoadedFor.current = null;
      return;
    }
    if (dashboardLoadedFor.current === id && workspace?.loadState === 'ready' && workspace.consultationId === id) return;
    void loadDashboardWorkspace(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, token, consultation?.id]);

  const onFileChosen = (file: File | null) => {
    if (!file) { setSelectedFile(null); return; }
    const error = validateDocumentFile(file, activeConsultationId || 'pending');
    if (error && error !== 'Create or load a consultation first.') {
      setSelectedFile(null);
      report('error', error);
      return;
    }
    setSelectedFile(file);
  };

  const logoutButton = user && <button className="ghost-button small" onClick={logout}><LogOut size={15} /> Sign out</button>;
  const tabItems: { id: Tab; label: string; icon: typeof UserRound }[] = [
    { id: 'patient', label: 'Patient intake', icon: UserRound },
    { id: 'records', label: 'Documents & records', icon: FileText },
    { id: 'dashboard', label: 'Doctor dashboard', icon: LayoutDashboard },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><HeartPulse size={24} /></div><div><div className="brand-title">Nurse Amma</div><div className="brand-subtitle">CARE WORKSPACE</div></div></div>
        <div className="side-section-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {tabItems.map((item) => <button key={item.id} onClick={() => setTab(item.id)} className={`nav-item ${tab === item.id ? 'active' : ''}`}><item.icon size={18} /><span>{item.label}</span></button>)}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-note"><ShieldCheck size={17} /><div><strong>Privacy first</strong><p>Use synthetic records. Clinical findings remain unverified until reviewed.</p></div></div>
        <div className="sidebar-footer">Academic prototype · v0.1</div>
      </aside>

      <main className="main-area">
        <header className="topbar"><div><div className="eyebrow">NURSE AMMA / INTEGRATED WORKSPACE</div><h1>{tab === 'patient' ? 'Patient intake' : tab === 'records' ? 'Documents & records' : 'Doctor dashboard'}</h1></div><div className="topbar-actions"><span className={`connection ${apiState}`}><span className="dot" />{apiState === 'online' ? 'API reachable' : apiState === 'offline' ? 'API unavailable' : 'Checking API'}</span>{logoutButton}</div></header>

        {notice && <div className={`notice notice-${notice.kind}`} role="status"><span>{notice.text}</span><button aria-label="Dismiss notification" onClick={() => setNotice(null)}>×</button></div>}

        {!token ? (
          <section className="login-layout">
            <div className="welcome-panel"><div className="welcome-icon"><Stethoscope size={28} /></div><span className="kicker">PRE-CONSULTATION CARE</span><h2>One connected view of the patient's story.</h2><p>Collect reported history, process uploaded documents and prepare a structured draft for professional review.</p><div className="welcome-checks"><span><BadgeCheck size={16} /> Source-aware records</span><span><BadgeCheck size={16} /> Protected API access</span><span><BadgeCheck size={16} /> Human review first</span></div></div>
            <form className="card login-card" onSubmit={login}><div className="card-heading"><div className="icon-chip"><LogIn size={19} /></div><div><h2>Sign in</h2><p>Use the account created through the backend API.</p></div></div><div className="field"><Label>Email address</Label><input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="clinician@example.com" /></div><div className="field"><Label>Password</Label><input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter password" /></div><button className="primary-button full" disabled={loginBusy}>{loginBusy ? <LoaderCircle className="spin" size={17} /> : <LogIn size={17} />} Sign in securely</button><p className="microcopy">The access token is held in memory and is cleared when you sign out or refresh the page.</p></form>
          </section>
        ) : (
          <>
            <section className="context-strip"><div className="context-icon"><Users size={18} /></div><div className="context-copy"><strong>{patient?.full_name || 'No patient loaded'}</strong><span>{activePatientId || 'Create or load a patient to begin'}{activeConsultationId ? ` · Consultation ${activeConsultationId}` : ''}</span></div><div className="context-right"><StatusPill tone={consultation?.status === 'completed' ? 'good' : activeConsultationId ? 'warn' : 'neutral'}>{consultation?.status || 'No active consultation'}</StatusPill><span className="role-text">{String(user?.role || 'authenticated user')}</span></div></section>

            {tab === 'patient' && <div className="content-grid patient-grid">
              <section className="card"><div className="card-heading"><div className="icon-chip"><UserRound size={18} /></div><div><h2>Patient details</h2><p>Create a synthetic patient or load an existing record.</p></div><span className="step-no">01</span></div>
                <form onSubmit={createPatient} className="form-stack">
                  <div className="field"><Label>Patient full name</Label><input value={patientName} onChange={(e) => setPatientName(e.target.value)} placeholder="Synthetic Test Patient" required /></div>
                  <div className="field"><Label>Date of birth <span className="optional">(optional)</span></Label><input type="date" value={dob} onChange={(e) => setDob(e.target.value)} /></div>
                  
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', margin: '4px 0' }}>
                    <input 
                      type="checkbox" 
                      id="consent-cb" 
                      checked={hasConsent} 
                      onChange={(e) => setHasConsent(e.target.checked)} 
                      style={{ marginTop: '3px' }} 
                    />
                    <label htmlFor="consent-cb" style={{ fontSize: '11px', lineHeight: '1.4', color: '#38564e', cursor: 'pointer' }}>
                      I confirm I have obtained consent to process this patient's medical data.
                    </label>
                  </div>

                  <button className="primary-button" disabled={busy !== null || !hasConsent}>
                    {busy === 'create-patient' ? <LoaderCircle className="spin" size={16} /> : <Users size={16} />} Create patient
                  </button>
                </form>
                <div className="divider-label"><span>OR LOAD BY PATIENT ID</span></div><form className="inline-form" onSubmit={loadPatient}><input value={patientIdInput} onChange={(e) => setPatientIdInput(e.target.value)} placeholder="Patient UUID" aria-label="Patient ID" /><button className="secondary-button" disabled={busy !== null}>Load</button></form>
                {patient && <div className="record-summary"><div><small>Patient ID</small><code>{patient.id}</code></div><StatusPill tone="good">Saved</StatusPill></div>}
              </section>

              <section className="card"><div className="card-heading"><div className="icon-chip"><ClipboardList size={18} /></div><div><h2>Start consultation</h2><p>Connect the clinical workflow to a patient record.</p></div><span className="step-no">02</span></div>
                <form onSubmit={createConsultation} className="form-stack"><div className="field"><Label>Patient ID</Label><input value={patient?.id || patientIdInput} onChange={(e) => { setPatientIdInput(e.target.value); if (patient && patient.id !== e.target.value) setPatient(null); }} placeholder="Create or enter patient UUID" required /></div><div className="field"><Label>Language</Label><select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="en">English</option><option value="ta">Tamil</option><option value="hi">Hindi</option></select></div><button className="primary-button" disabled={busy !== null || !activePatientId}>{busy === 'create-consultation' ? <LoaderCircle className="spin" size={16} /> : <ArrowRight size={16} />} Start consultation</button></form>
                <div className="divider-label"><span>OR LOAD EXISTING CONSULTATION</span></div><form className="inline-form" onSubmit={loadConsultation}><input value={consultationIdInput} onChange={(e) => { setConsultationIdInput(e.target.value); setWorkspace(null); setConsultation(null);setPatient(null); }} placeholder="Consultation UUID" aria-label="Consultation ID" /><button className="secondary-button" disabled={busy !== null}>Load</button></form>
                {consultation && <div className="record-summary"><div><small>Consultation ID</small><code>{consultation.id}</code></div><StatusPill tone="good">Connected</StatusPill></div>}
              </section>

              <section className="card span-two"><div className="card-heading"><div className="icon-chip"><Activity size={18} /></div><div><h2>Clinical history</h2><p>Request the next question, capture the response, then save through the existing API.</p></div><span className="step-no">03</span></div>
                <div className="question-layout">
                  <div className="form-stack">
                    <div className="field"><Label>Chief complaint</Label><textarea rows={3} value={chiefComplaint} onChange={(e) => setChiefComplaint(e.target.value)} placeholder="Enter the patient's reported main concern. Do not add inferred symptoms." /></div>
                    <div className="compact-grid">
                      <div className="field"><Label>Duration value <span className="optional">(optional)</span></Label><input type="number" min={1} step={1} value={durationValue} onChange={(e) => setDurationValue(e.target.value)} placeholder="e.g. 4" /></div>
                      <div className="field"><Label>Duration unit</Label><select value={durationUnit} onChange={(e) => setDurationUnit(e.target.value as DurationUnit)}><option value="hours">hours</option><option value="days">days</option><option value="weeks">weeks</option><option value="months">months</option></select></div>
                    </div>
                    <div className="compact-grid">
                      <div className="field"><Label>Severity <span className="optional">(optional)</span></Label><input value={severity} onChange={(e) => setSeverity(e.target.value)} placeholder="mild, moderate, severe" /></div>
                      <div className="field"><Label>Progression <span className="optional">(optional)</span></Label><input value={progression} onChange={(e) => setProgression(e.target.value)} placeholder="worsening, improving" /></div>
                    </div>
                    <div className="field"><Label>Location <span className="optional">(optional)</span></Label><input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Patient-reported location" /></div>
                    <button className="primary-button" onClick={getNextQuestion} disabled={busy !== null || !activeConsultationId}>{busy === 'next-question' ? <LoaderCircle className="spin" size={16} /> : <Workflow size={16} />} Get next question</button>
                    {questionResult !== null && (
                      <div className="question-card">
                        <span className="kicker">NEXT QUESTION RESPONSE</span>
                        <p>{getText(questionResult, ['question_text', 'question', 'text', 'prompt']) || 'Inspect the structured response below.'}</p>
                        {questionComplete && <StatusPill tone="good">Pathway complete</StatusPill>}
                        {questionOptions.length > 0 && (
                          <div className="choice-row">
                            {questionOptions.map((option) => (
                              <button type="button" key={option} className={`choice-chip ${answerText === option ? 'selected' : ''}`} onClick={() => setAnswerText(option)} disabled={busy !== null}>{option}</button>
                            ))}
                          </div>
                        )}
                        <JsonPanel value={questionResult} />
                      </div>
                    )}
                  </div>
                  <div className="form-stack">
                    <div className="field"><Label>Patient answer</Label><textarea rows={3} value={answerText} onChange={(e) => setAnswerText(e.target.value)} placeholder="Capture what the patient actually said." /></div>
                    <div className="field"><Label>Associated symptoms <span className="optional">(comma-separated, optional)</span></Label><input value={associatedSymptoms} onChange={(e) => setAssociatedSymptoms(e.target.value)} placeholder="e.g. body pain" /></div>
                    <div className="field"><Label>Current medications <span className="optional">(optional)</span></Label><input value={currentMedications} onChange={(e) => setCurrentMedications(e.target.value)} placeholder="Patient-reported medications" /></div>
                    <div className="field"><Label>Past medical history <span className="optional">(optional)</span></Label><input value={pastMedicalHistory} onChange={(e) => setPastMedicalHistory(e.target.value)} /></div>
                    <div className="field"><Label>Allergies <span className="optional">(optional)</span></Label><input value={allergies} onChange={(e) => setAllergies(e.target.value)} /></div>
                    <button className="secondary-button" onClick={prepareResponseJson} disabled={!activeConsultationId || busy !== null}>Prepare response payload</button>
                    <div className="field"><Label>Response JSON <span className="optional">(review API fields before submitting)</span></Label><textarea className="json-editor" rows={10} value={responseJson} onChange={(e) => setResponseJson(e.target.value)} spellCheck={false} /></div>
                    <button className="primary-button" onClick={saveResponse} disabled={busy !== null || !activeConsultationId}>{busy === 'save-response' ? <LoaderCircle className="spin" size={16} /> : <BadgeCheck size={16} />} Save response</button>
                    {savedSubmission && (
                      <div className="save-confirm">
                        <div>
                          <small>Server-confirmed submission{savedSubmission.version ? ` · version ${savedSubmission.version}` : ''}</small>
                          <code>{savedSubmission.id}</code>
                          <span>{getText(savedSubmission.payload, ['answer_text', 'answer']) || 'No follow-up answer was included in this snapshot.'}</span>
                        </div>
                        <StatusPill tone="warn">{savedSubmission.verification_status || 'unverified'}</StatusPill>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </div>}

            {tab === 'records' && <div className="content-grid records-grid">
              <section className="card">
                <div className="card-heading"><div className="icon-chip"><CloudUpload size={18} /></div><div><h2>Upload medical document</h2><p>Use a synthetic PDF or image. Uploads are tied to the current consultation.</p></div></div>
                <form className="form-stack" onSubmit={uploadDocument}>
                  <div className="field"><Label>Consultation ID</Label><input value={consultationIdInput || consultation?.id || ''} onChange={(e) => { setConsultationIdInput(e.target.value); setWorkspace(null); setConsultation(null); }} placeholder="Consultation UUID" required /></div>
                  <label className="drop-zone">
                    <CloudUpload size={25} />
                    <strong>{selectedFile?.name || 'Choose a PDF or image'}</strong>
                    <span>PDF, PNG, JPG, JPEG · maximum 10 MB</span>
                    <input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={(e) => onFileChosen(e.target.files?.[0] || null)} />
                  </label>
                  <button className="primary-button" disabled={busy !== null || !selectedFile || !activeConsultationId}>
                    {busy === 'upload-document' ? <LoaderCircle className="spin" size={16} /> : <CloudUpload size={16} />}
                    {busy === 'upload-document' ? 'Uploading…' : 'Upload document'}
                  </button>
                </form>
                {uploadProgress && <div className="notice notice-info">{uploadProgress}</div>}
                <div className="callout"><ShieldCheck size={17} /><p>Files are validated by the backend. Extracted entities must remain <strong>unverified</strong> until a clinician reviews the original source. Upload success is not the same as completed extraction.</p></div>
              </section>

              <section className="card">
                <div className="card-heading"><div className="icon-chip"><FileText size={18} /></div><div><h2>Saved documents</h2><p>Read metadata and extraction results stored by the backend.</p></div></div>
                <div className="field"><Label>Consultation ID</Label><input value={consultationIdInput || consultation?.id || ''} onChange={(e) => { setConsultationIdInput(e.target.value); setWorkspace(null); setConsultation(null); }} placeholder="Consultation UUID" /></div>
                <button className="secondary-button" onClick={() => refreshDocuments()} disabled={busy !== null || !activeConsultationId}>{busy === 'list-documents' ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />} Refresh documents</button>
                <div className="document-list">
                  {documents.length === 0 ? (
                    <div className="empty-state"><FileText size={26} /><strong>No documents loaded</strong><span>Upload a synthetic report or refresh the consultation list.</span></div>
                  ) : documents.map((doc) => (
                    <div className="document-row" key={doc.id}>
                      <div className="document-icon"><FileText size={18} /></div>
                      <div className="document-info">
                        <strong>{doc.filename || doc.id}</strong>
                        <span>{doc.extraction_method || 'Extraction pending'} · {doc.page_count ?? '—'} page(s)</span>
                        <code>{doc.id}</code>
                      </div>
                      <div className="document-actions">
                        <StatusPill tone={processingTone(doc.processing_status)}>{doc.processing_status || 'unknown'}</StatusPill>
                        <StatusPill tone={verificationTone(doc.verification_status)}>{doc.verification_status || 'unverified'}</StatusPill>
                        <button className="text-button" onClick={() => getDocument(doc.id)} disabled={busy !== null}>View</button>
                        <button className="text-button" onClick={() => reprocessDocument(doc.id)} disabled={busy !== null}>Reprocess</button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {documentDetail && (
                <section className="card span-two">
                  <div className="card-heading">
                    <div className="icon-chip"><FileText size={18} /></div>
                    <div>
                      <h2>{documentDetail.filename || 'Document detail'}</h2>
                      <p>Persisted extraction; original binary is not sent by the API. Identifier: {documentDetail.id}</p>
                    </div>
                    <StatusPill tone={verificationTone(documentDetail.verification_status)}>{documentDetail.verification_status || 'unverified'}</StatusPill>
                  </div>
                  <div className="metric-grid">
                    <div className="metric"><small>Processing</small><strong>{documentDetail.processing_status || '—'}</strong></div>
                    <div className="metric"><small>Extraction method</small><strong>{documentDetail.extraction_method || '—'}</strong></div>
                    <div className="metric"><small>Pages</small><strong>{documentDetail.page_count ?? '—'}</strong></div>
                    <div className="metric"><small>Entities</small><strong>{documentDetail.entities?.length ?? 0}</strong></div>
                  </div>
                  {documentDetail.error_message && <div className="notice notice-error">{documentDetail.error_message}</div>}
                  {documentDetail.processing_status === 'completed' && !documentDetail.text?.trim() && <div className="notice notice-info">Extraction finished, but no text was returned.</div>}
                  {documentDetail.processing_status === 'processing' && <div className="notice notice-info">Processing is in progress. Results are not complete yet.</div>}
                  {documentVerifyOptions(documentDetail.verification_status || '').length > 0 && (
                    <div className="button-row" style={{ marginTop: '12px' }}>
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
                  {documentDetail.verified_at && (
                    <p className="microcopy" style={{ textAlign: 'left', marginTop: '8px' }}>
                      Reviewed {formatTimestamp(documentDetail.verified_at)}
                      {documentDetail.verification_notes ? ` · ${documentDetail.verification_notes}` : ''}
                    </p>
                  )}
                  <h3 className="subheading">Extracted entities</h3>
                  <JsonPanel value={documentDetail.entities || []} />
                  <h3 className="subheading">Extracted text</h3>
                  <pre className="text-panel">{documentDetail.text || 'No extracted text returned.'}</pre>
                </section>
              )}
            </div>}

            {tab === 'dashboard' && <div className="dashboard-layout">
              <section className="card dashboard-toolbar"><div className="field grow"><Label>Consultation ID</Label><input value={consultationIdInput || consultation?.id || ''} onChange={(e) => { setConsultationIdInput(e.target.value); setWorkspace(null); setConsultation(null); }} placeholder="Paste a consultation UUID" /></div><button className="primary-button" onClick={refreshDashboard} disabled={busy !== null || !activeConsultationId}>{busy === 'dashboard-consultation' ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />} Refresh workspace</button></section>
              <div className="dashboard-cards">
                <section className="card"><div className="card-heading"><div className="icon-chip"><ClipboardList size={18} /></div><div><h2>Consultation</h2><p>Stored consultation context</p></div></div>{consultation ? <><div className="detail-line"><span>Patient ID</span><code>{consultation.patient_id}</code></div><div className="detail-line"><span>Language</span><strong>{consultation.language || '—'}</strong></div><div className="detail-line"><span>Status</span><StatusPill>{consultation.status || 'unknown'}</StatusPill></div></> : <div className="empty-state compact">Load a consultation to view its details.</div>}</section>
                <section className="card">
                  <div className="card-heading">
                    <div className="icon-chip"><FileText size={18} /></div>
                    <div><h2>Draft summary</h2><p>Structured summary from the saved clinical history</p></div>
                  </div>
                  <div className="button-row">
                    <button className="secondary-button" onClick={getSummary} disabled={busy !== null || !activeConsultationId || !activeWorkspace?.consultation}>
                      Retrieve saved summary
                    </button>
                    <button className="primary-button" onClick={generateSummary} disabled={busy !== null || !activeConsultationId || !activeWorkspace?.consultation}>
                      {busy === 'generate-summary' ? <LoaderCircle className="spin" size={16} /> : <Activity size={16} />}
                      Generate draft summary from latest saved history
                    </button>
                  </div>
                  {!activeWorkspace && <div className="empty-state compact">Load the consultation into the doctor workspace before retrieving or generating its summary.</div>}
                  {activeWorkspace?.summaryState === 'error' && <div className="notice notice-error">{activeWorkspace.summaryError || 'The summary could not be loaded.'}</div>}
                  {activeWorkspace?.summaryState === 'missing' && <div className="empty-state compact">No saved summary exists for this consultation. Save patient-reported clinical history first, then generate a draft.</div>}
                  {visibleSummary && <div className="clinical-summary">
                    <div className="summary-status-row">
                      <div><small>Summary ID</small><code>{visibleSummary.summary_id}</code></div>
                      <StatusPill tone={verificationLabel(visibleSummary.review_status).tone}>
                        {visibleSummary.review_status.replace(/_/g, ' ')}
                      </StatusPill>
                    </div>
                    <div className="summary-section">
                      <h3 className="subheading">Chief complaint</h3>
                      <p>{visibleSummary.chief_complaint || 'Not recorded.'}</p>
                    </div>
                    <div className="summary-section">
                      <h3 className="subheading">History of present illness</h3>
                      <p>{visibleSummary.history_of_present_illness || 'Not recorded.'}</p>
                    </div>
                    <div className="summary-section">
                      <h3 className="subheading">Past medical history</h3>
                      {visibleSummary.past_medical_history.length > 0
                        ? <ul>{visibleSummary.past_medical_history.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
                        : <p>No past medical history recorded in this summary.</p>}
                    </div>
                    <div className="summary-section">
                      <h3 className="subheading">Medication history</h3>
                      {visibleSummary.medication_history.length > 0
                        ? <ul className="summary-medications">{visibleSummary.medication_history.map((medication, index) => <li key={`${medication.name}-${index}`}>
                            {medication.name.trim().toLowerCase() === 'not provided'
                              ? <span className="medication-not-provided">No medication information provided.</span>
                              : <>
                                  <strong>{medication.name}</strong>
                                  <span>{sourceLabel(medication.source_type)}</span>
                                  <StatusPill tone={medication.status === 'verified' ? 'good' : 'warn'}>{verificationLabel(medication.status).text}</StatusPill>
                                </>}
                          </li>)}</ul>
                        : <p>No medications recorded in this summary.</p>}
                    </div>
                    <div className="summary-section">
                      <h3 className="subheading">Allergies</h3>
                      {visibleSummary.allergies.length > 0
                        ? <ul>{visibleSummary.allergies.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
                        : <p>No allergies recorded in this summary.</p>}
                    </div>
                    <div className="summary-section">
                      <h3 className="subheading">Investigation history</h3>
                      {visibleSummary.investigation_history.length > 0
                        ? <ul>{visibleSummary.investigation_history.map((item, index) => {
                            const title = getText(item, ['name', 'test_name', 'investigation', 'title', 'description', 'result', 'finding']);
                            return <li key={index}>{title || 'Investigation record returned by the API; detailed fields are not yet mapped in this view.'}</li>;
                          })}</ul>
                        : <p>No investigations recorded in this summary.</p>}
                    </div>
                    <div className="summary-section">
                      <h3 className="subheading">Red flags</h3>
                      {visibleSummary.red_flags.length > 0
                        ? <div className="red-flag-list">{visibleSummary.red_flags.map((flag) => {
                            const reviewId = flag.id;
                            const nextOptions = reviewId ? redFlagReviewOptions(flag.review_status) : [];
                            return (
                              <div className="notice notice-error" key={reviewId || flag.flag_id}>
                                <strong>{flag.severity.toUpperCase()} — {flag.trigger}</strong>
                                <p>{flag.action_required}</p>
                                <small>
                                  Review status: {flag.review_status.replace(/_/g, ' ')}
                                  {flag.reviewed_at ? ` · Reviewed ${formatTimestamp(flag.reviewed_at)}` : ''}
                                </small>
                                {flag.review_notes && <p><small>Notes: {flag.review_notes}</small></p>}
                                {nextOptions.length > 0 && reviewId && (
                                  <div className="button-row" style={{ marginTop: '8px' }}>
                                    {nextOptions.map((nextStatus) => (
                                      <button
                                        key={nextStatus}
                                        type="button"
                                        className="secondary-button small"
                                        disabled={busy !== null}
                                        onClick={() => reviewRedFlagAction(reviewId, nextStatus)}
                                      >
                                        {busy === `review-flag-${reviewId}-${nextStatus}` ? <LoaderCircle className="spin" size={14} /> : <ShieldCheck size={14} />}
                                        {nextStatus.replace(/_/g, ' ')}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}</div>
                        : <p>{redFlagAbsenceNote(visibleSummary.red_flags)}</p>}
                    </div>
                    <div className="notice notice-info">This is a generated draft, not a diagnosis or clinical decision. Patient-reported and extracted information must not be treated as verified unless the backend records that verification.</div>
                  </div>}
                </section>
                <section className="card">
                  <div className="card-heading">
                    <div className="icon-chip"><Workflow size={18} /></div>
                    <div>
                      <h2>Medical timeline</h2>
                      <p>Chronological events derived from persisted records for this consultation</p>
                    </div>
                  </div>
                  {activeWorkspace?.timelineState === 'error' && (
                    <div className="notice notice-error">
                      {activeWorkspace.timelineError || 'The timeline could not be loaded.'}
                    </div>
                  )}
                  {activeWorkspace?.timelineState === 'idle' && (
                    <div className="empty-state compact">
                      Load the workspace to retrieve timeline events.
                    </div>
                  )}
                  {activeWorkspace?.timelineState === 'loaded' && activeWorkspace.timeline.length === 0 && (
                    <div className="empty-state compact">
                      No timeline events have been recorded for this consultation yet.
                    </div>
                  )}
                  {activeWorkspace?.timelineState === 'loaded' && activeWorkspace.timeline.length > 0 && (
                    <div className="document-list">
                      {activeWorkspace.timeline.map((event) => {
                        const label = verificationLabel(event.status);
                        return (
                          <div className="document-row" key={event.event_id}>
                            <div className="document-icon"><Activity size={18} /></div>
                            <div className="document-info">
                              <strong>{event.title}</strong>
                              <span>{formatTimestamp(event.occurred_at)} · {sourceLabel(event.source)}</span>
                              {event.description && <span>{event.description}</span>}
                              <code>{event.event_type}</code>
                            </div>
                            <StatusPill tone={label.tone}>{label.text}</StatusPill>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </section>
                <section className="card">
                  <div className="card-heading">
                    <div className="icon-chip"><ShieldCheck size={18} /></div>
                    <div><h2>Clinical review</h2><p>Persisted review, verification, and correction</p></div>
                  </div>
                  {!visibleSummary && <div className="empty-state compact">Load a saved summary before recording a review.</div>}
                  {visibleSummary && (
                    <>
                      <div className="detail-line">
                        <span>Review status</span>
                        <StatusPill tone={verificationLabel(visibleSummary.review_status).tone}>
                          {visibleSummary.review_status.replace(/_/g, ' ')}
                        </StatusPill>
                      </div>
                      {visibleSummary.reviewed_at && (
                        <div className="detail-line">
                          <span>Reviewed</span>
                          <strong>{formatTimestamp(visibleSummary.reviewed_at)}</strong>
                        </div>
                      )}
                      {visibleSummary.review_notes && (
                        <div className="detail-line">
                          <span>Review notes</span>
                          <strong>{visibleSummary.review_notes}</strong>
                        </div>
                      )}
                      {summaryReviewOptions(visibleSummary.review_status).length > 0 && (
                        <div className="form-stack">
                          <div className="field">
                            <Label>Review notes <span className="optional">(optional)</span></Label>
                            <textarea
                              rows={2}
                              value={reviewNotes[visibleSummary.summary_id] || ''}
                              onChange={(e) => setReviewNotes((prev) => ({ ...prev, [visibleSummary.summary_id]: e.target.value }))}
                              placeholder="Notes to be persisted with the review"
                            />
                          </div>
                          <div className="button-row">
                            {summaryReviewOptions(visibleSummary.review_status).map((status) => (
                              <button
                                key={status}
                                type="button"
                                className={status === 'approved' ? 'primary-button' : 'secondary-button'}
                                disabled={busy !== null}
                                onClick={() => reviewSummaryAction(visibleSummary.summary_id, status)}
                              >
                                {busy === `review-summary-${visibleSummary.summary_id}-${status}` ? <LoaderCircle className="spin" size={14} /> : <ShieldCheck size={14} />}
                                Mark {status.replace(/_/g, ' ')}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      <div className="callout" style={{ marginTop: '16px' }}>
                        <AlertCircle size={17} />
                        <p>Corrections reset the review status to pending and invalidate any prior approval. Only server-confirmed reviews are labelled verified; the frontend never upgrades status on its own.</p>
                      </div>
                      {correctionDraft && correctionDraft.summaryId === visibleSummary.summary_id && (
                        <>
                          <div className="field" style={{ marginTop: '16px' }}>
                            <Label>Correct chief complaint</Label>
                            <textarea
                              rows={2}
                              value={correctionDraft.cc}
                              onChange={(e) => setCorrectionDraft((current) => current ? { ...current, cc: e.target.value } : current)}
                            />
                          </div>
                          <div className="field">
                            <Label>Correct history of present illness</Label>
                            <textarea
                              rows={4}
                              value={correctionDraft.hpi}
                              onChange={(e) => setCorrectionDraft((current) => current ? { ...current, hpi: e.target.value } : current)}
                            />
                          </div>
                          <div className="field">
                            <Label>Correction notes <span className="optional">(optional)</span></Label>
                            <textarea
                              rows={2}
                              value={correctionDraft.notes}
                              onChange={(e) => setCorrectionDraft((current) => current ? { ...current, notes: e.target.value } : current)}
                              placeholder="Reason or reference for this correction"
                            />
                          </div>
                          <button
                            className="primary-button"
                            disabled={
                              busy !== null
                              || (correctionDraft.cc === visibleSummary.chief_complaint
                                  && correctionDraft.hpi === visibleSummary.history_of_present_illness)
                            }
                            onClick={() => correctSummaryAction(visibleSummary.summary_id)}
                          >
                            {busy === `correct-summary-${visibleSummary.summary_id}` ? <LoaderCircle className="spin" size={16} /> : <ClipboardList size={16} />}
                            Apply correction and reset review
                          </button>
                        </>
                      )}
                    </>
                  )}
                </section>
                <section className="card span-two"><div className="card-heading"><div className="icon-chip"><FileText size={18} /></div><div><h2>Linked source documents</h2><p>Inspect provenance before reviewing the summary.</p></div><button className="text-button" onClick={() => setTab('records')}>Open records</button></div>{documents.length ? documents.map((doc) => <div className="document-row" key={doc.id}><div className="document-icon"><FileText size={18} /></div><div className="document-info"><strong>{doc.filename || doc.id}</strong><span>{doc.extraction_method || 'Extraction'}</span><code>{doc.id}</code></div><StatusPill tone={processingTone(doc.processing_status)}>{doc.processing_status || 'unknown'}</StatusPill><StatusPill tone={verificationTone(doc.verification_status)}>{doc.verification_status || 'unverified'}</StatusPill><button className="secondary-button small" onClick={() => getDocument(doc.id)} disabled={busy !== null}>Inspect</button></div>) : <div className="empty-state compact">No linked documents loaded. Refresh the workspace or use Documents & records.</div>}</section>
              </div>
            </div>}
          </>
        )}

        <footer className="app-footer"><span>© Nurse Amma · Academic prototype</span><span><span className={`dot ${apiState}`} /> {API_BASE}</span><span>Clinical content is not a diagnosis. Human review is required.</span></footer>
      </main>
    </div>
  );
}