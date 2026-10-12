# litestream
Time Machine live music streaming for microcontroller

## Plex Album Browser

The bare-bones `plexalbums` app shares Plex accounts and connection logic with
`livemusic`, but selects its own music libraries through its Plex configuration
menu. Here, "collection" means those selected music libraries, not a Plex
collection-tag filter. Album titles do not need dates.

Existing `livemusic` library selections are preserved. `plexalbums` starts with
none selected: add libraries from its **Plex > Add Library** menu. Selecting or
removing a library affects only the current app. Accounts are shared, so deleting
an account removes its library selections from both apps.

- Left knob: album artists, alphabetically (case-insensitive).
- The Artist page starts with up to 15 recently played artists, newest first,
  followed by the complete alphabetical list (including those recent artists).
  History is saved in the `plexalbums` state and updated when playback starts.
- Center knob: that artist's albums, oldest release first using Plex release
	date/year metadata. Unknown dates sort last; ties sort by title.
- Right knob: playable tracks, in disc/track order.
- Turning Artist or Album immediately changes the next knob's choices and resets
	the child selections. Browsing does not interrupt current playback.
- Select on Artist opens Albums; Select on Album plays from the beginning;
	Select on Track plays from that track through the rest of the album.
- Play/Pause controls the current playlist. Stop, Rewind, and Fast Forward use
	the existing audio player. Left knob press hides the screen; Center/Right
	knob presses open Album/Track. Rewind/Fast Forward adjust volume when the
	screen is hidden. Hold Power to return to configuration.

In Dev Mode, use **Choose App > plexalbums**, or run `import plexalbums;
plexalbums.run()` on the device. Normal non-dev startup remains `livemusic`.
The app remembers artist, album, and volume separately from the other apps.

When available, Plex cover art is resized and downloaded before playback starts.
After 30 seconds showing the playing tracks, the screen switches to the cover.
Turning a knob returns to browsing. Missing artwork, download errors, or firmware
without JPEG display support leave the track list visible. Only the current
cover is stored, in `/config/plexalbums_cover.jpg`.

## History
This project is a continuation of the deadstream project (https://github.com/eichblatt/deadstream)
but designed to work on a microcontroller like the ESP32.
