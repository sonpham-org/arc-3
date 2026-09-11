"""
Author: Claude Opus 5 (Bubba)
Date: 11-September-2026
PURPOSE: Measure how the ARC-3 ASCII board encoding's character table affects token
count. Renders a synthetic 64x64 board shaped like bp35 (black field, sky-blue rooms,
green blocks, grey speckle) under several 16-char colour tables and reports tokens per
board. Exists because the choice of WHICH characters carry the common colours changes
cost by >2x under BPE: vocabularies contain long merged runs of separator characters
(- = . # *) but not of most letters, so repeated-cell runs compress very differently.
NOTE: uses tiktoken o200k_base as a stand-in. Qwen3.8-Flash-Next uses a different
tokenizer; re-run against the real one before acting on absolute numbers.
SRP/DRY check: Pass - no existing token-cost benchmark for the board encoding; the
encoder itself lives in ARC3-Inference/inference/utils/grid_utils.py and is not duplicated
here (only its output shape is reproduced).
"""
import random
import tiktoken

ENC = tiktoken.get_encoding("o200k_base")

SCHEMES = {
    "current (grid_utils.ARC_COLOR_CHARS)": "WwgGcBMPRbSYOrNp",
    "ordinal Z..K descending":              "ZYXWVUTSRQPONMLK",
    "hybrid: symbols on greys/background":  ".-=#*/_+MPRbSYON",
    "all-symbol":                           ".-=#*/_+~%Xaflo:",
}


def sample_board(seed: int = 11) -> list[list[int]]:
    """A 64x64 board with the colour mix a real ARC-3 level tends to have."""
    random.seed(seed)
    grid = [[5] * 64 for _ in range(64)]
    for (r0, c0, r1, c1) in [(6, 12, 30, 40), (34, 8, 58, 52), (4, 44, 26, 60)]:
        for r in range(r0, r1):
            for c in range(c0, c1):
                grid[r][c] = 10
    for r in range(10, 14):
        for c in range(16, 36, 5):
            for k in range(3):
                grid[r][c + k] = 14
    for _ in range(700):
        r, c = random.randrange(64), random.randrange(64)
        if grid[r][c] == 5:
            grid[r][c] = 3
    grid[40][24], grid[40][25] = 9, 11
    return grid


def render(grid: list[list[int]], table: str) -> str:
    return "\n".join("".join(table[v] for v in row) for row in grid)


def main() -> None:
    grid = sample_board()
    baseline = None
    for name, table in SCHEMES.items():
        tokens = len(ENC.encode(render(grid, table)))
        baseline = baseline or tokens
        print(f"{tokens:6d} tokens  {tokens / baseline:.2f}x  {name}  [{table}]")


if __name__ == "__main__":
    main()
