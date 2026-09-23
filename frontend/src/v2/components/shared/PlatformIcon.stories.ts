import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect } from "storybook/test";
import { DEFAULT_PLATFORM_ICON } from "@/v2/composables/usePlatformIconCache/iconCache";
import {
  platformGalleryArgTypes,
  platformGalleryControlInclude,
  platformGalleryDefaultArgs,
  platformGalleryStoryParameters,
  platformGalleryStyles,
  platformIconGalleryTemplate,
  platformIconSizesTemplate,
  platformSizeLadderSteps,
  platformSizesStoryParameters,
  platformSizesStoryStyles,
  shippedPlatformGalleryEntries,
} from "../../../../.storybook/fixtures/platformIconGallery";
import {
  PLATFORM_ICON_SIZE_MAX,
  PLATFORM_ICON_SIZE_MIN,
  PLATFORM_ICON_SLUG_OPTIONS,
  PLATFORM_ICON_SRC_OPTIONS,
  platformIconDefaultArgs,
  platformIconSlugLabels,
  platformIconSrcLabels,
  platformIconStoryControlInclude,
} from "../../../../.storybook/fixtures/platformIconStoryControls";
import { STORYBOOK_NON_CACHED_ICON_SVG } from "../../../../.storybook/fixtures/urls";
import PlatformIcon from "./PlatformIcon.vue";

type StoryArgs = {
  slug: (typeof PLATFORM_ICON_SLUG_OPTIONS)[number];
  fsSlug: string;
  overrideSrc: boolean;
  src: (typeof PLATFORM_ICON_SRC_OPTIONS)[number];
  size: number;
  alt: string;
  title: string;
  showTooltip: boolean;
  name?: string;
};

const meta: Meta<StoryArgs> = {
  title: "Shared/PlatformIcon",
  component: PlatformIcon,
  args: platformIconDefaultArgs as StoryArgs,
  parameters: {
    controls: { include: [...platformIconStoryControlInclude] },
  },
  argTypes: {
    slug: {
      control: "select",
      options: [...PLATFORM_ICON_SLUG_OPTIONS],
      labels: platformIconSlugLabels,
    },
    fsSlug: {
      control: "text",
      description:
        "Filesystem slug when it differs from platform slug (e.g. dreamcast + dc).",
    },
    overrideSrc: {
      control: "boolean",
      description:
        "When true, `src` is passed through and wins over slug resolution.",
    },
    src: {
      control: "select",
      options: [...PLATFORM_ICON_SRC_OPTIONS],
      labels: platformIconSrcLabels,
    },
    size: {
      control: {
        type: "range",
        min: PLATFORM_ICON_SIZE_MIN,
        max: PLATFORM_ICON_SIZE_MAX,
        step: 1,
      },
    },
    alt: { control: "text" },
    title: { control: "text" },
    showTooltip: { control: "boolean" },
    name: { control: false, table: { disable: true } },
  },
  render: (args) => ({
    components: { PlatformIcon },
    setup() {
      const src = args.overrideSrc ? args.src : undefined;
      const fsSlug = args.fsSlug.trim() || undefined;
      return { args, src, fsSlug };
    },
    template: `
      <PlatformIcon
        :slug="args.slug"
        :fs-slug="fsSlug"
        :src="src"
        :size="args.size"
        :alt="args.alt"
        :title="args.title"
        :show-tooltip="args.showTooltip"
      />
    `,
  }),
};

export default meta;

type Story = StoryObj<StoryArgs>;

export const Default: Story = {};

export const SlugAllowlistHitResolvesSnes: Story = {
  name: "Slug hit",
  args: {
    slug: "snes",
    overrideSrc: false,
    size: 40,
    showTooltip: false,
  },
  play: async ({ canvasElement }) => {
    const img = canvasElement.querySelector("img");
    expect(img?.getAttribute("src")).toMatch(/snes\.svg$/);
  },
};

export const SlugAllowlistMissShowsDefault: Story = {
  name: "Slug miss",
  args: {
    slug: "switch_mods",
    overrideSrc: false,
    size: 40,
    showTooltip: false,
  },
  play: async ({ canvasElement }) => {
    const img = canvasElement.querySelector("img");
    expect(img?.getAttribute("src")).toBe(DEFAULT_PLATFORM_ICON);
  },
};

export const ExplicitFixtureSrcNotInGlob: Story = {
  name: "Fixture override",
  args: {
    slug: "non-cached-icon",
    overrideSrc: true,
    src: STORYBOOK_NON_CACHED_ICON_SVG,
    size: 40,
    showTooltip: false,
  },
  play: async ({ canvasElement }) => {
    const img = canvasElement.querySelector("img");
    expect(img?.getAttribute("src")).toBe(STORYBOOK_NON_CACHED_ICON_SVG);
  },
};

export const ShippedSlugRow: Story = {
  name: "Slug row",
  parameters: { controls: { disable: true } },
  render: () => ({
    components: { PlatformIcon },
    template: `
      <div style="display:flex;gap:.5rem;align-items:center">
        <PlatformIcon slug="snes" :show-tooltip="false" />
        <PlatformIcon slug="nes" :show-tooltip="false" />
        <PlatformIcon slug="gba" :show-tooltip="false" />
        <PlatformIcon slug="switch_mods" :show-tooltip="false" />
      </div>
    `,
  }),
};

type GalleryStoryArgs = StoryArgs & {
  showLabels: boolean;
};

export const AllPlatforms: StoryObj<GalleryStoryArgs> = {
  name: "All platforms",
  parameters: {
    ...platformGalleryStoryParameters,
    controls: { include: [...platformGalleryControlInclude] },
  },
  args: platformGalleryDefaultArgs,
  argTypes: {
    ...platformGalleryArgTypes,
    slug: { control: false, table: { disable: true } },
    fsSlug: { control: false, table: { disable: true } },
    overrideSrc: { control: false, table: { disable: true } },
    src: { control: false, table: { disable: true } },
    alt: { control: false, table: { disable: true } },
    title: { control: false, table: { disable: true } },
  },
  render: (args) => ({
    components: { PlatformIcon },
    setup() {
      return {
        args,
        icons: shippedPlatformGalleryEntries,
        styles: platformGalleryStyles,
      };
    },
    template: platformIconGalleryTemplate,
  }),
};

export const Sizes: Story = {
  name: "Sizes",
  parameters: platformSizesStoryParameters,
  render: () => ({
    components: { PlatformIcon },
    setup() {
      return {
        icons: shippedPlatformGalleryEntries,
        sizes: platformSizeLadderSteps,
        styles: platformSizesStoryStyles,
      };
    },
    template: platformIconSizesTemplate,
  }),
};

export const InsideFlexParent: Story = {
  name: "Flex parent",
  parameters: { controls: { disable: true } },
  render: () => ({
    components: { PlatformIcon },
    template: `
      <div style="display:flex;align-items:center;gap:6px;padding:6px;border:1px dashed var(--r-color-border);border-radius:6px">
        <span style="font:11px sans-serif;color:var(--r-color-fg-muted)">flex parent</span>
        <PlatformIcon slug="snes" :size="22" :show-tooltip="false" />
      </div>
    `,
  }),
};
