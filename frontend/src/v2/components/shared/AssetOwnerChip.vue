<script setup lang="ts">
// Avatar plus username for a community save or state.
import { RAvatar } from "@v2/lib";
import type { AssetOwner } from "@/v2/utils/assets";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

defineOptions({ inheritAttrs: false });

withDefaults(defineProps<{ owner: AssetOwner; size?: number }>(), {
  size: 16,
});
</script>

<template>
  <span class="r-asset-owner" v-bind="$attrs">
    <RAvatar
      :image="
        userAvatarUrl({
          userId: owner.user_id,
          avatarPath: owner.user_avatar_path,
          updatedAt: owner.user_updated_at,
        })
      "
      :size="size"
    />
    <span>{{ owner.username }}</span>
  </span>
</template>

<style scoped>
.r-asset-owner {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
}
</style>
