import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Collapse,
  Divider,
  Grid,
  GridCol,
  Group,
  Loader,
  Modal,
  MultiSelect,
  NumberInput,
  Popover,
  Progress,
  RingProgress,
  SegmentedControl,
  SimpleGrid,
  Slider,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { useLocalStorage } from '@mantine/hooks'
import {
  IconAlertCircle,
  IconChartBar,
  IconCheck,
  IconChevronDown,
  IconChevronUp,
  IconCurrencyEuro,
  IconHistory,
  IconPlayerPlay,
  IconRefresh,
  IconRobot,
  IconTargetArrow,
  IconTicket,
  IconTrophy,
  IconX,
  IconWand,
} from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useState } from 'react'
import { bettingSlipsApi, leaguesApi, fixturesApi, type PlacedBet, type CustomSlip } from '../api'
// ISO display abbreviations — independent of flag-URL codes
const COUNTRY_ABBR: Record<string, string> = {
  Germany: 'GER', France: 'FRA', Italy: 'ITA', Spain: 'ESP', England: 'ENG',
  Turkey: 'TUR', Netherlands: 'NED', Belgium: 'BEL', Portugal: 'POR',
  Scotland: 'SCO', Austria: 'AUT', Switzerland: 'SUI', Greece: 'GRE',
  Russia: 'RUS', Ukraine: 'UKR', Croatia: 'CRO', Serbia: 'SRB',
  'Czech Republic': 'CZE', Romania: 'ROU', Poland: 'POL', Hungary: 'HUN',
  Denmark: 'DEN', Sweden: 'SWE', Norway: 'NOR', Finland: 'FIN',
  'United States': 'USA', Brazil: 'BRA', Argentina: 'ARG',
  Europe: 'UEFA', World: 'INT',
  'Saudi-Arabia': 'KSA', 'Saudi Arabia': 'KSA',
}

// Fallback: derive country from known league names (for slips generated before country field was added)
const LEAGUE_TO_COUNTRY: Array<[string, string]> = [
  // Germany
  ['Bundesliga', 'Germany'], ['2. Bundesliga', 'Germany'], ['3. Liga', 'Germany'],
  // France
  ['Ligue 1', 'France'], ['Ligue 2', 'France'], ['National', 'France'],
  // Italy
  ['Serie A', 'Italy'], ['Serie B', 'Italy'],
  ['Serie C - Girone A', 'Italy'], ['Serie C - Girone B', 'Italy'], ['Serie C - Girone C', 'Italy'],
  // Spain
  ['La Liga', 'Spain'], ['Segunda División', 'Spain'], ['Primera Federación', 'Spain'],
  // England
  ['Premier League', 'England'], ['Championship', 'England'], ['League One', 'England'], ['League Two', 'England'],
  // Turkey
  ['Süper Lig', 'Turkey'], ['1. Lig', 'Turkey'], ['2. Lig', 'Turkey'],
  // Netherlands
  ['Eredivisie', 'Netherlands'], ['Eerste Divisie', 'Netherlands'],
  // Belgium
  ['Jupiler Pro League', 'Belgium'], ['Challenger Pro League', 'Belgium'], ['First Amateur Division', 'Belgium'],
  // Portugal
  ['Primeira Liga', 'Portugal'], ['Liga Portugal 2', 'Portugal'], ['Segunda Liga', 'Portugal'],
  // Scotland
  ['Premiership', 'Scotland'], ['Championship', 'Scotland'],
  // Austria
  ['Bundesliga', 'Austria'], // ambiguous name; current slips should provide country from backend
  // Switzerland
  ['Super League', 'Switzerland'], ['Challenge League', 'Switzerland'],
  // Greece
  ['Super League 1', 'Greece'], ['Super League 2', 'Greece'],
  // Poland
  ['Ekstraklasa', 'Poland'], ['I Liga', 'Poland'],
  ['II Liga - East', 'Poland'], ['II Liga - West', 'Poland'], ['II Liga', 'Poland'],
  // Saudi Arabia
  ['Pro League', 'Saudi-Arabia'], ['Division 1', 'Saudi-Arabia'], ['Division 2', 'Saudi-Arabia'],
  // UEFA
  ['UEFA Champions League', 'Europe'], ['UEFA Europa League', 'Europe'], ['UEFA Conference League', 'Europe'],
]

function resolveCountry(country: string, league: string): string {
  if (country) return country
  return LEAGUE_TO_COUNTRY.find(([leagueName]) => leagueName === league)?.[1] || ''
}

