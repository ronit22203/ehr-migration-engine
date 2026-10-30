import { Button, Classes, Radio, RadioGroup, Spinner } from '@blueprintjs/core'
import { useId, useState } from 'react'
import { deleteAllFaxes, deleteFax, uploadFax } from '../api'
import type { ExplorerFilter, PacketSummary, PageSummary } from '../types'

function matchesFilter(page: PageSummary, selected: ExplorerFilter): boolean {
  if (selected === 'All') return true
  if (selected === 'Missing') return page.missing || page.failed
  if (selected === 'Pending') return page.pending
  if (selected === 'Reviewed') return page.reviewed
  return true
}

export function Explorer({
  packets,
  filter,
  selectedStem,
  onFilter,
  onSelect,
  onChanged,
}: {
  packets: PacketSummary[]
  filter: ExplorerFilter
  selectedStem: string | null
  onFilter: (filter: ExplorerFilter) => void
  onSelect: (stem: string) => void
  onChanged: () => Promise<void>
}) {
  const inputId = useId()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function withBusy(work: () => Promise<void>) {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await work()
      await onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function onUpload(fileList: FileList | null) {
    const file = fileList?.[0]
    if (!file) return
    await withBusy(async () => {
      const result = await uploadFax(file)
      const cleared = result.fax.cleared ?? 0
      setMessage(
        cleared > 0
          ? `Replaced drop with ${result.fax.filename} (cleared ${cleared} prior files). Click Split drop.`
          : `Uploaded ${result.fax.filename}. Click Split drop in the pipeline console.`,
      )
    })
  }

  async function onDeletePacket(stem: string, filename: string) {
    if (!window.confirm(`Remove ${filename} and its derived pages from the drop?`)) return
    await withBusy(async () => {
      await deleteFax(stem)
      setMessage(`Removed ${filename}.`)
    })
  }

  async function onClearDrop() {
    if (!window.confirm('Clear every fax in the drop and all derived stage files?')) return
    await withBusy(async () => {
      await deleteAllFaxes()
      setMessage('Fax drop cleared.')
    })
  }

  return (
    <div className="wb-pane">
      <p className="wb-kicker">Explorer</p>
      <div className="wb-upload-card">
        <p className="wb-upload-title">Upload fax / PDF</p>
        <p className={Classes.TEXT_MUTED}>
          Replaces the live drop with this one PDF so Split/OCR process only your upload.
        </p>
        <label className="wb-upload-button" htmlFor={inputId}>
          <input
            id={inputId}
            className="wb-upload-input"
            type="file"
            accept="application/pdf,.pdf"
            disabled={busy}
            onChange={(event) => {
              const files = event.currentTarget.files
              event.currentTarget.value = ''
              void onUpload(files)
            }}
          />
          {busy ? <Spinner size={16} /> : null}
          {busy ? 'Uploading…' : 'Choose PDF to upload'}
        </label>
        <Button
          small
          minimal
          intent="danger"
          disabled={busy || !packets.length}
          text="Clear drop"
          onClick={() => void onClearDrop()}
        />
      </div>
      {message ? <p className={Classes.TEXT_MUTED}>{message}</p> : null}
      {error ? <p className="wb-error">{error}</p> : null}
      <RadioGroup
        selectedValue={filter}
        onChange={(event) => onFilter(event.currentTarget.value as ExplorerFilter)}
        inline
      >
        {(['All', 'Missing', 'Pending', 'Reviewed'] as ExplorerFilter[]).map((item) => (
          <Radio key={item} label={item} value={item} />
        ))}
      </RadioGroup>
      {!packets.length ? (
        <p className={Classes.TEXT_MUTED}>No fax packets yet. Upload a PDF above, then run Split drop.</p>
      ) : (
        packets.map((packet) => {
          const pages = packet.pages.filter((page) => matchesFilter(page, filter))
          if (filter !== 'All' && !pages.length && packet.pages.length) return null
          return (
            <div key={packet.stem} className="wb-packet">
              <div className="wb-packet-header">
                <div className="wb-packet-title">{packet.filename}</div>
                <Button
                  small
                  minimal
                  intent="danger"
                  icon="trash"
                  disabled={busy}
                  title={`Remove ${packet.filename}`}
                  onClick={() => void onDeletePacket(packet.stem, packet.filename)}
                />
              </div>
              {!packet.pages.length ? (
                <p className={Classes.TEXT_MUTED}>Uploaded · not split yet</p>
              ) : !pages.length ? (
                <p className={Classes.TEXT_MUTED}>No pages match this filter.</p>
              ) : (
                pages.map((page) => {
                  const label = `${String(page.page_number).padStart(3, '0')}  ${page.marker}`
                  return (
                    <Button
                      key={page.stem}
                      fill
                      alignText="left"
                      intent={page.stem === selectedStem ? 'primary' : 'none'}
                      className="wb-page-button"
                      onClick={() => onSelect(page.stem)}
                      text={label}
                    />
                  )
                })
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
