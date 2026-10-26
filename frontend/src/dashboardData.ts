import { asDocumentList, processingTone, verificationTone, type StatusTone } from './documentUi';

export interface MedicationHistoryItem {
  name: string;
  source_type?: string;
  status?: string;
}

export interface RedFlagView {
  id?: string;
  flag_id: string;
  severity: string;
  trigger: string;
  action_required: string;
  review_status: string;
  reviewed_by_user_id?: string;
  reviewed_at?: string;
  review_notes?: string;
}

export interface DraftSummary {
  summary_id: string;
  consultation_id: string;
  chief_complaint: string;
  history_of_present_illness: string;
  past_medical_history: string[];
  medication_history: MedicationHistoryItem[];
  allergies: string[];
  investigation_history: unknown[];
  red_flags: RedFlagView[];
  review_status: string;
  reviewed_by_user_id?: string;
  reviewed_at?: string;
  review_notes?: string;
  corrected_by_user_id?: string;
  corrected_at?: string;
}

export type SummaryViewState = 'idle' | 'missing' | 'loaded' | 'error';
export type WorkspaceLoadState = 'idle' | 'loading' | 'ready' | 'error';
export type TimelineViewState = 'idle' | 'loading' | 'loaded' | 'error';

export interface TimelineEventView {
  event_id: string;
  event_type: string;
  occurred_at: string;
  title: string;
  description?: string;
  source: string;
  status: string;
  related_entity_id?: string;
  related_entity_type?: string;
  metadata: Record<string, unknown>;
}

export interface DashboardDocument {
  id: string;
  filename?: string;
  processing_status?: string;
  verification_status?: string;
  page_count?: number;
  extraction_method?: string;
  created_at?: string;
  error_message?: string | null;
  consultation_id?: string;
  verified_by_user_id?: string;
  verified_at?: string;
  verification_notes?: string;
}

export interface DashboardWorkspace {
  consultationId: string;
  loadState: WorkspaceLoadState;
  consultation: {
    id: string;
    patient_id: string;
    language?: string;
    status?: string;
    created_at?: string;
    completed_at?: string | null;
  } | null;
  patient: {
    id: string;
    full_name?: string;
    date_of_birth?: string | null;
    created_at?: string;
  } | null;
  summary: DraftSummary | null;
  summaryState: SummaryViewState;
  documents: DashboardDocument[];
  timeline: TimelineEventView[];
  timelineState: TimelineViewState;
  patientError?: string;
  summaryError?: string;
  documentsError?: string;
  timelineError?: string;
  error?: string;
}

export function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string');
}

export function belongsToConsultation(recordId: string | undefined | null, requestedId: string): boolean {
  return Boolean(recordId && requestedId && recordId === requestedId);
}

export function isMissingSummaryMessage(message: string): boolean {
  return message.toLowerCase().includes('no saved clinical summary');
}

export function isMissingHistoryMessage(message: string): boolean {
  return message.toLowerCase().includes('no saved clinical history submission');
}

export function parseRedFlags(value: unknown): RedFlagView[] {
  if (!Array.isArray(value)) return [];
  const flags: RedFlagView[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') continue;
    const row = item as Record<string, unknown>;
    if (typeof row.flag_id !== 'string' || !row.flag_id.trim()) continue;
    flags.push({
      ...(typeof row.id === 'string' && row.id.trim() ? { id: row.id } : {}),
      flag_id: row.flag_id,
      severity: typeof row.severity === 'string' ? row.severity : 'unspecified',
      trigger: typeof row.trigger === 'string' ? row.trigger : '',
      action_required: typeof row.action_required === 'string' ? row.action_required : '',
      review_status: typeof row.review_status === 'string' ? row.review_status : 'pending_review',
      ...(typeof row.reviewed_by_user_id === 'string' ? { reviewed_by_user_id: row.reviewed_by_user_id } : {}),
      ...(typeof row.reviewed_at === 'string' ? { reviewed_at: row.reviewed_at } : {}),
      ...(typeof row.review_notes === 'string' ? { review_notes: row.review_notes } : {}),
    });
  }
  return flags;
}

export function parseMedicationHistory(value: unknown): MedicationHistoryItem[] {
  if (!Array.isArray(value)) return [];
  const items: MedicationHistoryItem[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') continue;
    const row = item as Record<string, unknown>;
    const name = typeof row.name === 'string' ? row.name : '';
    if (!name) continue;
    items.push({
      name,
      source_type: typeof row.source_type === 'string' ? row.source_type : undefined,
      status: typeof row.status === 'string' ? row.status : undefined,
    });
  }
  return items;
}

