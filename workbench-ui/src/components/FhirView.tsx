import { Callout, Classes, Code, Spinner } from '@blueprintjs/core'
import { useEffect, useState } from 'react'
import { fetchFhir } from '../api'

export function FhirView({ stem }: { stem: string }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [payload, setPayload] = useState<Awaited<ReturnType<typeof fetchFhir>> | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchFhir(stem)
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
  if (!payload?.available) {
    return (
      <Callout intent="warning" title="FHIR serialization has not been run for this page.">
        <Code>make fhir</Code>
      </Callout>
    )
  }
  return (
    <div>
      <p className={Classes.TEXT_MUTED}>
        {payload.path} · {payload.type || 'bundle'} · {payload.count} resources
      </p>
      {payload.summary ? <p className={Classes.TEXT_MUTED}>{payload.summary}</p> : null}
      <pre className="wb-pre">{JSON.stringify(payload.bundle, null, 2)}</pre>
    </div>
  )
}
