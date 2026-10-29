export type Stage =
  | 'Overview'
  | 'Ingestion'
  | 'OCR'
  | 'Extraction'
  | 'Normalization'
  | 'Patient Timeline'
  | 'FHIR'

export type ArtifactView = 'Source' | 'OCR' | 'Clinical JSON' | 'FHIR'

export type ExplorerFilter = 'All' | 'Missing' | 'Pending' | 'Reviewed'

export interface PageSummary {
  stem: string
  page_number: number
  marker: string
  missing: boolean
  pending: boolean
  reviewed: boolean
  failed: boolean
  has_ocr: boolean
  has_structured: boolean
  has_error: boolean
  has_atomic: boolean
}

export interface PacketSummary {
  stem: string
  filename: string
  pages: PageSummary[]
}

export interface BatchResponse {
  batch_id: string
  counts: {
    packets: number
    pages: number
    ocr: number
    structured: number
    failures: number
    pending_facts: number
    accepted_facts: number
  }
  packets: PacketSummary[]
  coverage: Array<Record<string, string | number>>
  failures: Array<Record<string, string | number>>
  review_events: Array<Record<string, string>>
}

export interface FactPayload {
  field_path: string
  kind: string
  value: string
  requires_code: boolean
  dosage: string | null
  clinical_status: string | null
  result: string | null
  units: string | null
  flag: string | null
  label: string
  effective_value: string
  code_system_placeholder: string
  needs_code: boolean
  review: {
    status: string
    revised_value: string | null
    code_system: string | null
    code: string | null
    display: string | null
    reason: string | null
    timestamp: string
  } | null
  provenance: {
    resolved: boolean
    source_file: string | null
    page_number: number | null
    block_index: number | null
    reading_order: number | null
    block_text: string | null
    confidence: number | null
  } | null
}

export interface PageDetail {
  stem: string
  page_number: number
  packet_stem: string
  extraction: Record<string, unknown> | null
  error: Record<string, unknown> | null
  facts: FactPayload[]
  selected_field: string | null
  checks: Array<{ label: string; state: string }>
  has_atomic: boolean
  has_ocr: boolean
  has_fhir: boolean
  patient_name: string | null
}

export interface TimelineResponse {
  available: boolean
  patient_name: string
  pages: Array<{
    document: string
    conditions: Array<Record<string, unknown>>
    observations: Array<Record<string, unknown>>
    medications: Array<Record<string, unknown>>
  }>
  error: string | null
  hint: string | null
}
