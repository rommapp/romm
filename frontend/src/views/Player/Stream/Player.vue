<template>
  <v-main class="stream-player-main">
    <!-- Launch screen  -->
    <div
      v-if="
        playerState === 'idle' ||
        playerState === 'loading' ||
        playerState === 'error'
      "
      class="launch-screen"
    >
      <!-- Cover art -->
      <img
        v-if="rom?.url_cover"
        :src="rom.url_cover"
        class="launch-cover mx-auto mb-5 d-block"
        alt="Cover art"
      />
      <v-icon v-else size="96" color="grey-darken-1" class="mb-5">
        mdi-disc
      </v-icon>

      <h1 class="text-h5 font-weight-bold text-center mb-1">
        {{ rom?.name ?? "Unknown Game" }}
      </h1>
      <p class="text-caption text-medium-emphasis text-center mb-6">
        {{ platformLabel }} · Streaming
      </p>

      <!-- Session-in-use alert -->
      <v-alert
        v-if="playerState === 'error' && errorType === 'occupied'"
        type="warning"
        variant="tonal"
        class="mb-5"
        max-width="440"
      >
        <strong>Session in use.</strong><br />
        <span v-if="occupiedBy">
          {{ occupiedBy.rom_name }} has been playing since
          {{ formatTime(occupiedBy.claimed_at) }}.
        </span>
        <span v-else>Someone else is currently playing. Try again later.</span>
      </v-alert>

      <!-- Generic error alert -->
      <v-alert
        v-else-if="playerState === 'error'"
        type="error"
        variant="tonal"
        class="mb-5"
        max-width="440"
      >
        {{ errorMessage }}
      </v-alert>

      <!-- Action buttons -->
      <div class="d-flex gap-3 justify-center flex-wrap">
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-play"
          :loading="playerState === 'loading'"
          :disabled="playerState === 'loading'"
          @click="handlePlay"
        >
          {{
            playerState === "error" && errorType === "occupied"
              ? "Try Again"
              : "Play"
          }}
        </v-btn>

        <v-btn
          variant="tonal"
          size="large"
          prepend-icon="mdi-arrow-left"
          :to="backRoute"
        >
          Back
        </v-btn>
      </div>
    </div>

    <!-- Active player (shown after session is claimed) -->
    <div
      v-show="playerState === 'playing'"
      ref="playerWrapper"
      class="player-wrapper"
      :class="{ 'hide-cursor': !isUIVisible }"
      @mousemove="handleMouseMove"
      role="presentation"
    >
      <!-- iframe points at the emulator container's built-in web UI -->
      <iframe
        v-if="containerHost"
        ref="streamFrame"
        :src="containerHost"
        class="stream-frame"
        allow="gamepad *; fullscreen *; autoplay *"
        allowfullscreen
        referrerpolicy="no-referrer"
        title="Game stream"
      />

      <!-- Hover sensors for cross-origin fallback -->
      <div class="player-sensor-top" @mousemove="handleMouseMove" />
      <div class="player-sensor-bottom" @mousemove="handleMouseMove" />

      <!-- Control bar — mirrors the EmulatorJS player bar style -->
      <div class="player-control-bar" :class="{ 'is-visible': isUIVisible }">
        <span class="player-title text-body-2 font-weight-medium">
          {{ rom?.name }}
        </span>

        <span class="text-caption text-medium-emphasis ml-2">
          · {{ platformLabel }}
        </span>

        <v-spacer />

        <!-- Volume controls -->
        <v-btn
          icon
          variant="text"
          density="compact"
          :title="isMuted ? 'Unmute' : 'Mute'"
          @click="toggleMute"
        >
          <svg
            v-if="!isMuted"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
          >
            <path
              d="M8.335799999999999 1.8004c-0.12733333333333333 -0.05506666666666667 -0.2669333333333333 -0.0754 -0.4046666666666666 -0.058866666666666664 -0.13773333333333332 0.01653333333333333 -0.2685333333333333 0.06933333333333333 -0.3792 0.1529333333333333L3.8049999999999997 4.857533333333333H0.9438666666666666c-0.20786666666666667 0 -0.40726666666666667 0.08253333333333332 -0.5542666666666667 0.2295333333333333 -0.147 0.147 -0.22959999999999997 0.34639999999999993 -0.22959999999999997 0.5543333333333333v4.7032c0 0.20786666666666667 0.08259999999999999 0.40726666666666667 0.22959999999999997 0.5542666666666667 0.147 0.14706666666666665 0.34639999999999993 0.22959999999999997 0.5542666666666667 0.22959999999999997h2.861133333333333l3.7077333333333335 2.9629999999999996c0.13786666666666667 0.11073333333333332 0.3091333333333333 0.17146666666666666 0.486 0.17246666666666666 0.11706666666666667 0.002 0.2328 -0.024933333333333335 0.3370666666666667 -0.0784 0.1334 -0.06346666666666667 0.24613333333333332 -0.1634 0.32513333333333333 -0.2882 0.07906666666666666 -0.12486666666666665 0.12126666666666666 -0.26946666666666663 0.12166666666666666 -0.4172666666666667V2.5058666666666665c-0.00039999999999999996 -0.14773333333333333 -0.0426 -0.29233333333333333 -0.12166666666666666 -0.4172 -0.07899999999999999 -0.1248 -0.19173333333333334 -0.22473333333333334 -0.32513333333333333 -0.28826666666666667Zm-1.1209333333333333 10.049199999999999L4.565333333333333 9.733133333333333c-0.13786666666666667 -0.11059999999999999 -0.3091333333333333 -0.1714 -0.486 -0.1724H1.7277333333333333V6.4252H4.079333333333333c0.17686666666666664 -0.001 0.3481333333333333 -0.061733333333333335 0.486 -0.1724l2.6495333333333333 -2.1164666666666667v7.713266666666667Zm6.788333333333332 -8.293333333333333c-0.1476 -0.1476 -0.3478 -0.2305333333333333 -0.5565333333333333 -0.2305333333333333s-0.40900000000000003 0.08293333333333333 -0.5566 0.2305333333333333c-0.1476 0.1476 -0.2305333333333333 0.3478 -0.2305333333333333 0.5565333333333333s0.08293333333333333 0.40900000000000003 0.2305333333333333 0.5566c0.46166666666666667 0.46086666666666665 0.8223333333333334 1.0126666666666666 1.0591333333333333 1.6204 0.23686666666666667 0.6077999999999999 0.34473333333333334 1.2581333333333333 0.31666666666666665 1.9098 -0.028 0.6517333333333333 -0.19126666666666664 1.2904 -0.47939999999999994 1.8756666666666666 -0.28806666666666664 0.5851333333333333 -0.6948666666666666 1.1039999999999999 -1.1942666666666666 1.5235333333333332 -0.12126666666666666 0.10366666666666666 -0.208 0.24193333333333333 -0.2486 0.39626666666666666 -0.0406 0.15439999999999998 -0.03319999999999999 0.3174 0.021399999999999995 0.4673999999999999 0.05446666666666666 0.15 0.15353333333333333 0.2797333333333333 0.2837333333333333 0.3719333333333333 0.13026666666666664 0.0922 0.28559999999999997 0.1424 0.44513333333333327 0.144 0.18319999999999997 0.00039999999999999996 0.3606666666666667 -0.0634 0.5017333333333334 -0.18033333333333335 0.6669999999999999 -0.5586666666666666 1.2105333333333332 -1.25 1.5958666666666668 -2.0300666666666665 0.3853333333333333 -0.7800666666666666 0.6041333333333333 -1.6318666666666666 0.6424666666666666 -2.5010666666666665 0.03833333333333333 -0.8692666666666666 -0.10466666666666666 -1.7369333333333332 -0.41986666666666667 -2.547933333333333 -0.31506666666666666 -0.8109999999999999 -0.7956 -1.5475333333333332 -1.4108666666666665 -2.162733333333333ZM11.784799999999999 5.774666666666667c-0.07306666666666667 -0.07313333333333333 -0.1598 -0.13106666666666666 -0.2553333333333333 -0.17066666666666666 -0.09553333333333333 -0.03953333333333333 -0.1978 -0.059866666666666665 -0.30119999999999997 -0.059866666666666665 -0.10339999999999999 0 -0.20566666666666666 0.02033333333333333 -0.3011333333333333 0.059866666666666665 -0.09559999999999999 0.039599999999999996 -0.18233333333333335 0.09753333333333333 -0.25539999999999996 0.17066666666666666 -0.07306666666666667 0.07306666666666667 -0.13106666666666666 0.1598 -0.17066666666666666 0.2553333333333333 -0.03953333333333333 0.09546666666666666 -0.059866666666666665 0.1978 -0.059866666666666665 0.30119999999999997 0 0.10333333333333333 0.02033333333333333 0.20573333333333332 0.059866666666666665 0.30119999999999997 0.039599999999999996 0.09546666666666666 0.09759999999999999 0.18226666666666663 0.17066666666666666 0.2553333333333333 0.2944 0.29266666666666663 0.46073333333333333 0.6902 0.46246666666666664 1.1052666666666666 0.00013333333333333334 0.2284 -0.04953333333333333 0.4540666666666667 -0.14566666666666667 0.6611333333333334 -0.09613333333333332 0.2072 -0.2364 0.3908666666666667 -0.4108666666666666 0.5381333333333334 -0.0794 0.06586666666666666 -0.145 0.14666666666666667 -0.19306666666666666 0.23786666666666767 -0.048133333333333334 0.0912 -0.0778 0.19099999999999998 -0.0872 0.2937333333333333 -0.009466666666666667 0.1026 0.0013999999999999998 0.2061333333333333 0.032 0.3046 0.030666666666666665 0.09846666666666666 0.08033333333333333 0.18993333333333332 0.14633333333333332 0.2690666666666667 0.06639999999999999 0.07886666666666667 0.1476 0.14379999999999998 0.23906666666666665 0.19119999999999998 0.09153333333333333 0.047333333333333324 0.19146666666666667 0.07626666666666666 0.29406666666666664 0.08499999999999999 0.10266666666666666 0.008733333333333333 0.206 -0.0028666666666666667 0.30419999999999997 -0.034133333333333335 0.09813333333333332 -0.0312 0.18926666666666664 -0.08153333333333333 0.2679333333333333 -0.148 0.3504666666666666 -0.29386666666666666 0.6324 -0.6607999999999999 0.8260666666666667 -1.0751333333333333 0.19366666666666665 -0.41433333333333333 0.2942666666666667 -0.8661333333333332 0.29486666666666667 -1.3234666666666666 -0.004399999999999999 -0.8308666666666666 -0.33359999999999995 -1.627 -0.9171333333333332 -2.2183333333333333Z"
              fill="currentColor"
              stroke-width="0.6667"
            ></path>
          </svg>
          <svg
            v-else
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
          >
            <path
              d="M8.334733333333332 1.8012c-0.12726666666666664 -0.05506666666666667 -0.26686666666666664 -0.0754 -0.40459999999999996 -0.058866666666666664 -0.13766666666666666 0.01653333333333333 -0.26846666666666663 0.06926666666666667 -0.3791333333333333 0.1529333333333333L3.8045333333333335 4.857866666666666H0.9438c-0.20786666666666667 0 -0.40726666666666667 0.08259999999999999 -0.5542666666666667 0.22959999999999997 -0.14693333333333333 0.147 -0.2295333333333333 0.34633333333333327 -0.2295333333333333 0.5542v4.7025999999999994c0 0.20786666666666667 0.08259999999999999 0.40726666666666667 0.2295333333333333 0.5542 0.147 0.14706666666666665 0.34639999999999993 0.22959999999999997 0.5542666666666667 0.22959999999999997h2.860733333333333l3.7072666666666665 2.9626666666666663c0.13786666666666667 0.11066666666666666 0.3091333333333333 0.1714 0.48593333333333333 0.1724 0.11706666666666667 0.0019333333333333331 0.2328 -0.024933333333333335 0.33699999999999997 -0.0784 0.1334 -0.06346666666666667 0.24613333333333332 -0.1634 0.32513333333333333 -0.2882 0.07906666666666666 -0.1248 0.12126666666666666 -0.2694 0.12166666666666666 -0.4172V2.5065999999999997c-0.00039999999999999996 -0.14773333333333333 -0.0426 -0.29233333333333333 -0.12166666666666666 -0.41713333333333336 -0.07899999999999999 -0.12486666666666665 -0.19173333333333334 -0.22473333333333334 -0.32513333333333333 -0.28826666666666667Zm-1.1208 10.047933333333333 -2.6491333333333333 -2.1162c-0.13786666666666667 -0.11059999999999999 -0.3091333333333333 -0.1714 -0.48593333333333333 -0.1724h-2.3513333333333333V6.4254h2.3513333333333333c0.17679999999999998 -0.001 0.34806666666666664 -0.061733333333333335 0.48593333333333333 -0.1724l2.6491333333333333 -2.1162v7.7123333333333335Zm6.983466666666666 -3.8562 1.4107333333333332 -1.4029333333333334c0.07306666666666667 -0.07306666666666667 0.13106666666666666 -0.1598 0.17066666666666666 -0.25526666666666664 0.039466666666666664 -0.09546666666666666 0.059866666666666665 -0.1978 0.059866666666666665 -0.30119999999999997 0 -0.10333333333333333 -0.020399999999999998 -0.20566666666666666 -0.059866666666666665 -0.3011333333333333 -0.039599999999999996 -0.09546666666666666 -0.09759999999999999 -0.18226666666666663 -0.17066666666666666 -0.2553333333333333 -0.073 -0.07306666666666667 -0.1598 -0.13106666666666666 -0.2553333333333333 -0.1706 -0.09546666666666666 -0.03953333333333333 -0.19773333333333332 -0.059866666666666665 -0.3011333333333333 -0.059866666666666665 -0.10333333333333333 0 -0.20566666666666666 0.02033333333333333 -0.3011333333333333 0.059866666666666665 -0.09553333333333333 0.03953333333333333 -0.18226666666666663 0.09753333333333333 -0.2553333333333333 0.1706l-1.4029333333333334 1.4108 -1.4029999999999998 -1.4108c-0.14753333333333332 -0.1476 -0.3477333333333333 -0.23046666666666665 -0.5564666666666667 -0.23046666666666665s-0.4088666666666666 0.08286666666666666 -0.5564666666666667 0.23046666666666665c-0.1476 0.1476 -0.2305333333333333 0.3478 -0.2305333333333333 0.5564666666666667s0.08293333333333333 0.4088666666666666 0.2305333333333333 0.5564666666666667l1.4108 1.4029333333333334 -1.4108 1.4029999999999998c-0.07346666666666667 0.07286666666666666 -0.1317333333333333 0.15953333333333333 -0.17153333333333332 0.2551333333333333 -0.03986666666666666 0.09546666666666666 -0.06033333333333333 0.19786666666666666 -0.06033333333333333 0.30133333333333334s0.020466666666666668 0.20586666666666667 0.06033333333333333 0.30146666666666666c0.0398 0.09553333333333333 0.09806666666666666 0.18219999999999997 0.17153333333333332 0.255 0.07286666666666666 0.07353333333333333 0.1596 0.13186666666666666 0.25506666666666666 0.1716 0.09553333333333333 0.0398 0.19793333333333332 0.06026666666666666 0.3014 0.06026666666666666s0.20593333333333333 -0.020466666666666668 0.30146666666666666 -0.06026666666666666c0.09546666666666666 -0.03973333333333333 0.1821333333333333 -0.09806666666666666 0.255 -0.1716l1.4029999999999998 -1.4108 1.4029333333333334 1.4108c0.07286666666666666 0.07353333333333333 0.1596 0.13186666666666666 0.25506666666666666 0.1716 0.09553333333333333 0.0398 0.19793333333333332 0.06026666666666666 0.3014 0.06026666666666666s0.20593333333333333 -0.020466666666666668 0.30146666666666666 -0.06026666666666666c0.09546666666666666 -0.03973333333333333 0.1821333333333333 -0.09806666666666666 0.255 -0.1716 0.07346666666666667 -0.0728 0.13179999999999997 -0.15946666666666665 0.1716 -0.255 0.0398 -0.09559999999999999 0.06026666666666666 -0.19799999999999998 0.06026666666666666 -0.30146666666666666s-0.020466666666666668 -0.20593333333333333 -0.06026666666666666 -0.30133333333333334c-0.0398 -0.09559999999999999 -0.09813333333333332 -0.18226666666666663 -0.1716 -0.2551333333333333l-1.4107333333333332 -1.4029999999999998Z"
              fill="currentColor"
              stroke-width="0.6667"
            ></path>
          </svg>
        </v-btn>
        <input
          v-model.number="volume"
          type="range"
          min="0"
          max="1"
          step="0.01"
          class="volume-slider"
          title="Volume"
          :disabled="isMuted"
        />

        <!-- Save/load state controls -->
        <select
          v-model.number="selectedSlot"
          class="slot-selector"
          title="Save slot"
        >
          <option v-for="n in 9" :key="n" :value="n">Slot {{ n }}</option>
        </select>

        <v-btn
          icon
          variant="text"
          density="compact"
          title="Save state"
          :loading="isSavingState"
          :disabled="isSavingState || isLoadingState || isSavingAndExiting"
          @click="handleSaveState"
        >
          <v-icon size="20">mdi-content-save-outline</v-icon>
        </v-btn>

        <v-btn
          icon
          variant="text"
          density="compact"
          title="Load state"
          :loading="isLoadingState"
          :disabled="isSavingState || isLoadingState || isSavingAndExiting"
          @click="handleLoadState"
        >
          <v-icon size="20">mdi-restore</v-icon>
        </v-btn>

        <v-btn
          icon
          variant="text"
          density="compact"
          :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen'"
          @click="toggleFullscreen"
        >
          <!-- Icons by SVGRepo (CC Attribution License) -->
          <svg
            v-if="isFullscreen"
            width="20"
            height="20"
            viewBox="0 0 48 48"
            xmlns="http://www.w3.org/2000/svg"
          >
            <g id="Layer_2" data-name="Layer 2">
              <g id="icons_Q2" data-name="icons Q2">
                <g>
                  <path
                    fill="currentColor"
                    d="M8,26a2,2,0,0,0-2,2.3A2.1,2.1,0,0,0,8.1,30h7.1L4.7,40.5a2,2,0,0,0-.2,2.8A1.8,1.8,0,0,0,6,44a2,2,0,0,0,1.4-.6L18,32.8v7.1A2.1,2.1,0,0,0,19.7,42,2,2,0,0,0,22,40V28a2,2,0,0,0-2-2Z"
                  />
                  <path
                    fill="currentColor"
                    d="M43.7,4.8a2,2,0,0,0-3.1-.2L30,15.2V8.1A2.1,2.1,0,0,0,28.3,6,2,2,0,0,0,26,8V20a2,2,0,0,0,2,2H39.9A2.1,2.1,0,0,0,42,20.3,2,2,0,0,0,40,18H32.8L43.4,7.5A2.3,2.3,0,0,0,43.7,4.8Z"
                  />
                </g>
              </g>
            </g>
          </svg>
          <svg
            v-else
            width="20"
            height="20"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M21.7092 2.29502C21.8041 2.3904 21.8757 2.50014 21.9241 2.61722C21.9727 2.73425 21.9996 2.8625 22 2.997L22 3V9C22 9.55228 21.5523 10 21 10C20.4477 10 20 9.55228 20 9V5.41421L14.7071 10.7071C14.3166 11.0976 13.6834 11.0976 13.2929 10.7071C12.9024 10.3166 12.9024 9.68342 13.2929 9.29289L18.5858 4H15C14.4477 4 14 3.55228 14 3C14 2.44772 14.4477 2 15 2H20.9998C21.2749 2 21.5242 2.11106 21.705 2.29078L21.7092 2.29502Z"
              fill="currentColor"
            />
            <path
              d="M10.7071 14.7071L5.41421 20H9C9.55228 20 10 20.4477 10 21C10 21.5523 9.55228 22 9 22H3.00069L2.997 22C2.74301 21.9992 2.48924 21.9023 2.29502 21.7092L2.29078 21.705C2.19595 21.6096 2.12432 21.4999 2.07588 21.3828C2.02699 21.2649 2 21.1356 2 21V15C2 14.4477 2.44772 14 3 14C3.55228 14 4 14.4477 4 15V18.5858L9.29289 13.2929C9.68342 12.9024 10.3166 12.9024 10.7071 13.2929C11.0976 13.6834 11.0976 14.3166 10.7071 14.7071Z"
              fill="currentColor"
            />
          </svg>
        </v-btn>

        <v-btn
          icon
          variant="text"
          density="compact"
          title="Save and exit"
          :loading="isSavingAndExiting"
          :disabled="isSavingAndExiting"
          @click="handleSaveAndExit"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M3 5.75C3 4.23122 4.23122 3 5.75 3H15.7145C16.5764 3 17.4031 3.34241 18.0126 3.9519L20.0481 5.98744C20.6576 6.59693 21 7.42358 21 8.28553V12.0218C20.5368 11.7253 20.0335 11.4858 19.5 11.3135V8.28553C19.5 7.8214 19.3156 7.37629 18.9874 7.0481L16.9519 5.01256C16.6918 4.75246 16.3582 4.58269 16 4.52344V7.25C16 8.49264 14.9926 9.5 13.75 9.5H9.25C8.00736 9.5 7 8.49264 7 7.25V4.5H5.75C5.05964 4.5 4.5 5.05964 4.5 5.75V18.25C4.5 18.9404 5.05964 19.5 5.75 19.5H6V14.25C6 13.0074 7.00736 12 8.25 12H14.0343C13.3987 12.4013 12.8376 12.9098 12.3762 13.5H8.25C7.83579 13.5 7.5 13.8358 7.5 14.25V19.5H11.3135C11.4858 20.0335 11.7253 20.5368 12.0218 21H5.75C4.23122 21 3 19.7688 3 18.25V5.75ZM8.5 4.5V7.25C8.5 7.66421 8.83579 8 9.25 8H13.75C14.1642 8 14.5 7.66421 14.5 7.25V4.5H8.5ZM23 17.5C23 20.5376 20.5376 23 17.5 23C14.4624 23 12 20.5376 12 17.5C12 14.4624 14.4624 12 17.5 12C20.5376 12 23 14.4624 23 17.5ZM14.5 17C14.2239 17 14 17.2239 14 17.5C14 17.7761 14.2239 18 14.5 18H19.2929L17.6464 19.6464C17.4512 19.8417 17.4512 20.1583 17.6464 20.3536C17.8417 20.5488 18.1583 20.5488 18.3536 20.3536L20.8536 17.8536C21.0488 17.6583 21.0488 17.3417 20.8536 17.1464L18.3536 14.6464C18.1583 14.4512 17.8417 14.4512 17.6464 14.6464C17.4512 14.8417 17.4512 15.1583 17.6464 15.3536L19.2929 17H14.5Z"
              fill="currentColor"
            />
          </svg>
        </v-btn>

        <v-btn
          icon
          variant="text"
          density="compact"
          color="error"
          title="Stop and release session"
          :disabled="isSavingAndExiting"
          @click="handleStop"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 512 512"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill="currentColor"
              transform="translate(106.71015930175781,57.85955810546875)"
              d="M0 0 C1.11432404 -0.00571014 2.22864807 -0.01142029 3.3767395 -0.01730347 C5.18864525 -0.01898026 5.18864525 -0.01898026 7.03715515 -0.02069092 C8.32079956 -0.02565582 9.60444397 -0.03062073 10.92698669 -0.03573608 C14.43745383 -0.04880523 17.94790188 -0.05529409 21.45838952 -0.05974674 C23.65521704 -0.06268591 25.85203944 -0.06679225 28.04886436 -0.07125092 C34.93289867 -0.08491042 41.81692117 -0.09458505 48.70096809 -0.09845281 C56.62809399 -0.1029321 64.55504735 -0.12048046 72.48212081 -0.1494534 C78.62331182 -0.1711146 84.76445444 -0.18115942 90.90568322 -0.18249393 C94.56739115 -0.18353863 98.22893655 -0.18937501 101.89060402 -0.20731354 C105.97862241 -0.22695303 110.06628218 -0.22248764 114.15434265 -0.21600342 C115.35620712 -0.2252182 116.55807159 -0.23443298 117.7963562 -0.243927 C128.25695616 -0.19204106 135.70279924 1.54525583 143.3367157 8.92559814 C149.32027748 15.7109572 150.00271881 22.57536325 149.7351532 31.47637939 C148.78366845 39.30526269 145.36095272 44.90935193 139.3289032 49.88653564 C101.25040586 73.30262309 49.99202309 54.14044189 5.2898407 54.14044189 C5.2898407 149.18044189 5.2898407 244.22044189 5.2898407 342.14044189 C46.5398407 342.14044189 87.7898407 342.14044189 130.2898407 342.14044189 C138.7221695 346.35660629 145.43170845 349.84660102 148.8132782 358.87091064 C150.61989506 367.47455322 150.43692569 376.32752594 145.8992157 383.98809814 C140.85419249 390.73520442 135.44550735 394.21504541 127.2898407 396.14044189 C122.93978016 396.55815081 118.61711804 396.55086803 114.2495575 396.52862549 C112.33066208 396.53651093 112.33066208 396.53651093 110.3730011 396.54455566 C106.88721422 396.55814767 103.4016959 396.55296346 99.91590476 396.54341841 C96.2500006 396.53577451 92.58411804 396.54288092 88.91821289 396.5475769 C82.76087865 396.55302284 76.60365262 396.54587565 70.44633484 396.53155518 C63.35548855 396.51525263 56.26490142 396.52050432 49.17406148 396.53703439 C43.06076952 396.55070862 36.94755499 396.55253945 30.83425266 396.54471838 C27.19431593 396.5400715 23.55450041 396.53933336 19.91457176 396.54932785 C15.84899789 396.55971252 11.78386064 396.54526395 7.7183075 396.52862549 C6.53194199 396.53469818 5.34557648 396.54077087 4.1232605 396.54702759 C-11.20396154 396.43152478 -24.15691497 392.28891373 -35.3820343 381.66387939 C-44.28083192 372.01853835 -48.82409228 360.68801365 -48.84158707 347.59428978 C-48.84734878 345.96769198 -48.84734878 345.96769198 -48.8532269 344.30823362 C-48.85236042 343.12770213 -48.85149394 341.94717065 -48.8506012 340.73086548 C-48.85357232 339.46830449 -48.85654344 338.2057435 -48.8596046 336.90492308 C-48.86765169 333.40715456 -48.86946289 329.90940659 -48.87020206 326.41162992 C-48.87205663 322.63641389 -48.87960601 318.86120843 -48.88633728 315.08599854 C-48.89990507 306.83374664 -48.90594296 298.58149961 -48.91034794 290.32923841 C-48.91311312 285.17349743 -48.91735099 280.01775831 -48.92185211 274.86201859 C-48.93404299 260.57883255 -48.94434251 246.29564802 -48.9477272 232.01245689 C-48.94794677 231.09872688 -48.94816634 230.18499686 -48.94839256 229.24357805 C-48.94861083 228.32769829 -48.94882911 227.41181853 -48.949054 226.46818483 C-48.94949746 224.61235515 -48.94994403 222.75652548 -48.95039368 220.9006958 C-48.95061511 219.98014596 -48.95083654 219.05959611 -48.95106468 218.11115082 C-48.95501109 203.20133991 -48.97246113 188.29157793 -48.9957532 173.38178591 C-49.01949029 158.06308797 -49.03193014 142.74441455 -49.03309512 127.42569792 C-49.03401058 118.8292872 -49.03973032 110.23294021 -49.05791473 101.63654709 C-49.07334759 94.31525596 -49.07841745 86.99404827 -49.07017663 79.67274396 C-49.06628131 75.94061166 -49.06714467 72.20864723 -49.08123398 68.4765358 C-49.09640153 64.42154391 -49.08807336 60.36692701 -49.07765198 56.31192017 C-49.08570838 55.14477301 -49.09376479 53.97762585 -49.10206532 52.7751106 C-49.01076508 37.53432896 -44.78805282 24.61912176 -34.2335968 13.46856689 C-24.51666184 4.50371668 -13.17219429 0.04066434 0 0 Z"
            />
            <path
              fill="currentColor"
              transform="translate(354,145)"
              d="M0 0 C6.65383716 5.38756849 12.70653895 11.55150894 18.7668457 17.58984375 C19.9859388 18.79908005 19.9859388 18.79908005 21.22966003 20.03274536 C23.88121896 22.66481236 26.5289391 25.30069023 29.17578125 27.9375 C30.54276689 29.29837234 30.54276689 29.29837234 31.93736839 30.68673706 C36.25765988 34.98840686 40.57593243 39.29208189 44.89111739 43.59887409 C49.84289994 48.5408599 54.8028842 53.47442177 59.7698701 58.40112591 C64.09915132 62.69651391 68.41731801 67.00292328 72.73171043 71.31326294 C74.55791924 73.13461318 76.38749409 74.95259512 78.22054482 76.76705933 C80.78328273 79.30539511 83.33303948 81.85612927 85.88012695 84.41015625 C86.63190216 85.1491214 87.38367737 85.88808655 88.15823364 86.64944458 C95.24091079 93.80245935 99.57164405 100.57466081 100.25 110.75 C100.00512848 123.77716495 91.05791774 132.24259775 82.38354492 140.90698242 C81.53881119 141.75843338 80.69407745 142.60988434 79.82374573 143.48713684 C77.52578639 145.80074008 75.22341196 148.1098196 72.91826034 150.41625381 C71.47410768 151.86183611 70.03139179 153.30883674 68.58916664 154.75634193 C63.54584323 159.81811277 58.49743695 164.87474829 53.4440918 169.92651367 C48.75201646 174.61738684 44.07122248 179.31931164 39.39555663 184.02653617 C35.3634391 188.08488489 31.32356637 192.13540363 27.2776745 196.18002015 C24.86890209 198.58828524 22.46326387 200.99947964 20.06542015 203.4186306 C17.38792991 206.11578383 14.6979807 208.79988962 12.00463867 211.48120117 C11.22355743 212.27352142 10.4424762 213.06584167 9.63772583 213.88217163 C2.6370668 220.80391023 -4.57346954 226.0545598 -14.6875 226.25 C-22.94859415 226.11656089 -29.20028258 223.82522872 -35.203125 218.0625 C-41.19414257 211.18585375 -42.55801857 204.68002564 -42.6640625 195.6875 C-40.80756961 185.3785042 -34.39435852 178.70045071 -27.10546875 171.6171875 C-26.14744706 170.66851604 -25.19054158 169.71871619 -24.23469543 168.76785278 C-21.74193069 166.2939842 -19.234519 163.83551868 -16.72351074 161.38018799 C-14.15347524 158.86172477 -11.59791243 156.32866412 -9.04101562 153.796875 C-4.04124138 148.85038039 0.97418726 143.92004807 6 139 C5.13731538 138.99853344 4.27463076 138.99706688 3.38580418 138.99555588 C-17.62232178 138.95847577 -38.63028655 138.89944498 -59.63828182 138.81609726 C-69.79767554 138.77631782 -79.95699192 138.74391974 -90.11645508 138.72900391 C-98.97327014 138.71598174 -107.82991495 138.68900258 -116.68663412 138.64538693 C-121.37457911 138.62278489 -126.06231422 138.60708857 -130.75031853 138.60811615 C-135.16713592 138.6088635 -139.58348956 138.5908826 -144.00018692 138.55883217 C-145.61700512 138.55034678 -147.23387541 138.54857398 -148.8507061 138.55419731 C-159.18009443 138.58532442 -166.59943289 137.63499709 -175.25 131.8125 C-181.10024286 125.82929707 -183.69777543 119.53336853 -184.25 111.25 C-184.09287601 102.89100396 -180.63937941 96.05101294 -175 90 C-168.98933127 85.24155392 -163.45657291 83.75537848 -155.86257935 83.7215271 C-155.16733245 83.7157347 -154.47208555 83.7099423 -153.75577056 83.70397437 C-151.43885788 83.68704315 -149.12214521 83.68410386 -146.80517578 83.68115234 C-145.13928238 83.67184941 -143.47339363 83.66168019 -141.80751038 83.65071106 C-137.29355667 83.62343821 -132.77963413 83.60826969 -128.26561975 83.59528303 C-123.54503466 83.57964063 -118.82451308 83.55285393 -114.10397339 83.5272522 C-105.16874857 83.48048408 -96.23351177 83.44373043 -87.29822719 83.41057932 C-77.124119 83.37234406 -66.95007465 83.32293756 -56.77602029 83.27259517 C-35.85072734 83.16930456 -14.92539397 83.0800348 6 83 C5.45764709 82.46875015 4.91529419 81.93750031 4.35650635 81.39015198 C-0.7761675 76.35805887 -5.89639378 71.31376274 -11.00341415 66.25564671 C-13.6288277 63.65622148 -16.25863959 61.06160905 -18.89941406 58.4777832 C-21.45227896 55.97962443 -23.99239162 53.46910967 -26.52448273 50.94990349 C-27.95394764 49.534044 -29.39601629 48.13094554 -30.83831787 46.72816467 C-37.00528374 40.56384355 -41.18952106 35.13675962 -42.56640625 26.41015625 C-42.5558374 17.352655 -41.23602103 10.86221544 -35.203125 3.9375 C-25.26370638 -5.60434188 -11.86785728 -6.67446504 0 0 Z"
            />
          </svg>
        </v-btn>
      </div>
    </div>
  </v-main>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStreamingStore } from "@/stores/streaming";

