import { Collapse, HTMLTable } from '@blueprintjs/core'
import { useState } from 'react'
import type { BatchResponse } from '../types'

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

export function PipelineConsole({ batch }: { batch: BatchResponse }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="wb-console">
      <button type="button" className="wb-console-toggle" onClick={() => setOpen((value) => !value)}>
        Pipeline console
      </button>
      <Collapse isOpen={open}>
        <div className="wb-console-body">
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