export function parseDraftSummary(data: unknown): DraftSummary | null {
  if (!data || typeof data !== 'object') return null;
  const row = data as Record<string, unknown>;
  if (typeof row.summary_id !== 'string' || !row.summary_id.trim()) return null;
  if (typeof row.consultation_id !== 'string' || !row.consultation_id.trim()) return null;
  if (typeof row.chief_complaint !== 'string') return null;
  return {
    summary_id: row.summary_id,
    consultation_id: row.consultation_id,
    chief_complaint: row.chief_complaint,
    history_of_present_illness: typeof row.history_of_present_illness === 'string' ? row.history_of_present_illness : '',
    past_medical_history: asStringList(row.past_medical_history),
    medication_history: parseMedicationHistory(row.medication_history),
    allergies: asStringList(row.allergies),
    investigation_history: Array.isArray(row.investigation_history) ? row.investigation_history : [],
    red_flags: parseRedFlags(row.red_flags),
    review_status: typeof row.review_status === 'string' ? row.review_status : 'pending_doctor_approval',
    ...(typeof row.reviewed_by_user_id === 'string' ? { reviewed_by_user_id: row.reviewed_by_user_id } : {}),
    ...(typeof row.reviewed_at === 'string' ? { reviewed_at: row.reviewed_at } : {}),
    ...(typeof row.review_notes === 'string' ? { review_notes: row.review_notes } : {}),
    ...(typeof row.corrected_by_user_id === 'string' ? { corrected_by_user_id: row.corrected_by_user_id } : {}),
    ...(typeof row.corrected_at === 'string' ? { corrected_at: row.corrected_at } : {}),
  };
}

export function parseTimelineEvents(value: unknown): TimelineEventView[] {
  if (!value || typeof value !== 'object') return [];
  const row = value as Record<string, unknown>;
  if (!Array.isArray(row.events)) return [];

  const events: TimelineEventView[] = [];
  for (const item of row.events) {
    if (!item || typeof item !== 'object') continue;
    const event = item as Record<string, unknown>;
    if (typeof event.event_id !== 'string' || !event.event_id.trim()) continue;
    if (typeof event.event_type !== 'string' || !event.event_type.trim()) continue;
    if (typeof event.occurred_at !== 'string' || !event.occurred_at.trim()) continue;
    if (typeof event.title !== 'string' || !event.title.trim()) continue;
    if (typeof event.source !== 'string' || !event.source.trim()) continue;
    if (typeof event.status !== 'string' || !event.status.trim()) continue;

    events.push({
      event_id: event.event_id,
      event_type: event.event_type,
      occurred_at: event.occurred_at,
      title: event.title,
      ...(typeof event.description === 'string' ? { description: event.description } : {}),
      source: event.source,
      status: event.status,
      ...(typeof event.related_entity_id === 'string' ? { related_entity_id: event.related_entity_id } : {}),
      ...(typeof event.related_entity_type === 'string' ? { related_entity_type: event.related_entity_type } : {}),
      metadata: event.metadata && typeof event.metadata === 'object' && !Array.isArray(event.metadata)
        ? event.metadata as Record<string, unknown>
        : {},
    });
  }
  return events;
}

export function confirmDraftSummary(status: number, data: unknown): DraftSummary {
  if (status !== 200) {
    throw new Error('The server did not confirm that the draft summary was generated.');
  }
  const parsed = parseDraftSummary(data);
  if (!parsed) {
    throw new Error('The server did not return a recognizable draft summary.');
  }
  return parsed;
}

export function sourceLabel(source?: string | null): string {
  if (source === 'patient_reported') return 'Patient-reported';
  if (source === 'document' || source === 'document_extracted') return 'Document-extracted';
  if (source === 'generated_summary' || source === 'draft_summary') return 'Generated clinical summary';
  if (source === 'clinician_verified' || source === 'verified') return 'Clinician-verified';
  return source?.trim() ? source : 'Source not stated';
}

export function verificationLabel(status?: string | null): { text: string; tone: StatusTone; verified: boolean } {
  if (status === 'verified') return { text: 'Clinician-verified', tone: 'good', verified: true };
  if (status === 'approved') return { text: 'Approved', tone: 'good', verified: true };
  if (status === 'pending_doctor_approval' || status === 'pending_review') {
    return { text: status.replace(/_/g, ' '), tone: 'warn', verified: false };
  }
  if (status === 'rejected') return { text: 'Rejected', tone: 'bad', verified: false };
  if (status === 'unverified' || !status) return { text: 'unverified', tone: 'warn', verified: false };
  return { text: status.replace(/_/g, ' '), tone: 'warn', verified: false };
}

