<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import storeActivity from "@/stores/activity";

const props = defineProps<{ romId: number }>();
const { t } = useI18n();
const activityStore = storeActivity();

onMounted(() => {
  activityStore.initSocket();
  if (!activityStore.initialized) {
    activityStore.fetchAll();
  }
});

const activePlayers = computed(() => activityStore.getByRomId(props.romId));

function formatStartedAt(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
</script>

<template>
  <v-card
    v-if="activePlayers.length > 0"
    class="mb-3"
    variant="tonal"
    color="success"
    density="compact"
  >
    <v-card-text class="d-flex align-center flex-wrap py-2">
      <v-icon class="mr-2" color="success" size="small">
        mdi-access-point
      </v-icon>
      <span class="text-body-2 font-weight-medium mr-3">
        {{ t("activity.now-playing") }}
      </span>
      <v-avatar
        v-for="player in activePlayers"
        :key="`${player.user_id}-${player.device_id}`"
        size="32"
        class="mr-1"
      >
        <v-img
          v-if="player.avatar_path"
          :src="`/assets/${player.avatar_path}`"
          :alt="player.username"
        />
        <v-icon v-else>mdi-account-circle</v-icon>
        <v-tooltip activator="parent" location="bottom">
          <div>
            <strong>{{ player.username }}</strong>
            <div class="text-caption">
              {{ t("activity.playing-on", { device: player.device_type }) }}
            </div>
            <div class="text-caption">
              {{
                t("activity.playing-since", {
                  time: formatStartedAt(player.started_at),
                })
              }}
            </div>
          </div>
        </v-tooltip>
      </v-avatar>
    </v-card-text>
  </v-card>
</template>
