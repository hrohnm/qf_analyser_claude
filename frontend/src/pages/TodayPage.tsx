import {
  Stack, Title, Group, Text, Badge, Loader, Center,
  Box, Image, ActionIcon, Tooltip, Divider, Paper, Button, Select,
} from '@mantine/core'
import {
  IconChevronLeft, IconChevronRight, IconCalendar,
  IconRefresh, IconStarFilled, IconFlame, IconPlayerPause, IconPlayerPlay,
} from '@tabler/icons-react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import 'dayjs/locale/de'
import { useEffect, useRef, useState } from 'react'
import { bettingSlipsApi, fixturesApi, syncApi, type EnrichedFixture } from '../api'
import { MatchRow, MATCH_ROW_GRID } from '../components/common/MatchRow'
import { leagueLogoUrl, countryFlagUrl, COUNTRY_FLAGS } from '../types'
import { useUiStore } from '../store/uiStore'

dayjs.locale('de')

const COUNTRY_ORDER = ['Germany', 'England', 'Spain', 'France', 'Italy', 'Turkey']
const DEFAULT_AUTO_REFRESH_SECONDS = 300
const REFRESH_INTERVAL_OPTIONS = [
  { value: '1', label: '1 Minute' },
  { value: '2', label: '2 Minuten' },
  { value: '5', label: '5 Minuten' },
  { value: '10', label: '10 Minuten' },
  { value: '15', label: '15 Minuten' },
]
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

function countrySortIndex(country: string) {
  const idx = COUNTRY_ORDER.indexOf(country)
  return idx === -1 ? COUNTRY_ORDER.length : idx
}

function sortFixturesByCountryLeague(fixtures: EnrichedFixture[]) {
  return [...fixtures].sort((a, b) => {
    const countryA = a.league_country ?? 'Sonstige'
    const countryB = b.league_country ?? 'Sonstige'
    const countryDiff = countrySortIndex(countryA) - countrySortIndex(countryB)
    if (countryDiff !== 0) return countryDiff
    if (countryA !== countryB) return countryA.localeCompare(countryB)

    const tierA = a.league_tier ?? 99
    const tierB = b.league_tier ?? 99
    if (tierA !== tierB) return tierA - tierB

    const leagueA = a.league_name ?? ''
    const leagueB = b.league_name ?? ''
    if (leagueA !== leagueB) return leagueA.localeCompare(leagueB)

    const kickoffA = a.kickoff_utc ?? ''
    const kickoffB = b.kickoff_utc ?? ''
    if (kickoffA !== kickoffB) return kickoffA.localeCompare(kickoffB)

    return a.id - b.id
  })
}

type SlipTip = {
  source: 'ai' | 'pattern'
  slipName: string
  market: string
  pick: string | null
}

function buildSlipTipsMap(rawSlipData: Array<{ source: 'ai' | 'pattern'; data: any }>): Map<number, SlipTip[]> {
  const map = new Map<number, SlipTip[]>()

  for (const entry of rawSlipData) {
    const slips = entry.data?.slips?.slips ?? []
    for (const slip of slips) {
      const slipName = slip.name || `Schein ${slip.slip_nr}`
      for (const pick of (slip.picks ?? [])) {
        const fixtureId = pick.fixture_id
        if (typeof fixtureId !== 'number') continue
        const current = map.get(fixtureId) ?? []
        current.push({
          source: entry.source,
          slipName,
          market: pick.market ?? 'Tipp',
          pick: pick.pick ?? null,
        })
        map.set(fixtureId, current)
      }
    }
  }

  return map
}

function liveSnapshot(fixtures: EnrichedFixture[]): string {
  return fixtures
    .filter(f => ['1H', 'HT', '2H'].includes(f.status_short ?? ''))
    .map(f => `${f.id}:${f.status_short}:${f.home_score ?? '-'}:${f.away_score ?? '-'}`)
    .sort()
    .join('|')
}

function scoreSnapshot(fixtures: EnrichedFixture[]): Map<number, string> {
  return new Map(
    fixtures.map(f => [f.id, `${f.home_score ?? '-'}:${f.away_score ?? '-'}`])
  )
}

