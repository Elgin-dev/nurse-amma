import { describe, expect, it } from 'vitest';
import { createInFlightGuard } from './historyPayload';
import {
  belongsToConsultation,
  canStartExclusiveAction,
  confirmDraftSummary,
  dashboardTargetId,
  documentRowCaption,
  documentVerifyOptions,
  emptyWorkspace,
  isMissingHistoryMessage,
  isMissingSummaryMessage,
  parseDashboardDocuments,
  parseDraftSummary,
  parseTimelineEvents,
  redFlagAbsenceNote,
  redFlagReviewOptions,
  shouldReplaceWorkspace,
  sourceLabel,
  stripSummaryPrefix,
  summaryReviewOptions,
  verificationLabel,
} from './dashboardData';

const summaryFixture = {
  summary_id: 'SUM-aaaa',
  consultation_id: 'consult-1',
  chief_complaint: 'fever',
  history_of_present_illness: 'Patient reports fever for 4 days.',
  past_medical_history: ['asthma'],
  medication_history: [
    { name: 'Medication A', source_type: 'patient_reported', status: 'unverified' },
  ],
  allergies: [],
  investigation_history: [],
  red_flags: [
    {
      id: 'flag-1',
      flag_id: 'RF-001',
      severity: 'high',
      trigger: 'Fever >= 3 days with cognitive/sensory alteration',
      action_required: 'Immediate urgent triage and clinician evaluation required.',
      review_status: 'pending_review',
    },
  ],
  review_status: 'pending_doctor_approval',
};

describe('dashboard data loading helpers', () => {
  it('loads a real consultation target and seeds an empty workspace while fetching', () => {
    expect(dashboardTargetId('  consult-1  ', 'stale')).toBe('consult-1');
    expect(dashboardTargetId('', 'consult-2')).toBe('consult-2');
    expect(dashboardTargetId('', '')).toBe('');
    const loading = emptyWorkspace('consult-1');
    expect(loading.loadState).toBe('loading');
    expect(loading.consultation).toBeNull();
    expect(loading.summary).toBeNull();
    expect(loading.documents).toEqual([]);
    expect(loading.timeline).toEqual([]);
    expect(loading.timelineState).toBe('idle');
  });

  it('maps a missing summary to an empty state rather than a fabricated draft', () => {
    expect(isMissingSummaryMessage('No saved clinical summary found')).toBe(true);
    expect(isMissingHistoryMessage('No saved clinical history submission found')).toBe(true);
    expect(parseDraftSummary(null)).toBeNull();
    expect(parseDraftSummary({ chief_complaint: 'fever' })).toBeNull();
  });

  it('surfaces consultation and summary request failures without inventing records', () => {
    expect(parseDraftSummary({ detail: 'Consultation not found' })).toBeNull();
    expect(() => confirmDraftSummary(500, summaryFixture)).toThrow(/did not confirm/);
    expect(canStartExclusiveAction('dashboard-consultation')).toBe(false);
    expect(canStartExclusiveAction(null)).toBe(true);
  });
});

