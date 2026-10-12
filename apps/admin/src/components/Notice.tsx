export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="notice notice--warn" role="alert"><p>{error instanceof Error ? error.message : "เกิดข้อผิดพลาด"}</p></div>;
}
