#!/usr/bin/python3

import sys
import struct
from array import array
from collections import namedtuple
from pathlib import Path

UF2_MAGIC0 = 0x0A324655
UF2_MAGIC1 = 0x9E5D5157
UF2_MAGIC2 = 0x0AB16F30

NOOK_ADDR = 0x20040800

def usage():
    sys.stderr.write('Usage: %s <infile> <outfile>\n' % (sys.argv[0]))
    return 1

def die(msg, *fmt):
    sys.stderr.write('Error: %s\n' % ((msg % fmt)))
    return 1

def warn(msg, *fmt):
    sys.stderr.write('Warning: %s\n' % ((msg % fmt)))

def block2unblock(addr):
    return 0x20000000 + ((((addr & 0xFFFF) >> 2) << 4)) | (((addr >> 16) & 3) << 2) | (addr & 3)

def main():
    argv = sys.argv
    argc = len(argv)
    
    if argc < 3:
        return usage()
    
    patchjump = None
    patchnook = None
    
    loc0 = Path(argv[0]) / '..'
    loc1 = loc0 / 'stage1.bin'
    loc2 = loc0 / 'stage2.bin'
    
    with open(loc1, 'rb') as fi:
        tst = fi.read(8)
        assert(len(tst) == 4), "Invalid stage1"
        patchjump = struct.unpack('<I', tst)[0]
    
    with open(loc2, 'rb') as fi:
        tst = fi.read()
        assert(len(tst) <= 0x100), "Stage2 too big"
        if len(tst) < 0x100:
            tst = tst + (b'\x00' * (0x100 - len(tst)))
        
        patchnook = tst
    
    ufstruct = struct.Struct('< 8I 256s 220x 1I')
    assert(ufstruct.size == 512), "Bad struct def"
    uftuple = namedtuple('UF2Struct', 'magic0, magic1, flags, dst, len, iBlock, nBlocks, dummy, buf, magic2')
    
    
    ramunstriped = array('I', [0] * (0x40000 >> 2))
    ramstriped = array('I', [0] * (0x40000 >> 2))
    ramused = array('B', [0] * (0x40000 >> (8 + 2)))
    misc = []
    bootable = False
    serial = None
    
    with open(argv[1], 'rb') as f:
        blocki = 0
        blockn = None
        uf = None
        
        while True:
            buf = f.read(512)
            if not buf:
                assert(blocki == uf.nBlocks), "Missing blocks"
                break
            
            assert(len(buf) == 512), "Bad input file"
            
            uf = uftuple(*ufstruct.unpack_from(buf, 0))
            
            if uf.magic0 != UF2_MAGIC0 or uf.magic1 != UF2_MAGIC1 or uf.magic2 != UF2_MAGIC2:
                warn("%8X: Invalid UF2 magic, skipping", blocki)
                blocki += 1
                continue
            
            if blockn == None:
                blockn = uf.nBlocks
                serial = uf.dummy
            else:
                assert(uf.nBlocks == blockn), "Total block mismatch"
            
            assert(uf.iBlock == blocki), "Invalid or non-sequential block indexing"
            assert(uf.iBlock < blockn), "Block index overflow"
            
            assert(uf.flags == 0x2000), "Non-RAM UF2 images are not supported yet"
            assert(uf.len == 0x100), "Non- SDK-generated UF2 files are not supported (yet?)"
            assert(not (uf.dst & 0xFF)), "Misaligned addresses are not supported (yet?)"
            
            if uf.dst >= 0x20000000 and uf.dst < 0x20040000:
                return die("Striped UF2 binaries are not supported (already striped?)")
            elif uf.dst >= 0x21000000 and uf.dst < 0x21040000:
                # Note: guaranteed to not cross bank boundaries, so only need to calcualte once
                
                if uf.dst == 0x21000000:
                    bootable = True
                
                stripeloc = (block2unblock(uf.dst) >> 2) & 0xFFFF
                unstripeloc = ((uf.dst) >> 2) & 0xFFFF
                
                ramused[stripeloc >> 8] = True
                
                src = array('I')
                src.frombytes(uf.buf)
                
                for x in range(256 >> 2):
                    ramstriped[stripeloc] = src[x]
                    ramunstriped[unstripeloc] = src[x]
                    
                    stripeloc += 4
                    unstripeloc += 1
                
                
                
            else:
                misc.append(uf)
            
            blocki += 1
    
    assert(ramused[0] and bootable), "Yeah, you're not going to boot this"
    
    assert(ramunstriped[0] == 0x491C481B
       and ramunstriped[1] == 0xC8066008
       and ramunstriped[2] == 0x8808F381
       and ramunstriped[3] == 0x481A4710
       and ramunstriped[0x70 >> 2] == 0x21000100),\
           "Unknown bootcode, can't patch this (report with .uf2 and unstripped .elf attached to issue)"
    
    assert(not (NOOK_ADDR in misc)), "Bootcode segment occupied"
    
    ramstriped[0] = patchjump
    
    # 0x20040800
    
    #outblockcnt = sum(4 if ramused[i] else 0 for i in range(len(ramused))) + 1
    outblockcnt = sum(4 if ramused[i] else 4 for i in range(len(ramused))) + 1
    outblk = 0
    
    outram = ramstriped.tobytes()
    assert(len(outram) == 0x40000), "WTF, bad RAM size"
    
    with open(argv[2], 'wb') as fo:
        for x in range(len(ramused)):
            #if not ramused[x]:
            if False:
                continue
            
            for y in range(4):
                dstaddr = 0x20000000 | (x << 10) | (y << 8)
                dstbuf = dstaddr & 0x3FFFF
                
                uf = uftuple(magic0 = UF2_MAGIC0, magic1 = UF2_MAGIC1, flags = 0x2000,
                             dst = dstaddr, len = 0x100,
                             iBlock = outblk, nBlocks = outblockcnt, dummy = serial,
                             buf = outram[dstbuf : (dstbuf + 0x100)],
                             magic2 = UF2_MAGIC2)
                
                ufbytes = ufstruct.pack(*uf)
                assert(len(ufbytes) == 512), "Yeah, no idea how this assert could fail"
                
                fo.write(ufbytes)
                
                outblk += 1
        
        if True:
            dstaddr = NOOK_ADDR
            
            uf = uftuple(magic0 = UF2_MAGIC0, magic1 = UF2_MAGIC1, flags = 0x2000,
                         dst = dstaddr, len = 0x100,
                         iBlock = outblk, nBlocks = outblockcnt, dummy = serial,
                         buf = patchnook,
                         magic2 = UF2_MAGIC2)
            
            ufbytes = ufstruct.pack(*uf)
            assert(len(ufbytes) == 512), "Yeah, no idea how this assert could fail"
            
            fo.write(ufbytes)
        
        fo.flush()
        pass
    pass

if __name__ == '__main__':
    sys.exit(main() or 0)
