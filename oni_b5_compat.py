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


# === EXPORTADOR COLLADA 1.4.1 Y OPERADORES RESTANTES PARA BLENDER 5.2 ===
import os
import math
import mathutils
import bmesh

def _mat_to_str(mat):
    vals = []
    for row in mat:
        for v in row:
            vals.append(f"{v:.6f}")
    return " ".join(vals)

def _write_oni_collada_141(
    context,
    filepath,
    apply_modifiers=True,
    selected=True,
    include_children=False,
    include_armatures=True,
    deform_bones_only=True,
    triangulate=False,
    sort_by_name=True,
    open_sim=True,
    global_forward='Y',
    global_up='Z',
    apply_global_orientation=False,
):
    objs = list(context.selected_objects) if selected else list(context.scene.objects)
    if include_children:
        extra = []
        for o in objs:
            extra.extend(o.children_recursive)
        for o in extra:
            if o not in objs:
                objs.append(o)

    arm_objs = [o for o in objs if o.type == 'ARMATURE']
    mesh_objs = [o for o in objs if o.type == 'MESH']
    if sort_by_name:
        mesh_objs.sort(key=lambda o: o.name)

    arm_obj = arm_objs[0] if arm_objs else None
    if not arm_obj:
        for m in mesh_objs:
            if m.parent and m.parent.type == 'ARMATURE':
                arm_obj = m.parent
                break
            for mod in m.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    arm_obj = mod.object
                    break

    depsgraph = context.evaluated_depsgraph_get()

    lines = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">')
    lines.append('  <asset>')
    lines.append('    <contributor>')
    lines.append('      <author>Blender User</author>')
    lines.append('      <authoring_tool>Blender 5.2.0 Onigiri Collada Exporter</authoring_tool>')
    lines.append('    </contributor>')
    lines.append('    <created>2026-01-01T00:00:00</created>')
    lines.append('    <modified>2026-01-01T00:00:00</modified>')
    lines.append('    <unit name="meter" meter="1"/>')
    lines.append(f'    <up_axis>{global_up}_UP</up_axis>')
    lines.append('  </asset>')
    lines.append('  <library_images/>')

    # Recopilar materiales
    materials = []
    for m_obj in mesh_objs:
        for slot in m_obj.material_slots:
            if slot.material and slot.material not in materials:
                materials.append(slot.material)

    # library_effects
    lines.append('  <library_effects>')
    for mat in materials:
        mid = mat.name.replace(" ", "_")
        lines.append(f'    <effect id="{mid}-effect">')
        lines.append('      <profile_COMMON>')
        lines.append('        <technique sid="common">')
        lines.append('          <lambert>')
        lines.append('            <diffuse>')
        c = mat.diffuse_color
        lines.append(f'              <color sid="diffuse">{c[0]:.6f} {c[1]:.6f} {c[2]:.6f} {c[3]:.6f}</color>')
        lines.append('            </diffuse>')
        lines.append('          </lambert>')
        lines.append('        </technique>')
        lines.append('      </profile_COMMON>')
        lines.append('    </effect>')
    lines.append('  </library_effects>')

    # library_materials
    lines.append('  <library_materials>')
    for mat in materials:
        mid = mat.name.replace(" ", "_")
        lines.append(f'    <material id="{mid}-material" name="{mat.name}">')
        lines.append(f'      <instance_effect url="#{mid}-effect"/>')
        lines.append('    </material>')
    lines.append('  </library_materials>')

    # library_geometries
    lines.append('  <library_geometries>')
    mesh_skin_data = {}

    for m_obj in mesh_objs:
        if apply_modifiers:
            # Desactivar temporalmente el modificador Armature para obtener la malla en bind pose con otros modificadores aplicados
            arm_mods = []
            for mod in m_obj.modifiers:
                if mod.type == 'ARMATURE' and mod.show_viewport:
                    arm_mods.append(mod)
                    mod.show_viewport = False
            depsgraph.update()
            eval_obj = m_obj.evaluated_get(depsgraph)
            me = bpy.data.meshes.new_from_object(eval_obj)
            for mod in arm_mods:
                mod.show_viewport = True
            depsgraph.update()
        else:
            me = m_obj.data.copy()

        if triangulate:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.triangulate(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()

        me.calc_loop_triangles()
        geom_id = f"{m_obj.name}-mesh"
        lines.append(f'    <geometry id="{geom_id}" name="{m_obj.name}">')
        lines.append('      <mesh>')

        # Positions
        pos_floats = []
        for v in me.vertices:
            co = v.co
            pos_floats.extend([f"{co.x:.6f}", f"{co.y:.6f}", f"{co.z:.6f}"])
        v_count = len(me.vertices)
        lines.append(f'        <source id="{geom_id}-positions">')
        lines.append(f'          <float_array id="{geom_id}-positions-array" count="{v_count * 3}">{" ".join(pos_floats)}</float_array>')
        lines.append('          <technique_common>')
        lines.append(f'            <accessor source="#{geom_id}-positions-array" count="{v_count}" stride="3">')
        lines.append('              <param name="X" type="float"/>')
        lines.append('              <param name="Y" type="float"/>')
        lines.append('              <param name="Z" type="float"/>')
        lines.append('            </accessor>')
        lines.append('          </technique_common>')
        lines.append('        </source>')

        # Normals (por loop)
        norm_floats = []
        for loop in me.loops:
            no = loop.normal if hasattr(loop, "normal") and loop.normal.length > 0 else me.vertices[loop.vertex_index].normal
            norm_floats.extend([f"{no.x:.6f}", f"{no.y:.6f}", f"{no.z:.6f}"])
        l_count = len(me.loops)
        lines.append(f'        <source id="{geom_id}-normals">')
        lines.append(f'          <float_array id="{geom_id}-normals-array" count="{l_count * 3}">{" ".join(norm_floats)}</float_array>')
        lines.append('          <technique_common>')
        lines.append(f'            <accessor source="#{geom_id}-normals-array" count="{l_count}" stride="3">')
        lines.append('              <param name="X" type="float"/>')
        lines.append('              <param name="Y" type="float"/>')
        lines.append('              <param name="Z" type="float"/>')
        lines.append('            </accessor>')
        lines.append('          </technique_common>')
        lines.append('        </source>')

        # UVs
        uv_layers = me.uv_layers
        has_uv = len(uv_layers) > 0
        if has_uv:
            for uv_idx, uv_layer in enumerate(uv_layers):
                uv_floats = []
                for d in uv_layer.data:
                    uv_floats.extend([f"{d.uv.x:.6f}", f"{d.uv.y:.6f}"])
                lines.append(f'        <source id="{geom_id}-map-{uv_idx}">')
                lines.append(f'          <float_array id="{geom_id}-map-{uv_idx}-array" count="{l_count * 2}">{" ".join(uv_floats)}</float_array>')
                lines.append('          <technique_common>')
                lines.append(f'            <accessor source="#{geom_id}-map-{uv_idx}-array" count="{l_count}" stride="2">')
                lines.append('              <param name="S" type="float"/>')
                lines.append('              <param name="T" type="float"/>')
                lines.append('            </accessor>')
                lines.append('          </technique_common>')
                lines.append('        </source>')

        lines.append(f'        <vertices id="{geom_id}-vertices">')
        lines.append(f'          <input semantic="POSITION" source="#{geom_id}-positions"/>')
        lines.append('        </vertices>')

        # Triangles agrupados por material
        mat_tris = {}
        for tri in me.loop_triangles:
            m_idx = tri.material_index
            mat_tris.setdefault(m_idx, []).append(tri)

        if not mat_tris:
            mat_tris[0] = []

        for m_idx, tris in mat_tris.items():
            mat_attr = ""
            if m_obj.material_slots and 0 <= m_idx < len(m_obj.material_slots) and m_obj.material_slots[m_idx].material:
                mname = m_obj.material_slots[m_idx].material.name.replace(" ", "_")
                mat_attr = f' material="{mname}-material"'
            lines.append(f'        <triangles count="{len(tris)}"{mat_attr}>')
            lines.append(f'          <input semantic="VERTEX" source="#{geom_id}-vertices" offset="0"/>')
            lines.append(f'          <input semantic="NORMAL" source="#{geom_id}-normals" offset="1"/>')
            stride_inputs = 2
            if has_uv:
                for uv_idx in range(len(uv_layers)):
                    lines.append(f'          <input semantic="TEXCOORD" source="#{geom_id}-map-{uv_idx}" offset="{2 + uv_idx}" set="{uv_idx}"/>')
                stride_inputs += len(uv_layers)
            p_indices = []
            for tri in tris:
                for v_i, l_i in zip(tri.vertices, tri.loops):
                    p_indices.append(str(v_i))
                    p_indices.append(str(l_i))
                    if has_uv:
                        for _ in range(len(uv_layers)):
                            p_indices.append(str(l_i))
            lines.append(f'          <p>{" ".join(p_indices)}</p>')
            lines.append('        </triangles>')

        lines.append('      </mesh>')
        lines.append('    </geometry>')

        # Guardar pesos de vértices para library_controllers
        vgroups = m_obj.vertex_groups
        vg_idx_to_name = {vg.index: vg.name for vg in vgroups}
        mesh_skin_data[m_obj.name] = {
            "v_count": v_count,
            "vg_map": vg_idx_to_name,
            "verts_weights": [[(g.group, g.weight) for g in v.groups] for v in me.vertices],
            "matrix_world": m_obj.matrix_world.copy(),
            "materials": [s.material for s in m_obj.material_slots if s.material]
        }
        bpy.data.meshes.remove(me)

    lines.append('  </library_geometries>')

    # library_controllers
    lines.append('  <library_controllers>')
    if arm_obj and include_armatures:
        arm_name_clean = arm_obj.name.replace(".", "_")
        # Lista de huesos deformadores
        export_bones = []
        for b in arm_obj.data.bones:
            if deform_bones_only and not b.use_deform:
                continue
            export_bones.append(b)
        if not export_bones:
            export_bones = list(arm_obj.data.bones)

        for m_obj in mesh_objs:
            sdata = mesh_skin_data[m_obj.name]
            cid = f"{arm_name_clean}_{m_obj.name}-skin"
            geom_id = f"{m_obj.name}-mesh"
            lines.append(f'    <controller id="{cid}" name="{arm_name_clean}">')
            lines.append(f'      <skin source="#{geom_id}">')
            lines.append(f'        <bind_shape_matrix>{_mat_to_str(sdata["matrix_world"])}</bind_shape_matrix>')

            # Determinar joints usados o del esqueleto
            bone_names = [b.name.replace(" ", "_") for b in export_bones]
            bone_idx_map = {b.name: idx for idx, b in enumerate(export_bones)}

            # source joints (Name_array)
            lines.append(f'        <source id="{cid}-joints">')
            lines.append(f'          <Name_array id="{cid}-joints-array" count="{len(bone_names)}">{" ".join(bone_names)}</Name_array>')
            lines.append('          <technique_common>')
            lines.append(f'            <accessor source="#{cid}-joints-array" count="{len(bone_names)}" stride="1">')
            lines.append('              <param name="JOINT" type="name"/>')
            lines.append('            </accessor>')
            lines.append('          </technique_common>')
            lines.append('        </source>')

            # source bind_poses (float4x4)
            bind_Author_floats = []
            for b in export_bones:
                inv_mat = (arm_obj.matrix_world @ b.matrix_local).inverted()
                bind_Author_floats.append(_mat_to_str(inv_mat))
            lines.append(f'        <source id="{cid}-bind_poses">')
            lines.append(f'          <float_array id="{cid}-bind_poses-array" count="{len(export_bones) * 16}">{" ".join(bind_Author_floats)}</float_array>')
            lines.append('          <technique_common>')
            lines.append(f'            <accessor source="#{cid}-bind_poses-array" count="{len(export_bones)}" stride="16">')
            lines.append('              <param name="TRANSFORM" type="float4x4"/>')
            lines.append('            </accessor>')
            lines.append('          </technique_common>')
            lines.append('        </source>')

            # source weights
            weight_floats = []
            vcount_list = []
            v_pairs = []
            w_idx = 0
            vg_map = sdata["vg_map"]
            for vw in sdata["verts_weights"]:
                valid_vw = []
                for g_idx, w_val in vw:
                    bname = vg_map.get(g_idx)
                    if bname in bone_idx_map and w_val > 0.00001:
                        valid_vw.append((bone_idx_map[bname], w_val))
                vcount_list.append(str(len(valid_vw)))
                for j_idx, w_val in valid_vw:
                    weight_floats.append(f"{w_val:.6f}")
                    v_pairs.append(f"{j_idx} {w_idx}")
                    w_idx += 1

            if not weight_floats:
                weight_floats.append("1.000000")

            lines.append(f'        <source id="{cid}-weights">')
            lines.append(f'          <float_array id="{cid}-weights-array" count="{len(weight_floats)}">{" ".join(weight_floats)}</float_array>')
            lines.append('          <technique_common>')
            lines.append(f'            <accessor source="#{cid}-weights-array" count="{len(weight_floats)}" stride="1">')
            lines.append('              <param name="WEIGHT" type="float"/>')
            lines.append('            </accessor>')
            lines.append('          </technique_common>')
            lines.append('        </source>')

            lines.append('        <joints>')
            lines.append(f'          <input semantic="JOINT" source="#{cid}-joints"/>')
            lines.append(f'          <input semantic="INV_BIND_MATRIX" source="#{cid}-bind_poses"/>')
            lines.append('        </joints>')

            lines.append(f'        <vertex_weights count="{sdata["v_count"]}">')
            lines.append(f'          <input semantic="JOINT" source="#{cid}-joints" offset="0"/>')
            lines.append(f'          <input semantic="WEIGHT" source="#{cid}-weights" offset="1"/>')
            lines.append(f'          <vcount>{" ".join(vcount_list)}</vcount>')
            lines.append(f'          <v>{" ".join(v_pairs)}</v>')
            lines.append('        </vertex_weights>')

            lines.append('      </skin>')
            lines.append('    </controller>')
    lines.append('  </library_controllers>')

    # library_visual_scenes
    lines.append('  <library_visual_scenes>')
    lines.append('    <visual_scene id="Scene" name="Scene">')
    if arm_obj:
        arm_id = arm_obj.name.replace(".", "_")
        lines.append(f'      <node id="{arm_id}" name="{arm_obj.name}" type="NODE">')
        lines.append(f'        <matrix sid="transform">{_mat_to_str(arm_obj.matrix_world)}</matrix>')

        # Recursivamente escribir los huesos como nodos JOINT
        def _write_bone_node(bone, indent="        "):
            bname = bone.name.replace(" ", "_")
            if bone.parent:
                local_mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
            else:
                local_mat = bone.matrix_local
            lines.append(f'{indent}<node id="{bname}" name="{bname}" sid="{bname}" type="JOINT">')
            lines.append(f'{indent}  <matrix sid="transform">{_mat_to_str(local_mat)}</matrix>')
            for child in bone.children:
                _write_bone_node(child, indent + "  ")
            lines.append(f'{indent}</node>')

        root_bones = [b for b in arm_obj.data.bones if b.parent is None]
        for rb in root_bones:
            _write_bone_node(rb, "        ")

        root_bone_name = root_bones[0].name.replace(" ", "_") if root_bones else "mPelvis"

        # Nodos de malla con instance_controller dentro del nodo padre del Armature (como espera devkit.py línea 637)
        for m_obj in mesh_objs:
            cid = f"{arm_id}_{m_obj.name}-skin"
            mid = m_obj.name.replace(".", "_")
            lines.append(f'        <node id="{mid}" name="{m_obj.name}" type="NODE">')
            lines.append(f'          <matrix sid="transform">{_mat_to_str(mathutils.Matrix.Identity(4))}</matrix>')
            lines.append(f'          <instance_controller url="#{cid}">')
            lines.append(f'            <skeleton>#{root_bone_name}</skeleton>')
            mats = mesh_skin_data[m_obj.name]["materials"]
            if mats:
                lines.append('            <bind_material>')
                lines.append('              <technique_common>')
                for mat in mats:
                    mname = mat.name.replace(" ", "_")
                    lines.append(f'                <instance_material symbol="{mname}-material" target="#{mname}-material"/>')
                lines.append('              </technique_common>')
                lines.append('            </bind_material>')
            lines.append('          </instance_controller>')
            lines.append('        </node>')

        lines.append('      </node>')
    else:
        for m_obj in mesh_objs:
            mid = m_obj.name.replace(".", "_")
            lines.append(f'      <node id="{mid}" name="{m_obj.name}" type="NODE">')
            lines.append(f'        <matrix sid="transform">{_mat_to_str(m_obj.matrix_world)}</matrix>')
            lines.append(f'        <instance_geometry url="#{m_obj.name}-mesh"/>')
            lines.append('      </node>')

    lines.append('    </visual_scene>')
    lines.append('  </library_visual_scenes>')
    lines.append('  <scene>')
    lines.append('    <instance_visual_scene url="#Scene"/>')
    lines.append('  </scene>')
    lines.append('</COLLADA>')

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


class WM_OT_oni_collada_export(bpy.types.Operator):
    bl_idname = "wm.collada_export"
    bl_label = "Export COLLADA (Onigiri B5 Compat)"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="")
    check_existing: bpy.props.BoolProperty(default=True)
    apply_modifiers: bpy.props.BoolProperty(default=True)
    export_mesh_type_selection: bpy.props.StringProperty(default='render')
    selected: bpy.props.BoolProperty(default=True)
    include_children: bpy.props.BoolProperty(default=False)
    include_armatures: bpy.props.BoolProperty(default=True)
    include_shapekeys: bpy.props.BoolProperty(default=False)
    include_animations: bpy.props.BoolProperty(default=False)
    deform_bones_only: bpy.props.BoolProperty(default=True)
    triangulate: bpy.props.BoolProperty(default=False)
    use_object_instantiation: bpy.props.BoolProperty(default=False)
    use_blender_profile: bpy.props.BoolProperty(default=False)
    sort_by_name: bpy.props.BoolProperty(default=True)
    open_sim: bpy.props.BoolProperty(default=True)
    export_object_transformation_type_selection: bpy.props.StringProperty(default='matrix')
    export_global_forward_selection: bpy.props.StringProperty(default='Y')
    export_global_up_selection: bpy.props.StringProperty(default='Z')
    apply_global_orientation: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        _write_oni_collada_141(
            context=context,
            filepath=self.filepath,
            apply_modifiers=self.apply_modifiers,
            selected=self.selected,
            include_children=self.include_children,
            include_armatures=self.include_armatures,
            deform_bones_only=self.deform_bones_only,
            triangulate=self.triangulate,
            sort_by_name=self.sort_by_name,
            open_sim=self.open_sim,
            global_forward=self.export_global_forward_selection,
            global_up=self.export_global_up_selection,
            apply_global_orientation=self.apply_global_orientation,
        )
        return {'FINISHED'}


