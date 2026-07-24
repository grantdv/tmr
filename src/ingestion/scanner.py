from pathlib import Path
from typing import List


class FileScanner:
    SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

    def __init__(self, input_dir):
        self.input_dir = Path(input_dir)

    def scan(self) -> List[str]:
        if not self.input_dir.exists():
            return []
        files = []
        for path in sorted(self.input_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                files.append(str(path))
        return files
