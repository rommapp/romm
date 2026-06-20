import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RTable from "./RTable.vue";
import type { RTableColumn } from "./types";

// Cast through `Meta` because RTable is a generic component (`<T>`) —
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
