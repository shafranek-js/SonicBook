import logging
import os
import subprocess

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])
GAMMA_BRIGHTNESS_LEVEL = 100


class BrightnessRequest(BaseModel):
    level: int


def get_system_idle_seconds() -> float | None:
    if os.name != "nt":
        return None
    try:
        import ctypes

        class LastInputInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("dwTime", ctypes.c_uint),
            ]

        last_input = LastInputInfo()
        last_input.cbSize = ctypes.sizeof(last_input)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input)):
            return None

        current_tick = ctypes.windll.kernel32.GetTickCount()
        elapsed_ms = (current_tick - last_input.dwTime) & 0xFFFFFFFF
        return max(0.0, elapsed_ms / 1000.0)
    except Exception:
        logger.debug("Failed to read system idle time", exc_info=True)
        return None


def run_powershell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def get_screen_brightness() -> int | None:
    if os.name != "nt":
        return None
    global GAMMA_BRIGHTNESS_LEVEL
    try:
        result = run_powershell(
            "$b = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop | "
            "Select-Object -First 1 -ExpandProperty CurrentBrightness; "
            "if ($null -eq $b) { exit 2 }; [int]$b"
        )
        if result.returncode != 0:
            return GAMMA_BRIGHTNESS_LEVEL if is_gamma_brightness_supported() else None
        return max(0, min(100, int(result.stdout.strip().splitlines()[-1])))
    except Exception:
        logger.debug("Failed to read screen brightness", exc_info=True)
        return GAMMA_BRIGHTNESS_LEVEL if is_gamma_brightness_supported() else None


def set_screen_brightness(level: int) -> int | None:
    if os.name != "nt":
        return None
    global GAMMA_BRIGHTNESS_LEVEL
    safe_level = max(0, min(100, int(level)))
    try:
        result = run_powershell(
            f"$level = {safe_level}; "
            "$methods = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop; "
            "if (!$methods) { exit 2 }; "
            "$methods | ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName WmiSetBrightness "
            "-Arguments @{Timeout=1;Brightness=$level} | Out-Null }; "
            "$level"
        )
        if result.returncode != 0:
            return set_gamma_brightness(safe_level)
        return safe_level
    except Exception:
        logger.debug("Failed to set screen brightness", exc_info=True)
        return set_gamma_brightness(safe_level)


def build_gamma_ramp(level: int):
    import ctypes

    safe_level = max(0, min(100, int(level)))
    ramp_type = ctypes.c_ushort * (256 * 3)
    ramp = ramp_type()
    for channel in range(3):
        offset = channel * 256
        for index in range(256):
            ramp[offset + index] = min(65535, int(index * 257 * safe_level / 100))
    return ramp


def is_gamma_brightness_supported() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        hdc = ctypes.windll.user32.GetDC(None)
        if not hdc:
            return False
        try:
            ramp_type = ctypes.c_ushort * (256 * 3)
            ramp = ramp_type()
            return bool(ctypes.windll.gdi32.GetDeviceGammaRamp(hdc, ctypes.byref(ramp)))
        finally:
            ctypes.windll.user32.ReleaseDC(None, hdc)
    except Exception:
        logger.debug("Failed to probe gamma brightness support", exc_info=True)
        return False


def set_gamma_brightness(level: int) -> int | None:
    if os.name != "nt":
        return None
    global GAMMA_BRIGHTNESS_LEVEL
    safe_level = max(0, min(100, int(level)))
    try:
        import ctypes

        hdc = ctypes.windll.user32.GetDC(None)
        if not hdc:
            return None
        try:
            ramp = build_gamma_ramp(safe_level)
            if not ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp)):
                return None
        finally:
            ctypes.windll.user32.ReleaseDC(None, hdc)
        GAMMA_BRIGHTNESS_LEVEL = safe_level
        return safe_level
    except Exception:
        logger.debug("Failed to set gamma brightness", exc_info=True)
        return None


@router.get("/idle")
async def system_idle():
    idle_seconds = get_system_idle_seconds()
    return {
        "supported": idle_seconds is not None,
        "idle_seconds": idle_seconds,
    }


@router.get("/brightness")
async def system_brightness():
    level = get_screen_brightness()
    return {
        "supported": level is not None,
        "level": level,
    }


@router.post("/brightness")
async def update_system_brightness(request: BrightnessRequest):
    level = set_screen_brightness(request.level)
    return {
        "supported": level is not None,
        "level": level,
    }
