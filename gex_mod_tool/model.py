"""Project data and the inspector configuration, without UE dependencies."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import tempfile
import uuid


SCHEMA = "g-ex.mod.inspector.v1"
CONFIG_RELATIVE_PATH = Path("UI") / "Hangar" / "inspector.json"
PARTS_RELATIVE_PATH = Path("ExtentData") / "Parts"
_EXCLUDED = re.compile(r"(?:^|[._\-\s])(bak|backup|archive)(?:$|[._\-\s])", re.I)


def _excluded(name: str) -> bool:
    return bool(_EXCLUDED.search(name)) or name in {"备份", "归档"}


def _read_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _rows(value):
    return value if isinstance(value, list) else []


def _object(value):
    return value if isinstance(value, dict) else {}


def _domain(value, local=False):
    text = value.casefold() if isinstance(value, str) else ""
    if text == "none":
        text = ""
    return text or ("local" if local else "")


def _pool_key(cost):
    binding = _object(cost.get("resourceBinding"))
    shared = _domain(binding.get("sharedDomainKey"))
    return (cost.get("costTag", ""), shared,
            "" if shared else _domain(binding.get("localDomainKey"), local=True))


def _unpack(value):
    if isinstance(value, list):
        return [_unpack(item) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("type") == "text":
        return value.get("value", "")
    if value.get("type") == "array":
        return _unpack(value.get("values", []))
    if value.get("type") == "struct":
        return _unpack(value.get("fields", {}))
    return {key: _unpack(item) for key, item in value.items()}


def _references(value):
    """Read both reflected JSON structs and UE's textual reference form."""
    value = _unpack(value)
    if isinstance(value, str):
        result = []
        for chunk in re.split(r"(?=DefinitionId\s*=)", value):
            match = re.search(r'DefinitionId\s*=\s*"([^\"]+)"', chunk)
            if not match:
                continue
            target = re.search(r"\bTarget\s*=\s*([A-Za-z_]+)", chunk[match.end():])
            owner = re.search(r"PartBinding\s*=\s*\(\s*Target\s*=\s*([A-Za-z_]+)", chunk)
            result.append((match.group(1), target.group(1) if target else "ContextSource",
                           owner.group(1) if owner else "Self"))
        return result
    if isinstance(value, list):
        return [ref for item in value for ref in _references(item)]
    if not isinstance(value, dict):
        return []
    binding = value.get("driveBinding", value.get("DriveBinding"))
    if isinstance(binding, dict):
        return _references(binding)
    definition = value.get("definitionId", value.get("DefinitionId"))
    if isinstance(definition, str) and definition:
        part = _object(value.get("partBinding", value.get("PartBinding")))
        return [(definition, value.get("target", value.get("Target", "ContextSource")),
                 part.get("target", part.get("Target", "Self")))]
    return [ref for item in value.values() for ref in _references(item)]


