import ast
import struct
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


def parse_po(path):
    """解析简单的 .po 文件（不含复数和上下文），返回 {msgid: msgstr}。"""
    entries = {}
    msgid = msgstr = None
    current = None

    def flush():
        if msgid is not None and msgstr is not None:
            entries[msgid] = msgstr

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            msgid, msgstr, current = ast.literal_eval(line[6:]), None, "id"
        elif line.startswith("msgstr "):
            msgstr, current = ast.literal_eval(line[7:]), "str"
        elif line.startswith('"'):
            text = ast.literal_eval(line)
            if current == "id":
                msgid += text
            else:
                msgstr += text
    flush()
    return entries


def write_mo(entries, path):
    """按 GNU gettext 的 .mo 格式写出（与 msgfmt 输出兼容）。"""
    keys = sorted(entries)
    ids = [key.encode("utf-8") for key in keys]
    strs = [entries[key].encode("utf-8") for key in keys]

    header_size = 7 * 4
    table_size = len(keys) * 8
    ids_offset = header_size + 2 * table_size
    strs_offset = ids_offset + sum(len(item) + 1 for item in ids)

    id_table, str_table = [], []
    offset = ids_offset
    for item in ids:
        id_table += [len(item), offset]
        offset += len(item) + 1
    offset = strs_offset
    for item in strs:
        str_table += [len(item), offset]
        offset += len(item) + 1

    output = struct.pack(
        "Iiiiiii",
        0x950412DE,
        0,
        len(keys),
        header_size,
        header_size + table_size,
        0,
        0,
    )
    output += struct.pack(f"{len(id_table)}i", *id_table)
    output += struct.pack(f"{len(str_table)}i", *str_table)
    output += b"".join(item + b"\0" for item in ids)
    output += b"".join(item + b"\0" for item in strs)
    path.write_bytes(output)


class Command(BaseCommand):
    help = "把 LOCALE_PATHS 中的 .po 编译为 .mo（不依赖 GNU gettext）"

    def handle(self, *args, **options):
        for locale_path in settings.LOCALE_PATHS:
            for po_path in Path(locale_path).glob("*/LC_MESSAGES/*.po"):
                mo_path = po_path.with_suffix(".mo")
                write_mo(parse_po(po_path), mo_path)
                self.stdout.write(f"已编译：{mo_path}")
