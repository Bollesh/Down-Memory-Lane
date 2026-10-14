"""Generates an image with the trained Flux LoRA model on Replicate."""
from functools import lru_cache

import replicate

import config

# Inputs of a Flux LoRA trained with ostris/flux-dev-lora-trainer.
GENERATION_INPUT = {
    "model": "dev",            # "dev" = best quality; "schnell" is faster but rougher
    "lora_scale": 1.0,         # how strongly your face LoRA applies
    "num_outputs": 1,
    "aspect_ratio": "4:5",
    "output_format": "png",
    "guidance_scale": 3.0,
    "num_inference_steps": 28,
}


@lru_cache(maxsize=1)
def model_ref():
    """`owner/name:version` for replicate.run; resolves the latest version if none is pinned."""
    if ":" in config.REPLICATE_MODEL:
        return config.REPLICATE_MODEL
    version = replicate.models.get(config.REPLICATE_MODEL).latest_version
    return f"{config.REPLICATE_MODEL}:{version.id}"


def generate(prompt):
    """Run the model and return the PNG bytes."""
    output = replicate.run(model_ref(), input={**GENERATION_INPUT, "prompt": prompt})
    first = output[0] if isinstance(output, (list, tuple)) else output
    return first.read()
