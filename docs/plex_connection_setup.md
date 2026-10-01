# Plex Connection Setup for Live Music

This guide explains how to connect the Time Machine to Plex and how Plex albums must be formatted so they are recognized as live music shows.

## What This Feature Reads from Plex

The Time Machine only scans Plex libraries that are:

- Added through the Plex setup menu in the device UI
- Music libraries (Plex section type `artist`)

## Connect the Device to Plex

1. Connect the device to Wi-Fi.
2. Open the configuration menu (long-press the Power button).
3. Open Plex setup.
4. Choose Add Library.
5. If Add Server appears, choose Add Account if needed, enter your Plex username/password, and then choose your server.
6. Choose the music library section you want to use.
7. Repeat Add Library if you want additional Plex libraries.
8. Choose Continue to save and exit.

Notes:

- You can review current selections with Show Libraries.
- You can remove a library with Delete Library.
- The Plex account can be removed with Delete Account.

## Required Album Format for Live Music Detection

An album is treated as a live show only if its album title contains a valid ISO date.

Required date format:

- `YYYY-MM-DD` (preferred)
- `YYYY_MM_DD` (also accepted)

The date can appear at the beginning or later in the title, but it must be a valid calendar date string of length 10.

### Accepted title examples

- `1977-05-08 Barton Hall, Ithaca, NY`
- `1977_05_08 - Cornell University`
- `Grateful Dead 1977-05-08 Barton Hall`
- `1989-10-16 Meadowlands (SBD)`

### Not accepted title examples

- `5-8-77 Barton Hall` (not ISO)
- `1977/05/08 Barton Hall` (slashes are not accepted)
- `Cornell University Show` (no date)

## How Artist/Collection Name Is Chosen

When assigning a Plex show to a collection (band/artist), album-level artist fields are preferred in this order:

1. `originalTitle`
2. `albumArtist`
3. `grandparentTitle`
4. `parentTitle`
5. `artist` (fallback)

Recommendation: set Album Artist in Plex metadata consistently for each show.

## Supported Audio Types

Playable tracks are discovered from:

- MP3 (`.mp3`)
- OGG (`.ogg`)
- FLAC (`.flac`, streamed via Plex transcode URL) -- flac is discouraged, transcoding leads to problems.

## Practical Library Hygiene Tips

- Use one show per album.
- Ensure each show album title includes one ISO date.
- Keep album artist consistent across all tracks in a show.
- Avoid duplicate albums with the same date/title unless you intentionally want multiple tape choices.

## Troubleshooting

If no shows appear:

1. Confirm the selected Plex library is a Music library.
2. Confirm album titles include `YYYY-MM-DD` or `YYYY_MM_DD`.
3. Confirm the device can still reach Plex over the network.
4. Re-open Plex setup and verify the selected server/library entries.
5. If credentials changed, remove and re-add the Plex account.

