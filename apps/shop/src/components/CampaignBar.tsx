/** The notice bar shown above the header while a campaign runs. Plain text, optionally a link. */
export function CampaignBar({ text, url, accent }: { text: string; url: string; accent: string }) {
  const inner = <span>{text}</span>;
  return (
    <div className="campaign-bar" style={{ background: accent }} role="region" aria-label="ประกาศ">
      {url ? <a href={url}>{inner}</a> : inner}
    </div>
  );
}
