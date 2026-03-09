import {
  Stack, Title, Card, Group, Text, RingProgress, Button, Table,
  Badge, NumberInput, Alert
} from '@mantine/core'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { IconRefresh, IconAlertCircle, IconCheck } from '@tabler/icons-react'
import { useBudget } from '../hooks/useFixtures'
import { syncApi } from '../api'
import type { SyncResult } from '../types'

export function SyncPage() {
  const { data: budget, refetch: refetchBudget } = useBudget()
  const queryClient = useQueryClient()
  const [seasonYear, setSeasonYear] = useState<number>(
    new Date().getMonth() >= 6 ? new Date().getFullYear() : new Date().getFullYear() - 1
  )
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)

  const { mutate: runSync, isPending } = useMutation({
    mutationFn: () => syncApi.triggerFixtures(seasonYear),
    onSuccess: (data) => {
      setSyncResult(data)
      refetchBudget()
      queryClient.invalidateQueries({ queryKey: ['fixtures'] })
      queryClient.invalidateQueries({ queryKey: ['leagues'] })
    },
  })

  const pct = budget ? Math.round((budget.used_today / budget.limit) * 100) : 0
  const color = pct < 50 ? 'green' : pct < 80 ? 'yellow' : 'red'

  return (
    <Stack>
      <Title order={2}>Sync & Budget</Title>

      {/* Budget Card */}
      <Card withBorder padding="lg" radius="md">
        <Group>
          <RingProgress
            size={100}
            thickness={10}
            roundCaps
            sections={[{ value: pct, color }]}
            label={
              <Text ta="center" size="xs" fw={700}>
                {pct}%
              </Text>
            }
          />
          <Stack gap={4}>
            <Text fw={600} size="lg">API-Budget heute</Text>
            <Text>
              <Text span fw={700} c={color}>{budget?.used_today ?? '–'}</Text>
              {' / '}
              <Text span c="dimmed">{budget?.limit ?? 7500} Calls</Text>
            </Text>
            <Text c="dimmed" size="sm">
              {budget?.remaining ?? '–'} verbleibend · Stand: {budget?.date ?? '…'}
            </Text>
          </Stack>
        </Group>
      </Card>

      {/* Sync Controls */}
      <Card withBorder padding="lg" radius="md">
        <Stack>
          <Text fw={600}>Fixture-Sync</Text>
          <Text c="dimmed" size="sm">
            Lädt alle Spiele für die gewählte Saison (18 Ligen, ~18 API-Calls parallel).
          </Text>
          <Group>
            <NumberInput
              label="Saison"
              value={seasonYear}
              onChange={v => v && setSeasonYear(Number(v))}
              min={2020}
              max={2026}
              w={100}
            />
            <Button
              leftSection={<IconRefresh size={16} />}
              onClick={() => runSync()}
              loading={isPending}
              mt="auto"
            >
              Sync starten
            </Button>
          </Group>
        </Stack>
      </Card>

      {/* Sync Result */}
      {syncResult && (
        <Card withBorder padding="lg" radius="md">
          <Stack>
            <Group>
              <IconCheck size={20} color="green" />
              <Text fw={600}>{syncResult.message}</Text>
            </Group>
            {syncResult.results && (
              <Table verticalSpacing="xs" fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Liga</Table.Th>
                    <Table.Th ta="right">Spiele</Table.Th>
                    <Table.Th>Status</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {syncResult.results.map(r => (
                    <Table.Tr key={r.league_id}>
                      <Table.Td>{r.league_name}</Table.Td>
                      <Table.Td ta="right">{r.count ?? '–'}</Table.Td>
                      <Table.Td>
                        {r.error ? (
                          <Badge color="red" size="xs">Fehler</Badge>
                        ) : (
                          <Badge color="green" size="xs">OK</Badge>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
            {syncResult.results?.some(r => r.error) && (
              <Alert icon={<IconAlertCircle size={16} />} color="red" title="Fehler">
                {syncResult.results.filter(r => r.error).map(r => (
                  <Text key={r.league_id} size="xs">{r.league_name}: {r.error}</Text>
                ))}
              </Alert>
            )}
          </Stack>
        </Card>
      )}
    </Stack>
  )
}
