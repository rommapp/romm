<template>
  <div class="w-full h-screen flex flex-col overflow-hidden">
    <!-- States -->
    <div
      v-if="loading"
      class="m-auto text-fg0 text-lg"
    >
      Loading {{ rom?.name || 'game' }}…
    </div>
    <div
      v-else-if="error"
      class="m-auto text-red-400 p-4"
    >
      {{ error }}
    </div>
    <div
      v-else-if="unsupported"
      class="m-auto text-red-400 p-4"
    >
      This platform is not supported in the web player yet.
    </div>

    <!-- Main content -->
    <div
      v-else
      class="relative w-full h-full overflow-y-auto overflow-x-hidden pb-28 md:pb-32"
    >
      <BackButton :on-back="goBackToPlatform" />

      <!-- Backdrop -->
      <div class="absolute inset-0 z-0 overflow-hidden">
        <img
          v-if="coverUrl"
          :src="coverUrl"
          :alt="`${rom?.name} background`"
          class="w-full h-full object-cover blur-xl brightness-75 saturate-[1.25] contrast-110 scale-110"
        >
      </div>
      <div class="absolute inset-0 bg-gradient-to-b from-black/70 via-black/20 to-black/80 pointer-events-none z-0" />

      <div class="relative z-10">
        <!-- HERO -->
        <section class="relative min-h-[65vh] flex items-end">
          <div class="w-full max-w-[1400px] mx-auto px-8 md:px-12 lg:px-16 pb-10 flex flex-col md:flex-row gap-8 md:gap-12 items-end">
            <!-- Poster -->
            <div class="shrink-0 self-center md:self-end">
              <img
                v-if="coverUrl"
                :src="coverUrl"
                :alt="`${rom?.name} cover`"
                class="w-[220px] md:w-[260px] h-auto rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.8),_0_0_0_1px_rgba(255,255,255,0.1)]"
              >
              <div
                v-else
                class="w-[220px] md:w-[260px] h-[340px] md:h-[380px] rounded-2xl bg-gradient-to-br from-[var(--accent-2)] to-[var(--accent)] flex flex-col items-center justify-center shadow-[0_10px_40px_rgba(0,0,0,0.8),_0_0_0_1px_rgba(255,255,255,0.1)]"
              >
                <div class="text-4xl mb-2">
                  🎮
                </div>
                <div class="text-6xl font-black text-black/80 drop-shadow">
                  {{ rom?.name?.charAt(0) || '?' }}
                </div>
              </div>
            </div>

            <!-- Content -->
            <div class="flex-1 max-w-[900px]">
              <h1 class="text-white text-4xl md:text-5xl font-extrabold mb-3 drop-shadow">
                {{ rom?.name }}
              </h1>

              <div class="flex flex-wrap items-center gap-2 md:gap-4 mb-5 text-sm">
                <span class="bg-[var(--accent-2)] text-black px-3 py-1 rounded text-xs font-semibold">
                  {{ rom?.platform_name || (rom?.platform_slug||'RETRO')?.toString().toUpperCase() }}
                </span>
                <span
                  v-if="releaseYear !== null"
                  class="text-gray-300 font-medium"
                >
                  {{ releaseYear }}
                </span>
                <span
                  v-if="firstRegion"
                  class="text-gray-300 font-medium"
                >
                  {{ firstRegion }}
                </span>
                <span
                  v-if="genres.length"
                  class="text-gray-300 font-medium truncate max-w-[50%]"
                >
                  {{ genres.join(', ') }}
                </span>
              </div>

              <div
                v-if="rom?.summary"
                class="text-[#ddd] text-base leading-6 mb-6 line-clamp-3 cursor-pointer"
                :class="{ 'ring-2 ring-white/30 rounded-md px-1 -translate-y-0.5': selectedZone==='description' }"
                tabindex="0"
                @click="openDescription()"
                @keydown.enter.prevent="openDescription()"
              >
                {{ rom.summary }}
              </div>

              <div class="flex gap-3 md:gap-4 mb-2">
                <button
                  class="flex items-center gap-3 px-6 md:px-8 py-3 md:py-4 rounded-lg text-base md:text-lg font-semibold min-w-[130px] md:min-w-[140px] justify-center transition-all"
                  :class="{ 'bg-white text-black hover:bg-[#e5e5e5]': true, 'scale-105 shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--accent-2),_0_0_16px_var(--accent-2)]': selectedZone==='play' }"
                  @click="play()"
                >
                  <span class="text-lg md:text-xl">▶</span>
                  Play
                </button>
                <button
                  class="bg-white/15 hover:bg-white/25 border border-white/20 text-white px-5 md:px-6 py-3 md:py-4 rounded-lg font-semibold transition-all"
                  :class="{ 'scale-105 shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--accent-2),_0_0_16px_var(--accent-2)]': selectedZone==='details' }"
                  @click="openDetails()"
                >
                  Details
                </button>
              </div>

              <div 
                v-if="rom?.user_states?.length"
                class="mt-4"
              >
                <h3 class="text-[10px] uppercase tracking-wider text-gray-400 font-semibold mb-2">
                  SAVE STATES
                </h3>
                <div
                  ref="statesRef"
                  class="w-full overflow-x-auto overflow-y-hidden no-scrollbar"
                >
                  <div class="flex items-center gap-3 py-1 px-2 min-w-max">
                    <button
                      v-for="(st,i) in rom.user_states"
                      :key="st.id"
                      :ref="el => registerStateEl(el as HTMLElement|null, i)"
                      class="group relative rounded-md overflow-hidden flex flex-col bg-white/5 border border-white/10 hover:bg-white/10 transition-all w-[140px] h-[80px]"
                      :class="{ 'ring-2 ring-[var(--accent-2)] scale-[1.05] shadow-[0_0_0_2px_var(--accent-2)]': selectedZone==='states' && selectedStateIndex===i }"
                      :aria-label="'State from ' + relativeTime(st.updated_at)"
                      @click="startWithState(i)"
                    >
                      <div
                        v-if="!st.screenshot?.download_path"
                        class="absolute inset-0 flex items-center justify-center text-[10px] text-white/40 font-medium select-none"
                      >
                        STATE
                      </div>
                      <img
                        v-else
                        :src="st.screenshot.download_path"
                        :alt="'State screenshot ' + (i+1)"
                        class="w-full h-full object-cover select-none pointer-events-none"
                        draggable="false"
                        loading="lazy"
                      >
                      <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-black/0 px-2 pt-4 pb-1 text-[10px] text-white/80 tracking-wide flex justify-between items-end">
                        <span class="truncate max-w-[90%]">{{ relativeTime(st.updated_at) }}</span>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- SCREENSHOTS -->
        <section
          v-if="screenshotUrls.length"
          class="fixed bottom-0 inset-x-0 z-30 py-3 md:py-4 bg-black/40 backdrop-blur-md border-t border-white/10"
        >
          <div class="w-full max-w-[1400px] mx-auto px-8 md:px-12 lg:px-16">
            <h3 class="text-gray-300 text-xs md:text-sm font-semibold uppercase tracking-wide">
              Screenshots
            </h3>
            <div 
              ref="shotsRef"
              class="w-full overflow-x-auto overflow-y-hidden no-scrollbar"
            >
              <div class="flex items-center gap-3 md:gap-4 py-6 px-2 min-w-max">
                <button
                  v-for="(src, idx) in screenshotUrls"
                  :key="`${idx}-${src}`"
                  :ref="el => registerShotEl(el as HTMLElement|null, idx)"
                  class="relative h-32 md:h-40 aspect-[16/9] rounded-md flex-none bg-white/5 border-2 border-white/10 overflow-hidden cursor-pointer transition-all duration-200 hover:-translate-y-[2px] hover:scale-[1.03] hover:shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--accent-2),_0_0_16px_var(--accent-2)]"
                  :class="{ 'scale-[1.03] shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--accent-2),_0_0_16px_var(--accent-2)]': selectedZone==='shots' && selectedShot===idx }"
                  tabindex="0"
                  @click="openLightbox(idx)"
                  @focus="selectedShot = idx"
                  @keydown.enter.prevent="openLightbox(idx)"
                >
                  <img
                    class="w-full h-full object-cover select-none"
                    loading="lazy"
                    draggable="false"
                    :src="primaryScreenshotSrc(src)"
                    :data-alt="altScreenshotSrc(src)"
                    :alt="`${rom?.name} screenshot ${idx + 1}`"
                    @error="onScreenshotError"
                  >
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- Modal -->
    <div
      v-if="showDescription"
      ref="descOverlayRef"
      class="modal-overlay"
      tabindex="0"
      @click="showDescription=false"
    >
      <div
        class="modal-content"
        @click.stop
      >
        <div class="modal-header">
          <h2>{{ rom?.name }} - Description</h2>
          <button
            class="modal-close"
            @click="showDescription=false"
          >
            ×
          </button>
        </div>
        <div class="modal-body">
          <p>{{ rom?.summary }}</p>
        </div>
        <div class="modal-footer">
          <NavigationText 
            :show-navigation="true" 
            :show-select="false" 
            :show-back="true"
            :show-toggle-favorite="false"
            :show-menu="false"
          />
        </div>
      </div>
    </div>
  
    <!-- Details Modal -->
    <div
      v-if="showDetails"
      ref="detailsOverlayRef"
      class="modal-overlay"
      tabindex="0"
      @click="showDetails=false"    
    >
      <div
        class="modal-content modal-wide"
        @click.stop
      >
        <div class="modal-header">
          <h2>{{ rom?.name }} - Details</h2>
          <button
            class="modal-close"
            @click="showDetails=false"
          >
            ×
          </button>
        </div>
        <div class="modal-body">
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
            <div
              v-if="companies.length"
              class="bg-white/5 border border-white/10 rounded-md pa-2 md:p-5"
            >
              <div class="text-gray-400 text-xs font-semibold mb-1 uppercase tracking-wide">
                Companies
              </div>
              <div class="text-white text-sm md:text-base leading-6 break-words">
                {{ companies.join(', ') }}
              </div>
            </div>
            <div
              v-if="genres.length"
              class="bg-white/5 border border-white/10 rounded-md pa-2 md:p-5"
            >
              <div class="text-gray-400 text-xs font-semibold mb-1 uppercase tracking-wide">
                Genres
              </div>
              <div class="text-white text-sm md:text-base leading-6 break-words">
                {{ genres.join(', ') }}
              </div>
            </div>
            <div
              v-if="releaseYear !== null"
              class="bg-white/5 border border-white/10 rounded-md pa-2 md:p-5"
            >
              <div class="text-gray-400 text-xs font-semibold mb-1 uppercase tracking-wide">
                Release Year
              </div>
              <div class="text-white text-sm md:text-base leading-6 break-words">
                {{ releaseYear }}
              </div>
            </div>
            <div
              v-if="regions.length"
              class="bg-white/5 border border-white/10 rounded-md pa-2 md:p-5"
            >
              <div class="text-gray-400 text-xs font-semibold mb-1 uppercase tracking-wide">
                Regions
              </div>
              <div class="text-white text-sm md:text-base leading-6 break-words">
                {{ regions.join(', ') }}
              </div>
            </div>
            <div class="bg-white/5 border border-white/10 rounded-md pa-2 md:p-5">
              <div class="text-gray-400 text-xs font-semibold mb-1 uppercase tracking-wide">
                File Size
              </div>
              <div class="text-white text-sm md:text-base leading-6 break-words">
                {{ Math.round((rom?.files?.[0]?.file_size_bytes || 0) / 1024) }} KB
              </div>
            </div>
            <div class="bg-white/5 border border-white/10 rounded-md pa-2 md:p-5">
              <div class="text-gray-400 text-xs font-semibold mb-1 uppercase tracking-wide">
                File
              </div>
              <div class="text-white text-sm md:text-base leading-6 break-words">
                {{ rom?.files?.[0]?.file_name || 'Unknown' }}
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <NavigationText 
            :show-navigation="false" 
            :show-select="false" 
            :show-back="true"
            :show-toggle-favorite="false"
            :show-menu="false"
          />
        </div>
      </div>
    </div>
    <ScreenshotLightbox
      v-if="showLightbox"
      :urls="screenshotUrls"
      :start-index="selectedShot"
      @close="showLightbox=false"
    />
    
    <NavigationHint 
      :show-navigation="true"
      :show-select="true"
      :show-back="true"
      :show-toggle-favorite="false"
      :show-menu="false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue';
