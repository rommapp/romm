<script setup>
import ActionBar from '@/components/GameCard/ActionBar.vue'
import Cover from '@/components/GameCard/Cover.vue'

// Props
const props = defineProps(['rom'])
</script>

<template>
    <v-hover v-slot="{isHovering, props}">
        <v-card 
            v-bind="props"
            :class="{'on-hover': isHovering}"
            :elevation="isHovering ? 20 : 3">
            <v-hover v-slot="{isHovering, props}" open-delay="800">
                <cover :rom="rom" :isHovering="isHovering" :hoverProps="props"/>
                <action-bar :rom="rom"/>
            </v-hover>
        </v-card>
    </v-hover>
</template>

<style scoped>
.v-card .rom-title{
    transition: opacity .4s ease-in-out;
}
.rom-title.on-hover {
    opacity: 1;
}
.rom-title:not(.on-hover) {
    opacity: 0.85;
}
.v-card.on-hover {
    opacity: 1;
}
.v-card:not(.on-hover) {
    opacity: 0.85;
}
.cover{
    cursor: pointer;
}
</style>