export function redFlagAbsenceNote(flags: RedFlagView[]): string {
  if (flags.length === 0) {
    return 'No red-flag rules matched this submission. That is not a determination that the patient is medically safe.';
  }
  return 'Red flags are generated from implemented backend rules and remain pending clinical review.';
}

export function emptyWorkspace(consultationId: string): DashboardWorkspace {
  return {
    consultationId,
    loadState: 'loading',
    consultation: null,
    patient: null,
    summary: null,
    summaryState: 'idle',
    documents: [],
    timeline: [],
    timelineState: 'idle',
  };
}

export function parseDashboardDocuments(value: unknown, consultationId: string): DashboardDocument[] {
  const documents: DashboardDocument[] = [];

  for (const candidate of asDocumentList(value)) {
    const row = candidate as Record<string, unknown>;
    const id = typeof row.id === 'string' ? row.id : '';
    if (!id) continue;

    const docConsultationId = typeof row.consultation_id === 'string' ? row.consultation_id : undefined;
    if (docConsultationId && !belongsToConsultation(docConsultationId, consultationId)) continue;

    const document: DashboardDocument = {
      id,
      ...(typeof row.filename === 'string' ? { filename: row.filename } : {}),
      ...(typeof row.processing_status === 'string' ? { processing_status: row.processing_status } : {}),
      ...(typeof row.verification_status === 'string' ? { verification_status: row.verification_status } : {}),
      ...(typeof row.page_count === 'number' ? { page_count: row.page_count } : {}),
      ...(typeof row.extraction_method === 'string' ? { extraction_method: row.extraction_method } : {}),
      ...(typeof row.created_at === 'string' ? { created_at: row.created_at } : {}),
      ...(typeof row.error_message === 'string' || row.error_message === null
        ? { error_message: row.error_message as string | null }
        : {}),
      ...(docConsultationId ? { consultation_id: docConsultationId } : {}),
      ...(typeof row.verified_by_user_id === 'string' ? { verified_by_user_id: row.verified_by_user_id } : {}),
      ...(typeof row.verified_at === 'string' ? { verified_at: row.verified_at } : {}),
      ...(typeof row.verification_notes === 'string' ? { verification_notes: row.verification_notes } : {}),
    };
    documents.push(document);
  }

  return documents;
}

export function documentRowCaption(doc: DashboardDocument): string {
  const processing = doc.processing_status || 'unknown';
  const verification = doc.verification_status || 'unverified';
  const extracted = processing === 'completed' ? (doc.extraction_method || 'extracted') : processing;
  return `${extracted} · ${verification}`;
}

export { processingTone, verificationTone };

export function shouldReplaceWorkspace(
  current: DashboardWorkspace | null,
  incomingConsultationId: string,
  requestSerial: number,
  currentSerial: number,
): boolean {
  if (requestSerial !== currentSerial) return false;
  if (current && current.consultationId !== incomingConsultationId && current.loadState === 'ready') {
    return requestSerial === currentSerial;
  }
  return true;
}

export function canStartExclusiveAction(busyKey: string | null): boolean {
  return busyKey === null;
}

export function dashboardTargetId(consultationIdInput: string, loadedConsultationId?: string): string {
  return consultationIdInput.trim() || loadedConsultationId?.trim() || '';
}

export function formatTimestamp(value?: string | null): string {
  if (!value) return '—';
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleString();
}

export function stripSummaryPrefix(summaryId: string): string {
  return summaryId.startsWith('SUM-') ? summaryId.slice(4) : summaryId;
}

export function summaryReviewOptions(currentStatus: string): string[] {
  if (currentStatus === 'pending_doctor_approval') return ['approved', 'rejected', 'needs_correction'];
  if (currentStatus === 'needs_correction') return ['approved', 'rejected'];
  return [];
}

export function redFlagReviewOptions(currentStatus: string): string[] {
  if (currentStatus === 'pending_review') return ['acknowledged', 'verified', 'dismissed', 'corrected'];
  if (currentStatus === 'acknowledged') return ['verified', 'dismissed', 'corrected'];
  return [];
}

export function documentVerifyOptions(currentStatus: string): string[] {
  if (currentStatus === 'unverified') return ['verified', 'rejected'];
  return [];
}