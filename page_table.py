#!/usr/bin/env python3
"""Page table — virtual memory address translation with TLB.

One file. Zero deps. Does one thing well.

Multi-level page table (x86-64 style 4-level), TLB with LRU eviction,
page fault handling, and demand paging simulation.
"""
import sys, random

class PageTableEntry:
    __slots__ = ('present', 'frame', 'dirty', 'accessed', 'writable', 'user')
    def __init__(self, frame=0, present=False, writable=True, user=True):
        self.present = present
        self.frame = frame
        self.dirty = False
        self.accessed = False
        self.writable = writable
        self.user = user

class TLB:
    def __init__(self, size=64):
        self.size = size
        self.entries = {}  # vpn -> (frame, tick)
        self.tick = 0
        self.hits = 0
        self.misses = 0

    def lookup(self, vpn):
        self.tick += 1
        if vpn in self.entries:
            self.entries[vpn] = (self.entries[vpn][0], self.tick)
            self.hits += 1
            return self.entries[vpn][0]
        self.misses += 1
        return None

    def insert(self, vpn, frame):
        if len(self.entries) >= self.size:
            # LRU eviction
            victim = min(self.entries, key=lambda k: self.entries[k][1])
            del self.entries[victim]
        self.entries[vpn] = (frame, self.tick)

    def invalidate(self, vpn):
        self.entries.pop(vpn, None)

    def flush(self):
        self.entries.clear()

    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total if total else 0

class PageTable:
    """Simulated 4-level page table (like x86-64)."""
    PAGE_SIZE = 4096
    LEVELS = 4
    BITS_PER_LEVEL = 9

    def __init__(self, physical_frames=256):
        self.root = {}  # Nested dicts simulating page table levels
        self.physical_frames = physical_frames
        self.next_frame = 0
        self.tlb = TLB(64)
        self.page_faults = 0
        self.translations = 0

    def _split_vpn(self, vpn):
        indices = []
        for _ in range(self.LEVELS):
            indices.append(vpn & ((1 << self.BITS_PER_LEVEL) - 1))
            vpn >>= self.BITS_PER_LEVEL
        return list(reversed(indices))

    def _alloc_frame(self):
        if self.next_frame >= self.physical_frames:
            return None  # OOM
        frame = self.next_frame
        self.next_frame += 1
        return frame

    def translate(self, virtual_addr):
        """Translate virtual address to physical address."""
        self.translations += 1
        vpn = virtual_addr >> 12
        offset = virtual_addr & 0xFFF

        # TLB check
        frame = self.tlb.lookup(vpn)
        if frame is not None:
            return frame * self.PAGE_SIZE + offset

        # Walk page table
        indices = self._split_vpn(vpn)
        table = self.root
        for i, idx in enumerate(indices[:-1]):
            if idx not in table:
                table[idx] = {}
            table = table[idx]

        leaf_idx = indices[-1]
        if leaf_idx not in table or not isinstance(table[leaf_idx], PageTableEntry) or not table[leaf_idx].present:
            # Page fault — demand paging
            self.page_faults += 1
            frame = self._alloc_frame()
            if frame is None:
                raise MemoryError("Out of physical frames")
            pte = PageTableEntry(frame=frame, present=True)
            table[leaf_idx] = pte
        else:
            pte = table[leaf_idx]

        pte.accessed = True
        self.tlb.insert(vpn, pte.frame)
        return pte.frame * self.PAGE_SIZE + offset

    def stats(self):
        return (f"translations={self.translations:,}, page_faults={self.page_faults:,}, "
                f"frames_used={self.next_frame}/{self.physical_frames}, "
                f"TLB hit_rate={self.tlb.hit_rate():.1%}")

def main():
    random.seed(42)
    pt = PageTable(physical_frames=1024)
    print("=== Virtual Memory (4-Level Page Table + TLB) ===\n")

    # Sequential access — good TLB locality
    print("Sequential access (1000 pages):")
    for i in range(1000):
        addr = i * 4096 + random.randint(0, 4095)
        phys = pt.translate(addr)
    print(f"  {pt.stats()}")

    # Reset stats
    pt2 = PageTable(1024)
    print("\nRandom access (1000 unique pages):")
    pages = list(range(1000))
    random.shuffle(pages)
    for p in pages:
        pt2.translate(p * 4096 + 100)
    # Re-access some (should hit TLB)
    for p in pages[:100]:
        pt2.translate(p * 4096 + 200)
    print(f"  {pt2.stats()}")

    # Locality simulation: working set
    pt3 = PageTable(1024)
    print("\nWorking set (10 hot pages, 990 cold):")
    hot_pages = list(range(10))
    cold_pages = list(range(10, 1000))
    for _ in range(10000):
        if random.random() < 0.9:
            p = random.choice(hot_pages)
        else:
            p = random.choice(cold_pages)
        pt3.translate(p * 4096 + random.randint(0, 4095))
    print(f"  {pt3.stats()}")

if __name__ == "__main__":
    main()
