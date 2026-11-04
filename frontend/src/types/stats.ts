/** A KPI column in a gallery header: `Stat` renders one per entry. Shared by
 *  the header component and the views that compose the rows. */
export interface StatRow {
  label: string;
  /** A number rolls up on screen; a string (a size, a date) is printed. */
  value: string | number;
}
