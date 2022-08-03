vecaddr equ 0x21000100

.create "stage1.bin", 0x20000000

.3ds
.thumb
.area 4
BL bootlol ; B range is too short, need BL
.endarea

.close

; This address should be used by Core1 booting, so it's safe to patch
.create "stage2.bin", 0x20040800

bootlol:
    LDR r0, =vecaddr
    LDR r1, =0xE000ED08
    STR r0, [r1]
    LDMIA r0!, {r1, r2}
    .word 0x8808F381 ; MSR MSP, r1
    BX r2
    
    .pool

.close
