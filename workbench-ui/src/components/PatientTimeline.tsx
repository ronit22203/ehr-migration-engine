import { Callout, Classes, Code, HTMLTable, Spinner } from '@blueprintjs/core'
import { useEffect, useState } from 'react'
import { fetchTimeline } from '../api'
import type { TimelineResponse } from '../types'

function Section({
  title,
  rows,
  columns,
}: {
  title: string
  rows: Array<Record<string, unknown>>
  columns: string[]
}) {
  const cleaned = rows.filter((row) => columns.some((column) => row[column]))
  if (!cleaned.length) return null
  return (
    <div className="wb-timeline-section">
      <p className={Classes.TEXT_MUTED}>{title}</p>
      <HTMLTable striped compact bordered className="wb-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cleaned.map((row, index) => (
            <tr key={`${title}-${index}`}>
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </HTMLTable>
    </div>
  )
}

export function PatientTimeline({ patientName }: { patientName: string | null }) {
  const [loading, setLoading] = useState(false)
  const [payload, setPayload] = useState<TimelineResponse | null>(null)

  useEffect(() => {
    if (!patientName) {
      setPayload(null)
      return
    }
    let cancelled = false
    setLoading(true)
    fetchTimeline(patientName)
      .then((data) => {
        if (!cancelled) setPayload(data)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [patientName])

  if (!patientName) {
    return <p className={Classes.TEXT_MUTED}>This page has no patient name. Select a page that extracted one.</p>
  }
  if (loading) return <Spinner size={24} />
  if (!payload) return null
  if (!payload.available) {
    return (
      <Callout intent="warning" title={`Neo4j is not available. ${payload.error || ''}`}>
        <Code>{payload.hint || 'docker compose up -d && make graph'}</Code>
      </Callout>
    )
  }
  if (!payload.pages.length) {
    return (
      <Callout intent="warning" title="No documents for this patient are in the graph yet.">
        <Code>make graph</Code>
      </Callout>
    )
  }
  return (
    <div>
      <h3>Patient timeline</h3>
      <p className={Classes.TEXT_MUTED}>{payload.patient_name}</p>
      {payload.pages.map((page) => (
        <div key={page.document} className="wb-timeline-page">
          <strong>{page.document}</strong>
          <Section title="Condition" rows={page.conditions} columns={['raw', 'display', 'code', 'status']} />
          <Section
            title="Observation"
            rows={page.observations}
            columns={['raw', 'value', 'units', 'flag', 'code']}
          />
          <Section title="Medication" rows={page.medications} columns={['raw', 'display', 'dosage', 'code']} />
        </div>
      ))}
    </div>
  )
}
