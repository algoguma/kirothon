import { isMocked } from '../api'
import type { MockGroup } from '../api/mockConfig'

/** Small "mock 데이터" label shown next to sections whose API group is mocked. */
export function MockTag({ group }: { group: MockGroup }) {
  if (!isMocked(group)) return null
  return (
    <span className="mock-tag" title="VITE_USE_MOCK 설정으로 mock 데이터를 보여주고 있습니다">
      mock 데이터
    </span>
  )
}
