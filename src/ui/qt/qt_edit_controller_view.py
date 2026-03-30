from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QPalette, QColor
from .qt_top_panel import QtTopPanel
from typing import Optional
from PyQt5.QtWidgets import QFormLayout, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QScrollArea, QDialog, QVBoxLayout, QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor, QKeySequence
from PyQt5.QtCore import Qt
from .qt_section import QtSection
from src.ui.controller_config import ControllerConfig, ControllerType, ControllerAction
from src.ui.controller_mapping_defaults import get_joystick_default_mappings
from src.ui.controllers_repository import ControllersRepository
from PyQt5.QtWidgets import QInputDialog


class EditControllerView(QWidget):
    def __init__(self, controller: ControllerConfig | type, parent=None, back_action=None, qt_app=None):
        super().__init__(parent)
        self.controller = controller
        self.setup_background()
        self.setStyleSheet(
            "QLabel { color: #fff; }"
            "QPushButton { color: #fff; }"
        )

        # Wrap back_action to save repository if editing (mirror EditRobotView)
        def wrapped_back_action(pop_to_root: bool = False):
            try:
                # Only save when editing an existing ControllerConfig instance
                if isinstance(self.controller, ControllerConfig):
                    repo = ControllersRepository()
                    repo.save_to_file(repo._storage_file)
            except Exception:
                pass
            if back_action:
                back_action(pop_to_root=pop_to_root)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.top_panel = QtTopPanel(self, back_action=wrapped_back_action, title=self._get_title(), qt_app=qt_app)
        layout.addWidget(self.top_panel)

        # Configuration form (match EditRobotView margins/policies)
        config_widget = QWidget()
        config_layout = QFormLayout()
        config_layout.setLabelAlignment(Qt.AlignLeft)
        config_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        config_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        config_widget.setLayout(config_layout)
        config_widget.setMinimumWidth(1)
        config_widget.setSizePolicy(
            config_widget.sizePolicy().horizontalPolicy(),
            config_widget.sizePolicy().verticalPolicy(),
        )

        # Determine if adding new (controller is a type/class) or editing existing
        repo = ControllersRepository()
        is_new = False
        if isinstance(self.controller, type):
            # For controllers we normally expect an instance; support class for symmetry
            is_new = True
            cfg_instance = ControllerConfig(type=ControllerType.KEYBOARD, guid=None)
        elif isinstance(self.controller, ControllerConfig):
            cfg_instance = self.controller
            # If identical controller is not present in repo, treat as new (show Create)
            exists = any(
                (c.type == cfg_instance.type and c.guid == cfg_instance.guid)
                for c in repo.get_controllers()
            )
            is_new = not exists
        else:
            is_new = True
            cfg_instance = ControllerConfig(type=ControllerType.KEYBOARD, guid=None)

        # Per-type fields: we do not allow changing type here; show fields
        # depending on the controller type.
        # Remove manual GUID entry; user selects from available joysticks only
            has_available_joysticks = True
        def get_available_joysticks():
            try:
                import pygame

                pygame.joystick.init()
                count = pygame.joystick.get_count()
                res = []
                for i in range(count):
                    try:
                        j = pygame.joystick.Joystick(i)
                        try:
                            j.init()
                        except Exception:
                            pass
                        try:
                            name = j.get_name() or ""
                        except Exception:
                            name = ""
                        try:
                            guid_raw = j.get_guid() if hasattr(j, "get_guid") else ""
                            guid = str(guid_raw) if guid_raw is not None else ""
                        except Exception:
                            guid = ""
                        res.append({"index": i, "name": name, "guid": guid})
                    except Exception:
                        continue
                return res
            except Exception:
                return []

        if cfg_instance.type == ControllerType.JOYSTICK:
            if not is_new:
                # Editing existing controller: show its name instead of a selector
                display_name = cfg_instance.name or (cfg_instance.guid or "Joystick")
                name_label = QLabel(display_name)
                name_label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
                config_layout.addRow(QLabel("Joystick"), name_label)
                has_available_joysticks = True
            else:
                # Adding new controller: provide a dropdown of available joysticks
                joystick_combo = QComboBox()
                joysticks = get_available_joysticks()
                model = QStandardItemModel()
                existing = repo.get_controllers()
                available_count = 0
                for j in joysticks:
                    name = j["name"] or f"Joystick {j['index']}"
                    data = j["guid"] if j["guid"] else name
                    # Skip devices that are already added
                    already_added = any(
                        (c.type == ControllerType.JOYSTICK and ((c.guid and c.guid == data) or (not c.guid and c.name == name)))
                        for c in existing
                    )
                    if already_added:
                        continue
                    item = QStandardItem(name)
                    item.setData(data, Qt.UserRole)
                    model.appendRow(item)
                    available_count += 1

                joystick_combo.setModel(model)
                if available_count > 0:
                    joystick_combo.setCurrentIndex(0)
                else:
                    joystick_combo.setEnabled(False)

                joystick_combo.setStyleSheet("font-size: 13px; padding: 6px; background: #222; color: #fff; border-radius: 4px;")
                joystick_combo.setFixedHeight(28)

                joystick_label = QLabel("Joystick")
                joystick_label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
                config_layout.addRow(joystick_label, joystick_combo)

                # Prefill defaults for known joystick types.
                try:
                    if is_new and not getattr(cfg_instance, "mappings", None) and available_count > 0:
                        selected_name = joystick_combo.itemText(joystick_combo.currentIndex())
                        selected_guid = joystick_combo.model().item(joystick_combo.currentIndex()).data(Qt.UserRole)
                        defaults = get_joystick_default_mappings(selected_name, selected_guid)
                        if defaults:
                            cfg_instance.mappings = defaults
                except Exception:
                    pass

                # Flag to indicate if any new devices are available for creation
                has_available_joysticks = available_count > 0
        elif cfg_instance.type == ControllerType.VOICE:
            # Voice controller: show settings and command reference
            type_label = QLabel("Type")
            type_label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
            type_value = QLabel("Voice")
            type_value.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
            config_layout.addRow(type_label, type_value)

            from src.ui.voice.voice_settings import (
                SUPPORTED_LANGUAGES, MODEL_SIZES,
                load_voice_settings, save_voice_settings,
            )
            settings = load_voice_settings()

            lang_combo = QComboBox()
            lang_combo.setStyleSheet(
                "QComboBox { background: #444; color: #fff; padding: 6px; border-radius: 4px; font-size: 13px; }"
                "QComboBox::drop-down { border: none; }"
                "QComboBox QAbstractItemView { background: #444; color: #fff; selection-background-color: #666; }"
            )
            lang_combo.setFixedHeight(28)
            current_lang = settings.get("language", "en")
            for code, name in SUPPORTED_LANGUAGES:
                lang_combo.addItem(name, code)
                if code == current_lang:
                    lang_combo.setCurrentIndex(lang_combo.count() - 1)
            config_layout.addRow(QLabel("Language"), lang_combo)

            model_combo = QComboBox()
            model_combo.setStyleSheet(
                "QComboBox { background: #444; color: #fff; padding: 6px; border-radius: 4px; font-size: 13px; }"
                "QComboBox::drop-down { border: none; }"
                "QComboBox QAbstractItemView { background: #444; color: #fff; selection-background-color: #666; }"
            )
            model_combo.setFixedHeight(28)
            current_model = settings.get("model_size", "base")
            for size_id, label in MODEL_SIZES:
                model_combo.addItem(label, size_id)
                if size_id == current_model:
                    model_combo.setCurrentIndex(model_combo.count() - 1)
            config_layout.addRow(QLabel("Model"), model_combo)

            def _save_voice_settings():
                save_voice_settings({
                    "language": lang_combo.currentData(),
                    "model_size": model_combo.currentData(),
                })
            lang_combo.currentIndexChanged.connect(lambda _: _save_voice_settings())
            model_combo.currentIndexChanged.connect(lambda _: _save_voice_settings())

            info = QLabel("Push-to-talk: hold V key or mic button")
            info.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
            config_layout.addRow(QLabel(""), info)
        else:
            # Keyboard: no GUID
            type_label = QLabel("Type")
            type_label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
            type_value = QLabel("Keyboard")
            type_value.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
            config_layout.addRow(type_label, type_value)
            info = QLabel("Keyboard input controller")
            info.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
            config_layout.addRow(QLabel(""), info)

        config_section = QtSection("Configuration", config_widget)
        config_section.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(config_section)

        # Voice command reference section
        if cfg_instance.type == ControllerType.VOICE:
            from PyQt5.QtWidgets import QWidget as W, QVBoxLayout as V, QGridLayout

            ref_widget = W()
            ref_layout = V()
            ref_layout.setContentsMargins(0, 0, 0, 0)
            ref_layout.setSpacing(8)
            ref_widget.setLayout(ref_layout)

            _header_style = "font-size: 12px; color: #aaa; font-weight: bold; background: transparent; padding: 2px 0;"
            _phrase_style = "font-size: 12px; color: #8af; background: transparent; padding: 2px 4px;"
            _action_style = "font-size: 12px; color: #fff; background: transparent; padding: 2px 4px;"

            # One-shot commands table — show phrases for selected language
            from src.ui.voice.command_parser import get_command_reference
            commands = get_command_reference(settings.get("language", "en"))

            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(2)
            h_say = QLabel("Say")
            h_say.setStyleSheet(_header_style)
            h_action = QLabel("Action")
            h_action.setStyleSheet(_header_style)
            grid.addWidget(h_say, 0, 0)
            grid.addWidget(h_action, 0, 1)

            for i, (phrase, action) in enumerate(commands, start=1):
                pl = QLabel(f'"{phrase}"')
                pl.setStyleSheet(_phrase_style)
                al = QLabel(action)
                al.setStyleSheet(_action_style)
                grid.addWidget(pl, i, 0)
                grid.addWidget(al, i, 1)

            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            ref_layout.addLayout(grid)

            # Movement commands
            move_header = QLabel("Movement commands")
            move_header.setStyleSheet(_header_style)
            ref_layout.addWidget(move_header)

            from src.ui.voice.command_parser import get_movement_examples
            move_examples = get_movement_examples(settings.get("language", "en"))
            for ex in move_examples:
                el = QLabel(ex)
                el.setStyleSheet("font-size: 12px; color: #8af; background: transparent; padding: 1px 4px;")
                el.setWordWrap(True)
                ref_layout.addWidget(el)

            ref_section = QtSection("Voice commands", ref_widget)
            ref_section.setContentsMargins(16, 0, 16, 0)
            layout.addWidget(ref_section)

        # Mappings section: only for joystick controllers
        if cfg_instance.type == ControllerType.JOYSTICK:
            # Skip actions requiring complex parameters; use simple button->action mapping
            from PyQt5.QtWidgets import QWidget as W, QVBoxLayout as V, QHBoxLayout as H

            mappings_widget = W()
            mappings_layout = V()
            mappings_layout.setContentsMargins(0, 0, 0, 0)
            mappings_layout.setSpacing(0)
            mappings_widget.setLayout(mappings_layout)

            # Create dedicated containers for movement and actions so they can be
            # presented in separate sections.
            movement_widget = W()
            movement_layout = V()
            movement_layout.setContentsMargins(0, 0, 0, 0)
            movement_layout.setSpacing(4)
            movement_widget.setLayout(movement_layout)

            actions_widget = W()
            actions_layout = V()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(4)
            actions_widget.setLayout(actions_layout)

            # Pose group (stand/stretch/sit)
            pose_widget = W()
            pose_layout = V()
            pose_layout.setContentsMargins(0, 0, 0, 0)
            pose_layout.setSpacing(4)
            pose_widget.setLayout(pose_layout)

            # Other toggles group (flash/led/lidar)
            other_widget = W()
            other_layout = V()
            other_layout.setContentsMargins(0, 0, 0, 0)
            other_layout.setSpacing(4)
            other_widget.setLayout(other_layout)

            # Use ControllerAction enum for available actions
            # Present actions grouped: Movement, Pose, Actions, Other
            simple_actions = [
                # Movement group (movement mapping handled separately in UI)
                ControllerAction.RUN,
                ControllerAction.SLOW,

                # Pose group
                ControllerAction.STAND_UP,
                ControllerAction.STAND_DOWN,
                ControllerAction.STRETCH,
                ControllerAction.SIT,

                # Actions group
                ControllerAction.HELLO,
                ControllerAction.JUMP,
                ControllerAction.FINGER_HEART,
                ControllerAction.DANCE1,

                # Other toggles
                ControllerAction.TOGGLE_FLASH,
                ControllerAction.TOGGLE_LED,
            ]

            # Movement/rotation mapping keys
            movement_action = ControllerAction.MOVEMENT
            rotation_action = ControllerAction.ROTATION

            # Ensure cfg_instance has mappings list and remove deprecated mappings
            if cfg_instance.mappings is None:
                cfg_instance.mappings = []
            else:
                try:
                    cfg_instance.mappings = [m for m in cfg_instance.mappings if m.get('action') != 'stop_move']
                except Exception:
                    pass

            # Helper to get/set mapping for action
            def get_mapping_for(action):
                key = action.value if hasattr(action, "value") else action
                for m in cfg_instance.mappings:
                    if m.get("action") == key:
                        return m.get("input")
                return None

            def set_mapping_for(action, input_id):
                key = action.value if hasattr(action, "value") else action
                def _normalize(x):
                    try:
                        if x is None:
                            return ""
                        if isinstance(x, (list, tuple)):
                            return "axes:" + ",".join(str(i) for i in x)
                        return str(x)
                    except Exception:
                        return str(x)

                def canonical_stick(x):
                    # Return a canonical stick string like 'stick:N' for axes/lists/old formats
                    try:
                        if x is None:
                            return None
                        if isinstance(x, str) and x.startswith("stick:"):
                            parts = x.split(":")
                            try:
                                return f"stick:{int(parts[1])}"
                            except Exception:
                                return x
                        # axes:0,1 or list/tuple
                        if isinstance(x, (list, tuple)):
                            if len(x) >= 1:
                                a0 = int(x[0])
                                return f"stick:{a0//2}"
                            return None
                        if isinstance(x, str) and x.startswith("axes:"):
                            try:
                                nums = [int(s) for s in x.split(":",1)[1].split(",") if s]
                                if nums:
                                    return f"stick:{min(nums)//2}"
                            except Exception:
                                return None
                        # numeric string or int -> axis index
                        if isinstance(x, int):
                            return f"stick:{x//2}"
                        if isinstance(x, str):
                            # try to parse integer
                            try:
                                v = int(x)
                                return f"stick:{v//2}"
                            except Exception:
                                pass
                        return None
                    except Exception:
                        return None

                new_norm = _normalize(input_id)
                new_canon = canonical_stick(input_id)

                # Remove this input from any other action that already uses it (consider canonical equivalence)
                to_remove = []
                for m in list(cfg_instance.mappings):
                    if m.get("action") == key:
                        continue
                    other = m.get("input")
                    if _normalize(other) == new_norm:
                        to_remove.append(m)
                        continue
                    # also consider canonical stick equivalence
                    other_canon = canonical_stick(other)
                    if new_canon is not None and other_canon == new_canon:
                        to_remove.append(m)

                for rem in to_remove:
                    try:
                        cfg_instance.mappings.remove(rem)
                    except Exception:
                        pass
                    # update UI label if present
                    try:
                        if rem.get("action") in mapping_rows:
                            mapping_rows[rem.get("action")][1].setText("(not set)")
                    except Exception:
                        pass

                # Set or update mapping for the requested action
                for m in cfg_instance.mappings:
                    if m.get("action") == key:
                        m["input"] = input_id
                        return
                cfg_instance.mappings.append({"action": key, "input": input_id})

            mapping_rows = {}

            # --- Axis mappings: Movement (2 axes) and Rotation (1 axis) ---
            # Movement: maps to a pair of axes (x,y) used for forward/sideways movement
            # Rotation: maps to a single axis used for rotation
            def format_axis_pair(pair):
                if not pair:
                    return "(not set)"
                try:
                    a, b = pair
                    # Display a concise analog id (not directions)
                    return f"Analog {min(a, b)}"
                except Exception:
                    try:
                        # if stored as single int
                        return f"Analog {int(pair)}"
                    except Exception:
                        return str(pair)

            def format_axis_single(ax):
                # Accept either a single int or a stored pair; prefer single
                if ax is None:
                    return "(not set)"
                try:
                    if isinstance(ax, (list, tuple)) and len(ax) > 0:
                        a = ax[0]
                        return f"Analog {a}"
                    return f"Axis{int(ax)}"
                except Exception:
                    return str(ax)

            def mapping_label(mapping):
                # mapping may be None, int, list, or strings like 'stick:0' or 'stick:0:axis:1'
                if mapping is None:
                    return "(not set)"
                try:
                    if isinstance(mapping, str) and mapping.startswith("Button"):
                        return mapping
                    if isinstance(mapping, str) and mapping.startswith("Axis"):
                        parts = mapping.split(":")
                        if len(parts) == 2:
                            direction = "+" if parts[1] == "+" else "-"
                            return f"{parts[0]} {direction}"
                        return mapping
                    if isinstance(mapping, str) and mapping.startswith("Hat"):
                        parts = mapping.split(":")
                        if len(parts) == 2:
                            return f"D-pad {parts[1]}"
                        return mapping
                    if isinstance(mapping, str) and mapping.startswith("stick:"):
                        parts = mapping.split(":")
                        try:
                            sid = int(parts[1])
                            return f"Stick {sid}"
                        except Exception:
                            return mapping
                    if isinstance(mapping, (list, tuple)) and len(mapping) >= 1:
                        return f"Stick {int(mapping[0]) // 2}"
                    if isinstance(mapping, int):
                        return f"Analog {mapping}"
                    return str(mapping)
                except Exception:
                    return str(mapping)

            # Axis capture helper
            def capture_axes(act, want_pair=False, val_label=None):
                try:
                    import pygame

                    pygame.init()
                    pygame.joystick.init()
                except Exception:
                    QMessageBox.information(self, "No input captured", "No joystick input detected or joystick unavailable.")
                    return False

                # Determine target joystick indices to monitor
                indices = []
                try:
                    count = pygame.joystick.get_count()
                    for i in range(count):
                        try:
                            j = pygame.joystick.Joystick(i)
                            try:
                                j.init()
                            except Exception:
                                pass
                            name = ""
                            try:
                                name = j.get_name() or ""
                            except Exception:
                                name = ""
                            guid = ""
                            try:
                                guid_raw = j.get_guid() if hasattr(j, "get_guid") else ""
                                guid = str(guid_raw) if guid_raw is not None else ""
                            except Exception:
                                guid = ""
                            if 'joystick_combo' in locals() and joystick_combo is not None and joystick_combo.isEnabled():
                                try:
                                    data = joystick_combo.model().item(joystick_combo.currentIndex()).data(Qt.UserRole)
                                    if data and data == guid:
                                        indices.append(i)
                                except Exception:
                                    indices.append(i)
                            elif isinstance(cfg_instance, ControllerConfig) and cfg_instance.guid:
                                if guid == cfg_instance.guid:
                                    indices.append(i)
                            else:
                                indices.append(i)
                        except Exception:
                            continue
                except Exception:
                    pass

                if not indices:
                    QMessageBox.information(self, "No joystick", "No joystick available for capture.")
                    return False

                dlg = QDialog(self)
                dlg.setWindowTitle(f"Capture axis for {act}")
                dlg.setModal(True)
                dlg_layout = QVBoxLayout()
                lbl = QLabel("Move the joystick axis/stick strongly to capture...\nPress Cancel to abort.")
                dlg_layout.addWidget(lbl)
                btn_cancel = QPushButton("Cancel")
                dlg_layout.addWidget(btn_cancel)
                dlg.setLayout(dlg_layout)

                timer = QTimer(dlg)

                # We'll collect several baseline samples to compute a stable baseline
                baseline = {}
                baseline_samples = {}
                settle_polls = 4

                # Debounce: require consecutive detections on same axis
                move_counts = {}
                consecutive_required = 3
                polls_elapsed = {"count": 0}

                def poll_axes():
                    try:
                        pygame.event.pump()
                    except Exception:
                        return
                    polls_elapsed["count"] += 1
                    # use more significant thresholds to avoid spurious captures
                    threshold_abs = 0.5
                    threshold_delta = 0.4
                    for idx in indices:
                        try:
                            j = pygame.joystick.Joystick(idx)
                            try:
                                j.init()
                            except Exception:
                                pass
                            na = j.get_numaxes()
                            vals = [j.get_axis(a) for a in range(na)]
                            # collect baseline samples for the first few polls
                            if idx not in baseline_samples:
                                baseline_samples[idx] = []
                            if polls_elapsed["count"] <= settle_polls:
                                baseline_samples[idx].append(vals)
                                # wait until we have enough samples
                                continue
                            # compute averaged baseline if not yet computed
                            if idx not in baseline:
                                # average across collected samples
                                samples = baseline_samples.get(idx, [])
                                if samples:
                                    avg = [0.0] * na
                                    for s in samples:
                                        for a in range(min(len(s), na)):
                                            avg[a] += s[a]
                                    avg = [avg[a] / len(samples) for a in range(na)]
                                else:
                                    avg = [0.0] * na
                                baseline[idx] = avg

                            deltas = [abs(vals[a] - (baseline[idx][a] if a < len(baseline[idx]) else 0.0)) for a in range(na)]

                            # require a significant delta from the settled baseline
                            moved = [i for i in range(na) if deltas[i] > threshold_delta]
                            if not moved:
                                # reset counts for this joystick
                                for a in range(na):
                                    move_counts[(idx, a)] = 0
                                continue

                            # update consecutive counts
                            for a in range(na):
                                key = (idx, a)
                                if a in moved:
                                    move_counts[key] = move_counts.get(key, 0) + 1
                                else:
                                    move_counts[key] = 0

                            # wait a short settle period to ignore GUI-induced transients
                            if polls_elapsed["count"] < 4:
                                continue

                            # collect axes that meet consecutive requirement
                            candidates = [a for a in range(na) if move_counts.get((idx, a), 0) >= consecutive_required]
                            if not candidates:
                                continue

                            if want_pair:
                                    # prefer two most-moved axes among candidates (store stick id)
                                cand_sorted = sorted(candidates, key=lambda a: deltas[a], reverse=True)
                                if len(cand_sorted) >= 2:
                                    a1, a2 = cand_sorted[0], cand_sorted[1]
                                else:
                                    # if only one detected, try adjacent axis, else duplicate
                                    a1 = cand_sorted[0]
                                    if a1 + 1 < na:
                                        a2 = a1 + 1
                                    elif a1 - 1 >= 0:
                                        a2 = a1 - 1
                                    else:
                                        a2 = a1
                                # store both axes so later runtime can read both (represents the analog stick)
                                    stick_id = min(a1, a2) // 2
                                    set_mapping_for(act, f"stick:{stick_id}")
                                if val_label:
                                        val_label.setText(f"Stick {stick_id}")
                                timer.stop()
                                dlg.accept()
                                return
                            else:
                                # single axis mapping (rotation): pick candidate with largest delta
                                best = max(candidates, key=lambda a: deltas[a])
                                stick_id = best // 2
                                # store stick id only (remember whole analog)
                                set_mapping_for(act, f"stick:{stick_id}")
                                if val_label:
                                    val_label.setText(f"Stick {stick_id}")
                                timer.stop()
                                dlg.accept()
                                return
                        except Exception:
                            continue

                timer.timeout.connect(poll_axes)
                timer.start(50)

                def on_cancel():
                    try:
                        timer.stop()
                    except Exception:
                        pass
                    dlg.reject()

                btn_cancel.clicked.connect(on_cancel)
                result = dlg.exec()
                try:
                    timer.stop()
                except Exception:
                    pass
                return result == QDialog.Accepted

            # Movement row
            mv_row = W()
            mv_layout = H()
            mv_row.setLayout(mv_layout)
            mv_label = QLabel("Movement (forward/back/sideways)")
            mv_label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
            mv_val = QLabel(mapping_label(get_mapping_for(movement_action)))
            mv_val.setStyleSheet("font-size: 12px; color: #bbb; background: transparent;")
            mv_btn = QPushButton("Change")
            mv_btn.setCursor(Qt.PointingHandCursor)

            def on_mv_change():
                capture_axes(movement_action, want_pair=True, val_label=mv_val)

            mv_btn.clicked.connect(on_mv_change)
            mv_layout.addWidget(mv_label)
            mv_layout.addStretch(1)
            mv_layout.addWidget(mv_val)
            mv_layout.addWidget(mv_btn)
            movement_layout.addWidget(mv_row)
            mapping_rows[movement_action.value] = (mv_label, mv_val, mv_btn)

            # Rotation row
            rot_row = W()
            rot_layout = H()
            rot_row.setLayout(rot_layout)
            rot_label = QLabel("Rotation (turn)")
            rot_label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
            rot_val = QLabel(mapping_label(get_mapping_for(rotation_action)))
            rot_val.setStyleSheet("font-size: 12px; color: #bbb; background: transparent;")
            rot_btn = QPushButton("Change")
            rot_btn.setCursor(Qt.PointingHandCursor)

            def on_rot_change():
                capture_axes(rotation_action, want_pair=False, val_label=rot_val)

            rot_btn.clicked.connect(on_rot_change)
            rot_layout.addWidget(rot_label)
            rot_layout.addStretch(1)
            rot_layout.addWidget(rot_val)
            rot_layout.addWidget(rot_btn)
            movement_layout.addWidget(rot_row)
            mapping_rows[rotation_action.value] = (rot_label, rot_val, rot_btn)

            # Organize actions into groups matching ControllerAction categories
            movement_group = [ControllerAction.RUN, ControllerAction.SLOW]
            pose_group = [ControllerAction.STAND_UP, ControllerAction.STAND_DOWN, ControllerAction.STRETCH, ControllerAction.SIT]
            actions_group = [ControllerAction.HELLO, ControllerAction.JUMP, ControllerAction.FINGER_HEART, ControllerAction.DANCE1]
            other_group = [ControllerAction.TOGGLE_FLASH, ControllerAction.TOGGLE_LED]

            for action in simple_actions:
                row = W()
                row_layout = H()
                row.setLayout(row_layout)
                # action may be an Enum; display a human-friendly label
                label_text = action.value.replace("_", " ").capitalize() if hasattr(action, "value") else str(action)
                label = QLabel(label_text)
                label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")
                value = get_mapping_for(action)
                value_label = QLabel(mapping_label(value))
                value_label.setStyleSheet("font-size: 12px; color: #bbb; background: transparent;")
                btn = QPushButton("Change")
                btn.setCursor(Qt.PointingHandCursor)

                def make_handler(act, val_label):
                    def handler():
                        # Try to capture joystick button press for the selected joystick.
                        def try_capture_with_pygame(target_guid=None, target_name=None):
                            try:
                                import pygame

                                pygame.init()
                                pygame.joystick.init()
                            except Exception:
                                return False

                            # Build list of joystick indices to monitor
                            indices = []
                            try:
                                count = pygame.joystick.get_count()
                                for i in range(count):
                                    try:
                                        j = pygame.joystick.Joystick(i)
                                        try:
                                            j.init()
                                        except Exception:
                                            pass
                                        name = ""
                                        try:
                                            name = j.get_name() or ""
                                        except Exception:
                                            name = ""
                                        guid = ""
                                        try:
                                            guid_raw = j.get_guid() if hasattr(j, "get_guid") else ""
                                            guid = str(guid_raw) if guid_raw is not None else ""
                                        except Exception:
                                            guid = ""
                                        if target_guid:
                                            if guid == target_guid:
                                                indices.append(i)
                                        elif target_name:
                                            if name == target_name:
                                                indices.append(i)
                                        else:
                                            indices.append(i)
                                    except Exception:
                                        continue
                            except Exception:
                                return False

                            if not indices:
                                return False

                            # Show dialog and poll for button presses
                            dlg = QDialog(self)
                            dlg.setWindowTitle(f"Press button for {act}")
                            dlg.setModal(True)
                            dlg_layout = QVBoxLayout()
                            lbl = QLabel("Waiting for joystick button or D-pad press...\nPress Cancel to abort.")
                            dlg_layout.addWidget(lbl)
                            btn_cancel = QPushButton("Cancel")
                            dlg_layout.addWidget(btn_cancel)
                            dlg.setLayout(dlg_layout)

                            timer = QTimer(dlg)

                            # For axis-as-button detection: collect baseline samples then detect sustained delta
                            def poll():
                                try:
                                    pygame.event.pump()
                                except Exception:
                                    return
                                for idx in indices:
                                    try:
                                        j = pygame.joystick.Joystick(idx)
                                        try:
                                            j.init()
                                        except Exception:
                                            pass
                                        # check buttons
                                        nb = j.get_numbuttons()
                                        for b in range(nb):
                                            try:
                                                if j.get_button(b):
                                                    # capture
                                                    input_id = f"Button{b}"
                                                    set_mapping_for(act, input_id)
                                                    val_label.setText(mapping_label(input_id))
                                                    timer.stop()
                                                    dlg.accept()
                                                    return
                                            except Exception:
                                                continue

                                        # check D-pad / hat directions
                                        nh = j.get_numhats() if hasattr(j, "get_numhats") else 0
                                        for h in range(nh):
                                            try:
                                                hat_x, hat_y = j.get_hat(h)
                                            except Exception:
                                                continue
                                            if hat_y > 0:
                                                input_id = f"Hat{h}:Up"
                                            elif hat_y < 0:
                                                input_id = f"Hat{h}:Down"
                                            elif hat_x < 0:
                                                input_id = f"Hat{h}:Left"
                                            elif hat_x > 0:
                                                input_id = f"Hat{h}:Right"
                                            else:
                                                input_id = None

                                            if input_id:
                                                set_mapping_for(act, input_id)
                                                val_label.setText(mapping_label(input_id))
                                                timer.stop()
                                                dlg.accept()
                                                return

                                        # check axes for trigger-like buttons (some controllers expose triggers as axes)
                                        na = j.get_numaxes()
                                        try:
                                            # initialize counters and baseline storage on the function
                                            if not hasattr(poll, "count"):
                                                poll.count = 0
                                            poll.count += 1
                                            if not hasattr(poll, "axis_counts"):
                                                poll.axis_counts = {}
                                            if not hasattr(poll, "baseline_samples"):
                                                poll.baseline_samples = {}
                                            if not hasattr(poll, "baseline_avg"):
                                                poll.baseline_avg = {}

                                            settle_polls = 4
                                            threshold_delta = 0.4
                                            consecutive_required = 2

                                            # collect baseline samples for the first few polls
                                            for a in range(na):
                                                try:
                                                    v = j.get_axis(a)
                                                except Exception:
                                                    v = 0.0
                                                key = (idx, a)
                                                if poll.count <= settle_polls:
                                                    poll.baseline_samples.setdefault(key, []).append(v)
                                                    poll.axis_counts[key] = 0
                                                    continue

                                                # compute averaged baseline when we pass the settle window
                                                if key not in poll.baseline_avg:
                                                    samples = poll.baseline_samples.get(key, [])
                                                    if samples:
                                                        poll.baseline_avg[key] = sum(samples) / len(samples)
                                                    else:
                                                        poll.baseline_avg[key] = 0.0

                                                # detect significant delta from baseline
                                                delta = abs(v - poll.baseline_avg.get(key, 0.0))
                                                if delta > threshold_delta:
                                                    poll.axis_counts[key] = poll.axis_counts.get(key, 0) + 1
                                                else:
                                                    poll.axis_counts[key] = 0

                                                if poll.axis_counts.get(key, 0) >= consecutive_required:
                                                    # capture axis as a button-like input
                                                    # determine direction relative to baseline average
                                                    base = poll.baseline_avg.get(key, 0.0)
                                                    try:
                                                        delta = v - base
                                                    except Exception:
                                                        delta = 0.0
                                                    direction = '+' if delta >= 0 else '-'
                                                    input_id = f"Axis{a}:{direction}"
                                                    set_mapping_for(act, input_id)
                                                    val_label.setText(mapping_label(input_id))
                                                    timer.stop()
                                                    dlg.accept()
                                                    return
                                        except Exception:
                                            pass
                                    except Exception:
                                        continue

                            timer.timeout.connect(poll)
                            timer.start(50)

                            def on_cancel():
                                try:
                                    timer.stop()
                                except Exception:
                                    pass
                                dlg.reject()

                            btn_cancel.clicked.connect(on_cancel)
                            result = dlg.exec()
                            try:
                                timer.stop()
                            except Exception:
                                pass
                            return result == QDialog.Accepted

                        # Determine target joystick from selector or cfg_instance
                        target_guid = None
                        target_name = None
                        try:
                            if 'joystick_combo' in locals() and joystick_combo is not None and joystick_combo.isEnabled():
                                # itemData holds guid or name
                                data = joystick_combo.model().item(joystick_combo.currentIndex()).data(Qt.UserRole)
                                # try to use as guid first
                                target_guid = data
                            elif isinstance(cfg_instance, ControllerConfig) and cfg_instance.guid:
                                target_guid = cfg_instance.guid
                            elif isinstance(cfg_instance, ControllerConfig) and cfg_instance.name:
                                target_name = cfg_instance.name
                        except Exception:
                            target_guid = None
                            target_name = None

                        captured = try_capture_with_pygame(target_guid=target_guid, target_name=target_name)
                        if not captured:
                            QMessageBox.information(self, "No input captured", "No joystick input detected or joystick unavailable.")

                    return handler

                btn.clicked.connect(make_handler(action, value_label))
                row_layout.addWidget(label)
                row_layout.addStretch(1)
                row_layout.addWidget(value_label)
                row_layout.addWidget(btn)
                # Place the row into the appropriate group layout
                if action in movement_group:
                    movement_layout.addWidget(row)
                elif action in pose_group:
                    pose_layout.addWidget(row)
                elif action in actions_group:
                    actions_layout.addWidget(row)
                elif action in other_group:
                    other_layout.addWidget(row)
                else:
                    # Default to actions layout
                    actions_layout.addWidget(row)
                # store mapping row keyed by action string for compatibility with existing storage
                act_key = action.value if hasattr(action, "value") else action
                mapping_rows[act_key] = (label, value_label, btn)
            # Adjust visible label text for 'slow' if present
            try:
                special_slow = ControllerAction.SLOW.value
                if special_slow in mapping_rows:
                    try:
                        mapping_rows[special_slow][0].setText('Slow down')
                    except Exception:
                        pass
            except Exception:
                pass

            # Wrap mappings in a scroll area so long lists are scrollable
            # Combine movement and actions sections into a single scrollable area
            movement_section = QtSection("Movement", movement_widget)
            movement_section.setContentsMargins(16, 0, 16, 0)
            pose_section = QtSection("Pose", pose_widget)
            pose_section.setContentsMargins(16, 0, 16, 0)
            actions_section = QtSection("Actions", actions_widget)
            actions_section.setContentsMargins(16, 0, 16, 0)
            other_section = QtSection("Other", other_widget)
            other_section.setContentsMargins(16, 0, 16, 0)

            content_widget = QWidget()
            content_layout = QVBoxLayout()
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(8)
            content_widget.setLayout(content_layout)
            content_layout.addWidget(movement_section)
            content_layout.addWidget(pose_section)
            content_layout.addWidget(actions_section)
            content_layout.addWidget(other_section)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content_widget)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setStyleSheet("background-color: #303032;")
            layout.addWidget(scroll)

        if cfg_instance.type == ControllerType.KEYBOARD:
            from PyQt5.QtWidgets import QWidget as W, QVBoxLayout as V, QHBoxLayout as H

            movement_widget = W()
            movement_layout = V()
            movement_layout.setContentsMargins(0, 0, 0, 0)
            movement_layout.setSpacing(4)
            movement_widget.setLayout(movement_layout)

            actions_widget = W()
            actions_layout = V()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(4)
            actions_widget.setLayout(actions_layout)

            pose_widget = W()
            pose_layout = V()
            pose_layout.setContentsMargins(0, 0, 0, 0)
            pose_layout.setSpacing(4)
            pose_widget.setLayout(pose_layout)

            other_widget = W()
            other_layout = V()
            other_layout.setContentsMargins(0, 0, 0, 0)
            other_layout.setSpacing(4)
            other_widget.setLayout(other_layout)

            keyboard_movement_actions = [
                "front",
                "back",
                "side_left",
                "side_right",
                "rotate_left",
                "rotate_right",
                ControllerAction.RUN,
                ControllerAction.SLOW,
            ]
            pose_group = [ControllerAction.STAND_UP, ControllerAction.STAND_DOWN, ControllerAction.STRETCH, ControllerAction.SIT]
            actions_group = [ControllerAction.HELLO, ControllerAction.JUMP, ControllerAction.FINGER_HEART, ControllerAction.DANCE1]
            other_group = [ControllerAction.TOGGLE_FLASH, ControllerAction.TOGGLE_LED]

            if cfg_instance.mappings is None:
                cfg_instance.mappings = []

            def _action_key(action):
                return action.value if hasattr(action, "value") else str(action)

            def _get_mapping_for(action):
                key = _action_key(action)
                for m in cfg_instance.mappings:
                    if m.get("action") == key:
                        return m.get("input")
                return None

            def _set_mapping_for(action, input_id):
                key = _action_key(action)
                for m in list(cfg_instance.mappings):
                    if m.get("action") != key and m.get("input") == input_id:
                        try:
                            cfg_instance.mappings.remove(m)
                        except Exception:
                            pass
                for m in cfg_instance.mappings:
                    if m.get("action") == key:
                        m["input"] = input_id
                        return
                cfg_instance.mappings.append({"action": key, "input": input_id})

            def _display_key(input_id):
                if not input_id:
                    return "(not set)"
                try:
                    if isinstance(input_id, str) and input_id.startswith("Key:"):
                        key_int = int(input_id.split(":", 1)[1])
                        special_names = {
                            Qt.Key_Space: "Space",
                            Qt.Key_Tab: "Tab",
                            Qt.Key_Backtab: "Shift+Tab",
                            Qt.Key_Backspace: "Backspace",
                            Qt.Key_Return: "Enter",
                            Qt.Key_Enter: "Numpad Enter",
                            Qt.Key_Escape: "Escape",
                            Qt.Key_Insert: "Insert",
                            Qt.Key_Delete: "Delete",
                            Qt.Key_Pause: "Pause",
                            Qt.Key_Print: "Print Screen",
                            Qt.Key_SysReq: "SysRq",
                            Qt.Key_Clear: "Clear",
                            Qt.Key_Home: "Home",
                            Qt.Key_End: "End",
                            Qt.Key_Left: "Left",
                            Qt.Key_Up: "Up",
                            Qt.Key_Right: "Right",
                            Qt.Key_Down: "Down",
                            Qt.Key_PageUp: "Page Up",
                            Qt.Key_PageDown: "Page Down",
                            Qt.Key_Shift: "Shift",
                            Qt.Key_Control: "Ctrl",
                            Qt.Key_Meta: "Meta",
                            Qt.Key_Alt: "Alt",
                            Qt.Key_CapsLock: "Caps Lock",
                            Qt.Key_NumLock: "Num Lock",
                            Qt.Key_ScrollLock: "Scroll Lock",
                            Qt.Key_Menu: "Menu",
                            Qt.Key_Help: "Help",
                            Qt.Key_Super_L: "Left Super",
                            Qt.Key_Super_R: "Right Super",
                            Qt.Key_AltGr: "AltGr",
                            Qt.Key_unknown: "Unknown",
                        }
                        if key_int in special_names:
                            return special_names[key_int]

                        # A-Z
                        if Qt.Key_A <= key_int <= Qt.Key_Z:
                            return chr(key_int)
                        # 0-9
                        if Qt.Key_0 <= key_int <= Qt.Key_9:
                            return chr(key_int)
                        # F1-F35
                        if Qt.Key_F1 <= key_int <= Qt.Key_F35:
                            return f"F{key_int - Qt.Key_F1 + 1}"
                        # Numpad digits
                        if Qt.Key_0 <= key_int <= Qt.Key_9 and (key_int & Qt.KeypadModifier):
                            return f"Numpad {chr(key_int)}"

                        # Common punctuation keys
                        punctuation = {
                            Qt.Key_Minus: "-",
                            Qt.Key_Equal: "=",
                            Qt.Key_BracketLeft: "[",
                            Qt.Key_BracketRight: "]",
                            Qt.Key_Backslash: "\\",
                            Qt.Key_Semicolon: ";",
                            Qt.Key_Apostrophe: "'",
                            Qt.Key_Comma: ",",
                            Qt.Key_Period: ".",
                            Qt.Key_Slash: "/",
                            Qt.Key_QuoteLeft: "`",
                        }
                        if key_int in punctuation:
                            return punctuation[key_int]

                        key_name = QKeySequence(key_int).toString(QKeySequence.NativeText)
                        return key_name if key_name else f"Key {key_int}"
                except Exception:
                    pass
                return str(input_id)

            def _capture_keyboard_key(title):
                class _CaptureDialog(QDialog):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.captured_key = None
                        self.setWindowTitle(title)
                        self.setModal(True)
                        dlg_layout = QVBoxLayout()
                        dlg_layout.addWidget(QLabel("Press any keyboard key to map this action..."))
                        btn_cancel = QPushButton("Cancel")
                        btn_cancel.clicked.connect(self.reject)
                        dlg_layout.addWidget(btn_cancel)
                        self.setLayout(dlg_layout)

                    def keyPressEvent(self, event):
                        self.captured_key = event.key()
                        self.accept()

                dlg = _CaptureDialog(self)
                result = dlg.exec()
                if result == QDialog.Accepted and dlg.captured_key is not None:
                    return f"Key:{int(dlg.captured_key)}"
                return None

            def _display_label_for_action(action):
                if isinstance(action, str):
                    return action.replace("_", " ").capitalize()
                return action.value.replace("_", " ").capitalize()

            all_keyboard_actions = keyboard_movement_actions + pose_group + actions_group + other_group

            for action in all_keyboard_actions:
                row = W()
                row_layout = H()
                row.setLayout(row_layout)

                label = QLabel(_display_label_for_action(action))
                label.setStyleSheet("font-size: 13px; color: #fff; background: transparent;")

                mapped_input = _get_mapping_for(action)
                value_label = QLabel(_display_key(mapped_input))
                value_label.setStyleSheet("font-size: 12px; color: #bbb; background: transparent;")

                btn = QPushButton("Change")
                btn.setCursor(Qt.PointingHandCursor)

                def make_key_handler(act, val_label):
                    def _handler():
                        captured = _capture_keyboard_key(f"Press key for {_display_label_for_action(act)}")
                        if captured:
                            _set_mapping_for(act, captured)
                            val_label.setText(_display_key(captured))

                    return _handler

                btn.clicked.connect(make_key_handler(action, value_label))
                row_layout.addWidget(label)
                row_layout.addStretch(1)
                row_layout.addWidget(value_label)
                row_layout.addWidget(btn)

                if action in keyboard_movement_actions:
                    movement_layout.addWidget(row)
                elif action in pose_group:
                    pose_layout.addWidget(row)
                elif action in actions_group:
                    actions_layout.addWidget(row)
                else:
                    other_layout.addWidget(row)

            movement_section = QtSection("Movement", movement_widget)
            movement_section.setContentsMargins(16, 0, 16, 0)
            pose_section = QtSection("Pose", pose_widget)
            pose_section.setContentsMargins(16, 0, 16, 0)
            actions_section = QtSection("Actions", actions_widget)
            actions_section.setContentsMargins(16, 0, 16, 0)
            other_section = QtSection("Other", other_widget)
            other_section.setContentsMargins(16, 0, 16, 0)

            content_widget = QWidget()
            content_layout = QVBoxLayout()
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(8)
            content_widget.setLayout(content_layout)
            content_layout.addWidget(movement_section)
            content_layout.addWidget(pose_section)
            content_layout.addWidget(actions_section)
            content_layout.addWidget(other_section)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content_widget)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setStyleSheet("background-color: #303032;")
            layout.addWidget(scroll)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        # If adding (controller provided as type/class or unsaved instance) show Create
        if is_new:
            create_btn = QPushButton("Create")
            create_btn.setCursor(Qt.PointingHandCursor)
            create_btn.setStyleSheet(
                "font-size: 14px; padding: 8px 24px; background: #222; color: white; border-radius: 6px;"
            )

            def on_create():
                # Use the controller type from the cfg_instance passed to this view
                ctype = cfg_instance.type
                # Get selected guid/data from combo if joystick
                selected_guid = None
                if ctype == ControllerType.JOYSTICK:
                    try:
                        selected_guid = joystick_combo.itemData(joystick_combo.currentIndex())
                    except Exception:
                        selected_guid = None
                # Use the selected joystick name as the stored name when available
                selected_name = None
                if ctype == ControllerType.JOYSTICK:
                    try:
                        selected_name = joystick_combo.itemText(joystick_combo.currentIndex())
                    except Exception:
                        selected_name = None
                cfg = ControllerConfig(type=ctype, guid=(selected_guid or None), name=(selected_name or None))
                # carry mappings from cfg_instance if present
                try:
                    cfg.mappings = list(cfg_instance.mappings) if getattr(cfg_instance, 'mappings', None) else []
                except Exception:
                    cfg.mappings = []
                repo = ControllersRepository()
                repo.add_controller(cfg)
                if back_action:
                    back_action(pop_to_root=True)

            create_btn.clicked.connect(on_create)
            btn_row.addWidget(create_btn)
            # Disable Create when there are no available joysticks to add
            try:
                if cfg_instance.type == ControllerType.JOYSTICK:
                    create_btn.setEnabled(has_available_joysticks)
            except Exception:
                pass
            btn_row.addStretch(1)
        else:
            # Editing existing controller: persist on back (no explicit Save/Delete buttons)
            btn_row.addStretch(1)

        btn_row_widget = QWidget()
        btn_row_widget.setLayout(btn_row)

        # Only show the bottom button panel if it contains any visible buttons
        # or when creating a new controller (always show Create button)
        show_bottom = bool(is_new)
        try:
            btns = btn_row_widget.findChildren(QPushButton)
            for b in btns:
                try:
                    if b.isVisible():
                        show_bottom = True
                        break
                except Exception:
                    # if visibility can't be determined, assume visible
                    show_bottom = True
                    break
        except Exception:
            show_bottom = False

        if show_bottom:
            layout.addWidget(btn_row_widget)
            layout.addStretch(1)

        self.setLayout(layout)

    def _get_title(self):
        # Title depends on whether we're adding or editing
        repo = ControllersRepository()
        if isinstance(self.controller, type):
            return "Add controller"
        if isinstance(self.controller, ControllerConfig):
            exists = any(
                (c.type == self.controller.type and c.guid == self.controller.guid)
                for c in repo.get_controllers()
            )
            return "Edit controller" if exists else "Add controller"
        return "Edit controller"

    def setup_background(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)
