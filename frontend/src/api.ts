export type JsonObject = Record<string, unknown>;

export interface ApiResult<T = unknown> {
  data: T;
  status: number;
}

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export async function request<T = unknown>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<ApiResult<T>> {
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach the API at ${API_BASE}. Start the backend and verify the API URL.`);
  }

  const contentType = response.headers.get('content-type') || '';
  const body: unknown = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '');

  if (!response.ok) {
    let message = `Request failed (HTTP ${response.status}).`;
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      message = formatApiDetail((body as { detail: unknown }).detail) || message;
    } else if (typeof body === 'string' && body.trim()) {
      message = body;
    }
    throw new Error(message);
  }
  return { data: body as T, status: response.status };
}

export interface OpenApiDocument {
  paths: Record<string, Record<string, { requestBody?: { content?: Record<string, { schema?: Schema }> } }>>;
  components?: { schemas?: Record<string, Schema> };
}

export interface Schema {
  $ref?: string;
  type?: string;
  format?: string;
  title?: string;
  description?: string;
  enum?: unknown[];
  const?: unknown;
  nullable?: boolean;
  default?: unknown;
  required?: string[];
  properties?: Record<string, Schema>;
  items?: Schema;
  anyOf?: Schema[];
  oneOf?: Schema[];
  allOf?: Schema[];
}

function resolveSchema(schema: Schema, spec: OpenApiDocument, depth = 0): Schema {
  if (depth > 8) return schema;
  let current = schema;
  if (current.$ref) {
    const key = current.$ref.split('/').pop() || '';
    current = spec.components?.schemas?.[key] || {};
  }
  if (current.allOf?.length) {
    return current.allOf.reduce<Schema>((acc, part) => {
      const resolved = resolveSchema(part, spec, depth + 1);
      return { ...acc, ...resolved, properties: { ...(acc.properties || {}), ...(resolved.properties || {}) }, required: [...(acc.required || []), ...(resolved.required || [])] };
    }, current);
  }
  if (current.anyOf?.length) return resolveSchema(current.anyOf.find(s => s.type !== 'null') || current.anyOf[0], spec, depth + 1);
  if (current.oneOf?.length) return resolveSchema(current.oneOf[0], spec, depth + 1);
  if (current.properties) {
    const properties: Record<string, Schema> = {};
    for (const [name, prop] of Object.entries(current.properties)) properties[name] = resolveSchema(prop, spec, depth + 1);
    return { ...current, properties };
  }
  if (current.items) return { ...current, items: resolveSchema(current.items, spec, depth + 1) };
  return current;
}

function exampleValue(schema: Schema, spec: OpenApiDocument, depth = 0): unknown {
  if (depth > 6) return null;
  const s = resolveSchema(schema, spec);
  if (s.const !== undefined) return s.const;
  if (s.default !== undefined) return s.default;
  if (s.enum?.length) return s.enum[0];
  if (s.nullable) return null;
  if (s.type === 'object' || s.properties) {
    const result: JsonObject = {};
    const required = new Set(s.required || []);
    for (const [key, prop] of Object.entries(s.properties || {})) {
      if (required.has(key)) result[key] = exampleValue(prop, spec, depth + 1);
    }
    return result;
  }
  if (s.type === 'array') return [];
  if (s.type === 'boolean') return false;
  if (s.type === 'integer' || s.type === 'number') return 0;
  if (s.format === 'uuid') return '';
  if (s.format === 'date') return '';
  if (s.format === 'date-time') return '';
  if (s.type === 'string') return '';
  return null;
}

export function requestBodyTemplate(spec: OpenApiDocument | null, path: string, method: string): string {
  const schema = spec?.paths?.[path]?.[method.toLowerCase()]?.requestBody?.content?.['application/json']?.schema;
  if (!schema || !spec) return '{\n  \n}';
  const resolved = resolveSchema(schema, spec);
  const sample = exampleValue(resolved, spec);
  return JSON.stringify(sample && typeof sample === 'object' ? sample : {}, null, 2);
}

export function schemaProperties(spec: OpenApiDocument | null, path: string, method: string): Record<string, Schema> {
  if (!spec) return {};
  const schema = spec.paths?.[path]?.[method.toLowerCase()]?.requestBody?.content?.['application/json']?.schema;
  if (!schema) return {};
  return resolveSchema(schema, spec).properties || {};
}

export function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === 'string' && item.trim()) return item;
      if (item && typeof item === 'object' && 'msg' in item) {
        const loc = Array.isArray((item as { loc?: unknown }).loc)
          ? (item as { loc: unknown[] }).loc.filter((part) => part !== 'body' && part !== 'query').join('.')
          : '';
        const msg = String((item as { msg: unknown }).msg);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return '';
    }).filter(Boolean);
    return parts.length ? parts.join(' ') : null;
  }
  if (detail && typeof detail === 'object' && 'msg' in detail) {
    return String((detail as { msg: unknown }).msg);
  }
  return null;
}

export function formatError(error: unknown): string {
  return error instanceof Error ? error.message : 'An unexpected error occurred.';
}

export function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
