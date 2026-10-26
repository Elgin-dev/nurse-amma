export type JsonObject = Record<string, unknown>;

export type DurationUnit = 'hours' | 'days' | 'weeks' | 'months';

export interface SymptomDetails {
  duration?: { value: number; unit: DurationUnit } | null;
  severity?: string | null;
  progression?: string | null;
  location?: string | null;
}

const DURATION_UNITS: DurationUnit[] = ['hours', 'days', 'weeks', 'months'];

export function assignSchemaField(
  payload: JsonObject,
  schemaProperties: Record<string, unknown>,
  names: string[],
  value: unknown,
): void {
  if (value === undefined) return;
  const name = names.find((candidate) => candidate in schemaProperties) || names[0];
  payload[name] = value;
}

export function parseJsonObject(raw: string): { ok: true; value: JsonObject } | { ok: false; error: string } {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { ok: false, error: 'Response JSON must be an object matching the history request schema.' };
    }
    return { ok: true, value: parsed as JsonObject };
  } catch {
    return { ok: false, error: 'Response JSON is invalid. Correct it before saving, or prepare the payload again.' };
  }
}

export function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

export function csvToList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function asSymptomDetails(value: unknown): SymptomDetails {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const raw = value as JsonObject;
  const details: SymptomDetails = {};
  if (typeof raw.severity === 'string') details.severity = raw.severity;
  if (typeof raw.progression === 'string') details.progression = raw.progression;
  if (typeof raw.location === 'string') details.location = raw.location;
  if (raw.duration && typeof raw.duration === 'object' && !Array.isArray(raw.duration)) {
    const duration = raw.duration as JsonObject;
    const unit = duration.unit;
    const numericValue = duration.value;
    if (
      typeof numericValue === 'number' &&
      Number.isInteger(numericValue) &&
      numericValue > 0 &&
      typeof unit === 'string' &&
      DURATION_UNITS.includes(unit as DurationUnit)
    ) {
      details.duration = { value: numericValue, unit: unit as DurationUnit };
    }
  }
  return details;
}

export function buildPatientResponsePayload(input: {
  consultationId: string;
  chiefComplaint: string;
  symptomDetails: SymptomDetails;
  associatedSymptoms: string[];
  pastMedicalHistory: string[];
  currentMedications: string[];
  allergies: string[];
  questionKey?: string;
  questionText?: string;
  answerText?: string;
  schemaProperties?: Record<string, unknown>;
  existing?: JsonObject;
}): JsonObject {
  const props = input.schemaProperties || {};
  const payload: JsonObject = { ...(input.existing || {}) };
  const assign = (names: string[], value: unknown) => assignSchemaField(payload, props, names, value);

  assign(['consultation_id'], input.consultationId);
  assign(['chief_complaint'], input.chiefComplaint);
  assign(['symptom_details'], input.symptomDetails);
  assign(['associated_symptoms'], input.associatedSymptoms);
  assign(['past_medical_history'], input.pastMedicalHistory);
  assign(['current_medications'], input.currentMedications);
  assign(['allergies'], input.allergies);
  assign(['question_key', 'question_id', 'key'], input.questionKey || null);
  assign(['question_text', 'question'], input.questionText || null);
  assign(['answer_text', 'answer'], input.answerText || null);
  assign(['source'], 'patient_reported');
  return payload;
}

export function validateHistorySave(input: {
  consultationId: string;
  chiefComplaint: string;
  answerText: string;
  hasQuestion: boolean;
  questionComplete: boolean;
}): string | null {
  if (!input.consultationId) return 'Create or load a consultation first.';
  if (!input.chiefComplaint.trim()) return 'Enter the patient-reported chief complaint first.';
  if (input.hasQuestion && !input.questionComplete && !input.answerText.trim()) {
    return "Enter the patient's answer before saving.";
  }
  return null;
}

export function createInFlightGuard() {
  let inFlight = false;
  return {
    get busy() {
      return inFlight;
    },
    async run<T>(action: () => Promise<T>): Promise<T | undefined> {
      if (inFlight) return undefined;
      inFlight = true;
      try {
        return await action();
      } finally {
        inFlight = false;
      }
    },
  };
}

export function confirmPersistedSubmission(
  status: number,
  data: unknown,
): { id: string; version?: number; payload?: JsonObject; verification_status?: string; source?: string } {
  if (status !== 201 && status !== 200) {
    throw new Error('The server did not confirm that the response was saved.');
  }
  if (!data || typeof data !== 'object') {
    throw new Error('The server did not return a saved history submission.');
  }
  const record = data as JsonObject;
  const id = typeof record.id === 'string' ? record.id : '';
  if (!id) {
    throw new Error('The server response did not include a saved submission id.');
  }
  return {
    id,
    version: typeof record.version === 'number' ? record.version : undefined,
    payload: record.payload && typeof record.payload === 'object' && !Array.isArray(record.payload)
      ? record.payload as JsonObject
      : undefined,
    verification_status: typeof record.verification_status === 'string' ? record.verification_status : undefined,
    source: typeof record.source === 'string' ? record.source : undefined,
  };
}
