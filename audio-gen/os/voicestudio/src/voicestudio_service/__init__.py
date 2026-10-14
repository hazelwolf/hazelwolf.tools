# Load env + data/cache dirs before anything imports upstream, torch or huggingface_hub.
from . import config  # noqa: F401
