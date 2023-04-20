
import re

from handler import dbh


def parse_tags(file_name: str) -> tuple:
    reg: str = ''
    rev: str = ''
    other_tags: list = []
    tags: list = re.findall('\(([^)]+)', file_name)
    for tag in tags:
        if tag.split('-')[0].lower() == 'reg':
            try: reg = tag.split('-', 1)[1]
            except IndexError: pass
        elif tag.split('-')[0].lower() == 'rev':
            try: rev = tag.split('-', 1)[1]
            except IndexError: pass
        else:
            other_tags.append(tag)
    return reg, rev, other_tags


def get_file_extension(rom: dict) -> str:
    return rom['file_name'].split('.')[-1] if not rom['multi'] else ''


def rom_exists_db(file_name: str, platform: str) -> int:
    db_roms: list = dbh.get_roms(platform)
    rom_id: int = 0
    for db_rom in db_roms:
        if db_rom.file_name == file_name:
            rom_id = db_rom.id
            break
    return rom_id
