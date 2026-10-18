import bpy

class _FakeBoneGroup:
    def __init__(self, pose, coll):
        self._pose = pose
        self._coll = coll

    @property
    def name(self):
        return self._coll.name if self._coll else "Group"

    @name.setter
    def name(self, val):
        if self._coll:
            self._coll.name = val

    @property
    def color_set(self):
        return self._coll.get("oni_color_set", "DEFAULT") if self._coll else "DEFAULT"

    @color_set.setter
    def color_set(self, val):
        if not self._coll:
            return
        self._coll["oni_color_set"] = val
        # En Blender 4.0/5.x el color está en el hueso directamente
        valid_palettes = {f"THEME{i:02d}" for i in range(1, 21)} | {"DEFAULT", "CUSTOM"}
        pal = val if val in valid_palettes else "DEFAULT"
        for b in self._coll.bones:
            try:
                b.color.palette = pal
            except Exception:
                pass
            if self._pose and b.name in self._pose.bones:
                try:
                    self._pose.bones[b.name].color.palette = pal
                except Exception:
                    pass


class _FakeBoneGroups:
    def __init__(self, pose):
        self._pose = pose

    def _arm(self):
        return self._pose.id_data.data if (self._pose and self._pose.id_data) else None

    def new(self, name="Group"):
        arm = self._arm()
        if not arm:
            return None
        coll = arm.collections.get(name) or arm.collections.new(name)
        arm["oni_active_bg"] = coll.name
        return _FakeBoneGroup(self._pose, coll)

    def remove(self, bg):
        arm = self._arm()
        if arm and bg and bg._coll:
            try:
                arm.collections.remove(bg._coll)
            except Exception:
                pass

    @property
    def active(self):
        arm = self._arm()
        if not arm or len(arm.collections) == 0:
            return None
        act_name = arm.get("oni_active_bg", "")
        coll = arm.collections.get(act_name) or arm.collections.active or arm.collections[0]
        return _FakeBoneGroup(self._pose, coll)

    @active.setter
    def active(self, bg):
        arm = self._arm()
        if arm and bg and bg._coll:
            arm["oni_active_bg"] = bg._coll.name
            try:
                arm.collections.active = bg._coll
            except Exception:
                pass

    @property
    def active_index(self):
        arm = self._arm()
        if not arm or len(arm.collections) == 0:
            return 0
        act = self.active
        for i, c in enumerate(arm.collections):
            if act and c.name == act.name:
                return i
        return 0

    @active_index.setter
    def active_index(self, idx):
        arm = self._arm()
        if arm and 0 <= idx < len(arm.collections):
            arm["oni_active_bg"] = arm.collections[idx].name

    def get(self, key, default=None):
        arm = self._arm()
        if arm and key in arm.collections:
            return _FakeBoneGroup(self._pose, arm.collections[key])
        return default

    def keys(self):
        arm = self._arm()
        return [c.name for c in arm.collections] if arm else []

    def values(self):
        arm = self._arm()
        return [_FakeBoneGroup(self._pose, c) for c in arm.collections] if arm else []

    def items(self):
        arm = self._arm()
        return [(c.name, _FakeBoneGroup(self._pose, c)) for c in arm.collections] if arm else []

    def __contains__(self, key):
        arm = self._arm()
        if isinstance(key, str):
            return (key in arm.collections) if arm else False
        return False

    def __getitem__(self, key):
        arm = self._arm()
        if not arm:
            raise KeyError(key)
        if isinstance(key, int):
            if 0 <= key < len(arm.collections):
                return _FakeBoneGroup(self._pose, arm.collections[key])
            raise IndexError(key)
        if key not in arm.collections:
            coll = arm.collections.new(str(key))
            return _FakeBoneGroup(self._pose, coll)
        return _FakeBoneGroup(self._pose, arm.collections[key])

    def __iter__(self):
        arm = self._arm()
        if arm:
            for c in arm.collections:
                yield _FakeBoneGroup(self._pose, c)

    def __len__(self):
        arm = self._arm()
        return len(arm.collections) if arm else 0


class _FakeArmatureLayers:
    def __init__(self, arm):
        self._arm = arm

    def _ensure_state(self):
        if "oni_layers" not in self._arm:
            state = [True] + [False] * 31
            self._arm["oni_layers"] = state
        return list(self._arm["oni_layers"])

    def __getitem__(self, idx):
        state = self._ensure_state()
        if isinstance(idx, slice):
            return state[idx]
        return bool(state[idx]) if 0 <= idx < 32 else False

    def __setitem__(self, idx, val):
        state = self._ensure_state()
        if isinstance(idx, slice):
            state[idx] = [bool(v) for v in val]
        elif 0 <= idx < 32:
            state[idx] = bool(val)
            cname = f"Layer_{idx}"
            if cname in self._arm.collections:
                self._arm.collections[cname].is_visible = bool(val)
        self._arm["oni_layers"] = state

    def __len__(self):
        return 32

    def __iter__(self):
        return iter(self._ensure_state())


