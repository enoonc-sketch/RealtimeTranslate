"""小宠物名单（id、名字、emoji）。想加新宠物：这里加一行 + tools/pet_render 里加造型并重新渲染。"""

PETS = [
    ("cat", "猫咪", "🐱"), ("dog", "小狗", "🐶"), ("bunny", "兔兔", "🐰"),
    ("bear", "小熊", "🐻"), ("panda", "熊猫", "🐼"), ("fox", "狐狸", "🦊"),
    ("tiger", "小老虎", "🐯"), ("pig", "小猪", "🐷"), ("hamster", "仓鼠", "🐹"),
    ("chick", "小鸡", "🐥"), ("duck", "小鸭", "🦆"), ("penguin", "企鹅", "🐧"),
    ("frog", "青蛙", "🐸"), ("dino", "小恐龙", "🦖"), ("unicorn", "独角兽", "🦄"),
    ("slime", "史莱姆", "🟢"), ("ghost", "小幽灵", "👻"), ("robot", "机器人", "🤖"),
]
DEFAULT_PET = "cat"
PET_MODES = {"minimized": "最小化 / 隐藏时显示", "always": "一直显示", "off": "不显示"}


def pet_ids():
    return [p[0] for p in PETS]


def pet_name(pid):
    for i, n, _ in PETS:
        if i == pid:
            return n
    return pid


def pet_display(pid):
    for i, n, e in PETS:
        if i == pid:
            return "%s %s" % (e, n)
    return pid
