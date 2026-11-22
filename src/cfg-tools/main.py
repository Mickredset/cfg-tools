from cfglib import Config, load_variables, save_variables


class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"


class Player:
    def __init__(self, name, level=1):
        self.name = name
        self.level = level
        self.position = Vector(10, 5)
        self.inventory = ["sword", "potion"]

    def __repr__(self):
        return (
            "Player("
            f"name={self.name!r}, "
            f"level={self.level}, "
            f"position={self.position}, "
            f"inventory={self.inventory}"
            ")"
        )


def main():
    cfg = Config()

    # Обычное значение в стиле твоего cfg.
    cfg.set_object("datatest", "test1", "Fnfjnfj")

    # Объекты.
    player = Player("Hero")
    vector = Vector(3, 4)

    cfg.set_object("objects", "player", player)
    cfg.set_object("objects", "vector", vector)

    # Даже класс можно сохранить как значение.
    cfg.set_object("objects", "player_class", Player)

    cfg.save("example.cfg")

    loaded = Config("example.cfg")

    print("datatest/test1 =", loaded.get_object("datatest", "test1"))
    print("objects/player =", loaded.get_object("objects", "player"))
    print("objects/vector =", loaded.get_object("objects", "vector"))
    print("objects/player_class =", loaded.get_object("objects", "player_class"))

    # Сохраняем кучу переменных, кроме некоторых.
    # Берем глобальные и локальные переменные.
    namespace = {**globals(), **locals()}

    vars_cfg, skipped = save_variables(
        "variables.cfg",
        namespace,
        section="globals",
        exclude={
            "cfg",
            "loaded",
            "vars_cfg",
            "skipped",
            "namespace",
            "main",
        },
        exclude_prefixes=("_",),
    )

    print()
    print("Сохранено переменных в variables.cfg")
    print("Пропущено:", skipped)

    restored = load_variables("variables.cfg", section="globals")

    print()
    print("Восстановленный player из variables.cfg:")
    print(restored.get("player"))


if __name__ == "__main__":
    main()