class EXPORT_SCENE_OT_oni_obj(bpy.types.Operator):
    bl_idname = "export_scene.obj"
    bl_label = "Export OBJ (Onigiri B5 Compat)"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="")
    check_existing: bpy.props.BoolProperty(default=True)
    use_selection: bpy.props.BoolProperty(default=True)
    use_mesh_modifiers: bpy.props.BoolProperty(default=True)
    use_edges: bpy.props.BoolProperty(default=True)
    use_smooth_groups: bpy.props.BoolProperty(default=False)
    use_smooth_groups_bitflags: bpy.props.BoolProperty(default=False)
    use_normals: bpy.props.BoolProperty(default=True)
    use_uvs: bpy.props.BoolProperty(default=True)
    use_materials: bpy.props.BoolProperty(default=True)
    use_triangles: bpy.props.BoolProperty(default=False)
    use_nurbs: bpy.props.BoolProperty(default=False)
    use_vertex_groups: bpy.props.BoolProperty(default=False)
    use_blen_objects: bpy.props.BoolProperty(default=True)
    group_by_object: bpy.props.BoolProperty(default=False)
    group_by_material: bpy.props.BoolProperty(default=False)
    keep_vertex_order: bpy.props.BoolProperty(default=True)
    global_scale: bpy.props.FloatProperty(default=1.0)
    path_mode: bpy.props.StringProperty(default='AUTO')
    axis_forward: bpy.props.StringProperty(default='-Z')
    axis_up: bpy.props.StringProperty(default='Y')

    def execute(self, context):
        return bpy.ops.wm.obj_export(
            filepath=self.filepath,
            check_existing=self.check_existing,
            export_selected_objects=self.use_selection,
            apply_modifiers=self.use_mesh_modifiers,
            export_normals=self.use_normals,
            export_uv=self.use_uvs,
            export_materials=self.use_materials,
            export_triangulated_mesh=self.use_triangles,
            global_scale=self.global_scale,
        )


