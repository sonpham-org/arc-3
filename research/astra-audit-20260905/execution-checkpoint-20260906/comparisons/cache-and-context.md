# Full-context cache interpretation

The full-context harness retains complete history blocks until rendered input exceeds the configured allowance, then removes the minimum number of oldest complete blocks needed to fit. There is no lower post-trim target. Because vLLM prefix-cache hashes include the parent prefix, removing an early history block invalidates the later hash chain even when the retained text is unchanged. Near-limit trimming can therefore cause repeated large prefills.

Generated-token allowance and retained input length are different. Images, prompts, tool results, and preserved reasoning all consume the input window. An observed 40-image compatibility fixture used 45,074 input tokens, including 40,960 image tokens, before substantial reasoning history. CPU KV storage can retain more sessions, but it does not raise the server's accepted context length.

The matrix shows the strongest outcome at 43,313 context/11 lanes. The longer-context, lower-lane arms still score well, but none beats it. That pattern can reflect a balance among context retention, game coverage, request batching, and time spent prefilling. It does not establish that excess context directly harms reasoning.

A future hysteresis arm can keep the same overflow trigger but trim to roughly 100–104k rather than barely fitting under a 122,368-token input ceiling. This should amortize prefix rebuilds over more turns, at the cost of dropping more old evidence per trim. It remains untested and should be evaluated at equal time and matched returned-response tokens.
