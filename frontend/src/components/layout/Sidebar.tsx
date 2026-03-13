import {
  Stack, Text, Loader, Group, ActionIcon, Badge,
  ScrollArea, Image, Divider, Box, UnstyledButton,
} from '@mantine/core'
import { useNavigate, useLocation } from 'react-router-dom'
import { IconStar, IconStarFilled } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useLeagues } from '../../hooks/useLeagues'
import { useUiStore } from '../../store/uiStore'
import { COUNTRY_FLAGS, leagueLogoUrl } from '../../types'
import { fixturesApi } from '../../api'
import type { League } from '../../types'

const COUNTRY_ORDER = ['Germany', 'England', 'Spain', 'France', 'Italy', 'Turkey']
const COUNTRY_NAMES: Record<string, string> = {
  Germany: 'Deutschland',
  England: 'England',
  Spain: 'Spanien',
  France: 'Frankreich',
  Italy: 'Italien',
  Turkey: 'Türkei',
}

// ─── League item (bwin-style) ──────────────────────────────────────────────
function LeagueItem({
  league,
  isActive,
  isFavorite,
  count,
  dimmed,
  onSelect,
  onToggleFavorite,
}: {
  league: League
  isActive: boolean
  isFavorite: boolean
  count?: number
  dimmed?: boolean
  onSelect: () => void
  onToggleFavorite: () => void
}) {
  return (
    <Box
      component="div"
      onClick={dimmed ? undefined : onSelect}
      style={{
        display: 'block',
        width: '100%',
        padding: '7px 10px',
        borderRadius: 6,
        opacity: dimmed ? 0.38 : 1,
        cursor: dimmed ? 'default' : 'pointer',
        backgroundColor: isActive
          ? 'light-dark(#e7f5ff, rgba(34,139,230,0.15))'
          : undefined,
        borderLeft: isActive ? '2px solid var(--mantine-color-blue-5)' : '2px solid transparent',
        transition: 'background 0.1s',
      }}
      className="sidebar-league-item"
    >
      <Group justify="space-between" wrap="nowrap" gap={6}>
        <Group gap={8} wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
          <Image
            src={leagueLogoUrl(league.id)}
            w={20} h={20} fit="contain"
            style={{ flexShrink: 0 }}
            fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
          />
          <Text size="xs" fw={isActive ? 700 : 500} truncate style={{ flex: 1 }}>
            {league.name}
          </Text>
        </Group>
        <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
          {count !== undefined && count > 0 && (
            <Badge size="xs" variant="light" color="blue" style={{ minWidth: 22 }}>
              {count}
            </Badge>
          )}
          {!dimmed && (
            <ActionIcon
              variant="subtle"
              size="xs"
              color={isFavorite ? 'yellow' : 'gray'}
              onClick={(e) => { e.stopPropagation(); onToggleFavorite() }}
            >
              {isFavorite ? <IconStarFilled size={10} /> : <IconStar size={10} />}
            </ActionIcon>
          )}
        </Group>
      </Group>
    </Box>
  )
}

// ─── Section label ──────────────────────────────────────────────────────────
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <Text
      size="10px" fw={700} tt="uppercase" c="dimmed"
      px={10} pt={10} pb={2}
      style={{ letterSpacing: '0.08em' }}
    >
      {children}
    </Text>
  )
}

