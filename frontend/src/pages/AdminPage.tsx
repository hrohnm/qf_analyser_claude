import {
  Stack, Title, Card, Group, Text, Button, Badge, Switch,
  Table, ScrollArea, Alert, Loader, Image, TextInput, Select,
  Modal, Divider, Progress, ThemeIcon, SimpleGrid,
} from '@mantine/core'
import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  IconRefresh, IconAlertCircle, IconCheck, IconSearch,
  IconCloudDownload, IconX, IconInfoCircle,
} from '@tabler/icons-react'
import { adminApi } from '../api'
import type { LeagueAdmin, SyncEstimate, SyncStatus } from '../api'

const COUNTRY_FLAGS: Record<string, string> = {
  Germany: '🇩🇪',
  England: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
  Spain: '🇪🇸',
  France: '🇫🇷',
  Italy: '🇮🇹',
  Turkey: '🇹🇷',
}

const TIER_LABEL: Record<number, string> = {
  1: '1. Liga',
  2: '2. Liga',
  3: '3. Liga',
}

// ── Sync-Status-Badge ────────────────────────────────────────────────────────
function SyncStatusBadge({ status }: { status: SyncStatus }) {
  if (status.status === 'running') {
    const label = status.phase === 'fixtures' ? 'Fixtures…' : 'Details…'
    return (
      <Badge size="xs" color="blue" variant="dot" leftSection={<Loader size={8} color="blue" />}>
        {label}
      </Badge>
    )
  }
  if (status.status === 'done') {
    return <Badge size="xs" color="green" variant="light">Fertig</Badge>
  }
  if (status.status === 'error') {
    return <Badge size="xs" color="red" variant="light">Fehler</Badge>
  }
  return null
}

