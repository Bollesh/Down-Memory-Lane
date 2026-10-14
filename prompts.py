"""Turns a casual request ("my 5-year-old self on a beach") into a full image prompt.

The LoRA only shows *you* when the prompt contains its trigger word, and the
photos look believable when the age and photo style are spelled out. Users
shouldn't have to know either, so this module adds them.
"""
import re

STYLE = ("realistic candid family photograph, natural light, "
         "shot on 35mm film, soft film grain, nostalgic")

# "my 5-year-old self", "your 2 year old self", "myself", "me", ...
_SELF_WITH_AGE = re.compile(
    r"\b(?:my|your)\s+(\d{1,2})\s*-?\s*(?:years?|yrs?)\s*-?\s*old\s+self\b", re.I)
_SELF = re.compile(r"\b(?:my\s*self|your\s*self|me)\b", re.I)
# "5 years old", "5-year-old", "age 5", "aged 5", "at 5"
_AGE_PHRASES = [
    re.compile(r"\b(\d{1,2})\s*-?\s*(?:years?|yrs?)\s*-?\s*old\b", re.I),
    re.compile(r"\b(?:at\s+)?aged?\s+(\d{1,2})\b", re.I),
    re.compile(r"\bat\s+(\d{1,2})\b", re.I),
]
_LEADING_FILLER = re.compile(r"^(?:a\s+)?(?:photo|picture|image)\s+of\s+", re.I)
_POSSESSIVE = re.compile(r"\b(?:my|your|our)\b", re.I)


def extract_age(description):
    """(age or None, description with the age/self phrase removed)."""
    m = _SELF_WITH_AGE.search(description)
    if m:
        return int(m.group(1)), description[:m.start()] + description[m.end():]
    for pattern in _AGE_PHRASES:
        m = pattern.search(description)
        if m:
            return int(m.group(1)), description[:m.start()] + description[m.end():]
    return None, description


def age_phrase(age):
    if age is None:
        return ""
    if age <= 3:
        return f"as a {age}-year-old toddler"
    if age <= 12:
        return f"as a {age}-year-old child"
    if age <= 19:
        return f"as a {age}-year-old teenager"
    return f"at age {age}"


def clean_scene(text):
    text = _LEADING_FILLER.sub("", text.strip())
    text = _SELF.sub("", text)
    text = _POSSESSIVE.sub("the", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,.-")


def build_prompt(description, trigger_word):
    """Full prompt for the Flux LoRA model."""
    age, rest = extract_age(description)
    scene = clean_scene(rest)
    subject = " ".join(p for p in (f"a photo of {trigger_word}", age_phrase(age)) if p)
    return f"{subject}, {scene}, {STYLE}" if scene else f"{subject}, {STYLE}"
