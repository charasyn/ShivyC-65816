"""Objects used for the AST -> IL phase of the compiler."""

from collections import namedtuple

class CType:
    """Represents a C type, like `int` or `double` or a struct.

    size (int) - The result of sizeof on this type.

    """

    def __init__(self, size):
        """Initialize type."""
        self.size = size

class ILCommand:
    """Stores a single IL command.

    op (Enum) - Type of command, like ADD or MULT
    args - (List[ILValue]) - Arguments of command

    """

    # Supported commands, as used in the constructor of ILCommand.
    #
    # Accepts one output argument and one input argument. Sets the output
    # argument to the input argument.
    SET = 1
    # Accepts one input argument. Returns the input argument value from the
    # current function.
    RETURN = 2
    # Accepts one output argument and two input arguments. Sets the output
    # argument to the sum of the input arguments.
    ADD = 3
    # Accepts one output argument and two input arguments. Sets the output
    # argument to the product of the input arguments.
    MULT = 4

    def __init__(self, op, args):
        """Initialize an ILCommand."""
        self.op = op
        self.args = args

class ILCode:
    """Stores the IL code generated from the AST.

    lines (List) - The lines of code recorded.

    """

    def __init__(self):
        """Initialize IL code."""
        self.commands = []

    def add_command(self, command, arg1=None, arg2=None, output=None):
        """Add a new command to the IL code.

        command (int) - One of the supported commands, as described above.
        arg1, arg2, output (ILValue) - ILValue objects representing the command
        arguments.

        """
        self.commands.append(ILCommand(command, [output, arg1, arg2]))

    def __iter__(self):
        """Return the lines of code in order when iterating through ILCode.

        The returned lines will have command, arg1, arg2, and output as
        attributes, some of which may be NONE if not applicable for that
        command.

        """
        return iter(self.commands)

    def __str__(self):  # noqa: D202, pragma: no cover
        """Return a pretty-printed version of the IL code.

        Useful for debugging, but not to be used for testing. See
        __eq__ below instead.

        """

        def op_name(op):
            """Return the name of an op as a string.

            Example:
                op_name(ILCommand.RETURN) -> "RETURN"

            This is a /terrible/ hack, but works for debugging purposes.
            """
            for name in ILCommand.__dict__:
                if ILCommand.__dict__[name] == op:
                    return name.ljust(7)
            return None

        strlines = []
        for command in self.commands:
            strlines.append(
                str(command.args[0]) + " - " + command_name(command.op) + " " +
                str(command.args[1]) + ", " + str(command.args[2]))
        return '\n'.join(strlines)

    def __eq__(self, other):  # pragma: no cover
        """Check for equality between this IL code object and another.

        Equality is only checked by verifying the IL values are correct
        relative to each other. That is,

        0492 - SET 5823
        5823 - ADD 0492, 1043

        and

        5943 - SET 1342
        1342 - ADD 5943, 8742

        evaluate equal. It the provided ILCode objects need not use real
        ILValue objects as the command arguments. For testing, it can be easier
        to use integers or strings.

        """
        # keys are ILValue ids from self, and values are ILValue ids from other
        value_map = dict()

        def is_equivalent(value1, value2):
            """Check if the given IL values are equivalent based on context."""
            if value1 is None and value2 is None:
                return True
            elif value1 is None or value2 is None:
                return False

            if value1 in value_map:
                return value2 is value_map[value1]
            elif value2 in value_map.values():
                return False
            else:
                value_map[value1] = value2
                return True

        # Check if number of lines match
        if len(other.commands) != len(self.commands):
            return False
        for com1, com2 in zip(self.commands, other.commands):
            if com1.op != com2.op:
                return False
            if len(com1.args) != len(com2.args):
                return False
            for arg1, arg2 in zip(com1.args, com2.args):
                if not is_equivalent(arg1, arg2):
                    return False
        return True


class ILValue:
    """Value that appears as an element in generated IL code.

    Do not use this class directly; instead, use one of the derived classes
    below.

    value_type (enum) - One of the values below describing the general
    type of value this is.
    ctype (Type) - C type of this value.

    """

    # Options for value_type:
    # Temporary value. These are used to store intermediate values in
    # computations.
    TEMP = 1
    # Literal value. These are literal values that are known at compile time.
    LITERAL = 2
    # Variable value. These represent variables in the original C code.
    VARIABLE = 3

    def __init__(self, value_type, ctype):
        """Initialize IL value."""
        self.ctype = ctype
        self.value_type = value_type

    def __str__(self):
        """Pretty-print the last 4 digits of the ID for display."""
        return str(id(self) % 10000)


class TempILValue(ILValue):
    """ILValue that represents a temporary intermediate value."""

    def __init__(self, ctype):
        """Initialize temp IL value."""
        super().__init__(ILValue.TEMP, ctype)


class LiteralILValue(ILValue):
    """ILValue that represents a literal value.

    value (str) - Value in an representation that is convenient for asm.

    """

    def __init__(self, ctype, value):
        """Initialize literal IL value."""
        super().__init__(ILValue.LITERAL, ctype)
        self.value = value

    # We want to literals to compare equal iff they have the same value and
    # type, so the ASM generation step can keep track of their storage
    # locations as one unit.
    def __eq__(self, other):
        """Test equality by comparing type and value."""
        if not isinstance(other, LiteralILValue):
            return False
        return self.ctype == other.ctype and self.value == other.value

    def __hash__(self):
        """Hash based on type and value."""
        return hash((self.ctype, self.value))


class VariableILValue(ILValue):
    """ILValue that represents a variable.

    offset (int) - Memory offset of this variable, usually positive.

    """

    def __init__(self, ctype, offset):
        """Initialize variable IL value."""
        super().__init__(ILValue.VARIABLE, ctype)
        self.offset = offset


class SymbolTable:
    """Symbol table for the IL -> AST phase.

    This object stores variable name and types, and is mostly used for type
    checking.

    """

    def __init__(self):
        """Initialize symbol table."""
        self.table = dict()

    def lookup(self, name):
        """Look up the identifier with the given name.

        This function returns the ILValue object for the identifier.

        name (str) - Identifier name to search for.

        """
        if name in self.table:
            return self.table[name]
        else:
            # TODO: raise a real exception here
            raise NotImplementedError("unknown identifier")

    def add(self, name, ctype):
        """Add an identifier with the given name and type to the symbol table.

        name (str) - Identifier name to add.
        ctype (CType) - C type of the identifier we're adding.

        """
        if name not in self.table:
            # TODO: use real offsets
            self.table[name] = VariableILValue(ctype, 0)
        else:
            # TODO: raise a real exception here
            raise NotImplementedError("already declared")
