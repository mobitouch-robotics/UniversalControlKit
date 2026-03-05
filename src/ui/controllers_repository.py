from typing import List, Optional
from .controller_config import ControllerConfig
import json


class ControllersRepository:
    """Singleton repository for storing controller configurations to controllers.json

    Mirrors the robots repository behaviour: keeps an in-memory list and persists
    to `controllers.json` in the current working directory.
    """

    _instance = None
    _storage_file = "controllers.json"

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.controllers: List[ControllerConfig] = []
        # simple observer callbacks called when controllers change
        self._observers = []
        try:
            self.load_from_file(self._storage_file)
        except Exception:
            self.controllers = []
        self._initialized = True

    def save_to_file(self, filepath: str):
        data = [c.to_dict() for c in self.controllers]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # notify observers on save
        try:
            for cb in list(self._observers):
                try:
                    cb()
                except Exception:
                    pass
        except Exception:
            pass

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        self.controllers.clear()
        for item in data:
            try:
                cfg = ControllerConfig.from_dict(item)
                self.controllers.append(cfg)
            except Exception:
                # skip invalid entries
                continue
        # notify observers after loading
        try:
            for cb in list(self._observers):
                try:
                    cb()
                except Exception:
                    pass
        except Exception:
            pass

    def add_controller(self, controller: ControllerConfig) -> bool:
        # avoid duplicates by comparing type and any overlapping identifier (guid or name)
        def _identifiers_overlap(a_guid, a_name, b_guid, b_name):
            a_ids = set([x for x in (a_guid, a_name) if x])
            b_ids = set([x for x in (b_guid, b_name) if x])
            return len(a_ids.intersection(b_ids)) > 0

        for c in self.controllers:
            if c.type == controller.type and _identifiers_overlap(c.guid, c.name, controller.guid, controller.name):
                return False
        self.controllers.append(controller)
        try:
            self.save_to_file(self._storage_file)
        except Exception:
            pass
        # notify observers
        try:
            for cb in list(self._observers):
                try:
                    cb()
                except Exception:
                    pass
        except Exception:
            pass
        return True

    def delete_controller(self, controller: ControllerConfig) -> bool:
        for c in list(self.controllers):
            if c.type == controller.type and c.guid == controller.guid:
                self.controllers.remove(c)
                try:
                    self.save_to_file(self._storage_file)
                except Exception:
                    pass
                # notify observers
                try:
                    for cb in list(self._observers):
                        try:
                            cb()
                        except Exception:
                            pass
                except Exception:
                    pass
                return True
        return False

    def add_observer(self, callback):
        try:
            if callback not in self._observers:
                self._observers.append(callback)
        except Exception:
            pass

    def remove_observer(self, callback):
        try:
            if callback in self._observers:
                self._observers.remove(callback)
        except Exception:
            pass

    def get_controllers(self) -> List[ControllerConfig]:
        return self.controllers

    def get_by_guid(self, guid: str) -> Optional[ControllerConfig]:
        for c in self.controllers:
            if c.guid == guid:
                return c
        return None
