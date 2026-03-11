#!/usr/bin/env python3
"""page_table - Multi-level page table simulator (x86-64 style 4-level paging).

Usage: python page_table.py [--levels N] [--page-size BITS] [--demo]
"""
import sys, random

class PageTableEntry:
    __slots__ = ('present','frame','dirty','accessed','writable','user','nx')
    def __init__(self, frame=0, present=False, writable=True, user=False):
        self.present = present; self.frame = frame
        self.dirty = False; self.accessed = False
        self.writable = writable; self.user = user; self.nx = False

class MultiLevelPageTable:
    def __init__(self, levels=4, bits_per_level=9, offset_bits=12):
        self.levels = levels
        self.bits_per_level = bits_per_level
        self.offset_bits = offset_bits
        self.root = {}
        self.next_frame = 0x1000
        self.page_faults = 0
        self.translations = 0
        self.tlb = {}  # VA page -> PA frame
        self.tlb_hits = 0

    def _indices(self, vaddr):
        offset = vaddr & ((1 << self.offset_bits) - 1)
        remaining = vaddr >> self.offset_bits
        indices = []
        for _ in range(self.levels):
            indices.append(remaining & ((1 << self.bits_per_level) - 1))
            remaining >>= self.bits_per_level
        return list(reversed(indices)), offset

    def _alloc_frame(self):
        f = self.next_frame
        self.next_frame += 1
        return f

    def map_page(self, vaddr, frame=None, writable=True, user=False):
        indices, _ = self._indices(vaddr)
        table = self.root
        for i, idx in enumerate(indices[:-1]):
            if idx not in table:
                table[idx] = {}
            table = table[idx]
        leaf_idx = indices[-1]
        if frame is None:
            frame = self._alloc_frame()
        table[leaf_idx] = PageTableEntry(frame, True, writable, user)
        # Invalidate TLB
        page = vaddr >> self.offset_bits
        self.tlb.pop(page, None)
        return frame

    def translate(self, vaddr, write=False):
        self.translations += 1
        page = vaddr >> self.offset_bits
        _, offset = self._indices(vaddr)
        # TLB check
        if page in self.tlb:
            self.tlb_hits += 1
            return (self.tlb[page] << self.offset_bits) | offset
        indices, offset = self._indices(vaddr)
        table = self.root
        for i, idx in enumerate(indices[:-1]):
            if idx not in table:
                self.page_faults += 1
                return None  # Page fault
            table = table[idx]
        leaf_idx = indices[-1]
        if leaf_idx not in table:
            self.page_faults += 1
            return None
        pte = table[leaf_idx]
        if not pte.present:
            self.page_faults += 1
            return None
        if write and not pte.writable:
            return None  # Protection fault
        pte.accessed = True
        if write:
            pte.dirty = True
        self.tlb[page] = pte.frame
        return (pte.frame << self.offset_bits) | offset

    def flush_tlb(self):
        self.tlb.clear()

    def stats(self):
        return {
            "translations": self.translations,
            "page_faults": self.page_faults,
            "tlb_hits": self.tlb_hits,
            "tlb_entries": len(self.tlb),
            "hit_rate": f"{self.tlb_hits/max(1,self.translations)*100:.1f}%"
        }

def main():
    levels, demo = 4, True
    for i, a in enumerate(sys.argv[1:]):
        if a == "--levels" and i+2 <= len(sys.argv[1:]): levels = int(sys.argv[i+2])
        if a == "--demo": demo = True

    pt = MultiLevelPageTable(levels=levels)
    print(f"Page Table: {levels}-level, {pt.bits_per_level} bits/level, "
          f"{pt.offset_bits}-bit offset ({1<<pt.offset_bits}B pages)")
    print(f"VA width: {levels*pt.bits_per_level+pt.offset_bits} bits\n")

    # Map some pages
    mappings = []
    for i in range(16):
        vaddr = i * (1 << pt.offset_bits)
        frame = pt.map_page(vaddr)
        mappings.append((vaddr, frame))
        print(f"  Mapped VA 0x{vaddr:08x} -> frame 0x{frame:04x}")

    print(f"\nTranslations:")
    for va, expected_frame in mappings[:8]:
        for off in [0, 100, 4095]:
            addr = va + off
            pa = pt.translate(addr)
            print(f"  VA 0x{addr:08x} -> PA 0x{pa:08x}" if pa else f"  VA 0x{addr:08x} -> PAGE FAULT")

    # Access unmapped page
    pa = pt.translate(0xDEAD000)
    print(f"  VA 0xDEAD000 -> {'PAGE FAULT' if pa is None else f'0x{pa:08x}'}")

    # TLB test - re-access
    print(f"\nRe-accessing (TLB warm):")
    for va, _ in mappings[:4]:
        pt.translate(va)

    print(f"\nStats: {pt.stats()}")

if __name__ == "__main__":
    main()
