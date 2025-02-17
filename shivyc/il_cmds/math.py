"""IL commands for mathematical operations."""

from typing import Dict
import shivyc.asm_cmds as asm_cmds
from shivyc.errors import CompilerError
from shivyc.il_gen import ILValue
import shivyc.spots as spots
from shivyc.il_cmds.base import ILCommand


class _AddMult(ILCommand):
    """Base class for ADD, MULT, and SUB."""

    # Indicates whether this instruction is commutative. If not,
    # a "neg" instruction is inserted when the order is flipped. Override
    # this value in subclasses.
    comm = False

    # The ASM instruction to generate for this command. Override this value
    # in subclasses.
    Inst = None

    def __init__(self, output, arg1, arg2): # noqa D102
        self.output = output
        self.arg1 = arg1
        self.arg2 = arg2

    def inputs(self): # noqa D102
        return [self.arg1, self.arg2]

    def outputs(self): # noqa D102
        return [self.output]

    def rel_spot_pref(self): # noqa D102
        return {self.output: [self.arg1, self.arg2]}
    
    def abs_spot_pref(self):
        return {self.output: [spots.A]}

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        """Make the ASM for ADD, MULT, and SUB."""
        ctype = self.arg1.ctype
        size = ctype.size

        arg1_spot = spotmap[self.arg1]
        arg2_spot = spotmap[self.arg2]

        # Get temp register for computation.
        temp = get_reg([spotmap[self.output],
                        arg1_spot,
                        arg2_spot])

        if temp == arg1_spot:
            if not self._is_imm64(arg2_spot):
                asm_code.add(self.Inst(temp, arg2_spot, size))
            else:
                temp2 = get_reg([], [temp])
                asm_code.add(asm_cmds.Mov(temp2, arg2_spot, size))
                asm_code.add(self.Inst(temp, temp2, size))
        elif temp == arg2_spot:
            if not self._is_imm64(arg1_spot):
                asm_code.add(self.Inst(temp, arg1_spot, size))
            else:
                temp2 = get_reg([], [temp])
                asm_code.add(asm_cmds.Mov(temp2, arg1_spot, size))
                asm_code.add(self.Inst(temp, temp2, size))

            if not self.comm:
                asm_code.add(asm_cmds.Neg(temp, None, size))

        else:
            if (not self._is_imm64(arg1_spot) and
                 not self._is_imm64(arg2_spot)):
                asm_code.add(asm_cmds.Mov(temp, arg1_spot, size))
                asm_code.add(self.Inst(temp, arg2_spot, size))
            elif (self._is_imm64(arg1_spot) and
                  not self._is_imm64(arg2_spot)):
                asm_code.add(asm_cmds.Mov(temp, arg1_spot, size))
                asm_code.add(self.Inst(temp, arg2_spot, size))
            elif (not self._is_imm64(arg1_spot) and
                  self._is_imm64(arg2_spot)):
                asm_code.add(asm_cmds.Mov(temp, arg2_spot, size))
                asm_code.add(self.Inst(temp, arg1_spot, size))
                if not self.comm:
                    asm_code.add(asm_cmds.Neg(temp, None, size))

            else:  # both are imm64
                raise NotImplementedError(
                    "never reach because of constant folding")

        if temp != spotmap[self.output]:
            asm_code.add(asm_cmds.Mov(spotmap[self.output], temp, size))


class Add(_AddMult):
    """Adds arg1 and arg2, then saves to output.

    IL values output, arg1, arg2 must all have the same type. No type
    conversion or promotion is done here.
    """
    comm = True
    Inst = asm_cmds.Add


class Subtr(_AddMult):
    """Subtracts arg1 and arg2, then saves to output.

    ILValues output, arg1, and arg2 must all have types of the same size.
    """
    comm = False
    Inst = asm_cmds.Sub


