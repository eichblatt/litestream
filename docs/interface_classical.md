# Command Interface Description -- Classical Mode

## Intro

This document describes the behavior of the Time Machine in the Classical music mode. The device is intended to be intuitive, so these directions should be unnecessary.

Since there is no danger in pressing any button or turning any knob, the user should feel free to explore the device ***before*** referring to these directions. Also, the user interface is designed so that everything that is absolutely necessary is **directly accessible** by turning the knobs and pressing the buttons. As far as menus and long-pressed buttons are available, they are *strictly for convenience*.

## Reference Tables

This section contains a high-level description of the responses to button presses and knob turning.

### Buttons

| Button         | Short Press | Long Press | Notes |
|----------------|-------------|------------|-------|
| **Select**     | Select and Play keyed work | Show all performances of keyed work | When on composer or genre screen, plays composer, genre radio |
| **Play/Pause** | Toggle play/pause | - | "Pause/Play" would be a better name for this button |
| **Rewind**     | Previous track | - | Lower the Volume when screen is off |
| **FFwd**       | Next track | - | Increase the volume control when screen is off |
| **Stop**       | Stop playback | - | Returns playback to beginning of the selected work |
| **Power**      | Pause music and Toggle screen | Configure menu | Rotate any knob or press play to re-illuminate the screen |
| **Left Button**  | Darken the screen | - | Rotate any knob or press play to re-illuminate the screen |
| **Center Button**| Go to *Radio* "composer" | - | Rotate center knob to enter **Radio** menu |
| **Right Button** | Go to *Favorites* "composer" | - | Rotate center knob to enter **Favorites** menu |

### Knobs

| Knob              | Knob Soft Label   | Function      | Notes |
|-------------------|-------------------|---------------|-------|
| **Left Knob**     | **Composer**      | Tee up a composer for selection | Teeing up does *not* select the composer |
|                   | **Jump 100**      | Move the cursor ahead/back in the current menu by 100 items | Wrap around in list if needed |
| **Center Knob**   | **Genre**         | Tee up a genre | Teeing up does *not* select the genre |
|                   | **Jump 10**       | Move the cursor ahead/back in the current menu by 10 items | Wrap around the list if needed |
| **Right Knob**    | **Work**          | Tee up a work | Teeing up does *not* select the work |
|                   | **Next/Prev**     | Move the cursor to the next/previous item in the current menu | Wrap around the list if needed |

## The Buttons

