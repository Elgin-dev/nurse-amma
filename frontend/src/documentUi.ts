export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;
export const ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg'] as const;

export type StatusTone = 'good' | 'warn' | 'bad' | 'neutral';

export function fileExtension(filename: string): string {
  const name = filename.replace(/\\/g, '/').split('/').pop() || '';
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

export function validateDocumentFile(
  file: { name: string; size: number } | null,
  consultationId: string,
): string | null {
  if (!consultationId) return 'Create or load a consultation first.';
  if (!file) return 'Choose a synthetic PDF or image first.';
  const extension = fileExtension(file.name);
  if (!ALLOWED_DOCUMENT_EXTENSIONS.includes(extension as (typeof ALLOWED_DOCUMENT_EXTENSIONS)[number])) {
    return 'Only PDF, PNG, JPG, and JPEG files are supported.';
  }
  if (file.size <= 0) return 'Uploaded file is empty.';
  if (file.size > MAX_DOCUMENT_BYTES) return 'File size must not exceed 10 MB.';
  return null;
}

export function processingTone(status?: string | null): StatusTone {
  if (status === 'completed') return 'good';
  if (status === 'failed') return 'bad';
  if (status === 'processing') return 'warn';
  return 'warn';
}

export function verificationTone(status?: string | null): StatusTone {
  return status === 'verified' ? 'good' : 'warn';
}

export function describeUploadResult(doc: {
  id?: string;
  processing_status?: string;
  verification_status?: string;
  error_message?: string | null;
  text?: string;
}): string {
  const id = doc.id ? ` Document ID: ${doc.id}.` : '';
  const unverified = ' Extracted content remains unverified until a clinician reviews the original source.';
  const status = doc.processing_status || 'unknown';

  if (status === 'processing') {
    return `Document uploaded and is still processing.${id} Do not treat extraction as complete.`;
  }
  if (status === 'failed') {
    return `Document was stored but processing failed.${id}${doc.error_message ? ` ${doc.error_message}` : ''}`;
  }
  if (status === 'completed') {
    const empty = !doc.text?.trim() ? ' No extracted text was returned.' : '';
    return `Document stored. Extraction completed with status: completed.${id}${empty}${unverified}`;
  }
  return `Document request finished with status: ${status}.${id} Processing is not confirmed complete.${unverified}`;
}

export function asDocumentList(value: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(value)) {
    return value.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object');
  }
  if (value && typeof value === 'object' && Array.isArray((value as { documents?: unknown }).documents)) {
    return ((value as { documents: unknown[] }).documents).filter(
      (item): item is Record<string, unknown> => !!item && typeof item === 'object',
    );
  }
  return [];
}