interface Rom {
  id: number;
  name: string;
  file_name: string;
  full_path: string;
  platform_slug: string;
  url_cover?: string | null;
}

type PlayerState = "idle" | "loading" | "playing" | "error";
type ErrorType = "occupied" | "not_configured" | "server" | null;

const route = useRoute();
const router = useRouter();
const streamingStore = useStreamingStore();

const rom = ref<Rom | null>(null);
const playerState = ref<PlayerState>("idle");
const errorType = ref<ErrorType>(null);
const errorMessage = ref<string>("");
const occupiedBy = ref<{ rom_name: string; claimed_at: string } | null>(null);
const containerHost = ref<string>("");
const isFullscreen = ref(false);
const isUIVisible = ref(true);
const isSavingAndExiting = ref(false);
const isSavingState = ref(false);
const isLoadingState = ref(false);
const selectedSlot = ref(1);
const volume = ref(1);
const isMuted = ref(false);

// Sync volume slider (0–1) and mute button to the broker in real time.
// Debounced via watch — only fires after the value settles for 150ms.
let volumeDebounce: ReturnType<typeof setTimeout> | null = null;
watch(volume, (val) => {
  if (volumeDebounce) clearTimeout(volumeDebounce);
  volumeDebounce = setTimeout(() => {
    const platform = rom.value?.platform_slug;
    if (platform)
      void streamingStore.setVolume(platform, Math.round(val * 100));
  }, 150);
});
let uiTimeout: ReturnType<typeof setTimeout> | null = null;

