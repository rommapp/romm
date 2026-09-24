// The event log row's geometry, shared by EventLogRow's styles and the list's
// windowing, which has to know every row's height before it renders.

/** A row with its title and details each on one line. */
export const EVENT_ROW_HEIGHT = 62;

/** On a phone, a row stacks its title, detail, author and where from. */
export const PHONE_EVENT_ROW = {
  paddingBlock: 8,
  /** Drops the title's first line to the middle of the event's icon. */
  titleOffset: 4,
  titleLine: 19,
  metaLine: 17,
  gap: 2,
  /** The title and the detail each wrap to at most this many lines. */
  maxLines: 2,
} as const;

export interface PhoneEventLines {
  title: number;
  /** 0 when the event has no detail. */
  detail: number;
  /** Whether it names a device or an address. */
  where: boolean;
}

export function phoneEventRowHeight({
  title,
  detail,
  where,
}: PhoneEventLines): number {
  const { paddingBlock, titleOffset, titleLine, metaLine, gap } =
    PHONE_EVENT_ROW;
  const blocks = [title > 0, detail > 0, true, where].filter(Boolean).length;
  const lines = detail + 1 + (where ? 1 : 0);
  return (
    2 * paddingBlock +
    titleOffset +
    title * titleLine +
    lines * metaLine +
    (blocks - 1) * gap
  );
}