class Mult(ILCommand):
    """Multiplies arg1 and arg2, then saves to output.

    IL values output, arg1, arg2 must all have the same type. No type
    conversion or promotion is done here.
    """

    MULT32 = 1     # $06 * $0A -> $06
    MULT16 = 2     # A * Y -> A
    MULT168 = 3    # A(16) * Y(8) -> A
    # ADDCHAIN16 = 4 # A * const -> A

    comm = True
    Inst = asm_cmds.Imul
    
    def __init__(self, output, arg1: ILValue, arg2: ILValue): # noqa D102
        self.output = output
        if arg1.literal or (not arg2.literal and arg1.ctype.size < arg2.ctype.size):
            arg1, arg2 = arg2, arg1
        # If arg is literal, it's arg2
        # Otherwise, arg1 has bigger type of them
        self.arg1 = arg1
        self.arg2 = arg2
        if self.arg1.ctype.size > 2 or self.arg1.ctype.size > 2:
            self.impl = self.MULT32
        # elif self._can_do_literal():
        #     self.impl = self.ADDCHAIN16
        elif self.arg2.ctype.size == 2:
            self.impl = self.MULT16
        else:
            # I don't think the frontend will generate this ATM
            # TODO: make frontend detect MULT168 cases
            self.impl = self.MULT168

    def inputs(self): # noqa D102
        return [self.arg1, self.arg2]

    def outputs(self): # noqa D102
        return [self.output]
    
    def _valid_output_spot(self):
        if self.impl == self.MULT32:
            return spots.DP06
        else:
            return spots.A
    
    def _valid_spots(self):
        if self.impl == self.MULT32:
            return spots.DP06
        else:
            return spots.A
    
    def abs_spot_pref(self):
        pref: Dict[ILValue, spots.Spot]
        if self.impl == self.MULT32:
            pref = {self.output: [spots.DP06], self.arg1: [spots.DP06, spots.DP0A], self.arg2: [spots.DP06, spots.DP0A]}
        else:
            pref = {self.output: [spots.A], self.arg1: [spots.A], self.arg2: [spots.Y]}
        return pref

    def clobber(self):
        if self.impl == self.MULT32:
            return [spots.A, spots.Y, spots.DP06, spots.DP0A]
        else:
            return [spots.A, spots.Y]

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        """Make the ASM for MULT."""
        ctype = self.arg1.ctype
        size = ctype.size

        required_spotmap = self.abs_spot_pref()
        arg1_spot = spotmap[self.arg1]
        arg2_spot = spotmap[self.arg2]

        # print(f'Mult{self.impl} arg1:{arg1_spot} arg2:{arg2_spot} out:{spotmap[self.output]}')

        impl_to_function = {
            self.MULT32: "MULT32",
            self.MULT16: "MULT16",
            self.MULT168: "MULT168",
        }
        if self.impl == self.MULT32:
            pass
        elif self.impl == self.MULT16 or self.impl == self.MULT168:
            arg1_req = required_spotmap[self.arg1][0]
            arg2_req = required_spotmap[self.arg2][0]
            # We don't need to worry about saving the previous value since
            # we marked the required registers as clobber
            if arg1_spot != arg1_req:
                asm_code.add(asm_cmds.Mov(arg1_req, arg1_spot, size))
            if arg2_spot != arg2_req:
                asm_code.add(asm_cmds.Mov(arg2_req, arg2_spot, size))
            asm_code.add(asm_cmds.Call(spots.LiteralSpot(impl_to_function[self.impl])))
        else:
            raise NotImplementedError(f"Unknown multiplication implementation {self.impl}")

        # if temp == arg1_spot:
        #     if not self._is_imm64(arg2_spot):
        #         asm_code.add(self.Inst(temp, arg2_spot, size))
        #     else:
        #         temp2 = get_reg([], [temp])
        #         asm_code.add(asm_cmds.Mov(temp2, arg2_spot, size))
        #         asm_code.add(self.Inst(temp, temp2, size))
        # elif temp == arg2_spot:
        #     if not self._is_imm64(arg1_spot):
        #         asm_code.add(self.Inst(temp, arg1_spot, size))
        #     else:
        #         temp2 = get_reg([], [temp])
        #         asm_code.add(asm_cmds.Mov(temp2, arg1_spot, size))
        #         asm_code.add(self.Inst(temp, temp2, size))

        #     if not self.comm:
        #         asm_code.add(asm_cmds.Neg(temp, None, size))

        # else:
        #     if (not self._is_imm64(arg1_spot) and
        #          not self._is_imm64(arg2_spot)):
        #         asm_code.add(asm_cmds.Mov(temp, arg1_spot, size))
        #         asm_code.add(self.Inst(temp, arg2_spot, size))
        #     elif (self._is_imm64(arg1_spot) and
        #           not self._is_imm64(arg2_spot)):
        #         asm_code.add(asm_cmds.Mov(temp, arg1_spot, size))
        #         asm_code.add(self.Inst(temp, arg2_spot, size))
        #     elif (not self._is_imm64(arg1_spot) and
        #           self._is_imm64(arg2_spot)):
        #         asm_code.add(asm_cmds.Mov(temp, arg2_spot, size))
        #         asm_code.add(self.Inst(temp, arg1_spot, size))
        #         if not self.comm:
        #             asm_code.add(asm_cmds.Neg(temp, None, size))

        #     else:  # both are imm64
        #         raise NotImplementedError(
        #             "never reach because of constant folding")

        if required_spotmap[self.output][0] != spotmap[self.output]:
            asm_code.add(asm_cmds.Mov(spotmap[self.output], required_spotmap[self.output][0], size))




