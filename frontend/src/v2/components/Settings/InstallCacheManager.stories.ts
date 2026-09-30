import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, within } from "storybook/test";
import InstallCacheManager from "@/v2/components/Settings/InstallCacheManager.vue";
import { installCache } from "@/v2/utils/install.fixtures";
import { mockApi } from "@/v2/utils/mockApi.fixtures";

const CACHE_URL = "/roms/install/cache";

const meta: Meta<typeof InstallCacheManager> = {
  title: "Settings/InstallCacheManager",
  component: InstallCacheManager,
  args: { canEdit: true },
  render: (args) => ({
    components: { InstallCacheManager },
    setup: () => ({ args }),
    template: `<div style="width: 560px"><InstallCacheManager v-bind="args" /></div>`,
  }),
};

export default meta;
type Story = StoryObj<typeof InstallCacheManager>;

export const Default: Story = {
  beforeEach: () => mockApi([{ url: CACHE_URL, data: installCache }]),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(await canvas.findByText("Example Game")).toBeVisible();
    const deletes = canvas.getAllByRole("button", {
      name: "Delete install cache",
    });
    await expect(deletes[0]).toBeEnabled();
    // The second entry is still streaming, so its cache can't be deleted yet.
    await expect(deletes[1]).toBeDisabled();
  },
};

export const Empty: Story = {
  beforeEach: () =>
    mockApi([{ url: CACHE_URL, data: { total_bytes: 0, entries: [] } }]),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      await canvas.findByText("No install caches on disk."),
    ).toBeVisible();
    await expect(
      canvas.getByRole("button", { name: "Delete all" }),
    ).toBeDisabled();
  },
};

export const Loading: Story = {
  beforeEach: () => mockApi([{ url: CACHE_URL, pending: true }]),
};

export const ReadOnly: Story = {
  args: { canEdit: false },
  beforeEach: () => mockApi([{ url: CACHE_URL, data: installCache }]),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await canvas.findByText("Example Game");
    for (const button of canvas.getAllByRole("button")) {
      await expect(button).toBeDisabled();
    }
  },
};
