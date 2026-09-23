/**
 * Storybook-only asset URLs (`/storybook-fixtures/...`).
 * Import from `*.stories.ts` only. Audit: `rg storybook-fixtures frontend`
 */

export const STORYBOOK_PLATFORM_ICON_FIXTURES =
  "/storybook-fixtures/platform-icons" as const;

/** Not in the build-time platform icon glob; use with PlatformIcon `:src`. */
export const STORYBOOK_NON_CACHED_ICON_SVG =
  `${STORYBOOK_PLATFORM_ICON_FIXTURES}/non-cached-icon.svg` as const;
