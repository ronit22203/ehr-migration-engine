import { HTMLTable } from '@blueprintjs/core'
import type { BatchResponse } from '../types'

export function Overview({ batch }: { batch: BatchResponse }) {
  const rows = [
    ['Packets', batch.counts.packets],
    ['Pages', batch.counts.pages],
    ['OCR artifacts', batch.counts.ocr],
    ['Clinical JSON', batch.counts.structured],
    ['Extraction failures', batch.counts.failures],
    ['Facts pending review', batch.counts.pending_facts],
    ['Facts accepted', batch.counts.accepted_facts],
  ]
  return (
    <div>
      <h3>Batch</h3>
      <p className="wb-muted">Counts come from files on disk and the review ledger.</p>
      <HTMLTable striped compact bordered className="wb-table">
        <thead>
          <tr>
            <th>measure</th>
            <th>count</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([measure, count]) => (
            <tr key={String(measure)}>
              <td>{measure}</td>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </HTMLTable>
    </div>
  )
}