function countryAbbr(country: string, league = ''): string {
  const resolved = resolveCountry(country, league)
  return COUNTRY_ABBR[resolved] ?? resolved.slice(0, 3).toUpperCase()
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function targetColor(combined: number, slipNr?: number) {
  // Slip 7 "Favoriten Auswärts" hat absichtlich höhere Kombinationsquote
  if (slipNr === 7) return combined >= 10 ? 'grape' : 'orange'
  if (combined >= 8 && combined <= 12) return 'green'
  if (combined >= 6 && combined < 8) return 'yellow'
  return 'red'
}

function statusColor(status: string) {
  if (status === 'won') return 'green'
  if (status === 'lost') return 'red'
  if (status === 'void') return 'yellow'
  return 'blue'
}

function statusLabel(status: string) {
  if (status === 'won') return 'Gewonnen'
  if (status === 'lost') return 'Verloren'
  if (status === 'void') return 'Void'
  return 'Angespielt'
}

function fixtureStatusLabel(status: string | null | undefined) {
  if (!status) return null
  if (status === 'NS') return 'Nicht gestartet'
  if (status === 'HT') return 'Halbzeit'
  if (status === '1H' || status === '2H') return status
  if (status === 'FT' || status === 'AET' || status === 'PEN') return 'Beendet'
  return status
}

function fixtureStatusColor(status: string | null | undefined) {
  if (!status) return 'gray'
  if (status === '1H' || status === 'HT' || status === '2H') return 'orange'
  if (status === 'FT' || status === 'AET' || status === 'PEN') return 'green'
  return 'gray'
}

// ─── Stats bar ────────────────────────────────────────────────────────────────

function StatsBar({ source }: { source: string }) {
  const { data: stats } = useQuery({
    queryKey: ['betting-stats', source],
    queryFn: () => bettingSlipsApi.getStats({ source }),
    staleTime: 30_000,
  })

  if (!stats || stats.total_placed === 0) return null

  const profit = stats.net_profit ?? 0
  const profitColor = profit > 0 ? 'green' : profit < 0 ? 'red' : 'gray'

  return (
    <Card withBorder p="sm">
      <SimpleGrid cols={{ base: 2, xs: 4, sm: 6 }} spacing="xs">
        <Box>
          <Text size="xs" c="dimmed">Gespielt</Text>
          <Text fw={700}>{stats.total_placed}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Offen</Text>
          <Text fw={700}>{stats.pending}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Gewonnen</Text>
          <Text fw={700} c="green">{stats.won}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Verloren</Text>
          <Text fw={700} c="red">{stats.lost}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Quote-Ø (W)</Text>
          <Text fw={700}>{stats.avg_odd_won?.toFixed(2) ?? '–'}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Profit/Loss</Text>
          <Text fw={700} c={profitColor}>
            {stats.net_profit != null ? `${profit >= 0 ? '+' : ''}${profit.toFixed(2)} €` : '–'}
          </Text>
        </Box>
      </SimpleGrid>
    </Card>
  )
}

// ─── Pick result dot ──────────────────────────────────────────────────────────

function PickDot({ result }: { result: string | null }) {
  const bg =
    result === 'win'  ? 'var(--mantine-color-green-6)' :
    result === 'loss' ? 'var(--mantine-color-red-6)'   :
                        'var(--mantine-color-gray-3)'
  return (
    <Box style={{
      width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
      background: bg, display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {result === 'win'  && <Text size="xs" c="white" fw={900} lh={1}>✓</Text>}
      {result === 'loss' && <Text size="xs" c="white" fw={900} lh={1}>✗</Text>}
    </Box>
  )
}

// ─── Slip card (Betano style) ─────────────────────────────────────────────────

function SlipCard({
  slip,
  source,
  slipDate,
  placedBet,
  onRefresh,
  defaultStake,
}: {
  slip: any
  source: 'ai' | 'pattern'
  slipDate: string
  placedBet: PlacedBet | null
  onRefresh: () => void
  defaultStake?: number
}) {
  const picks: any[] = slip.picks ?? []
  const combined: number = slip.combined_odd ?? 0
  const slipName = source === 'pattern' && slip.name ? slip.name : `Schein ${slip.slip_nr}`
  const [stake, setStake] = useState<number | string>(defaultStake ?? '')
  const [actualOdd, setActualOdd] = useState<number | string>(combined > 0 ? combined : '')
  const [stakeOpen, setStakeOpen] = useState(false)
  const isSettled = placedBet && placedBet.status !== 'placed'
  const stakeAmt = placedBet?.stake ? Number(placedBet.stake) : 0
  const TAX = 0.053 // Betano 5,3% Sportwettensteuer — vom Einsatz abgezogen
  const placedOdd = placedBet?.combined_odd ?? combined
  const returnAmt = placedBet?.status === 'won' ? stakeAmt * (1 - TAX) * placedOdd : 0
  const previewOdd = actualOdd !== '' ? Number(actualOdd) : combined
  const previewStake = stake !== '' ? Number(stake) : (defaultStake ?? 0)
  const potentialReturn = previewStake > 0 && previewOdd > 0 ? previewStake * (1 - TAX) * previewOdd : null

  // Group picks by fixture_id for Betano-style game rows
  const gameGroups: {
    fixtureId: number
    home: string
    away: string
    league: string
    country: string
    kickoff: string
    statusShort?: string | null
    homeScore?: number | null
    awayScore?: number | null
    picks: any[]
  }[] = []
  const seen = new Map<number, number>()
  for (const pick of picks) {
    const fid = pick.fixture_id
    if (!seen.has(fid)) {
      seen.set(fid, gameGroups.length)
      gameGroups.push({
        fixtureId: fid,
        home: pick.home,
        away: pick.away,
        league: pick.league,
        country: pick.country ?? '',
        kickoff: pick.kickoff,
        statusShort: pick.fixture_status_short ?? null,
        homeScore: pick.fixture_home_score ?? null,
        awayScore: pick.fixture_away_score ?? null,
        picks: [],
      })
    }
    gameGroups[seen.get(fid)!].picks.push(pick)
  }
  // Sort by country → league → kickoff so same-league games appear together
  gameGroups.sort((a, b) => {
    const ca = resolveCountry(a.country, a.league)
    const cb = resolveCountry(b.country, b.league)
    if (ca !== cb) return ca.localeCompare(cb)
    if (a.league !== b.league) return a.league.localeCompare(b.league)
    return a.kickoff.localeCompare(b.kickoff)
  })

  const placeMutation = useMutation({
    mutationFn: () => bettingSlipsApi.placeBet({
      slip_date: slipDate, source, slip_nr: slip.slip_nr,
      slip_name: slipName,
      combined_odd: actualOdd !== '' ? Number(actualOdd) : combined,
      stake: stake !== '' ? Number(stake) : undefined,
    }),
    onSuccess: () => { setStakeOpen(false); setStake(''); onRefresh() },
  })
  const settleMutation = useMutation({
    mutationFn: (status: 'won' | 'lost' | 'void') => bettingSlipsApi.settleBet(placedBet!.id, status),
    onSuccess: onRefresh,
  })
  const unplaceMutation = useMutation({
    mutationFn: () => bettingSlipsApi.unplaceBet(placedBet!.id),
    onSuccess: onRefresh,
  })
  const regenerateMutation = useMutation({
    mutationFn: () => bettingSlipsApi.regenerateSlip(slipDate, slip.slip_nr),
    onSuccess: onRefresh,
  })

  const headerBg =
    placedBet?.status === 'won'  ? 'var(--mantine-color-green-9)' :
    placedBet?.status === 'lost' ? 'var(--mantine-color-red-9)'   :
    placedBet?.status === 'placed' ? 'var(--mantine-color-blue-9)' :
                                   'var(--mantine-color-dark-6)'

  return (
    <Card withBorder p={0} h="100%" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* ── Header ── */}
      <Box px="sm" py={8} style={{ background: headerBg }}>
        <Group justify="space-between" wrap="nowrap">
          <Stack gap={0}>
            <Text size="sm" fw={700} c="white" lh={1.2}>
              {slipName}
            </Text>
            <Text size="xs" c="rgba(255,255,255,0.65)" lh={1.2}>
              {slip.slip_nr === 7
                ? `${gameGroups.length} Siegerwetten · @ ${combined.toFixed(2)}`
                : `${gameGroups.length}-er Kombiwette · @ ${combined.toFixed(2)}`}
            </Text>
          </Stack>
          <Group gap={6} style={{ flexShrink: 0 }}>
            {!placedBet && source === 'pattern' && (
              <Tooltip label="Schein neu generieren" fz="xs" withArrow>
                <Button
                  size="xs" variant="subtle" color="gray" px={6}
                  loading={regenerateMutation.isPending}
                  onClick={() => regenerateMutation.mutate()}
                  style={{ color: 'rgba(255,255,255,0.6)' }}
                >
                  <IconRefresh size={14} />
                </Button>
              </Tooltip>
            )}
            {placedBet ? (
              <Badge size="md" color={statusColor(placedBet.status)} variant="filled" style={{ border: '1px solid rgba(255,255,255,0.3)' }}>
                {statusLabel(placedBet.status)}
              </Badge>
            ) : (
              <Badge size="md" color="gray" variant="outline" style={{ borderColor: 'rgba(255,255,255,0.3)', color: 'rgba(255,255,255,0.7)' }}>
                Offen
              </Badge>
            )}
          </Group>
        </Group>
      </Box>

      {/* ── Pick rows ── */}
      <Stack gap={0} style={{ flex: 1 }}>
        {gameGroups.map((game, gi) => {
          const hasBB = game.picks.some(p => p.betbuilder === true)
          const bbResult: string | null = hasBB
            ? game.picks.every(p => p.result === 'win') ? 'win'
              : game.picks.some(p => p.result === 'loss') ? 'loss'
              : null
            : null

          return (
            <Box key={game.fixtureId}>
              {gi > 0 && <Divider />}

              {/* Bet Builder game header */}
              {hasBB && (
                <Box
                  px="sm" py={7}
                  style={{
                    background: 'var(--mantine-color-gray-1)',
                    borderLeft: '3px solid var(--mantine-color-gray-4)',
                  }}
                >
                  <Group justify="space-between" wrap="nowrap" gap="xs">
                    <Group gap={6} wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                      <Badge size="xs" color="gray" variant="filled" radius="sm" style={{ flexShrink: 0 }}>BB</Badge>
                      <Stack gap={0} style={{ minWidth: 0 }}>
                        <Text size="xs" fw={700} truncate>{game.home} – {game.away}</Text>
                        <Group gap={6} wrap="wrap">
                          <Text size="xs" c="dimmed" truncate>
                            {countryAbbr(game.country, game.league)} · {game.league} · {game.kickoff}
                          </Text>
                          {game.statusShort && (
                            <Badge size="xs" color={fixtureStatusColor(game.statusShort)} variant="light">
                              {fixtureStatusLabel(game.statusShort)}
                              {game.homeScore != null && game.awayScore != null ? ` · ${game.homeScore}:${game.awayScore}` : ''}
                            </Badge>
                          )}
                        </Group>
                      </Stack>
                    </Group>
                    <PickDot result={bbResult} />
                  </Group>
                </Box>
              )}

              {/* Individual pick rows */}
              {game.picks.map((pick, pi) => (
                <Box
                  key={pi}
                  py={6}
                  style={{
                    paddingLeft: hasBB ? 28 : 'var(--mantine-spacing-sm)',
                    paddingRight: 'var(--mantine-spacing-sm)',
                    borderLeft: hasBB ? '3px solid var(--mantine-color-gray-3)' : '3px solid transparent',
                  }}
                >
                  <Group justify="space-between" wrap="nowrap" gap="xs">
                    <Group gap={8} wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                      <PickDot result={pick.result} />
                      <Stack gap={0} style={{ minWidth: 0 }}>
                        <Text size="xs" fw={600} truncate>
                          {pick.market}
                          {pick.pick ? <Text span c="dimmed"> · {pick.pick}</Text> : null}
                        </Text>
                        {!hasBB && (
                          <Group gap={6} wrap="wrap">
                            <Text size="xs" c="dimmed" truncate>
                              {countryAbbr(pick.country ?? '', pick.league)} · {pick.league} · {pick.home} – {pick.away} · {pick.kickoff}
                            </Text>
                            {pick.fixture_status_short && (
                              <Badge size="xs" color={fixtureStatusColor(pick.fixture_status_short)} variant="light">
                                {fixtureStatusLabel(pick.fixture_status_short)}
                                {pick.fixture_home_score != null && pick.fixture_away_score != null ? ` · ${pick.fixture_home_score}:${pick.fixture_away_score}` : ''}
                              </Badge>
                            )}
                          </Group>
                        )}
                      </Stack>
                    </Group>
                    {pick.odd != null && (
                      <Box style={{
                        background: 'var(--mantine-color-gray-1)',
                        borderRadius: 4, padding: '1px 6px', minWidth: 38, textAlign: 'center',
                        flexShrink: 0,
                      }}>
                        <Text size="xs" fw={700}>{Number(pick.odd).toFixed(2)}</Text>
                      </Box>
                    )}
                  </Group>
                </Box>
              ))}
            </Box>
          )
        })}
      </Stack>

      {/* ── Footer: Einsatz / Gewinne ── */}
      <Box px="sm" py={8} style={{ borderTop: '1px solid var(--mantine-color-gray-2)', background: 'var(--mantine-color-gray-0)' }}>
        <Group justify="space-between">
          <Stack gap={0}>
            <Text size="xs" c="dimmed">Einsatz</Text>
            <Text size="sm" fw={700}>{stakeAmt > 0 ? `${stakeAmt.toFixed(2)} €` : '–'}</Text>
          </Stack>
          <Stack gap={0} style={{ textAlign: 'right' }}>
            <Text size="xs" c="dimmed">
              {placedBet?.status === 'won' ? 'Gewinn' : 'Möglicher Gewinn'}
              <Text span size="xs" c="dimmed" fs="italic"> (–5,3% St.)</Text>
            </Text>
            <Text size="sm" fw={700} c={placedBet?.status === 'won' ? 'green' : 'dimmed'}>
              {placedBet?.status === 'won'
                ? `${returnAmt.toFixed(2)} €`
                : potentialReturn
                  ? `${potentialReturn.toFixed(2)} €`
                  : '–'
              }
            </Text>
          </Stack>
        </Group>
      </Box>

      {/* ── Actions ── */}
      <Box px="sm" py={8} style={{ borderTop: '1px solid var(--mantine-color-gray-2)' }}>
        {!placedBet ? (
          <Popover opened={stakeOpen} onChange={setStakeOpen} withArrow position="top">
            <Popover.Target>
              <Button size="xs" variant="light" color="blue" leftSection={<IconCurrencyEuro size={13} />} fullWidth
                onClick={() => setStakeOpen(o => !o)}>
                Angespielt
              </Button>
            </Popover.Target>
            <Popover.Dropdown>
              <Stack gap="xs" w={200}>
                <Text size="xs" fw={600}>Einsatz</Text>
                <NumberInput size="xs" placeholder="z.B. 10" min={0} step={1} decimalScale={2}
                  value={stake} onChange={setStake} rightSection={<Text size="xs" c="dimmed">€</Text>} />
                <Text size="xs" fw={600}>Betano-Quote</Text>
                <NumberInput size="xs" placeholder={combined.toFixed(2)} min={1} step={0.05} decimalScale={2}
                  value={actualOdd} onChange={setActualOdd} />
                {potentialReturn !== null && (
                  <Box style={{ background: 'var(--mantine-color-green-0)', borderRadius: 4, padding: '4px 8px' }}>
                    <Text size="xs" c="dimmed">Möglicher Gewinn</Text>
                    <Text size="xs" fw={700} c="green">{potentialReturn.toFixed(2)} €</Text>
                    <Text size="xs" c="dimmed" fs="italic">inkl. −5,3% Betano-Steuer</Text>
                  </Box>
                )}
                <Button size="xs" loading={placeMutation.isPending} onClick={() => placeMutation.mutate()}>
                  Bestätigen
                </Button>
              </Stack>
            </Popover.Dropdown>
          </Popover>
        ) : isSettled ? (
          <Group justify="space-between">
            <Text size="xs" c="dimmed">{statusLabel(placedBet.status)}</Text>
            <Button size="xs" variant="subtle" color="gray" loading={unplaceMutation.isPending}
              onClick={() => unplaceMutation.mutate()}>
              Zurücksetzen
            </Button>
          </Group>
        ) : (
          <Group gap={6}>
            <Button size="xs" variant="filled" color="green" style={{ flex: 1 }}
              leftSection={<IconTrophy size={12} />} loading={settleMutation.isPending}
              onClick={() => settleMutation.mutate('won')}>
              Gewonnen
            </Button>
            <Button size="xs" variant="filled" color="red" style={{ flex: 1 }}
              leftSection={<IconX size={12} />} loading={settleMutation.isPending}
              onClick={() => settleMutation.mutate('lost')}>
              Verloren
            </Button>
            <Tooltip label="Void / Annulliert">
              <Button size="xs" variant="light" color="yellow" leftSection={<IconCheck size={12} />}
                loading={settleMutation.isPending} onClick={() => settleMutation.mutate('void')}>
                Void
              </Button>
            </Tooltip>
            <Button size="xs" variant="subtle" color="gray" loading={unplaceMutation.isPending}
              onClick={() => unplaceMutation.mutate()}>
              <IconX size={13} />
            </Button>
          </Group>
        )}
      </Box>
    </Card>
  )
}

// ─── Slip Detail Modal ────────────────────────────────────────────────────────

function SlipDetailModal({
  opened,
  onClose,
  slipDate,
  source,
  slipNr,
  slipName,
}: {
  opened: boolean
  onClose: () => void
  slipDate: string
  source: string
  slipNr: number
  slipName: string
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['slip-detail', slipDate, source],
    queryFn: () => bettingSlipsApi.get(slipDate, source as any),
    enabled: opened,
    staleTime: 60_000,
  })

  // data.slips kann ein Array oder ein Objekt {slips:[...]} sein
  const slipsList: any[] = Array.isArray(data?.slips)
    ? data.slips
    : (data?.slips?.slips ?? [])
  const slip = slipsList.find((s: any) => s.slip_nr === slipNr) ?? null

  const picks: any[] = slip?.picks ?? []

  // Group by fixture
  const gameGroups: { fixtureId: number; home: string; away: string; league: string; kickoff: string; statusShort?: string | null; homeScore?: number | null; awayScore?: number | null; picks: any[] }[] = []
  const seen = new Map<number, number>()
  for (const pick of picks) {
    const fid = pick.fixture_id
    if (!seen.has(fid)) {
      seen.set(fid, gameGroups.length)
      gameGroups.push({
        fixtureId: fid,
        home: pick.home,
        away: pick.away,
        league: pick.league,
        kickoff: pick.kickoff,
        statusShort: pick.fixture_status_short ?? null,
        homeScore: pick.fixture_home_score ?? null,
        awayScore: pick.fixture_away_score ?? null,
        picks: [],
      })
    }
    gameGroups[seen.get(fid)!].picks.push(pick)
  }

  const resultColor = (r: string | null) =>
    r === 'win' ? 'green' : r === 'loss' ? 'red' : r === 'push' ? 'yellow' : 'gray'

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Text fw={700}>{slipName} · {dayjs(slipDate).format('DD.MM.YYYY')}</Text>}
      size="lg"
    >
      {isLoading && <Center py="xl"><Loader /></Center>}

      {!isLoading && !slip && (
        <Text c="dimmed" ta="center" py="md">Keine Daten gefunden.</Text>
      )}

      {slip && (
        <Stack gap="sm">
          <Group gap="xs">
            <Badge color="grape" variant="filled">{slip.combined_odd?.toFixed(2)}</Badge>
            <Text size="sm" c="dimmed">{gameGroups.length} Spiele</Text>
            {slip.reasoning && (
              <Text size="xs" c="dimmed" style={{ flex: 1 }}>{slip.reasoning}</Text>
            )}
          </Group>

          {gameGroups.map((game, gi) => (
            <Box key={game.fixtureId}>
              {gi > 0 && <Divider />}
              <Group gap={6} mt={gi > 0 ? 8 : 0} mb={4}>
                <Text size="xs" c="dimmed" fw={500}>{game.kickoff}</Text>
                <Text size="xs" c="dimmed">·</Text>
                <Text size="xs" c="dimmed">{game.league}</Text>
                {game.statusShort && ['FT', 'AET', 'PEN'].includes(game.statusShort) && (
                  <>
                    <Text size="xs" c="dimmed">·</Text>
                    <Text size="xs" fw={700}>
                      {game.homeScore} : {game.awayScore}
                    </Text>
                  </>
                )}
              </Group>
              <Text size="sm" fw={600} mb={6}>{game.home} – {game.away}</Text>
              {game.picks.map((pick: any, pi: number) => (
                <Box key={pi} mb={6} pl="sm"
                  style={{ borderLeft: `3px solid var(--mantine-color-${resultColor(pick.result)}-5)` }}>
                  <Group justify="space-between">
                    <Group gap={4}>
                      <Text size="xs" c="dimmed">{pick.market}:</Text>
                      <Text size="xs" fw={500}>{pick.pick}</Text>
                      {pick.betbuilder && (
                        <Badge size="xs" variant="outline" color="orange">BB</Badge>
                      )}
                    </Group>
                    <Group gap={8}>
                      <Badge size="xs" variant="light" color="blue">{pick.odd?.toFixed(2)}</Badge>
                      {pick.result && (
                        <Badge size="xs" variant="filled" color={resultColor(pick.result)}>
                          {pick.result === 'win' ? '✓' : pick.result === 'loss' ? '✗' : '~'}
                        </Badge>
                      )}
                    </Group>
                  </Group>
                  {pick.reasoning && (
                    <Text size="xs" c="dimmed" mt={2} style={{ fontStyle: 'italic' }}>
                      {pick.reasoning}
                    </Text>
                  )}
                </Box>
              ))}
            </Box>
          ))}
        </Stack>
      )}
    </Modal>
  )
}


