from __future__ import annotations

from pathlib import Path

from .config import seed_everything


class LocalQwenAgent:
    """Local deterministic Transformers adapter with a structured-output boundary."""

    def __init__(self, model_path: Path, max_new_tokens: int = 512, seed: int = 0) -> None:
        self.model_path = Path(model_path)
        self.max_new_tokens = max_new_tokens
        self.seed = seed
        self._tokenizer = None
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        seed_everything(self.seed)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
        quantization_config = BitsAndBytesConfig(load_in_8bit=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            local_files_only=True,
            torch_dtype=torch.float16,
            quantization_config=quantization_config,
            device_map="auto",
        )

    def generate(self, prompt: str) -> str:
        self._load()
        messages = [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": prompt},
        ]
        text = self._tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)
        import torch

        with torch.inference_mode():
            output = self._model.generate(
                **inputs, max_new_tokens=self.max_new_tokens, do_sample=False
            )
        return self._tokenizer.decode(output[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
