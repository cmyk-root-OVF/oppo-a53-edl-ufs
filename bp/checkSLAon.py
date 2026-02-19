"""
Project: Oppo A53 (CPH2127) SLA Research Tool
Description: Investigating Firehose protocol stability and Serial Link Authentication (SLA) 
             on Qualcomm SM4250 (Snapdragon 460).
Author: vfs19
Inspiration: B.Kerler's EDL Project
Note: This script targets the USBError(19) issue during the Firehose handshake phase.
"""

import usb.core
import usb.util
import time
import os

# Qualcomm HS-USB QDLoader 9008 Identifiers
VID = 0x05C6
PID = 0x9008

# Path to the Firehose Programmer (.elf)
# Ensure this path is correct for your environment
LOADER_PATH = '/home/vfs19/roota53/prog_firehose_ddr_res.elf'

def find_device():
    """Locate the Qualcomm 9008 device on the USB bus."""
    print("[*] Scanning for Qualcomm HS-USB QDLoader 9008...")
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        raise ValueError('[!] Device not found. Ensure the device is in EDL mode.')
    print(f"[+] Device detected at Bus {dev.bus} Address {dev.address}")
    return dev

def configure_usb(dev):
    """Configure USB endpoints for Firehose communication."""
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
        dev.set_configuration()
        print("[+] USB configuration established.")
    except usb.core.USBError as e:
        print(f"[!] Configuration error: {e}")
        raise

    cfg = dev.get_active_configuration()
    intf = cfg[(0,0)]

    # Endpoint detection for data transmission
    ep_out = usb.util.find_descriptor(
        intf, custom_match = \
        lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_OUT)

    ep_in = usb.util.find_descriptor(
        intf, custom_match = \
        lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_IN)

    if ep_out is None or ep_in is None:
        raise RuntimeError("[!] Could not find valid USB endpoints.")
        
    print("[+] Endpoints IN/OUT successfully mapped.")
    return ep_out, ep_in

def main():
    try:
        dev = find_device()
        ep_out, ep_in = configure_usb(dev)

        # === PHASE 1: SAHARA PROTOCOL / LOADER UPLOAD ===
        if not os.path.exists(LOADER_PATH):
            print(f"[!] Error: Programmer not found at {LOADER_PATH}")
            return

        print(f"[*] Uploading Firehose Programmer: {os.path.basename(LOADER_PATH)}")
        with open(LOADER_PATH, 'rb') as f:
            loader_data = f.read()
        
        # Injecting loader via Raw USB Write
        ep_out.write(loader_data)
        print(f"[+] Injected {len(loader_data)} bytes. Waiting for Firehose initialization...")
        
        # Buffer time for SoC to execute the loader in RAM
        time.sleep(2) 

        # === PHASE 2: FIREHOSE KEEP-ALIVE & SLA PROBING ===
        # The 'NOP' command is used to test connectivity without triggering data read/write.
        # Most Oppo devices with SLA will disconnect here if the session is not authenticated.
        
        nop_command = b'<?xml version="1.0" ?><data><nop /></data>\x00'
        print("[*] Starting NOP flood to probe SLA/Watchdog behavior...")
        
        count = 0
        while True:
            try:
                print(f"[*] Sending Keep-Alive packet #{count+1}...")
                ep_out.write(nop_command)
                
                # Reading device response
                response = ep_in.read(1024, timeout=1000)
                decoded_res = response.decode('utf-8', errors='ignore')
                print(f"[+] Device Response: {decoded_res}")

                count += 1
                time.sleep(0.5) 

            except usb.core.USBError as e:
                print(f"\n[!] Connection dropped: {e}")
                if "No such device" in str(e):
                    print("[!] Result: SLA Authentication likely active.")
                    print("[!] Analysis: Connection terminated by SoC after failing to receive Auth Token.")
                break

    except KeyboardInterrupt:
        print("\n[*] Research interrupted by user.")
    except Exception as e:
        print(f"[!] Fatal Error: {e}")

if __name__ == '__main__':
    main()