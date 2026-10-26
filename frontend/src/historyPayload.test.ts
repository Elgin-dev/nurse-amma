import { describe, expect, it } from 'vitest';
import {
  assignSchemaField,
  buildPatientResponsePayload,
  confirmPersistedSubmission,
  createInFlightGuard,
  parseJsonObject,
  validateHistorySave,
} from './historyPayload';

describe('buildPatientResponsePayload', () => {
  it('builds the Pydantic history fields from the form, including Q&A even if OpenAPI properties are missing', () => {
    const payload = buildPatientResponsePayload({
      consultationId: '11111111-1111-1111-1111-111111111111',
      chiefComplaint: 'fever',
      symptomDetails: { severity: 'moderate', duration: { value: 2, unit: 'days' } },
      associatedSymptoms: ['body pain'],
      pastMedicalHistory: [],
      currentMedications: ['Medication A'],
      allergies: [],
      questionKey: 'duration',
      questionText: 'How many days have you had the fever?',
      answerText: '1-2 days',
      schemaProperties: {},
    });

    expect(payload).toMatchObject({
      consultation_id: '11111111-1111-1111-1111-111111111111',
      chief_complaint: 'fever',
      symptom_details: { severity: 'moderate', duration: { value: 2, unit: 'days' } },
      associated_symptoms: ['body pain'],
      current_medications: ['Medication A'],
      question_key: 'duration',
      question_text: 'How many days have you had the fever?',
      answer_text: '1-2 days',
      source: 'patient_reported',
    });
  });

  it('does not invent clinical values when optional history fields are empty', () => {
    const payload = buildPatientResponsePayload({
      consultationId: '11111111-1111-1111-1111-111111111111',
      chiefComplaint: 'cough',
      symptomDetails: {},
      associatedSymptoms: [],
      pastMedicalHistory: [],
      currentMedications: [],
      allergies: [],
      schemaProperties: { consultation_id: {}, chief_complaint: {}, symptom_details: {} },
    });

    expect(payload.symptom_details).toEqual({});
    expect(payload.associated_symptoms).toEqual([]);
    expect(payload.question_key).toBeNull();
    expect(payload.answer_text).toBeNull();
    expect(payload.source).toBe('patient_reported');
  });
});

describe('assignSchemaField', () => {
  it('uses the OpenAPI property name when present and otherwise falls back to the canonical field', () => {
    const withSchema: Record<string, unknown> = {};
    assignSchemaField(withSchema, { answer_text: {} }, ['answer_text', 'answer'], 'Two days');
    expect(withSchema).toEqual({ answer_text: 'Two days' });

    const withoutSchema: Record<string, unknown> = {};
    assignSchemaField(withoutSchema, {}, ['answer_text', 'answer'], 'Two days');
    expect(withoutSchema).toEqual({ answer_text: 'Two days' });
  });
});

describe('validateHistorySave', () => {
  it('requires a consultation, chief complaint, and answer for an active follow-up question', () => {
    expect(validateHistorySave({
      consultationId: '',
      chiefComplaint: 'fever',
      answerText: 'Two days',
      hasQuestion: true,
      questionComplete: false,
    })).toMatch(/consultation/i);

    expect(validateHistorySave({
      consultationId: 'cid',
      chiefComplaint: '',
      answerText: 'Two days',
      hasQuestion: true,
      questionComplete: false,
    })).toMatch(/chief complaint/i);

    expect(validateHistorySave({
      consultationId: 'cid',
      chiefComplaint: 'fever',
      answerText: '   ',
      hasQuestion: true,
      questionComplete: false,
    })).toMatch(/answer/i);

    expect(validateHistorySave({
      consultationId: 'cid',
      chiefComplaint: 'fever',
      answerText: 'Two days',
      hasQuestion: true,
      questionComplete: false,
    })).toBeNull();
  });
});

describe('parseJsonObject', () => {
  it('rejects invalid JSON so a failed save cannot be treated as success', () => {
    expect(parseJsonObject('{').ok).toBe(false);
    expect(parseJsonObject('[]').ok).toBe(false);
    expect(parseJsonObject('{"chief_complaint":"fever"}')).toEqual({
      ok: true,
      value: { chief_complaint: 'fever' },
    });
  });
});

describe('confirmPersistedSubmission', () => {
  it('accepts only a server-confirmed submission with an id', () => {
    const saved = confirmPersistedSubmission(201, {
      id: 'sub-1',
      version: 1,
      payload: { answer_text: 'Two days' },
      verification_status: 'unverified',
      source: 'patient_reported',
    });
    expect(saved.id).toBe('sub-1');
    expect(saved.payload?.answer_text).toBe('Two days');
    expect(() => confirmPersistedSubmission(201, { version: 1 })).toThrow(/submission id/);
    expect(() => confirmPersistedSubmission(204, { id: 'sub-1' })).toThrow(/did not confirm/);
  });
});

describe('createInFlightGuard', () => {
  it('prevents a second submission while the first request is still pending', async () => {
    const guard = createInFlightGuard();
    let started = 0;
    let finished = 0;
    let release!: () => void;
    const pending = new Promise<void>((resolve) => { release = resolve; });

    const first = guard.run(async () => {
      started += 1;
      await pending;
      finished += 1;
      return 'saved';
    });
    const second = guard.run(async () => {
      started += 1;
      finished += 1;
      return 'duplicate';
    });

    expect(started).toBe(1);
    expect(await second).toBeUndefined();
    release();
    expect(await first).toBe('saved');
    expect(finished).toBe(1);
    expect(await guard.run(async () => 'later')).toBe('later');
  });
});
