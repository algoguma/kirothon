export const SERVICE_NAME = '분신으로 자동답장'

export function Brand() {
  return (
    <span className="brand">
      <img src="/favicon.svg" alt="" width={24} height={24} />
      {SERVICE_NAME}
    </span>
  )
}
