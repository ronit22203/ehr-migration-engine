import type { BatchResponse, PageDetail, TimelineResponse } from './types'

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || response.statusText)
  }
  return response.json() as Promise<T>
}

export function fetchBatch(): Promise<BatchResponse> {
  return getJson('/api/batch')
}

export function fetchPage(stem: string, fieldPath?: string | null): Promise<PageDetail> {
  const params = new URLSearchParams()
  if (fieldPath) params.set('field_path', fieldPath)
  const query = params.toString()
  return getJson(`/api/pages/${encodeURIComponent(stem)}${query ? `?${query}` : ''}`)
}

export function sourcePngUrl(stem: string, fieldPath?: string | null): string {
  const params = new URLSearchParams()
  if (fieldPath) params.set('field_path', fieldPath)
  const query = params.toString()
  return `/api/pages/${encodeURIComponent(stem)}/source.png${query ? `?${query}` : ''}`
}

export function fetchOcr(stem: string, fieldPath?: string | null) {
  const params = new URLSearchParams()
  if (fieldPath) params.set('field_path', fieldPath)
  const query = params.toString()
  return getJson<{
    available: boolean
    matched_block: number | null
    blocks: Array<{ index: number; matched: boolean; text: string }>
    parsed_text: string
  }>(`/api/pages/${encodeURIComponent(stem)}/ocr${query ? `?${query}` : ''}`)
}

export function fetchClinical(stem: string) {
  return getJson<{
    available: boolean
    path: string | null
    data: unknown
    error: unknown
  }>(`/api/pages/${encodeURIComponent(stem)}/clinical`)
}

export function fetchFhir(stem: string) {
  return getJson<{
    available: boolean
    path: string | null
    bundle: unknown
    summary: string | null
    count: number
    type: string | null
  }>(`/api/pages/${encodeURIComponent(stem)}/fhir`)
}

export function fetchTimeline(name: string): Promise<TimelineResponse> {
  return getJson(`/api/patients/${encodeURIComponent(name)}/timeline`)
}

export async function postReview(
  stem: string,
  body: {
    field_path: string
    status: 'accepted' | 'rejected' | 'corrected'
    revised_value?: string
    reason?: string
    code_system?: string
    code?: string
    display?: string
  },
) {
  const response = await fetch(`/api/pages/${encodeURIComponent(stem)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let message = response.statusText
    try {
      const payload = await response.json()
      if (payload?.detail) message = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
    } catch {
      /* keep status text */
    }
    throw new Error(message)
  }
  return response.json()
}
