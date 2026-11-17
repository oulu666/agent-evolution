"""Generation-based evaluation for sequential tool learning."""
from __future__ import annotations

import gc
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from ..metrics import (answers_equal, evaluate_stage_family, joint_success,
                       observations_equal)
from ..tools import (build_calendar_registry, build_db_registry,
                     build_file_registry, build_stats_registry,
                     materialize_sandbox)
from ..utils import (append_jsonl, canonical_json, ensure_dir, gpu_peak_gb,
                     gpu_reset_peak, now_iso, read_jsonl, set_seed)
from .dataset import conversation_text
from .train import load_base_model, load_tokenizer


def load_eval_model(config: Dict[str, Any], adapter_dir: Optional[str] = None):
    from peft import PeftModel
    set_seed(int(config["seed"]))
    tokenizer = load_tokenizer(config)
    tokenizer.padding_side = "left"
    model, _ = load_base_model(config)
    if adapter_dir:
        model = PeftModel.from_pretrained(model, adapter_dir)
    model.eval()
    return model, tokenizer


def _eos_ids(tokenizer) -> List[int]:
    values = [tokenizer.eos_token_id,
              tokenizer.convert_tokens_to_ids("<|im_end|>")]
    result = []
    for value in values:
        if isinstance(value, int) and value >= 0 and value not in result:
            result.append(value)
    return result


def generate_text(model, tokenizer, messages: List[Dict[str, str]],
                  max_new_tokens: int) -> str:
    """Compatibility wrapper retaining the original text-only return value."""
    return generate_with_usage(model, tokenizer, messages, max_new_tokens)[0]


def generate_with_usage(model, tokenizer, messages: List[Dict[str, str]],
                        max_new_tokens: int) -> Tuple[str, Dict[str, Any]]:
    """Run the original greedy generation and count actual model token IDs."""
    started = time.perf_counter()
    text = conversation_text(tokenizer, messages, generation=True)
    encoded = tokenizer(text, return_tensors="pt", add_special_tokens=False)
    encoded = {key: value.to("cuda") for key, value in encoded.items()}
    with torch.no_grad():
        output = model.generate(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            eos_token_id=_eos_ids(tokenizer),
        )
    generated = output[0][encoded["input_ids"].shape[1]:]
    answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
    input_tokens = int(encoded["input_ids"].shape[1])
    output_tokens = int(generated.shape[0])
    return answer, {
        "inference_calls": 1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "generation_seconds": time.perf_counter() - started,
        "batch_size": 1,
    }


def generate_batch_with_usage(model, tokenizer,
                              conversations: List[List[Dict[str, str]]],
                              max_new_tokens: int) -> List[Tuple[str, Dict[str, Any]]]:
    """Opt-in cached, left-padded greedy generation with per-request usage.

    Output counts include the first EOS, but exclude padding after EOS. Input
    counts exclude left padding. Generation time is equally apportioned over
    the batch; inference_calls counts logical requests, not generate batches.
    """
    if not conversations:
        return []
    started = time.perf_counter()
    texts = [conversation_text(tokenizer, messages, generation=True)
             for messages in conversations]
    previous_padding_side = tokenizer.padding_side
    try:
        tokenizer.padding_side = "left"
        encoded = tokenizer(texts, return_tensors="pt", add_special_tokens=False,
                            padding=True)
    finally:
        tokenizer.padding_side = previous_padding_side
    encoded = {key: value.to("cuda") for key, value in encoded.items()}
    eos_ids = _eos_ids(tokenizer)
    with torch.no_grad():
        output = model.generate(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            eos_token_id=eos_ids,
            use_cache=True,
        )
    prompt_width = encoded["input_ids"].shape[1]
    answers = []
    for index in range(len(conversations)):
        token_ids = output[index][prompt_width:].tolist()
        for position, token_id in enumerate(token_ids):
            if token_id in eos_ids:
                token_ids = token_ids[:position + 1]
                break
        answer = tokenizer.decode(token_ids, skip_special_tokens=True).strip()
        input_tokens = int(encoded["attention_mask"][index].sum().item())
        answers.append((answer, {
            "inference_calls": 1,
            "input_tokens": input_tokens,
            "output_tokens": len(token_ids),
            "total_tokens": input_tokens + len(token_ids),
            "batch_size": len(conversations),
        }))
    elapsed = time.perf_counter() - started
    for _, usage in answers:
        usage["generation_seconds"] = elapsed / len(conversations)
        usage["batch_generation_seconds"] = elapsed
    return answers


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        else:
            if character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:index + 1])
                    except ValueError:
                        return None
    return None


def parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    value = extract_json_object(text)
    if not isinstance(value, dict):
        return None
    if "tool" not in value or not isinstance(value.get("arguments"), dict):
        return None
    if not isinstance(value["tool"], str):
        return None
    return value


def parse_final_answer(text: str) -> Tuple[bool, Any]:
    value = extract_json_object(text)
    if not isinstance(value, dict) or "answer" not in value:
        return False, None
    return True, value["answer"]


def _registry_for(family: str, episode: Dict[str, Any], db_path: str,
                  calendar_path: str):
    if family == "file":
        temp = tempfile.TemporaryDirectory()
        sandbox = materialize_sandbox(episode.get("environment", {}).get("files", {}),
                                      temp.name)
        return build_file_registry(sandbox), temp
    if family == "database":
        return build_db_registry(db_path), None
    if family == "python":
        return build_stats_registry(), None
    if family == "calendar":
        return build_calendar_registry(calendar_path), None
    raise ValueError("unknown family: %s" % family)


def evaluate_family(model, tokenizer, episodes: List[Dict[str, Any]],
                    config: Dict[str, Any], stage: Dict[str, Any],
                    output_dir: Path, db_path: str,
                    calendar_path: str) -> Dict[str, Any]:
    """Evaluate using two actual generations per episode, with optional batching.

    ``evaluation.batch_size`` defaults to one, preserving the original greedy
    generation arguments. Values above one opt into left-padding and KV caching
    for both generations. Every final prompt uses the actual registry response
    to the predicted call; expected answers are used only for scoring.
    """
    batch_size = int(config["evaluation"].get("batch_size", 1))
    if batch_size < 1:
        raise ValueError("evaluation.batch_size must be positive")
    ensure_dir(output_dir)
    results_path = output_dir / "results.jsonl"
    if results_path.exists():
        results_path.unlink()
    if not episodes:
        raise ValueError("Empty evaluation split for stage %s" % stage["name"])
    family = episodes[0]["tool_family"]
    gpu_reset_peak()
    started = time.time()
    results = []
    print("eval", stage["name"], family, "n", len(episodes), flush=True)
    for offset in range(0, len(episodes), batch_size):
        batch = episodes[offset:offset + batch_size]
        base_messages = [[episode["messages"][0], episode["messages"][1]]
                         for episode in batch]
        tool_outputs = _generate_evaluation_batch(
            model, tokenizer, base_messages,
            int(config["evaluation"]["max_new_tokens_tool"]), batch_size)
        tool_results = []
        final_messages = []
        for episode, messages, (tool_raw, _) in zip(batch, base_messages, tool_outputs):
            tool_result = _evaluate_tool_prediction(
                episode, tool_raw, db_path, calendar_path)
            tool_results.append(tool_result)
            final_messages.append(messages + [
                {"role": "assistant", "content": tool_raw if tool_raw else "{}"},
                {"role": "user", "content": "TOOL RESULT:\n" + tool_result["observation"]},
            ])
        answer_outputs = _generate_evaluation_batch(
            model, tokenizer, final_messages,
            int(config["evaluation"]["max_new_tokens_answer"]), batch_size)
        for index, (episode, tool_result, tool_output, answer_output) in enumerate(
                zip(batch, tool_results, tool_outputs, answer_outputs)):
            _, tool_usage = tool_output
            answer_raw, answer_usage = answer_output
            answer_parsed, predicted_answer = parse_final_answer(answer_raw)
            final_correct = (answer_parsed and
                             answers_equal(episode["expected_final_answer"], predicted_answer))
            tool_usage["batch_id"] = "%s:%s:tool:%s" % (stage["name"], family, offset)
            answer_usage["batch_id"] = "%s:%s:answer:%s" % (stage["name"], family, offset)
            result = {
                "episode_id": episode["episode_id"],
                "tool_family": episode["tool_family"],
                "skill_labels": episode["skill_labels"],
                "split": episode["split"],
                **tool_result,
                "final_correct": bool(final_correct),
                "answer_raw": answer_raw,
                "predicted_answer": predicted_answer,
                "expected_final_answer": episode["expected_final_answer"],
                "generation_usage": {"tool": tool_usage, "answer": answer_usage},
            }
            result["joint_success"] = joint_success(result)
            for key in ("inference_calls", "input_tokens", "output_tokens",
                        "total_tokens", "generation_seconds"):
                result[key] = tool_usage[key] + answer_usage[key]
            results.append(result)
            append_jsonl(results_path, result)
            position = offset + index + 1
            if position % 10 == 0:
                print("eval", stage["name"], family, position, flush=True)
    report = evaluate_stage_family(results, stage, family, output_dir)
    report["peak_gpu_gb"] = gpu_peak_gb()
    report["duration_seconds"] = round(time.time() - started, 2)
    report["inference_usage"]["duration_seconds"] = report["duration_seconds"]
    report["evaluation_protocol"] = {
        "batch_size": batch_size,
        "do_sample": False,
        "use_cache": True if batch_size > 1 else "model_default",
        "padding_side": "left" if batch_size > 1 else "single_sequence",
        "output_token_count_includes_eos": True,
        "output_token_count_excludes_post_eos_padding": True,
    }
    report["adapter"] = stage.get("adapter")
    from ..utils import write_json
    write_json(output_dir / "stage_report.json", report)
    print("eval done", stage["name"], family,
          "final", report["metrics"]["final_task_success_rate"],
          "peak_gpu_gb", report["peak_gpu_gb"], flush=True)
    return report


