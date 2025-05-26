# Command Interface Description -- Live Music Mode

## Intro

This document describes the behavior of the Time Machine in the Live Music mode. The device is intended to be intuitive, so these directions should be unnecessary.

Since there is no danger in pressing any button or turning any knob, the user should feel free to ***explore*** the device ***before*** referring to these directions. The basic navigation is all **directly accessible** by turning the three knobs and pressing the six simple buttons. The menus and long-pressed buttons are strictly for **convenience** or going **deeper** into the archive.

## Reference Tables

This section contains a high-level description of the responses to button presses and knob turning.

### Buttons

| Button         | Short Press | Long Press | Notes |
|----------------|-------------|------------|-------|
| [**Select**](#select) | Play show on selected date | Choose specific tape | Shows venue/city and starts playback |
| [**Play/Pause**](#playpause) | Toggle play/pause | - | "Pause/Play" would be a better name for this button |
| [**Rewind**](#rewind)     | Previous track | - | Lower the Volume when screen is off |
| [**FFwd**](#ffwd)   | Next track | - | Increase the volume control when screen is off |
| [**Stop**](#stop)   | Stop playback | - | Returns playback to beginning of the selected show |
| [**Power**](#power-menu)  | Pause music and Toggle screen | Configure menu | Rotate any knob or press play to re-illuminate the screen |

### Knobs

| Knob              | Function      | Notes |
|-------------------|---------------|-------|
| [**Left Knob (Year)**](#left-knob-year) | Select year | Changes the year component of the date |
| [**Center Knob (Month)**](#center-knob-month) | Select month | Changes the month component of the date |
| [**Right Knob (Day)**](#right-knob-day) | Select day | Changes the day component of the date |

## The Buttons

This section describes the detailed response of button presses, depending on the context when they are pressed.

### Select

The Select button selects the current highlighted date and starts playback.

**Short Press**:

- When a date is selected: Plays the first available show on that date
- When already playing a show: Displays the tape ID in the venue area

**Long Press**:

- Opens the tape selection menu for the current date
- Allows choosing between multiple shows or tape sources if available for the date

### Play/Pause

The Play/Pause button controls playback without changing the current selection.

- During playback: Pauses the currently playing music
- When paused: Resumes playback from the pause point
- When stopped: Starts playback of the currently selected show from the beginning

### Rewind

The Rewind button navigates backward in the current tracklist or controls volume when the screen is off.

- During playback: Jumps to the previous track in the current show
- At the beginning of a track: Returns to the beginning of the previous track
- When playing and screen is off: Decreases the volume

### FFwd

The Fast Forward button navigates forward in the current tracklist or controls volume when the screen is off.

- During playback: Jumps to the next track in the current show
- When at the last track: Completes playback
- When playing and screen is off: Increases the volume

### Stop

The Stop button halts all playback.

- During playback: Stops the music and returns to the beginning of the current show
- When stopped: Does nothing

### Power (Menu)

The Power button controls the screen display and provides access to configuration options.

**Short Press**:

- When screen is on: Turns off the screen and pauses music
- When screen is off: Turns the screen back on

**Long Press**:

- Opens the configuration menu with system settings options
- Provides access to software updates, network settings, authentication, and device testing

### Year Button (Left Knob Button)

Today in History. Stages today's date for the currently displayed year.

### Month Button (Center Knob Button)

Turns off the screen.

### Day Button (Right Knob Button)

Jumps to the next available show. Generally, this will be on a different date. In the case where there are multiple bands loaded, and there is more than one show on the same date, pressing hte Month button will take you to the next show on that date. 

## The Knobs

This section describes how the knobs work to navigate through the archive of live shows.

### Left Knob (Year)

The Left knob controls which year is selected for browsing shows.

- Rotating the knob changes the year component of the date shown at the top of the screen
- Available years are based on the shows in the archive
- When a year with no shows is selected, the display will automatically jump to the nearest date with available content

### Center Knob (Month)

The Center knob controls which month is selected for browsing shows.

- Rotating the knob changes the month component of the date shown at the top of the screen (1-12)
- When rotating to a new month, the display updates to show availability within that month

### Right Knob (Day)

The Right knob controls which day is selected for browsing shows.

- Rotating the knob changes the day component of the date shown at the top of the screen (1-31)
- Days with available shows are highlighted or indicated visually
- When rotating to a day with no shows, the display will provide visual feedback

## Contexts

The Time Machine live music interface operates within several distinct contexts that determine how user inputs are interpreted.

### Main Navigation Contexts

#### 1. **Date Selection Context**

- **Active when:** The user is browsing through dates
- **Display:** Shows the currently selected date at the top of the screen
- **Control focus:** All three knobs adjust the date components
- **Actions available:** Press Select to play a show on the selected date

### Playback Contexts

#### 2. **Show Playback Context**

- **Active when:** A show is playing or paused
- **Display:** Shows venue/city, date, and collection information
- **Control focus:** Rewind/FFwd buttons navigate between tracks
- **Actions available:** Press Play/Pause to toggle playback state

#### 3. **Tape Selection Context**

- **Active when:** User long-presses Select on a date with multiple shows
- **Display:** Shows a list of available shows/tapes for the selected date
- **Control focus:** Knobs navigate through the list
- **Actions available:** Select a specific tape or collection to play

### Special Contexts

#### 4. **Configuration Context**

- **Active when:** User long-presses the Power button
- **Display:** Shows system settings and options
- **Control focus:** Knobs navigate through configuration options
- **Actions available:** Update software, configure network, test device

#### 5. **Screen Off Context**

- **Active when:** Screen is darkened via Power
- **Display:** Screen is off, but device remains operational
- **Control focus:** Volume control via Rewind/FFwd buttons
- **Actions available:** Limited to volume adjustment and screen wake-up

These contexts determine how the interface responds to user inputs, creating a coherent navigation system through the live music archive that adapts based on the current state and user focus.