import { formatDistanceToNow } from 'date-fns';
import { useRoute, useRouter } from 'vue-router';
import romApi from '@/services/api/rom';
import type { DetailedRomSchema } from '@/__generated__/models/DetailedRomSchema';
import ScreenshotLightbox from '@/console/components/ScreenshotLightbox.vue';
import BackButton from '@/console/components/BackButton.vue';
import NavigationText from '@/console/components/NavigationText.vue';
import NavigationHint from '@/console/components/NavigationHint.vue';
import { useInputScope } from '@/console/composables/useInputScope';
import type { InputAction } from '@/console/input/actions';
import { getCoreForPlatform } from '@/console/constants/cores';

const route = useRoute();
const router = useRouter();
const romId = Number(route.params.rom);

const rom = ref<DetailedRomSchema>();
const loading = ref(true);
const error = ref('');
const unsupported = ref(false);
type FocusZone = 'play'|'description'|'details'|'shots'|'lightbox'|'states';
const selectedZone = ref<FocusZone>('play');
const selectedStateIndex = ref(0);
const showDescription = ref(false);
const showDetails = ref(false);
const showLightbox = ref(false);
const selectedShot = ref(0);
const shotsRef = ref<HTMLDivElement|null>(null);
const shotEls = ref<HTMLElement[]>([]);
const statesRef = ref<HTMLDivElement|null>(null);
const stateEls = ref<HTMLElement[]>([]);
const descOverlayRef = ref<HTMLElement|null>(null);
const detailsOverlayRef = ref<HTMLElement|null>(null);

