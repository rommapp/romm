<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useNavigationController } from "@/utils/navigation-controller";
import { useGamepadSupport } from "@/composables/useNavigation";

const navigationController = useNavigationController();
const { isGamepadConnected } = useGamepadSupport();

const showStatus = ref(false);
const currentFocus = ref<string>("");
const elementsCount = ref(0);
const isEnabled = ref(true);

const updateStatus = () => {
  const state = navigationController.getState();
  const currentElement = navigationController.getCurrentFocus();

  isEnabled.value = state.isEnabled;
  elementsCount.value = state.elementsCount;
  currentFocus.value = currentElement?.id || "";
};

const toggleStatus = () => {
  showStatus.value = !showStatus.value;
};

onMounted(() => {
  // Update status every 100ms
  const interval = setInterval(updateStatus, 100);

  onUnmounted(() => {
    clearInterval(interval);
  });
});
</script>

<template>
  <div class="navigation-status">
    <!-- Status indicator -->
    <v-btn
      v-if="isGamepadConnected"
      icon
      size="small"
      variant="text"
      class="status-indicator"
      @click="toggleStatus"
    >
      <v-icon>mdi-gamepad-variant</v-icon>
    </v-btn>

    <!-- Status panel -->
    <v-card
      v-if="showStatus"
      class="status-panel"
      elevation="8"
      max-width="300"
    >
      <v-card-title class="text-h6 pa-4">
        Navigation Status
        <v-btn
          icon
          size="small"
          variant="text"
          class="ml-auto"
          @click="toggleStatus"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-4">
        <v-list density="compact">
          <v-list-item>
            <template #prepend>
              <v-icon>mdi-gamepad-variant</v-icon>
            </template>
            <v-list-item-title>
              Gamepad: {{ isGamepadConnected ? "Connected" : "Disconnected" }}
            </v-list-item-title>
          </v-list-item>

          <v-list-item>
            <template #prepend>
              <v-icon>mdi-keyboard</v-icon>
            </template>
            <v-list-item-title> Keyboard: Enabled </v-list-item-title>
          </v-list-item>

          <v-list-item>
            <template #prepend>
              <v-icon>mdi-cursor-pointer</v-icon>
            </template>
            <v-list-item-title>
              Elements: {{ elementsCount }}
            </v-list-item-title>
          </v-list-item>

          <v-list-item v-if="currentFocus">
            <template #prepend>
              <v-icon>mdi-target</v-icon>
            </template>
            <v-list-item-title> Focus: {{ currentFocus }} </v-list-item-title>
          </v-list-item>
        </v-list>

        <v-divider class="my-4"></v-divider>

        <div class="text-caption">
          <h4 class="mb-2">Controls:</h4>
          <div class="controls-grid">
            <div class="control-item">
              <kbd>↑↓←→</kbd> or <kbd>WASD</kbd>
              <span>Navigate</span>
            </div>
            <div class="control-item">
              <kbd>Enter</kbd> or <kbd>Space</kbd>
              <span>Activate</span>
            </div>
            <div class="control-item">
              <kbd>Esc</kbd>
              <span>Back</span>
            </div>
            <div class="control-item">
              <kbd>H</kbd>
              <span>Home</span>
            </div>
            <div class="control-item">
              <kbd>F</kbd>
              <span>Search</span>
            </div>
            <div class="control-item">
              <kbd>R</kbd>
              <span>Scan</span>
            </div>
            <div class="control-item">
              <kbd>P</kbd>
              <span>Platforms</span>
            </div>
            <div class="control-item">
              <kbd>C</kbd>
              <span>Collections</span>
            </div>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>

<style scoped>
.navigation-status {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
}

.status-indicator {
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border-radius: 50%;
}

.status-panel {
  position: absolute;
  top: 50px;
  right: 0;
  background: rgba(0, 0, 0, 0.9);
  color: white;
}

.controls-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.control-item kbd {
  background: #333;
  border: 1px solid #555;
  border-radius: 3px;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 10px;
  min-width: 20px;
  text-align: center;
}

.control-item span {
  color: #ccc;
}
</style>
