"""IL commands for labels, jumps, and function calls."""

from typing import List
import shivyc.asm_cmds as asm_cmds
from shivyc.ctypes import PointerCType
from shivyc.il_gen import ILValue
import shivyc.spots as spots
from shivyc.il_cmds.base import ILCommand
from shivyc.spots import LiteralSpot, MemSpot, Spot


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

    func - Pointer to function, or function itself
    args - Arguments of the function, in left-to-right order. Must match the
    parameter types the function expects.
    ret - If function has non-void return type, IL value to save the return
    value. Its type must match the function return value.
    """

    def __init__(self, func, args, ret): # noqa D102
        self.func = func
        self.args = args
        self.ret = ret
        self.func_is_ptr = isinstance(self.func.ctype, PointerCType)
        if self.func_is_ptr:
            self.func_ctype = self.func.ctype.arg
        else:
            self.func_ctype = self.func.ctype
        self.void_return = self.func_ctype.ret.is_void()
        if not self.void_return:
            if self.func_ctype.ret.size <= 2:
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

        ret_size = self.func_ctype.ret.size

        args_with_spots = list(zip(self.args, self.arg_spots))
        reg_args = filter(lambda _, spot:     isinstance(spot, spots.RegSpot), args_with_spots)
        mem_args = filter(lambda _, spot: not isinstance(spot, spots.RegSpot), args_with_spots)

        # Determine if we will need to do any memory copies.
        if mem_args and any(True for arg, reg in mem_args if spotmap[arg] != reg):
            # Determine which register to use to copy
            copy_reg = None
            preserve_y = False
            if spots.Y not in self.arg_spots:
                copy_reg = spots.Y
            else:
                # Registers are supposed to be passed. Look for one that will be overwritten later.
                for arg, dst_spot in reg_args:
                    src_spot = spotmap[arg]
                    if src_spot != dst_spot:
                        # This reg doesn't hold it's intended value currently! Let's use it to copy.
                        copy_reg = dst_spot
                        break
            if copy_reg is None:
                # OK. Let's just save one on the stack.
                copy_reg = spots.Y
                preserve_y = True
            if preserve_y:
                asm_code.add(asm_cmds.Push(spots.Y, size=2))
            # Now we should be able to use copy_reg to copy data around.
            for arg, reg in mem_args:
                if spotmap[arg] == reg:
                    continue
                self._move_any_size(reg, spotmap[arg], arg.ctype.size, copy_reg)
            # If we had to put Y on the stack, get it back.
            if preserve_y:
                asm_code.add(asm_cmds.Pop(spots.Y, size=2))


        for arg, reg in zip(self.args, self.arg_spots):
            if spotmap[arg] == reg:
                continue
            asm_code.add(asm_cmds.Mov(reg, spotmap[arg], arg.ctype.size))
        
        # We need to use the call trampoline if we are calling a pointer and we don't know it's actual value.
        # If it's a literal then we don't need to use the trampoline.
        calling_a_pointer = self.func_is_ptr and not isinstance(func_spot, spots.LiteralSpot)
        if calling_a_pointer:
            fp_size = self.func.ctype.size
            preserve_y = spots.Y in self.arg_spots
            if fp_size == 2:
                # This stores the pointer in the trampoline memory, then jumps directly to it.
                if preserve_y:
                    asm_code.add(asm_cmds.Push(spots.Y, size=2))
                asm_code.add(asm_cmds.Mov(spots.Y, func_spot, size=2))
                asm_code.add(asm_cmds.Mov(spots.MemSpot("TRAMPOLINE_LO"), spots.Y, size=2))
                if preserve_y:
                    asm_code.add(asm_cmds.Pop(spots.Y, size=2))
                # PEA label-1 ; JMP (TRAMPOLINE_LO) ; label:
                label = asm_code.get_label()
                asm_code.add(asm_cmds.Push(spots.LiteralSpot(f'({label})-1'), size=2))
                asm_code.add(asm_cmds.Jmp(spots.MemSpot('TRAMPOLINE_LO'), size=2))
                asm_code.add(asm_cmds.Label(label))
            else:
                if preserve_y:
                    asm_code.add(asm_cmds.Push(spots.Y, size=2))
                asm_code.add(asm_cmds.Mov(spots.Y, func_spot, size=2))
                asm_code.add(asm_cmds.Mov(spots.MemSpot("TRAMPOLINE_LO"), spots.Y, size=2))
                asm_code.add(asm_cmds.Mov(spots.Y, func_spot.shift(2), size=2))
                asm_code.add(asm_cmds.Mov(spots.MemSpot("TRAMPOLINE_HI"), spots.Y, size=2))
                if preserve_y:
                    asm_code.add(asm_cmds.Pop(spots.Y, size=2))
                asm_code.add(asm_cmds.Call(spots.LiteralSpot("CALL_TRAMPOLINE"), size=4))
        else:
            asm_code.add(asm_cmds.Call(func_spot.get_manifest(), size=self.func.ctype.size))

        if not self.void_return and spotmap[self.ret] != self.ret_spot:
            asm_code.add(asm_cmds.Mov(spotmap[self.ret], self.ret_spot, ret_size))
