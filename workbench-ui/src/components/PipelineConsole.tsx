import { Button, Callout, Collapse, HTMLTable, Spinner, Tag } from '@blueprintjs/core'
import { useCallback, useEffect, useState } from 'react'
import { fetchPipelineActions, fetchPipelineStatus, killPipeline, runPipelineAction } from '../api'
import type { BatchResponse, PipelineAction, PipelineJobStatus } from '../types'

function Table({ rows, title }: { rows: Array<Record<string, unknown>>; title: string }) {
  if (!rows.length) return <p className="wb-muted">No {title.toLowerCase()}.</p>
  const columns = Object.keys(rows[0])
  return (
    <HTMLTable striped compact bordered className="wb-table">
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column}>{column}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={`${title}-${index}`}>
            {columns.map((column) => (
              <td key={column}>{String(row[column] ?? '')}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </HTMLTable>
  )
}

const RUN_GROUP = [
  'data-run-raw',
  'triage-pdfs',
  'ocr',
  'parse',
  'extract',
  'normalize',
  'graph',
  'fhir',
]

const CLEAN_GROUP = ['clean-ocr', 'clean-extract', 'clean-normalize', 'clean']

export function PipelineConsole({
  batch,
  onPipelineFinished,
}: {
  batch: BatchResponse
  onPipelineFinished: () => Promise<void>
}) {
  const [open, setOpen] = useState(true)
  const [actions, setActions] = useState<PipelineAction[]>([])
  const [job, setJob] = useState<PipelineJobStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshStatus = useCallback(async () => {
    const status = await fetchPipelineStatus()
    setJob(status)
    return status
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchPipelineActions()
      .then((payload) => {
        if (!cancelled) setActions(payload.actions)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    refreshStatus().catch((err: Error) => {
      if (!cancelled) setError(err.message)
    })
    return () => {
      cancelled = true
    }
  }, [refreshStatus])

  useEffect(() => {
    if (job?.status !== 'running') return
    const timer = window.setInterval(() => {
      void refreshStatus()
        .then(async (status) => {
          if (status.status === 'succeeded' || status.status === 'failed' || status.status === 'cancelled') {
            await onPipelineFinished()
          }
        })
        .catch((err: Error) => setError(err.message))
    }, 1500)
    return () => window.clearInterval(timer)
  }, [job?.status, onPipelineFinished, refreshStatus])

  async function run(actionId: string) {
    setError(null)
    try {
      const status = await runPipelineAction(actionId)
      setJob(status)
      setOpen(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function kill() {
    setError(null)
    try {
      const status = await killPipeline()
      setJob(status)
      await onPipelineFinished()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const byId = Object.fromEntries(actions.map((action) => [action.id, action]))
  const running = job?.status === 'running'
  const statusIntent =
    job?.status === 'failed' || job?.status === 'cancelled'
      ? 'danger'
      : job?.status === 'succeeded'
        ? 'success'
        : 'primary'

  return (
    <div className="wb-console">
      <button type="button" className="wb-console-toggle" onClick={() => setOpen((value) => !value)}>
        Pipeline console
        {job?.status && job.status !== 'idle' ? (
          <Tag minimal className="wb-console-tag" intent={statusIntent}>
            {job.label || job.action} · {job.status}
          </Tag>
        ) : null}
      </button>
      <Collapse isOpen={open}>
        <div className="wb-console-body">
          <p className="wb-muted">Makefile targets</p>
          <div className="wb-pipeline-actions">
            {RUN_GROUP.map((id) => {
              const action = byId[id]
              if (!action) return null
              return (
                <Button
                  key={id}
                  small
                  disabled={running}
                  title={action.description}
                  text={action.label}
                  onClick={() => void run(id)}
                />
              )
            })}
            <Button
              small
              intent="danger"
              icon="stop"
              disabled={!running}
              title="Stop the running make job and pipeline workers (make kill-pipeline)"
              text="Kill pipeline"
              onClick={() => void kill()}
            />
          </div>
          <div className="wb-pipeline-actions">
            {CLEAN_GROUP.map((id) => {
              const action = byId[id]
              if (!action) return null
              return (
                <Button
                  key={id}
                  small
                  minimal
                  intent="warning"
                  disabled={running}
                  title={action.description}
                  text={action.label}
                  onClick={() => void run(id)}
                />
              )
            })}
          </div>
          {error ? <Callout intent="danger" className="wb-pipeline-callout">{error}</Callout> : null}
          {job && job.status !== 'idle' ? (
            <div className="wb-pipeline-log-wrap">
              <div className="wb-pipeline-log-head">
                <span>
                  {job.label} · {job.status}
                  {job.returncode != null ? ` · exit ${job.returncode}` : ''}
                </span>
                {running ? (
                  <div className="wb-pipeline-log-actions">
                    <Spinner size={16} />
                    <Button small intent="danger" icon="stop" text="Kill" onClick={() => void kill()} />
                  </div>
                ) : null}
              </div>
              <pre className="wb-pre wb-pre-tight wb-pipeline-log">{job.log || 'Waiting for output…'}</pre>
              {job.error ? <p className="wb-error">{job.error}</p> : null}
            </div>
          ) : null}
          <p className="wb-muted">Stage coverage</p>
          <Table rows={batch.coverage} title="Stage coverage" />
          <p className="wb-muted">Extraction failures</p>
          <Table rows={batch.failures} title="Extraction failures" />
          <p className="wb-muted">Review ledger</p>
          <Table rows={batch.review_events} title="Review actions" />
        </div>
      </Collapse>
    </div>
  )
}
