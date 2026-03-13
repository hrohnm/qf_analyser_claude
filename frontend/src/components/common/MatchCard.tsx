import { Group, Text, Badge, Avatar, Stack, Box, Tooltip } from '@mantine/core'
import { IconRobot } from '@tabler/icons-react'
import dayjs from 'dayjs'
import 'dayjs/locale/de'
import type { Fixture } from '../../types'
import type { EnrichedFixture } from '../../api'
import { STATUS_LABELS, teamLogoUrl } from '../../types'

dayjs.locale('de')

interface Props {
  fixture: Fixture | EnrichedFixture
  eloByTeam?: Record<number, number>
  onClick?: () => void
}

function statusColor(status: string | null): string {
  switch (status) {
    case 'FT': case 'AET': case 'PEN': return 'green'
    case '1H': case '2H': return 'yellow'
    case 'HT': return 'orange'
    case 'CANC': case 'PST': return 'red'
    default: return 'gray'
  }
}

function fmtElo(v: number | undefined) {
  if (v == null) return null
  return v.toFixed(1).replace('.', ',')
}

function fmtPct(v: number | null | undefined) {
  if (v == null) return null
  return `${(v * 100).toFixed(0)}%`
}

function isEnriched(f: Fixture | EnrichedFixture): f is EnrichedFixture {
  return 'has_ai_picks' in f
}

export function MatchCard({ fixture, eloByTeam, onClick }: Props) {
  const isFinished = ['FT', 'AET', 'PEN'].includes(fixture.status_short ?? '')
  const isLive = ['1H', 'HT', '2H'].includes(fixture.status_short ?? '')
  const kickoff = fixture.kickoff_utc ? dayjs(fixture.kickoff_utc + 'Z') : null
  const homeElo = fmtElo(eloByTeam?.[fixture.home_team_id])
  const awayElo = fmtElo(eloByTeam?.[fixture.away_team_id])

  const enriched = isEnriched(fixture) ? fixture : null
  const hasProbs = enriched && (enriched.p_home_win != null || enriched.p_btts != null)

  return (
    <Box
      style={{
        borderRadius: 8,
        padding: '8px 12px',
        borderLeft: `3px solid var(--mantine-color-${statusColor(fixture.status_short)}-6)`,
        cursor: onClick ? 'pointer' : 'default',
      }}
      onClick={onClick}
    >
      <Group justify="space-between" wrap="nowrap" gap="xs">
        {/* Heim */}
        <Group gap={6} style={{ flex: 1, justifyContent: 'flex-end' }} wrap="nowrap">
          <Stack gap={0} style={{ flex: 1 }}>
            <Text size="sm" fw={500} ta="right">{fixture.home_team_name}</Text>
            {homeElo && <Text size="xs" c="dimmed" ta="right">Elo {homeElo}</Text>}
          </Stack>
          <Avatar src={teamLogoUrl(fixture.home_team_id)} size={22} radius="sm"
            styles={{ image: { objectFit: 'contain' } }} />
        </Group>

        {/* Mitte */}
        <Stack gap={2} align="center" style={{ minWidth: 70 }}>
          {isFinished || isLive ? (
            <Text fw={700} size="md">{fixture.home_score ?? '–'} : {fixture.away_score ?? '–'}</Text>
          ) : (
            <Text size="sm" c="dimmed">{kickoff ? kickoff.format('HH:mm') : '–'}</Text>
          )}
          <Badge size="xs" color={statusColor(fixture.status_short)} variant={isLive ? 'filled' : 'dot'}>
            {STATUS_LABELS[fixture.status_short ?? ''] ?? fixture.status_short ?? '–'}
          </Badge>
          {isFinished && fixture.home_ht_score != null && (
            <Text size="10px" c="dimmed">HZ: {fixture.home_ht_score}:{fixture.away_ht_score}</Text>
          )}
          {enriched && (
            <Tooltip label={enriched.has_ai_picks ? 'KI-Picks vorhanden' : 'Keine KI-Picks'} withArrow>
              <IconRobot size={13}
                color={enriched.has_ai_picks
                  ? 'var(--mantine-color-violet-6)'
                  : 'var(--mantine-color-gray-4)'} />
            </Tooltip>
          )}
        </Stack>

        {/* Gast */}
        <Group gap={6} style={{ flex: 1 }} wrap="nowrap">
          <Avatar src={teamLogoUrl(fixture.away_team_id)} size={22} radius="sm"
            styles={{ image: { objectFit: 'contain' } }} />
          <Stack gap={0} style={{ flex: 1 }}>
            <Text size="sm" fw={500}>{fixture.away_team_name}</Text>
            {awayElo && <Text size="xs" c="dimmed">Elo {awayElo}</Text>}
          </Stack>
        </Group>
      </Group>

      {/* Wahrscheinlichkeiten – nur für ausstehende Spiele */}
      {hasProbs && !isFinished && (
        <Group gap={4} mt={5} wrap="wrap">
          {enriched!.p_home_win != null && (
            <Badge size="xs" color="blue" variant="light">1 {fmtPct(enriched!.p_home_win)}</Badge>
          )}
          {enriched!.p_draw != null && (
            <Badge size="xs" color="gray" variant="light">X {fmtPct(enriched!.p_draw)}</Badge>
          )}
          {enriched!.p_away_win != null && (
            <Badge size="xs" color="teal" variant="light">2 {fmtPct(enriched!.p_away_win)}</Badge>
          )}
          {enriched!.p_goal_home != null && (
            <Badge size="xs" color="orange" variant="outline">⚽H {fmtPct(enriched!.p_goal_home)}</Badge>
          )}
          {enriched!.p_goal_away != null && (
            <Badge size="xs" color="orange" variant="outline">⚽A {fmtPct(enriched!.p_goal_away)}</Badge>
          )}
          {enriched!.p_btts != null && (
            <Badge size="xs" color="violet" variant="outline">BTTS {fmtPct(enriched!.p_btts)}</Badge>
          )}
        </Group>
      )}
    </Box>
  )
}