class _BitShiftCmd(ILCommand):
    """Base class for bitwise shift commands."""

    # The ASM instruction to generate for this command. Override this value
    # in subclasses.
    Inst = None

    def __init__(self, output, arg1, arg2): # noqa D102
        self.output = output
        self.arg1 = arg1
        self.arg2 = arg2

    def inputs(self): # noqa D102
        return [self.arg1, self.arg2]

    def outputs(self): # noqa D102
        return [self.output]

    def clobber(self):  # noqa D102
        raise NotImplementedError()
        # return [spots.RCX]

    def abs_spot_pref(self): # noqa D102
        raise NotImplementedError()
        # return {self.arg2: [spots.RCX]}

    def rel_spot_pref(self): # noqa D102
        return {self.output: [self.arg1]}

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        raise NotImplementedError()
        arg1_spot = spotmap[self.arg1]
        arg1_size = self.arg1.ctype.size
        arg2_spot = spotmap[self.arg2]
        arg2_size = self.arg2.ctype.size

        # According Intel® 64 and IA-32 software developer's manual
        # Vol. 2B 4-582 second (count) operand must be represented as
        # imm8 or CL register.
        # if not self._is_imm8(arg2_spot) and arg2_spot != spots.RCX:
        #     if arg1_spot == spots.RCX:
        #         out_spot = spotmap[self.output]
        #         temp_spot = get_reg([out_spot, arg1_spot],
        #                             [arg2_spot, spots.RCX])
        #         asm_code.add(asm_cmds.Mov(temp_spot, arg1_spot, arg1_size))
        #         arg1_spot = temp_spot
        #     asm_code.add(asm_cmds.Mov(spots.RCX, arg2_spot, arg2_size))
        #     arg2_spot = spots.RCX

        if spotmap[self.output] == arg1_spot:
            asm_code.add(self.Inst(arg1_spot, arg2_spot, arg1_size, 1))
        else:
            out_spot = spotmap[self.output]
            temp_spot = get_reg([out_spot, arg1_spot], [arg2_spot])
            if arg1_spot != temp_spot:
                asm_code.add(asm_cmds.Mov(temp_spot, arg1_spot, arg1_size))
            asm_code.add(self.Inst(temp_spot, arg2_spot, arg1_size, 1))
            if temp_spot != out_spot:
                asm_code.add(asm_cmds.Mov(out_spot, temp_spot, arg1_size))


class RBitShift(_BitShiftCmd):
    """Right bitwise shift operator for IL value.
    Shifts each bit in IL value left operand to the right by position
    indicated by right operand."""

    Inst = asm_cmds.Sar


class LBitShift(_BitShiftCmd):
    """Left bitwise shift operator for IL value.
    Shifts each bit in IL value left operand to the left by position
    indicated by right operand."""

    Inst = asm_cmds.Sal