const releaseYear = computed(() => {
  const ts = rom.value?.igdb_metadata?.first_release_date ?? rom.value?.metadatum?.first_release_date;
  if (!ts) return null;
  const millis = ts < 10_000_000_000 ? ts * 1000 : ts;
  return new Date(millis).getFullYear();
});
const companies = computed(() => rom.value?.igdb_metadata?.companies ?? rom.value?.metadatum?.companies ?? []);
const genres = computed(() => rom.value?.igdb_metadata?.genres ?? rom.value?.metadatum?.genres ?? []);
const regions = computed(() => rom.value?.regions ?? []);
const firstRegion = computed(() => regions.value[0] || '');

// Build screenshot URLs: Only use merged_screenshots from IGDB/external sources,
// excluding user_screenshots from resources/roms/[id]/screenshots (like save state screenshots).
const screenshotUrls = computed(() => {
  // Only return merged screenshots from IGDB/external sources, exclude user screenshots
  const merged = rom.value?.merged_screenshots || [];
  return merged;
});

// Cover URL with fallbacks for background/poster (prefer local resources first)
const coverUrl = computed(() =>
  rom.value?.path_cover_large || rom.value?.path_cover_small || rom.value?.url_cover || ''
);

function openDescription(){ showDescription.value = true; }
function openDetails(){ showDetails.value = true; }

