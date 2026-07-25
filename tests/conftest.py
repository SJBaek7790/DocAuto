import sys
from pathlib import Path

# Add scripts directory to sys.path for flat imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
