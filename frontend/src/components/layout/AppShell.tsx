import { AppShell, Burger, Group, Title, useMantineColorScheme, ActionIcon } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconSun, IconMoon } from '@tabler/icons-react'
import { Sidebar } from './Sidebar'
import { BudgetIndicator } from './BudgetIndicator'

interface Props {
  children: React.ReactNode
}

export function AppLayout({ children }: Props) {
  const [opened, { toggle }] = useDisclosure()
  const { colorScheme, toggleColorScheme } = useMantineColorScheme()

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4} fw={700} c="green">
              ⚽ Quotenfabrik
            </Title>
          </Group>
          <Group>
            <BudgetIndicator />
            <ActionIcon
              variant="subtle"
              onClick={() => toggleColorScheme()}
              size="sm"
            >
              {colorScheme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar>
        <Sidebar />
      </AppShell.Navbar>

      <AppShell.Main>
        {children}
      </AppShell.Main>
    </AppShell>
  )
}
