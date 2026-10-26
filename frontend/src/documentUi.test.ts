import { describe, expect, it } from 'vitest';
import {
  asDocumentList,
  describeUploadResult,
  MAX_DOCUMENT_BYTES,
  processingTone,
  validateDocumentFile,
  verificationTone,
} from './documentUi';

describe('validateDocumentFile', () => {
  it('accepts a supported PDF under the backend size limit', () => {
    expect(validateDocumentFile(
      { name: 'synthetic-report.pdf', size: 1024 },
      '11111111-1111-1111-1111-111111111111',
    )).toBeNull();
  });

  it('rejects missing consultation, empty files, oversized files, and unsupported types', () => {
    expect(validateDocumentFile({ name: 'report.pdf', size: 10 }, '')).toMatch(/consultation/i);
    expect(validateDocumentFile(null, 'cid')).toMatch(/choose/i);
    expect(validateDocumentFile({ name: 'notes.txt', size: 10 }, 'cid')).toMatch(/PDF, PNG, JPG/i);
    expect(validateDocumentFile({ name: 'empty.pdf', size: 0 }, 'cid')).toMatch(/empty/i);
    expect(validateDocumentFile({ name: 'huge.pdf', size: MAX_DOCUMENT_BYTES + 1 }, 'cid')).toMatch(/10 MB/i);
  });
});

describe('describeUploadResult', () => {
  it('does not treat upload success as clinician-verified extraction', () => {
    const completed = describeUploadResult({
      id: 'doc-1',
      processing_status: 'completed',
      verification_status: 'unverified',
      text: 'Hemoglobin: 13.2 g/dL',
    });
    expect(completed).toMatch(/doc-1/);
    expect(completed).toMatch(/completed/);
    expect(completed.toLowerCase()).toMatch(/unverified/);

    expect(describeUploadResult({ id: 'doc-2', processing_status: 'processing' })).toMatch(/still processing/);
    expect(describeUploadResult({ id: 'doc-3', processing_status: 'failed', error_message: 'Unable to process' })).toMatch(/failed/);
    expect(describeUploadResult({ id: 'doc-4', processing_status: 'completed', text: '' })).toMatch(/No extracted text/);
  });
});

describe('document status mapping', () => {
  it('maps processing and verification states without implying a completed review', () => {
    expect(processingTone('completed')).toBe('good');
    expect(processingTone('failed')).toBe('bad');
    expect(processingTone('processing')).toBe('warn');
    expect(verificationTone('unverified')).toBe('warn');
    expect(verificationTone(undefined)).toBe('warn');
  });

  it('reads documents from either a raw array or the consultation list payload', () => {
    expect(asDocumentList({ documents: [{ id: 'a' }, null] })).toEqual([{ id: 'a' }]);
    expect(asDocumentList([])).toEqual([]);
    expect(asDocumentList(null)).toEqual([]);
  });
});