describe('draft summary parsing', () => {
  it('parses GET/POST summary payloads using the real response fields', () => {
    const parsed = parseDraftSummary(summaryFixture);
    expect(parsed).toMatchObject({
      summary_id: 'SUM-aaaa',
      consultation_id: 'consult-1',
      chief_complaint: 'fever',
      review_status: 'pending_doctor_approval',
    });
    expect(parsed?.red_flags).toHaveLength(1);
    expect(parsed?.red_flags[0].id).toBe('flag-1');
    expect(parsed?.medication_history[0]).toEqual({
      name: 'Medication A',
      source_type: 'patient_reported',
      status: 'unverified',
    });
    expect(confirmDraftSummary(200, summaryFixture).summary_id).toBe('SUM-aaaa');
  });

  it('parses persisted reviewer metadata on summary and red flags', () => {
    const withReview = {
      ...summaryFixture,
      review_status: 'approved',
      reviewed_by_user_id: 'user-1',
      reviewed_at: '2026-10-26T10:00:00Z',
      review_notes: 'Reviewed',
      corrected_by_user_id: 'user-2',
      corrected_at: '2026-10-26T09:00:00Z',
      red_flags: [
        {
          ...summaryFixture.red_flags[0],
          review_status: 'acknowledged',
          reviewed_by_user_id: 'user-1',
          reviewed_at: '2026-10-26T10:05:00Z',
          review_notes: 'Acknowledged',
        },
      ],
    };
    const parsed = parseDraftSummary(withReview);
    expect(parsed?.reviewed_by_user_id).toBe('user-1');
    expect(parsed?.reviewed_at).toBe('2026-10-26T10:00:00Z');
    expect(parsed?.review_notes).toBe('Reviewed');
    expect(parsed?.corrected_by_user_id).toBe('user-2');
    expect(parsed?.corrected_at).toBe('2026-10-26T09:00:00Z');
    expect(parsed?.red_flags[0].reviewed_by_user_id).toBe('user-1');
    expect(parsed?.red_flags[0].reviewed_at).toBe('2026-10-26T10:05:00Z');
    expect(parsed?.red_flags[0].review_notes).toBe('Acknowledged');
  });

  it('does not treat a failed POST as a successful generation', () => {
    expect(() => confirmDraftSummary(200, { summary_id: 'x' })).toThrow(/recognizable/);
    expect(() => confirmDraftSummary(422, { detail: 'Field required' })).toThrow(/did not confirm/);
  });
});

describe('duplicate summary submissions', () => {
  it('ignores a second generate request while the first is pending', async () => {
    const guard = createInFlightGuard();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    const first = guard.run(async () => {
      await gate;
      return confirmDraftSummary(200, summaryFixture);
    });
    const second = guard.run(async () => confirmDraftSummary(200, { ...summaryFixture, summary_id: 'SUM-bbbb' }));
    expect(await second).toBeUndefined();
    release();
    expect((await first)?.summary_id).toBe('SUM-aaaa');
  });
});

describe('source, red-flag, and verification display', () => {
  it('labels sources and never upgrades unverified or pending review to clinician-verified', () => {
    expect(sourceLabel('patient_reported')).toBe('Patient-reported');
    expect(sourceLabel('document_extracted')).toBe('Document-extracted');
    expect(sourceLabel('draft_summary')).toBe('Generated clinical summary');
    expect(verificationLabel('unverified')).toEqual({ text: 'unverified', tone: 'warn', verified: false });
    expect(verificationLabel('pending_doctor_approval').verified).toBe(false);
    expect(verificationLabel('approved').verified).toBe(true);
    expect(verificationLabel('rejected').tone).toBe('bad');
    expect(verificationLabel('verified')).toEqual({ text: 'Clinician-verified', tone: 'good', verified: true });
  });

  it('shows backend red flags when present and does not imply safety when none match', () => {
    const parsed = parseDraftSummary(summaryFixture);
    expect(parsed?.red_flags[0].flag_id).toBe('RF-001');
    expect(redFlagAbsenceNote(parsed?.red_flags || [])).toMatch(/pending clinical review/);
    expect(redFlagAbsenceNote([])).toMatch(/not a determination that the patient is medically safe/);
  });
});

