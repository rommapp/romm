import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RTextField from "@/v2/lib/forms/RTextField/RTextField.vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RCard from "@/v2/lib/primitives/RCard/RCard.vue";
import RExpandTransition from "./RExpandTransition.vue";

const meta: Meta<typeof RExpandTransition> = {
  title: "Structural/RExpandTransition",
  component: RExpandTransition,
  argTypes: {
    appear: { control: "boolean" },
    duration: { control: "text" },
  },
};

export default meta;
type Story = StoryObj<typeof RExpandTransition>;

// ── v-if — mount/unmount ─────────────────────────────────────────

export const VIf: Story = {
  name: "v-if (mount/unmount)",
  render: (args) => ({
    components: { RExpandTransition, RBtn, RCard },
    setup: () => ({ args, open: ref(false) }),
    template: `
      <div style="padding:40px;display:flex;flex-direction:column;gap:12px;max-width:420px">
        <RBtn variant="translucent" @click="open = !open">
          {{ open ? 'Hide' : 'Reveal' }} details
        </RBtn>
        <RExpandTransition v-bind="args">
          <RCard v-if="open" variant="elevated">
            <div style="padding:14px;font:13px sans-serif">
              <p style="margin:0 0 8px"><strong>Variable height content</strong></p>
              <p style="margin:0;line-height:1.5">
                The wrapper measures <code>scrollHeight</code> on enter
                and animates from 0 to that value. Same on leave, in
                reverse — so the panel collapses smoothly regardless of
                how tall its content grew while open.
              </p>
            </div>
          </RCard>
        </RExpandTransition>
      </div>
    `,
  }),
};

// ── v-show — display toggle ─────────────────────────────────────

export const VShow: Story = {
  name: "v-show (display toggle)",
  render: () => ({
    components: { RExpandTransition, RBtn, RCard },
    setup: () => ({ open: ref(true) }),
    template: `
      <div style="padding:40px;display:flex;flex-direction:column;gap:12px;max-width:420px">
        <RBtn variant="translucent" @click="open = !open">
          {{ open ? 'Hide' : 'Show' }} panel
        </RBtn>
        <RExpandTransition>
          <RCard v-show="open" variant="elevated">
            <div style="padding:14px;font:13px sans-serif">
              The element stays in the DOM — only <code>display</code>
              flips. Use v-show when remount cost matters (e.g. holding
              an iframe, video, or expensive form state).
            </div>
          </RCard>
        </RExpandTransition>
      </div>
    `,
  }),
};

// ── Conditional sibling sections ─────────────────────────────────

export const TwoPanels: Story = {
  name: "Mode swap (Login-style)",
  render: () => ({
    components: { RExpandTransition, RBtn, RCard, RTextField },
    setup: () => ({ forgotMode: ref(false) }),
    template: `
      <div style="padding:40px;display:flex;flex-direction:column;gap:8px;max-width:380px">
        <RExpandTransition>
          <div v-show="!forgotMode" style="display:flex;flex-direction:column;gap:10px">
            <RTextField label="Username" prefix-label="stacked" />
            <RTextField label="Password" type="password" prefix-label="stacked" />
            <RBtn variant="text" size="small" @click="forgotMode = true">
              Forgot password?
            </RBtn>
          </div>
        </RExpandTransition>

        <RExpandTransition>
          <div v-show="forgotMode" style="display:flex;flex-direction:column;gap:10px">
            <RTextField label="Email" prefix-label="stacked" />
            <RBtn variant="text" size="small" @click="forgotMode = false">
              ← Back to sign in
            </RBtn>
          </div>
        </RExpandTransition>
      </div>
    `,
  }),
};

// ── Initial mount animation ──────────────────────────────────────

export const Appear: Story = {
  name: "appear (animate on mount)",
  args: { appear: true },
  render: (args) => ({
    components: { RExpandTransition, RCard },
    setup: () => ({ args }),
    template: `
      <div style="padding:40px;max-width:420px">
        <RExpandTransition v-bind="args">
          <RCard variant="elevated">
            <div style="padding:14px;font:13px sans-serif">
              With <code>appear</code>, the element animates in even on
              the first render — useful for landing pages or onboarding
              cards that should feel deliberate when first painted.
            </div>
          </RCard>
        </RExpandTransition>
      </div>
    `,
  }),
};

// ── Custom duration ──────────────────────────────────────────────

export const CustomDuration: Story = {
  name: "Custom duration",
  args: { duration: "500ms" },
  render: (args) => ({
    components: { RExpandTransition, RBtn, RCard },
    setup: () => ({ args, open: ref(false) }),
    template: `
      <div style="padding:40px;display:flex;flex-direction:column;gap:12px;max-width:420px">
        <RBtn variant="translucent" @click="open = !open">Toggle</RBtn>
        <RExpandTransition v-bind="args">
          <RCard v-if="open" variant="elevated">
            <div style="padding:14px;font:13px sans-serif">
              Slow expand at 500ms — pass any CSS time value to the
              <code>duration</code> prop.
            </div>
          </RCard>
        </RExpandTransition>
      </div>
    `,
  }),
};
