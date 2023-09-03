# Decoder Chip VS1053

## Notes from Mike

- I think you will still need at least an input ring buffer to guard against WiFi glitches/slowness.
- It runs from SPI. Same as the screen.
- So basically the same code but instead of calling the single line in the current player that calls the C decode function, you would send it to SPI
- Try and use the same pins as we are using for the DAC. I think you can assign SPI to any pins
- I hope that gapless works as we have no opportunity to buffer the output