This section describes the detailed response of button presses, depending on the context when they are pressed. See the [Knobs section](#the-knobs) below for details about *rotating* the knobs.

### Select

The Select button selects the current highlighted option or selection.

**Short Press**:

- When a composer is teed up: Plays a radio based on the composer
- When a genre is teed up: Plays a radio based on the composer and genre
- When a work is teed up: Plays the teed up work with the default performance
- During radio selection: Starts playing the selected radio station

**Long Press**:

- When a work is teed up: Opens a menu to choose between different performances of the work
- When in tracklist view: Allows selection of an alternative performance of the current work

### Play/Pause

The Play/Pause button controls playback without changing the current selection.

- During playback: Pauses the currently playing music
- When paused: Resumes playback from the pause point
- When stopped: Starts playback of the currently selected work from the beginning
- When a work is teed up and nothing is selected: Plays the teed up work with the default performance

### Rewind

The Rewind button navigates backward in the current tracklist or controls volume when the screen is off.

- During playback: Jumps to the previous track in the current work
- At the beginning of a track: Returns to the beginning of the previous track
- When playing and screen is off (see [Left button](#left-button)): Decreases the volume

### FFwd

The Fast Forward button navigates forward in the current tracklist or controls volume when the screen is off.

- During playback: Jumps to the next track in the current work
- When at the last track: Completes playback
- When playing and screen is off (see [Left button](#left-button)): Increases the volume

### Stop

The Stop button halts all playback.

- During playback: Stops the music and returns to the beginning of the current work
- When stopped: Does nothing

### Power (Menu)

The Power button controls the screen display and provides access to configuration options.

**Short Press**:

- When screen is on: Turns off the screen and pauses music
- When screen is off: Turns the screen back on

**Long Press**:

- Opens the configuration menu with system settings options
- Provides access to software updates, network settings, authentication, and device testing

### Left Button

The Left button provides a shortcut to darken the screen. See the [Knobs section](#the-knobs) below for details about *rotating* the knobs.

- In any context: Immediately darkens the screen

### Center Button

The Center button provides a shortcut to the Radio feature. See the [Knobs section](#the-knobs) below for details about *rotating* the knobs.

- Jumps directly to the Radio menu with the cursor on the composer selection
- Equivalent to rotating the Left knob to the "Radio" option at the top of the composer list

### Right Button

The Right button provides a shortcut to the Favorites feature. See the [Knobs section](#the-knobs) below for details about *rotating* the knobs.

- Jumps directly to the Favories menu with the cursor on the composer selection
- Equivalent to rotating the Left knob to the "Favorites" option near the top of the composer list

## The Knobs

This section describes the detailed response of *rotating* the knobs, depending on the context. See the [Buttons section](#the-buttons) above for details about *pressing* the knobs.

### Left Knob

The Left knob controls which composer or group of 100 items are selected, depending on context.

When in default context, rotating the Left knob scrolls through available composers. The composer name will be displayed but not selected until the [Select](#select) button is pressed.

In menus with many items, the Left knob moves the cursor forward or backward by 100 items. This allows quick navigation through long lists.

Note: In all contexts, rotation of the Left knob will wake up the screen if it was previously darkened.

### Center Knob

The Center knob controls which genre or group of 10 items are selected, depending on context.

When in default context, rotating the Center knob scrolls through available genres relevant to the teed-up composer. The genre name will be displayed but not selected until the [Select](#select) button is pressed.

In menus with many items, the Center knob moves the cursor forward or backward by 10 items. This provides medium-speed navigation through long lists.

Note: In all contexts, rotation of the Center knob will wake up the screen if it was previously darkened.

### Right Knob

The Right knob controls which work or individual item is selected, depending on context.

When in default context, rotating the Right knob scrolls through available works relevant to the teed-up composer and genre. The work title will be displayed but not selected until the [Select](#select), or [Play/Pause](#playpause) button is pressed.

In menus with many items, the Right knob moves the cursor forward or backward by 1 item. This provides fine-grained navigation through lists.

In Radio mode, the Right knob allows you to navigate through different radio station options or playlists.

In the Favorites menu, rotating the Right knob scrolls through your saved favorite works.

Note: In all contexts, rotation of the Right knob will wake up the screen if it was previously darkened.

## Contexts

The Time Machine classical music interface operates within several distinct contexts that determine how user inputs are interpreted. Each context provides a different view and focus, enabling users to navigate through the classical music library efficiently.

### Main Navigation Contexts

#### 1. **Composer Context**

- **Active when:** The user is browsing or has teed up a composer
- **Display:** Shows a scrollable list of composers
- **Control focus:** [Left knob](#left-knob) navigates between composers
- **Actions available:** Turn [Center Knob](#center-knob) to view the teed up composer's genres, or press [Select](#select) to play composer radio

#### 2. **Genre Context**

- **Active when:** A composer has been teed up and user is browsing genres
- **Display:** Shows available genres for the teed up composer
- **Control focus:** [Center knob](#center-knob) navigates between genres
- **Actions available:** Turn [Right Knob](#right-knob) to view works within teed up composer and genre, or press [Select](#select) to play genre-specific radio

#### 3. **Work Context**

- **Active when:** A composer and genre have been teed up
- **Display:** Shows available works within the teed up genre
- **Control focus:** [Right knob](#right-knob) navigates between works
- **Actions available:** press [Select](#select) to play the default performance of the work. Long-press [Select](#select) to display all performances of the work (see [Performance Selection Context](#4-performance-selection-context))

### Playback Contexts

#### 4. **Performance Selection Context**

- **Active when:** User long-presses [Select](#select) on a teed up work
- **Display:** Shows alternative performances of the selected work
- **Control focus:** Left, Center, and Right knobs navigate between performances, at different granularities.
- **Actions available:** Press [Select](#select) to play a specific performance of the work

#### 5. **Tracklist Context**

- **Active when:** A work is playing or paused
- **Display:** Shows the tracks of the current performance
- **Control focus:** None
- **Actions available:** Press [Play/Pause](#playpause) to pause, [Ffwd](#ffwd) or [Rewind](#rewind) to advance/reverse tracks.

### Special Contexts

#### 6. **Radio Context**

- **Active when:** Accessed via Center button or composer navigation, then turn [Center Knob](#center-knob).
- **Display:** Shows radio station options
- **Control focus:** [Right knob](#right-knob) navigates between radio options
- **Actions available:** Select a radio station to begin playback

#### 7. **Favorites Context**

- **Active when:** Accessed via [Right button](#right-button) or composer navigation, then turn [Center Knob](#center-knob).
- **Display:** Shows favorite works
- **Control focus:** [Right knob](#right-knob) navigates between saved favorites
- **Actions available:** Select a favorite to play

#### 8. **Configuration Context**

- **Active when:** User long-presses the [Power button](#power-menu)
- **Display:** Shows system settings and options
- **Control focus:** Knobs navigate through configuration options
- **Actions available:** Update software, configure network, test device

#### 9. **Screen Off Context**

- **Active when:** Screen is darkened via [Power](#power-menu) or [Left button](#left-button)
- **Display:** Screen is off, but device remains operational
- **Control focus:** When playing: Volume control via [Rewind](#rewind)/[FFwd](#ffwd) buttons
- **Actions available:** Limited to volume adjustment and screen wake-up

These contexts determine how the interface responds to user inputs, creating a coherent navigation system through the classical music library that adapts based on the current state and user focus.
