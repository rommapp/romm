import { userEvent, waitFor, within } from "storybook/test";

// Selectable rows and tiles are toggle buttons, so `aria-pressed` marks them.
export function selectableItems(root: HTMLElement): HTMLElement[] {
  const ui = within(root);
  return [
    ...ui.queryAllByRole("button", { pressed: true }),
    ...ui.queryAllByRole("button", { pressed: false }),
  ];
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
  const ui = within(root);
  const tab = ui.queryByRole("tab", { name: label });
  if (tab) {
    await userEvent.click(tab);
    return;
  }
  const trigger = ui
    .queryAllByRole("button", { expanded: false })
    .find((b) => b.getAttribute("aria-haspopup") === "menu");
  if (!trigger) {
    throw new Error("Save data subtab nav not found (tab or menu trigger)");
  }
  await userEvent.click(trigger);
  const option = await waitFor(() =>
    within(document.body).getByRole("menuitem", { name: label }),
  );
  await userEvent.click(option);
}
