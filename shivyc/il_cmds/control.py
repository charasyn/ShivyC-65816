"""IL commands for labels, jumps, and function calls."""

from typing import List
import shivyc.asm_cmds as asm_cmds
import shivyc.spots as spots
from shivyc.il_cmds.base import ILCommand
from shivyc.spots import LiteralSpot, Spot


class Label(ILCommand):
    """Label - Analogous to an ASM label."""

    def __init__(self, label): # noqa D102
        """The label argument is an string label name unique to this label."""
        self.label = label

    def inputs(self): # noqa D102
        return []

    def outputs(self): # noqa D102
        return []

    def label_name(self):  # noqa D102
        return self.label

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        asm_code.add(asm_cmds.Label(self.label))

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.label_name()})'


class Jump(ILCommand):
    """Jumps unconditionally to a label."""

    def __init__(self, label): # noqa D102
        self.label = label

    def inputs(self): # noqa D102
        return []

    def outputs(self): # noqa D102
        return []

    def targets(self): # noqa D102
        return [self.label]

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        asm_code.add(asm_cmds.Jmp(self.label))

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.targets()[0]})'


class _GeneralJump(ILCommand):
    """General class for jumping to a label based on condition."""

    # ASM command to output for this jump IL command.
    # (asm_cmds.Je for JumpZero and asm_cmds.Jne for JumpNotZero)
    asm_cmd = None

    def __init__(self, cond, label): # noqa D102
        self.cond = cond
        self.label = label

    def inputs(self): # noqa D102
        return [self.cond]

    def outputs(self): # noqa D102
        return []

    def targets(self): # noqa D102
        return [self.label]

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        size = self.cond.ctype.size

        if isinstance(spotmap[self.cond], LiteralSpot):
            r = get_reg()
            asm_code.add(asm_cmds.Mov(r, spotmap[self.cond], size))
            cond_spot = r
        else:
            cond_spot = spotmap[self.cond]

        zero_spot = LiteralSpot("0")
        asm_code.add(asm_cmds.Cmp(cond_spot, zero_spot, size))
        asm_code.add(self.command(self.label))

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.inputs()[0]}, {self.targets()[0]})'


class JumpZero(_GeneralJump):
    """Jumps to a label if given condition is zero."""

    command = asm_cmds.Je


class JumpNotZero(_GeneralJump):
    """Jumps to a label if given condition is zero."""

    command = asm_cmds.Jne


class Return(ILCommand):
    """RETURN - returns the given value from function.

    If arg is None, then returns from the function without putting any value
    in the return register. Today, only supports values that fit in one
    register.
    """

    def __init__(self, arg=None): # noqa D102
        # arg must already be cast to return type
        self.arg = arg

    def inputs(self): # noqa D102
        return [self.arg]

    def outputs(self): # noqa D102
        return []

    def clobber(self):  # noqa D102
        return [spots.A]

    def abs_spot_pref(self):  # noqa D102
        return {self.arg: [spots.A]}

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        if self.arg and spotmap[self.arg] != spots.A:
            size = self.arg.ctype.size
            asm_code.add(asm_cmds.Mov(spots.A, spotmap[self.arg], size))

        # asm_code.add(asm_cmds.Mov(spots.RSP, spots.RBP, 8))
        asm_code.add(asm_cmds.Pop(spots.DP, None, 8))
        asm_code.add(asm_cmds.Ret())


class Call(ILCommand):
    """Call a given function.

    func - Pointer to function
    args - Arguments of the function, in left-to-right order. Must match the
    parameter types the function expects.
    ret - If function has non-void return type, IL value to save the return
    value. Its type must match the function return value.
    """

    def __init__(self, func, args, ret): # noqa D102
        self.func = func
        self.args = args
        self.ret = ret
        self.void_return = self.func.ctype.arg.ret.is_void()
        if not self.void_return:
            if self.func.ctype.arg.ret.size <= 2:
                self.ret_spot = spots.A
            else:
                self.ret_spot = spots.MemSpot(spots.DP, 0x06)
        self.arg_spots: List[spots.Spot] = None

    def inputs(self): # noqa D102
        return [self.func] + self.args

    def outputs(self): # noqa D102
        return [] if self.void_return else [self.ret]

    def clobber(self): # noqa D102
        # All caller-saved registers are clobbered by function call
        clobbered_regs = set((spots.A, spots.X, spots.Y))
        call_spots = set(self.arg_spots)
        if not self.void_return:
            call_spots.add(self.ret_spot)
        return list(clobbered_regs | call_spots)

    def abs_spot_pref(self): # noqa D102
        prefs = {} if self.void_return else {self.ret: [self.ret_spot]}
        for arg, reg in zip(self.args, self.arg_spots):
            prefs[arg] = [reg]
        prefs[self.func] = [spots.MemSpot(spots.DP, 0x06)]
        return prefs

    def abs_spot_conf(self): # noqa D102
        # We don't want the function pointer to be in the same register as
        # an argument will be placed into.
        return {self.func: self.arg_spots}

    def indir_write(self): # noqa D102
        return self.args

    def indir_read(self): # noqa D102
        return self.args

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        func_spot = spotmap[self.func]

        func_size = self.func.ctype.size
        ret_size = self.func.ctype.arg.ret.size

        # Check if function pointer spot will be clobbered by moving the
        # arguments into the correct registers.
        if spotmap[self.func] in self.arg_spots:
            # Get a register which isn't one of the unallowed registers.
            r = get_reg([], self.arg_spots)
            asm_code.add(asm_cmds.Mov(r, spotmap[self.func], func_size))
            func_spot = r

        for arg, reg in zip(self.args, self.arg_spots):
            if spotmap[arg] == reg:
                continue
            asm_code.add(asm_cmds.Mov(reg, spotmap[arg], arg.ctype.size))

        asm_code.add(asm_cmds.Call(func_spot, None, self.func.ctype.size))

        if not self.void_return and spotmap[self.ret] != self.ret_spot:
            asm_code.add(asm_cmds.Mov(spotmap[self.ret], self.ret_spot, ret_size))
