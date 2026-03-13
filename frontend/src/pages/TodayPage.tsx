import {
  Stack, Title, Group, Text, Badge, Loader, Center,
  Box, Image, ActionIcon, Tooltip, Divider, Paper,
} from '@mantine/core'
import {
  IconChevronLeft, IconChevronRight, IconCalendar,
  IconRefresh, IconStarFilled, IconFlame,
} from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import 'dayjs/locale/de'
import { fixturesApi, type EnrichedFixture } from '../api'
import { MatchRow, MATCH_ROW_GRID } from '../components/common/MatchRow'
import { leagueLogoUrl, countryFlagUrl, COUNTRY_FLAGS } from '../types'
import { useUiStore } from '../store/uiStore'

dayjs.locale('de')

const COUNTRY_ORDER = ['Germany', 'England', 'Spain', 'France', 'Italy', 'Turkey']
const COUNTRY_NAMES: Record<string, string> = {
  Germany: 'Deutschland', England: 'England', Spain: 'Spanien',
  France: 'Frankreich', Italy: 'Italien', Turkey: 'Türkei',
}

function toDateStr(d: dayjs.Dayjs) {
  return d.format('YYYY-MM-DD')
}

function groupByCountryAndLeague(fixtures: EnrichedFixture[]) {
  const result: Record<string, Record<number, { leagueName: string; leagueTier: number; leagueCountry: string; fixtures: EnrichedFixture[] }>> = {}
  for (const f of fixtures) {
    const country = f.league_country ?? 'Sonstige'
    const lid = f.league_id
    if (!result[country]) result[country] = {}
    if (!result[country][lid]) result[country][lid] = {
      leagueName: f.league_name ?? String(lid),
      leagueTier: f.league_tier ?? 99,
      leagueCountry: country,
      fixtures: [],
    }
    result[country][lid].fixtures.push(f)
  }
  return result
}

// ─── Table Column Header ───────────────────────────────────────────────────
function ColumnHeaders() {
  return (
    <Box style={{
      display: 'grid',
      gridTemplateColumns: MATCH_ROW_GRID,
      padding: '4px 12px',
      borderBottom: '1px solid var(--mantine-color-default-border)',
    }}>
      <Box />
      <Text size="10px" c="dimmed" ta="right" tt="uppercase" fw={600} pr={10}>Heim</Text>
      <Text size="10px" c="dimmed" ta="center" tt="uppercase" fw={600}>Ergebnis</Text>
      <Text size="10px" c="dimmed" tt="uppercase" fw={600} pl={10}>Gast</Text>
      <Group gap={4} pl={12} wrap="nowrap">
        <Text size="10px" c="dimmed" tt="uppercase" fw={600}>1</Text>
        <Text size="10px" c="dimmed">·</Text>
        <Text size="10px" c="dimmed" tt="uppercase" fw={600}>X</Text>
        <Text size="10px" c="dimmed">·</Text>
        <Text size="10px" c="dimmed" tt="uppercase" fw={600}>2</Text>
        <Box style={{ width: 1, height: 12, backgroundColor: 'var(--mantine-color-default-border)', margin: '0 6px' }} />
        <Text size="10px" c="dimmed" tt="uppercase" fw={600}>Tor-Wkt.</Text>
      </Group>
    </Box>
  )
}

// ─── League Table Block ────────────────────────────────────────────────────
function LeagueBlock({
  leagueId,
  leagueName,
  leagueCountry,
  fixtures,
  isFavorite,
  showHeader,
  onClick,
  onRowClick,
}: {
  leagueId: number
  leagueName: string
  leagueCountry: string
  fixtures: EnrichedFixture[]
  isFavorite: boolean
  showHeader: boolean
  onClick: () => void
  onRowClick: (id: number) => void
}) {
  const liveCount = fixtures.filter(f => ['1H', 'HT', '2H'].includes(f.status_short ?? '')).length

  return (
    <Box style={{
      borderRadius: 8,
      border: '1px solid var(--mantine-color-default-border)',
      overflow: 'hidden',
      backgroundColor: 'light-dark(white, var(--mantine-color-dark-7))',
    }}>
      {/* League Header */}
      {showHeader && (
        <Group
          px="md" py="xs" gap="sm"
          justify="space-between"
          style={{
            cursor: 'pointer',
            borderBottom: '1px solid var(--mantine-color-default-border)',
            backgroundColor: 'light-dark(#f8f9fa, var(--mantine-color-dark-6))',
          }}
          onClick={onClick}
        >
          <Group gap={10} wrap="nowrap">
            <Image
              src={countryFlagUrl(leagueCountry)}
              w={20} h={14} fit="contain"
              fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
            />
            <Image
              src={leagueLogoUrl(leagueId)}
              w={20} h={20} fit="contain"
              fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
            />
            <Text fw={700} size="sm">{leagueName}</Text>
            <Text size="xs" c="dimmed">
              {COUNTRY_NAMES[leagueCountry] ?? leagueCountry}
            </Text>
            {isFavorite && <IconStarFilled size={12} color="var(--mantine-color-yellow-5)" />}
          </Group>
          <Group gap={8}>
            {liveCount > 0 && (
              <Badge size="xs" color="orange" variant="filled" leftSection={<IconFlame size={10} />}>
                {liveCount} Live
              </Badge>
            )}
            <Badge size="xs" variant="light" color="blue">{fixtures.length} Spiele</Badge>
          </Group>
        </Group>
      )}

      {/* Column headers – once per block */}
      <ColumnHeaders />

      {/* Match rows */}
      <Stack gap={0}>
        {fixtures.map((f, i) => (
          <Box key={f.id}>
            {i > 0 && <Divider style={{ margin: '0 12px' }} />}
            <Box
              className="match-row-hover"
              style={{ transition: 'background 0.1s' }}
            >
              <MatchRow fixture={f} onClick={() => onRowClick(f.id)} />
            </Box>
          </Box>
        ))}
      </Stack>
    </Box>
  )
}