// Navigate back to the platform page using the ROM's platform_id
function goBackToPlatform() {
  if (rom.value?.platform_id) {
    router.push({ name: 'console-platform', params: { id: rom.value.platform_id } });
  } else {
    // Fallback to home if platform_id is not available
    router.push({ name: 'console-home' });
  }
}

const { on } = useInputScope();
function handleAction(action: InputAction): boolean {
  // Lightbox handling
  if(showLightbox.value){
    if(action==='moveRight') { selectedShot.value = (selectedShot.value + 1) % Math.max(1, screenshotUrls.value.length); return true; }
    if(action==='moveLeft') { selectedShot.value = (selectedShot.value - 1 + Math.max(1, screenshotUrls.value.length)) % Math.max(1, screenshotUrls.value.length); return true; }
    if(action==='back') { showLightbox.value = false; return true; }
    return false;
  }

  // Modal handling (description/details)
  if(showDescription.value || showDetails.value){
    if(action==='back'){ showDescription.value=false; showDetails.value=false; return true; }
    if(action==='moveUp' || action==='moveDown'){
      const body = document.querySelector('.modal-body') as HTMLElement|null; if(!body) return true;
      const amt = 40; if(action==='moveUp') body.scrollTop -= amt; else body.scrollTop += amt; return true;
    }
    return false;
  }

  // Main focus navigation
  switch(selectedZone.value){
  case 'play':
      if(action==='moveUp' && rom.value?.summary) { selectedZone.value='description'; return true; }
      if(action==='moveRight') { selectedZone.value='details'; return true; }
      if(action==='moveDown') { 
    if(rom.value?.user_states?.length){ selectedZone.value='states'; selectedStateIndex.value = 0; return true; }
    if(screenshotUrls.value.length){ selectedZone.value='shots'; selectedShot.value = 0; nextTick(scrollShotsToSelected); } return true; }
      if(action==='confirm') { play(); return true; }
      if(action==='back') { goBackToPlatform(); return true; }
      return false;
    case 'description':
      if(action==='moveDown') { selectedZone.value='play'; return true; }
      if(action==='confirm') { openDescription(); return true; }
      if(action==='back') { goBackToPlatform(); return true; }
      return false;
    case 'details':
      if(action==='moveLeft') { selectedZone.value='play'; return true; }
      if(action==='moveUp') { selectedZone.value='description'; return true; }
      if(action==='moveDown') { 
        if(rom.value?.user_states?.length){ selectedZone.value='states'; selectedStateIndex.value = 0; return true; }
        if(screenshotUrls.value.length){ selectedZone.value='shots'; selectedShot.value = 0; nextTick(scrollShotsToSelected); } return true; }
      if(action==='confirm') { openDetails(); return true; }
      if(action==='back') { goBackToPlatform(); return true; }
      return false;
    case 'states':
      if(action==='moveUp') { selectedZone.value='play'; return true; }
      if(action==='moveDown') { if(screenshotUrls.value.length){ selectedZone.value='shots'; selectedShot.value=0; nextTick(scrollShotsToSelected); } return true; }
  if(action==='moveRight') { if(rom.value?.user_states){ selectedStateIndex.value = (selectedStateIndex.value + 1) % rom.value.user_states.length; nextTick(scrollStatesToSelected); return true; } }
  if(action==='moveLeft') { if(rom.value?.user_states){ selectedStateIndex.value = (selectedStateIndex.value - 1 + rom.value.user_states.length) % rom.value.user_states.length; nextTick(scrollStatesToSelected); return true; } }
      if(action==='confirm') { startWithState(selectedStateIndex.value); return true; }
      if(action==='back') { goBackToPlatform(); return true; }
      return false;
    case 'shots':
      if(action==='moveUp') { selectedZone.value = rom.value?.user_states?.length ? 'states' : 'play'; return true; }
      if(action==='moveRight') { if(screenshotUrls.value.length){ selectedShot.value = (selectedShot.value + 1) % screenshotUrls.value.length; nextTick(scrollShotsToSelected); } return true; }
      if(action==='moveLeft') { if(screenshotUrls.value.length){ selectedShot.value = (selectedShot.value - 1 + screenshotUrls.value.length) % screenshotUrls.value.length; nextTick(scrollShotsToSelected); } return true; }
      if(action==='confirm') { showLightbox.value = true; return true; }
      if(action==='back') { goBackToPlatform(); return true; }
      return false;
    default:
      return false;
  }
}

