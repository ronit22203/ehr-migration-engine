import { Callout, Classes, Code, Spinner } from '@blueprintjs/core'
import { useEffect, useState } from 'react'
import { fetchClinical } from '../api'

export function JsonView({ stem }: { stem: string }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [payload, setPayload] = useState<Awaited<ReturnType<typeof fetchClinical>> | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchClinical(stem)
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
  }, [stem])

  if (loading) return <Spinner size={24} />
  if (error) return <Callout intent="danger">{error}</Callout>
  if (payload?.available) {
    return (
      <div>
        {payload.path ? <p className={Classes.TEXT_MUTED}>{payload.path}</p> : null}
        <pre className="wb-pre">{JSON.stringify(payload.data, null, 2)}</pre>
      </div>
    )
  }
  if (payload?.error) {
    return (
      <div>
        <p className={Classes.TEXT_MUTED}>Extraction failed for this page.</p>
        <pre className="wb-pre">{JSON.stringify(payload.error, null, 2)}</pre>
      </div>
    )
  }
  return (
    <Callout intent="warning" title="Extraction has not been run for this page.">
      <Code>make extract</Code>
    </Callout>
  )
}
