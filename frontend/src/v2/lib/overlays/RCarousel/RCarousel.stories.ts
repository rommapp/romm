import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { ref } from "vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RCarousel from "./RCarousel.vue";

// Sample images — picsum is deterministic by seed and works offline through
// the Storybook CDN cache.
const SAMPLES = [
  "https://picsum.photos/seed/r-carousel-1/1280/720",
  "https://picsum.photos/seed/r-carousel-2/1280/720",
  "https://picsum.photos/seed/r-carousel-3/1280/720",
  "https://picsum.photos/seed/r-carousel-4/1280/720",
  "https://picsum.photos/seed/r-carousel-5/1280/720",
];

const meta: Meta<typeof RCarousel> = {
  title: "Overlays/RCarousel",
  component: RCarousel,
  argTypes: {
    fullscreen: { control: "boolean" },
    loop: { control: "boolean" },
    showCounter: { control: "boolean" },
    showArrows: { control: "boolean" },
    showThumbnails: { control: "boolean" },
    closeLabel: { control: "text" },
    prevLabel: { control: "text" },
    nextLabel: { control: "text" },
    ariaLabel: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RCarousel>;

export const Inline: Story = {
  args: {
    items: SAMPLES,
    loop: true,
    showThumbnails: true,
    ariaLabel: "Image carousel",
  },
  render: (args) => ({
    components: { RCarousel },
    setup() {
      const index = ref(0);
      return { args, index };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 32px; background: #07070f; min-height: 540px;">
        <RCarousel
          v-bind="args"
          v-model="index"
          style="width: 720px; height: 460px;"
        >
          <template #default="{ item, index }">
            <img :src="item" :alt="'Slide ' + (index + 1)" style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px;" />
          </template>
          <template #thumbnail="{ item }">
            <img :src="item" />
          </template>
        </RCarousel>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);

    await step("counter renders 1 / N to start", async () => {
      const counter = await canvas.findByText("1 / 5");
      expect(counter).toBeInTheDocument();
    });

    await step("clicking next advances the index", async () => {
      const next = canvas.getByRole("button", { name: "Next" });
      await userEvent.click(next);
      const counter = await canvas.findByText("2 / 5");
      expect(counter).toBeInTheDocument();
    });

    await step("clicking prev rewinds", async () => {
      const prev = canvas.getByRole("button", { name: "Previous" });
      await userEvent.click(prev);
      const counter = await canvas.findByText("1 / 5");
      expect(counter).toBeInTheDocument();
    });

    await step("loop wraps from first to last on prev", async () => {
      const prev = canvas.getByRole("button", { name: "Previous" });
      await userEvent.click(prev);
      const counter = await canvas.findByText("5 / 5");
      expect(counter).toBeInTheDocument();
    });

    await step("clicking a thumbnail jumps to that index", async () => {
      const thumbs = canvas.getAllByRole("button", { name: /^\d+ \/ 5$/ });
      await userEvent.click(thumbs[2]);
      const counter = await canvas.findByText("3 / 5");
      expect(counter).toBeInTheDocument();
    });
  },
};

export const InlineLight: Story = {
  args: {
    items: SAMPLES,
    showThumbnails: true,
  },
  render: (args) => ({
    components: { RCarousel },
    setup() {
      const index = ref(0);
      return { args, index };
    },
    template: `
      <div class="r-v2 r-v2-light" style="padding: 32px; background: #f4f4f8; min-height: 540px;">
        <RCarousel
          v-bind="args"
          v-model="index"
          style="width: 720px; height: 460px;"
        >
          <template #default="{ item, index }">
            <img :src="item" :alt="'Slide ' + (index + 1)" style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px;" />
          </template>
          <template #thumbnail="{ item }">
            <img :src="item" />
          </template>
        </RCarousel>
      </div>
    `,
  }),
};

export const Fullscreen: Story = {
  args: {
    items: SAMPLES,
    fullscreen: true,
    loop: true,
    showThumbnails: true,
    ariaLabel: "Screenshot lightbox",
  },
  render: (args) => ({
    components: { RCarousel, RBtn },
    setup() {
      const index = ref<number | null>(null);
      const onClose = fn(() => (index.value = null));
      return { args, index, onClose };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 32px; background: #07070f; min-height: 540px;">
        <RBtn @click="index = 0">Open lightbox</RBtn>
        <RCarousel
          v-if="index !== null"
          v-bind="args"
          v-model="index"
          @close="onClose"
        >
          <template #default="{ item, index }">
            <img :src="item" :alt="'Slide ' + (index + 1)" />
          </template>
          <template #thumbnail="{ item }">
            <img :src="item" />
          </template>
        </RCarousel>
      </div>
    `,
  }),
};

export const NoLoop: Story = {
  args: {
    items: SAMPLES.slice(0, 3),
    loop: false,
  },
  render: (args) => ({
    components: { RCarousel },
    setup() {
      const index = ref(0);
      return { args, index };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 32px; background: #07070f; min-height: 360px;">
        <RCarousel
          v-bind="args"
          v-model="index"
          style="width: 560px; height: 320px;"
        >
          <template #default="{ item, index }">
            <img :src="item" :alt="'Slide ' + (index + 1)" style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px;" />
          </template>
        </RCarousel>
      </div>
    `,
  }),
};

export const SingleItem: Story = {
  args: {
    items: SAMPLES.slice(0, 1),
  },
  render: (args) => ({
    components: { RCarousel },
    setup() {
      const index = ref(0);
      return { args, index };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 32px; background: #07070f; min-height: 360px;">
        <RCarousel
          v-bind="args"
          v-model="index"
          style="width: 560px; height: 320px;"
        >
          <template #default="{ item }">
            <img :src="item" alt="Single slide" style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px;" />
          </template>
        </RCarousel>
      </div>
    `,
  }),
};
