<script setup lang="ts">
import { debounce } from "lodash";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { storeToRefs } from "pinia";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay, useTheme } from "vuetify";
import type { RomUserStatus } from "@/__generated__";
import RetroAchievements from "@/components/Details/RetroAchievements.vue";
import RSection from "@/components/common/RSection.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import { getTextForStatus, getEmojiForStatus } from "@/utils";

const { t } = useI18n();
const props = defineProps<{ rom: DetailedRom }>();
const tab = ref<"status" | "ra" | "notes">("status");
const auth = storeAuth();
const theme = useTheme();
const { mdAndUp, mdAndDown, smAndDown } = useDisplay();
const { scopes } = storeToRefs(auth);
const editingNote = ref(false);
const romUser = ref(props.rom.rom_user);
const publicNotes =
  props.rom.user_notes?.filter((note) => note.user_id !== auth.user?.id) ?? [];

const statusOptions = [
  "never_playing",
  "retired",
  "incomplete",
  "finished",
  "completed_100",
];

function editNote() {
  if (editingNote.value) {
    romApi.updateUserRomProps({
      romId: props.rom.id,
      data: romUser.value,
    });
  }
  editingNote.value = !editingNote.value;
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
          <RSection
            icon="mdi-account"
            :title="t('rom.my-notes')"
            elevation="0"
            title-divider
            bg-color="bg-surface"
            class="mt-2"
          >
            <template #toolbar-append>
              <v-btn-group divided density="compact" class="mr-1">
                <v-tooltip
                  location="top"
                  class="tooltip"
                  transition="fade-transition"
                  :text="
                    romUser.note_is_public ? 'Make private' : 'Make public'
                  "
                  open-delay="500"
                >
                  <template #activator="{ props: tooltipProps }">
                    <v-btn
                      :disabled="!scopes.includes('roms.user.write')"
                      v-bind="tooltipProps"
                      class="bg-toplayer"
                      @click="romUser.note_is_public = !romUser.note_is_public"
                    >
                      <v-icon size="large">
                        {{ romUser.note_is_public ? "mdi-eye" : "mdi-eye-off" }}
                      </v-icon>
                    </v-btn>
                  </template>
                </v-tooltip>
                <v-tooltip
                  location="top"
                  class="tooltip"
                  transition="fade-transition"
                  text="Edit note"
                  open-delay="500"
                >
                  <template #activator="{ props: tooltipProps }">
                    <v-btn
                      :disabled="!scopes.includes('roms.user.write')"
                      v-bind="tooltipProps"
                      class="bg-toplayer"
                      @click="editNote"
                    >
                      <v-icon size="large">
                        {{ editingNote ? "mdi-check" : "mdi-pencil" }}
                      </v-icon>
                    </v-btn>
                  </template>
                </v-tooltip>
              </v-btn-group>
            </template>
            <template #content>
              <MdEditor
                v-if="editingNote"
                v-model="romUser.note_raw_markdown"
                no-highlight
                no-katex
                no-mermaid
                no-prettier
                no-upload-img
                :disabled="!scopes.includes('roms.user.write')"
                :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
                language="en-US"
                :preview="false"
              />
              <MdPreview
                v-else
                no-highlight
                no-katex
                no-mermaid
                :model-value="romUser.note_raw_markdown"
                :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
                language="en-US"
                preview-theme="vuepress"
                code-theme="github"
                class="py-4 px-6"
              />
            </template>
          </RSection>
          <RSection
            v-if="publicNotes.length > 0"
            icon="mdi-account-multiple"
            :title="t('rom.public-notes')"
            elevation="0"
            title-divider
            bg-color="bg-surface"
            class="mt-2"
          >
            <template #content>
              <v-expansion-panels multiple flat variant="accordion">
                <v-expansion-panel
                  v-for="note in publicNotes"
                  :key="note.user_id"
                  rounded="0"
                >
                  <v-expansion-panel-title class="bg-toplayer">
                    <span class="text-body-1">{{ note.username }}</span>
                  </v-expansion-panel-title>
                  <v-expansion-panel-text class="bg-surface">
                    <MdPreview
                      no-highlight
                      no-katex
                      no-mermaid
                      :model-value="note.note_raw_markdown"
                      :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
                      language="en-US"
                      preview-theme="vuepress"
                      code-theme="github"
                      class="py-4 px-6"
                    />
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </template>
          </RSection>
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
