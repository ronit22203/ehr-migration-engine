import { Callout, Code, Spinner } from '@blueprintjs/core'
import { useEffect, useState } from 'react'
import { fetchOcr } from '../api'

export function OcrView({ stem, fieldPath }: { stem: string; fieldPath: string | null }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [payload, setPayload] = useState<Awaited<ReturnType<typeof fetchOcr>> | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchOcr(stem, fieldPath)
      .then((data) => {
        if (!cancelled) {
          setPayload(data)
          setError(null)
        }
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
  }, [stem, fieldPath])

  if (loading) return <Spinner size={24} />
  if (error) return <Callout intent="danger">{error}</Callout>
  if (!payload?.available) {
    return (
      <Callout intent="warning" title="OCR has not been run for this page.">
        <Code>make ocr</Code>
        {payload?.parsed_text ? <pre className="wb-pre">{payload.parsed_text}</pre> : null}
      </Callout>
    )
  }
  if (!payload.blocks.length) {
    return <pre className="wb-pre">{payload.parsed_text || 'OCR file has no text.'}</pre>
  }
  return (
    <pre className="wb-pre">
      {payload.blocks
        .map((block) => `block ${block.index}${block.matched ? ' · matched' : ''}\n${block.text}`)
        .join('\n\n')}
    </pre>
  )
}
