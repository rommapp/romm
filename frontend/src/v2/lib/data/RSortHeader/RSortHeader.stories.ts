import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within } from "storybook/test";
import { ref } from "vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RSortHeader from "./RSortHeader.vue";
import type { RSortDir } from "./types";

const meta: Meta<typeof RSortHeader> = {
  title: "Data/RSortHeader",
  component: RSortHeader,
  argTypes: {
    dir: { control: "inline-radio", options: ["asc", "desc"] },
    align: { control: "inline-radio", options: ["start", "end", "center"] },
  },
  // A columnheader is only valid inside a row, so every story renders one.
  render: (args) => ({
    components: { RSortHeader },
    setup: () => ({ args }),
    template: `
      <div role="table" style="width: 240px;">
        <div role="row" style="height: 40px; display: flex;">
          <RSortHeader v-bind="args" style="flex: 1;" />
        </div>
      </div>
    `,
  }),
};

export default meta;
type Story = StoryObj<typeof RSortHeader>;

export const Default: Story = {
  args: { label: "Title", sortable: true, active: true, dir: "asc" },
};

// The toolbar switches every story's theme; this one pins light.
export const Light: Story = {
  args: { label: "Title", sortable: true, active: true, dir: "asc" },
  globals: { theme: "light" },
};

export const Inactive: Story = {
  args: { label: "Size", sortable: true },
};

export const EndAligned: Story = {
  args: {
    label: "Rating",
    sortable: true,
    active: true,
    dir: "desc",
    align: "end",
  },
};

export const NotSortable: Story = {
  args: { label: "Tags" },
};

export const WithAppend: Story = {
  args: { label: "Type", sortable: true },
  render: (args) => ({
    components: { RSortHeader, RBtn },
    setup: () => ({ args }),
    template: `
      <div role="table" style="width: 240px;">
        <div role="row" style="height: 40px; display: flex;">
          <RSortHeader v-bind="args" style="flex: 1;">
            <template #append>
              <RBtn
                variant="text"
                size="small"
                icon="mdi-information-outline"
                aria-label="About types"
              />
            </template>
          </RSortHeader>
        </div>
      </div>
    `,
  }),
};

const COLUMNS = [
  { key: "name", label: "Title", sortable: true },
  { key: "cover", label: "Cover", hideLabel: true },
  { key: "size", label: "Size", sortable: true, align: "end" as const },
  { key: "tags", label: "Tags" },
];

// A full header row, with the sort state held by the parent the way a list
// header does.
export const KeyboardSort: Story = {
  name: "Header row, keyboard sort (play)",
  render: () => ({
    components: { RSortHeader },
    setup: () => {
      const sortKey = ref("name");
      const sortDir = ref<RSortDir>("asc");
      function onSort(key: string, dir: RSortDir) {
        sortKey.value = key;
        sortDir.value = dir;
      }
      return { columns: COLUMNS, sortKey, sortDir, onSort };
    },
    template: `
      <div role="table" style="width: 520px;">
        <div
          role="row"
          style="display: grid; grid-template-columns: 1fr 60px 100px 1fr; gap: 12px; height: 40px;"
        >
          <RSortHeader
            v-for="col in columns"
            :key="col.key"
            :label="col.label"
            :sortable="col.sortable"
            :hide-label="col.hideLabel"
            :align="col.align"
            :active="sortKey === col.key"
            :dir="sortDir"
            @sort="onSort(col.key, $event)"
          />
        </div>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const header = (name: string) => canvas.getByRole("columnheader", { name });

    await step("only sortable headers are tab stops", async () => {
      await userEvent.tab();
      await expect(canvas.getByRole("button", { name: "Title" })).toHaveFocus();
      await userEvent.tab();
      await expect(canvas.getByRole("button", { name: "Size" })).toHaveFocus();
    });

    await step("Enter sorts a new column ascending", async () => {
      await userEvent.keyboard("{Enter}");
      await expect(header("Size")).toHaveAttribute("aria-sort", "ascending");
      await expect(header("Title")).toHaveAttribute("aria-sort", "none");
    });

    await step("Space flips the active column", async () => {
      await userEvent.keyboard(" ");
      await expect(header("Size")).toHaveAttribute("aria-sort", "descending");
    });

    await step("a hidden label still names its header", async () => {
      await expect(header("Cover")).not.toHaveAttribute("aria-sort");
      await expect(header("Tags")).not.toHaveAttribute("aria-sort");
    });
  },
};
