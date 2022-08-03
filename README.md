# oof2

Mangle "blocked RAM" (0x210xxxxx) payloads, so the RP2 bootrom can load it.

Normally the blocked_ram CMake option produces binaries at 0x200xxxxx which is whitelisted in the RP2 bootrom, but if you're already pushing the limits of the hardware, and have optimized RAM bank usage to the extreme, striped RAM just doesn't cut it.
Since there is the mistake in bootrom code not whitelisting unstriped RAM mirror, the binary has to be mangled before it can be loaded.
Another unfortunate side-effect is that the code can't be executed directly, but a stub has to be injected into BANK4 or BANK5, which is actually just a copypaste of the entrypoint code. This is required, because the code expects execution to begin at 0x21000000 |1, whereas due to the mangling, code starts at 0x20000000 |1 instead, which is bad.

## Repo contents

- `elf2uf2.diff` - you must sadly apply this patch to `${PICO_SDK_PATH}/tools/elf2uf2/main.cpp` to force it to generate a valid .uf2, but one which the bootrom doesn't accept
- `bootcode.S` - use ARMIPS to assemble the injected payload launcher
    - `stage1.bin` and `stage2.bin` - preassembled stage payloads, so ARMIPS doesn't need to be acquired for this purpose only, but they can be reassembled just fine by running `armips bootcode.S`
- `link.ld` - copy `link.ld` into your project folder, and put `pico_set_linker_script(programname ${CMAKE_CURRENT_LIST_DIR}/link.ld)` in your `CMakeLists.txt`
- `oof2.py` - main mangler script; run it to see how to use it

## Usage

Prerequisites:
- patch elf2uf2 with `elf2uf2.diff`
- assemble patched bootcode with `armips bootcode.S`
- setup project linker script to be `link.ld` from this repo

After every build:
- run `python3 programname.uf2 D:\\asd.uf2` where `programname.uf2` is the generated .uf2 you want to upload, and `D:\\` is where the pico bootrom shows up as an MSC USB device
    - alternatively just patch the .uf2 into the current folder, and deal with it later somehow else
