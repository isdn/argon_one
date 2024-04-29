#### Argon One fan control daemon


This is a rewritten version of the Argon One daemon.

Only the fan speed control feature was implemented.

Due to a hardware "bug" the fan speed control might not work. 
Please see [the following thread](https://forum.argon40.com/t/argon-one-v2-fan-speed-not-working/1575/4).  
I replaced the capacitor mentioned there (10uF -> 10nF).

##### Configuration

The default config file location is `/etc/default/argonone.toml`.

This location can be changed by the `CONFIG_FILE` environment variable.

##### Installation

Requirements:
- smartctl (smartmontools)
- lsblk
- awk

Also requires additional python libraries:
- smbus2
- RPi.GPIO
- toml

1. Download the `argonone.py` file and place it in `/usr/local/bin/`.
2. Run `chmod 755 /usr/local/bin/argonone.py`.
3. Download `argonone-example.toml`, move it to `/etc/default/argonone.toml`, and adjust the configuration options.
4. Set up the systemd unit.

##### Systemd unit

Please see [this unit file](argonone.service).

You can copy it to `/etc/systemd/system/` and adjust locations of the python3 binary and `argonone.py` if necessary.

Then execute the following as root:
```bash
systemctl daemon-reload
systemctl enable argonone.service
systemctl start argonone.service
```

##### References

- https://github.com/Argon40Tech/Argon-ONE-i2c-Codes
- https://github.com/Argon40Tech/Argon40case/tree/master/src
- https://forum.argon40.com/t/argon-one-v2-fan-speed-not-working/1575/4

