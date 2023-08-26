<script setup>
const props = defineProps(["value", "icon"]);
</script>
<template>
  <v-col :key="value" cols="6" sm="3" md="2" lg="2" class="px-2">
    <v-item v-slot="{ isSelected, toggle }">
      <v-card
        :color="isSelected ? 'romm-accent-1' : 'romm-gray'"
        class="d-flex align-center"
        height="50"
        variant="outlined"
        @click="toggle"
      >
        <v-scroll-y-transition>
          <div class="text-subtitle-2 flex-grow-1 text-center text-capitalize">
            <v-icon class="mr-2">{{ icon }}</v-icon>
            {{ value }}
          </div>
        </v-scroll-y-transition>
      </v-card>
    </v-item>
  </v-col>
</template>