def _generate_evaluation_batch(model, tokenizer, conversations,
                               max_new_tokens: int, batch_size: int):
    if batch_size > 1:
        return generate_batch_with_usage(model, tokenizer, conversations, max_new_tokens)
    return [generate_with_usage(model, tokenizer, messages, max_new_tokens)
            for messages in conversations]


def _evaluate_tool_prediction(episode: Dict[str, Any], tool_raw: str,
                              db_path: str, calendar_path: str) -> Dict[str, Any]:
    tool_call = parse_tool_call(tool_raw)
    predicted_tool = tool_call["tool"] if tool_call else None
    predicted_arguments = tool_call["arguments"] if tool_call else {}
    tool_correct = predicted_tool == episode["expected_tool"]
    arguments_correct = (isinstance(predicted_arguments, dict) and
                         answers_equal(episode["expected_arguments"], predicted_arguments))
    registry, temp = _registry_for(episode["tool_family"], episode, db_path, calendar_path)
    try:
        if predicted_tool is None:
            observation = canonical_json({
                "ok": False, "error": "model did not return a valid tool call"})
        else:
            observation = registry.observation(predicted_tool, predicted_arguments)
        execution_success = (predicted_tool is not None and
                             observations_equal(episode["expected_observation"], observation))
    finally:
        if temp is not None:
            temp.cleanup()
    return {
        "tool_correct": bool(tool_correct),
        "arguments_correct": bool(arguments_correct),
        "execution_success": bool(execution_success),
        "predicted_tool": predicted_tool,
        "predicted_arguments": predicted_arguments,
        "tool_call_raw": tool_raw,
        "observation": observation,
        "expected_observation": episode["expected_observation"],
    }


def free_model(model) -> None:
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
