"""Bounded CPU token counting through the same vLLM chat renderer as inference."""
from collections import OrderedDict
import hashlib
import json
import time

import requests


class FullContextTokens:
    def __init__(self, base_url, model, context, headers, emit=None, session=None):
        base = base_url.rstrip('/')
        self.url = (base[:-3] if base.endswith('/v1') else base) + '/tokenize'
        self.model, self.context, self.headers, self.emit = model, context, dict(headers), emit
        self.session = session if session is not None else requests.Session()
        self.cache = OrderedDict()

    def count(self, messages, tools, thinking):
        # Match ChatCompletionRequest._normalize_messages_before. /tokenize
        # lacks this alias normalization; otherwise it silently omits old
        # reasoning_content while inference includes it. Never mutate history.
        normalized = []
        for message in messages:
            item = dict(message)
            reasoning = item.pop('reasoning_content', None)
            if reasoning is not None and item.get('reasoning') is None:
                item['reasoning'] = reasoning
            if item.get('tool_calls') is not None and not isinstance(item['tool_calls'], list):
                item['tool_calls'] = list(item['tool_calls'])
            normalized.append(item)
        payload = {'model': self.model, 'messages': normalized, 'add_generation_prompt': True,
                   'chat_template_kwargs': {'enable_thinking': bool(thinking)}}
        if tools:
            payload['tools'] = tools
        # Tool-schema dictionary order is rendered into the prompt. Sorting
        # nested keys would tokenize a different prompt than inference sends.
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        key = hashlib.sha256(raw).hexdigest()
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        started = time.monotonic()
        # /tokenize renders text, tools and image placeholders on CPU. It does
        # not generate tokens. Failed counts never fall back to JSON byte size.
        response = self.session.post(self.url, data=raw, headers=self.headers, timeout=15)
        response.raise_for_status()
        if len(response.content) > 8 * 1024**2:
            raise ValueError('Tokenizer response exceeded the bounded size')
        data = response.json()
        count, maximum = data.get('count'), data.get('max_model_len')
        if type(count) is not int or count < 0 or type(maximum) is not int or maximum < self.context:
            raise ValueError('Tokenizer did not confirm the requested context and count')
        self.cache[key] = count
        while len(self.cache) > 8:
            self.cache.popitem(last=False)
        if self.emit:
            self.emit('context_tokens', tokens=count, messages=len(messages), elapsed=time.monotonic()-started,
                      context=self.context, request_fingerprint=key)
        return count