// ─── Live Highlights Section ───────────────────────────────────────────────
function LiveHighlights({
  fixtures,
  onRowClick,
}: {
  fixtures: EnrichedFixture[]
  onRowClick: (id: number) => void
}) {
  if (!fixtures.length) return null

  return (
    <Box style={{
      borderRadius: 8,
      border: '2px solid var(--mantine-color-orange-5)',
      overflow: 'hidden',
      backgroundColor: 'light-dark(white, var(--mantine-color-dark-7))',
    }}>
      {/* Live Header */}
      <Group
        px="md" py="xs" gap="sm"
        justify="space-between"
        style={{
          borderBottom: '1px solid var(--mantine-color-default-border)',
          background: 'linear-gradient(90deg, light-dark(#fff4e6, #2a1a00) 0%, light-dark(white, var(--mantine-color-dark-7)) 100%)',
        }}
      >
        <Group gap={10}>
          <Badge
            color="orange" variant="filled" size="sm"
            leftSection={<IconFlame size={11} />}
          >
            LIVE
          </Badge>
          <Text fw={700} size="sm">Live-Spiele</Text>
          <Text size="xs" c="dimmed">Alle Live-Events ({fixtures.length})</Text>
        </Group>
        <Group gap={8}>
          <Text size="10px" c="dimmed" tt="uppercase" fw={600}>Vorhersage</Text>
          <Text size="10px" c="dimmed" tt="uppercase" fw={600}>Tor-Wkt.</Text>
        </Group>
      </Group>

      <ColumnHeaders />

      <Stack gap={0}>
        {fixtures.map((f, i) => (
          <Box key={f.id}>
            {i > 0 && <Divider style={{ margin: '0 12px' }} />}
            <MatchRow fixture={f} onClick={() => onRowClick(f.id)} />
          </Box>
        ))}
      </Stack>
    </Box>
  )
}

