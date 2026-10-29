import { Radio, RadioGroup } from '@blueprintjs/core'
import type { Stage } from '../types'

const STAGES: Stage[] = [
  'Overview',
  'Ingestion',
  'OCR',
  'Extraction',
  'Normalization',
  'Patient Timeline',
  'FHIR',
]

export function StageBar({ stage, onChange }: { stage: Stage; onChange: (stage: Stage) => void }) {
  return (
    <RadioGroup
      className="wb-stage-bar"
      selectedValue={stage}
      onChange={(event) => onChange(event.currentTarget.value as Stage)}
      inline
    >
      {STAGES.map((item) => (
        <Radio key={item} label={item} value={item} />
      ))}
    </RadioGroup>
  )
}
