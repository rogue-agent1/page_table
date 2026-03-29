#!/usr/bin/env python3
"""Virtual memory: page table, TLB, page replacement (LRU, Clock, NRU)."""
import sys
from collections import OrderedDict

class PageTableEntry:
    def __init__(self, frame=-1, valid=False, dirty=False, referenced=False):
        self.frame,self.valid,self.dirty,self.referenced = frame,valid,dirty,referenced

class TLB:
    def __init__(self, size=16): self.size = size; self.entries = OrderedDict()
    def lookup(self, page):
        if page in self.entries: self.entries.move_to_end(page); return self.entries[page]
        return None
    def insert(self, page, frame):
        if len(self.entries) >= self.size: self.entries.popitem(last=False)
        self.entries[page] = frame
    def invalidate(self, page): self.entries.pop(page, None)

class VirtualMemory:
    def __init__(self, n_pages=64, n_frames=16, page_size=4096):
        self.n_pages,self.n_frames,self.page_size = n_pages,n_frames,page_size
        self.page_table = [PageTableEntry() for _ in range(n_pages)]
        self.frames = [None]*n_frames; self.free_frames = list(range(n_frames))
        self.tlb = TLB(16)
        self.stats = {"hits":0,"misses":0,"tlb_hits":0,"page_faults":0,"evictions":0}
        self.clock_hand = 0
    def access(self, virtual_addr, write=False):
        page = virtual_addr // self.page_size; offset = virtual_addr % self.page_size
        # TLB lookup
        frame = self.tlb.lookup(page)
        if frame is not None: self.stats["tlb_hits"] += 1
        else:
            pte = self.page_table[page]
            if pte.valid:
                frame = pte.frame; self.stats["hits"] += 1
            else:
                frame = self._page_fault(page); self.stats["page_faults"] += 1
            self.tlb.insert(page, frame)
        self.page_table[page].referenced = True
        if write: self.page_table[page].dirty = True
        return frame * self.page_size + offset
    def _page_fault(self, page):
        if self.free_frames:
            frame = self.free_frames.pop(0)
        else:
            frame = self._evict_clock()
        self.frames[frame] = page
        self.page_table[page].frame = frame
        self.page_table[page].valid = True
        return frame
    def _evict_clock(self):
        while True:
            page = self.frames[self.clock_hand]
            if page is not None and not self.page_table[page].referenced:
                self.page_table[page].valid = False
                self.tlb.invalidate(page)
                self.stats["evictions"] += 1
                frame = self.clock_hand
                self.clock_hand = (self.clock_hand + 1) % self.n_frames
                return frame
            if page is not None: self.page_table[page].referenced = False
            self.clock_hand = (self.clock_hand + 1) % self.n_frames

def main():
    import random; random.seed(42)
    vm = VirtualMemory(64, 8, 4096)
    for _ in range(1000):
        page = random.choices(range(64), weights=[1/(i+1) for i in range(64)])[0]
        addr = page * 4096 + random.randint(0, 4095)
        vm.access(addr, write=random.random() < 0.3)
    print(f"  Stats: {vm.stats}")
    hit_rate = vm.stats["hits"] / (vm.stats["hits"]+vm.stats["page_faults"]) * 100
    tlb_rate = vm.stats["tlb_hits"] / 1000 * 100
    print(f"  Page hit rate: {hit_rate:.1f}%")
    print(f"  TLB hit rate: {tlb_rate:.1f}%")

if __name__ == "__main__": main()