// ─── TodayPage ─────────────────────────────────────────────────────────────
export function TodayPage() {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0)
  const activeDate = dayjs().add(offset, 'day')
  const dateStr = toDateStr(activeDate)

  const { activeLeagueFilter, favoriteLeagueIds } = useUiStore()

  const { data: fixtures = [], isLoading, refetch } = useQuery({
    queryKey: ['fixtures-today-enriched', dateStr],
    queryFn: () => fixturesApi.todayEnriched(dateStr),
    staleTime: 1000 * 60 * 5,
  })

  const isToday = offset === 0
  const dateLabel = isToday ? 'Heute'
    : offset === 1 ? 'Morgen'
    : offset === -1 ? 'Gestern'
    : activeDate.format('dddd, DD. MMMM')

  // Filter
  const visibleFixtures = activeLeagueFilter !== null
    ? fixtures.filter(f => f.league_id === activeLeagueFilter)
    : fixtures

  const liveFixtures = visibleFixtures.filter(f => ['1H', 'HT', '2H'].includes(f.status_short ?? ''))
  const nonLiveFixtures = visibleFixtures.filter(f => !['1H', 'HT', '2H'].includes(f.status_short ?? ''))

  const finishedCount = fixtures.filter(f => ['FT', 'AET', 'PEN'].includes(f.status_short ?? '')).length
  const liveCount = fixtures.filter(f => ['1H', 'HT', '2H'].includes(f.status_short ?? '')).length
  const nsCount = fixtures.filter(f => f.status_short === 'NS').length

  // Gruppenreihenfolge: Favoriten-Länder vorn
  const grouped = groupByCountryAndLeague(nonLiveFixtures)
  const favCountries = [...new Set(
    nonLiveFixtures.filter(f => favoriteLeagueIds.includes(f.league_id)).map(f => f.league_country ?? 'Sonstige')
  )]
  const countryOrder = [
    ...favCountries,
    ...COUNTRY_ORDER.filter(c => !favCountries.includes(c)),
    ...Object.keys(grouped).filter(c => !COUNTRY_ORDER.includes(c) && !favCountries.includes(c)),
  ].filter(c => grouped[c])

  return (
    <Stack gap="md">
      {/* ── Header ─────────────────────────────────────────────── */}
      <Group justify="space-between" align="center" wrap="nowrap">
        <Stack gap={2}>
          <Title order={2}>Spieltag</Title>
          <Text c="dimmed" size="sm">
            {activeLeagueFilter
              ? visibleFixtures[0]?.league_name ?? 'Liga'
              : 'Spiele unserer Ligen'}
          </Text>
        </Stack>

        {/* Datums-Navigation */}
        <Group gap="xs">
          <ActionIcon variant="subtle" onClick={() => setOffset(o => o - 1)}>
            <IconChevronLeft size={18} />
          </ActionIcon>
          <Group gap={6} style={{ minWidth: 180, justifyContent: 'center' }}>
            <IconCalendar size={16} />
            <Text fw={600} size="sm">{dateLabel}</Text>
            <Text c="dimmed" size="xs">{activeDate.format('DD.MM.YYYY')}</Text>
          </Group>
          <ActionIcon variant="subtle" onClick={() => setOffset(o => o + 1)}>
            <IconChevronRight size={18} />
          </ActionIcon>
          {isToday && (
            <Tooltip label="Aktualisieren">
              <ActionIcon variant="subtle" onClick={() => refetch()}>
                <IconRefresh size={16} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>

        {/* Status-Badges */}
        <Group gap={6}>
          {liveCount > 0 && (
            <Badge color="orange" variant="filled" size="sm" leftSection={<IconFlame size={11} />}>
              {liveCount} Live
            </Badge>
          )}
          {finishedCount > 0 && <Badge color="green" variant="light" size="sm">{finishedCount} beendet</Badge>}
          {nsCount > 0 && <Badge color="gray" variant="light" size="sm">{nsCount} ausstehend</Badge>}
          {fixtures.length === 0 && !isLoading && <Badge color="gray" variant="light" size="sm">0 Spiele</Badge>}
        </Group>
      </Group>

      {/* ── Inhalt ─────────────────────────────────────────────── */}
      {isLoading ? (
        <Center py="xl"><Loader /></Center>
      ) : visibleFixtures.length === 0 ? (
        <Paper withBorder p="xl" radius="md">
          <Stack align="center" gap="xs">
            <Text size="xl">📅</Text>
            <Text fw={500}>Keine Spiele am {activeDate.format('DD.MM.YYYY')}</Text>
            <Text c="dimmed" size="sm">In unseren Ligen finden an diesem Tag keine Partien statt.</Text>
          </Stack>
        </Paper>
      ) : (
        <Stack gap="sm">
          {/* Live-Sektion (ganz oben, orange umrandet) */}
          {liveFixtures.length > 0 && (
            <LiveHighlights
              fixtures={liveFixtures}
              onRowClick={(id) => navigate(`/spiel/${id}`)}
            />
          )}

          {/* Liga-Blöcke nach Land */}
          {countryOrder.map(country => {
            const leaguesInCountry = Object.entries(grouped[country])
              .sort(([idA, a], [idB, b]) => {
                const aFav = favoriteLeagueIds.includes(Number(idA))
                const bFav = favoriteLeagueIds.includes(Number(idB))
                if (aFav && !bFav) return -1
                if (!aFav && bFav) return 1
                return a.leagueTier - b.leagueTier
              })

            return (
              <Stack key={country} gap="xs">
                {/* Land-Trennlinie */}
                <Group gap={6} px={2}>
                  <Image
                    src={countryFlagUrl(country)}
                    w={18} h={13} fit="contain"
                    fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
                  />
                  <Text size="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: '0.07em' }}>
                    {COUNTRY_FLAGS[country] ?? ''} {COUNTRY_NAMES[country] ?? country}
                  </Text>
                </Group>

                {leaguesInCountry.map(([leagueIdStr, leagueData]) => {
                  const leagueId = Number(leagueIdStr)
                  return (
                    <LeagueBlock
                      key={leagueId}
                      leagueId={leagueId}
                      leagueName={leagueData.leagueName}
                      leagueCountry={country}
                      fixtures={leagueData.fixtures}
                      isFavorite={favoriteLeagueIds.includes(leagueId)}
                      showHeader
                      onClick={() => navigate(`/liga/${leagueId}`)}
                      onRowClick={(id) => navigate(`/spiel/${id}`)}
                    />
                  )
                })}
              </Stack>
            )
          })}
        </Stack>
      )}
    </Stack>
  )
}
