"""Backward compatibility wrapper for Streamlit UI."""
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = Path(__file__).resolve().parent

if str(_SRC_DIR) in sys.path:
    sys.path.remove(str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if 'app' in sys.modules and not hasattr(sys.modules['app'], '__path__'):
    del sys.modules['app']

from app.streamlit_app import main

def get_ranker():
    from src.ranker import ResumeRanker
    return ResumeRanker()

def get_skill_extractor():
    from src.skill_extractor import TechnicalSkillExtractor
    return TechnicalSkillExtractor()

if __name__ == '__main__':
    main()
