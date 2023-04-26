import re


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


def get_file_name_with_no_tags(file_name: str) -> str:
    return re.sub('[\(\[].*?[\)\]]', '', file_name.split('.')[0])


def get_file_extension(rom: dict) -> str:
    return rom['file_name'].split('.')[-1] if not rom['multi'] else ''