function playRefreshTone() {
  if (typeof window === 'undefined') return
  const AudioCtx = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AudioCtx) return

  const context = new AudioCtx()
  const oscillator = context.createOscillator()
  const gain = context.createGain()

  oscillator.type = 'sine'
  oscillator.frequency.setValueAtTime(880, context.currentTime)
  oscillator.frequency.exponentialRampToValueAtTime(660, context.currentTime + 0.18)
  gain.gain.setValueAtTime(0.0001, context.currentTime)
  gain.gain.exponentialRampToValueAtTime(0.045, context.currentTime + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.22)

  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start()
  oscillator.stop(context.currentTime + 0.23)
  oscillator.onended = () => {
    void context.close()
  }
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
  slipTipsMap,
  scoreChangedIds,
}: {
  leagueId: number
  leagueName: string
  leagueCountry: string
  fixtures: EnrichedFixture[]
  isFavorite: boolean
  showHeader: boolean
  onClick: () => void
  onRowClick: (id: number) => void
  slipTipsMap: Map<number, SlipTip[]>
  scoreChangedIds: Set<number>
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
              <MatchRow
                fixture={f}
                slipTips={slipTipsMap.get(f.id) ?? []}
                scoreChanged={scoreChangedIds.has(f.id)}
                onClick={() => onRowClick(f.id)}
              />
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
  slipTipsMap,
  scoreChangedIds,
}: {
  fixtures: EnrichedFixture[]
  onRowClick: (id: number) => void
  slipTipsMap: Map<number, SlipTip[]>
  scoreChangedIds: Set<number>
}) {
  if (!fixtures.length) return null

  const liveGroups = fixtures.reduce<Array<{ country: string; fixtures: EnrichedFixture[] }>>((acc, fixture) => {
    const country = fixture.league_country ?? 'Sonstige'
    const current = acc[acc.length - 1]
    if (current && current.country === country) {
      current.fixtures.push(fixture)
      return acc
    }
    acc.push({ country, fixtures: [fixture] })
    return acc
  }, [])

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
        {liveGroups.map((group, groupIndex) => (
          <Box key={group.country}>
            {groupIndex > 0 && <Divider my={4} />}
            <Group gap={6} px="sm" py={6}>
              <Image
                src={countryFlagUrl(group.country)}
                w={16}
                h={12}
                fit="contain"
                fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
              />
              <Text size="10px" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: '0.07em' }}>
                {COUNTRY_FLAGS[group.country] ?? ''} {COUNTRY_NAMES[group.country] ?? group.country}
              </Text>
            </Group>
            {group.fixtures.map((f, i) => (
              <Box key={f.id}>
                {(i > 0 || groupIndex > 0) && <Divider style={{ margin: '0 12px' }} />}
                <MatchRow
                  fixture={f}
                  slipTips={slipTipsMap.get(f.id) ?? []}
                  scoreChanged={scoreChangedIds.has(f.id)}
                  onClick={() => onRowClick(f.id)}
                />
              </Box>
            ))}
          </Box>
        ))}
      </Stack>
    </Box>
  )
}

