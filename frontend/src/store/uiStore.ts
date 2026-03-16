import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UiStore {
  selectedLeagueId: number | null
  selectedSeason: number
  setLeague: (id: number) => void
  setSeason: (year: number) => void

  // Favoriten (persistent)
  favoriteLeagueIds: number[]
  toggleFavoriteLeague: (id: number) => void

  // Aktiver Filter auf der Spieltag-Seite
  activeLeagueFilter: number | null
  setActiveLeagueFilter: (id: number | null) => void

  // Datum-Offset für die Spieltag-Seite (0 = heute, ±N Tage)
  spieltagOffset: number
  setSpieltagOffset: (offset: number | ((prev: number) => number)) => void
}

const currentSeason = new Date().getMonth() >= 6
  ? new Date().getFullYear()
  : new Date().getFullYear() - 1

export const useUiStore = create<UiStore>()(
  persist(
    (set, get) => ({
      selectedLeagueId: null,
      selectedSeason: currentSeason,
      setLeague: (id) => set({ selectedLeagueId: id }),
      setSeason: (year) => set({ selectedSeason: year }),

      favoriteLeagueIds: [],
      toggleFavoriteLeague: (id) => {
        const current = get().favoriteLeagueIds
        const next = current.includes(id)
          ? current.filter(x => x !== id)
          : [...current, id]
        set({ favoriteLeagueIds: next })
      },

      activeLeagueFilter: null,
      setActiveLeagueFilter: (id) => set({ activeLeagueFilter: id }),

      spieltagOffset: 0,
      setSpieltagOffset: (offset) => set((state) => {
        const next = typeof offset === 'function' ? offset(state.spieltagOffset) : offset
        return { spieltagOffset: Number.isFinite(next) ? next : 0 }
      }),
    }),
    {
      name: 'qf-ui-store',
      partialize: (state) => ({
        favoriteLeagueIds: state.favoriteLeagueIds,
        selectedSeason: state.selectedSeason,
      }),
    }
  )
)
