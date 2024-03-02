# Using mpremote

## Reference

via pip, see <https://docs.micropython.org/en/latest/reference/mpremote.html>

## Commands I Find Useful

### Mounting the linux filesystem

Mount the current directory (on my linux machine) to the device.

```{}
:  ~/projects/litestream ; mpremote mount timemachine  
```

This will put me in the repl with the code on my local machine mounted.
From the repl, I can import code and run it. 

To re-import the code, I think I have to do a soft reset (Ctrl-A Ctrl-D), then Ctrl-B to get back to the normal repl.


### Tell the machine to automatically start playing

`mpremote autoboot`


