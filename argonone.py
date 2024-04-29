#!/usr/bin/python3
from os import environ, popen, path
from smbus import SMBus
from RPi.GPIO import RPI_INFO
from time import sleep
from threading import Thread, Event
from tomllib import load as load_toml
from signal import signal, SIGINT, SIGTERM

# accepts config filename in CONFIG_FILE env var
_DEFAULT_CONFIG_PATH = '/etc/default/argonone.toml'
_FAN_ADDR = 0x1a
_FAN_DUTY_CYCLE = 0x80


def get_cpu_temp() -> float:
    try:
        with open(file='/sys/class/thermal/thermal_zone0/temp', mode='r') as f:
            return float(int(f.readline())/1000)
    except OSError:
        return 0.0


def get_hdd_devs() -> list[str] | None:
    c = {"smartctl": "/usr/sbin/smartctl", "lsblk": "/usr/bin/lsblk", "grep": "/usr/bin/grep", "awk": "/usr/bin/awk"}
    for cmd in c.values():
        if not path.exists(cmd):
            return None
    cmd = f"{c['lsblk']}|{c['grep']} -e '^[sh]d.*0 disk'|{c['awk']} '{{print $1}}'"
    try:
        devs = popen(cmd).read().strip()
        return devs.split('\n') if devs else None
    except OSError:
        return None


def get_hdd_temp(devs: list[str]) -> float:
    temp = 0.0
    c = {"sctl": "/usr/sbin/smartctl", "grep": "/usr/bin/grep", "awk": "/usr/bin/awk"}
    try:
        for dev in devs:
            val = float(
                popen(f"{c['sctl']} -d sat -A /dev/{dev}|{c['grep']} Temperature_Celsius|{c['awk']} '{{print $10}}'")
                .read().strip())
            temp = max(val, temp)
    except OSError:
        temp = 0.0
    return temp


def init_bus() -> SMBus | None:
    _SMBUS_DEV = 1 if RPI_INFO['P1_REVISION'] > 1 else 0
    try:
        return SMBus(_SMBUS_DEV)
    except Exception:
        print("Cannot create SMBus instance")
        return None


def check_control_registers_support(bus: SMBus) -> bool:
    if bus is None:
        return False
    try:
        old = bus.read_byte_data(_FAN_ADDR, _FAN_DUTY_CYCLE)
        new = old + 1 if old < 100 else 98
        bus.write_byte_data(_FAN_ADDR, _FAN_DUTY_CYCLE, new)
        sleep(1)
        new = bus.read_byte_data(_FAN_ADDR, _FAN_DUTY_CYCLE)
        return new != old
    except Exception:
        return False


def set_fan_speed(bus: SMBus, speed: int, registers_support=False) -> None:
    if bus is None:
        return
    _speed = speed if speed in range(0, 101) else 100 if speed > 100 else 0
    if registers_support:
        bus.write_byte_data(_FAN_ADDR, _FAN_DUTY_CYCLE, _speed)
    else:
        bus.write_byte(_FAN_ADDR, _speed)
    sleep(1)


def turn_off_fan(bus: SMBus, registers_support: bool) -> None:
    set_fan_speed(bus, 0, registers_support)


def control_fan(bus: SMBus, config: dict[str, dict], stop: Event) -> None:
    registers_support = check_control_registers_support(bus)
    hdd_devs = get_hdd_devs()
    cpu_temp_config, hdd_temp_config = get_temp_values(config)
    cpu_enabled, hdd_enabled = (config['cpu_temp']['enabled'],
                                config['hdd_temp']['enabled'] if hdd_devs else False)
    prev_speed = -1
    while not stop.is_set():
        cpu_new_speed = 0
        hdd_new_speed = 0
        if cpu_enabled:
            cpu_temp = get_cpu_temp()
            for t, s in cpu_temp_config.items():
                if cpu_temp >= t:
                    cpu_new_speed = s
                    break
        if hdd_enabled:
            hdd_temp = get_hdd_temp(hdd_devs)
            for t, s in hdd_temp_config.items():
                if hdd_temp >= t:
                    hdd_new_speed = s
                    break
        new_speed = max(cpu_new_speed, hdd_new_speed)
        if prev_speed >= new_speed:
            stop.wait(30)
        if prev_speed == new_speed:
            continue
        prev_speed = new_speed
        set_fan_speed(bus, 100, registers_support)
        set_fan_speed(bus, new_speed, registers_support)
        stop.wait(30)
    turn_off_fan(bus, registers_support)
    return


def load_config() -> dict[str, dict] | None:
    config_file = environ.get('CONFIG_FILE', _DEFAULT_CONFIG_PATH)
    try:
        with open(file=config_file, mode='rb') as f:
            config = load_toml(f)
    except OSError:
        return None
    if (config.get('cpu_temp') is None
            or not config['cpu_temp'].get('enabled')
            or not isinstance(config['cpu_temp'].get('fan_speed'), dict)):
        config['cpu_temp'] = {'enabled': False, 'fan_speed': {}}
    if (config.get('hdd_temp') is None
            or not config['hdd_temp'].get('enabled')
            or not isinstance(config['hdd_temp'].get('fan_speed'), dict)):
        config['hdd_temp'] = {'enabled': False, 'fan_speed': {}}
    return config


def get_temp_values(config: dict[str, dict]) -> (dict[int, int], dict[int, int]):
    return (
        dict(sorted([(int(k), int(v)) for k, v in config['cpu_temp']['fan_speed'].items()], reverse=True)),
        dict(sorted([(int(k), int(v)) for k, v in config['hdd_temp']['fan_speed'].items()], reverse=True))
    )


if __name__ == '__main__':
    stop_event = Event()
    signal(SIGTERM, lambda signum, frame: stop_event.set())
    signal(SIGINT, lambda signum, frame: stop_event.set())
    cfg = load_config()
    if cfg is None:
        raise ValueError("Cannot read config file")
    smbus = init_bus()
    control_fan_thread = Thread(name='fan_control', daemon=True, target=control_fan, args=(smbus, cfg, stop_event))
    control_fan_thread.start()
    stop_event.wait()
    control_fan_thread.join(5)
    exit(0)