class Project:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.parts_dir = self.root / PARTS_RELATIVE_PATH
        if not self.parts_dir.is_dir():
            raise ValueError("所选目录中找不到 ExtentData/Parts，请选择游戏工程根目录。")
        self.config_path = self.root / CONFIG_RELATIVE_PATH
        if self.config_path.exists():
            data = _read_json(self.config_path)
            if not isinstance(data, dict) or data.get("schema") != SCHEMA:
                raise ValueError("配置文件的 schema 不是 g-ex.mod.inspector.v1，未打开该文件。")
            if not isinstance(data.get("parts"), dict) or not isinstance(data.get("drives"), dict):
                raise ValueError("配置文件中的 parts 或 drives 不是对象，未打开该文件。")
            self.data = data
        else:
            self.data = {"schema": SCHEMA, "parts": {}, "drives": {}}
        self.original = copy.deepcopy(self.data)
        self.parts = {}
        self.drives = {}
        self.part_documents = {}
        self.drive_documents = {}
        self.drive_classes = {}
        self.skipped = 0
        self._load_catalog()

    def _load_catalog(self):
        for folder, dirs, files in os.walk(self.parts_dir):
            dirs[:] = sorted(name for name in dirs if not _excluded(name))
            for filename in sorted(files):
                if not filename.lower().endswith(".json") or _excluded(filename):
                    continue
                try:
                    item = _read_json(Path(folder) / filename)
                except (OSError, UnicodeError, json.JSONDecodeError):
                    self.skipped += 1
                    continue
                if not isinstance(item, dict) or not isinstance(item.get("part"), dict):
                    continue
                definition_id = item.get("id")
                if not isinstance(definition_id, str) or not definition_id:
                    continue
                part = item["part"]
                info = part.get("partInfo") or {}
                name = info.get("displayName") if isinstance(info, dict) else ""
                name = name if isinstance(name, str) and name else definition_id
                if isinstance(part.get("drive"), dict):
                    self.drives.setdefault(definition_id, name)
                    self.drive_documents.setdefault(definition_id, item)
                    source = _object(item.get("source"))
                    for key in ("asset", "generatedClass"):
                        if isinstance(source.get(key), str):
                            self.drive_classes.setdefault(source[key], definition_id)
                else:
                    costs = []
                    for cost in part.get("costs", []):
                        if isinstance(cost, dict) and isinstance(cost.get("costTag"), str):
                            tag = cost["costTag"]
                            if tag and tag != "None":
                                label = cost.get("displayName")
                                costs.append((tag, label if isinstance(label, str) else ""))
                    self.parts.setdefault(definition_id, {"name": name, "costs": costs})
                    self.part_documents.setdefault(definition_id, item)

        # Keep existing custom or currently unavailable definitions editable.
        for definition_id in self.data["parts"]:
            self.parts.setdefault(definition_id, {"name": definition_id, "costs": []})
        for definition_id in self.data["drives"]:
            self.drives.setdefault(definition_id, definition_id)
        for part in self.data["parts"].values():
            if not isinstance(part, dict):
                continue
            for entry in part.get("entries", []):
                if isinstance(entry, dict):
                    for definition_id in entry.get("drives", []):
                        if isinstance(definition_id, str):
                            self.drives.setdefault(definition_id, definition_id)

    def changed(self):
        return self.data != self.original

    def default_entries(self, definition_id):
        """Project the unconfigured source pools and public participant drives."""
        part = _object(_object(self.part_documents.get(definition_id)).get("part"))
        participant_ids = []
        unresolved = []
        for raw in _rows(part.get("drives")):
            if not isinstance(raw, str) or not raw or raw == "None":
                continue
            candidate = self.drive_classes.get(raw)
            if candidate is None:
                short = raw.rsplit(".", 1)[-1].removesuffix("_C")
                candidate = short if short in self.drive_documents else None
            if candidate and candidate not in participant_ids:
                participant_ids.append(candidate)
            elif candidate is None:
                unresolved.append(raw)
        for candidate in _rows(part.get("connectedPartDefinitionIds")):
            if candidate in self.drive_documents and candidate not in participant_ids:
                participant_ids.append(candidate)
            elif isinstance(candidate, str) and candidate not in self.drive_documents and candidate not in self.part_documents:
                unresolved.append(candidate)
        documents = {key: self.drive_documents[key] for key in participant_ids}
        drives = {key: _object(_object(item.get("part")).get("drive")) for key, item in documents.items()}
        try:
            presentation = _object(_read_json(self.root / "ExtentData" / "UI" / "Cockpit" / "presentation.json"))
            presentation_drives = _object(presentation.get("drives"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            presentation_drives = {}

        existing = _object(self.data["parts"].get(definition_id))
        existing_entries = [item for item in _rows(existing.get("entries")) if isinstance(item, dict)]
        used_tags = {tag for entry in existing_entries for tag in _rows(entry.get("resources")) if isinstance(tag, str)}
        used_drives = {key for entry in existing_entries for key in _rows(entry.get("drives")) if isinstance(key, str)}

        def is_public(drive):
            visible = _object(drive.get("properties")).get("bPubliclyVisible", True)
            return visible is not False and str(visible).casefold() not in {"false", "0"}

        def direct_requests(drive):
            return [item for item in _rows(_object(drive.get("driveCost")).get("costs")) if isinstance(item, dict)]

        def requests(drive):
            result = direct_requests(drive)
            muzzle = _object(drive.get("muzzle"))
            result += [item for item in _rows(_object(muzzle.get("instantFireCost")).get("costs")) if isinstance(item, dict)]
            props = _object(drive.get("properties"))
            if str(props.get("UseBasicCost", "True")).casefold() == "false":
                result += [item for item in _rows(_object(drive.get("actionCost")).get("costs")) if isinstance(item, dict)]
            return result

        def drive_title(key):
            info = _object(_object(documents[key].get("part")).get("partInfo"))
            title = info.get("displayName")
            return title if isinstance(title, str) and title else key

        pools = []
        for cost in _rows(part.get("costs")):
            if not isinstance(cost, dict) or not isinstance(cost.get("costTag"), str):
                continue
            key = _pool_key(cost)
            public_owners, hidden_owners = [], []
            for drive_id, drive in drives.items():
                if any(_pool_key(request)[:2] == key[:2] for request in direct_requests(drive)):
                    bucket = public_owners if is_public(drive) else hidden_owners
                    title = drive_title(drive_id)
                    if title not in bucket:
                        bucket.append(title)
            visible_resources = []
            for resource in _rows(cost.get("resources")):
                if not isinstance(resource, dict):
                    continue
                tag = resource.get("resourceTag", "")
                if (tag == "消耗.资源.过热" and resource.get("costType") == "Heat" and
                        str(cost.get("class", "")).endswith(".CostManagerObject_Weapon")):
                    consumes_heat = any(
                        _pool_key(request)[:2] == key[:2] and any(
                            usage.get("tag") == tag and isinstance(usage.get("value"), (int, float)) and usage["value"] > 0
                            for usage in _rows(request.get("resources")) if isinstance(usage, dict))
                        for drive in drives.values() for request in direct_requests(drive))
                    if not consumes_heat:
                        continue
                visible_resources.append(resource)
            if not visible_resources:
                continue
            names = [str(resource.get("resourceTag", "")).rsplit(".", 1)[-1] for resource in visible_resources]
            title = cost.get("displayName") or " / ".join(public_owners or hidden_owners or list(dict.fromkeys(names)))
            is_weapon = str(cost.get("class", "")).endswith(".CostManagerObject_Weapon") or any(
                resource.get("resourceTag") == "消耗.资源.子弹" for resource in visible_resources)
            pools.append({"key": key, "tag": cost["costTag"], "title": title, "weapon": is_weapon})

        def links(start):
            found, visited = set(), set()
            external = False

            def visit(drive_id):
                nonlocal external
                if drive_id in visited:
                    return
                visited.add(drive_id)
                drive = drives.get(drive_id)
                if drive is None:
                    return
                for request in requests(drive):
                    owner = _object(_object(request.get("resourceBinding")).get("ownerPart"))
                    if owner.get("target", "Self") not in ("", "Self"):
                        external = True
                        continue
                    request_key = _pool_key(request)
                    for index, pool in enumerate(pools):
                        if pool["key"] == request_key:
                            found.add(index)
                props = _object(drive.get("properties"))
                runtime_class = str(_object(documents[drive_id].get("runtime")).get("class", ""))
                references = []
                if runtime_class.endswith(".MainDrive"):
                    references += _references(props.get("MainShootReferences"))
                    references += _references(props.get("MainSpecialReferences"))
                references += _references(_object(presentation_drives.get(drive_id)).get("resourceDrives"))
                for target_id, target, owner in references:
                    if target == "ContextSource" or (target == "Part" and owner in ("", "Self")):
                        visit(target_id)
                    else:
                        external = True

            visit(start)
            return found, external

        linked = {}
        public_ids = [key for key in participant_ids if is_public(drives[key]) and key not in used_drives]
        for key in public_ids:
            runtime_class = str(_object(documents[key].get("runtime")).get("class", ""))
            if runtime_class.endswith(".ProgramDrive"):
                continue
            matches, external = links(key)
            if len(matches) == 1 and not external:
                index = next(iter(matches))
                if pools[index]["tag"] not in used_tags:
                    linked.setdefault(index, []).append(key)

        entries, linked_ids = [], set()
        for index, pool in enumerate(pools):
            if pool["tag"] in used_tags:
                continue
            pool_drives = linked.get(index, [])
            if not pool["weapon"] and not pool_drives:
                continue
            entries.append({"id": "entry_" + uuid.uuid4().hex, "title": pool["title"],
                            "resources": [pool["tag"]], "drives": pool_drives})
            used_tags.add(pool["tag"])
            linked_ids.update(pool_drives)
        for key in public_ids:
            if key not in linked_ids:
                override = _object(self.data["drives"].get(key))
                entries.append({"id": "entry_" + uuid.uuid4().hex,
                                "title": override.get("title", drive_title(key)), "resources": [], "drives": [key]})
        return entries, unresolved

    def save(self):
        if self.config_path.exists() and not self.changed():
            return False
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=self.config_path.parent,
                prefix=".inspector-", suffix=".tmp", delete=False
            ) as file:
                temp_path = Path(file.name)
                file.write(text)
            os.replace(temp_path, self.config_path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        self.original = copy.deepcopy(self.data)
        return True


def settings_path():
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".config"
    return base / "G-EX Mod Tool" / "settings.json"


def last_project():
    try:
        result = _read_json(settings_path())
        return result.get("project", "") if isinstance(result, dict) else ""
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ""


def remember_project(path):
    settings = settings_path()
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"project": str(path)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
