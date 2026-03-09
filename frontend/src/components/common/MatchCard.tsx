import { Group, Text, Badge, Avatar, Stack, Box } from '@mantine/core'
import dayjs from 'dayjs'
import 'dayjs/locale/de'
import type { Fixture } from '../../types'
import { STATUS_LABELS, teamLogoUrl } from '../../types'

dayjs.locale('de')

interface Props {
  fixture: Fixture
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

export function MatchCard({ fixture, eloByTeam, onClick }: Props) {
  const isFinished = ['FT', 'AET', 'PEN'].includes(fixture.status_short ?? '')
  const isLive = ['1H', 'HT', '2H'].includes(fixture.status_short ?? '')
  // Append 'Z' so dayjs treats the stored UTC value as UTC and converts to browser local time
  const kickoff = fixture.kickoff_utc ? dayjs(fixture.kickoff_utc + 'Z') : null
  const homeElo = fmtElo(eloByTeam?.[fixture.home_team_id])
  const awayElo = fmtElo(eloByTeam?.[fixture.away_team_id])

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
            <Text size="sm" fw={500} ta="right">
              {fixture.home_team_name}
            </Text>
            {homeElo && (
              <Text size="xs" c="dimmed" ta="right">
                Elo {homeElo}
              </Text>
            )}
          </Stack>
          <Avatar
            src={teamLogoUrl(fixture.home_team_id)}
            size={22}
            radius="sm"
            styles={{ image: { objectFit: 'contain' } }}
          />
        </Group>

        {/* Mitte: Ergebnis / Zeit */}
        <Stack gap={2} align="center" style={{ minWidth: 70 }}>
          {isFinished || isLive ? (
            <Text fw={700} size="md">
              {fixture.home_score ?? '–'} : {fixture.away_score ?? '–'}
            </Text>
          ) : (
            <Text size="sm" c="dimmed">
              {kickoff ? kickoff.format('HH:mm') : '–'}
            </Text>
          )}
          <Badge
            size="xs"
            color={statusColor(fixture.status_short)}
            variant={isLive ? 'filled' : 'dot'}
          >
            {STATUS_LABELS[fixture.status_short ?? ''] ?? fixture.status_short ?? '–'}
          </Badge>
          {isFinished && fixture.home_ht_score != null && (
            <Text size="10px" c="dimmed">
              HZ: {fixture.home_ht_score}:{fixture.away_ht_score}
            </Text>
          )}
        </Stack>

        {/* Gast */}
        <Group gap={6} style={{ flex: 1 }} wrap="nowrap">
          <Avatar
            src={teamLogoUrl(fixture.away_team_id)}
            size={22}
            radius="sm"
            styles={{ image: { objectFit: 'contain' } }}
          />
          <Stack gap={0} style={{ flex: 1 }}>
            <Text size="sm" fw={500}>
              {fixture.away_team_name}
            </Text>
            {awayElo && (
              <Text size="xs" c="dimmed">
                Elo {awayElo}
              </Text>
            )}
          </Stack>
        </Group>
      </Group>
    </Box>
  )
}
