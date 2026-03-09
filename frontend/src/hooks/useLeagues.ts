import { useQuery } from '@tanstack/react-query'
import { leaguesApi } from '../api'

export function useLeagues() {
  return useQuery({
    queryKey: ['leagues'],
    queryFn: leaguesApi.list,
    staleTime: Infinity, // Ligen ändern sich kaum
  })
}
