<template>
  <div
    class="modal-overlay"
    tabindex="0"
    @click.self="close"
    @keydown.esc.prevent.stop="close"
    @keydown.arrow-left.prevent="prev"
    @keydown.arrow-right.prevent="next"
  >
    <div
      class="modal-content modal-wide lightbox"
      :class="{ 'animate-zoomIn': animateIn }"
      @click.stop
    >
      <div class="modal-header">
        <h2>Screenshots</h2>
        <button
          class="modal-close"
          aria-label="Close"
          @click="close"
        >
          ×
        </button>
      </div>

      <div class="modal-body lightbox-body">
        <div class="lightbox-stage">
          <img
            v-if="currentSrc"
            :src="currentSrc"
            :data-alt="currentAlt"
            :alt="`Screenshot ${index + 1} of ${urls.length}`"
            class="lightbox-image"
            draggable="false"
            @error="onError"
            @load="onLoad"
          >
          <div
            v-else
            class="lightbox-fallback"
          >
            Image failed to load.
          </div>

          <div class="lightbox-counter">
            {{ index + 1 }} / {{ urls.length }}
          </div>

          <button
            v-if="urls.length > 1"
            class="lightbox-nav left"
            aria-label="Previous"
            @click.stop="prev"
          >
            ◀
          </button>
          <button
            v-if="urls.length > 1"
            class="lightbox-nav right"
            aria-label="Next"
            @click.stop="next"
          >
            ▶
          </button>
        </div>
      </div>

      <div class="modal-footer">
        <span class="modal-hint">← → Navigate • Backspace to close</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

const props = defineProps<{ urls: string[]; startIndex?: number }>();
const emit = defineEmits(['close']);

const index = ref(Math.min(Math.max(props.startIndex ?? 0, 0), Math.max(props.urls.length - 1, 0)));
const triedAlt = ref(false);
const animateIn = ref(true);

const currentUrl = computed(() => props.urls[index.value] || '');

function buildAlt(u: string): string {
  const [path, qs] = u.split('?');
  if (path.startsWith('/assets/')) {
    const relative = path.slice('/assets/'.length);
    return `/api/raw/assets/${relative}${qs ? `?${qs}` : ''}`;
  }
  return u;
}

const currentSrc = computed(() => currentUrl.value);
const currentAlt = computed(() => buildAlt(currentUrl.value));

function close(){ emit('close'); }
function prev(){ index.value = (index.value - 1 + props.urls.length) % props.urls.length; triedAlt.value = false; }
function next(){ index.value = (index.value + 1) % props.urls.length; triedAlt.value = false; }

function onError(e: Event){
  const img = e.target as HTMLImageElement;
  if(!triedAlt.value && img.getAttribute('data-alt') && img.src !== img.getAttribute('data-alt')){
    triedAlt.value = true;
    img.src = img.getAttribute('data-alt') || img.src;
    return;
  }
}

function onLoad(){
  animateIn.value = false; requestAnimationFrame(() => { animateIn.value = true; });
}

onMounted(() => {
  (document.activeElement as HTMLElement | null)?.blur();
});

watch(() => props.startIndex, (v) => { if(typeof v==='number') index.value = v; });
</script>

<style scoped>
/* Match Game.vue modal styling */
.modal-overlay{ position:fixed; inset:0; background:rgba(0,0,0,0.8); backdrop-filter:blur(10px); display:flex; align-items:center; justify-content:center; z-index:1100; animation: fadeIn .2s ease; }
.modal-content{ background:rgba(20,20,20,0.95); backdrop-filter:blur(20px); border:1px solid rgba(255,255,255,0.2); border-radius:16px; max-width:1000px; max-height:80vh; width:90%; overflow:hidden; animation: slideUp .3s ease; }
.modal-header{ display:flex; justify-content:space-between; align-items:center; padding:1.25rem 1.5rem; border-bottom:1px solid rgba(255,255,255,0.1); }
.modal-header h2{ color:white; font-size:1.25rem; font-weight:600; margin:0; }
.modal-close{ background:none; border:none; color:#ccc; font-size:2rem; cursor:pointer; padding:0; width:40px; height:40px; display:flex; align-items:center; justify-content:center; border-radius:8px; transition:all .2s ease; }
.modal-close:hover{ background:rgba(255,255,255,0.1); color:white; }
.modal-body{ padding:0; max-height:calc(80vh - 56px - 52px); /* minus header and footer */ overflow:hidden; }
.modal-footer{ padding:0.75rem 1.5rem; border-top:1px solid rgba(255,255,255,0.1); text-align:center; }
.modal-hint{ color:#888; font-size:.9rem; }

/* Lightbox specific */
.lightbox{ position:relative; }
.lightbox-body{ display:flex; align-items:center; justify-content:center; background:transparent; }
.lightbox-stage{ position:relative; width:100%; height:100%; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.2); }
.lightbox-image{ display:block; max-width:90vw; max-height:62vh; object-fit:contain; user-select:none; }
.lightbox-fallback{ padding:2rem; color:rgba(255,255,255,0.7); }
.lightbox-counter{ position:absolute; right:12px; bottom:10px; color:rgba(255,255,255,0.85); font-size:12px; background:rgba(0,0,0,0.5); border-radius:6px; padding:2px 8px; }
.lightbox-nav{ position:absolute; top:50%; transform:translateY(-50%); width:40px; height:40px; border-radius:9999px; background:rgba(0,0,0,0.6); color:rgba(255,255,255,0.9); display:flex; align-items:center; justify-content:center; border:1px solid rgba(255,255,255,0.15); }
.lightbox-nav:hover{ background:rgba(0,0,0,0.7); }
.lightbox-nav.left{ left:12px; }
.lightbox-nav.right{ right:12px; }

@keyframes fadeIn { from{opacity:0} to{opacity:1} }
@keyframes slideUp { from{ opacity:0; transform: translateY(20px); } to{ opacity:1; transform: translateY(0);} }
@keyframes zoomIn { from { transform: scale(0.985); } to { transform: scale(1); } }
.animate-zoomIn { animation: zoomIn .18s ease-out; }
</style>
