export type RowType = "alias" | "variant" | "auto" | null;

export interface Row {
  fsSlug: string;
  slug?: string | undefined;
  displayName?: string | undefined;
  type: RowType;
}
