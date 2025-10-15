<script setup lang="ts">
import { computed } from "vue";
import type { ScanStats } from "@/__generated__";

const props = defineProps<{
  scanStats: ScanStats;
}>();

const scanProgress = computed(() => {
  const stats = props.scanStats;
  const totalPlatforms = stats.total_platforms || 0;
  const totalRoms = stats.total_roms || 0;
  const scannedPlatforms = stats.scanned_platforms || 0;
  const scannedRoms = stats.scanned_roms || 0;

  return {
    platforms: `${scannedPlatforms}/${totalPlatforms}`,
    platformsProgress: Math.round((scannedPlatforms / totalPlatforms) * 100),
    roms: `${scannedRoms}/${totalRoms}`,
    romsProgress: Math.round((scannedRoms / totalRoms) * 100),
    addedRoms: stats.added_roms || 0,
    metadataRoms: stats.metadata_roms || 0,
    scannedFirmware: stats.scanned_firmware || 0,
    addedFirmware: stats.added_firmware || 0,
  };
});
</script>

<template>
  <div class="scan-progress">
    <!-- Progress Bars -->
    <div class="progress-bars">
      <div class="progress-item">
        <div class="progress-label">
          <v-icon icon="mdi-console" size="16" class="mr-2" />
          <span>Platforms</span>
          <span class="progress-percentage"
            >{{ scanProgress.platformsProgress }}%</span
          >
        </div>
        <v-progress-linear
          :model-value="scanProgress.platformsProgress"
          color="primary"
          height="8"
          rounded
          class="progress-bar"
        />
        <div class="progress-details">
          {{ scanProgress.platforms }} platforms processed
        </div>
      </div>

      <div class="progress-item">
        <div class="progress-label">
          <v-icon icon="mdi-gamepad-variant" size="16" class="mr-2" />
          <span>ROMs</span>
          <span class="progress-percentage"
            >{{ scanProgress.romsProgress }}%</span
          >
        </div>
        <v-progress-linear
          :model-value="scanProgress.romsProgress"
          color="secondary"
          height="8"
          rounded
          class="progress-bar"
        />
        <div class="progress-details">
          {{ scanProgress.roms }} ROMs processed
        </div>
      </div>
    </div>

    <!-- Summary Stats -->
    <div class="summary-stats">
      <div class="stats-grid">
        <div class="stat-item stat-item--primary">
          <div class="stat-icon">
            <v-icon icon="mdi-console" size="20" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ scanProgress.platforms }}</div>
            <div class="stat-label">Platforms</div>
          </div>
        </div>

        <div class="stat-item stat-item--secondary">
          <div class="stat-icon">
            <v-icon icon="mdi-gamepad-variant" size="20" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ scanProgress.roms }}</div>
            <div class="stat-label">ROMs</div>
          </div>
        </div>

        <div class="stat-item stat-item--success">
          <div class="stat-icon">
            <v-icon icon="mdi-plus-circle" size="20" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ scanProgress.addedRoms }}</div>
            <div class="stat-label">Added</div>
          </div>
        </div>

        <div class="stat-item stat-item--info">
          <div class="stat-icon">
            <v-icon icon="mdi-information" size="20" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ scanProgress.metadataRoms }}</div>
            <div class="stat-label">Metadata</div>
          </div>
        </div>

        <div class="stat-item stat-item--warning">
          <div class="stat-icon">
            <v-icon icon="mdi-chip" size="20" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ scanProgress.scannedFirmware }}</div>
            <div class="stat-label">Firmware</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scan-progress {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.progress-bars {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.progress-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
}

.progress-percentage {
  font-family: "Monaco", "Menlo", monospace;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 8px;
  border-radius: 12px;
}

.progress-bar {
  border-radius: 4px;
  overflow: hidden;
}

.progress-details {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
  transition: all 0.3s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border-color: rgba(255, 255, 255, 0.2);
}

.stat-item--primary {
  border-left: 4px solid #2196f3;
  background: linear-gradient(
    135deg,
    rgba(33, 150, 243, 0.1) 0%,
    rgba(33, 150, 243, 0.05) 100%
  );
}

.stat-item--secondary {
  border-left: 4px solid #9c27b0;
  background: linear-gradient(
    135deg,
    rgba(156, 39, 176, 0.1) 0%,
    rgba(156, 39, 176, 0.05) 100%
  );
}

.stat-item--success {
  border-left: 4px solid #4caf50;
  background: linear-gradient(
    135deg,
    rgba(76, 175, 80, 0.1) 0%,
    rgba(76, 175, 80, 0.05) 100%
  );
}

.stat-item--info {
  border-left: 4px solid #00bcd4;
  background: linear-gradient(
    135deg,
    rgba(0, 188, 212, 0.1) 0%,
    rgba(0, 188, 212, 0.05) 100%
  );
}

.stat-item--warning {
  border-left: 4px solid #ff9800;
  background: linear-gradient(
    135deg,
    rgba(255, 152, 0, 0.1) 0%,
    rgba(255, 152, 0, 0.05) 100%
  );
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
  font-family: "Monaco", "Menlo", monospace;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Responsive Design */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: 12px;
  }

  .stat-item {
    padding: 12px;
    gap: 8px;
  }

  .stat-icon {
    width: 32px;
    height: 32px;
  }

  .stat-value {
    font-size: 16px;
  }

  .stat-label {
    font-size: 10px;
  }
}
</style>
