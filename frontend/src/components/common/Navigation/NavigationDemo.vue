<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useNavigation } from "@/composables/useNavigation";
import { useKeyboardShortcuts } from "@/composables/useNavigation";

const demoButton1Ref = ref<HTMLElement>();
const demoButton2Ref = ref<HTMLElement>();
const demoButton3Ref = ref<HTMLElement>();
const demoCardRef = ref<HTMLElement>();

const message = ref("Use arrow keys, WASD, or a gamepad to navigate!");
const clickCount = ref(0);

// Register navigation elements
useNavigation(demoButton1Ref, "demo-btn-1", {
  priority: 10,
  action: () => {
    message.value = "Button 1 clicked!";
    clickCount.value++;
  },
});

useNavigation(demoButton2Ref, "demo-btn-2", {
  priority: 20,
  action: () => {
    message.value = "Button 2 clicked!";
    clickCount.value++;
  },
});

useNavigation(demoButton3Ref, "demo-btn-3", {
  priority: 30,
  action: () => {
    message.value = "Button 3 clicked!";
    clickCount.value++;
  },
});

useNavigation(demoCardRef, "demo-card", {
  priority: 15,
  action: () => {
    message.value = "Card clicked!";
    clickCount.value++;
  },
});

// Add custom keyboard shortcuts
const { addShortcut } = useKeyboardShortcuts();

onMounted(() => {
  addShortcut("KeyD", () => {
    message.value = "D key pressed - Demo shortcut!";
  });
});
</script>

<template>
  <div class="navigation-demo">
    <v-card class="demo-container" elevation="4">
      <v-card-title class="text-h5 pa-4">
        Navigation Controller Demo
      </v-card-title>

      <v-card-text class="pa-4">
        <div class="demo-message mb-4">
          <v-alert :text="message" type="info" variant="tonal" class="mb-4" />

          <div class="text-center">
            <v-chip color="primary" class="ma-2">
              Clicks: {{ clickCount }}
            </v-chip>
          </div>
        </div>

        <div class="demo-grid">
          <!-- Navigation buttons -->
          <v-btn
            ref="demoButton1Ref"
            v-navigation="{ id: 'demo-btn-1', priority: 10 }"
            color="primary"
            size="large"
            class="demo-btn"
            @click="
              message = 'Button 1 clicked!';
              clickCount++;
            "
          >
            Button 1
          </v-btn>

          <v-btn
            ref="demoButton2Ref"
            v-navigation="{ id: 'demo-btn-2', priority: 20 }"
            color="secondary"
            size="large"
            class="demo-btn"
            @click="
              message = 'Button 2 clicked!';
              clickCount++;
            "
          >
            Button 2
          </v-btn>

          <v-btn
            ref="demoButton3Ref"
            v-navigation="{ id: 'demo-btn-3', priority: 30 }"
            color="success"
            size="large"
            class="demo-btn"
            @click="
              message = 'Button 3 clicked!';
              clickCount++;
            "
          >
            Button 3
          </v-btn>

          <!-- Demo card -->
          <v-card
            ref="demoCardRef"
            v-navigation="{ id: 'demo-card', priority: 15 }"
            class="demo-interactive-card"
            elevation="2"
            @click="
              message = 'Card clicked!';
              clickCount++;
            "
          >
            <v-card-text class="text-center pa-4">
              <v-icon size="48" color="primary" class="mb-2">
                mdi-gamepad-variant
              </v-icon>
              <div class="text-h6">Interactive Card</div>
              <div class="text-caption">Click or navigate to me!</div>
            </v-card-text>
          </v-card>
        </div>

        <v-divider class="my-6"></v-divider>

        <div class="controls-info">
          <h3 class="text-h6 mb-3">Controls:</h3>
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
              <kbd>D</kbd>
              <span>Demo shortcut</span>
            </div>
            <div class="control-item">
              <kbd>Esc</kbd>
              <span>Go back</span>
            </div>
          </div>
        </div>

        <v-divider class="my-6"></v-divider>

        <div class="gamepad-info">
          <h3 class="text-h6 mb-3">Gamepad Support:</h3>
          <div class="gamepad-controls">
            <div class="control-item">
              <v-icon>mdi-gamepad-variant</v-icon>
              <span>D-pad or Left Stick: Navigate</span>
            </div>
            <div class="control-item">
              <v-icon>mdi-circle</v-icon>
              <span>A Button: Activate</span>
            </div>
            <div class="control-item">
              <v-icon>mdi-square</v-icon>
              <span>B Button: Go back</span>
            </div>
            <div class="control-item">
              <v-icon>mdi-triangle</v-icon>
              <span>Y Button: Menu</span>
            </div>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>

<style scoped>
.navigation-demo {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.demo-container {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
}

.demo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.demo-btn {
  height: 80px;
  font-size: 1.1em;
  font-weight: 500;
}

.demo-interactive-card {
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
}

.demo-interactive-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.demo-interactive-card:focus {
  border-color: #1976d2;
  outline: none;
}

.controls-grid,
.gamepad-controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 8px;
}

.control-item kbd {
  background: #333;
  color: white;
  border: 1px solid #555;
  border-radius: 4px;
  padding: 4px 8px;
  font-family: monospace;
  font-size: 12px;
  min-width: 24px;
  text-align: center;
}

.control-item span {
  font-size: 14px;
  color: #666;
}

.gamepad-controls .control-item {
  background: rgba(25, 118, 210, 0.1);
}

.gamepad-controls .control-item .v-icon {
  color: #1976d2;
}

/* Focus styles for navigation */
:deep(.navigation-focused) {
  outline: 2px solid #1976d2 !important;
  outline-offset: 2px !important;
  transform: scale(1.02) !important;
  transition: all 0.2s ease !important;
}
</style>
