import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor } from "storybook/test";
import { DEFAULT_PLATFORM_ICON } from "@/v2/composables/usePlatformIconCache/iconCache";
import {
  platformGalleryArgTypes,
  platformGalleryControlInclude,
  platformGalleryDefaultArgs,
  platformGalleryStoryParameters,
  platformGalleryStyles,
  platformIconSizesTemplate,
  platformSizeLadderSteps,
  platformSizesStoryParameters,
  platformSizesStoryStyles,
  rPlatformIconGalleryTemplate,
  rPlatformIconSizesTemplate,
  shippedPlatformGalleryEntries,
} from "../../../../../.storybook/fixtures/platformIconGallery";
import {
  MISSING_PROD_SRC,
  PLATFORM_ICON_SIZE_MAX,
  PLATFORM_ICON_SIZE_MIN,
  R_PLATFORM_ICON_SRC_OPTIONS,
  SHIPPED_GBA_SRC,
  SHIPPED_NES_SRC,
  SHIPPED_SNES_SRC,
  rPlatformIconDefaultArgs,
  rPlatformIconSrcLabels,
  rPlatformIconStoryControlInclude,
} from "../../../../../.storybook/fixtures/platformIconStoryControls";
import { STORYBOOK_NON_CACHED_ICON_SVG } from "../../../../../.storybook/fixtures/urls";
import RPlatformIcon from "./RPlatformIcon.vue";

type StoryArgs = {
  src: (typeof R_PLATFORM_ICON_SRC_OPTIONS)[number];
  useFallback: boolean;
  fallbackSrc: typeof DEFAULT_PLATFORM_ICON;
  size: number;
  alt: string;
  title: string;
  showTooltip: boolean;
  name?: string;
  slug?: string;
  fsSlug?: string;
};

const meta: Meta<StoryArgs> = {
  title: "Media/RPlatformIcon",
  component: RPlatformIcon,
  args: rPlatformIconDefaultArgs as StoryArgs,
  parameters: {
    controls: { include: [...rPlatformIconStoryControlInclude] },
  },
  argTypes: {
    src: {
      control: "select",
      options: [...R_PLATFORM_ICON_SRC_OPTIONS],
      labels: rPlatformIconSrcLabels,
    },
    useFallback: { control: "boolean" },
    fallbackSrc: {
      control: "select",
      options: [DEFAULT_PLATFORM_ICON],
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
    slug: { control: false, table: { disable: true } },
    fsSlug: { control: false, table: { disable: true } },
  },
  render: (args) => ({
    components: { RPlatformIcon },
    setup() {
      const fallbackSrc = args.useFallback ? args.fallbackSrc : undefined;
      return { args, fallbackSrc };
    },
    template: `
      <RPlatformIcon
        :src="args.src"
        :fallback-src="fallbackSrc"
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

export const SrcMissingProdPathFallsBack: Story = {
  name: "Missing prod src",
  parameters: { controls: { disable: true } },
  render: () => ({
    components: { RPlatformIcon },
    template: `
      <RPlatformIcon
        :src="'${MISSING_PROD_SRC}'"
        :fallback-src="'${DEFAULT_PLATFORM_ICON}'"
        :size="40"
        alt="Missing platform"
        title="Missing prod asset"
        :show-tooltip="false"
      />
    `,
  }),
  play: async ({ canvasElement }) => {
    const triggerFallback = () => {
      canvasElement.querySelector("img")?.dispatchEvent(new Event("error"));
    };
    triggerFallback();
    await waitFor(() => {
      const img = canvasElement.querySelector("img");
      expect(img?.getAttribute("src")).toBe(DEFAULT_PLATFORM_ICON);
    });
  },
};

export const SrcFixtureNotInGlobPaints: Story = {
  name: "Fixture src",
  parameters: { controls: { disable: true } },
  render: () => ({
    components: { RPlatformIcon },
    template: `
      <RPlatformIcon
        :src="'${STORYBOOK_NON_CACHED_ICON_SVG}'"
        :fallback-src="'${DEFAULT_PLATFORM_ICON}'"
        :size="40"
        alt="Fixture icon"
        title="Storybook-only asset"
        :show-tooltip="false"
      />
    `,
  }),
  play: async ({ canvasElement }) => {
    const img = canvasElement.querySelector("img");
    expect(img?.getAttribute("src")).toMatch(/non-cached-icon\.svg$/);
  },
};

export const ShippedIconRow: Story = {
  name: "Shipped row",
  parameters: { controls: { disable: true } },
  render: () => ({
    components: { RPlatformIcon },
    template: `
      <div style="display:flex;gap:.5rem;align-items:center">
        <RPlatformIcon :src="'${SHIPPED_SNES_SRC}'" :fallback-src="'${DEFAULT_PLATFORM_ICON}'" title="SNES" :show-tooltip="false" />
        <RPlatformIcon :src="'${SHIPPED_NES_SRC}'" :fallback-src="'${DEFAULT_PLATFORM_ICON}'" title="NES" :show-tooltip="false" />
        <RPlatformIcon :src="'${SHIPPED_GBA_SRC}'" :fallback-src="'${DEFAULT_PLATFORM_ICON}'" title="GBA" :show-tooltip="false" />
        <RPlatformIcon :src="'${MISSING_PROD_SRC}'" :fallback-src="'${DEFAULT_PLATFORM_ICON}'" title="Missing" :show-tooltip="false" />
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
    controls: {
      include: [...platformGalleryControlInclude, "useFallback"],
    },
  },
  args: {
    ...platformGalleryDefaultArgs,
    useFallback: true,
    fallbackSrc: DEFAULT_PLATFORM_ICON,
  },
  argTypes: {
    ...platformGalleryArgTypes,
    useFallback: { control: "boolean" },
    fallbackSrc: { control: false, table: { disable: true } },
    src: { control: false, table: { disable: true } },
    alt: { control: false, table: { disable: true } },
    title: { control: false, table: { disable: true } },
  },
  render: (args) => ({
    components: { RPlatformIcon },
    setup() {
      const fallback = args.useFallback ? args.fallbackSrc : undefined;
      return {
        args,
        fallback,
        icons: shippedPlatformGalleryEntries,
        styles: platformGalleryStyles,
      };
    },
    template: rPlatformIconGalleryTemplate,
  }),
};

export const Sizes: Story = {
  name: "Sizes",
  parameters: platformSizesStoryParameters,
  render: () => ({
    components: { RPlatformIcon },
    setup() {
      return {
        icons: shippedPlatformGalleryEntries,
        sizes: platformSizeLadderSteps,
        fallback: DEFAULT_PLATFORM_ICON,
        styles: platformSizesStoryStyles,
      };
    },
    template: rPlatformIconSizesTemplate,
  }),
};

export const InsideFlexParent: Story = {
  name: "Flex parent",
  parameters: { controls: { disable: true } },
  render: () => ({
    components: { RPlatformIcon },
    template: `
      <div style="display:flex;align-items:center;gap:6px;padding:6px;border:1px dashed var(--r-color-border);border-radius:6px">
        <span style="font:11px sans-serif;color:var(--r-color-fg-muted)">flex parent</span>
        <RPlatformIcon :src="'${SHIPPED_SNES_SRC}'" :fallback-src="'${DEFAULT_PLATFORM_ICON}'" :size="22" :show-tooltip="false" />
      </div>
    `,
  }),
};
