<script setup lang="ts">
import { debounce } from "lodash";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { storeToRefs } from "pinia";
import { ref, watch, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";
import type { RomUserStatus } from "@/__generated__";
import MultiNoteManager from "@/components/Details/MultiNoteManager.vue";
import RetroAchievements from "@/components/Details/RetroAchievements.vue";
import RSection from "@/components/common/RSection.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import { getTextForStatus, getEmojiForStatus } from "@/utils";

const { t } = useI18n();
const props = defineProps<{ rom: DetailedRom }>();
const route = useRoute();
const router = useRouter();

// Valid subtab values
const validTabs = ["status", "ra", "notes"] as const;

// Helper function to update URL with new query parameters
const updateQuery = (updates: Record<string, any>) => {
  router.replace({
    path: route.path,
    query: { ...route.query, ...updates },
  });
};

// Helper function to remove subtab from URL
const removeSubtab = () => {
  if (route.query.subtab) {
    const { subtab, ...queryWithoutSubtab } = route.query;
    router.replace({
      path: route.path,
      query: queryWithoutSubtab,
    });
  }
};

// Initialize sub-tab from query parameter or default to "status"
const tab = ref<"status" | "ra" | "notes">(
  validTabs.includes(route.query.subtab as any)
    ? (route.query.subtab as "status" | "ra" | "notes")
    : "status",
);
const auth = storeAuth();
const theme = useTheme();
const { mdAndUp, mdAndDown, smAndDown } = useDisplay();
const { scopes } = storeToRefs(auth);
const romUser = ref(props.rom.rom_user);

// Watch for sub-tab changes and update URL
watch(tab, (newSubTab) => {
  if (route.query.subtab !== newSubTab) {
    updateQuery({ subtab: newSubTab });
  }
});

// Watch for URL changes and update sub-tab
watch(
  () => route.query.subtab,
  (newSubTab) => {
    if (newSubTab && validTabs.includes(newSubTab as any)) {
      tab.value = newSubTab as "status" | "ra" | "notes";
    }
  },
  { immediate: true },
);

// Watch for parent tab changes and clean up subtab when not on personal tab
watch(
  () => route.query.tab,
  (newTab) => {
    if (newTab !== "personal") {
      removeSubtab();
    }
  },
);

// Clean up subtab parameter when component unmounts

const statusOptions = [
  "never_playing",
  "retired",
  "incomplete",
  "finished",
  "completed_100",
];

async function onNotesUpdated() {
  // Refetch the ROM to get updated all_user_notes
  try {
    const updatedRom = await romApi.getRom({ romId: props.rom.id });
    // Update the parent component with the new ROM data
    // This is a bit of a hack - ideally we'd have better state management
    Object.assign(props.rom, updatedRom.data);
  } catch (error) {
    console.error("Failed to refetch ROM data:", error);
  }
}

function onStatusItemClick(status: string | null) {
  romUser.value.status = status as RomUserStatus | null;
}

watch(
  () => props.rom,
  async () => (romUser.value = props.rom.rom_user),
);

watch(
  romUser,
  debounce(() => {
    if (scopes.value.includes("roms.user.write")) {
      romApi.updateUserRomProps({
        romId: props.rom.id,
        data: romUser.value,
      });
    }
  }, 500),
  { deep: true },
);
</script>

<template>
  <v-row no-gutters>
    <v-col cols="12" lg="auto">
      <v-tabs
        v-model="tab"
        :direction="mdAndDown ? 'horizontal' : 'vertical'"
        :align-tabs="mdAndDown ? 'center' : 'start'"
        slider-color="secondary"
        class="mr-4 mt-2"
        selected-class="bg-toplayer"
      >
        <v-tab
          prepend-icon="mdi-list-status"
          class="rounded text-caption"
          value="status"
        >
          Status
        </v-tab>
        <v-tab
          v-if="rom.ra_id && auth.user?.ra_username"
          prepend-icon="mdi-trophy"
          class="rounded text-caption"
          value="ra"
        >
          RetroAchievements
        </v-tab>
        <v-tab
          prepend-icon="mdi-notebook-edit"
          class="rounded text-caption"
          value="notes"
        >
          Notes
        </v-tab>
      </v-tabs>
    </v-col>
    <v-col>
      <v-tabs-window v-model="tab">
        <v-tabs-window-item value="status">
          <v-row
            class="align-center pa-2"
            :class="{ 'text-center': smAndDown }"
            no-gutters
          >
            <v-col cols="12" md="5">
              <v-checkbox
                v-model="romUser.backlogged"
                :disabled="!scopes.includes('roms.user.write')"
                color="primary"
                hide-details
              >
                <template #label>
                  <span>{{ t("rom.backlogged") }}</span
                  ><span class="ml-2">{{
                    getEmojiForStatus("backlogged")
                  }}</span>
                </template>
              </v-checkbox>
              <v-checkbox
                v-model="romUser.now_playing"
                :disabled="!scopes.includes('roms.user.write')"
                color="primary"
                hide-details
              >
                <template #label>
                  <span>{{ t("rom.now-playing") }}</span
                  ><span class="ml-2">{{
                    getEmojiForStatus("now_playing")
                  }}</span>
                </template>
              </v-checkbox>
              <v-checkbox
                v-model="romUser.hidden"
                :disabled="!scopes.includes('roms.user.write')"
                color="primary"
                hide-details
              >
                <template #label>
                  <span>{{ t("rom.hidden") }}</span
                  ><span class="ml-2">{{ getEmojiForStatus("hidden") }}</span>
                </template>
              </v-checkbox>
            </v-col>
            <v-col cols="12" md="7">
              <v-row
                class="d-flex align-center"
                :class="{ 'mt-4': smAndDown }"
                no-gutters
              >
                <v-col cols="12" md="4">
                  <v-label>{{ t("rom.rating") }}</v-label>
                </v-col>
                <v-col cols="12" md="8">
                  <v-rating
                    v-model="romUser.rating"
                    :class="{ 'ml-2': mdAndUp }"
                    hover
                    ripple
                    clearable
                    length="10"
                    size="26"
                    :disabled="!scopes.includes('roms.user.write')"
                    active-color="yellow"
                    @update:model-value="
                      romUser.rating =
                        typeof $event === 'number' ? $event : parseInt($event)
                    "
                  />
                </v-col>
              </v-row>
              <v-row class="d-flex align-center mt-4" no-gutters>
                <v-col cols="12" md="4">
                  <v-label>{{ t("rom.difficulty") }}</v-label>
                </v-col>
                <v-col cols="12" md="8">
                  <v-rating
                    v-model="romUser.difficulty"
                    :class="{ 'ml-2': mdAndUp }"
                    hover
                    ripple
                    clearable
                    length="10"
                    size="26"
                    :disabled="!scopes.includes('roms.user.write')"
                    full-icon="mdi-chili-mild"
                    empty-icon="mdi-chili-mild-outline"
                    active-color="red"
                    @update:model-value="
                      romUser.difficulty =
                        typeof $event === 'number' ? $event : parseInt($event)
                    "
                  />
                </v-col>
              </v-row>
              <v-row class="d-flex align-center mt-4" no-gutters>
                <v-col cols="12" md="4">
                  <v-label>{{ t("rom.completion") }} %</v-label>
                </v-col>
                <v-col cols="12" md="8">
                  <v-slider
                    v-model="romUser.completion"
                    :class="{ 'ml-4': mdAndUp }"
                    :disabled="!scopes.includes('roms.user.write')"
                    min="1"
                    max="100"
                    step="1"
                    hide-details
                    track-fill-color="primary"
                  >
                    <template #append>
                      <v-label class="ml-2 opacity-100">
                        {{ romUser.completion }}%
                      </v-label>
                    </template>
                  </v-slider>
                </v-col>
              </v-row>
              <div class="d-flex align-center mt-4">
                <v-select
                  v-model="romUser.status"
                  :disabled="!scopes.includes('roms.user.write')"
                  :items="statusOptions"
                  hide-details
                  :label="t('rom.status')"
                  clearable
                  variant="outlined"
                  density="compact"
                  class="mt-1"
                >
                  <template #selection="{ item }">
                    <span>{{
                      getEmojiForStatus(item.raw as RomUserStatus)
                    }}</span
                    ><span class="ml-2">{{
                      getTextForStatus(item.raw as RomUserStatus)
                    }}</span>
                  </template>
                  <template #item="{ item }">
                    <v-list-item link @click="onStatusItemClick(item.raw)">
                      <span>{{
                        getEmojiForStatus(item.raw as RomUserStatus)
                      }}</span
                      ><span class="ml-2">{{
                        getTextForStatus(item.raw as RomUserStatus)
                      }}</span>
                    </v-list-item>
                  </template>
                </v-select>
              </div>
            </v-col>
          </v-row>
        </v-tabs-window-item>
        <v-tabs-window-item value="ra">
          <RetroAchievements :rom="rom" />
        </v-tabs-window-item>
        <v-tabs-window-item value="notes">
          <MultiNoteManager :rom="rom" @notes-updated="onNotesUpdated" />
        </v-tabs-window-item>
      </v-tabs-window>
    </v-col>
  </v-row>
</template>

<style>
.md-editor-dark {
  --md-bk-color: #161b22 !important;
}
.md-editor,
.md-preview {
  line-height: 1.25 !important;
}
.md-editor-preview {
  word-break: break-word !important;

  blockquote {
    border-left-color: rgba(var(--v-theme-secondary));
  }

  .md-editor-code-flag {
    visibility: hidden;
  }

  .md-editor-admonition {
    border-color: rgba(var(--v-theme-secondary));
    background-color: rgba(var(--v-theme-toplayer)) !important;
  }

  .md-editor-code summary,
  .md-editor-code code {
    background-color: rgba(var(--v-theme-toplayer)) !important;
  }
}

.vuepress-theme pre code {
  background-color: #0d1117;
}
.v-expansion-panel-text__wrapper {
  padding: 0px !important;
}
</style>