const playerWrapper = ref<HTMLElement | null>(null);
const streamFrame = ref<HTMLIFrameElement | null>(null);

// Cleanup refs for iframe listener management
let attachTimeouts: ReturnType<typeof setTimeout>[] = [];
let iframeLoadCleanup: (() => void) | null = null;
let contentWindowCleanup: (() => void) | null = null;

const romId = computed(() => Number(route.params.rom));

const container = computed(() =>
  rom.value
    ? streamingStore.containerForPlatform(rom.value.platform_slug)
    : null,
);

const platformLabel = computed(
  () => container.value?.label ?? rom.value?.platform_slug?.toUpperCase() ?? "",
);

const backRoute = computed(() =>
  rom.value ? { name: "rom", params: { rom: rom.value.id } } : { name: "home" },
);

onMounted(async () => {
  await fetchRom();
  document.addEventListener("fullscreenchange", onFullscreenChange);
  showUI();
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  if (uiTimeout) clearTimeout(uiTimeout);
  attachTimeouts.forEach((id) => clearTimeout(id));
  attachTimeouts = [];
  iframeLoadCleanup?.();
  iframeLoadCleanup = null;
  contentWindowCleanup?.();
  contentWindowCleanup = null;
  if (playerState.value === "playing") {
    // Navigation away while a game is active — fire save+kill in the broker
    // background and return immediately so navigation is never held up.
    void streamingStore.saveAndExit(rom.value?.platform_slug ?? "", 0, false);
  } else {
    // No active game (or handleSaveAndExit already ran) — plain release is fine.
    void streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  }
});