class IMPORT_SCENE_OT_oni_obj(bpy.types.Operator):
    bl_idname = "import_scene.obj"
    bl_label = "Import OBJ (Onigiri B5 Compat)"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="")
    use_edges: bpy.props.BoolProperty(default=True)
    use_smooth_groups: bpy.props.BoolProperty(default=True)
    use_split_objects: bpy.props.BoolProperty(default=True)
    use_split_groups: bpy.props.BoolProperty(default=False)
    use_groups_as_vgroups: bpy.props.BoolProperty(default=False)
    use_image_search: bpy.props.BoolProperty(default=False)
    split_mode: bpy.props.StringProperty(default='OFF')
    axis_forward: bpy.props.StringProperty(default='-Z')
    axis_up: bpy.props.StringProperty(default='Y')

    def execute(self, context):
        return bpy.ops.wm.obj_import(filepath=self.filepath)


class MESH_OT_oni_loop_multi_select(bpy.types.Operator):
    bl_idname = "mesh.loop_multi_select"
    bl_label = "Loop Multi Select (Onigiri B5 Compat)"
    ring: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if hasattr(bpy.ops.mesh, "loop_select"):
            return bpy.ops.mesh.loop_select(ring=self.ring)
        return {'FINISHED'}


_ONI_EXTRA_OPS = (
    WM_OT_oni_collada_export,
    EXPORT_SCENE_OT_oni_obj,
    IMPORT_SCENE_OT_oni_obj,
    MESH_OT_oni_loop_multi_select,
)

def register_b5_extra_ops():
    for cls in _ONI_EXTRA_OPS:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass

register_b5_extra_ops()
