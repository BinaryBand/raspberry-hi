# TODO

## Guard `make rclone mount` against missing mount point

Running `make rclone mount pcloud:Media /mnt/media` before `make site --tags jellyfin`
has been run will still fail because `/mnt/media` won't exist on the Pi yet.

Options to consider:

- **Makefile dependency**: add a `media-prereqs` target that runs
  `ansible-playbook site.yml --tags jellyfin` and make the `rclone` target depend on it,
  or at least print a clear error if the directory is absent.

- **SSH preflight check**: in the `rclone` Makefile target, SSH and test
  `[ -d /mnt/media ]` before forwarding the rclone command, exiting with a helpful
  message if the check fails.

Either approach prevents silent fusermount failures and guides the user to run
provisioning first.
