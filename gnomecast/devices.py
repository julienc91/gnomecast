from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Device:
    manufacturer: str
    model_name: str
    h265: bool
    ac3: bool


_devices = {
    Device(
        manufacturer="Unknown manufacturer",
        model_name="Chromecast",
        h265=False,
        ac3=False,
    ),
    Device(
        manufacturer="Unknown manufacturer",
        model_name="Chromecast Ultra",
        h265=True,
        ac3=True,
    ),
    Device(
        manufacturer="Unknown manufacturer",
        model_name="Google Home Mini",
        h265=False,
        ac3=False,
    ),
    Device(
        manufacturer="VIZIO",
        model_name="P75-F1",
        h265=True,
        ac3=True,
    ),
}


def get_device(manufacturer: str, model_name: str) -> Device:
    """
    Get a device by its manufacturer and model name.
    """
    for device in _devices:
        if device.manufacturer == manufacturer and device.model_name == model_name:
            return device
    return Device(
        manufacturer="Unknown manufacturer", model_name="Default", h265=False, ac3=False
    )
