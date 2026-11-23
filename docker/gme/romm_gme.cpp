// Entry points the soundtrack player's AudioWorklet calls on top of libgme's
// own C API, which returns its handles and track info through out-parameters.
#include <emscripten/emscripten.h>
#include <stdlib.h>
#include <string.h>

#include "gme/gme.h"

// Fade applied when the file doesn't specify one.
static int const DEFAULT_FADE_MSECS = 8000;

static char const GYM_TAG[] = "GYMX";
static long const GYM_HEADER_SIZE = 428;
// libgme reads a GYM frame until a zero command, so trailing zeros stop a
// truncated stream from reading past the buffer.
static long const GYM_PADDING = 4;

// Loads a GYM from a zero-padded copy. A headerless log gets a blank header,
// since libgme only counts frames for the length of a headered file.
static Music_Emu* open_gym( unsigned char const* data, long size, int sample_rate )
{
	bool const headerless = size < 4 || memcmp( data, GYM_TAG, 4 ) != 0;
	long const header = headerless ? GYM_HEADER_SIZE : 0;
	long const total = header + size + GYM_PADDING;
	unsigned char* copy = (unsigned char*) calloc( total, 1 );
	if ( !copy )
		return nullptr;
	if ( headerless )
		memcpy( copy, GYM_TAG, 4 );
	memcpy( copy + header, data, size );

	Music_Emu* emu = gme_new_emu( gme_gym_type, sample_rate );
	if ( emu && gme_load_data( emu, copy, total ) )
	{
		gme_delete( emu );
		emu = nullptr;
	}
	free( copy );
	return emu;
}

extern "C" {

EMSCRIPTEN_KEEPALIVE
Music_Emu* romm_gme_open( void const* data, long size, int sample_rate )
{
	unsigned char const* bytes = (unsigned char const*) data;
	if ( size >= 4 && memcmp( bytes, GYM_TAG, 4 ) == 0 )
		return open_gym( bytes, size, sample_rate );

	Music_Emu* emu = nullptr;
	if ( !gme_open_data( data, size, &emu, sample_rate ) )
		return emu;

	// A headerless GYM log has no magic, so it's taken, as libgme takes one,
	// when it starts with a valid command.
	if ( size > 0 && bytes[0] <= 3 )
		return open_gym( bytes, size, sample_rate );
	return nullptr;
}

// Starts the file's song with a fade-out at its resolved length, so looping
// songs end. Returns the length including the fade in milliseconds, or -1 on error.
EMSCRIPTEN_KEEPALIVE
int romm_gme_start( Music_Emu* emu )
{
	if ( gme_start_track( emu, 0 ) )
		return -1;

	gme_info_t* info = nullptr;
	if ( gme_track_info( emu, &info, 0 ) )
		return -1;

	int const length = info->play_length;
	int const fade = info->fade_length > 0 ? info->fade_length : DEFAULT_FADE_MSECS;
	gme_free_info( info );

	gme_set_fade_msecs( emu, length, fade );
	return length + fade;
}

}
