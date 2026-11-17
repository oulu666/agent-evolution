"""Chat tokenization with assistant-only labels."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

try:
    from torch.utils.data import Dataset
except Exception:  # CPU smoke tests do not need torch
    class Dataset:  # type: ignore
        pass

ASSISTANT_HEADER = "<|im_start|>assistant\n"
ASSISTANT_HEADER_SHORT = "<|im_start|>assistant"
IM_END = "<|im_end|>"


def _manual_chat(messages: Sequence[Dict[str, str]], generation: bool = False) -> str:
    parts = []
    for message in messages:
        parts.append("<|im_start|>%s\n%s<|im_end|>\n"
                     % (message["role"], message["content"]))
    if generation:
        parts.append("<|im_start|>assistant\n")
    return "".join(parts)


def conversation_text(tokenizer: Any, messages: Sequence[Dict[str, str]],
                      generation: bool = False) -> str:
    if getattr(tokenizer, "chat_template", None):
        try:
            return tokenizer.apply_chat_template(
                list(messages), tokenize=False, add_generation_prompt=generation,
                enable_thinking=False)
        except TypeError:
            try:
                return tokenizer.apply_chat_template(
                    list(messages), tokenize=False, add_generation_prompt=generation)
            except Exception:
                pass
        except Exception:
            pass
    return _manual_chat(messages, generation=generation)


def _find_all(sequence: Sequence[int], subsequence: Sequence[int]) -> List[int]:
    if not subsequence:
        return []
    limit = len(sequence) - len(subsequence) + 1
    return [index for index in range(max(0, limit))
            if list(sequence[index:index + len(subsequence)]) == list(subsequence)]


def assistant_spans(input_ids: Sequence[int], tokenizer: Any) -> List[tuple]:
    header_ids = tokenizer.encode(ASSISTANT_HEADER, add_special_tokens=False)
    starts = _find_all(input_ids, header_ids)
    if not starts:
        short_ids = tokenizer.encode(ASSISTANT_HEADER_SHORT, add_special_tokens=False)
        starts = _find_all(input_ids, short_ids)
        header_length = len(short_ids)
    else:
        header_length = len(header_ids)
    if not starts:
        raise ValueError("Could not find an assistant header in the tokenized chat. "
                         "Check the tokenizer chat template.")
    end_id = tokenizer.convert_tokens_to_ids(IM_END)
    spans = []
    for start in starts:
        content_start = start + header_length
        content_end = len(input_ids)
        for index in range(content_start, len(input_ids)):
            if input_ids[index] == end_id:
                content_end = index + 1  # include <|im_end|>
                break
        spans.append((content_start, content_end))
    return spans


def tokenize_episode(episode: Dict[str, Any], tokenizer: Any,
                     max_length: int) -> Dict[str, Any]:
    messages = episode["messages"]
    text = conversation_text(tokenizer, messages, generation=False)
    encoded = tokenizer(text, add_special_tokens=False, truncation=True,
                        max_length=max_length, return_attention_mask=False)
    input_ids = list(encoded["input_ids"])
    labels = [-100] * len(input_ids)
    spans = assistant_spans(input_ids, tokenizer)
    for start, end in spans:
        start = min(start, len(input_ids))
        end = min(end, len(input_ids))
        for index in range(start, end):
            labels[index] = input_ids[index]
    if not any(label != -100 for label in labels):
        raise ValueError("No assistant tokens were labeled for %s" % episode["episode_id"])
    return {"input_ids": input_ids,
            "attention_mask": [1] * len(input_ids),
            "labels": labels}


class ChatDataset(Dataset):
    def __init__(self, rows: List[Dict[str, Any]], tokenizer: Any,
                 max_length: int) -> None:
        self.rows = rows
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> Dict[str, Any]:
        return tokenize_episode(self.rows[index], self.tokenizer, self.max_length)


class DataCollator:
    def __init__(self, tokenizer: Any) -> None:
        self.pad_token_id = tokenizer.pad_token_id
        if self.pad_token_id is None:
            self.pad_token_id = tokenizer.eos_token_id

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        import torch
        max_length = max(len(feature["input_ids"]) for feature in features)
        input_ids = []
        attention_mask = []
        labels = []
        for feature in features:
            padding = max_length - len(feature["input_ids"])
            input_ids.append(feature["input_ids"] + [self.pad_token_id] * padding)
            attention_mask.append(feature["attention_mask"] + [0] * padding)
            labels.append(feature["labels"] + [-100] * padding)
        return {"input_ids": torch.tensor(input_ids, dtype=torch.long),
                "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
                "labels": torch.tensor(labels, dtype=torch.long)}
