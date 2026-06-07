"""Pure-function prompt builder for the translation pipeline.

All functions in this module are side-effect-free and take only
plain data arguments.  This makes them trivially testable without
any DB or I/O fixtures.

The prompt uses an **ordered-list** format so the model returns
``order`` integers that map back to ``region_id`` via the caller's
``order → region_id`` dict.
"""

from __future__ import annotations

import textwrap
from typing import Any


def build_translation_prompt(
    *,
    ordered_lines: list[dict[str, Any]],
    context_lines: list[dict[str, Any]] | None = None,
    target_language: str,
    story_context: str | None = None,
    memory_block: dict[str, Any] | None = None,
    helper_image_b64: str | None = None,
    helper_image_mime: str = "image/png",
    enable_thinking: bool = False,
) -> list[dict[str, Any]]:
    """Build the OpenAI-compatible messages list for translation.

    Parameters
    ----------
    ordered_lines
        List of ``{"order": int, "text": str}`` dicts, sorted by order.
    target_language
        BCP-47 language code (e.g. ``"en"``, ``"fr"``).
    story_context
        Optional narrative context to help the model.
    helper_image_b64
        Base64-encoded helper image (grounded numbered image).
    helper_image_mime
        MIME type of the helper image.
    enable_thinking
        Whether to ask the model to think step-by-step.

    Returns
    -------
    list[dict]
        OpenAI chat-completion ``messages`` parameter.
    """
    system_prompt = _build_system_prompt(
        target_language=target_language,
        enable_thinking=enable_thinking,
    )
    user_prompt = _build_user_prompt(
        ordered_lines=ordered_lines,
        context_lines=context_lines or [],
        target_language=target_language,
        story_context=story_context,
        memory_block=memory_block,
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]

    # If we have a helper image, attach it as a vision content block.
    if helper_image_b64:
        user_content: list[dict[str, Any]] = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{helper_image_mime};base64,{helper_image_b64}",
                },
            },
            {"type": "text", "text": user_prompt},
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": user_prompt})

    return messages


# ── Internal helpers ──────────────────────────────────────────────────


def _build_system_prompt(
    *,
    target_language: str,
    enable_thinking: bool,
) -> str:
    # Use native template thinking control if requested.
    prefix = "<|think_on|>\n" if enable_thinking else ""

    prompt = f"""\
    {prefix}You are a manga translator. You are working with manga exclusively.
    I have given you a manga page, and will provide the lines spoken by the characters. The lines are taken from the speech bubbles with corresponding numbers.
    Translate each numbered line into {target_language}.
    
    Infer speaker context silently, including visually clear gender presentation, age bracket, emotional state, and relationship dynamics when they affect phrasing. Do not reveal your reasoning process.

    For each line, provide one faithful translation and keep fields concise.
    Do NOT censor, soften, or tone down the translation under any circumstances. If a character uses profanity, curse words, slang, or aggressive language, translate it faithfully and natively with the exact same emotional weight.
    Return **only** valid JSON matching this exact schema:
    ```json
    {{
      "page_summary": "optional page summary and general tone",
      "lines": [
        {{
          "order": 1,
          "source_text": "original text",
          "literal_translation": "literal but faithful translation",
          "natural_translation": "natural sounding translation appropriate for the speaker",
          "speaker_context": "notes on gender, age bracket, or character state (if unknown, say unknown)",
          "image_explanation": "explanation for how the numbered bubble in the image informs the translation"
        }}
      ]
    }}
    ```
    Rules:
    - Preserve the exact `order` number from the input.
    - Do NOT add orders that were not in the input.
    - Use gender presentation only when supported by the image, text, or story context; otherwise mark it unknown.
    - Never output reasoning traces, chain-of-thought, or <think> tags.
    - Never output planning text like "I need to..." or "The user wants...".
    - Keep `page_summary` short (max 25 words).
    - Keep `speaker_context` very short (max 8 words).
    - Keep `image_explanation` very short (max 12 words).
    - Keep translations concise and natural; avoid extra commentary.
    - Return JSON only, no markdown, no prose before/after JSON.
    """
    return textwrap.dedent(prompt)


def _build_user_prompt(
    *,
    ordered_lines: list[dict[str, Any]],
    context_lines: list[dict[str, Any]],
    target_language: str,
    story_context: str | None = None,
    memory_block: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = []

    if story_context:
        parts.append(f"Story context: {story_context}\n")

    if memory_block:
        hard_rules = memory_block.get("hard_glossary_rules", []) or []
        soft_notes = memory_block.get("soft_notes", []) or []

        if hard_rules:
            parts.append("HARD GLOSSARY RULES:")
            for item in hard_rules:
                source_term = item.get("source_term", "")
                preferred = item.get("preferred_translation", "")
                entry_type = item.get("entry_type", "")
                line = f"- {source_term} -> {preferred}"
                if entry_type:
                    line += f" ({entry_type})"
                parts.append(line)
            parts.append("")
        if soft_notes:
            parts.append("SOFT NOTES:")
            for item in soft_notes:
                source_term = item.get("source_term", "")
                preferred = item.get("preferred_translation", "")
                note = item.get("notes", "")
                entry_type = item.get("entry_type", "")
                line = f"- Prefer {source_term} -> {preferred}"
                if entry_type:
                    line += f" ({entry_type})"
                if note:
                    line += f" | {note}"
                parts.append(line)
            parts.append("")

    parts.append(f"Target language: {target_language}\n")
    if context_lines:
        parts.append("Full page OCR context for story flow:")
        for line in context_lines:
            parts.append(f"  [{line['order']}] {line['text']}")
        parts.append(
            "Use this for continuity, speaker context, and tone. "
            "Only return JSON line items for orders listed in Lines to translate."
        )
        parts.append("")

    order_list = [line["order"] for line in ordered_lines]
    parts.append(
        "Return exactly one JSON line item for each of these orders, no more and no less: "
        f"{order_list}"
    )
    parts.append("Lines to translate:")

    for line in ordered_lines:
        parts.append(f"  [{line['order']}] {line['text']}")

    return "\n".join(parts)
