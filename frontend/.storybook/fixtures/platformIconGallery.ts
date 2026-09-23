import { listShippedPlatformIcons } from "../../src/v2/composables/usePlatformIconCache/iconCache";
import {
  PLATFORM_ICON_SIZE_MAX,
  PLATFORM_ICON_SIZE_MIN,
} from "./platformIconStoryControls";

/** Same allowlist as production; built from `import.meta.glob` in iconCache. */
export const shippedPlatformGalleryEntries = listShippedPlatformIcons();

export const platformGalleryDefaultArgs = {
  size: 32,
  showTooltip: true,
  showLabels: true,
};

export const platformGallerySizeArgType = {
  control: {
    type: "range" as const,
    min: PLATFORM_ICON_SIZE_MIN,
    max: PLATFORM_ICON_SIZE_MAX,
    step: 1,
  },
};

export const platformGalleryArgTypes = {
  size: platformGallerySizeArgType,
  showTooltip: { control: "boolean" as const },
  showLabels: { control: "boolean" as const },
};

export const platformGalleryControlInclude = [
  "size",
  "showTooltip",
  "showLabels",
] as const;

export const platformGalleryStoryParameters = {
  layout: "fullscreen" as const,
  a11y: { test: "off" as const },
};

/** Bordered tile used in All platforms and Sizes stories. */
export const platformIconStoryBorderedCell =
  "box-sizing:border-box;display:flex;flex-direction:column;align-items:center;text-align:center;border:1px solid var(--r-color-border);border-radius:var(--r-radius-md)";

export const platformGalleryStyles = {
  shell:
    "box-sizing:border-box;display:flex;flex-direction:column;gap:var(--r-space-4);width:100%;min-height:100vh;padding:var(--r-space-5)",
  meta: "margin:0;font:11px/1.4 sans-serif;color:var(--r-color-fg-muted)",
  grid: "flex:1;width:100%;display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:var(--r-space-3);align-content:start",
  cell: `${platformIconStoryBorderedCell};gap:var(--r-space-2);padding:var(--r-space-3) var(--r-space-2)`,
  label:
    "font:10px/1.25 sans-serif;color:var(--r-color-fg-muted);word-break:break-all;max-width:100%",
};

export const platformIconGalleryTemplate = `
  <div :style="styles.shell">
    <p :style="styles.meta">{{ icons.length }} shipped platform icons</p>
    <div :style="styles.grid">
      <div
        v-for="entry in icons"
        :key="entry.slug"
        :style="styles.cell"
      >
        <PlatformIcon
          :slug="entry.slug"
          :size="args.size"
          :title="entry.slug"
          :show-tooltip="args.showTooltip"
        />
        <span v-if="args.showLabels" :style="styles.label">{{ entry.slug }}</span>
      </div>
    </div>
  </div>
`;

export const platformSizeLadderSteps = [72, 48, 32, 22, 16] as const;

export const platformSizesStoryParameters = {
  layout: "fullscreen" as const,
  a11y: { test: "off" as const },
  controls: { disable: true as const },
};

export const platformSizesStoryStyles = {
  shell:
    "box-sizing:border-box;width:100%;min-height:100vh;padding:var(--r-space-3) var(--r-space-4);display:flex;flex-direction:column;align-items:center;gap:var(--r-space-2)",
  row: "box-sizing:border-box;width:100%;max-width:760px;display:flex;flex-direction:column;align-items:flex-start;gap:var(--r-space-2);padding:var(--r-space-6) 0",
  rowTitle:
    "margin:0;text-align:left;display:inline-block;width:fit-content;max-width:100%;overflow-wrap:anywhere;font-family:var(--r-font-family-mono);font-size:18px;line-height:1.4;padding:2px 8px;border:1px solid var(--r-color-border);border-radius:var(--r-radius-sm);background:var(--r-color-surface);color:var(--r-color-fg)",
  sizeRun:
    "display:flex;flex-wrap:nowrap;justify-content:flex-start;gap:var(--r-space-3)",
  sizeCell: `${platformIconStoryBorderedCell};gap:var(--r-space-1);padding:var(--r-space-3) var(--r-space-2);width:72px;flex-shrink:0`,
  sizeLabel: `${platformGalleryStyles.label};text-align:center`,
  sizeSlot:
    "box-sizing:border-box;width:100%;height:72px;display:flex;align-items:flex-end;justify-content:center",
};

export const platformIconSizesTemplate = `
  <div :style="styles.shell">
    <div
      v-for="entry in icons"
      :key="entry.slug"
      :style="styles.row"
    >
      <code :style="styles.rowTitle">{{ entry.slug }}</code>
      <div :style="styles.sizeRun">
        <div
          v-for="size in sizes"
          :key="size"
          :style="styles.sizeCell"
        >
          <div :style="styles.sizeSlot">
            <PlatformIcon
              :slug="entry.slug"
              :size="size"
              :show-tooltip="false"
            />
          </div>
          <span :style="styles.sizeLabel">{{ size }}px</span>
        </div>
      </div>
    </div>
  </div>
`;
