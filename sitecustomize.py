# This file is automatically imported by Python's site module if present on sys.path.
# It allows us to set global warning filters very early, before any third-party libraries are imported.
import warnings

# Suppress noisy UserWarning emitted by langsmith when using Pydantic V1 on Python 3.14+
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module=r"langsmith\.schemas"
)
