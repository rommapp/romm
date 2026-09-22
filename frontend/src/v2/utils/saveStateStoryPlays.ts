import { expect, userEvent, waitFor, within } from "storybook/test";

/** Selectable save/state rows in AssetList (excludes slot fold buttons). */
export function listRows(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(".r-asset-list__row")];
}

/** Manage-mode static rows. */
export function manageListRows(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(".r-asset-list__row--static")];
}

/** Selectable tiles in AssetStrip. */
export function stripTiles(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(".r-asset-strip__tile")];
}

export function expectListRowCount(root: HTMLElement, min: number): void {
  const rows = listRows(root);
  expect(rows.length).toBeGreaterThanOrEqual(min);
}

export function canvas(root: HTMLElement) {
  return within(root);
}

/** Download actions use `Download {file_name}` aria labels. */
export function downloadButtons(root: HTMLElement) {
  return canvas(root).getAllByRole("button", { name: /^Download /i });
}

/** Own-item delete uses `Delete save` / `Delete state` labels. */
export function deleteButtons(root: HTMLElement) {
  return canvas(root).getAllByRole("button", { name: /^Delete /i });
}

/**
 * SaveDataTab uses vertical tabs (md+) or a menu trigger (sm-and-down).
 * Works in Storybook at any viewport width.
 */
export async function pickSaveDataSubtab(
  root: HTMLElement,
  label: RegExp,
): Promise<void> {
  const ui = canvas(root);
  const tab = ui.queryByRole("tab", { name: label });
  if (tab) {
    await userEvent.click(tab);
    return;
  }
  const trigger = root.querySelector(
    ".r-v2-subtab-nav__trigger",
  ) as HTMLElement | null;
  if (!trigger) {
    throw new Error("Save data subtab nav not found (tab or menu trigger)");
  }
  await userEvent.click(trigger);
  const menu = within(document.body);
  const option = await waitFor(() => menu.getByText(label));
  await userEvent.click(option);
}