async function fetchRom(): Promise<void> {
  try {
    const res = await fetch(`/api/roms/${romId.value}`);
    if (!res.ok) throw new Error("ROM not found");
    rom.value = await res.json();
  } catch {
    playerState.value = "error";
    errorType.value = "server";
    errorMessage.value = "Could not load ROM details.";
  }
}

function showUI(): void {
  isUIVisible.value = true;
  if (uiTimeout) clearTimeout(uiTimeout);
  uiTimeout = setTimeout(() => {
    isUIVisible.value = false;
  }, 1500);
}

function handleMouseMove(): void {
  showUI();
}

/**
 * Attach mousemove listener to iframe contentWindow if same-origin.
 * Cleans up any previous load listener before adding a new one.
 * Guards against double-attachment across repeated calls.
 */
function attachIframeListeners(): void {
  const frame = streamFrame.value;
  if (!frame) return;

  // Remove stale load listener from a prior call
  iframeLoadCleanup?.();
  iframeLoadCleanup = null;

  const tryAttach = (): void => {
    // Already attached from a previous tryAttach — nothing to do
    if (contentWindowCleanup) return;
    try {
      if (frame.contentWindow) {
        frame.contentWindow.addEventListener("mousemove", handleMouseMove);
        frame.contentWindow.addEventListener("mousedown", handleMouseMove);
        frame.contentWindow.addEventListener("touchstart", handleMouseMove);
        contentWindowCleanup = () => {
          try {
            frame.contentWindow?.removeEventListener(
              "mousemove",
              handleMouseMove,
            );
            frame.contentWindow?.removeEventListener(
              "mousedown",
              handleMouseMove,
            );
            frame.contentWindow?.removeEventListener(
              "touchstart",
              handleMouseMove,
            );
          } catch {
            // Cross-origin — listeners were never added, nothing to remove
          }
        };
      }
    } catch {
      // Cross-origin container, can't access contentWindow
    }
  };

  frame.addEventListener("load", tryAttach);
  iframeLoadCleanup = () => frame.removeEventListener("load", tryAttach);
  tryAttach();
}

