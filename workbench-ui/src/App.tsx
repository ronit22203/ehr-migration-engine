import { Callout, Classes, Radio, RadioGroup, Spinner } from '@blueprintjs/core'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchBatch, fetchPage } from './api'
import { Explorer } from './components/Explorer'
import { FhirView } from './components/FhirView'
import { Inspector } from './components/Inspector'
import { JsonView } from './components/JsonView'
import { OcrView } from './components/OcrView'
import { Overview } from './components/Overview'
import { PatientTimeline } from './components/PatientTimeline'
import { PipelineConsole } from './components/PipelineConsole'
import { SourceView } from './components/SourceView'
import { StageBar } from './components/StageBar'
import type { ArtifactView, BatchResponse, ExplorerFilter, PageDetail, Stage } from './types'

const STAGE_VIEW: Record<Stage, ArtifactView> = {
  Overview: 'Source',
  Ingestion: 'Source',
  OCR: 'OCR',
  Extraction: 'Clinical JSON',
  Normalization: 'Clinical JSON',
  'Patient Timeline': 'Source',
  FHIR: 'FHIR',
}

const VIEWER_STAGES = new Set<Stage>(['Ingestion', 'OCR', 'Extraction', 'Normalization', 'FHIR'])

function readParams() {
  const params = new URLSearchParams(window.location.search)
  return {
    stage: (params.get('stage') as Stage) || 'Overview',
    stem: params.get('stem'),
    field: params.get('field'),
    filter: (params.get('filter') as ExplorerFilter) || 'All',
    view: (params.get('view') as ArtifactView) || null,
  }
}

function writeParams(state: {
  stage: Stage
  stem: string | null
  field: string | null
  filter: ExplorerFilter
  view: ArtifactView
}) {
  const params = new URLSearchParams()
  params.set('stage', state.stage)
  params.set('filter', state.filter)
  params.set('view', state.view)
  if (state.stem) params.set('stem', state.stem)
  if (state.field) params.set('field', state.field)
  const next = `${window.location.pathname}?${params.toString()}`
  window.history.replaceState(null, '', next)
}

export default function App() {
  const initial = useMemo(() => readParams(), [])
  const [batch, setBatch] = useState<BatchResponse | null>(null)
  const [page, setPage] = useState<PageDetail | null>(null)
  const [stage, setStage] = useState<Stage>(initial.stage)
  const [stem, setStem] = useState<string | null>(initial.stem)
  const [field, setField] = useState<string | null>(initial.field)
  const [filter, setFilter] = useState<ExplorerFilter>(initial.filter)
  const [view, setView] = useState<ArtifactView>(initial.view || STAGE_VIEW[initial.stage])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reloadBatch = useCallback(async () => {
    const data = await fetchBatch()
    setBatch(data)
    if (!stem) {
      const first = data.packets.flatMap((packet) => packet.pages)[0]
      if (first) setStem(first.stem)
    }
  }, [stem])

  const reloadPage = useCallback(async () => {
    if (!stem) {
      setPage(null)
      return
    }
    const detail = await fetchPage(stem, field)
    setPage(detail)
  }, [stem, field])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    reloadBatch()
      .then(() => {
        if (!cancelled) setError(null)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [reloadBatch])

  useEffect(() => {
    let cancelled = false
    reloadPage()
      .then(() => {
        if (!cancelled) setError(null)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [reloadPage])

  useEffect(() => {
    writeParams({ stage, stem, field, filter, view })
  }, [stage, stem, field, filter, view])

  function changeStage(next: Stage) {
    setStage(next)
    setView(STAGE_VIEW[next])
  }

  function selectPage(next: string) {
    setStem(next)
    setField(null)
  }

  function selectField(next: string) {
    setField(next)
    if (stage === 'Overview' || stage === 'Patient Timeline') {
      setStage('OCR')
    }
    setView('Source')
  }

  const selectedFact = page?.facts.find((item) => item.field_path === field) ?? null

  return (
    <div className="wb-shell">
      <header className="wb-header">
        <div>
          <p className="wb-kicker">Migration workbench</p>
          <p className="wb-title">{batch?.batch_id || 'local-faxes'}</p>
        </div>
        <StageBar stage={stage} onChange={changeStage} />
      </header>

      {loading && !batch ? (
        <div className="wb-loading">
          <Spinner />
        </div>
      ) : error && !batch ? (
        <Callout intent="danger">{error}</Callout>
      ) : batch ? (
        <>
          <div className="wb-layout">
            <aside className="wb-left">
              <Explorer
                packets={batch.packets}
                filter={filter}
                selectedStem={stem}
                onFilter={setFilter}
                onSelect={selectPage}
              />
            </aside>
            <main className="wb-center">
              {stem ? (
                <p className="wb-meta">
                  {stem} · page {page?.page_number ?? '—'}
                </p>
              ) : null}
              {stage === 'Overview' ? (
                <Overview batch={batch} />
              ) : stage === 'Patient Timeline' ? (
                <PatientTimeline patientName={page?.patient_name ?? null} />
              ) : !stem ? (
                <p className={Classes.TEXT_MUTED}>Select a page in the explorer.</p>
              ) : (
                <>
                  {VIEWER_STAGES.has(stage) ? (
                    <RadioGroup
                      selectedValue={view}
                      onChange={(event) => setView(event.currentTarget.value as ArtifactView)}
                      inline
                    >
                      {(['Source', 'OCR', 'Clinical JSON', 'FHIR'] as ArtifactView[]).map((item) => (
                        <Radio key={item} label={item} value={item} />
                      ))}
                    </RadioGroup>
                  ) : null}
                  {page ? (
                    view === 'Source' ? (
                      <SourceView page={page} field={selectedFact} />
                    ) : view === 'OCR' ? (
                      <OcrView stem={stem} fieldPath={field} />
                    ) : view === 'Clinical JSON' ? (
                      <JsonView stem={stem} />
                    ) : (
                      <FhirView stem={stem} />
                    )
                  ) : (
                    <Spinner size={24} />
                  )}
                </>
              )}
            </main>
            <aside className="wb-right">
              <Inspector
                page={page}
                selectedField={field}
                onSelectField={selectField}
                onReviewed={async () => {
                  await reloadBatch()
                  await reloadPage()
                }}
              />
            </aside>
          </div>
          <PipelineConsole batch={batch} />
        </>
      ) : null}
    </div>
  )
}
