# Load env + cache dirs (HF_HOME, TORCH_HOME) before any submodule imports torch / huggingface_hub.
from . import config  # noqa: F401
