import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatApiDetail, formatError, request } from './api';

describe('formatApiDetail', () => {
  it('turns FastAPI validation arrays into readable field errors', () => {
    expect(formatApiDetail('consultation_id in request body must match the URL')).toBe(
      'consultation_id in request body must match the URL',
    );
    expect(formatApiDetail([
      { loc: ['body', 'symptom_details'], msg: 'Field required', type: 'missing' },
      { loc: ['body', 'chief_complaint'], msg: 'Field required', type: 'missing' },
    ])).toBe('symptom_details: Field required chief_complaint: Field required');
  });
});

describe('formatError', () => {
  it('keeps Error messages and uses a fallback for unknown values', () => {
    expect(formatError(new Error('Cannot reach the API'))).toBe('Cannot reach the API');
    expect(formatError('nope')).toBe('An unexpected error occurred.');
  });
});

describe('request', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns JSON from a successful authenticated response', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options: RequestInit) => {
      const headers = new Headers(options.headers);
      expect(headers.get('Authorization')).toBe('Bearer test-token');
      expect(headers.get('Content-Type')).toBe('application/json');
      return new Response(JSON.stringify({ id: 'sub-1', version: 1 }), {
        status: 201,
        headers: { 'content-type': 'application/json' },
      });
    }));

    const result = await request('/api/v1/consultations/cid/responses', {
      method: 'POST',
      body: JSON.stringify({ chief_complaint: 'fever' }),
    }, 'test-token');

    expect(result.status).toBe(201);
    expect(result.data).toEqual({ id: 'sub-1', version: 1 });
  });

  it('surfaces API failures instead of treating them as success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ detail: [{ loc: ['body', 'consultation_id'], msg: 'Field required' }] }),
      { status: 422, headers: { 'content-type': 'application/json' } },
    )));

    await expect(request('/api/v1/consultations/cid/responses', { method: 'POST', body: '{}' })).rejects.toThrow(
      'consultation_id: Field required',
    );
  });

  it('does not force JSON content-type on multipart uploads', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options: RequestInit) => {
      const headers = new Headers(options.headers);
      expect(headers.get('Content-Type')).toBeNull();
      return new Response(JSON.stringify({ id: 'doc-1', processing_status: 'completed' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }));

    const form = new FormData();
    form.append('file', new Blob(['%PDF-'], { type: 'application/pdf' }), 'report.pdf');
    const result = await request('/api/v1/consultations/cid/documents', { method: 'POST', body: form }, 'token');
    expect(result.data).toEqual({ id: 'doc-1', processing_status: 'completed' });
  });
});
