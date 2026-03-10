import {
  Stack, Title, Group, Text, Select, Badge,
  Loader, Center, Image, Grid, GridCol, ScrollArea, Paper
} from '@mantine/core'
import { useNavigate, useParams } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLeagues } from '../hooks/useLeagues'
import { useUiStore } from '../store/uiStore'
import { standingsApi, fixturesApi, leaguesApi } from '../api'
import { leagueLogoUrl, countryFlagUrl } from '../types'
import { StandingsTable } from '../components/tables/StandingsTable'
import { MatchdayView } from '../components/tables/MatchdayView'

export function LeaguePage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const leagueId = Number(id)
  const { data: leagues = [] } = useLeagues()
  const { selectedSeason, setSeason } = useUiStore()

  const league = leagues.find(l => l.id === leagueId)

  // ── Spieltage laden ────────────────────────────────────────────
  const { data: matchdays = [] } = useQuery({
    queryKey: ['matchdays', leagueId, selectedSeason],
    queryFn: () => standingsApi.matchdays(leagueId, selectedSeason),
    enabled: !!leagueId,
  })

  // Aktueller Spieltag = nächster mit mind. 1 offenen Spiel (NS),
  // sonst der letzte abgeschlossene
  const { data: upcomingFixtures = [] } = useQuery({
    queryKey: ['upcoming-check', leagueId, selectedSeason],
    queryFn: () => fixturesApi.list({ league_id: leagueId, season_year: selectedSeason, status: 'NS', limit: 1 }),
    enabled: !!leagueId,
  })
  const nextMatchday = upcomingFixtures[0]?.matchday ?? null
  const lastMatchday = matchdays.length > 0 ? matchdays[matchdays.length - 1] : 1
  const defaultMatchday = nextMatchday ?? lastMatchday

  const [selectedMatchday, setSelectedMatchday] = useState<number | null>(null)
  const activeMatchday = selectedMatchday ?? defaultMatchday

  // ── Tabelle bis zum aktiven Spieltag ─────────────────────────
  const { data: standings = [], isLoading: standingsLoading } = useQuery({
    queryKey: ['standings', leagueId, selectedSeason, activeMatchday],
    queryFn: () => standingsApi.get(leagueId, selectedSeason, activeMatchday),
    enabled: !!leagueId && activeMatchday > 0,
  })

  const { data: leagueElo = [] } = useQuery({
    queryKey: ['league-elo', leagueId, selectedSeason],
    queryFn: () => leaguesApi.elo(leagueId, selectedSeason),
    enabled: !!leagueId,
  })

  const eloByTeam = Object.fromEntries(
    leagueElo.map(row => [row.team_id, row.elo_overall])
  ) as Record<number, number>

  // Prüfen ob es Lücken in den Spieltagen gibt (z.B. Knockout-Runden bei CL)
  const hasGaps = matchdays.some((md, i) => i > 0 && md !== matchdays[i - 1] + 1)
  const knockoutLabels: Record<number, string> = {
    32: 'Round of 32', 16: 'Round of 16', 8: 'Viertelfinale',
    4: 'Halbfinale', 3: 'Spiel um Platz 3', 2: 'Finale',
  }
  const matchdayOptions = matchdays.map(md => {
    const label = hasGaps && knockoutLabels[md]
      ? knockoutLabels[md]
      : `Spieltag ${md}`
    return { value: String(md), label }
  })

  if (!league) return <Text c="dimmed">Liga nicht gefunden.</Text>

  return (
    <Stack gap="md">
      {/* ── Liga-Header ──────────────────────────────────────── */}
      <Group align="center" gap="md">
        <Image
          src={leagueLogoUrl(leagueId)}
          w={48} h={48} fit="contain"
          fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
        />
        <Stack gap={2}>
          <Group gap="xs">
            <Title order={2}>{league.name}</Title>
            <Badge variant="outline" color="green">Liga {league.tier}</Badge>
          </Group>
          <Group gap={6}>
            <Image
              src={countryFlagUrl(league.country)}
              w={18} h={13} fit="contain"
              fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
            />
            <Text c="dimmed" size="sm">{league.country}</Text>
          </Group>
        </Stack>

        <Select
          label="Saison"
          value={String(selectedSeason)}
          onChange={v => v && setSeason(Number(v))}
          data={['2022', '2023', '2024', '2025'].map(y => ({
            value: y,
            label: `${y}/${Number(y) + 1}`,
          }))}
          size="xs"
          w={120}
          ml="auto"
        />
      </Group>

      {/* ── Hauptlayout: Tabelle links, Spieltag rechts ──────── */}
      <Grid gutter="md">
        {/* Tabelle */}
        <GridCol span={{ base: 12, md: 7 }}>
          <Paper withBorder p="md" radius="md">
            <Group justify="space-between" mb="sm">
              <Text fw={600}>Tabelle nach {matchdayOptions.find(o => o.value === String(activeMatchday))?.label ?? `Spieltag ${activeMatchday}`}</Text>
              <Text size="xs" c="dimmed">{standings.length} Vereine · {selectedSeason}/{selectedSeason + 1}</Text>
            </Group>
            {standingsLoading ? (
              <Center py="xl"><Loader /></Center>
            ) : (
              <ScrollArea>
                <StandingsTable
                  standings={standings}
                  eloByTeam={eloByTeam}
                  onTeamClick={(teamId) => navigate(`/team/${teamId}?season_year=${selectedSeason}&league_id=${leagueId}`)}
                />
              </ScrollArea>
            )}
          </Paper>
        </GridCol>

        {/* Spieltag */}
        <GridCol span={{ base: 12, md: 5 }}>
          <Paper withBorder p="md" radius="md">
            <Group justify="space-between" mb="sm">
              <Text fw={600}>Spieltag</Text>
              <Select
                value={String(activeMatchday)}
                onChange={v => v && setSelectedMatchday(Number(v))}
                data={matchdayOptions}
                size="xs"
                w={150}
                searchable
                disabled={matchdays.length === 0}
              />
            </Group>

            <MatchdayView
              leagueId={leagueId}
              seasonYear={selectedSeason}
              eloByTeam={eloByTeam}
              matchday={activeMatchday}
              matchdays={matchdays}
              onMatchdayChange={md => setSelectedMatchday(md)}
            />
          </Paper>
        </GridCol>
      </Grid>
    </Stack>
  )
}