function play(){
  romApi.updateUserRomProps({ romId, data: {}, updateLastPlayed: true }).catch(()=>{});
  const query: Record<string, number> = {};
  // Only pass state if we're in the states zone (explicitly selected a state)
  if(selectedZone.value === 'states' && currentStateId.value) {
    query.state = currentStateId.value;
  }
  router.push({ name: 'console-play', params: { rom: romId }, query: Object.keys(query).length ? query : undefined });
}

const currentStateId = computed(() => rom.value?.user_states?.[selectedStateIndex.value]?.id);

function relativeTime(d: string | Date){
  try{ return formatDistanceToNow(new Date(d), { addSuffix: true }); }catch{ return ''; }
}

function startWithState(i: number){
  if(!rom.value?.user_states?.[i]) return;
  selectedStateIndex.value = i;
  play();
}

function registerShotEl(el: HTMLElement|null, idx: number){
  if(!el) return;
  shotEls.value[idx] = el;
}

function registerStateEl(el: HTMLElement|null, idx: number){
  if(!el) return;
  stateEls.value[idx] = el;
}

function scrollShotsToSelected(){
  const container = shotsRef.value;
  const el = shotEls.value[selectedShot.value];
  if(!container || !el) return;
  const cr = container.getBoundingClientRect();
  const er = el.getBoundingClientRect();
  const desiredLeft = el.offsetLeft - (cr.width/2) + (er.width/2);
  container.scrollTo({ left: desiredLeft, behavior: 'smooth' });
}

function scrollStatesToSelected(){
  const container = statesRef.value;
  const el = stateEls.value[selectedStateIndex.value];
  if(!container || !el) return;
  const cr = container.getBoundingClientRect();
  const er = el.getBoundingClientRect();
  const desiredLeft = el.offsetLeft - (cr.width/2) + (er.width/2);
  container.scrollTo({ left: desiredLeft, behavior: 'smooth' });
}

