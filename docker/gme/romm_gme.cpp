// Entry points the soundtrack player's AudioWorklet calls on top of libgme's
// own C API, which returns its handles and track info through out-parameters.
#include <emscripten/emscripten.h>

#include "gme/gme.h"

// Fade applied when the file doesn't specify one.
static int const DEFAULT_FADE_MSECS = 8000;

extern "C" {

EMSCRIPTEN_KEEPALIVE
Music_Emu* romm_gme_open( void const* data, long size, int sample_rate )
{
	Music_Emu* emu = nullptr;
	if ( gme_open_data( data, size, &emu, sample_rate ) )
		return nullptr;
	return emu;
}

// Starts a track with a fade-out at its resolved length, so looping songs end.
// Returns the length including the fade in milliseconds, or -1 on error.
EMSCRIPTEN_KEEPALIVE
int romm_gme_start( Music_Emu* emu, int track )
{
	if ( gme_start_track( emu, track ) )
		return -1;

	gme_info_t* info = nullptr;
	if ( gme_track_info( emu, &info, track ) )
		return -1;

	int const length = info->play_length;
	int const fade = info->fade_length > 0 ? info->fade_length : DEFAULT_FADE_MSECS;
	gme_free_info( info );

	gme_set_fade_msecs( emu, length, fade );
	return length + fade;
}

}
