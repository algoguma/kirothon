// VITE_USE_MOCK selects which API groups use src/api/mock.ts:
//   true                -> all groups (default)
//   false               -> none, everything calls the backend
//   llm,chats,sessions  -> only these groups; the rest call the backend
export const MOCK_GROUPS = ['auth', 'llm', 'chats', 'sessions'] as const
export type MockGroup = (typeof MOCK_GROUPS)[number]

function parse(raw: string | undefined): Set<MockGroup> {
  const value = (raw ?? 'true').trim().toLowerCase()
  if (value === 'true') return new Set(MOCK_GROUPS)
  if (value === 'false' || value === '') return new Set()
  return new Set(MOCK_GROUPS.filter((g) => value.split(',').map((s) => s.trim()).includes(g)))
}

export const mockedGroups = parse(import.meta.env.VITE_USE_MOCK)
export const isMocked = (group: MockGroup) => mockedGroups.has(group)