async function handlePlay(): Promise<void> {
  if (!rom.value) return;
  if (!container.value) {
    playerState.value = "error";
    errorType.value = "not_configured";
    errorMessage.value = `No streaming container is configured for ${rom.value?.platform_slug}.`;
    return;
  }

  playerState.value = "loading";
  errorType.value = null;
  occupiedBy.value = null;

  // Build the full ROM path as it appears inside the RomM container.
  // RomM mounts the library at /romm/library/roms, so the full path is:
  //   /romm/library/roms/<platform_slug>/<file_name>
  // This must match what the pcsx2 container can see at the same path.
  const romPath = `/romm/library/${rom.value.full_path}`;

  try {
    const session = await streamingStore.claimSession(
      rom.value.platform_slug,
      romPath,
      rom.value.name,
    );
    containerHost.value = session.host;
    playerState.value = "playing";

    // Wait for DOM to update and iframe to exist
    attachTimeouts.forEach((id) => clearTimeout(id));
    attachTimeouts = [];
    attachTimeouts.push(setTimeout(attachIframeListeners, 100));
    // Also try slightly later as some frames might be slow to initialize window
    attachTimeouts.push(setTimeout(attachIframeListeners, 500));
  } catch (err: unknown) {
    playerState.value = "error";

    const error = err as {
      status?: number;
      detail?: { rom_name: string; claimed_at: string } | null;
      message?: string;
    };

    if (error.status === 409) {
      errorType.value = "occupied";
      occupiedBy.value = error.detail ?? null;
    } else if (error.status === 404) {
      errorType.value = "not_configured";
      errorMessage.value =
        "No streaming container configured for this platform.";
    } else {
      errorType.value = "server";
      errorMessage.value = error.message ?? "An unexpected error occurred.";
    }
  }
}