// ─── TodayPage ─────────────────────────────────────────────────────────────
export function TodayPage() {
  const navigate = useNavigate()
  const { spieltagOffset: offset, setSpieltagOffset: setOffset } = useUiStore()
  const safeOffset = Number.isFinite(offset) ? offset : 0
  const activeDate = dayjs().add(safeOffset, 'day')
  const dateStr = toDateStr(activeDate)

  const { activeLeagueFilter, favoriteLeagueIds } = useUiStore()
  const audioArmedRef = useRef(false)
  const previousLiveSnapshotRef = useRef<string | null>(null)
  const previousScoreSnapshotRef = useRef<Map<number, string>>(new Map())
  const highlightTimeoutRef = useRef<number | null>(null)
  const [scoreChangedIds, setScoreChangedIds] = useState<Set<number>>(new Set())
  const [refreshCountdown, setRefreshCountdown] = useState(DEFAULT_AUTO_REFRESH_SECONDS)

  const {
    data: liveRefreshSettings,
    refetch: refetchLiveRefreshSettings,
  } = useQuery({
    queryKey: ['live-refresh-settings'],
    queryFn: () => syncApi.liveRefreshSettings(),
    staleTime: 15_000,
    refetchInterval: safeOffset === 0 ? 30_000 : false,
  })

  const autoRefreshEnabled = liveRefreshSettings?.enabled ?? true
  const autoRefreshSeconds = liveRefreshSettings?.interval_seconds ?? DEFAULT_AUTO_REFRESH_SECONDS
  const autoRefreshMs = autoRefreshSeconds * 1000

  const { data: fixtures = [], isLoading, refetch } = useQuery({
    queryKey: ['fixtures-today-enriched', dateStr],
    queryFn: () => fixturesApi.todayEnriched(dateStr),
    staleTime: 1000 * 60 * 5,
    refetchInterval: safeOffset === 0 && autoRefreshEnabled ? autoRefreshMs : false,
  })

  const { data: patternSlips } = useQuery({
    queryKey: ['betting-slips', dateStr, 'pattern', 'matchday'],
    queryFn: () => bettingSlipsApi.get(dateStr, 'pattern'),
    retry: false,
    staleTime: 30_000,
  })

  const { data: aiSlips } = useQuery({
    queryKey: ['betting-slips', dateStr, 'ai', 'matchday'],
    queryFn: () => bettingSlipsApi.get(dateStr, 'ai'),
    retry: false,
    staleTime: 30_000,
  })

  const liveRefreshMutation = useMutation({
    mutationFn: () => syncApi.refreshLiveToday(2025),
    onSuccess: async () => {
      await refetch()
    },
  })

  const liveRefreshSettingsMutation = useMutation({
    mutationFn: (payload: { enabled?: boolean; interval_seconds?: number }) =>
      syncApi.updateLiveRefreshSettings(payload),
    onSuccess: async () => {
      await refetchLiveRefreshSettings()
    },
  })

  const isToday = safeOffset === 0
  const dateLabel = isToday ? 'Heute'
    : safeOffset === 1 ? 'Morgen'
    : safeOffset === -1 ? 'Gestern'
    : activeDate.format('dddd, DD. MMMM')

  // Filter
  const visibleFixtures = activeLeagueFilter !== null
    ? fixtures.filter(f => f.league_id === activeLeagueFilter)
    : fixtures

  const liveFixtures = sortFixturesByCountryLeague(
    visibleFixtures.filter(f => ['1H', 'HT', '2H'].includes(f.status_short ?? ''))
  )
  const nonLiveFixtures = visibleFixtures.filter(f => !['1H', 'HT', '2H'].includes(f.status_short ?? ''))

  const finishedCount = fixtures.filter(f => ['FT', 'AET', 'PEN'].includes(f.status_short ?? '')).length
  const liveCount = fixtures.filter(f => ['1H', 'HT', '2H'].includes(f.status_short ?? '')).length
  const nsCount = fixtures.filter(f => f.status_short === 'NS').length
  const slipTipsMap = buildSlipTipsMap([
    { source: 'pattern', data: patternSlips },
    { source: 'ai', data: aiSlips },
  ])

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

  useEffect(() => {
    const unlockAudio = () => {
      audioArmedRef.current = true
    }

    window.addEventListener('pointerdown', unlockAudio, { once: true })
    return () => {
      window.removeEventListener('pointerdown', unlockAudio)
    }
  }, [])

  useEffect(() => {
    if (!isToday) {
      previousLiveSnapshotRef.current = null
      previousScoreSnapshotRef.current = new Map()
      setScoreChangedIds(new Set())
      setRefreshCountdown(autoRefreshSeconds)
      return
    }

    const snapshot = liveSnapshot(fixtures)
    const scores = scoreSnapshot(fixtures)
    if (previousLiveSnapshotRef.current === null) {
      previousLiveSnapshotRef.current = snapshot
      previousScoreSnapshotRef.current = scores
      return
    }

    const changedIds = new Set<number>()
    for (const fixture of fixtures) {
      const previousScore = previousScoreSnapshotRef.current.get(fixture.id)
      const currentScore = scores.get(fixture.id)
      if (
        previousScore != null &&
        currentScore != null &&
        previousScore !== currentScore &&
        ['1H', 'HT', '2H', 'FT', 'AET', 'PEN'].includes(fixture.status_short ?? '')
      ) {
        changedIds.add(fixture.id)
      }
    }

    if (
      snapshot &&
      snapshot !== previousLiveSnapshotRef.current &&
      audioArmedRef.current
    ) {
      playRefreshTone()
    }

    if (changedIds.size > 0) {
      setScoreChangedIds(changedIds)
      if (highlightTimeoutRef.current) {
        window.clearTimeout(highlightTimeoutRef.current)
      }
      highlightTimeoutRef.current = window.setTimeout(() => {
        setScoreChangedIds(new Set())
        highlightTimeoutRef.current = null
      }, 10000)
    }

    previousLiveSnapshotRef.current = snapshot
    previousScoreSnapshotRef.current = scores
  }, [fixtures, isToday, autoRefreshSeconds])

  useEffect(() => () => {
    if (highlightTimeoutRef.current) {
      window.clearTimeout(highlightTimeoutRef.current)
    }
  }, [])

  useEffect(() => {
    if (!isToday) return

    if (!autoRefreshEnabled) {
      setRefreshCountdown(autoRefreshSeconds)
      return
    }

    setRefreshCountdown(autoRefreshSeconds)
    const interval = window.setInterval(() => {
      setRefreshCountdown(prev => (prev <= 1 ? autoRefreshSeconds : prev - 1))
    }, 1000)

    return () => {
      window.clearInterval(interval)
    }
  }, [isToday, dateStr, autoRefreshEnabled, autoRefreshSeconds])

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
          <ActionIcon variant="subtle" onClick={() => setOffset(safeOffset - 1)}>
            <IconChevronLeft size={18} />
          </ActionIcon>
          <Group gap={6} style={{ minWidth: 180, justifyContent: 'center' }}>
            <IconCalendar size={16} />
            <Text fw={600} size="sm">{dateLabel}</Text>
            <Text c="dimmed" size="xs">{activeDate.format('DD.MM.YYYY')}</Text>
          </Group>
          <ActionIcon variant="subtle" onClick={() => setOffset(safeOffset + 1)}>
            <IconChevronRight size={18} />
          </ActionIcon>
          {isToday && (
            <Tooltip label="Aktualisieren">
              <ActionIcon variant="subtle" onClick={() => refetch()}>
                <IconRefresh size={16} />
              </ActionIcon>
            </Tooltip>
          )}
          {isToday && (
            <Tooltip label="Live-Zwischenstände aktualisieren">
              <Button
                size="xs"
                variant="light"
                color="orange"
                leftSection={<IconRefresh size={14} />}
                loading={liveRefreshMutation.isPending}
                disabled={liveRefreshMutation.isPending || liveCount === 0}
                onClick={() => liveRefreshMutation.mutate()}
              >
                Live aktualisieren
              </Button>
            </Tooltip>
          )}
          {isToday && (
            <Group gap="xs" wrap="nowrap">
              <Button
                size="xs"
                variant={autoRefreshEnabled ? 'default' : 'light'}
                color={autoRefreshEnabled ? 'gray' : 'green'}
                leftSection={autoRefreshEnabled ? <IconPlayerPause size={14} /> : <IconPlayerPlay size={14} />}
                loading={liveRefreshSettingsMutation.isPending}
                onClick={() => liveRefreshSettingsMutation.mutate({ enabled: !autoRefreshEnabled })}
              >
                {autoRefreshEnabled ? 'Auto pausieren' : 'Auto starten'}
              </Button>
              <Select
                size="xs"
                w={130}
                data={REFRESH_INTERVAL_OPTIONS}
                value={String(Math.round(autoRefreshSeconds / 60))}
                disabled={liveRefreshSettingsMutation.isPending}
                onChange={(value) => {
                  if (!value) return
                  const intervalSeconds = Number(value) * 60
                  if (intervalSeconds === autoRefreshSeconds) return
                  liveRefreshSettingsMutation.mutate({ interval_seconds: intervalSeconds })
                }}
              />
              <Badge size="sm" variant="light" color={autoRefreshEnabled ? 'gray' : 'yellow'}>
                {autoRefreshEnabled
                  ? `Nächste Aktualisierung in ${refreshCountdown}s`
                  : 'Auto-Refresh pausiert'}
              </Badge>
            </Group>
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
              slipTipsMap={slipTipsMap}
              scoreChangedIds={scoreChangedIds}
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
                    slipTipsMap={slipTipsMap}
                    scoreChangedIds={scoreChangedIds}
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
