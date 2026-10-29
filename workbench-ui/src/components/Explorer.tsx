import { Button, Classes, Radio, RadioGroup } from '@blueprintjs/core'
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
}: {
  packets: PacketSummary[]
  filter: ExplorerFilter
  selectedStem: string | null
  onFilter: (filter: ExplorerFilter) => void
  onSelect: (stem: string) => void
}) {
  return (
    <div className="wb-pane">
      <p className="wb-kicker">Explorer</p>
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
        <p className={Classes.TEXT_MUTED}>No fax packets in data/01_raw/faxes. Add a PDF there, then split it.</p>
      ) : (
        packets.map((packet) => {
          const pages = packet.pages.filter((page) => matchesFilter(page, filter))
          if (filter !== 'All' && !pages.length && packet.pages.length) return null
          return (
            <div key={packet.stem} className="wb-packet">
              <div className="wb-packet-title">{packet.filename}</div>
              {!packet.pages.length ? (
                <p className={Classes.TEXT_MUTED}>Not split</p>
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
