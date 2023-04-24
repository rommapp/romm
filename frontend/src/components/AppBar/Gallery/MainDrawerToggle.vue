<script setup>
import { inject } from "vue"

// Event listeners bus
const emitter = inject('emitter')

</script>

<template>
    <v-btn
        @click="emitter.emit('toggleMainDrawer')"
        rounded="0"
        icon>
        <v-avatar rounded="0">
            <v-img src="/assets/isotipo.svg"/>
        </v-avatar>
    </v-btn>
</template>