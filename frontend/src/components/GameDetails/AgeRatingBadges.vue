<script setup lang="ts">
// AgeRatingBadges: renders the ROM's age ratings as visual badges.
// Mirrors v1's matching logic (Details/Info/GameInfo.vue): the merged
// list of rating strings on `metadatum.age_ratings` is cross-referenced
// with `igdb_metadata.age_ratings` and `ss_metadata.age_ratings` to
// recover each entry's category + IGDB-hosted icon URL. Manually-typed
// entries shaped like "ESRB:T" / "PEGI:12" reconstruct the IGDB icon
// URL by convention. Anything we still can't resolve falls back to a
// chip with a shield icon so the rating stays semantically marked
// even without artwork.
import { computed, reactive } from "vue";
import { RIcon, RTooltip } from "@/lib";
import type { DetailedRom } from "@/stores/roms";
import { searchLocation } from "@/utils/searchLocation";

// IGDB hosts every rating icon at a conventional URL, but not every
// `category_rating` combo is actually populated: old/regional ratings
// 404 even though `igdbIconUrl` can build the URL. We track every URL
// that 404s in this Set so the matching badge swaps to the text chip
// fallback on the next paint, matching GameCard's "load image →
// fall back" pattern.
const failedImages = reactive(new Set<string>());

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRom }>();

// IGDB hosts the rating icons under category-specific folders; these
// slugs map our category codes to those folder names. ScreenScraper
// shares the same category codes so the same map serves both.
const CATEGORY_SLUG: Record<string, string> = {
  ESRB: "esrb",
  PEGI: "pegi",
  CERO: "cero",
  USK: "usk",
  GRAC: "grac",
  CLASS_IND: "class_ind",
  ACB: "acb",
};

type Badge = {
  rating: string;
  category: string;
  rating_cover_url?: string | undefined;
  label: string;
  // The stored entry, which the ageRatings search filter matches on.
  raw: string;
};

// IGDB icon URLs use lowercased rating codes with "+" stripped
// (e.g. "16+" → "16"). Mirrors v1's normalize fn so the URLs match.
function normalize(rating: string) {
  return rating.toString().toLowerCase().replace("+", "");
}

function igdbIconUrl(category: string, rating: string): string | undefined {
  const slug = CATEGORY_SLUG[category];
  if (!slug || !rating) return undefined;
  return `https://www.igdb.com/icons/rating_icons/${slug}/${slug}_${normalize(rating)}.png`;
}

// Ratings like "12" or "M" exist under several categories, so a rom can
// store the same string twice; each occurrence takes the next entry.
function queueByRating<T extends { rating: string }>(entries: T[]) {
  const queues = new Map<string, T[]>();
  for (const r of entries) {
    const key = r.rating.trim();
    const queue = queues.get(key);
    if (queue) queue.push(r);
    else queues.set(key, [r]);
  }
  return queues;
}

const badges = computed<Badge[]>(() => {
  const ratings = props.rom.metadatum?.age_ratings ?? [];
  const igdbByRating = queueByRating(
    props.rom.igdb_metadata?.age_ratings ?? [],
  );
  const ssByRating = queueByRating(props.rom.ss_metadata?.age_ratings ?? []);

  function resolve(entry: string): Omit<Badge, "label" | "raw"> {
    // Manually entered "CATEGORY:RATING": reconstruct the icon URL
    // by convention since there's no provider object to look up.
    if (entry.includes(":")) {
      const [categoryRaw, ratingRaw] = entry.split(":");
      const category = categoryRaw?.trim() ?? "";
      const rating = ratingRaw?.trim() ?? "";
      return {
        rating,
        category,
        rating_cover_url: igdbIconUrl(category, rating),
      };
    }

    const key = entry.trim();
    // IGDB entries already carry the icon URL.
    const igdbMatch = igdbByRating.get(key)?.shift();
    if (igdbMatch) return igdbMatch;

    // ScreenScraper entries carry the category but no icon URL;
    // reconstruct the same way as the manual case.
    const ssMatch = ssByRating.get(key)?.shift();
    if (ssMatch) {
      return {
        ...ssMatch,
        rating_cover_url: igdbIconUrl(ssMatch.category, ssMatch.rating),
      };
    }

    return { rating: entry, category: "", rating_cover_url: undefined };
  }

  return ratings.map((entry) => {
    const badge = resolve(entry);
    const label = badge.category
      ? `${badge.category}: ${badge.rating}`
      : badge.rating;
    return { ...badge, label, raw: entry };
  });
});
</script>

<template>
  <div v-if="badges.length" class="age-ratings">
    <RTooltip
      v-for="(b, i) in badges"
      :key="`${i}:${b.raw}`"
      :text="b.label"
      location="top"
      :open-delay="250"
    >
      <template #activator="{ props: activatorProps }">
        <router-link
          v-bind="activatorProps"
          class="age-ratings__link"
          :to="searchLocation('ageRatings', b.raw)"
        >
          <img
            v-if="b.rating_cover_url && !failedImages.has(b.rating_cover_url)"
            :src="b.rating_cover_url"
            :alt="b.label"
            class="age-ratings__img"
            loading="lazy"
            @error="failedImages.add(b.rating_cover_url!)"
          />
          <span v-else class="age-ratings__chip">
            <RIcon icon="mdi-shield-outline" size="13" />
            {{ b.label }}
          </span>
        </router-link>
      </template>
    </RTooltip>
  </div>
</template>

<style scoped>
.age-ratings {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.age-ratings__link {
  display: inline-flex;
  border-radius: var(--r-radius-sm);
  text-decoration: none;
}
.age-ratings__img {
  width: 44px;
  height: 44px;
  object-fit: contain;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  padding: 3px;
  border: 1px solid var(--r-color-border);
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.age-ratings__img:hover {
  transform: translateY(-1px);
  border-color: var(--r-color-border-strong);
}
.age-ratings__chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-chip);
  font-size: 11.5px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
  letter-spacing: 0.02em;
}
</style>
