<script setup lang="ts">
// PlayButton: Play, and the choice behind it. RomM's own launch is one target;
// every plugin action in the `game.play` slot is another. A game a plugin can
// start but the browser cannot still gets a Play button, which is the point of
// letting plugins take part in the decision rather than only adding buttons.
//
// One target plays straight away, exactly as it did before plugins existed.
// More than one asks which, in a dialog.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import GameActionBtn from "@/components/GameActions/GameActionBtn.vue";
import { useGameActions } from "@/composables/useGameActions";
import {
  usePluginActions,
  type PluginAction,
} from "@/composables/usePluginActions";
import { RBtn, RDialog, RIcon } from "@/lib";
import type { SimpleRom } from "@/stores/roms";

const props = defineProps<{
  rom: SimpleRom;
  size: "default" | "large";
}>();

const { t } = useI18n();
const actions = useGameActions(() => props.rom);
const plugins = usePluginActions(() => props.rom);
const choosing = ref(false);

interface Target {
  key: string;
  label: string;
  icon: string;
  /** The plugin action behind this target, absent for RomM's own launch. */
  action?: PluginAction;
}

/** Every way to start this game, RomM's own launch first. */
const targets = computed<Target[]>(() => {
  const list: Target[] = [];
  if (actions.canPlayLocally.value) {
    list.push({
      key: "romm",
      label: t("play.play-in-browser"),
      icon: "mdi-play",
    });
  }
  for (const action of plugins.playActions.value) {
    list.push({
      key: `${action.pluginId}:${action.id}`,
      label: action.label,
      icon: action.icon,
      action,
    });
  }
  return list;
});

/** The single way to play, when there is only one. */
const only = computed<Target | null>(() =>
  targets.value.length === 1 ? targets.value[0]! : null,
);

function run(target: Target): void {
  choosing.value = false;
  if (target.action) {
    plugins.open(target.action);
    return;
  }
  void actions.play("auto");
}

function onPlay(): void {
  if (only.value && only.value.action === undefined) return;
  if (only.value) {
    run(only.value);
    return;
  }
  choosing.value = true;
}
</script>

<template>
  <span v-if="targets.length === 0" />

  <!-- RomM's launch on its own: the anchor it has always been. -->
  <GameActionBtn
    v-else-if="only && only.action === undefined"
    :rom="rom"
    action="play"
    :size="size"
    variant="emphasized"
    with-label
    link
  />

  <button
    v-else
    type="button"
    class="r-game-btn r-game-btn--emphasized r-game-btn--labelled r-game-btn--action-play"
    :class="`r-game-btn--${size}`"
    :aria-label="targets.length > 1 ? t('play.play-with') : t('play.play')"
    @click="onPlay"
  >
    <RIcon icon="mdi-play" />
    <span class="r-game-btn__label">{{ t("play.play") }}</span>
    <RIcon v-if="targets.length > 1" icon="mdi-chevron-down" size="x-small" />
  </button>

  <RDialog v-model="choosing" icon="mdi-play" width="420" cancelable>
    <template #header>
      <span>{{ t("play.play-with") }}</span>
    </template>
    <template #content>
      <div class="play-choices">
        <RBtn
          v-for="target in targets"
          :key="target.key"
          block
          variant="surface"
          class="play-choices__row"
          @click="run(target)"
        >
          <RIcon :icon="target.icon" />
          <span>{{ target.label }}</span>
        </RBtn>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.play-choices {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.play-choices__row {
  justify-content: flex-start;
}
</style>
