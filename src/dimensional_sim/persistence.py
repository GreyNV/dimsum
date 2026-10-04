"""Data-only RNG serialization, including a restricted schema-one migration."""
import base64
import math
import pickletools
import random


def decode_rng_state(value, *, legacy: bool = False) -> tuple:
    if legacy:
        if not isinstance(value, str) or len(value) > 20_000:
            raise ValueError("invalid legacy RNG state")
        # Old saves used pickle for an integer tuple. Interpret only its data
        # opcodes; never invoke an unpickler, import globals, or call a reducer.
        stack = []
        marker = object()
        stopped = False
        try:
            raw = base64.b64decode(value, validate=True)
            for opcode, arg, _ in pickletools.genops(raw):
                name = opcode.name
                if name in ("PROTO", "FRAME", "MEMOIZE", "BINPUT", "LONG_BINPUT"):
                    continue
                if name == "MARK":
                    stack.append(marker)
                elif name in ("BININT", "BININT1", "BININT2", "LONG1", "LONG4", "BINFLOAT"):
                    stack.append(arg)
                elif name == "NONE":
                    stack.append(None)
                elif name == "EMPTY_TUPLE":
                    stack.append(())
                elif name == "TUPLE":
                    index = next(i for i in range(len(stack) - 1, -1, -1) if stack[i] is marker)
                    items = tuple(stack[index + 1:])
                    stack[index:] = [items]
                elif name in ("TUPLE1", "TUPLE2", "TUPLE3"):
                    size = int(name[-1])
                    if len(stack) < size:
                        raise ValueError("invalid tuple")
                    items = tuple(stack[-size:])
                    stack[-size:] = [items]
                elif name == "STOP":
                    stopped = True
                    break
                else:
                    raise ValueError(f"unsafe legacy RNG opcode: {name}")
            if not stopped or len(stack) != 1:
                raise ValueError("invalid legacy RNG data")
            value = stack[0]
        except (TypeError, ValueError, IndexError, StopIteration) as exc:
            raise ValueError("invalid or unsafe legacy RNG state") from exc
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("invalid RNG state")
    version, words, gaussian = value
    if version != 3 or not isinstance(words, (list, tuple)) or len(words) != 625:
        raise ValueError("invalid RNG state")
    if any(type(word) is not int or not 0 <= word <= 0xFFFFFFFF for word in words[:-1]):
        raise ValueError("invalid RNG words")
    if type(words[-1]) is not int or not 0 <= words[-1] <= 624:
        raise ValueError("invalid RNG index")
    if gaussian is not None and (
        isinstance(gaussian, bool) or not isinstance(gaussian, (int, float))
        or not math.isfinite(gaussian)
    ):
        raise ValueError("invalid RNG gaussian cache")
    state = (3, tuple(words), gaussian)
    random.Random().setstate(state)
    return state
