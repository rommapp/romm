<script setup lang="ts">
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import type { RomUserStatus } from "@/__generated__";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { ref, watch } from "vue";
import { useTheme } from "vuetify";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const auth = storeAuth();
const theme = useTheme();
const editingNote = ref(false);
const romUser = ref(props.rom.rom_user);
const publicNotes =
  props.rom.user_notes?.filter((note) => note.user_id !== auth.user?.id) ?? [];

const difficultyEmojis = [
  "😴",
  "🥱",
  "😐",
  "😄",
  "🤔",
  "🤯",
  "😓",
  "😡",
  "🤬",
  "😵",
];

const statusOptions = [
  null,
  "incomplete",
  "finished",
  "completed_100",
  "retired",
  "never_playing",
];

const statusToOption: Record<RomUserStatus, string> = {
  incomplete: "Incomplete (started but not finished)",
  finished: "Finished (reached the end)",
  completed_100: "Completed (all levels, achivements, endings, etc...)",
  retired: "Retired (won't play again)",
  never_playing: "Never playing (will never play)",
};

// Functions
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
  () => {
    romApi.updateUserRomProps({
      romId: props.rom.id,
      data: romUser.value,
    });
  },
  { deep: true },
);
</script>

<template>
  <v-card rounded="0" class="mb-2">
    <v-card-title class="bg-terciary">
      <v-list-item class="pl-2 pr-0">
        <span class="text-h6">Status</span>
      </v-list-item>
    </v-card-title>
    <v-card-text class="py-2 px-8">
      <v-row no-gutters>
        <v-col cols="6">
          <v-checkbox
            label="Backlogged"
            v-model="romUser.backlogged"
            color="romm-accent-1"
            hide-details
          />
          <v-checkbox
            label="Now playing"
            v-model="romUser.now_playing"
            color="romm-accent-1"
            hide-details
          />
          <v-checkbox
            label="Hidden"
            v-model="romUser.hidden"
            color="romm-accent-1"
            hide-details
          />
        </v-col>
        <v-col cols="6">
          <div class="d-flex align-center mt-3">
            <v-label class="text-body-2 mr-4">Rating</v-label>
            <v-rating
              hover
              ripple
              length="10"
              size="40"
              v-model="romUser.rating"
              @update:model-value="
                romUser.rating =
                  typeof $event === 'number' ? $event : parseInt($event)
              "
              active-color="romm-accent-1"
            />
          </div>
          <div class="d-flex align-center mt-2">
            <v-label class="text-body-2 mr-4">Difficulty</v-label>
            <v-slider
              v-model="romUser.difficulty"
              min="1"
              max="10"
              step="1"
              hide-details
              track-fill-color="romm-accent-1"
            />
            <v-label class="ml-2 opacity-100">
              {{
                difficultyEmojis[Math.floor(romUser.difficulty) - 1] ?? "😀"
              }}</v-label
            >
          </div>
          <div class="d-flex align-center mt-3">
            <v-label class="text-body-2 mr-4">Completion %</v-label>
            <v-slider
              v-model="romUser.completion"
              min="1"
              max="100"
              step="1"
              hide-details
              track-fill-color="romm-accent-1"
            />
            <v-label class="text-body-2 ml-2 opacity-100">
              {{ romUser.completion }}%
            </v-label>
          </div>
          <div class="d-flex align-center mt-3">
            <v-select
              v-model="romUser.status"
              :items="statusOptions"
              hide-details
              label="Status"
              dense
              rounded="0"
              variant="outlined"
              density="compact"
              class="mt-1"
            >
              <template v-slot:selection="{ item }">
                <span>{{ statusToOption[item.raw as RomUserStatus] }}</span>
              </template>
              <template v-slot:item="{ item }">
                <v-list-item
                  link
                  rounded="0"
                  @click="onStatusItemClick(item.raw)"
                >
                  {{ statusToOption[item.raw as RomUserStatus] }}
                </v-list-item>
              </template>
            </v-select>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
  <v-card rounded="0">
    <v-card-title class="bg-terciary">
      <v-list-item class="pl-2 pr-0">
        <span class="text-h6">My notes</span>
        <template #append>
          <v-btn-group divided density="compact">
            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              :text="romUser.note_is_public ? 'Make private' : 'Make public'"
              open-delay="500"
              ><template #activator="{ props: tooltipProps }">
                <v-btn
                  @click="romUser.note_is_public = !romUser.note_is_public"
                  v-bind="tooltipProps"
                  class="bg-terciary"
                >
                  <v-icon size="large">
                    {{ romUser.note_is_public ? "mdi-eye" : "mdi-eye-off" }}
                  </v-icon>
                </v-btn>
              </template></v-tooltip
            >
            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              text="Edit note"
              open-delay="500"
              ><template #activator="{ props: tooltipProps }">
                <v-btn
                  @click="editNote"
                  v-bind="tooltipProps"
                  class="bg-terciary"
                >
                  <v-icon size="large">
                    {{ editingNote ? "mdi-check" : "mdi-pencil" }}
                  </v-icon>
                </v-btn>
              </template></v-tooltip
            >
          </v-btn-group>
        </template>
      </v-list-item>
    </v-card-title>
    <v-card-text class="pa-2">
      <MdEditor
        v-if="editingNote"
        v-model="romUser.note_raw_markdown"
        :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
        language="en-US"
        :preview="false"
        :no-upload-img="true"
        class="editor-preview"
      />
      <MdPreview
        v-else
        :model-value="romUser.note_raw_markdown"
        :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
        preview-theme="vuepress"
        code-theme="github"
      />
    </v-card-text>
  </v-card>

  <v-card rounded="0" v-if="publicNotes && publicNotes.length > 0" class="mt-2">
    <v-card-title class="bg-terciary">
      <v-list-item class="pl-2 pr-0">
        <span class="text-h6">Public notes</span>
      </v-list-item>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-0">
      <v-expansion-panels multiple flat rounded="0" variant="accordion">
        <v-expansion-panel v-for="note in publicNotes">
          <v-expansion-panel-title class="bg-terciary">
            <span class="text-body-1">{{ note.username }}</span>
          </v-expansion-panel-title>
          <v-expansion-panel-text class="bg-secondary">
            <MdPreview
              :model-value="note.note_raw_markdown"
              :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
              preview-theme="vuepress"
              code-theme="github"
            />
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
  </v-card>
</template>

<style>
.md-editor-dark {
  --md-bk-color: #161b22 !important;
}
.md-editor,
.md-editor-preview {
  word-break: break-word !important;
  line-height: 1.25 !important;
}
.vuepress-theme pre code {
  background-color: #0d1117;
}
.v-expansion-panel-text__wrapper {
  padding: 0px !important;
}
</style>