export function Sidebar() {
  const { data: leagues, isLoading } = useLeagues()
  const {
    selectedLeagueId, setLeague,
    favoriteLeagueIds, toggleFavoriteLeague,
    activeLeagueFilter, setActiveLeagueFilter,
  } = useUiStore()
  const navigate = useNavigate()
  const location = useLocation()

  const isOnToday = location.pathname === '/'
  const isDataBrowser = location.pathname.startsWith('/liga') || location.pathname.startsWith('/team')

  // Today's fixtures — used to know which leagues have games today
  const todayStr = dayjs().format('YYYY-MM-DD')
  const { data: todayFixtures = [] } = useQuery({
    queryKey: ['fixtures-today-enriched', todayStr],
    queryFn: () => fixturesApi.todayEnriched(todayStr),
    enabled: isOnToday,
    staleTime: 1000 * 60 * 5,
  })
  const leagueIdsWithGamesToday = new Set(todayFixtures.map((f: { league_id: number }) => f.league_id))

  // For today view: only active leagues
  const activeLeagues = (leagues ?? []).filter(l => l.is_active)

  const grouped = COUNTRY_ORDER.reduce<Record<string, League[]>>((acc, country) => {
    acc[country] = activeLeagues
      .filter(l => l.country === country)
      .sort((a, b) => a.tier - b.tier)
    return acc
  }, {})

  const allLeagues = leagues ?? []
  const favoriteLeagues = activeLeagues.filter(l => favoriteLeagueIds.includes(l.id))

  /* ── Spieltag: Liga-Filter ────────────────────────────────────────────── */
  if (isOnToday) {
    return (
      <Stack gap={0} h="100%" style={{ overflow: 'hidden' }}>
        {/* Header */}
        <Group
          justify="space-between" px={10} py={8}
          style={{ borderBottom: '1px solid var(--mantine-color-default-border)', flexShrink: 0 }}
        >
          <Text size="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: '0.08em' }}>
            Ligen
          </Text>
          <Group gap={4}>
            {activeLeagueFilter !== null && (
              <Badge
                size="xs" color="blue" variant="filled"
                style={{ cursor: 'pointer' }}
                onClick={() => setActiveLeagueFilter(null)}
              >
                × alle
              </Badge>
            )}
          </Group>
        </Group>

        {isLoading ? (
          <Loader size="xs" mx="auto" my="md" />
        ) : (
          <ScrollArea style={{ flex: 1 }} scrollbarSize={4} offsetScrollbars>
            <Stack gap={0} py={4}>
              {/* Alle Ligen */}
              <UnstyledButton
                onClick={() => setActiveLeagueFilter(null)}
                px={10} py={6}
                style={{
                  borderRadius: 6,
                  backgroundColor: activeLeagueFilter === null
                    ? 'light-dark(#e7f5ff, rgba(34,139,230,0.15))'
                    : undefined,
                  borderLeft: activeLeagueFilter === null
                    ? '2px solid var(--mantine-color-blue-5)'
                    : '2px solid transparent',
                }}
              >
                <Text size="xs" fw={activeLeagueFilter === null ? 700 : 500}>Alle Ligen</Text>
              </UnstyledButton>

              {/* Favoriten */}
              {favoriteLeagues.length > 0 && (
                <>
                  <Divider my={6} mx={10} />
                  <SectionLabel>
                    <Group gap={4} component="span">
                      <IconStarFilled size={10} color="var(--mantine-color-yellow-5)" />
                      {' '}Favoriten
                    </Group>
                  </SectionLabel>
                  {favoriteLeagues.map(league => {
                    const hasGames = leagueIdsWithGamesToday.has(league.id)
                    return (
                      <LeagueItem
                        key={league.id}
                        league={league}
                        isActive={activeLeagueFilter === league.id}
                        isFavorite
                        dimmed={!hasGames}
                        onSelect={() => setActiveLeagueFilter(activeLeagueFilter === league.id ? null : league.id)}
                        onToggleFavorite={() => toggleFavoriteLeague(league.id)}
                      />
                    )
                  })}
                  <Divider my={6} mx={10} />
                </>
              )}

              {/* Nach Land */}
              {COUNTRY_ORDER.map(country => {
                const countryLeagues = grouped[country] ?? []
                if (!countryLeagues.length) return null
                return (
                  <Box key={country}>
                    <SectionLabel>
                      {COUNTRY_FLAGS[country]} {COUNTRY_NAMES[country]}
                    </SectionLabel>
                    {countryLeagues.map(league => {
                      const hasGames = leagueIdsWithGamesToday.has(league.id)
                      return (
                        <LeagueItem
                          key={league.id}
                          league={league}
                          isActive={activeLeagueFilter === league.id}
                          isFavorite={favoriteLeagueIds.includes(league.id)}
                          dimmed={!hasGames}
                          onSelect={() => setActiveLeagueFilter(activeLeagueFilter === league.id ? null : league.id)}
                          onToggleFavorite={() => toggleFavoriteLeague(league.id)}
                        />
                      )
                    })}
                  </Box>
                )
              })}

              {/* Weitere Länder (dynamisch, alphabetisch sortiert) */}
              {(() => {
                const otherCountries = [...new Set(
                  activeLeagues
                    .filter(l => !COUNTRY_ORDER.includes(l.country))
                    .map(l => l.country)
                )].sort()
                return otherCountries.map(country => {
                  const countryLeagues = activeLeagues
                    .filter(l => l.country === country)
                    .sort((a, b) => a.tier - b.tier)
                  return (
                    <Box key={country}>
                      <SectionLabel>
                        {COUNTRY_FLAGS[country] ?? '🌍'} {COUNTRY_NAMES[country] ?? country}
                      </SectionLabel>
                      {countryLeagues.map(league => {
                        const hasGames = leagueIdsWithGamesToday.has(league.id)
                        return (
                          <LeagueItem
                            key={league.id}
                            league={league}
                            isActive={activeLeagueFilter === league.id}
                            isFavorite={favoriteLeagueIds.includes(league.id)}
                            dimmed={!hasGames}
                            onSelect={() => setActiveLeagueFilter(activeLeagueFilter === league.id ? null : league.id)}
                            onToggleFavorite={() => toggleFavoriteLeague(league.id)}
                          />
                        )
                      })}
                    </Box>
                  )
                })
              })()}
            </Stack>
          </ScrollArea>
        )}
      </Stack>
    )
  }

  /* ── Datenbrowser: Liga-Navigation ───────────────────────────────────── */
  if (isDataBrowser) {
    return (
      <Stack gap={0} h="100%" style={{ overflow: 'hidden' }}>
        <Group
          px={10} py={8}
          style={{ borderBottom: '1px solid var(--mantine-color-default-border)', flexShrink: 0 }}
        >
          <Text size="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: '0.08em' }}>
            Ligen
          </Text>
        </Group>

        {isLoading ? (
          <Loader size="xs" mx="auto" my="md" />
        ) : (
          <ScrollArea style={{ flex: 1 }} scrollbarSize={4} offsetScrollbars>
            <Stack gap={0} py={4}>
              {COUNTRY_ORDER.map(country => {
                const countryLeagues = grouped[country] ?? []
                if (!countryLeagues.length) return null
                return (
                  <Box key={country}>
                    <SectionLabel>
                      {COUNTRY_FLAGS[country]} {COUNTRY_NAMES[country]}
                    </SectionLabel>
                    {countryLeagues.map(league => (
                      <LeagueItem
                        key={league.id}
                        league={league}
                        isActive={selectedLeagueId === league.id}
                        isFavorite={favoriteLeagueIds.includes(league.id)}
                        onSelect={() => {
                          setLeague(league.id)
                          navigate(`/liga/${league.id}`)
                        }}
                        onToggleFavorite={() => toggleFavoriteLeague(league.id)}
                      />
                    ))}
                  </Box>
                )
              })}
              {/* Weitere Länder (dynamisch, alphabetisch) */}
              {[...new Set(
                activeLeagues
                  .filter(l => !COUNTRY_ORDER.includes(l.country))
                  .map(l => l.country)
              )].sort().map(country => {
                const countryLeagues = activeLeagues
                  .filter(l => l.country === country)
                  .sort((a, b) => a.tier - b.tier)
                return (
                  <Box key={country}>
                    <SectionLabel>
                      {COUNTRY_FLAGS[country] ?? '🌍'} {COUNTRY_NAMES[country] ?? country}
                    </SectionLabel>
                    {countryLeagues.map(league => (
                      <LeagueItem
                        key={league.id}
                        league={league}
                        isActive={selectedLeagueId === league.id}
                        isFavorite={favoriteLeagueIds.includes(league.id)}
                        onSelect={() => {
                          setLeague(league.id)
                          navigate(`/liga/${league.id}`)
                        }}
                        onToggleFavorite={() => toggleFavoriteLeague(league.id)}
                      />
                    ))}
                  </Box>
                )
              })}
            </Stack>
          </ScrollArea>
        )}
      </Stack>
    )
  }

  return <Box />
}
