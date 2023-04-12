<script setup>
const ROMM_VERSION = import.meta.env.VITE_ROMM_VERSION
</script>

<template>
    <v-list-item class="d-flex justify-center alignt-center text-body-2">
        <p>RomM v{{ ROMM_VERSION }}</p>
    </v-list-item>
</template>