// ─── History tab ──────────────────────────────────────────────────────────────

function HistoryTab() {
  const queryClient = useQueryClient()
  const [histSource, setHistSource] = useState<'all' | 'ai' | 'pattern' | 'custom'>('all')
  const [detailSlip, setDetailSlip] = useState<{ slipDate: string; source: string; slipNr: number; name: string } | null>(null)
  const yesterday = dayjs().subtract(1, 'day').format('YYYY-MM-DD')

  const { data: history = [], isLoading, refetch } = useQuery({
    queryKey: ['betting-history', histSource],
    queryFn: () => bettingSlipsApi.getHistory(21, histSource === 'all' ? undefined : histSource),
    staleTime: 60_000,
  })

  const evaluateMutation = useMutation({
    mutationFn: ({ slipDate, source }: { slipDate: string; source?: string }) =>
      bettingSlipsApi.evaluate(slipDate, source),
    onSuccess: () => {
      refetch()
      queryClient.invalidateQueries({ queryKey: ['betting-stats'] })
    },
  })

  const evaluateYesterdayMutation = useMutation({
    mutationFn: () => bettingSlipsApi.evaluate(yesterday),
    onSuccess: () => {
      refetch()
      queryClient.invalidateQueries({ queryKey: ['betting-stats'] })
    },
  })

  const sourceLabel = (s: string) => s === 'ai' ? 'KI' : s === 'custom' ? 'Eigener' : 'Pattern'
  const sourceColor = (s: string) => s === 'ai' ? 'violet' : s === 'custom' ? 'grape' : 'blue'

  // Count open (placed but not settled) bets across all history
  const openCount = history.reduce(
    (n, day) => n + day.slips.filter(s => s.placed?.status === 'placed').length, 0
  )

  return (
    <Stack gap="md">
      {/* Morgenroutine */}
      <Card withBorder p="sm" bg="blue.0">
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Stack gap={2}>
            <Text fw={600} size="sm">Morgenroutine – Vortag auswerten</Text>
            <Text size="xs" c="dimmed">
              Wertet alle angespielten Scheine vom {dayjs(yesterday).format('DD.MM.YYYY')} automatisch aus.
            </Text>
          </Stack>
          <Button
            leftSection={<IconPlayerPlay size={14} />}
            size="sm"
            loading={evaluateYesterdayMutation.isPending}
            onClick={() => evaluateYesterdayMutation.mutate()}
          >
            Vortag auswerten
          </Button>
        </Group>
        {evaluateYesterdayMutation.data && (
          <Alert mt="xs" color="green" variant="light" p="xs">
            <Text size="xs">
              Ausgewertet: {evaluateYesterdayMutation.data.evaluated} ·
              Gewonnen: {evaluateYesterdayMutation.data.won} ·
              Verloren: {evaluateYesterdayMutation.data.lost}
              {evaluateYesterdayMutation.data.skipped > 0 && ` · Übersprungen: ${evaluateYesterdayMutation.data.skipped}`}
            </Text>
          </Alert>
        )}
      </Card>

      <Group justify="space-between">
        <Group gap="xs">
          <Text fw={600}>Letzte 21 Tage</Text>
          {openCount > 0 && (
            <Badge size="sm" color="blue">{openCount} offen</Badge>
          )}
        </Group>
        <SegmentedControl
          size="xs"
          value={histSource}
          onChange={v => setHistSource(v as any)}
          data={[
            { label: 'Alle', value: 'all' },
            { label: 'Pattern', value: 'pattern' },
            { label: 'KI', value: 'ai' },
            { label: 'Eigene', value: 'custom' },
          ]}
        />
      </Group>

      {isLoading && <Center py="xl"><Loader /></Center>}

      {!isLoading && history.length === 0 && (
        <Center py="xl">
          <Text c="dimmed">Keine gespeicherten Scheine gefunden.</Text>
        </Center>
      )}

      {detailSlip && (
        <SlipDetailModal
          opened={!!detailSlip}
          onClose={() => setDetailSlip(null)}
          slipDate={detailSlip.slipDate}
          source={detailSlip.source}
          slipNr={detailSlip.slipNr}
          slipName={detailSlip.name}
        />
      )}

      {history.map(day => {
        const dayOpen = day.slips.filter(s => s.placed?.status === 'placed').length
        return (
          <Card withBorder key={day.slip_date} p="xs">
            <Group mb="xs" justify="space-between">
              <Group gap="xs">
                <Text fw={700} size="sm">{dayjs(day.slip_date).format('dd, DD.MM.YYYY')}</Text>
                <Text size="xs" c="dimmed">
                  {day.slips.filter(s => s.placed).length}/{day.slips.length} angespielt
                </Text>
                {dayOpen > 0 && (
                  <Badge size="xs" color="blue">{dayOpen} offen</Badge>
                )}
              </Group>
              {dayOpen > 0 && (
                <Tooltip label="Ausstehende Scheine dieses Tages auswerten">
                  <Button
                    size="xs" variant="light"
                    leftSection={<IconPlayerPlay size={12} />}
                    loading={evaluateMutation.isPending}
                    onClick={() => evaluateMutation.mutate({ slipDate: day.slip_date })}
                  >
                    Auswerten
                  </Button>
                </Tooltip>
              )}
            </Group>
            <Table highlightOnHover fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Typ</Table.Th>
                  <Table.Th>Schein</Table.Th>
                  <Table.Th style={{ textAlign: 'right' }}>Quote</Table.Th>
                  <Table.Th style={{ textAlign: 'right' }}>Einsatz</Table.Th>
                  <Table.Th style={{ textAlign: 'center' }}>Status</Table.Th>
                  <Table.Th style={{ textAlign: 'right' }}>Return</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {day.slips.map((slip, i) => {
                  const pb = slip.placed
                  const returnVal = pb?.status === 'won' && pb.stake
                    ? pb.stake * pb.combined_odd
                    : null
                  return (
                    <Table.Tr
                      key={i}
                      style={{ opacity: pb ? 1 : 0.5, cursor: 'pointer' }}
                      onClick={() => setDetailSlip({ slipDate: day.slip_date, source: slip.source, slipNr: slip.slip_nr, name: slip.name })}
                    >
                      <Table.Td>
                        <Badge size="xs" color={sourceColor(slip.source)} variant="light">
                          {sourceLabel(slip.source)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Text size="xs" fw={500}>{slip.name}</Text>
                      </Table.Td>
                      <Table.Td style={{ textAlign: 'right' }}>
                        <Badge size="xs" color={targetColor(slip.combined_odd, slip.slip_nr)} variant="filled">
                          {slip.combined_odd?.toFixed(2) ?? '–'}
                        </Badge>
                      </Table.Td>
                      <Table.Td style={{ textAlign: 'right' }}>
                        <Text size="xs" c="dimmed">
                          {pb?.stake != null ? `${Number(pb.stake).toFixed(2)} €` : '–'}
                        </Text>
                      </Table.Td>
                      <Table.Td style={{ textAlign: 'center' }}>
                        {pb ? (
                          <Badge size="xs" color={statusColor(pb.status)} variant="filled">
                            {statusLabel(pb.status)}
                          </Badge>
                        ) : (
                          <Text size="xs" c="dimmed">–</Text>
                        )}
                      </Table.Td>
                      <Table.Td style={{ textAlign: 'right' }}>
                        <Text size="xs" c={returnVal ? 'green' : 'dimmed'}>
                          {returnVal != null ? `${returnVal.toFixed(2)} €` : '–'}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          </Card>
        )
      })}
    </Stack>
  )
}

// ─── Today tab ────────────────────────────────────────────────────────────────

function TodayTab() {
  const queryClient = useQueryClient()
  const today = dayjs().format('YYYY-MM-DD')
  const [source, setSource] = useState<'ai' | 'pattern'>('pattern')
  const [strategy] = useLocalStorage<SlipStrategy[]>({ key: 'qf-strategy-v5', defaultValue: STRATEGY_DEFAULTS })

  const { data: existing, isLoading } = useQuery({
    queryKey: ['betting-slips', today, source],
    queryFn: () => bettingSlipsApi.get(today, source),
    retry: false,
  })

  const { data: placedBets = [], refetch: refetchPlaced } = useQuery({
    queryKey: ['placed-bets', today, source],
    queryFn: () => bettingSlipsApi.getPlacedBets(today, source),
  })

  const aiMutation = useMutation({
    mutationFn: (force: boolean) => bettingSlipsApi.generate(today, force),
    onSuccess: (data) => {
      queryClient.setQueryData(['betting-slips', today, 'ai'], data)
      setSource('ai')
    },
  })

  const patternMutation = useMutation({
    mutationFn: (force: boolean) => bettingSlipsApi.generatePattern(today, force),
    onSuccess: (data) => {
      queryClient.setQueryData(['betting-slips', today, 'pattern'], data)
      setSource('pattern')
    },
  })

  const activeMutation = source === 'ai' ? aiMutation : patternMutation
  const slipsData = activeMutation.data ?? existing
  const slips: any[] = slipsData?.slips?.slips ?? []
  const daySummary: string = slipsData?.slips?.day_summary ?? ''
  const isPending = aiMutation.isPending || patternMutation.isPending

  const handleRefresh = () => {
    refetchPlaced()
    queryClient.invalidateQueries({ queryKey: ['betting-stats', source] })
    queryClient.invalidateQueries({ queryKey: ['betting-history'] })
  }

  return (
    <Stack gap="md">
      {/* Source switcher + actions */}
      <Group justify="space-between" wrap="wrap" gap="xs">
        <Text size="sm" c="dimmed">
          {dayjs().format('DD.MM.YYYY')} · Zielquote 8–12
        </Text>
        <Group gap="xs">
          <SegmentedControl
            size="xs"
            value={source}
            onChange={v => setSource(v as 'ai' | 'pattern')}
            data={[
              { label: 'Pattern', value: 'pattern' },
              { label: 'KI (Claude)', value: 'ai' },
            ]}
          />
          {slipsData && (
            <Tooltip label={source === 'pattern' ? 'Pattern neu berechnen' : 'KI neu generieren'}>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconRefresh size={13} />}
                loading={isPending}
                onClick={() => source === 'pattern' ? patternMutation.mutate(true) : aiMutation.mutate(true)}
              >
                Neu
              </Button>
            </Tooltip>
          )}
        </Group>
      </Group>

      {/* Stats */}
      <StatsBar source={source} />

      {isLoading && <Center py="xl"><Loader /></Center>}

      {(aiMutation.isError || patternMutation.isError) && (
        <Alert color="red" icon={<IconAlertCircle size={16} />}>
          {(activeMutation.error as any)?.response?.data?.detail ?? 'Fehler beim Generieren'}
        </Alert>
      )}

      {!slipsData && !isLoading && !isPending && !aiMutation.isError && !patternMutation.isError && (
        <Card withBorder>
          <Center py="xl">
            <Stack align="center" gap="sm">
              <IconTicket size={48} color="gray" />
              <Text c="dimmed">Noch keine {source === 'pattern' ? 'Pattern-Scheine' : 'KI-Scheine'} für heute.</Text>
              {source === 'pattern' ? (
                <>
                  <Button
                    variant="filled" color="blue"
                    leftSection={<IconChartBar size={15} />}
                    loading={patternMutation.isPending}
                    onClick={() => patternMutation.mutate(false)}
                  >
                    Pattern-Scheine erstellen
                  </Button>
                  <Text size="xs" c="dimmed">Rein algorithmisch aus MRP, Elo, Form und Torwahrscheinlichkeit.</Text>
                </>
              ) : (
                <>
                  <Button
                    variant="filled" color="violet"
                    leftSection={<IconRobot size={15} />}
                    loading={aiMutation.isPending}
                    onClick={() => aiMutation.mutate(false)}
                  >
                    KI-Scheine generieren
                  </Button>
                  <Text size="xs" c="dimmed">Claude analysiert Quoten und erstellt 3 Scheine.</Text>
                </>
              )}
            </Stack>
          </Center>
        </Card>
      )}

      {isPending && (
        <Card withBorder>
          <Center py="xl">
            <Stack align="center" gap="sm">
              <Loader color={source === 'pattern' ? 'blue' : 'violet'} />
              <Text c="dimmed">
                {source === 'pattern' ? 'Berechne Pattern-Scheine…' : 'Claude erstellt Scheine…'}
              </Text>
              {source === 'ai' && <Text size="xs" c="dimmed">Das kann 30–60 Sekunden dauern.</Text>}
            </Stack>
          </Center>
        </Card>
      )}

      {slips.length > 0 && (
        <>
          {daySummary && (
            <Alert
              color={source === 'pattern' ? 'blue' : 'violet'}
              variant="light"
              icon={source === 'pattern' ? <IconChartBar size={16} /> : <IconRobot size={16} />}
            >
              <Text size="sm">{daySummary}</Text>
            </Alert>
          )}

          {source === 'pattern' && (
            <Alert color="gray" variant="outline" p="xs">
              <Text size="xs" c="dimmed">
                <Text span fw={600}>Faire Quoten</Text> — berechnet aus unseren Modell-Wahrscheinlichkeiten (MRP).
                Keine Buchmacher-Quoten. Zielquote 8–12 pro Schein.
              </Text>
            </Alert>
          )}

          <Grid gutter="md">
            {slips.map((slip: any) => {
              const pb = placedBets.find(b => b.slip_nr === slip.slip_nr) ?? null
              const slipName = source === 'pattern' && slip.name ? slip.name : `Schein ${slip.slip_nr}`
              const strategyStake = strategy.find(s => s.name === slipName && s.active)?.stake
              return (
                <GridCol key={slip.slip_nr} span={{ base: 12, md: 4 }}>
                  <SlipCard
                    slip={slip}
                    source={source}
                    slipDate={today}
                    placedBet={pb}
                    onRefresh={handleRefresh}
                    defaultStake={strategyStake}
                  />
                </GridCol>
              )
            })}
          </Grid>

          <Text size="xs" c="dimmed" ta="right">
            {source === 'pattern' ? 'Pattern-Modell' : 'KI-Modell'} ·
            Generiert: {slipsData?.generated_at ? dayjs(slipsData.generated_at).format('DD.MM.YYYY HH:mm') : '–'} ·
            {slipsData?.model_version ?? '–'}
          </Text>
        </>
      )}
    </Stack>
  )
}

// ─── Strategy config ──────────────────────────────────────────────────────────

interface SlipStrategy {
  name: string
  kelly_q: number   // 1/4 Kelly % of bankroll (reference)
  stake: number     // EUR
  active: boolean
  // legacy fields kept for localStorage compat
  wr_backtest?: number
  ev_backtest?: number
  note?: string
}

// 25 € Tageseinsatz bei 140 € Bankroll: 10+10+5
const STRATEGY_DEFAULTS: SlipStrategy[] = [
  { name: 'Kombi 1',              kelly_q: 4.3, stake: 10, active: true },
  { name: 'Kombi 2',              kelly_q: 4.3, stake: 10, active: true },
  { name: 'Favoriten Auswärts',   kelly_q: 2.1, stake: 5,  active: true },
]

// ─── Strategie tab ────────────────────────────────────────────────────────────

function StrategieTab() {
  const queryClient = useQueryClient()
  const today = dayjs().format('YYYY-MM-DD')

  const [bankroll, setBankroll] = useLocalStorage<number>({ key: 'qf-bankroll-v2', defaultValue: 140 })
  const [strategy, setStrategy] = useLocalStorage<SlipStrategy[]>({
    key: 'qf-strategy-v5',
    defaultValue: STRATEGY_DEFAULTS,
  })

  const { data: stats } = useQuery({
    queryKey: ['betting-stats-all'],
    queryFn: () => bettingSlipsApi.getStats({ source: 'pattern' }),
    staleTime: 60_000,
  })

  const { data: statsBySlip = [] } = useQuery({
    queryKey: ['betting-stats-by-slip'],
    queryFn: () => bettingSlipsApi.getStatsBySlip('pattern'),
    staleTime: 60_000,
  })

  const placeMutation = useMutation({
    mutationFn: (source: 'pattern' | 'ai') => {
      const stakes: Record<string, number> = {}
      strategy.forEach(s => { if (s.active && s.stake > 0) stakes[s.name] = s.stake })
      return bettingSlipsApi.placeStrategy(today, source, stakes)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['placed-bets'] })
      queryClient.invalidateQueries({ queryKey: ['betting-history'] })
      queryClient.invalidateQueries({ queryKey: ['betting-stats'] })
    },
  })

  const totalProfit = stats?.net_profit ?? 0
  const currentBankroll = bankroll + totalProfit
  const roi = stats?.total_staked ? (totalProfit / stats.total_staked) * 100 : null
  const dailyStake = strategy.filter(s => s.active).reduce((sum, s) => sum + s.stake, 0)

  const updateStake = (name: string, stake: number) =>
    setStrategy(prev => prev.map(s => s.name === name ? { ...s, stake } : s))
  const toggleActive = (name: string) =>
    setStrategy(prev => prev.map(s => s.name === name ? { ...s, active: !s.active } : s))

  // Match live stats to strategy rows
  const liveMap = Object.fromEntries(statsBySlip.map(s => [s.name, s]))

  return (
    <Stack gap="md">
      {/* Bankroll panel */}
      <Grid gutter="md">
        <GridCol span={{ base: 12, sm: 4 }}>
          <Card withBorder h="100%">
            <Text size="xs" c="dimmed" mb={4}>Startkapital</Text>
            <NumberInput
              size="md"
              value={bankroll}
              onChange={v => setBankroll(Number(v) || 200)}
              min={10} step={10} decimalScale={0}
              rightSection={<Text size="sm" c="dimmed" pr={4}>€</Text>}
              styles={{ input: { fontWeight: 700, fontSize: 22 } }}
            />
            <Text size="xs" c="dimmed" mt={4}>In localStorage gespeichert</Text>
          </Card>
        </GridCol>

        <GridCol span={{ base: 12, sm: 4 }}>
          <Card withBorder h="100%">
            <Group justify="space-between" align="flex-start">
              <Stack gap={2}>
                <Text size="xs" c="dimmed">Aktuelles Kapital</Text>
                <Text fw={800} size="xl" c={currentBankroll >= bankroll ? 'green' : 'red'}>
                  {currentBankroll.toFixed(2)} €
                </Text>
                <Text size="xs" c={totalProfit >= 0 ? 'green' : 'red'}>
                  {totalProfit >= 0 ? '+' : ''}{totalProfit.toFixed(2)} € P&L
                </Text>
              </Stack>
              <RingProgress
                size={70} thickness={6}
                sections={[{
                  value: Math.min(100, Math.max(0, (currentBankroll / bankroll) * 100)),
                  color: currentBankroll >= bankroll ? 'green' : 'red',
                }]}
                label={<Text ta="center" size="xs" fw={700}>{((currentBankroll / bankroll) * 100).toFixed(0)}%</Text>}
              />
            </Group>
            {roi !== null && (
              <Text size="xs" c="dimmed" mt={4}>ROI auf Einsatz: {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%</Text>
            )}
          </Card>
        </GridCol>

        <GridCol span={{ base: 12, sm: 4 }}>
          <Card withBorder h="100%">
            <Text size="xs" c="dimmed" mb={4}>Heutige Aktion</Text>
            <Text fw={700} size="lg" mb="xs">{dailyStake} € Tageseinsatz</Text>
            <Stack gap={6}>
              <Button
                size="sm" fullWidth
                leftSection={<IconChartBar size={14} />}
                loading={placeMutation.isPending}
                onClick={() => placeMutation.mutate('pattern')}
              >
                Pattern spielen
              </Button>
              <Button
                size="sm" fullWidth variant="light" color="violet"
                leftSection={<IconRobot size={14} />}
                loading={placeMutation.isPending}
                onClick={() => placeMutation.mutate('ai')}
              >
                KI spielen
              </Button>
            </Stack>
          </Card>
        </GridCol>
      </Grid>

      {placeMutation.data && (
        <Alert color="green" variant="light" p="xs">
          <Text size="xs">{placeMutation.data.created} Scheine angespielt, {placeMutation.data.skipped} übersprungen.</Text>
        </Alert>
      )}

      {/* Strategy table */}
      <Card withBorder p={0}>
        <Group p="sm" pb="xs">
          <IconTargetArrow size={16} />
          <Text fw={600} size="sm">Einsatzstrategie — ¼ Kelly (Basis: 10-Tage-Backtest)</Text>
        </Group>
        <Divider />
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Schein</Table.Th>
              <Table.Th style={{ textAlign: 'center' }}>Win-Rate</Table.Th>
              <Table.Th style={{ textAlign: 'center' }}>EV</Table.Th>
              <Table.Th style={{ textAlign: 'center' }}>Scheine</Table.Th>
              <Table.Th style={{ textAlign: 'right' }}>Einsatz €</Table.Th>
              <Table.Th style={{ textAlign: 'center' }}>P&L</Table.Th>
              <Table.Th style={{ textAlign: 'center' }}>Aktiv</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {strategy.map((row) => {
              const live = liveMap[row.name]
              const evColor = !live ? 'dimmed' : live.ev > 0 ? 'green' : 'red'
              return (
                <Table.Tr key={row.name} style={{ opacity: row.active ? 1 : 0.45 }}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{row.name}</Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'center' }}>
                    {live ? (
                      <Tooltip label={`${live.won}W / ${live.lost}L`} withArrow fz="xs">
                        <Badge size="sm"
                          color={live.win_rate >= 0.45 ? 'green' : live.win_rate >= 0.25 ? 'yellow' : 'red'}
                          variant="light">
                          {(live.win_rate * 100).toFixed(0)}%
                        </Badge>
                      </Tooltip>
                    ) : <Text size="xs" c="dimmed">–</Text>}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'center' }}>
                    <Text size="sm" fw={600} c={evColor}>
                      {live ? `${live.ev >= 0 ? '+' : ''}${(live.ev * 100).toFixed(0)}%` : '–'}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'center' }}>
                    <Text size="xs" c="dimmed">{live ? live.total : '–'}</Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <NumberInput size="xs" value={row.stake}
                      onChange={v => updateStake(row.name, Number(v) || 0)}
                      min={0} step={1} decimalScale={0} disabled={!row.active} w={70}
                      styles={{ input: { textAlign: 'right', fontWeight: 600 } }}
                    />
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'center' }}>
                    {live ? (
                      <Text size="xs" fw={600} c={live.profit >= 0 ? 'green' : 'red'}>
                        {live.profit >= 0 ? '+' : ''}{live.profit.toFixed(2)} €
                      </Text>
                    ) : <Text size="xs" c="dimmed">–</Text>}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'center' }}>
                    <Switch size="sm" checked={row.active} onChange={() => toggleActive(row.name)} color="green" />
                  </Table.Td>
                </Table.Tr>
              )
            })}
          </Table.Tbody>
          <Table.Tfoot>
            <Table.Tr>
              <Table.Td colSpan={4}><Text size="xs" fw={600} c="dimmed">Gesamt (aktiv)</Text></Table.Td>
              <Table.Td style={{ textAlign: 'right' }}>
                <Text size="sm" fw={700}>{dailyStake} €</Text>
              </Table.Td>
              <Table.Td>
                <Text size="xs" fw={600} c={totalProfit >= 0 ? 'green' : 'red'}>
                  {totalProfit >= 0 ? '+' : ''}{totalProfit.toFixed(2)} €
                </Text>
              </Table.Td>
              <Table.Td />
            </Table.Tr>
          </Table.Tfoot>
        </Table>
      </Card>

      {/* Progress bars */}
      <Card withBorder p="sm">
        <Text size="xs" fw={600} c="dimmed" mb="xs">Bankroll-Entwicklung</Text>
        <Stack gap={6}>
          <Group justify="space-between">
            <Text size="xs">Start</Text>
            <Text size="xs" fw={600}>{bankroll} €</Text>
          </Group>
          <Progress
            value={Math.min(100, (currentBankroll / (bankroll * 1.5)) * 100)}
            color={currentBankroll >= bankroll ? 'green' : 'red'}
            size="sm"
            radius="xl"
          />
          <Group justify="space-between">
            <Text size="xs" c="dimmed">
              {stats?.settled ?? 0} ausgewertet · {stats?.won ?? 0}W / {stats?.lost ?? 0}L
              {stats?.win_rate ? ` · ${(stats.win_rate * 100).toFixed(0)}% WR` : ''}
            </Text>
            <Text size="xs" fw={700} c={currentBankroll >= bankroll ? 'green' : 'red'}>
              Aktuell: {currentBankroll.toFixed(2)} €
            </Text>
          </Group>
        </Stack>
      </Card>

      <Alert color="yellow" variant="outline" p="xs">
        <Text size="xs" c="dimmed">
          ⚠ Einsätze basieren auf 10-Tage-Backtest (58 Scheine). Kelly-Werte werden belastbar nach ~180 Scheinen (30 Tage). Bis dahin: Einsätze konservativ halten.
        </Text>
      </Alert>
    </Stack>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

