import { Group, RingProgress, Text, Tooltip, Badge } from '@mantine/core'
import { IconDatabase } from '@tabler/icons-react'
import { useBudget } from '../../hooks/useFixtures'

export function BudgetIndicator() {
  const { data: budget } = useBudget()

  if (!budget) return null

  const pct = Math.round((budget.used_today / budget.limit) * 100)
  const color = pct < 50 ? 'green' : pct < 80 ? 'yellow' : 'red'

  return (
    <Tooltip
      label={`${budget.used_today} / ${budget.limit} API-Calls heute (${budget.date})`}
      position="bottom"
    >
      <Group gap={6} style={{ cursor: 'default' }}>
        <RingProgress
          size={36}
          thickness={4}
          sections={[{ value: pct, color }]}
          label={<IconDatabase size={14} style={{ margin: 'auto', display: 'block' }} />}
        />
        <Text size="xs" c="dimmed">
          {budget.used_today}{' '}
          <Text span c={color} fw={600}>
            / {budget.limit}
          </Text>
        </Text>
        <Badge size="xs" color={color} variant="dot">
          {budget.remaining} verbleibend
        </Badge>
      </Group>
    </Tooltip>
  )
}
