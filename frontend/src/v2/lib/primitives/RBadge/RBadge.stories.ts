import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RAvatar from "../RAvatar/RAvatar.vue";
import RIcon from "../RIcon/RIcon.vue";
import RBadge from "./RBadge.vue";

const meta: Meta<typeof RBadge> = {
  title: "Primitives/RBadge",
  component: RBadge,
  argTypes: {
    content: { control: "text" },
    color: { control: "text" },
    icon: { control: "text" },
    location: {
      control: "select",
      options: [
        "top",
        "bottom",
        "start",
        "end",
        "top start",
        "top end",
        "bottom start",
        "bottom end",
      ],
    },
    dot: { control: "boolean" },
    inline: { control: "boolean" },
    bordered: { control: "boolean" },
    floating: { control: "boolean" },
    modelValue: { control: "boolean" },
    max: { control: "number" },
  },
};

export default meta;

type Story = StoryObj<typeof RBadge>;

// ── Content modes ───────────────────────────────────────────────────

export const Count: Story = {
  args: { content: "7" },
  render: (args) => ({
    components: { RBadge, RIcon },
    setup: () => ({ args }),
    template: `
      <RBadge v-bind="args">
        <RIcon icon="mdi-bell" size="28" />
      </RBadge>
    `,
  }),
};

export const Dot: Story = {
  args: { dot: true, color: "success" },
  render: (args) => ({
    components: { RBadge, RAvatar },
    setup: () => ({ args }),
    template: `
      <RBadge v-bind="args">
        <RAvatar color="primary" size="40">YZ</RAvatar>
      </RBadge>
    `,
  }),
};

export const IconBadge: Story = {
  name: "Icon content",
  args: { icon: "mdi-check", color: "success" },
  render: (args) => ({
    components: { RBadge, RAvatar },
    setup: () => ({ args }),
    template: `
      <RBadge v-bind="args">
        <RAvatar color="primary" size="48">YZ</RAvatar>
      </RBadge>
    `,
  }),
};

// ── Max / clamping ──────────────────────────────────────────────────

export const MaxClamp: Story = {
  name: "max clamping",
  render: () => ({
    components: { RBadge, RIcon },
    template: `
      <div style="display:flex;gap:36px;align-items:center;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge :content="3" :max="99"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>3</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge :content="42" :max="99"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>42</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge :content="100" :max="99"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>100 (clamped → 99+)</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge :content="999" :max="999"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>999 (max raised)</span>
        </div>
      </div>
    `,
  }),
};

// ── Locations ───────────────────────────────────────────────────────

export const Locations: Story = {
  name: "All 8 locations",
  render: () => ({
    components: { RBadge, RAvatar },
    template: `
      <div style="display:grid;grid-template-columns:repeat(4,auto);gap:32px 36px;align-items:center;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="top start"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>top start</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="top"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>top</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="top end"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>top end</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="end"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>end</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="bottom end"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>bottom end</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="bottom"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>bottom</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="bottom start"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>bottom start</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="7" location="start"><RAvatar color="primary" size="48">YZ</RAvatar></RBadge>
          <span>start</span>
        </div>
      </div>
    `,
  }),
};

// ── Modifiers ───────────────────────────────────────────────────────

export const Bordered: Story = {
  name: "Bordered (contrast ring)",
  render: () => ({
    components: { RBadge, RAvatar },
    template: `
      <div style="display:flex;gap:36px;align-items:center;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge dot color="success" location="bottom end">
            <RAvatar color="primary" size="48">YZ</RAvatar>
          </RBadge>
          <span>plain</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge dot color="success" bordered location="bottom end">
            <RAvatar color="primary" size="48">YZ</RAvatar>
          </RBadge>
          <span>bordered</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="5" bordered location="top end">
            <RAvatar color="accent" size="48">EM</RAvatar>
          </RBadge>
          <span>count + bordered</span>
        </div>
      </div>
    `,
  }),
};

export const Floating: Story = {
  name: "Floating (pushed further out)",
  render: () => ({
    components: { RBadge, RIcon },
    template: `
      <div style="display:flex;gap:36px;align-items:center;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="3"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>default</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="3" floating><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>floating</span>
        </div>
      </div>
    `,
  }),
};

export const Inline: Story = {
  name: "Inline (next to label)",
  render: () => ({
    components: { RBadge },
    template: `
      <div style="display:flex;flex-direction:column;gap:8px;font:13px/1.4 sans-serif;color:var(--r-color-fg)">
        <RBadge inline content="4" color="primary">
          <span>Inbox</span>
        </RBadge>
        <RBadge inline content="12" color="info">
          <span>Drafts</span>
        </RBadge>
        <RBadge inline content="142" :max="99" color="danger">
          <span>Spam</span>
        </RBadge>
      </div>
    `,
  }),
};

// ── Tones ───────────────────────────────────────────────────────────

export const Tones: Story = {
  render: () => ({
    components: { RBadge, RIcon },
    template: `
      <div style="display:grid;grid-template-columns:repeat(4,auto);gap:24px 28px;align-items:center;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9" color="primary"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>primary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9" color="secondary"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>secondary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9" color="accent"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>accent</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9" color="success"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>success</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9" color="warning"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>warning</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9" color="danger"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>danger</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9" color="info"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>info</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RBadge content="9"><RIcon icon="mdi-bell" size="28" /></RBadge>
          <span>default (error)</span>
        </div>
      </div>
    `,
  }),
};

// ── Motion ──────────────────────────────────────────────────────────

export const PopAnimation: Story = {
  name: "Pop animation (toggle modelValue)",
  render: () => ({
    components: { RBadge, RAvatar },
    setup() {
      const show = ref(true);
      return { show };
    },
    template: `
      <div style="display:flex;flex-direction:column;align-items:center;gap:18px;font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
        <RBadge :model-value="show" content="3" color="primary">
          <RAvatar color="accent" size="56">EM</RAvatar>
        </RBadge>
        <button
          type="button"
          style="padding:8px 16px;background:var(--r-color-brand-primary);color:white;border:none;border-radius:8px;font-weight:600;cursor:pointer"
          @click="show = !show"
        >
          {{ show ? "Hide badge" : "Show badge" }}
        </button>
        <span>Toggle to see the spring pop-in / quick fade-out.</span>
      </div>
    `,
  }),
};
