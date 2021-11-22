from typing import Callable, Dict, Iterable, List, Tuple, Type

from shivyc.il_cmds.base import ILCommand
from shivyc.il_gen import ILValue
from shivyc.spots import Spot

_peephole_defs = []
_peephole_max_len = 0

def peephole_decorator( pattern: Iterable[Type] ):
    def decorator( func ):
        _peephole_defs.append(( pattern, func ))
        global _peephole_max_len
        if len(pattern) > _peephole_max_len:
            _peephole_max_len = len(pattern)
        return func
    return decorator

def perform_il_peephole( commands: List[ILCommand] ) -> None:
    # Import so that we can get all of the peepholes
    import shivyc.ilpeep.all
    i = 0
    while i < len(commands):
        for pat, func in _peephole_defs:
            pat_match = True
            for type, cmd in zip(pat, commands[i:]):
                if not isinstance(cmd, type):
                    pat_match = False
                    break
            if not pat_match:
                continue
            if not func(commands, i):
                # peephole didn't match, try next one
                continue
            # peephole matched, let's move back in-case another one now applies
            i -= 1
            break
        else:
            # We tried all of the patterns and none of them applied.
            # Let's move on to the next IL starting point.
            i += 1
