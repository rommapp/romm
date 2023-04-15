<script setup>
const ROMM_VERSION = import.meta.env.VITE_ROMM_VERSION
</script>

<template>
    <v-list-item class="d-flex justify-center alignt-center text-body-2">
        <span class="text-secondary">RomM</span><span> v{{ ROMM_VERSION }}</span>
    </v-list-item>
</template>