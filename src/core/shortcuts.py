"""Qt-free keyboard shortcut mapping and dispatch helpers.

The UI layer converts Qt key events into canonical strings; resolution and
dispatch stay here so they can be unit-tested without PySide6 or a display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional


@dataclass(frozen=True)
class ShortcutAction:
    """A single key-to-action binding."""

    key: str
    action_id: str
    description: str
    context: str = "nle"


SHORTCUTS: tuple[ShortcutAction, ...] = (
    ShortcutAction("Space", "play_pause", "Play / pause the monitor"),
    ShortcutAction("Left", "previous_frame", "Step one frame backward"),
    ShortcutAction("Right", "next_frame", "Step one frame forward"),
    ShortcutAction("I", "set_in", "Set In point"),
    ShortcutAction("O", "set_out", "Set Out point"),
    ShortcutAction("U", "clear_trim", "Clear In/Out points"),
    ShortcutAction("S", "split", "Split / razor clip at playhead"),
    ShortcutAction("Delete", "delete", "Delete selected clip"),
    ShortcutAction("Shift+Delete", "ripple_delete", "Ripple delete selected clip"),
    ShortcutAction("V", "select_tool", "Select tool"),
    ShortcutAction("C", "razor_tool", "Razor tool"),
)

_MODIFIER_ALIASES = {
    "control": "Ctrl",
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "meta": "Meta",
    "command": "Meta",
}
_MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Meta")
_KEY_ALIASES = {
    "space": "Space",
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
    "delete": "Delete",
    "del": "Delete",
    "escape": "Esc",
    "esc": "Esc",
    "return": "Enter",
    "enter": "Enter",
}


def normalize_shortcut(sequence: str) -> str:
    """Return a canonical shortcut string (``Ctrl+Shift+S`` style)."""
    pieces = [piece.strip() for piece in str(sequence).split("+") if piece.strip()]
    if not pieces:
        return ""
    modifiers = []
    keys = []
    for piece in pieces:
        canonical = _MODIFIER_ALIASES.get(piece.lower())
        if canonical:
            if canonical not in modifiers:
                modifiers.append(canonical)
        else:
            keys.append(piece)
    modifiers.sort(key=lambda item: _MODIFIER_ORDER.index(item))
    if not keys:
        return "+".join(modifiers)
    key = keys[-1]
    if len(key) == 1 and key.isalpha():
        key = key.upper()
    else:
        key = _KEY_ALIASES.get(key.lower(), key)
    return "+".join(modifiers + [key])


def resolve_shortcut(
    sequence: str,
    context: Optional[str] = "nle",
    bindings: Iterable[ShortcutAction] = SHORTCUTS,
) -> Optional[ShortcutAction]:
    """Resolve a key sequence, preferring the requested context."""
    key = normalize_shortcut(sequence)
    available = tuple(bindings)
    if context is not None:
        scoped = [item for item in available if item.context == context and item.key == key]
        if scoped:
            return scoped[0]
    return next((item for item in available if item.key == key), None)


def is_text_input_class(class_name: str) -> bool:
    """Return whether a Qt widget class receives ordinary text input."""
    name = class_name.lower()
    ignored = (
        "qlineedit",
        "qtextedit",
        "qplaintextedit",
        "qspinbox",
        "qdoublespinbox",
        "qcombobox",
        "qkeysequenceedit",
    )
    return any(token in name for token in ignored)


def dispatch_shortcut(
    action: ShortcutAction, handlers: Dict[str, Callable[[], object]]
) -> bool:
    """Invoke the handler registered for *action*, returning success."""
    handler = handlers.get(action.action_id)
    if handler is None:
        return False
    handler()
    return True
