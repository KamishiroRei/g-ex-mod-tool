"""Read-only projections for the inspector editor and explicit config edits.

Game definitions remain the source of resources, public drives and facts.
Only the inspector configuration is changed by the set_* methods.
"""

from __future__ import annotations

import copy
import math
import os
from pathlib import Path

from .model import Project, _excluded, _object, _pool_key, _read_json, _references, _rows, _unpack


_ENTRY_FIELDS = {"id", "title", "description", "resources", "drives", "attributes"}
_DRIVE_FIELDS = {"title", "description", "attributes"}
_MISSING = object()
_HIDDEN_FIELDS = ("发射方式", "连射类型", "觉醒倍率", "每次耗弹", "每次开火耗弹",
                  "每枪口弹体", "出弹次数", "出弹时机", "出弹基础间隔", "重发基础间隔", "点射次数")
_ATTACK_FIELDS = (
    (("基础威力", "单枚基础威力", "威力"), "威力"),
    (("DP伤害",), "冲击力"),
    (("最大飞行距离", "射程", "攻击距离"), "射程"),
    (("爆炸半径", "范围"), "范围"),
    (("射速",), "射速"),
    (("击穿DP伤害",), "击穿冲击力"),
    (("驱动暴击率",), "暴击率"),
    (("贯穿",), "贯穿"),
)


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return int(result) if result.is_integer() else result


def _scalar(value):
    value = _unpack(value)
    return value if isinstance(value, (str, int, float, bool)) else None


def _struct(value):
    """Read the flat keys of a reflected struct without confusing nested keys."""
    value = _unpack(value)
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    value = value.strip()
    if not value.startswith("(") or not value.endswith(")"):
        return {}
    result, chunks, start, depth, quoted, escape = {}, [], 1, 0, False, False
    for index in range(1, len(value) - 1):
        char = value[index]
        if escape:
            escape = False
        elif char == "\\" and quoted:
            escape = True
        elif char == '"':
            quoted = not quoted
        elif not quoted:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                chunks.append(value[start:index])
                start = index + 1
    chunks.append(value[start:-1])
    for chunk in chunks:
        key, separator, raw = chunk.partition("=")
        if separator:
            result[key.strip()] = raw.strip().strip('"')
    return result


def _info(document):
    return _object(_object(document.get("part")).get("partInfo"))


def _drive(document):
    return _object(_object(document.get("part")).get("drive"))


def _properties(document):
    return _object(_drive(document).get("properties"))


def _runtime_class(document):
    return str(_object(document.get("runtime")).get("class", ""))


def _public(document):
    visible = _scalar(_properties(document).get("bPubliclyVisible", True))
    return visible is not False and str(visible).casefold() not in {"false", "0"}


def _type(document):
    properties = _properties(document)
    explicit = _scalar(properties.get("DisplayType"))
    if explicit in {"Melee", "Shooting", "Special"}:
        return explicit
    class_name = _runtime_class(document)
    if class_name.endswith(".MainDrive"):
        return "Shooting" if _scalar(properties.get("MainDriveFireType")) == "Shoot" else "Melee"
    if class_name.endswith(".ShootingDrive"):
        return "Shooting"
    if class_name.endswith(".FightingDrive"):
        return "Melee"
    return "Special"


def _title(document, fallback):
    value = _info(document).get("displayName")
    return value if isinstance(value, str) and value else fallback


def _description(document):
    value = _info(document).get("description")
    return value if isinstance(value, str) else ""


def _row(title, source, value, unit, origin, group="attack"):
    return {"title": title, "source": source, "value": value, "unit": unit,
            "group": group, "hidden": False, "origin": origin, "automatic": True}


def _merge_fields(existing, replacement, known):
    result = {key: copy.deepcopy(value) for key, value in _object(existing).items() if key not in known}
    result.update(copy.deepcopy(_object(replacement)))
    return result


def _copy(value):
    return _MISSING if value is _MISSING else copy.deepcopy(value)


def _entry_map(items):
    if not isinstance(items, list):
        return None
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in result:
            return None
        result[item["id"]] = item
    return result


