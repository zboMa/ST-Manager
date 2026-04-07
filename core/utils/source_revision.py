import os


def build_file_source_revision(path: str) -> str:
    try:
        stat = os.stat(path)
    except OSError:
        return ''
    return f'{int(stat.st_mtime_ns)}:{int(stat.st_size)}'