// ─── Custom Slip Builder ──────────────────────────────────────────────────────

function CustomSlipBuilder() {
  const today = dayjs().format('YYYY-MM-DD')
  const [slipDate, setSlipDate] = useState(today)
  const [selectedLeagues, setSelectedLeagues] = useState<string[]>([])
  const [selectedFixtures, setSelectedFixtures] = useState<string[]>([])
  const [targetOdd, setTargetOdd] = useState<number>(10)
  const [minPicks, setMinPicks] = useState<number | string>(3)
  const [maxPicks, setMaxPicks] = useState<number | string>(10)
  const [pickOddLo, setPickOddLo] = useState<number | string>(1.20)
  const [pickOddHi, setPickOddHi] = useState<number | string>(1.60)
  const [slipName, setSlipName] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [result, setResult] = useState<CustomSlip | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: leagues = [] } = useQuery({
    queryKey: ['leagues-list'],
    queryFn: () => leaguesApi.list(),
    staleTime: 300_000,
  })

  const { data: fixtures = [] } = useQuery({
    queryKey: ['fixtures-for-date', slipDate],
    queryFn: () => fixturesApi.today(slipDate),
    staleTime: 60_000,
  })

  const leagueOptions = leagues.map(l => ({
    value: String(l.id),
    label: `${l.name} (${l.country})`,
  }))

  const filteredFixtures = selectedLeagues.length > 0
    ? fixtures.filter(f => selectedLeagues.includes(String(f.league_id)))
    : fixtures

  const fixtureOptions = filteredFixtures.map(f => ({
    value: String(f.id),
    label: `${f.home_team_name ?? '?'} vs ${f.away_team_name ?? '?'} (${f.kickoff_utc ? dayjs(f.kickoff_utc).format('HH:mm') : '?'})`,
  }))

  const [saved, setSaved] = useState(false)
  const queryClient = useQueryClient()

  const generateMutation = useMutation({
    mutationFn: () => bettingSlipsApi.generateCustom({
      slip_date: slipDate,
      league_ids: selectedLeagues.length > 0 ? selectedLeagues.map(Number) : undefined,
      fixture_ids: selectedFixtures.length > 0 ? selectedFixtures.map(Number) : undefined,
      target_odd: targetOdd,
      min_picks: Number(minPicks),
      max_picks: Number(maxPicks),
      pick_odd_lo: Number(pickOddLo),
      pick_odd_hi: Number(pickOddHi),
      name: slipName || undefined,
    }),
    onSuccess: (data) => {
      setResult(data.slip)
      setSaved(false)
      setError(null)
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Unbekannter Fehler')
      setResult(null)
    },
  })

  const saveMutation = useMutation({
    mutationFn: () => bettingSlipsApi.saveCustom(slipDate, result!),
    onSuccess: () => {
      setSaved(true)
      queryClient.invalidateQueries({ queryKey: ['betting-history'] })
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Fehler beim Speichern')
    },
  })

  const picks = result?.picks ?? []
  // Group by fixture
  const gameGroups: { fixtureId: number; home: string; away: string; league: string; kickoff: string; picks: any[] }[] = []
  const seenFids = new Map<number, number>()
  for (const pick of picks) {
    const fid = pick.fixture_id
    if (!seenFids.has(fid)) {
      seenFids.set(fid, gameGroups.length)
      gameGroups.push({ fixtureId: fid, home: pick.home, away: pick.away, league: pick.league, kickoff: pick.kickoff, picks: [] })
    }
    gameGroups[seenFids.get(fid)!].picks.push(pick)
  }

  return (
    <Stack gap="md">
      <Card withBorder p="md">
        <Stack gap="md">
          <Text fw={600}>Parameter</Text>

          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
            <TextInput
              label="Datum"
              type="date"
              value={slipDate}
              onChange={e => { setSlipDate(e.target.value); setSelectedFixtures([]) }}
            />
            <TextInput
              label="Schein-Name (optional)"
              placeholder="z.B. Mein Custom Schein"
              value={slipName}
              onChange={e => setSlipName(e.target.value)}
            />
          </SimpleGrid>

          <MultiSelect
            label="Ligen (leer = alle verfügbaren)"
            placeholder="Ligen auswählen..."
            data={leagueOptions}
            value={selectedLeagues}
            onChange={v => { setSelectedLeagues(v); setSelectedFixtures([]) }}
            searchable
            clearable
          />

          <MultiSelect
            label={`Einzelne Spiele (optional, ${filteredFixtures.length} verfügbar)`}
            placeholder="Spiele auswählen oder leer lassen für alle..."
            data={fixtureOptions}
            value={selectedFixtures}
            onChange={setSelectedFixtures}
            searchable
            clearable
            disabled={filteredFixtures.length === 0}
          />

          <Box>
            <Text size="sm" fw={500} mb={6}>Zielquote: {targetOdd.toFixed(1)}</Text>
            <Slider
              min={2}
              max={100}
              step={0.5}
              value={targetOdd}
              onChange={setTargetOdd}
              marks={[
                { value: 5, label: '5x' },
                { value: 10, label: '10x' },
                { value: 20, label: '20x' },
                { value: 50, label: '50x' },
              ]}
            />
          </Box>

          <Button
            variant="subtle"
            size="xs"
            leftSection={advancedOpen ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
            onClick={() => setAdvancedOpen(o => !o)}
            style={{ alignSelf: 'flex-start' }}
          >
            Erweiterte Einstellungen
          </Button>

          <Collapse in={advancedOpen}>
            <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
              <NumberInput
                label="Min. Picks"
                min={1} max={20} value={minPicks}
                onChange={setMinPicks}
              />
              <NumberInput
                label="Max. Picks"
                min={1} max={20} value={maxPicks}
                onChange={setMaxPicks}
              />
              <NumberInput
                label="Pick-Quote min"
                min={1.01} max={10} step={0.05} decimalScale={2}
                value={pickOddLo}
                onChange={setPickOddLo}
              />
              <NumberInput
                label="Pick-Quote max"
                min={1.01} max={20} step={0.05} decimalScale={2}
                value={pickOddHi}
                onChange={setPickOddHi}
              />
            </SimpleGrid>
          </Collapse>

          <Button
            leftSection={<IconWand size={16} />}
            loading={generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
          >
            Schein generieren
          </Button>
        </Stack>
      </Card>

      {error && (
        <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />}>
          {error}
        </Alert>
      )}

      {result && (
        <Card withBorder p={0} style={{ overflow: 'hidden' }}>
          <Box px="sm" py={8} style={{ background: 'var(--mantine-color-grape-8)' }}>
            <Group justify="space-between">
              <Stack gap={0}>
                <Text size="sm" fw={700} c="white">{result.name}</Text>
                <Text size="xs" c="rgba(255,255,255,0.7)">
                  {gameGroups.length}-er Kombiwette · @ {result.combined_odd.toFixed(2)}
                </Text>
              </Stack>
              <Group gap="xs">
                <Badge color="grape" variant="filled" size="lg">
                  {result.combined_odd.toFixed(2)}
                </Badge>
                {saved ? (
                  <Badge color="green" variant="filled" size="sm" leftSection={<IconCheck size={12} />}>
                    Gespeichert
                  </Badge>
                ) : (
                  <Button
                    size="xs" variant="white" color="grape"
                    loading={saveMutation.isPending}
                    onClick={() => saveMutation.mutate()}
                  >
                    Speichern
                  </Button>
                )}
              </Group>
            </Group>
          </Box>

          <Stack gap={0} p="sm">
            {gameGroups.map((game, gi) => (
              <Box key={game.fixtureId}>
                {gi > 0 && <Divider my={6} />}
                <Group gap={6} mb={4}>
                  <Text size="xs" c="dimmed">{game.kickoff}</Text>
                  <Text size="xs" c="dimmed">·</Text>
                  <Text size="xs" c="dimmed">{game.league}</Text>
                </Group>
                <Text size="sm" fw={600} mb={4}>
                  {game.home} vs {game.away}
                </Text>
                {game.picks.map((pick: any, pi: number) => (
                  <Box key={pi} mb={6} pl="xs"
                    style={{ borderLeft: pick.betbuilder ? '2px solid var(--mantine-color-orange-5)' : undefined }}>
                    <Group justify="space-between">
                      <Group gap={4}>
                        <Text size="xs" c="dimmed">{pick.market}:</Text>
                        <Text size="xs" fw={500}>{pick.pick}</Text>
                        {pick.betbuilder && <Badge size="xs" color="orange" variant="outline">BB</Badge>}
                      </Group>
                      <Badge variant="light" color="blue" size="xs">
                        {pick.odd?.toFixed(2)}
                      </Badge>
                    </Group>
                    {pick.reasoning && (
                      <Text size="xs" c="dimmed" mt={2} style={{ fontStyle: 'italic' }}>
                        {pick.reasoning}
                      </Text>
                    )}
                  </Box>
                ))}
              </Box>
            ))}
          </Stack>

          {result.reasoning && (
            <Box px="sm" pb="sm">
              <Text size="xs" c="dimmed">{result.reasoning}</Text>
            </Box>
          )}
        </Card>
      )}
    </Stack>
  )
}


export function BettingSlipsPage() {
  return (
    <Stack gap="md">
      <Group gap="xs">
        <IconTicket size={22} />
        <Title order={2}>Wettscheine</Title>
      </Group>

      <Tabs defaultValue="strategie" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="strategie" leftSection={<IconTargetArrow size={14} />}>
            Strategie
          </Tabs.Tab>
          <Tabs.Tab value="heute" leftSection={<IconTicket size={14} />}>
            Heute
          </Tabs.Tab>
          <Tabs.Tab value="verlauf" leftSection={<IconHistory size={14} />}>
            Verlauf
          </Tabs.Tab>
          <Tabs.Tab value="custom" leftSection={<IconWand size={14} />}>
            Eigener Schein
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="strategie">
          <StrategieTab />
        </Tabs.Panel>

        <Tabs.Panel value="heute">
          <TodayTab />
        </Tabs.Panel>

        <Tabs.Panel value="verlauf">
          <HistoryTab />
        </Tabs.Panel>

        <Tabs.Panel value="custom">
          <CustomSlipBuilder />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}
