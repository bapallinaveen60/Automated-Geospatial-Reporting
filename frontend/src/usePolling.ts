import { useCallback, useEffect, useState } from 'react'

/** Load data, then reload every `intervalMs` while `shouldPoll(data)` is true. */
export function usePolling<T>(
  load: () => Promise<T>,
  shouldPoll: (data: T) => boolean,
  intervalMs = 5000,
) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setData(await load())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [load])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (data === null || !shouldPoll(data)) return
    const timer = window.setInterval(() => void refresh(), intervalMs)
    return () => window.clearInterval(timer)
  }, [data, shouldPoll, refresh, intervalMs])

  return { data, error, refresh }
}
