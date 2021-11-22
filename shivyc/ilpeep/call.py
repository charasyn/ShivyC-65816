from typing import Dict, List, Tuple, Union

from shivyc.il_cmds.base import ILCommand
from shivyc.il_cmds.value import AddrOf
from shivyc.il_cmds.control import Call
from shivyc.il_gen import ILValue
from shivyc.ilpeep import peephole_decorator
import shivyc.spots as spots
import shivyc.ctypes as ctypes

@peephole_decorator((AddrOf,Call))
def peep_call_symbol( commands: List[ILCommand],
                      start: int ) -> bool:
    cmd_addrof: AddrOf = commands[start]
    fn_val = cmd_addrof.var
    # If we're getting the address of a function, then just
    # directly call the function instead.
    if not isinstance(fn_val.ctype, ctypes.FunctionCType):
        return False
    cmd_call: Call = commands[start+1]
    cmd_call_new = Call(fn_val, cmd_call.args, cmd_call.ret)
    commands[start:start+2] = (cmd_call_new,)
    return True
