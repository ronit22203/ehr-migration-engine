import { Callout, Classes, Code } from '@blueprintjs/core'
import { sourcePngUrl } from '../api'
import type { FactPayload, PageDetail } from '../types'

export function SourceView({ page, field }: { page: PageDetail; field: FactPayload | null }) {
  if (!page.has_atomic) {
    return (
      <Callout intent="warning" title="This page has not been split.">
        <Code>make triage-pdfs</Code>
      </Callout>
    )
  }
  const url = sourcePngUrl(page.stem, field?.field_path)
  const link = field?.provenance
  return (
    <div>
      <img className="wb-source" src={url} alt={page.stem} />
      {link?.resolved ? (
        <p className={Classes.TEXT_MUTED}>
          {link.source_file} · page {link.page_number} · block {link.block_index}
          {link.reading_order != null ? ` · reading order ${link.reading_order}` : ''}
        </p>
      ) : field ? (
        <p className={Classes.TEXT_MUTED}>Provenance is unresolved. No OCR block contains this value.</p>
      ) : null}
    </div>
  )
}
