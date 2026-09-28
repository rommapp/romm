import { userEvent, waitFor, within } from "storybook/test";

// Selectable rows only; slot fold buttons use a different class.
export function listRows(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(".r-asset-list__row"));
}

export function manageListRows(root: HTMLElement): HTMLElement[] {
  return Array.from(
    root.querySelectorAll<HTMLElement>(".r-asset-list__row--static"),
  );
}

export function stripTiles(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(".r-asset-strip__tile"));
}

export function downloadButtons(root: HTMLElement) {
  return within(root).getAllByRole("button", { name: /^Download /i });
}

export function deleteButtons(root: HTMLElement) {
  return within(root).getAllByRole("button", { name: /^Delete /i });
}

// SaveDataTab renders vertical tabs from md up and a menu trigger below it.
export async function pickSaveDataSubtab(
  root: HTMLElement,
  label: RegExp,
): Promise<void> {
  const tab = within(root).queryByRole("tab", { name: label });
  if (tab) {
    await userEvent.click(tab);
    return;
  }
  const trigger = root.querySelector<HTMLElement>(".r-v2-subtab-nav__trigger");
  if (!trigger) {
    throw new Error("Save data subtab nav not found (tab or menu trigger)");
  }
  await userEvent.click(trigger);
  const option = await waitFor(() => within(document.body).getByText(label));
  await userEvent.click(option);
}