describe('document list and consultation switching', () => {
  it('renders processing and failed document states from API metadata', () => {
    const docs = parseDashboardDocuments({
      documents: [
        { id: 'd1', filename: 'labs.pdf', processing_status: 'completed', verification_status: 'unverified', consultation_id: 'consult-1' },
        { id: 'd2', filename: 'scan.png', processing_status: 'failed', error_message: 'Unable to process', consultation_id: 'consult-1' },
        { id: 'd3', filename: 'other.pdf', processing_status: 'completed', consultation_id: 'consult-other' },
        { filename: 'missing-id.pdf' },
      ],
    }, 'consult-1');
    expect(docs.map((doc) => doc.id)).toEqual(['d1', 'd2']);
    expect(documentRowCaption(docs[0])).toMatch(/unverified/);
    expect(documentRowCaption(docs[1])).toMatch(/failed/);
  });

  it('parses document verification metadata from the API', () => {
    const docs = parseDashboardDocuments({
      documents: [{
        id: 'd1',
        filename: 'labs.pdf',
        processing_status: 'completed',
        verification_status: 'verified',
        verified_by_user_id: 'user-1',
        verified_at: '2026-10-26T10:00:00Z',
        verification_notes: 'Reviewed',
        consultation_id: 'consult-1',
      }],
    }, 'consult-1');
    expect(docs[0].verified_by_user_id).toBe('user-1');
    expect(docs[0].verified_at).toBe('2026-10-26T10:00:00Z');
    expect(docs[0].verification_notes).toBe('Reviewed');
  });

  it('drops stale workspace results from a previous consultation request', () => {
    const current = { ...emptyWorkspace('consult-old'), loadState: 'ready' as const };
    expect(shouldReplaceWorkspace(current, 'consult-new', 1, 2)).toBe(false);
    expect(shouldReplaceWorkspace(current, 'consult-new', 2, 2)).toBe(true);
    expect(belongsToConsultation('consult-1', 'consult-1')).toBe(true);
    expect(belongsToConsultation('consult-1', 'consult-2')).toBe(false);
  });
});

describe('timeline parsing', () => {
  it('parses only well-formed timeline events', () => {
    const events = parseTimelineEvents({
      consultation_id: 'consult-1',
      events: [
        {
          event_id: 'history:abc',
          event_type: 'clinical_history_submitted',
          occurred_at: '2026-10-26T10:00:00Z',
          title: 'Clinical history v1 submitted',
          source: 'patient_reported',
          status: 'unverified',
          metadata: { version: 1 },
        },
        { event_id: 'bad' },
        null,
        'not-an-event',
      ],
    });
    expect(events).toHaveLength(1);
    expect(events[0].event_id).toBe('history:abc');
    expect(events[0].source).toBe('patient_reported');
    expect(events[0].status).toBe('unverified');
    expect(events[0].metadata).toEqual({ version: 1 });
  });

  it('returns an empty list for a missing or invalid timeline', () => {
    expect(parseTimelineEvents(null)).toEqual([]);
    expect(parseTimelineEvents({ detail: 'Consultation not found' })).toEqual([]);
    expect(parseTimelineEvents({ events: [] })).toEqual([]);
    expect(parseTimelineEvents({ events: 'not-array' })).toEqual([]);
  });
});

describe('review action helpers', () => {
  it('strips the SUM- prefix to produce the database UUID', () => {
    expect(stripSummaryPrefix('SUM-abc-123')).toBe('abc-123');
    expect(stripSummaryPrefix('abc-123')).toBe('abc-123');
    expect(stripSummaryPrefix('')).toBe('');
  });

  it('exposes only the allowed summary review transitions', () => {
    expect(summaryReviewOptions('pending_doctor_approval')).toEqual(['approved', 'rejected', 'needs_correction']);
    expect(summaryReviewOptions('needs_correction')).toEqual(['approved', 'rejected']);
    expect(summaryReviewOptions('approved')).toEqual([]);
    expect(summaryReviewOptions('rejected')).toEqual([]);
    expect(summaryReviewOptions('unknown')).toEqual([]);
  });

  it('exposes only the allowed red-flag review transitions', () => {
    expect(redFlagReviewOptions('pending_review')).toEqual(['acknowledged', 'verified', 'dismissed', 'corrected']);
    expect(redFlagReviewOptions('acknowledged')).toEqual(['verified', 'dismissed', 'corrected']);
    expect(redFlagReviewOptions('verified')).toEqual([]);
    expect(redFlagReviewOptions('dismissed')).toEqual([]);
    expect(redFlagReviewOptions('corrected')).toEqual([]);
  });

  it('exposes only the allowed document verification transitions', () => {
    expect(documentVerifyOptions('unverified')).toEqual(['verified', 'rejected']);
    expect(documentVerifyOptions('verified')).toEqual([]);
    expect(documentVerifyOptions('rejected')).toEqual([]);
    expect(documentVerifyOptions('')).toEqual([]);
  });
});