// ── Estimate-Details ─────────────────────────────────────────────────────────
function EstimateDetails({ estimate }: { estimate: SyncEstimate }) {
  const rows = [
    { label: 'Fixture-Liste laden', calls: estimate.calls_fixtures },
    { label: `Stats für ${estimate.calls_stats_needed} Spiele`, calls: estimate.calls_stats_needed },
    { label: `Events für ${estimate.calls_events_needed} Spiele`, calls: estimate.calls_events_needed },
  ]

  return (
    <Stack gap="xs">
      {estimate.is_estimate && (
        <Alert icon={<IconInfoCircle size={14} />} color="blue" variant="light" py={6}>
          Noch keine Fixtures in der DB – Schätzung basiert auf typischer Saisonlänge.
        </Alert>
      )}

      <SimpleGrid cols={2} spacing="xs">
        <Text size="sm" c="dimmed">Abgeschlossene Spiele</Text>
        <Text size="sm" fw={600}>{estimate.finished_fixtures}</Text>

        <Text size="sm" c="dimmed">Bereits Stats geladen</Text>
        <Text size="sm">{estimate.already_have_stats}</Text>

        <Text size="sm" c="dimmed">Bereits Events geladen</Text>
        <Text size="sm">{estimate.already_have_events}</Text>
      </SimpleGrid>

      <Divider />

      {rows.map(r => (
        <Group key={r.label} justify="space-between">
          <Text size="sm">{r.label}</Text>
          <Badge size="sm" variant="outline" color={r.calls === 0 ? 'gray' : 'blue'}>
            {r.calls} {r.calls === 1 ? 'Call' : 'Calls'}
          </Badge>
        </Group>
      ))}

      <Divider />

      <Group justify="space-between">
        <Text size="sm" fw={700}>Gesamt{estimate.is_estimate ? ' (ca.)' : ''}</Text>
        <Badge size="md" color="orange" variant="filled">
          ~{estimate.estimated_total_calls} API Calls
        </Badge>
      </Group>
    </Stack>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function AdminPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [filterCountry, setFilterCountry] = useState<string | null>(null)
  const [fetchResult, setFetchResult] = useState<{
    total_from_api: number; imported: number; updated: number; auto_activated: number
  } | null>(null)

  // Confirm-Modal
  const [confirmLeague, setConfirmLeague] = useState<LeagueAdmin | null>(null)
  const [estimate, setEstimate] = useState<SyncEstimate | null>(null)
  const [estimateLoading, setEstimateLoading] = useState(false)

  // Per-league sync status (polling)
  const [syncStatuses, setSyncStatuses] = useState<Record<number, SyncStatus>>({})
  const pollingRef = useRef<Record<number, ReturnType<typeof setInterval>>>({})

  const { data: leagues, isLoading } = useQuery({
    queryKey: ['admin', 'leagues'],
    queryFn: adminApi.listLeagues,
  })

  const { mutate: fetchFromApi, isPending: isFetching } = useMutation({
    mutationFn: adminApi.fetchLeaguesFromApi,
    onSuccess: (data) => {
      setFetchResult(data)
      queryClient.invalidateQueries({ queryKey: ['admin', 'leagues'] })
      queryClient.invalidateQueries({ queryKey: ['leagues'] })
    },
  })

  const { mutate: deactivateLeague } = useMutation({
    mutationFn: ({ id }: { id: number }) => adminApi.toggleLeague(id, false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'leagues'] })
      queryClient.invalidateQueries({ queryKey: ['leagues'] })
    },
  })

  const { mutate: startActivateAndSync, isPending: isStarting } = useMutation({
    mutationFn: (leagueId: number) => adminApi.activateAndSync(leagueId),
    onSuccess: (_, leagueId) => {
      setConfirmLeague(null)
      queryClient.invalidateQueries({ queryKey: ['admin', 'leagues'] })
      queryClient.invalidateQueries({ queryKey: ['leagues'] })
      startPolling(leagueId)
    },
  })

  // Polling helpers
  function startPolling(leagueId: number) {
    if (pollingRef.current[leagueId]) return
    pollingRef.current[leagueId] = setInterval(async () => {
      const status = await adminApi.syncStatus(leagueId)
      setSyncStatuses(prev => ({ ...prev, [leagueId]: status }))
      if (status.status === 'done' || status.status === 'error') {
        clearInterval(pollingRef.current[leagueId])
        delete pollingRef.current[leagueId]
        queryClient.invalidateQueries({ queryKey: ['admin', 'leagues'] })
      }
    }, 3000)
  }

  useEffect(() => {
    return () => {
      Object.values(pollingRef.current).forEach(clearInterval)
    }
  }, [])

  // Open confirm modal: load estimate
  async function openConfirm(league: LeagueAdmin) {
    setConfirmLeague(league)
    setEstimate(null)
    setEstimateLoading(true)
    try {
      const est = await adminApi.syncEstimate(league.id)
      setEstimate(est)
    } finally {
      setEstimateLoading(false)
    }
  }

  function handleToggle(league: LeagueAdmin, checked: boolean) {
    if (checked) {
      openConfirm(league)
    } else {
      deactivateLeague({ id: league.id })
    }
  }

  const countries = leagues ? [...new Set(leagues.map(l => l.country))].sort() : []

  const filtered = (leagues ?? []).filter(l => {
    const matchSearch = search.length === 0 ||
      l.name.toLowerCase().includes(search.toLowerCase()) ||
      l.country.toLowerCase().includes(search.toLowerCase())
    const matchCountry = !filterCountry || l.country === filterCountry
    return matchSearch && matchCountry
  })

  const activeCount = (leagues ?? []).filter(l => l.is_active).length

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>Administration</Title>
          <Text c="dimmed" size="sm">Ligen verwalten und aktivieren</Text>
        </div>
        <Group>
          {leagues && leagues.length > 0 && (
            <Badge size="lg" variant="light" color="green">
              {activeCount} von {leagues.length} aktiv
            </Badge>
          )}
          <Button
            leftSection={<IconRefresh size={16} />}
            loading={isFetching}
            onClick={() => fetchFromApi()}
          >
            Ligen von API laden (2025)
          </Button>
        </Group>
      </Group>

      {fetchResult && (
        <Alert
          icon={<IconCheck size={16} />}
          color="green"
          withCloseButton
          onClose={() => setFetchResult(null)}
        >
          API-Abruf abgeschlossen: {fetchResult.total_from_api} Ligen gefunden,{' '}
          {fetchResult.imported} neu importiert, {fetchResult.updated} aktualisiert,{' '}
          {fetchResult.auto_activated} automatisch aktiviert.
        </Alert>
      )}

      {/* Running syncs */}
      {Object.entries(syncStatuses).map(([leagueIdStr, status]) => {
        if (status.status !== 'running' && status.status !== 'done' && status.status !== 'error') return null
        const leagueId = Number(leagueIdStr)
        return (
          <Alert
            key={leagueId}
            icon={status.status === 'running'
              ? <Loader size={14} />
              : status.status === 'done'
                ? <IconCheck size={14} />
                : <IconX size={14} />}
            color={status.status === 'running' ? 'blue' : status.status === 'done' ? 'green' : 'red'}
            withCloseButton={status.status !== 'running'}
            onClose={() => setSyncStatuses(prev => {
              const next = { ...prev }
              delete next[leagueId]
              return next
            })}
          >
            {status.status === 'running' && (
              <>
                <Text size="sm" fw={600}>{status.league_name}: Sync läuft…</Text>
                <Text size="xs" c="dimmed">
                  Phase: {status.phase === 'fixtures' ? 'Fixtures werden geladen' : 'Details (Stats + Events) werden geladen'}
                </Text>
                <Progress value={status.phase === 'fixtures' ? 20 : 70} size="xs" mt={6} animated />
              </>
            )}
            {status.status === 'done' && (
              <Text size="sm">
                <b>{status.league_name}</b> vollständig geladen:{' '}
                {status.fixtures_loaded} Fixtures, {status.details_fetched} Details,{' '}
                {status.api_calls_used} API Calls verbraucht.
              </Text>
            )}
            {status.status === 'error' && (
              <Text size="sm">
                <b>{status.league_name}</b> Fehler: {status.error}
              </Text>
            )}
          </Alert>
        )
      })}

      <Card withBorder padding="md" radius="md">
        <Group mb="md">
          <TextInput
            placeholder="Liga oder Land suchen..."
            leftSection={<IconSearch size={14} />}
            value={search}
            onChange={e => setSearch(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <Select
            placeholder="Land filtern"
            data={[
              { value: '', label: 'Alle Länder' },
              ...countries.map(c => ({
                value: c,
                label: `${COUNTRY_FLAGS[c] ?? ''} ${c}`,
              })),
            ]}
            value={filterCountry ?? ''}
            onChange={v => setFilterCountry(v || null)}
            clearable
            style={{ width: 180 }}
          />
        </Group>

        {isLoading ? (
          <Group justify="center" py="xl">
            <Loader size="sm" />
            <Text c="dimmed" size="sm">Ligen werden geladen...</Text>
          </Group>
        ) : leagues?.length === 0 ? (
          <Alert icon={<IconAlertCircle size={16} />} color="blue">
            Noch keine Ligen in der Datenbank. Klicke auf "Ligen von API laden" um alle Ligen
            der Saison 2025 zu importieren.
          </Alert>
        ) : (
          <ScrollArea>
            <Table striped highlightOnHover withTableBorder withColumnBorders>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th style={{ width: 40 }}></Table.Th>
                  <Table.Th>Liga</Table.Th>
                  <Table.Th>Land</Table.Th>
                  <Table.Th>Tier</Table.Th>
                  <Table.Th>Saison</Table.Th>
                  <Table.Th style={{ width: 90 }}>Sync</Table.Th>
                  <Table.Th style={{ width: 80 }}>Aktiv</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filtered.map((league: LeagueAdmin) => {
                  const syncSt = syncStatuses[league.id]
                  return (
                    <Table.Tr key={league.id} style={{ opacity: league.is_active ? 1 : 0.5 }}>
                      <Table.Td>
                        <Image
                          src={league.logo_url ?? undefined}
                          w={24} h={24} fit="contain"
                          fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
                        />
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" fw={league.is_active ? 600 : 400}>
                          {league.name}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">
                          {COUNTRY_FLAGS[league.country] ?? ''} {league.country}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {league.tier < 99 ? (
                          <Badge size="xs" variant="outline" color="gray">
                            {TIER_LABEL[league.tier] ?? `Tier ${league.tier}`}
                          </Badge>
                        ) : (
                          <Text size="xs" c="dimmed">–</Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">{league.current_season ?? '–'}</Text>
                      </Table.Td>
                      <Table.Td>
                        {syncSt && <SyncStatusBadge status={syncSt} />}
                        {league.is_active && !syncSt && (
                          <Button
                            size="xs"
                            variant="subtle"
                            color="blue"
                            leftSection={<IconRefresh size={12} />}
                            onClick={() => startActivateAndSync(league.id)}
                            loading={isStarting}
                          >
                            Sync
                          </Button>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Switch
                          checked={league.is_active}
                          onChange={e => handleToggle(league, e.currentTarget.checked)}
                          size="sm"
                          color="green"
                          disabled={syncSt?.status === 'running'}
                        />
                      </Table.Td>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
      </Card>

      {/* ── Confirmation Modal ───────────────────────────────────────────── */}
      <Modal
        opened={!!confirmLeague}
        onClose={() => setConfirmLeague(null)}
        title={
          <Group gap="xs">
            <ThemeIcon color="orange" size="sm" variant="light">
              <IconCloudDownload size={14} />
            </ThemeIcon>
            <Text fw={700}>Liga aktivieren & Daten laden</Text>
          </Group>
        }
        size="md"
      >
        {confirmLeague && (
          <Stack gap="md">
            <Group gap="sm">
              <Image
                src={confirmLeague.logo_url ?? undefined}
                w={32} h={32} fit="contain"
                fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
              />
              <div>
                <Text fw={700}>{confirmLeague.name}</Text>
                <Text size="xs" c="dimmed">
                  {COUNTRY_FLAGS[confirmLeague.country] ?? ''} {confirmLeague.country}
                  {confirmLeague.tier < 99 ? ` · ${TIER_LABEL[confirmLeague.tier]}` : ''}
                  {confirmLeague.current_season ? ` · Saison ${confirmLeague.current_season}` : ''}
                </Text>
              </div>
            </Group>

            <Text size="sm" c="dimmed">
              Beim Aktivieren werden alle Fixtures der Saison 2025 geladen sowie
              Stats und Events für alle abgeschlossenen Spiele. Der Vorgang läuft
              im Hintergrund.
            </Text>

            <Divider label="Geschätzter API-Aufwand" labelPosition="center" />

            {estimateLoading ? (
              <Group justify="center" py="sm">
                <Loader size="sm" />
                <Text size="sm" c="dimmed">Berechne Aufwand...</Text>
              </Group>
            ) : estimate ? (
              <EstimateDetails estimate={estimate} />
            ) : null}

            <Group justify="flex-end" mt="xs">
              <Button variant="subtle" color="gray" onClick={() => setConfirmLeague(null)}>
                Abbrechen
              </Button>
              <Button
                leftSection={<IconCloudDownload size={16} />}
                color="green"
                loading={isStarting}
                disabled={estimateLoading}
                onClick={() => startActivateAndSync(confirmLeague.id)}
              >
                Aktivieren & Laden
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  )
}
