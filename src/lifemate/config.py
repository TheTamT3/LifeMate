from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    model_path: Path
    asr_model_path: Path
    max_steps: int = 8
    # Tool-call JSON is short; keeping this bounded avoids large KV caches on
    # 16 GB Colab GPUs while leaving enough room for multi-call responses.
    max_new_tokens: int = 128
    context_length: int = 16_384

    def __post_init__(self) -> None:
        if self.max_steps < 1 or self.max_new_tokens < 1:
            raise ValueError("max_steps and max_new_tokens must be positive")
        if self.context_length < 1 or self.context_length > 16_384:
            raise ValueError("context_length must be at most 16,384")


def seed_everything(seed: int) -> None:
    if not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.use_deterministic_algorithms(True, warn_only=True)
    except ImportError:
        pass
