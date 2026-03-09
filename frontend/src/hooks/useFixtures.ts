import { useQuery } from '@tanstack/react-query'
import { fixturesApi, syncApi } from '../api'

export function useFixtures(params: {
  league_id?: number
  season_year?: number
  status?: string
  matchday?: number
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: ['fixtures', params],
    queryFn: () => fixturesApi.list(params),
    enabled: !!params.league_id,
  })
}

export function useBudget() {
  return useQuery({
    queryKey: ['budget'],
    queryFn: syncApi.budget,
    refetchInterval: 60_000,
  })
}
