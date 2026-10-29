import { Button, Callout, Classes, FormGroup, InputGroup } from '@blueprintjs/core'
import { useEffect, useState } from 'react'
import { postReview } from '../api'
import type { PageDetail } from '../types'

const OPEN = new Set(['Pending', 'Review', 'Unresolved'])

export function Inspector({
  page,
  selectedField,
  onSelectField,
  onReviewed,
}: {
  page: PageDetail | null
  selectedField: string | null
  onSelectField: (fieldPath: string) => void
  onReviewed: () => void
}) {
  const fact = page?.facts.find((item) => item.field_path === selectedField) ?? null
  const [revised, setRevised] = useState('')
  const [reason, setReason] = useState('')
  const [system, setSystem] = useState('')
  const [code, setCode] = useState('')
  const [display, setDisplay] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setRevised(fact?.effective_value || fact?.value || '')
    setReason('')
    setSystem('')
    setCode('')
    setDisplay('')
    setError(null)
  }, [fact?.field_path, fact?.effective_value, fact?.value])

  async function submit(status: 'accepted' | 'rejected' | 'corrected') {
    if (!page || !fact) return
    setBusy(true)
    setError(null)
    try {
      await postReview(page.stem, {
        field_path: fact.field_path,
        status,
        revised_value: revised,
        reason,
        code_system: system,
        code,
        display,
      })
      onReviewed()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  if (!page) {
    return (
      <div className="wb-pane">
        <p className="wb-kicker">Inspector</p>
        <p className={Classes.TEXT_MUTED}>No page selected.</p>
      </div>
    )
  }

  if (!page.extraction) {
    const openCount = page.checks.filter((row) => OPEN.has(row.state)).length
    return (
      <div className="wb-pane">
        <p className="wb-kicker">Inspector</p>
        <p className={Classes.TEXT_MUTED}>
          {page.checks.length} checks · {openCount} open
        </p>
        {page.checks.map((row) => (
          <div key={row.label} className="wb-check">
            <span>{row.label}</span>
            <span>{row.state}</span>
          </div>
        ))}
        {page.error ? (
          <>
            <p className={Classes.TEXT_MUTED}>
              {String(page.error.error_type || 'failed')} · {String(page.error.attempts || 0)} attempts
            </p>
            {typeof page.error.message === 'string' ? <p>{page.error.message}</p> : null}
          </>
        ) : (
          <Callout intent="warning">
            Schema validation has not run for this page.
            <br />
            <code>make extract</code>
          </Callout>
        )}
      </div>
    )
  }

  if (!page.facts.length) {
    return (
      <div className="wb-pane">
        <p className="wb-kicker">Inspector</p>
        <p className={Classes.TEXT_MUTED}>
          No demographics, conditions, medications, or lab observations were extracted.
        </p>
      </div>
    )
  }

  const openCount = page.checks.filter((row) => OPEN.has(row.state)).length

  return (
    <div className="wb-pane">
      <p className="wb-kicker">Inspector</p>
      {page.facts.map((item) => (
        <Button
          key={item.field_path}
          fill
          alignText="left"
          className="wb-page-button"
          intent={item.field_path === selectedField ? 'primary' : 'none'}
          text={item.label}
          onClick={() => onSelectField(item.field_path)}
        />
      ))}

      {!fact ? (
        <p className={Classes.TEXT_MUTED}>Select a record to inspect provenance and review it.</p>
      ) : (
        <>
          <p className={Classes.TEXT_MUTED}>{fact.kind}</p>
          <pre className="wb-pre wb-pre-tight">{fact.value}</pre>
          {fact.review?.status === 'corrected' && fact.review.revised_value ? (
            <>
              <p className={Classes.TEXT_MUTED}>Revised</p>
              <pre className="wb-pre wb-pre-tight">{fact.review.revised_value}</pre>
            </>
          ) : null}
          {fact.dosage ? <p className={Classes.TEXT_MUTED}>Dosage {fact.dosage}</p> : null}
          {fact.result ? (
            <p className={Classes.TEXT_MUTED}>
              Result {fact.units ? `${fact.result} ${fact.units}` : fact.result}
            </p>
          ) : null}
          {fact.flag ? <p className={Classes.TEXT_MUTED}>Flag {fact.flag}</p> : null}
          {fact.clinical_status ? (
            <p className={Classes.TEXT_MUTED}>Clinical status {fact.clinical_status}</p>
          ) : null}
          {fact.review?.code ? (
            <>
              <p className={Classes.TEXT_MUTED}>Code</p>
              <pre className="wb-pre wb-pre-tight">
                {[fact.review.code_system, fact.review.code, fact.review.display].filter(Boolean).join('  ')}
              </pre>
            </>
          ) : null}
          {fact.review?.reason ? <p className={Classes.TEXT_MUTED}>{fact.review.reason}</p> : null}
          {fact.review ? (
            <p className={Classes.TEXT_MUTED}>
              {fact.review.status} · {fact.review.timestamp}
            </p>
          ) : null}

          <h4>Provenance</h4>
          {fact.provenance?.resolved ? (
            <>
              <p className={Classes.TEXT_MUTED}>
                {fact.provenance.source_file} · page {fact.provenance.page_number} · block{' '}
                {fact.provenance.block_index}
              </p>
              {fact.provenance.block_text ? <p>{fact.provenance.block_text}</p> : null}
              {fact.provenance.confidence != null ? (
                <p className={Classes.TEXT_MUTED}>OCR confidence {fact.provenance.confidence.toFixed(2)}</p>
              ) : null}
            </>
          ) : (
            <p className={Classes.TEXT_MUTED}>Provenance is unresolved. No OCR block contains this value.</p>
          )}

          {fact.needs_code ? (
            <p className={Classes.TEXT_MUTED}>
              This value has no terminology code. It stays out of the FHIR preview until you attach a code and
              accept it.
            </p>
          ) : null}

          <p className={Classes.TEXT_MUTED}>
            {page.checks.length} checks · {openCount} open
          </p>
          {page.checks.map((row) => (
            <div key={row.label} className="wb-check">
              <span>{row.label}</span>
              <span>{row.state}</span>
            </div>
          ))}

          <FormGroup label="Revised value">
            <InputGroup value={revised} onChange={(event) => setRevised(event.target.value)} />
          </FormGroup>
          <FormGroup label="Reason">
            <InputGroup value={reason} onChange={(event) => setReason(event.target.value)} />
          </FormGroup>
          {fact.requires_code ? (
            <>
              <FormGroup label="Code system">
                <InputGroup
                  value={system}
                  placeholder={fact.code_system_placeholder}
                  onChange={(event) => setSystem(event.target.value)}
                />
              </FormGroup>
              <FormGroup label="Code">
                <InputGroup value={code} onChange={(event) => setCode(event.target.value)} />
              </FormGroup>
              <FormGroup label="Display">
                <InputGroup value={display} onChange={(event) => setDisplay(event.target.value)} />
              </FormGroup>
            </>
          ) : null}
          <div className="wb-review-actions">
            <Button intent="success" disabled={busy} onClick={() => submit('accepted')} text="Accept" fill />
            <Button intent="danger" disabled={busy} onClick={() => submit('rejected')} text="Reject" fill />
            <Button intent="warning" disabled={busy} onClick={() => submit('corrected')} text="Correct" fill />
          </div>
          {error ? <Callout intent="danger">{error}</Callout> : null}
        </>
      )}
    </div>
  )
}
