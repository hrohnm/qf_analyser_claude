import { Table, Avatar, Text, Group, Badge, Tooltip, Box } from '@mantine/core'
import type { StandingRow } from '../../types'

interface Props {
  standings: StandingRow[]
  eloByTeam?: Record<number, number>
  onTeamClick?: (teamId: number) => void
}

const FORM_COLOR: Record<string, string> = { W: 'green', D: 'yellow', L: 'red' }
const FORM_LABEL: Record<string, string> = { W: 'S', D: 'U', L: 'N' }

function FormBadges({ form }: { form: string }) {
  return (
    <Group gap={2}>
      {form.split('').map((c, i) => (
        <Tooltip key={i} label={{ W: 'Sieg', D: 'Unentschieden', L: 'Niederlage' }[c] ?? c}>
          <Badge
            size="xs"
            color={FORM_COLOR[c] ?? 'gray'}
            variant="filled"
            styles={{ root: { minWidth: 18, padding: '0 3px' } }}
          >
            {FORM_LABEL[c] ?? c}
          </Badge>
        </Tooltip>
      ))}
    </Group>
  )
}

function rankColor(rank: number, total: number): string | undefined {
  if (rank <= 2) return 'green'
  if (rank === 3) return 'teal'
  if (rank >= total - 2) return 'red'
  return undefined
}

function fmtElo(v: number | undefined) {
  if (v == null) return null
  return v.toFixed(1).replace('.', ',')
}

export function StandingsTable({ standings, eloByTeam, onTeamClick }: Props) {
  if (!standings.length) return <Text c="dimmed">Keine Tabellendaten.</Text>

  return (
    <Table striped highlightOnHover verticalSpacing="xs" fz="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={36}>#</Table.Th>
          <Table.Th>Verein</Table.Th>
          <Table.Th ta="center" w={36}>Sp</Table.Th>
          <Table.Th ta="center" w={36}>S</Table.Th>
          <Table.Th ta="center" w={36}>U</Table.Th>
          <Table.Th ta="center" w={36}>N</Table.Th>
          <Table.Th ta="center" w={60}>Tore</Table.Th>
          <Table.Th ta="center" w={40}>Diff</Table.Th>
          <Table.Th ta="center" w={40} fw={700}>Pkt</Table.Th>
          <Table.Th>Form</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {standings.map(row => {
          const color = rankColor(row.rank, standings.length)
          return (
            <Table.Tr key={row.team_id}>
              <Table.Td>
                <Box
                  style={{
                    width: 4,
                    height: 20,
                    backgroundColor: color ? `var(--mantine-color-${color}-6)` : 'transparent',
                    borderRadius: 2,
                    float: 'left',
                    marginRight: 6,
                  }}
                />
                <Text size="xs" c={color} fw={color ? 700 : undefined}>{row.rank}</Text>
              </Table.Td>
              <Table.Td>
                <Group gap="xs" wrap="nowrap">
                  <Avatar
                    src={row.logo_url}
                    size={20}
                    radius="sm"
                    styles={{ image: { objectFit: 'contain' } }}
                  />
                  <div>
                    <Text
                      size="sm"
                      fw={500}
                      truncate
                      style={{ cursor: onTeamClick ? 'pointer' : 'default' }}
                      onClick={() => onTeamClick?.(row.team_id)}
                    >
                      {row.team_name}
                    </Text>
                    {fmtElo(eloByTeam?.[row.team_id]) && (
                      <Text size="xs" c="dimmed">Elo {fmtElo(eloByTeam?.[row.team_id])}</Text>
                    )}
                  </div>
                </Group>
              </Table.Td>
              <Table.Td ta="center"><Text size="xs">{row.played}</Text></Table.Td>
              <Table.Td ta="center"><Text size="xs">{row.won}</Text></Table.Td>
              <Table.Td ta="center"><Text size="xs">{row.drawn}</Text></Table.Td>
              <Table.Td ta="center"><Text size="xs">{row.lost}</Text></Table.Td>
              <Table.Td ta="center">
                <Text size="xs">{row.goals_for}:{row.goals_against}</Text>
              </Table.Td>
              <Table.Td ta="center">
                <Text size="xs" c={row.goal_diff > 0 ? 'green' : row.goal_diff < 0 ? 'red' : undefined}>
                  {row.goal_diff > 0 ? '+' : ''}{row.goal_diff}
                </Text>
              </Table.Td>
              <Table.Td ta="center">
                <Text size="sm" fw={700}>{row.points}</Text>
              </Table.Td>
              <Table.Td>
                <FormBadges form={row.form} />
              </Table.Td>
            </Table.Tr>
          )
        })}
      </Table.Tbody>
    </Table>
  )
}