class _FakeBoneLayers:
    def __init__(self, bone):
        self._bone = bone

    def _arm(self):
        id_data = self._bone.id_data
        if isinstance(id_data, bpy.types.Object):
            return id_data.data
        return id_data

    def _bname(self):
        return self._bone.name

    def __getitem__(self, idx):
        arm = self._arm()
        key = f"oni_blayer_{self._bname()}"
        state = list(arm.get(key, [True] + [False] * 31)) if arm else ([True] + [False] * 31)
        if isinstance(idx, slice):
            return state[idx]
        return bool(state[idx]) if 0 <= idx < 32 else False

    def __setitem__(self, idx, val):
        arm = self._arm()
        if not arm:
            return
        key = f"oni_blayer_{self._bname()}"
        state = list(arm.get(key, [True] + [False] * 31))
        if isinstance(idx, slice):
            state[idx] = [bool(v) for v in val]
        elif 0 <= idx < 32:
            state[idx] = bool(val)
        arm[key] = state

    def __len__(self):
        return 32

    def __iter__(self):
        return iter([self[i] for i in range(32)])


def _get_pose_bone_group(pbone):
    arm = pbone.id_data.data if pbone.id_data else None
    if not arm:
        return None
    bg_name = pbone.get("oni_bg_name", "")
    if bg_name and bg_name in arm.collections:
        return _FakeBoneGroup(pbone.id_data.pose, arm.collections[bg_name])
    if pbone.bone and len(pbone.bone.collections) > 0:
        return _FakeBoneGroup(pbone.id_data.pose, pbone.bone.collections[0])
    return None

def _set_pose_bone_group(pbone, bg):
    arm = pbone.id_data.data if pbone.id_data else None
    if not arm:
        return
    if bg is None:
        pbone["oni_bg_name"] = ""
        if pbone.bone:
            for c in list(pbone.bone.collections):
                c.unassign(pbone.bone)
        return
    coll = bg._coll if hasattr(bg, "_coll") else (arm.collections.get(str(bg)) or arm.collections.new(str(bg)))
    if coll:
        pbone["oni_bg_name"] = coll.name
        if pbone.bone:
            coll.assign(pbone.bone)
        pal = coll.get("oni_color_set", "DEFAULT")
        try:
            pbone.color.palette = pal
            if pbone.bone:
                pbone.bone.color.palette = pal
        except Exception:
            pass

def _get_pose_bone_group_index(pbone):
    arm = pbone.id_data.data if pbone.id_data else None
    bg = _get_pose_bone_group(pbone)
    if arm and bg:
        for i, c in enumerate(arm.collections):
            if c.name == bg.name:
                return i
    return 0

def _set_pose_bone_group_index(pbone, idx):
    arm = pbone.id_data.data if pbone.id_data else None
    if arm and 0 <= idx < len(arm.collections):
        _set_pose_bone_group(pbone, _FakeBoneGroup(pbone.id_data.pose, arm.collections[idx]))

def install_b5_shims():
    # 1. Armature.layers
    if not hasattr(bpy.types.Armature, "layers"):
        bpy.types.Armature.layers = property(
            lambda self: _FakeArmatureLayers(self),
            lambda self, val: _FakeArmatureLayers(self).__setitem__(slice(None), val)
        )
    # 2. Bone.layers & EditBone.layers & PoseBone.layers
    for btype in (bpy.types.Bone, bpy.types.EditBone, bpy.types.PoseBone):
        if not hasattr(btype, "layers"):
            btype.layers = property(
                lambda self: _FakeBoneLayers(self),
                lambda self, val: _FakeBoneLayers(self).__setitem__(slice(None), val)
            )
    # 3. Pose.bone_groups
    if not hasattr(bpy.types.Pose, "bone_groups"):
        bpy.types.Pose.bone_groups = property(lambda self: _FakeBoneGroups(self))
    # 4. PoseBone.bone_group & bone_group_index
    if not hasattr(bpy.types.PoseBone, "bone_group"):
        bpy.types.PoseBone.bone_group = property(_get_pose_bone_group, _set_pose_bone_group)
    if not hasattr(bpy.types.PoseBone, "bone_group_index"):
        bpy.types.PoseBone.bone_group_index = property(_get_pose_bone_group_index, _set_pose_bone_group_index)
    # 5. Mesh.use_auto_smooth
    if not hasattr(bpy.types.Mesh, "use_auto_smooth"):
        bpy.types.Mesh.use_auto_smooth = property(lambda self: True, lambda self, val: None)

install_b5_shims()


def _oni_childof_set_inverse(ctx_dict, **kwargs):
    with bpy.context.temp_override(**ctx_dict):
        return bpy.ops.constraint.childof_set_inverse(**kwargs)
import builtins
builtins._oni_childof_set_inverse = _oni_childof_set_inverse
