import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { defineComponent, h } from "vue";

// Intro / design-token preview story. Exists to verify the Storybook pipeline
// end-to-end (tokens + theme switcher) before any R-components land.

const tokenSwatches = [
  {
    title: "Brand",
    vars: [
      "--r-color-brand-primary",
      "--r-color-brand-primary-hover",
      "--r-color-brand-primary-pressed",
      "--r-color-brand-accent",
    ],
  },
  {
    title: "Semantic surface",
    vars: [
      "--r-color-bg",
      "--r-color-bg-elevated",
      "--r-color-surface",
      "--r-color-fg",
      "--r-color-fg-muted",
      "--r-color-border",
    ],
  },
  {
    title: "Status",
    vars: [
      "--r-color-success",
      "--r-color-warning",
      "--r-color-danger",
      "--r-color-info",
    ],
  },
  {
    title: "Romm brand",
    vars: [
      "--r-color-romm-red",
      "--r-color-romm-green",
      "--r-color-romm-blue",
      "--r-color-romm-gold",
    ],
  },
];

const VisualLanguage = defineComponent({
  setup() {
    return () =>
      h(
        "div",
        {
          class: "r-v2",
          style: {
            padding: "var(--r-space-8)",
            minWidth: "720px",
            display: "flex",
            flexDirection: "column",
            gap: "var(--r-space-6)",
          },
        },
        [
          h("h1", { style: { margin: 0 } }, "RomM v2 Design System"),
          h(
            "p",
            { style: { margin: 0, color: "var(--r-color-fg-muted)" } },
            "Toggle dark/light in the Storybook toolbar. Components land here as each wave ships.",
          ),
          ...tokenSwatches.map((group) =>
            h("section", { key: group.title }, [
              h(
                "h2",
                {
                  style: {
                    fontSize: "var(--r-font-size-lg)",
                    fontWeight: "var(--r-font-weight-semibold)",
                    margin: "0 0 var(--r-space-3) 0",
                  },
                },
                group.title,
              ),
              h(
                "div",
                {
                  style: {
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                    gap: "var(--r-space-3)",
                  },
                },
                group.vars.map((v) =>
                  h(
                    "div",
                    {
                      key: v,
                      style: {
                        borderRadius: "var(--r-radius-md)",
                        background: `var(${v})`,
                        height: "72px",
                        display: "flex",
                        alignItems: "end",
                        padding: "var(--r-space-2)",
                        border: "1px solid var(--r-color-border)",
                        color: "#fff",
                        fontFamily: "var(--r-font-family-mono)",
                        fontSize: "var(--r-font-size-xs)",
                        textShadow: "0 1px 2px rgba(0,0,0,0.6)",
                      },
                    },
                    v,
                  ),
                ),
              ),
            ]),
          ),
        ],
      );
  },
});

const meta: Meta<typeof VisualLanguage> = {
  title: "Visual Language",
  component: VisualLanguage,
  parameters: {
    layout: "fullscreen",
  },
};

export default meta;

type Story = StoryObj;

export const DesignTokens: Story = {};
