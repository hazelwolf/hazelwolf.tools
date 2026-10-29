# Load env + HF_HOME before anything imports ltx_*_mlx, mlx or huggingface_hub.
from . import config  # noqa: F401