def _merge_entries(base, local, disk, path, conflicts):
    base_map, local_map, disk_map = _entry_map(base), _entry_map(local), _entry_map(disk)
    if base_map is None or local_map is None or disk_map is None:
        conflicts.append(".".join(path))
        return _copy(local)
    ids = list(dict.fromkeys([*base_map, *disk_map, *local_map]))
    merged = {}
    for entry_id in ids:
        value = _merge_three(base_map.get(entry_id, _MISSING), local_map.get(entry_id, _MISSING),
                             disk_map.get(entry_id, _MISSING), (*path, entry_id), conflicts)
        if value is not _MISSING:
            merged[entry_id] = value
    common = set(base_map) & set(local_map) & set(disk_map)
    base_order = [key for key in base_map if key in common]
    local_order = [key for key in local_map if key in common]
    disk_order = [key for key in disk_map if key in common]
    local_reordered = local_order != base_order
    disk_reordered = disk_order != base_order
    if local_reordered and disk_reordered and local_order != disk_order:
        conflicts.append(".".join((*path, "顺序")))
    preferred = list(local_map) if local_reordered else list(disk_map)
    order = list(dict.fromkeys([*preferred, *local_map, *disk_map, *base_map]))
    return [merged[key] for key in order if key in merged]


def _merge_three(base, local, disk, path, conflicts):
    if local == base:
        return _copy(disk)
    if disk == base or local == disk:
        return _copy(local)
    if isinstance(local, dict) and isinstance(disk, dict) and (base is _MISSING or isinstance(base, dict)):
        base_map = {} if base is _MISSING else base
        keys = list(dict.fromkeys([*base_map, *disk, *local]))
        result = {}
        for key in keys:
            value = _merge_three(base_map.get(key, _MISSING), local.get(key, _MISSING),
                                 disk.get(key, _MISSING), (*path, str(key)), conflicts)
            if value is not _MISSING:
                result[key] = value
        return result
    if (len(path) >= 3 and path[0] == "parts" and path[-1] == "entries"
            and isinstance(local, list) and isinstance(disk, list)
            and (base is _MISSING or isinstance(base, list))):
        return _merge_entries([] if base is _MISSING else base, local, disk, path, conflicts)
    conflicts.append(".".join(path))
    return _copy(local)


def _project_override(available, override):
    if override is None:
        return copy.deepcopy(available)
    indexed = {}
    for fact in available:
        indexed.setdefault(fact.get("source", ""), fact)
        indexed.setdefault(fact.get("title", ""), fact)
    result = []
    for spec in _rows(override):
        if not isinstance(spec, dict):
            continue
        source = spec.get("source") if isinstance(spec.get("source"), str) else ""
        title = spec.get("title") if isinstance(spec.get("title"), str) else source
        if any(hidden in source or hidden in title for hidden in _HIDDEN_FIELDS):
            continue
        original = indexed.get(source, {}) if source else {}
        manual = "value" in spec
        value = spec.get("value") if manual else original.get("value")
        result.append({
            "title": title, "source": source, "value": value,
            "unit": spec.get("unit", original.get("unit", "")),
            "group": spec.get("group", "regular"), "hidden": bool(spec.get("hidden", False)),
            "origin": "手动填写" if manual else original.get("origin", "来源尚未解析"),
            "automatic": False,
        })
    return result