async function handleStop(): Promise<void> {
  await streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  playerState.value = "idle";
  containerHost.value = "";
  router.push(backRoute.value);
}

async function handleSaveAndExit(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isSavingAndExiting.value = true;
  try {
    await streamingStore.saveAndExit(rom.value.platform_slug, 0, true);
  } finally {
    isSavingAndExiting.value = false;
    playerState.value = "idle";
    containerHost.value = "";
  }
  // Outside finally so we always navigate away, even if the save failed.
  router.push(backRoute.value);
}

async function handleSaveState(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isSavingState.value = true;
  try {
    await streamingStore.saveState(rom.value.platform_slug, selectedSlot.value);
  } finally {
    isSavingState.value = false;
  }
}

async function handleLoadState(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isLoadingState.value = true;
  try {
    await streamingStore.loadState(rom.value.platform_slug, selectedSlot.value);
  } finally {
    isLoadingState.value = false;
  }
}

async function toggleFullscreen(): Promise<void> {
  if (!playerWrapper.value) return;
  try {
    if (!document.fullscreenElement) {
      await playerWrapper.value.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  } catch {
    // Fullscreen request denied (e.g., permissions policy or user gesture requirement)
  }
}

function toggleMute(): void {
  isMuted.value = !isMuted.value;
  const platform = rom.value?.platform_slug;
  if (platform) void streamingStore.setMute(platform, isMuted.value);
}

function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}
</script>

