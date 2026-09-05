"""Compact, informational request budgets; no stopping or scheduling policy."""
from __future__ import annotations

from copy import deepcopy
import math
import re

_TIME = r'(?:[0-9]+s|unknown)'
_OWN_LINE = (
    rf'\[Runtime budget\] time left {_TIME} \(game {_TIME}, suite {_TIME}\); '
    r'reported generated [0-9]+/[0-9]+ soft target\.'
)
_REMINDER = re.compile(rf'\n{_OWN_LINE}(?=\n|$)|\A{_OWN_LINE}(?:\n|$)')


def _remaining(value):
    if type(value) not in (int, float):
        return None
    try:
        value = float(value)
    except (OverflowError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _strip_text(text):
    # Repeat only to handle adjacent copies without consuming any other line.
    while True:
        cleaned = _REMINDER.sub('', text)
        if cleaned == text:
            return cleaned
        text = cleaned


def strip_reminders(messages):
    """Copy messages and remove only this module's canonical user reminder text."""
    copied = deepcopy(messages)
    for message in copied:
        if not isinstance(message, dict) or message.get('role') != 'user':
            continue
        content = message.get('content')
        if isinstance(content, str):
            message['content'] = _strip_text(content)
        elif isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str):
                    old = part['text']
                    part['text'] = _strip_text(old)
                    if old != part['text'] and not part['text'] and set(part) == {'type', 'text'}:
                        continue
                parts.append(part)
            message['content'] = parts
    return copied


class BudgetReminder:
    def __init__(self, target_tokens=108000):
        if type(target_tokens) is not int or target_tokens <= 0:
            raise ValueError('target_tokens must be a positive integer soft target')
        self.target_tokens = target_tokens
        self.emitted_count = 0

    def prepare(self, messages, *, status, generated_tokens):
        if type(generated_tokens) is not int or generated_tokens < 0:
            raise ValueError('generated_tokens must be a nonnegative reported integer')
        status = status if isinstance(status, dict) else {}
        game = _remaining(status.get('game_remaining_seconds'))
        suite = _remaining(status.get('suite_remaining_seconds'))
        available = [value for value in (game, suite) if value is not None]
        effective = min(available) if available else None
        display = lambda value: 'unknown' if value is None else f'{math.floor(value)}s'
        line = (f'[Runtime budget] time left {display(effective)} '
                f'(game {display(game)}, suite {display(suite)}); '
                f'reported generated {generated_tokens}/{self.target_tokens} soft target.')
        copied = strip_reminders(messages)
        user = next((message for message in reversed(copied)
                     if isinstance(message, dict) and message.get('role') == 'user'), None)
        emitted = False
        if user is not None:
            content = user.get('content')
            if isinstance(content, str):
                user['content'] = content + '\n' + line
                emitted = True
            elif isinstance(content, list):
                content.append({'type': 'text', 'text': line})
                emitted = True
        self.emitted_count += int(emitted)
        return copied, {
            'emitted': emitted, 'emitted_count': self.emitted_count, 'text': line if emitted else None,
            'game_remaining_seconds': game, 'suite_remaining_seconds': suite,
            'effective_remaining_seconds': effective, 'generated_tokens_reported': generated_tokens,
            'target_tokens': self.target_tokens,
        }
