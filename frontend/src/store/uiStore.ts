import { create } from 'zustand'

interface UiStore {
  selectedLeagueId: number | null
  selectedSeason: number
  setLeague: (id: number) => void
  setSeason: (year: number) => void
}

const currentSeason = new Date().getMonth() >= 6
  ? new Date().getFullYear()
  : new Date().getFullYear() - 1

export const useUiStore = create<UiStore>(set => ({
  selectedLeagueId: null,
  selectedSeason: currentSeason,
  setLeague: (id) => set({ selectedLeagueId: id }),
  setSeason: (year) => set({ selectedSeason: year }),
}))
