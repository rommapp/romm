<script setup>
// Props
const props = defineProps(['gettingRoms'])
</script>

<template>
    <v-dialog v-model="gettingRoms" scroll-strategy="none" width="auto" :scrim="false" persistent>
        <v-progress-circular color="secondary" :width="3" :size="70" indeterminate/>
    </v-dialog>
</template>