// Screenshot URL helpers and error handler
function primaryScreenshotSrc(u: string): string {
  // Use backend-provided URLs directly
  return u;
}
function altScreenshotSrc(u: string): string {
  // If u points to backend-local assets under /assets/, use raw endpoint (/api/raw/assets/<relative>)
  // Example: /assets/romm/resources/roms/1/3/screenshots/0.jpg?ts=123
  // becomes: /api/raw/assets/romm/resources/roms/1/3/screenshots/0.jpg?ts=123
  const [path, qs] = u.split('?');
  if (path.startsWith('/assets/')) {
    const relative = path.slice('/assets/'.length);
    return `/api/raw/assets/${relative}${qs ? `?${qs}` : ''}`;
  }
  return u;
}
function onScreenshotError(e: Event) {
  const img = e.target as HTMLImageElement;
  const triedAlt = img.dataset.altTried === 'true';
  if (!triedAlt) {
    const alt = img.getAttribute('data-alt');
    if (alt && alt !== img.src) {
      img.dataset.altTried = 'true';
      img.src = alt;
      return;
    }
  }
  // Hide broken image
  img.style.display = 'none';
}

function openLightbox(i: number){ selectedShot.value = i; showLightbox.value = true; }

onMounted(async () => {
  try{
    const { data } = await romApi.getRom({ romId });
    const slug = (data.platform_slug as string) || (data as unknown as { platform?: string; system?: string }).platform || (data as unknown as { platform?: string; system?: string }).system;
    const core = getCoreForPlatform(slug);
    if(!core) { unsupported.value = true; throw new Error(`Platform ${slug} not supported yet.`); }
    if(!data.files || !data.files.length) throw new Error('No game files found');
    rom.value = data;
  }catch(err: unknown){ error.value = err instanceof Error ? err.message : 'Failed to load game'; }
  finally{ loading.value = false; }
  selectedZone.value = 'play';
  off = on(handleAction);
});
// Focus overlays when opened so Esc works even if window handlers exist
watch(showDescription, (v) => { if(v) nextTick(() => descOverlayRef.value?.focus?.()); });
watch(showDetails, (v) => { if(v) nextTick(() => detailsOverlayRef.value?.focus?.()); });
watch(showLightbox, (v) => {
  if(v) {
    // Lightbox is its own component; it manages Esc and arrows internally via overlay bindings
  }
});
let off: (() => void) | null = null;
onUnmounted(() => { off?.(); off = null; });
</script>

<style scoped>
@keyframes subtleFloat { 0%,100%{ transform: scale(1.3) translateX(0) translateY(0) } 33%{ transform: scale(1.32) translateX(-10px) translateY(-5px) } 66%{ transform: scale(1.31) translateX(8px) translateY(-3px) } }
.modal-overlay{ position:fixed; inset:0; background:rgba(0,0,0,0.8); backdrop-filter:blur(10px); display:flex; align-items:center; justify-content:center; z-index:1000; animation: fadeIn .2s ease; }
.modal-content{ background:rgba(20,20,20,0.95); backdrop-filter:blur(20px); border:1px solid rgba(255,255,255,0.2); border-radius:16px; max-width:600px; max-height:70vh; width:90%; overflow:hidden; animation: slideUp .3s ease; }
.modal-content.modal-wide{ max-width:1000px; }
.modal-header{ display:flex; justify-content:space-between; align-items:center; padding:1.5rem 2rem; border-bottom:1px solid rgba(255,255,255,0.1); }
.modal-header h2{ color:white; font-size:1.5rem; font-weight:600; margin:0; }
.modal-close{ background:none; border:none; color:#ccc; font-size:2rem; cursor:pointer; padding:0; width:40px; height:40px; display:flex; align-items:center; justify-content:center; border-radius:8px; transition:all .2s ease; }
.modal-close:hover{ background:rgba(255,255,255,0.1); color:white; }
.modal-body{ padding:2rem; max-height:50vh; overflow-y:auto; scroll-behavior:smooth; }
.modal-footer{ padding:1rem 2rem; border-top:1px solid rgba(255,255,255,0.1); text-align:center; }
.modal-hint{ color:#888; font-size:.9rem; }
@keyframes fadeIn { from{opacity:0} to{opacity:1} }
@keyframes slideUp { from{ opacity:0; transform: translateY(20px); } to{ opacity:1; transform: translateY(0);} }
</style>