<style scoped>
/* Remove default v-main padding so the player fills the viewport */
.stream-player-main {
  padding: 0 !important;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0d0d0d;
}

.launch-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 2rem 1rem;
}

.launch-cover {
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
  width: 260px;
  max-width: 260px;
  height: auto;
  border-radius: 8px;
}

.player-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  overflow: hidden;
}

.player-wrapper.hide-cursor {
  cursor: none !important;
}

.player-control-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  min-height: 48px;
  background: rgba(18, 18, 18, 0.5);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  z-index: 10;
  box-shadow: 0 -4px 10px rgba(0, 0, 0, 0.3);

  /* Use visibility/opacity to avoid layout changes (flashing) */
  visibility: hidden;
  opacity: 0;
  transition:
    opacity 0.3s ease,
    visibility 0.3s ease;

  /* Hint GPU layer promotion to avoid main thread layout updates */
  will-change: opacity;
  transform: translateZ(0);
}

.player-control-bar.is-visible {
  visibility: visible;
  opacity: 1;
}

.player-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.slot-selector {
  -webkit-appearance: none;
  appearance: none;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.87);
  cursor: pointer;
  font-size: 12px;
  height: 28px;
  outline: none;
  padding: 0 6px;
  width: 62px;
}

.slot-selector:hover {
  background: rgba(255, 255, 255, 0.15);
}

.slot-selector option {
  background: #1e1e1e;
  color: rgba(255, 255, 255, 0.87);
}

.volume-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 80px;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.2);
  outline: none;
  cursor: pointer;
  transition: background 0.2s ease;
}

.volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  cursor: pointer;
  transition: background 0.2s ease;
}

.volume-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  cursor: pointer;
}

.volume-slider:hover::-webkit-slider-thumb {
  background: #fff;
}

.volume-slider:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.stream-frame {
  flex: 1;
  width: 100%;
  height: 100%;
  border: none;
  background: #000;
  display: block;
}

:fullscreen .stream-frame {
  height: 100vh;
}

.player-sensor-top,
.player-sensor-bottom {
  position: absolute;
  left: 0;
  width: 100%;
  z-index: 5;
  background: transparent;
}

.player-sensor-top {
  top: 0;
  height: 40px;
}

.player-sensor-bottom {
  bottom: 0;
  height: 80px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
