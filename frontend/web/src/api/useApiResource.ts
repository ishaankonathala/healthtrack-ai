import { useCallback, useEffect, useState } from 'react'
import { ApiError } from './client'

export type ResourceState<T> =
  | { status: 'idle' | 'loading'; data: null; error: null }
  | { status: 'success'; data: T; error: null }
  | { status: 'error'; data: null; error: ApiError | Error }

export function useApiResource<T>(
  key: string | null,
  load: (signal: AbortSignal) => Promise<T>,
) {
  const [reloadVersion, setReloadVersion] = useState(0)
  const [state, setState] = useState<ResourceState<T>>({
    status: key ? 'loading' : 'idle', data: null, error: null,
  })

  useEffect(() => {
    if (!key) {
      setState({ status: 'idle', data: null, error: null })
      return
    }

    const controller = new AbortController()
    setState({ status: 'loading', data: null, error: null })
    load(controller.signal)
      .then((data) => setState({ status: 'success', data, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({ status: 'error', data: null, error: error instanceof Error ? error : new Error('Unexpected API error.') })
      })
    return () => controller.abort()
  }, [key, load, reloadVersion])

  const reload = useCallback(() => setReloadVersion((version) => version + 1), [])
  return { ...state, reload }
}
