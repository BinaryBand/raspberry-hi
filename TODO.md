# TODO

## Guard against missing mount point

Running `make mount pcloud:Media /mnt/media` before `make site`
has been run will still fail because `/mnt/media` won't exist on the Pi yet.

Options to consider:

...
