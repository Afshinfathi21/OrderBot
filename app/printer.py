import os
import win32print
import win32api
import win32con
import pywintypes

DM_ORIENTATION = 0x00000001
DM_PAPERSIZE = 0x00000002
DM_COPIES = 0x00000100
DM_COLOR = 0x00000800
DM_DUPLEX = 0x00001000


DMORIENT_PORTRAIT = 1
DMORIENT_LANDSCAPE = 2
DMCOLOR_MONOCHROME = 1
DMCOLOR_COLOR = 2
DMDUP_SIMPLEX = 1 # یک‌رو
DMDUP_HORIZONTAL = 2 # دورو - افقی
DMDUP_VERTICAL = 3 # دورو - عمودی

def get_printer_capabilities(printer_name: str) -> dict:

    capabilities = {
        'is_color': False,
        'supports_duplex': False,
        'paper_sizes': {},
        'orientations': []
    }
    try:
        h_printer = win32print.OpenPrinter(printer_name)

        dev_caps = win32print.DeviceCapabilities(printer_name, None, win32con.DC_COLOR, None)
        capabilities['is_color'] = bool(dev_caps & 1)

        dev_caps = win32print.DeviceCapabilities(printer_name, None, win32con.DC_DUPLEX, None)
        capabilities['supports_duplex'] = bool(dev_caps)

        win32print.ClosePrinter(h_printer)
        return capabilities
    except pywintypes.error as e:
        print(f"Error getting capabilities for '{printer_name}': {e}")

        return capabilities


def print_file_with_settings(file_path: str, printer_name: str, settings: dict):

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"فایل در مسیر {file_path} یافت نشد.")

    try:

        h_printer = win32print.OpenPrinter(printer_name)
        dev_mode_bytes = win32print.GetPrinter(h_printer, 2)["pDevMode"]
        dev_mode = pywintypes.DEVMODEType(dev_mode_bytes)

        if 'copies' in settings:
            dev_mode.Copies = int(settings['copies'])
            dev_mode.Fields |= DM_COPIES

        if settings.get('color') == 'ColorFull':
            dev_mode.Color = DMCOLOR_COLOR
        else:
            dev_mode.Color = DMCOLOR_MONOCHROME
        dev_mode.Fields |= DM_COLOR

        if settings.get('layout') == 'Landscape':
            dev_mode.Orientation = DMORIENT_LANDSCAPE
        else:
            dev_mode.Orientation = DMORIENT_PORTRAIT
        dev_mode.Fields |= DM_ORIENTATION


        if settings.get('sides') == 'Double-sided':
            dev_mode.Duplex = DMDUP_VERTICAL 
        else:
            dev_mode.Duplex = DMDUP_SIMPLEX
        dev_mode.Fields |= DM_DUPLEX

        new_dev_mode_bytes = dev_mode.tobytes()
        win32print.SetPrinter(h_printer, 2, {"pDevMode": new_dev_mode_bytes}, 0)


        win32api.ShellExecute(
            0,
            "printto",
            f'"{file_path}"',
            f'"{printer_name}"',
            ".",
            0
        )

        win32print.ClosePrinter(h_printer)
        print(f"فایل '{file_path}' با موفقیت به پرینتر '{printer_name}' ارسال شد.")

    except Exception as e:
        raise RuntimeError(f"خطا در فرآیند چاپ برای پرینتر '{printer_name}': {e}") from e

