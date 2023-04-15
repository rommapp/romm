<script setup>
// Props
const props = defineProps(['noRoms'])
</script>

<template>
    <v-row v-if="noRoms" class="d-flex justify-center align-center mt-16">
        <div class="text-h6">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
    </v-row>
</template>