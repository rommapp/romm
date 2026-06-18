import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { onMounted, onUnmounted, ref } from "vue";
import "./RImg.stories.css";
import RImg from "./RImg.vue";

const meta: Meta<typeof RImg> = {
  title: "Primitives/RImg",
  component: RImg,
  argTypes: {
    src: { control: "text" },
    alt: { control: "text" },
    width: { control: "text" },
    height: { control: "text" },
    cover: { control: "boolean" },
    contain: { control: "boolean" },
    aspectRatio: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RImg>;

// A small known-good image we can use without network access in
// Storybook. The local logo ships at /assets/isotipo.svg.
const LOGO = "/assets/isotipo.svg";
// Picsum is fine in Storybook; we use seed-based URLs so each story
// renders a reproducible image.
const PHOTO = "https://picsum.photos/seed/romm/600/400";
const PHOTO_TALL = "https://picsum.photos/seed/romm-tall/300/600";

// ── Basic ────────────────────────────────────────────────────────────

export const Default: Story = {
  args: { src: LOGO, width: 80, alt: "RomM logo" },
};

export const NaturalSize: Story = {
  name: "Natural size (no width / height)",
  args: { src: LOGO, alt: "RomM logo" },
};

// ── Sizing ───────────────────────────────────────────────────────────

export const WidthOnly: Story = {
  name: "Width only — auto height",
  render: () => ({
    components: { RImg },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RImg src="${LOGO}" :width="32" alt="logo" />
          <span>width 32</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RImg src="${LOGO}" :width="64" alt="logo" />
          <span>width 64</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RImg src="${LOGO}" :width="128" alt="logo" />
          <span>width 128</span>
        </div>
      </div>
    `,
  }),
};

export const CoverFit: Story = {
  name: "cover · width × height",
  render: () => ({
    components: { RImg },
    template: `
      <div style="display:flex;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RImg src="${PHOTO}" :width="160" :height="100" cover alt="cover" style="border-radius:8px" />
          <span>cover · 160×100</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RImg src="${PHOTO_TALL}" :width="160" :height="100" cover alt="cover tall" style="border-radius:8px" />
          <span>cover · tall src → cropped</span>
        </div>
      </div>
    `,
  }),
};

export const ContainFit: Story = {
  name: "contain · width × height",
  render: () => ({
    components: { RImg },
    template: `
      <div style="display:flex;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RImg
            src="${PHOTO}"
            :width="160"
            :height="100"
            contain
            alt="contain"
            style="border-radius:8px;background:var(--r-color-surface)"
          />
          <span>contain · letterboxed</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RImg
            src="${PHOTO_TALL}"
            :width="160"
            :height="100"
            contain
            alt="contain tall"
            style="border-radius:8px;background:var(--r-color-surface)"
          />
          <span>contain · tall src → letterboxed</span>
        </div>
      </div>
    `,
  }),
};

export const AspectRatio: Story = {
  name: "aspectRatio (responsive)",
  render: () => ({
    components: { RImg },
    template: `
      <div style="display:flex;flex-direction:column;gap:16px;width:320px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div>
          <RImg src="${PHOTO}" aspect-ratio="16/9" cover style="width:100%;border-radius:8px" alt="16/9" />
          <div style="margin-top:6px">aspectRatio "16/9" · cover · width 100%</div>
        </div>
        <div>
          <RImg src="${PHOTO}" aspect-ratio="1/1" cover style="width:100%;border-radius:8px" alt="1/1" />
          <div style="margin-top:6px">aspectRatio "1/1" · cover · width 100%</div>
        </div>
        <div>
          <RImg src="${PHOTO}" aspect-ratio="4/3" cover style="width:100%;border-radius:8px" alt="4/3" />
          <div style="margin-top:6px">aspectRatio "4/3" · cover · width 100%</div>
        </div>
      </div>
    `,
  }),
};

// ── Slots ────────────────────────────────────────────────────────────

export const ErrorSlot: Story = {
  name: "error slot (fallback)",
  render: () => ({
    components: { RImg },
    template: `
      <div style="display:flex;align-items:center;gap:24px;font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
        <RImg src="/does-not-exist.png" :width="64" :height="64" alt="missing">
          <template #error>
            <div style="display:flex;flex-direction:column;align-items:center;gap:4px;color:var(--r-color-fg-faint)">
              <i class="mdi mdi-image-broken-variant" style="font-size:24px"></i>
              <span style="font-size:10px">missing</span>
            </div>
          </template>
        </RImg>
        <span>The src 404s — the <code>#error</code> slot renders instead.</span>
      </div>
    `,
  }),
};

export const LoadingSlot: Story = {
  name: "loading slot (placeholder)",
  render: () => ({
    components: { RImg },
    setup() {
      // The story controls how long the loading state lasts:
      //   1. Start with `src` empty — RImg renders the loading slot.
      //   2. After `loadingDelay` ms, set a real cache-busted src so
      //      the image fetches and `loaded` takes over.
      //   3. The "Reload" button restarts the cycle on demand.
      // This is how we make a network-fast image visibly demo the
      // loading state — without a delay proxy we'd flash past it in
      // a couple of frames.
      const src = ref<string | undefined>(undefined);
      const loadingDelay = 2500;
      let timer: ReturnType<typeof setTimeout> | undefined;
      let counter = 0;

      function reload() {
        if (timer) clearTimeout(timer);
        src.value = undefined;
        counter += 1;
        const myCounter = counter;
        timer = setTimeout(() => {
          // Cache-bust each cycle so picsum re-fetches.
          src.value = `https://picsum.photos/seed/r-img-loading-${myCounter}/400/400`;
        }, loadingDelay);
      }

      onMounted(reload);
      onUnmounted(() => {
        if (timer) clearTimeout(timer);
      });

      return { src, reload };
    },
    template: `
      <div style="display:flex;align-items:center;gap:24px;font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
        <RImg
          :src="src"
          :width="120"
          :height="120"
          cover
          alt="loading demo"
          style="border-radius:8px"
        >
          <template #loading>
            <div class="r-img-story-shimmer" />
          </template>
        </RImg>
        <div style="display:flex;flex-direction:column;gap:8px;max-width:240px">
          <span>The shimmer is forced visible for 2.5s before the image fetches. Click reload to re-trigger.</span>
          <button class="r-img-story-reload-btn" type="button" @click="reload">Reload</button>
        </div>
      </div>
    `,
  }),
};

export const DefaultSlotOverlay: Story = {
  name: "default slot (overlay over loaded image)",
  render: () => ({
    components: { RImg },
    template: `
      <RImg
        src="${PHOTO}"
        :width="320"
        :height="180"
        cover
        alt="overlay"
        style="border-radius:12px"
      >
        <div style="
          width:100%;height:100%;display:flex;align-items:flex-end;
          padding:12px;
          background: linear-gradient(
            180deg,
            transparent 40%,
            color-mix(in srgb, black 70%, transparent) 100%
          );
          color:white;font:600 14px/1.2 sans-serif;
        ">
          Overlay caption — composes on top of the image
        </div>
      </RImg>
    `,
  }),
};

// ── Real-world ──────────────────────────────────────────────────────

export const Logo: Story = {
  name: "Logo (AppNav usage)",
  render: () => ({
    components: { RImg },
    template: `
      <div style="display:inline-flex;align-items:center;gap:8px;padding:8px 12px;background:var(--r-color-surface);border-radius:8px">
        <RImg src="${LOGO}" :width="32" alt="isotipo" />
        <RImg src="/assets/logotipo.svg" :width="70" alt="logotipo" />
      </div>
    `,
  }),
};
