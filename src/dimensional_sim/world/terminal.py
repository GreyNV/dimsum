"""Terminal adapter: real input/clock here, deterministic simulation everywhere else.

Fixed 20ms simulation ticks are independent of display FPS. Key-repeat pulses hold
movement for 160ms; this is a keyboard adapter policy, not a gameplay rule.
"""
from contextlib import contextmanager
import os
import sys
import time

from .runtime import InputCommand
from .renderer import render, to_ansi, to_text

KEYS = {"w": "north", "d": "east", "s": "south", "a": "west"}


@contextmanager
def keyboard():
    """Yield a nonblocking character reader, restoring terminal state on every exit."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("play requires an interactive terminal; use demo for scripted output")
    if os.name == "nt":
        import msvcrt
        def read():
            chars = []
            while msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):
                    code = msvcrt.getwch()
                    char = {"H": "w", "P": "s", "K": "a", "M": "d"}.get(code, "")
                chars.append(char.lower())
            return chars
        yield read
    else:
        import select
        import termios
        import tty
        fd = sys.stdin.fileno()
        before = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            def read():
                chars = []
                while select.select([sys.stdin], [], [], 0)[0]:
                    chars.append(sys.stdin.read(1).lower())
                return chars
            yield read
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, before)


@contextmanager
def display(plain):
    """Enable Windows VT output when available; always restore console mode/cursor."""
    handle = mode = kernel = None
    if not plain and os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.windll.kernel32
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = kernel.GetStdHandle(-11)
        old = ctypes.c_ulong()
        if kernel.GetConsoleMode(handle, ctypes.byref(old)):
            mode = old.value
            if not kernel.SetConsoleMode(handle, mode | 4):
                plain = True
        else:
            plain = True
    try:
        if not plain:
            sys.stdout.write("\x1b[2J\x1b[?25l")
        yield plain
    finally:
        if not plain:
            sys.stdout.write("\x1b[0m\x1b[?25h\n")
            sys.stdout.flush()
        if mode is not None:
            kernel.SetConsoleMode(handle, mode)


def play(exploration, *, fps=20, plain=False, max_ticks=None):
    """Run until Q/Ctrl-C; max_ticks is an optional deterministic test/diagnostic bound."""
    if type(fps) is not int or not 1 <= fps <= 120:
        raise ValueError("FPS must be 1..120")
    if max_ticks is not None and (type(max_ticks) is not int or max_ticks < 1):
        raise ValueError("tick limit must be positive")
    with keyboard() as read, display(plain) as plain:
        last = time.monotonic_ns()
        accumulated, ticks, next_draw = 0, 0, 0
        move, movement_until, attack_pending = None, 0, False
        try:
            while max_ticks is None or ticks < max_ticks:
                now = time.monotonic_ns()
                accumulated += now - last
                last = now
                for char in read():
                    if char in ("q", "\x03"):
                        return
                    if char in KEYS:
                        move, movement_until = KEYS[char], ticks + 8
                    elif char == " ":
                        attack_pending = True
                while accumulated >= 20_000_000 and (max_ticks is None or ticks < max_ticks):
                    exploration.advance(20, InputCommand(
                        move=move if ticks < movement_until else None, attack=attack_pending))
                    attack_pending = False
                    ticks += 1
                    accumulated -= 20_000_000
                if now >= next_draw:
                    frame = render(exploration)
                    text = to_text(frame) if plain else to_ansi(frame)
                    player = exploration.player
                    status = (f"WASD move | Space attack | Q exit   "
                              f"{player.chunk.dimension} ({player.chunk.x},{player.chunk.y}) "
                              f"facing {player.facing}   ")
                    sys.stdout.write(("" if plain else "\x1b[H") + text + "\n" + status + "\n")
                    sys.stdout.flush()
                    next_draw = now + 1_000_000_000 // fps
                time.sleep(0.002)
        except KeyboardInterrupt:
            return
