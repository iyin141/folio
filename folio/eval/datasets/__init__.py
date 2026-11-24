from .models import Question, gutenberg_id_from_url  # noqa: F401
from .narrativeqa import load_narrativeqa  # noqa: F401
from .quality import load_quality  # noqa: F401

LOADERS = {"narrativeqa": load_narrativeqa, "quality": load_quality}