class Catalog:
    def __init__(self, project):
        self.project = project
        self._presentation = None
        self._rules = {}
        self._rule_ids = set()
        self._entries_cache = {}

    def _part_document(self, part_id):
        return _object(self.project.part_documents.get(part_id))

    def _drive_document(self, drive_id):
        return _object(self.project.drive_documents.get(drive_id))

    def _participants(self, part_id):
        part = _object(self._part_document(part_id).get("part"))
        result = []
        for raw in _rows(part.get("drives")):
            if not isinstance(raw, str) or not raw or raw == "None":
                continue
            definition = self.project.drive_classes.get(raw)
            if definition is None:
                short = raw.rsplit(".", 1)[-1].removesuffix("_C")
                definition = short if short in self.project.drive_documents else None
            if definition and definition not in result:
                result.append(definition)
        for definition in _rows(part.get("connectedPartDefinitionIds")):
            if definition in self.project.drive_documents and definition not in result:
                result.append(definition)
        return result

    def _public_drives(self, part_id):
        return [key for key in self._participants(part_id) if _public(self._drive_document(key))]

    def _costs(self, part_id):
        part = _object(self._part_document(part_id).get("part"))
        return [cost for cost in _rows(part.get("costs")) if isinstance(cost, dict)]

    def _cost_title(self, part_id, cost):
        title = cost.get("displayName")
        if isinstance(title, str) and title:
            return title
        key = _pool_key(cost)
        public, hidden = [], []
        for drive_id in self._participants(part_id):
            document = self._drive_document(drive_id)
            requests = _rows(_object(_drive(document).get("driveCost")).get("costs"))
            if any(isinstance(item, dict) and _pool_key(item)[:2] == key[:2] for item in requests):
                names = public if _public(document) else hidden
                name = _title(document, drive_id)
                if name not in names:
                    names.append(name)
        if public or hidden:
            return " / ".join(public or hidden)
        names = [str(item.get("resourceTag", "")).rsplit(".", 1)[-1]
                 for item in _rows(cost.get("resources")) if isinstance(item, dict)]
        return " / ".join(dict.fromkeys(name for name in names if name)) or str(cost.get("costTag", ""))

    def _resource(self, part_id, cost, resource):
        tag = str(resource.get("resourceTag", ""))
        origin = f"{part_id} / {cost.get('costTag', '')} / {tag}"
        if tag == "消耗.资源.过热" and resource.get("costType") == "Heat":
            value = _number(resource.get("overheatRecoverSpeed"))
            if value is None or value <= 0:
                value = _number(resource.get("recoverSpeed"))
            if resource.get("recoverType") != "Auto" or value is None or value <= 0:
                value = None
            return {"tag": tag, "title": "过热冷却", "value": value, "unit": "s", "origin": origin}
        title, unit = {
            "消耗.资源.子弹": ("弹药", "发"),
            "消耗.资源.EN": ("EN", ""),
            "消耗.资源.出力": ("出力", ""),
            "消耗.资源.觉醒槽": ("SP", ""),
        }.get(tag, (tag.rsplit(".", 1)[-1], ""))
        return {"tag": tag, "title": title, "value": _number(resource.get("capacityMax")),
                "unit": unit, "origin": origin}

    def _visible_resource(self, part_id, cost, resource):
        tag = resource.get("resourceTag")
        if (tag != "消耗.资源.过热" or resource.get("costType") != "Heat"
                or not str(cost.get("class", "")).endswith(".CostManagerObject_Weapon")):
            return True
        pool = _pool_key(cost)[:2]
        for drive_id in self._participants(part_id):
            drive = _drive(self._drive_document(drive_id))
            for request in _rows(_object(drive.get("driveCost")).get("costs")):
                if not isinstance(request, dict) or _pool_key(request)[:2] != pool:
                    continue
                for usage in _rows(request.get("resources")):
                    if isinstance(usage, dict) and usage.get("tag") == tag:
                        value = _number(usage.get("value"))
                        if value is not None and value > 0:
                            return True
        return False

    def parts(self):
        result = []
        for part_id, metadata in self.project.parts.items():
            document = self._part_document(part_id)
            if not document and part_id not in self.project.data["parts"]:
                continue
            fallback = _object(metadata).get("name") or part_id
            result.append({"id": part_id, "title": _title(document, fallback),
                           "description": _description(document), "available": bool(document)})
        return result

    def part(self, part_id):
        document = self._part_document(part_id)
        costs = []
        for cost in self._costs(part_id):
            tag = cost.get("costTag")
            if not isinstance(tag, str) or not tag or tag == "None":
                continue
            resources = [self._resource(part_id, cost, row) for row in _rows(cost.get("resources"))
                         if isinstance(row, dict) and self._visible_resource(part_id, cost, row)]
            costs.append({"id": tag, "title": self._cost_title(part_id, cost), "resources": resources})
        fallback = _object(self.project.parts.get(part_id)).get("name") or part_id
        return {"id": part_id, "title": _title(document, fallback),
                "description": _description(document), "costs": costs, "drives": self._public_drives(part_id)}

    def _entry_title(self, part_id, entry):
        title = entry.get("title")
        if isinstance(title, str) and title:
            return title
        wanted = set(item for item in _rows(entry.get("resources")) if isinstance(item, str))
        for cost in self._costs(part_id):
            if cost.get("costTag") in wanted:
                return self._cost_title(part_id, cost)
        for drive_id in _rows(entry.get("drives")):
            if isinstance(drive_id, str):
                override = _object(self.project.data["drives"].get(drive_id))
                return override.get("title", _title(self._drive_document(drive_id), drive_id))
        return str(entry.get("id", ""))

    def entries(self, part_id):
        if part_id in self._entries_cache:
            return copy.deepcopy(self._entries_cache[part_id])
        part = _object(self.project.data["parts"].get(part_id))
        explicit = [copy.deepcopy(item) for item in _rows(part.get("entries")) if isinstance(item, dict)]
        automatic, _unresolved = self.project.default_entries(part_id)
        for item in automatic:
            tags = [tag for tag in _rows(item.get("resources")) if isinstance(tag, str)]
            drives = [key for key in _rows(item.get("drives")) if isinstance(key, str)]
            item["id"] = "auto:resource:" + "|".join(tags) if tags else "auto:drive:" + "|".join(drives)
        result = ([{"config": item, "automatic": False, "title": self._entry_title(part_id, item)} for item in explicit]
                  + [{"config": item, "automatic": True, "title": self._entry_title(part_id, item)} for item in automatic])
        self._entries_cache[part_id] = result
        return copy.deepcopy(result)

    def _presentation_drives(self):
        if self._presentation is None:
            path = self.project.root / "ExtentData" / "UI" / "Cockpit" / "presentation.json"
            try:
                self._presentation = _object(_object(_read_json(path)).get("drives"))
            except (OSError, UnicodeError, ValueError):
                self._presentation = {}
        return self._presentation

    def _shot(self, drive_id):
        document = self._drive_document(drive_id)
        class_name = _runtime_class(document)
        if class_name.endswith(".ShootingDrive"):
            return drive_id, document
        if class_name.endswith(".FightingDrive") or _type(document) != "Shooting":
            return None
        properties = _properties(document)
        references = []
        if class_name.endswith(".MainDrive"):
            references.extend(_references(properties.get("MainShootReferences")))
            references.extend(_references(properties.get("MainSpecialReferences")))
        references.extend(_references(_object(self._presentation_drives().get(drive_id)).get("resourceDrives")))
        shots = []
        for target_id, target, owner in references:
            if target != "ContextSource" and not (target == "Part" and owner in ("", "Self")):
                continue
            shot = self._drive_document(target_id)
            if _runtime_class(shot).endswith(".ShootingDrive") and target_id not in [item[0] for item in shots]:
                shots.append((target_id, shot))
        return shots[0] if len(shots) == 1 else None

    def _rule(self, rule_id):
        if not isinstance(rule_id, str) or not rule_id or Path(rule_id).name != rule_id:
            return {}
        self._rule_ids.add(rule_id)
        if rule_id not in self._rules:
            path = self.project.root / "ExtentData" / "GameRules" / (rule_id + ".json")
            try:
                self._rules[rule_id] = _object(_read_json(path))
            except (OSError, UnicodeError, ValueError):
                self._rules[rule_id] = {}
        return self._rules[rule_id]

    def _damage(self, document):
        rule_id = _object(_properties(document).get("DriveDamageData")).get("id")
        rule = self._rule(rule_id)
        basic = _struct(_object(rule.get("properties")).get("BasicDamege"))
        impact = _struct(basic.get("DamegeDP"))
        result = []
        for fields, key, title, source, unit in (
            (basic, "Damege", "威力", "基础威力", ""),
            (impact, "BasicDamege", "冲击力", "DP伤害", ""),
            (impact, "BreakDamege", "击穿冲击力", "击穿DP伤害", ""),
            (basic, "CriticalRate", "暴击率", "驱动暴击率", "%"),
        ):
            value = _number(fields.get(key))
            if value is None or key in {"BreakDamege", "CriticalRate"} and value <= 0:
                continue
            if key == "CriticalRate":
                value *= 100
            result.append(_row(title, source, value, unit, f"{rule_id} / BasicDamege.{key}"))
        return result

    def _feed(self, part_id, shot):
        if not part_id:
            return None
        requests = _rows(_object(_drive(shot).get("driveCost")).get("costs"))
        for request in requests:
            if not isinstance(request, dict):
                continue
            owner = _object(_object(request.get("resourceBinding")).get("ownerPart"))
            if owner.get("target", "Self") not in ("", "Self"):
                return None
            for cost in self._costs(part_id):
                if (_pool_key(cost)[:2] == _pool_key(request)[:2]
                        and str(cost.get("class", "")).endswith(".CostManagerObject_Weapon")):
                    return cost
        return None

    def _ordnance(self, part_id, shot):
        feed = self._feed(part_id, shot)
        if not feed:
            return []
        values = {}
        for item in _rows(feed.get("extraInfos")):
            if not isinstance(item, dict) or not item.get("bulletClass"):
                continue
            params = _object(_object(item.get("projectileBehavior")).get("parameters"))
            contact = _object(params.get("contact"))
            origin = f"{part_id} / {feed.get('costTag', '')} / 弹体参数"
            if contact.get("mode") not in ("Stick", "Rest"):
                distance = _number(params.get("maxDistanceCm"))
                if distance is not None and distance > 0:
                    values.setdefault("最大飞行距离", []).append(_row("射程", "最大飞行距离", distance / 100, "m", origin))
            explosion = _object(params.get("explosion"))
            radius = _number(explosion.get("radiusCm"))
            if explosion.get("enabled") is True and radius is not None and radius > 0:
                values.setdefault("爆炸半径", []).append(_row("范围", "爆炸半径", radius / 100, "m", origin))
            if params.get("piercing") is True:
                values.setdefault("贯穿", []).append(_row("贯穿", "贯穿", "有", "", origin))
        # Several projectile definitions may disagree. Without a unique value the
        # editor leaves the source automatic instead of choosing a projectile.
        result = []
        for rows in values.values():
            if rows and all((row["value"], row["unit"]) == (rows[0]["value"], rows[0]["unit"]) for row in rows):
                result.append(rows[0])
        return result

    def _automatic_drive(self, drive_id, part_id):
        document = self._drive_document(drive_id)
        if not document:
            return []
        shot = self._shot(drive_id)
        shot_document = shot[1] if shot else None
        class_name = _runtime_class(document)
        damage_document = document if class_name.endswith(".FightingDrive") else shot_document
        result = self._damage(damage_document) if damage_document else []
        if shot_document:
            properties = _properties(shot_document)
            rate = _number(_scalar(properties.get("MuzzleRate")))
            mode = _scalar(properties.get("AutoType"))
            animation = _scalar(properties.get("MuzzleAnimType"))
            if rate is not None and rate > 0 and mode not in (None, "Keep", "Simple") and animation != "OnlyAnim":
                result.append(_row("射速", "射速", rate, "发/分", f"{shot[0]} / MuzzleRate"))
            result.extend(self._ordnance(part_id, shot_document))
        by_source = {row["source"]: row for row in result}
        ordered = []
        for aliases, _title in _ATTACK_FIELDS:
            for source in aliases:
                if source in by_source:
                    ordered.append(by_source[source])
                    break
        return ordered

    def drive(self, drive_id, part_id=None):
        document = self._drive_document(drive_id)
        override = _object(self.project.data["drives"].get(drive_id))
        title = override.get("title", _title(document, drive_id))
        description = override.get("description", _description(document))
        available = self._automatic_drive(drive_id, part_id)
        has_attributes = "attributes" in override
        return {"id": drive_id, "title": title, "description": description,
                "type": _type(document), "public": bool(document) and _public(document),
                "attributes_mode": "custom" if has_attributes else "auto",
                "attributes": _project_override(available, override.get("attributes") if has_attributes else None),
                "available_attributes": copy.deepcopy(available)}

    def entry_sources(self, part_id, entry_config):
        config = _object(entry_config)
        public = set(self._public_drives(part_id))
        drives = [key for key in _rows(config.get("drives")) if isinstance(key, str) and key in public]
        if len(drives) == 1:
            return self._automatic_drive(drives[0], part_id)
        tags = set(tag for tag in _rows(config.get("resources")) if isinstance(tag, str))
        if not tags or not drives:
            return []
        candidates = []
        for key in drives:
            shot = self._shot(key)
            feed = self._feed(part_id, shot[1]) if shot else None
            if (not feed or feed.get("costTag") not in tags
                    or not any(isinstance(item, dict) and item.get("bulletClass") for item in _rows(feed.get("extraInfos")))):
                return []
            candidates.append(self._automatic_drive(key, part_id))
        result = []
        for fact in candidates[0]:
            if all(any(row.get("source") == fact.get("source") and row.get("value") == fact.get("value")
                       and row.get("unit") == fact.get("unit") for row in rows) for rows in candidates[1:]):
                result.append(fact)
        return result

    def drive_sources(self, drive_id, part_id=None):
        return self._automatic_drive(drive_id, part_id)

    def drive_attributes(self, drive_id, part_id, config):
        config = _object(config)
        available = self.drive_sources(drive_id, part_id)
        return _project_override(available, config.get("attributes") if "attributes" in config else None)

    def entry_attributes(self, part_id, entry_config):
        config = _object(entry_config)
        available = self.entry_sources(part_id, config)
        return _project_override(available, config.get("attributes") if "attributes" in config else None)

    def set_entry(self, part_id, config):
        config = _object(config)
        entry_id = config.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            return
        existing_part = _object(self.project.data["parts"].get(part_id))
        entries = [copy.deepcopy(item) for item in _rows(existing_part.get("entries"))]
        for index, entry in enumerate(entries):
            if isinstance(entry, dict) and entry.get("id") == entry_id:
                entries[index] = _merge_fields(entry, config, _ENTRY_FIELDS)
                break
        else:
            entries.append(copy.deepcopy(config))
        self.set_entries(part_id, entries)

    def set_entries(self, part_id, configs):
        existing_part = _object(self.project.data["parts"].get(part_id))
        previous = {item.get("id"): item for item in _rows(existing_part.get("entries"))
                    if isinstance(item, dict) and isinstance(item.get("id"), str)}
        updated = []
        for config in _rows(configs):
            if not isinstance(config, dict):
                continue
            updated.append(_merge_fields(previous.get(config.get("id")), config, _ENTRY_FIELDS))
        part = copy.deepcopy(existing_part)
        part["entries"] = updated
        self.project.data["parts"][part_id] = part
        self._entries_cache.pop(part_id, None)

    def set_drive(self, drive_id, config):
        existing = _object(self.project.data["drives"].get(drive_id))
        updated = _merge_fields(existing, config, _DRIVE_FIELDS)
        if updated:
            self.project.data["drives"][drive_id] = updated
        else:
            self.project.data["drives"].pop(drive_id, None)
        self._entries_cache.clear()

    def watch_paths(self):
        """Existing files and directories consumed by the current catalog."""
        paths = set()
        for folder, dirs, files in os.walk(self.project.parts_dir):
            dirs[:] = [name for name in dirs if not _excluded(name)]
            paths.add(str(Path(folder)))
            for filename in files:
                if filename.lower().endswith(".json") and not _excluded(filename):
                    paths.add(str(Path(folder) / filename))
        rules_dir = self.project.root / "ExtentData" / "GameRules"
        if rules_dir.is_dir():
            paths.add(str(rules_dir))
        for rule_id in self._rule_ids:
            path = rules_dir / (rule_id + ".json")
            if path.is_file():
                paths.add(str(path))
        presentation = self.project.root / "ExtentData" / "UI" / "Cockpit" / "presentation.json"
        if presentation.parent.is_dir():
            paths.add(str(presentation.parent))
        if presentation.is_file():
            paths.add(str(presentation))
        config = self.project.config_path
        directory = config.parent
        while not directory.is_dir() and directory != directory.parent:
            directory = directory.parent
        if directory.is_dir():
            paths.add(str(directory))
        if config.is_file():
            paths.add(str(config))
        return sorted(paths)

    def refresh(self):
        """Refresh source documents and merge disk config into the live Project."""
        fresh = Project(self.project.root)
        conflicts = []
        merged = _merge_three(self.project.original, self.project.data, fresh.data, (), conflicts)
        old_parts = self.project.parts
        self.project.data = merged
        self.project.original = copy.deepcopy(fresh.data)
        for name in ("parts", "drives", "part_documents", "drive_documents", "drive_classes", "skipped"):
            setattr(self.project, name, getattr(fresh, name))
        for part_id in _object(merged.get("parts")):
            self.project.parts.setdefault(part_id, {"name": part_id, "costs": []})
            if part_id not in self.project.part_documents:
                previous = _object(old_parts.get(part_id)).get("name")
                if isinstance(previous, str) and previous:
                    self.project.parts[part_id]["name"] = previous
        for drive_id in _object(merged.get("drives")):
            self.project.drives.setdefault(drive_id, drive_id)
        for part in _object(merged.get("parts")).values():
            for entry in _rows(_object(part).get("entries")):
                for drive_id in _rows(_object(entry).get("drives")):
                    if isinstance(drive_id, str):
                        self.project.drives.setdefault(drive_id, drive_id)
        self._presentation = None
        self._rules.clear()
        self._entries_cache.clear()
        return {"conflicts": conflicts, "changed": self.project.changed()}
