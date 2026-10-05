import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { ref } from "vue";
import type { RSortDir } from "../RSortHeader/types";
import RTable from "./RTable.vue";
import type { RTableColumn, RTableSortPayload } from "./types";

// Cast through `Meta` because RTable is a generic component (`<T>`):
// Vue's compiled type narrows T to `unknown` here, which Storybook's
// Meta<typeof RTable> can't reconcile with our concrete DemoRow stories.
const meta: Meta = {
  title: "Data/RTable",
  // RTable is generic, so its component-typed shape doesn't fit
  // Storybook's `component` slot. The cast is narrow + intentional.
  component: RTable as never,
  argTypes: {
    loading: { control: "boolean" },
    sortKey: { control: "text" },
    sortDir: {
      control: "select",
      options: ["asc", "desc"],
    },
    clickableRows: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj;

interface DemoRow {
  id: number;
  name: string;
  size: string;
  added: string;
  rating: number;
}

const COLUMNS: RTableColumn[] = [
  {
    key: "name",
    label: "Title",
    sortable: true,
    width: "minmax(0, 1.6fr)",
  },
  {
    key: "size",
    label: "Size",
    sortable: true,
    width: "120px",
    skeletonWidth: 60,
  },
  {
    key: "added",
    label: "Added",
    sortable: true,
    width: "140px",
    skeletonWidth: 80,
  },
  {
    key: "rating",
    label: "Rating",
    sortable: true,
    width: "80px",
    skeletonWidth: 30,
  },
];

const ITEMS: DemoRow[] = [
  {
    id: 1,
    name: "Super Mario Bros.",
    size: "32 KB",
    added: "2024-01-12",
    rating: 9.4,
  },
  {
    id: 2,
    name: "Mega Man X",
    size: "1.2 MB",
    added: "2024-02-04",
    rating: 9.1,
  },
  {
    id: 3,
    name: "Chrono Trigger",
    size: "4.0 MB",
    added: "2024-02-21",
    rating: 9.8,
  },
  {
    id: 4,
    name: "Streets of Rage 2",
    size: "1.5 MB",
    added: "2024-03-09",
    rating: 8.7,
  },
];

export const Default: Story = {
  args: {
    columns: COLUMNS,
    items: ITEMS,
    itemKey: "id",
    sortKey: "name",
    sortDir: "asc",
    clickableRows: true,
  },
  render: (args) => ({
    components: { RTable },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 32px; background: #07070f;">
        <RTable v-bind="args" />
      </div>
    `,
  }),
};

export const Loading: Story = {
  args: {
    columns: COLUMNS,
    items: [] as DemoRow[],
    itemKey: "id",
    loading: true,
  },
  render: (args) => ({
    components: { RTable },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 32px; background: #07070f;">
        <RTable v-bind="args" />
      </div>
    `,
  }),
};

export const Empty: Story = {
  args: {
    columns: COLUMNS,
    items: [] as DemoRow[],
    itemKey: "id",
    emptyIcon: "mdi-folder-search-outline",
    emptyMessage: "No rows to show",
  },
  render: (args) => ({
    components: { RTable },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 32px; background: #07070f;">
        <RTable v-bind="args" />
      </div>
    `,
  }),
};

// Mobile card-stack: on `xs` each row reflows into a stacked card with the
// column label as a per-cell caption. The reflow keys off `html[data-bp~="xs"]`,
// so the story opens on the phone viewport preset.
export const MobileCardStack: Story = {
  globals: { viewport: { value: "rommPhoneXs" } },
  parameters: { layout: "fullscreen" },
  args: {
    columns: COLUMNS,
    items: ITEMS,
    itemKey: "id",
    sortKey: "name",
    sortDir: "asc",
  },
  render: (args) => ({
    components: { RTable },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 24px; background: #07070f;">
        <RTable v-bind="args" />
      </div>
    `,
  }),
};

const onRowClick = fn();

// Sort state lives with the consumer, so the story wires `update:sort` back
// into the props the way a real call site does.
export const SortAndRowActivation: Story = {
  name: "Sort and row activation (play)",
  args: {
    columns: [
      ...COLUMNS.slice(0, 3),
      { key: "rating", label: "Rating", width: "80px" },
    ],
    items: ITEMS,
    itemKey: "id",
    clickableRows: true,
  },
  render: (args) => ({
    components: { RTable },
    setup: () => {
      const sortKey = ref<string | null>("name");
      const sortDir = ref<RSortDir>("asc");
      function onSort(payload: RTableSortPayload) {
        sortKey.value = payload.key;
        sortDir.value = payload.dir;
      }
      return { args, sortKey, sortDir, onSort, onRowClick };
    },
    template: `
      <div style="padding: 32px;">
        <RTable
          v-bind="args"
          :sort-key="sortKey"
          :sort-dir="sortDir"
          @update:sort="onSort"
          @row:click="onRowClick"
        />
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const header = (name: string) => canvas.getByRole("columnheader", { name });

    await step("a new column starts ascending", async () => {
      await userEvent.click(canvas.getByRole("button", { name: "Size" }));
      await expect(header("Size")).toHaveAttribute("aria-sort", "ascending");
      await expect(header("Title")).toHaveAttribute("aria-sort", "none");
    });

    await step(
      "re-clicking the active column flips to descending",
      async () => {
        await userEvent.click(canvas.getByRole("button", { name: "Size" }));
        await expect(header("Size")).toHaveAttribute("aria-sort", "descending");
      },
    );

    await step("a non-sortable column has no sort control", async () => {
      await expect(header("Rating")).not.toHaveAttribute("aria-sort");
      await expect(
        canvas.queryByRole("button", { name: "Rating" }),
      ).not.toBeInTheDocument();
    });

    const row = canvas.getByText("Chrono Trigger").closest('[role="row"]');
    if (!(row instanceof HTMLElement)) throw new Error("expected a row");

    await step("clicking a row emits it", async () => {
      await userEvent.click(row);
      await expect(onRowClick).toHaveBeenCalledTimes(1);
      await expect(onRowClick).toHaveBeenLastCalledWith(ITEMS[2]);
    });

    await step("Enter and Space activate the focused row", async () => {
      row.focus();
      await userEvent.keyboard("{Enter}");
      await userEvent.keyboard(" ");
      await expect(onRowClick).toHaveBeenCalledTimes(3);
    });
  },
};
