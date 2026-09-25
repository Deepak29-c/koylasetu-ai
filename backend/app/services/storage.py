"""Original files on local disk: STORAGE_DIR/originals/<sha[:2]>/<sha>.<ext>."""

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

CHUNK = 1024 * 1024


class FileTooLarge(Exception):
    pass


@dataclass
class TempUpload:
    path: Path
    sha256: str
    size: int


def storage_root() -> Path:
    return Path(get_settings().storage_dir)


async def save_temp(upload: UploadFile) -> TempUpload:
    """Stream the upload to a temp file while hashing it and enforcing the size limit."""
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    tmp_dir = storage_root() / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / uuid.uuid4().hex
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("wb") as out:
            while block := await upload.read(CHUNK):
                size += len(block)
                if size > max_bytes:
                    raise FileTooLarge
                digest.update(block)
                out.write(block)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return TempUpload(path, digest.hexdigest(), size)


def move_to_originals(tmp: TempUpload, ext: str) -> Path:
    dest = storage_root() / "originals" / tmp.sha256[:2] / f"{tmp.sha256}.{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(tmp.path, dest)
    return dest
