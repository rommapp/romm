// The toolbar's clusters are layout-scoped: grid mode owns grouping and
// the sort axis/direction, while list mode sorts through its column
// headers and keeps only the layout switch.
import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import type { GroupByMode, LayoutMode } from "@/v2/composables/useGalleryMode";
import GalleryToolbar from "./GalleryToolbar.vue";
import { getSortOptions, type ListSortKey } from "./listColumns";

const meta: Meta<typeof GalleryToolbar> = {
  title: "Gallery/GalleryToolbar",
  component: GalleryToolbar,
  parameters: { layout: "fullscreen" },
};

export default meta;
type Story = StoryObj<typeof GalleryToolbar>;

// Wired to local state so the story behaves like a gallery view does:
// flipping the layout switch swaps the clusters in place.
function toolbarStory(initialLayout: LayoutMode) {
  return {
    components: { GalleryToolbar },
    setup() {
      const groupBy = ref<GroupByMode>("none");
      const layout = ref<LayoutMode>(initialLayout);
      const sortDir = ref<"asc" | "desc">("asc");
      const sortKey = ref<ListSortKey>("name");
      const search = ref("");
      return {
        groupBy,
        layout,
        sortDir,
        sortKey,
        search,
        sortOptions: getSortOptions(true),
      };
    },
    template: `
      <div style="padding: 16px 24px; min-width: 720px">
        <GalleryToolbar
          :group-by="groupBy"
          :layout="layout"
          :sort-dir="sortDir"
          :sort-key="sortKey"
          :sort-key-items="sortOptions"
          show-search
          show-filter
          :search="search"
          :filter-active-count="2"
          @update:group-by="groupBy = $event"
          @update:layout="layout = $event"
          @update:sort-dir="sortDir = $event"
          @update:sort-key="sortKey = $event"
          @update:search="search = $event"
        />
      </div>
    `,
  };
}

export const GridLayout: Story = {
  render: () => toolbarStory("grid"),
};

export const ListLayout: Story = {
  render: () => toolbarStory("list"),
};