class _DivMod(ILCommand):
    """Base class for ILCommand Div and Mod."""

    # Register which contains the value we want after the x86 div or idiv
    # command is executed. For the Div IL command, this is spots.RAX,
    # and for the Mod IL command, this is spots.RDX.
    return_reg = None

    def __init__(self, output, arg1, arg2):
        self.output = output
        self.arg1 = arg1
        self.arg2 = arg2

    def inputs(self):  # noqa D102
        return [self.arg1, self.arg2]

    def outputs(self):  # noqa D102
        return [self.output]

    def clobber(self):  # noqa D102
        return spots.registers

    def abs_spot_conf(self): # noqa D102
        raise NotImplementedError()
        # return {self.arg2: [spots.RDX, spots.RAX]}

    def abs_spot_pref(self): # noqa D102
        raise NotImplementedError()
        # return {self.output: [self.return_reg],
        #         self.arg1: [spots.RAX]}

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        raise NotImplementedError()
        ctype = self.arg1.ctype
        size = ctype.size

        output_spot = spotmap[self.output]
        arg1_spot = spotmap[self.arg1]
        arg2_spot = spotmap[self.arg2]

        # # Move first operand into RAX if we can do so without clobbering
        # # other argument
        # moved_to_rax = False
        # if spotmap[self.arg1] != spots.RAX and spotmap[self.arg2] != spots.RAX:
        #     moved_to_rax = True
        #     asm_code.add(asm_cmds.Mov(spots.RAX, arg1_spot, size))

        # # If the divisor is a literal or in a bad register, we must move it
        # # to a register.
        # if (self._is_imm(spotmap[self.arg2]) or
        #      spotmap[self.arg2] in [spots.RAX, spots.RDX]):
        #     r = get_reg([], [spots.RAX, spots.RDX])
        #     asm_code.add(asm_cmds.Mov(r, arg2_spot, size))
        #     arg2_final_spot = r
        # else:
        #     arg2_final_spot = arg2_spot

        # # If we did not move to RAX above, do so here.
        # if not moved_to_rax and arg1_spot != self.return_reg:
        #     asm_code.add(asm_cmds.Mov(spots.RAX, arg1_spot, size))

        if ctype.signed:
            if ctype.size == 4:
                asm_code.add(asm_cmds.Cdq())
            elif ctype.size == 8:
                asm_code.add(asm_cmds.Cqo())
            asm_code.add(asm_cmds.Idiv(arg2_final_spot, None, size))
        else:
            # zero out RDX register
            asm_code.add(asm_cmds.Xor(spots.RDX, spots.RDX, size))
            asm_code.add(asm_cmds.Div(arg2_final_spot, None, size))

        if spotmap[self.output] != self.return_reg:
            asm_code.add(asm_cmds.Mov(output_spot, self.return_reg, size))


class Div(_DivMod):
    """Divides given IL values.

    IL values output, arg1, arg2 must all have the same type of size at least
    int. No type conversion or promotion is done here.

    """

    # return_reg = spots.RAX


class Mod(_DivMod):
    """Divides given IL values.

    IL values output, arg1, arg2 must all have the same type of size at least
    int. No type conversion or promotion is done here.

    """

    # return_reg = spots.RDX


class _NegNot(ILCommand):
    """Base class for NEG and NOT."""

    # The ASM instruction to generate for this command. Override this value
    # in subclasses.
    Inst = None

    def __init__(self, output, arg):  # noqa D102
        self.output = output
        self.arg = arg

    def inputs(self):  # noqa D102
        return [self.arg]

    def outputs(self):  # noqa D102
        return [self.output]

    def rel_spot_pref(self):  # noqa D102
        return {self.output: [self.arg]}

    def make_asm(self, spotmap, home_spots, get_reg, asm_code, **kwargs): # noqa D102
        size = self.arg.ctype.size

        output_spot = spotmap[self.output]
        arg_spot = spotmap[self.arg]

        if output_spot != arg_spot:
            asm_code.add(asm_cmds.Mov(output_spot, arg_spot, size))
        asm_code.add(self.Inst(output_spot, None, size))


class Neg(_NegNot):
    """Negates given IL value (two's complement).

    No type promotion is done here.

    """

    Inst = asm_cmds.Neg


class Not(_NegNot):
    """Logically negates each bit of given IL value (one's complement).

    No type promotion is done here.

    """

    Inst = asm_cmds.Not
