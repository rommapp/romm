// MetadataProviderCard renders every metadata-provider surface: the
// settings tiles (tile layout, footer actions), the setup wizard step
// and the scan reference dialog (row layout, description + pills).
// The tile grid story reproduces the settings scenario that motivated
// the shared card: rows of unequal header height must keep every
// footer pinned to the bottom edge.
import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import MetadataProviderCard from "./MetadataProviderCard.vue";
import type { ProviderCardStatus } from "./types";

const logo = (label: string, color: string) =>
  `https://placehold.co/96x96/${color}/white?text=${label}`;

const ok: ProviderCardStatus = {
  tone: "success",
  icon: "mdi-check-circle-outline",
  label: "API key valid",
};
const missing: ProviderCardStatus = {
  tone: "neutral",
  icon: "mdi-key-alert-outline",
  label: "API key missing",
};
const disabled: ProviderCardStatus = {
  tone: "warning",
  icon: "mdi-power-plug-off-outline",
  label: "Disabled",
};
const checking: ProviderCardStatus = {
  tone: "neutral",
  icon: "mdi-progress-helper",
  label: "Checking...",
};

const meta: Meta<typeof MetadataProviderCard> = {
  title: "Shared/MetadataProviderCard",
  component: MetadataProviderCard,
  // The canvas body is not theme-painted; give the cards the app's
  // background so the light theme reads correctly.
  decorators: [
    () => ({
      template: `
        <div style="padding: 24px; background: var(--r-color-bg); border-radius: var(--r-radius-lg);">
          <story />
        </div>
      `,
    }),
  ],
};

export default meta;

type Story = StoryObj<typeof MetadataProviderCard>;

// The settings grid: card 3 carries a subtitle, so the row is taller
// than cards 1 and 2 need. Their footers must still sit on the bottom
// edge with the spare space absorbed above them, not below.
export const TileGrid: Story = {
  name: "Tile · settings grid",
  render: () => ({
    components: { MetadataProviderCard, RBtn },
    setup: () => ({ logo, ok, missing }),
    template: `
      <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; max-width: 900px;">
        <MetadataProviderCard name="IGDB" :logo="logo('IG', 'indigo')" :status="ok">
          <template #actions>
            <RBtn variant="translucent" size="small" prepend-icon="mdi-key-variant">Get API key</RBtn>
            <RBtn variant="text" size="small" prepend-icon="mdi-open-in-new">Website</RBtn>
          </template>
        </MetadataProviderCard>
        <MetadataProviderCard name="LaunchBox" :logo="logo('LB', 'teal')" :status="ok">
          <template #actions>
            <RBtn variant="text" size="small" prepend-icon="mdi-open-in-new">Website</RBtn>
          </template>
        </MetadataProviderCard>
        <MetadataProviderCard
          name="SteamGridDB"
          subtitle="Cover art"
          :logo="logo('SG', 'darkgreen')"
          :status="missing"
          dimmed
        >
          <template #actions>
            <RBtn variant="translucent" size="small" prepend-icon="mdi-key-variant">Get API key</RBtn>
            <RBtn variant="text" size="small" prepend-icon="mdi-open-in-new">Website</RBtn>
          </template>
        </MetadataProviderCard>
      </div>
    `,
  }),
};

// The setup wizard rows: description, mono setup pill, warning caveat
// pill and a status chip in the pill row.
export const RowList: Story = {
  name: "Row · wizard list",
  render: () => ({
    components: { MetadataProviderCard },
    setup: () => ({ logo, ok, disabled, checking }),
    template: `
      <div style="display: grid; gap: 8px; max-width: 560px;">
        <MetadataProviderCard
          layout="row"
          name="ScreenScraper"
          :logo="logo('SS', 'navy')"
          :status="ok"
          setup-hint="SCREENSCRAPER_USER + SCREENSCRAPER_PASSWORD"
        >
          <template #description>
            Community database with strong coverage of European releases.
          </template>
        </MetadataProviderCard>
        <MetadataProviderCard
          layout="row"
          name="MobyGames"
          :logo="logo('MG', 'maroon')"
          :status="checking"
          setup-hint="MOBYGAMES_API_KEY"
          caveat="Free tier is heavily rate-limited"
        >
          <template #description>
            The oldest game catalog on the web.
          </template>
        </MetadataProviderCard>
        <MetadataProviderCard
          layout="row"
          name="LaunchBox"
          :logo="logo('LB', 'teal')"
          :status="disabled"
          setup-hint="LAUNCHBOX_API_ENABLED=true"
          caveat="Windows-centric platform list"
          dimmed
        >
          <template #description>
            Crowd-sourced database from the LaunchBox frontend.
          </template>
        </MetadataProviderCard>
      </div>
    `,
  }),
};

// The scan reference dialog rows: same row layout without a status
// chip, so the pills close the card.
export const RowReference: Story = {
  name: "Row · reference (no status)",
  render: () => ({
    components: { MetadataProviderCard },
    setup: () => ({ logo }),
    template: `
      <div style="display: grid; gap: 8px; max-width: 560px;">
        <MetadataProviderCard
          layout="row"
          name="IGDB"
          :logo="logo('IG', 'indigo')"
          setup-hint="IGDB_CLIENT_ID + IGDB_CLIENT_SECRET"
        >
          <template #description>
            Twitch's game database. Broadest coverage of modern platforms.
          </template>
        </MetadataProviderCard>
        <MetadataProviderCard
          layout="row"
          name="Hasheous"
          :logo="logo('HA', 'purple')"
          setup-hint="HASHEOUS_API_ENABLED=true"
          caveat="Proxy: feeds ids into the catalogs"
        >
          <template #description>
            Hash-matching proxy that identifies ROMs by checksum.
          </template>
        </MetadataProviderCard>
      </div>
    `,
  }),
};
