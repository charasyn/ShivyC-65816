from typing import Dict, List, Union
from shivyc.il_gen import ILValue
import shivyc.spots as spots

def determine_calling_convention(param_sizes: List[int]) -> List[spots.Spot]:
    available = set((spots.A, spots.X, spots.Y))
    parent_stack_offset = 0x0E
    allocation = []
    for param_size in param_sizes:
        dest = None
        if param_size == 1:
            for reg in [spots.A]:
                if reg in available:
                    available.remove(reg)
                    dest = reg
                    break
        elif param_size == 2:
            for reg in [spots.A, spots.X, spots.Y]:
                if reg in available:
                    available.remove(reg)
                    dest = reg
                    break
        if not dest:
            # The parameter doesn't go in a register.
            # Put it starting at $0E in the parent's stack frame.
            reg = spots.ParentDPRelativeSpot(parent_stack_offset)
            parent_stack_offset += param_size
            dest = reg
        allocation.append(dest)
    return allocation
