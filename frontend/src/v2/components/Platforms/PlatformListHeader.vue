<script setup lang="ts">
// PlatformListHeader — column-header strip for the Platforms list-mode
// view. Mirrors GameListHeader's anatomy (sticky title row above the
// rows, shared CSS-grid template) but without sortable columns — the
// platforms index is small enough that fixed alphabetical order is
// fine. Kept as a separate component for visual parity with the ROM
// gallery and so the grid template lives next to its consumers.
//
// The three metadata columns (Family / Category / Generation) drop out
// on narrow viewports (see the `html[data-bp~="xs"]` rules below) so the
// row stays legible on mobile without horizontal scroll. The grid
// template flips in the same breakpoint so the cells re-align with the
// row's compact layout.
</script>

<template>
  <div class="plat-list-header" role="row">
    <div class="plat-list-header__cell">
      <span class="plat-list-header__label">Name</span>
    </div>
    <div class="plat-list-header__cell plat-list-header__cell--meta">
      <span class="plat-list-header__label">Family</span>
    </div>
    <div class="plat-list-header__cell plat-list-header__cell--meta">
      <span class="plat-list-header__label">Category</span>
    </div>
    <div class="plat-list-header__cell plat-list-header__cell--meta">
      <span class="plat-list-header__label">Generation</span>
    </div>
    <div class="plat-list-header__cell plat-list-header__cell--end">
      <span class="plat-list-header__label">Games</span>
    </div>
  </div>
</template>

<style scoped>
/* Grid template kept in lock-step with PLATFORM_LIST_GRID_TEMPLATE in
   platformListColumns.ts (the constant is exported for the index
   view's narrative; the header / row apply it via CSS so the
   breakpoint switch works without an inline-style override fight). */
.plat-list-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px 130px 110px 96px;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-header-h);
  background: var(--r-color-bg-elevated);
  border-bottom: 1px solid var(--r-color-border);
}

.plat-list-header__cell {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  height: 100%;
}

.plat-list-header__cell--end {
  justify-content: flex-end;
}

.plat-list-header__label {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html[data-bp~="xs"] .plat-list-header {
  grid-template-columns: minmax(0, 1fr) 96px;
}
html[data-bp~="xs"] .plat-list-header__cell--meta {
  display: none;
}
</style>
