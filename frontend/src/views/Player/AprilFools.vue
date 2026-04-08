<template>
  <v-row class="align-center justify-center h-100 af-backdrop" no-gutters>
    <v-col cols="auto" class="text-center">
      <div class="af-reveal">
        <img class="af-img" src="/assets/default/af.gif" alt="April Fools!" />
      </div>
      <v-btn
        class="mt-4 af-btn"
        block
        variant="outlined"
        size="large"
        prepend-icon="mdi-arrow-left"
        @click="$router.back()"
      >
        Go back
      </v-btn>
    </v-col>
  </v-row>
</template>

<style scoped>
.af-backdrop {
  animation: fade-in 0.6s ease-out;
}

.af-reveal {
  overflow: hidden;
  animation: clip-reveal 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.3s both;
}

.af-img {
  animation: zoom-settle 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.3s both;
}

.af-btn {
  animation: fade-in 0.4s ease-out 1s both;
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes clip-reveal {
  from {
    clip-path: circle(0% at 50% 50%);
  }
  to {
    clip-path: circle(150% at 50% 50%);
  }
}

@keyframes zoom-settle {
  from {
    transform: scale(1.3);
  }
  to {
    transform: scale(1);
  }
}
</style>
