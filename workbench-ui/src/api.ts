import type {
  BatchResponse,
  PageDetail,
  PipelineAction,
  PipelineJobStatus,
  TimelineResponse,
} from './types'

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || response.statusText)
  }
  return response.json() as Promise<T>
}

async function readError(response: Response): Promise<string> {
  let message = response.statusText
  try {
    const payload = await response.json()
    if (payload?.detail) {
      message = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
    }
  } catch {
    /* keep status text */
  }
  return message
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
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function uploadFax(file: File) {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch('/api/faxes', { method: 'POST', body: form })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<{
    ok: boolean
    fax: { stem: string; filename: string; bytes: number; cleared?: number }
  }>
}

export async function deleteFax(stem: string) {
  const response = await fetch(`/api/faxes/${encodeURIComponent(stem)}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function deleteAllFaxes() {
  const response = await fetch('/api/faxes', { method: 'DELETE' })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export function fetchPipelineActions(): Promise<{ actions: PipelineAction[] }> {
  return getJson('/api/pipeline/actions')
}

export function fetchPipelineStatus(): Promise<PipelineJobStatus> {
  return getJson('/api/pipeline/status')
}

export async function runPipelineAction(action: string): Promise<PipelineJobStatus> {
  const response = await fetch('/api/pipeline/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<PipelineJobStatus>
}

export async function killPipeline(): Promise<PipelineJobStatus> {
  const response = await fetch('/api/pipeline/kill', { method: 'POST' })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<PipelineJobStatus>
}
