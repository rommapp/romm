// The event log row's geometry, shared by EventLogRow's styles and the list's
// windowing, which has to know every row's height before it renders.

/** A row with its title and details each on one line. */
export const EVENT_ROW_HEIGHT = 62;

/** A row's spacing; on a phone it also stacks title, detail, author and where. */
export const EVENT_ROW = {
  paddingBlock: 8,
  gap: 2,
  /** Drops the title's first line to the middle of the event's icon. */
  titleOffset: 4,
  titleLine: 19,
  metaLine: 17,
  /** The title and the detail each wrap to at most this many lines. */
  maxLines: 2,
} as const;

/** The geometry as the custom properties EventLogRow's styles read. */
export const EVENT_ROW_VARS = {
  "--r-audit-pad-block": `${EVENT_ROW.paddingBlock}px`,
  "--r-audit-gap": `${EVENT_ROW.gap}px`,
  "--r-audit-title-offset": `${EVENT_ROW.titleOffset}px`,
  "--r-audit-title-line": `${EVENT_ROW.titleLine}px`,
  "--r-audit-meta-line": `${EVENT_ROW.metaLine}px`,
  "--r-audit-max-lines": EVENT_ROW.maxLines,
};

export function phoneEventRowHeight({
  title,
  detail,
  where,
}: {
  title: number;
  /** 0 when the event has no detail. */
  detail: number;
  /** Whether it names a device or an address. */
  where: boolean;
}): number {
  const { paddingBlock, gap, titleOffset, titleLine, metaLine } = EVENT_ROW;
  const line = metaLine + gap;
  return (
    2 * paddingBlock +
    titleOffset +
    title * titleLine +
    line +
    (detail ? detail * metaLine + gap : 0) +
    (where ? line : 0)
  );
}
