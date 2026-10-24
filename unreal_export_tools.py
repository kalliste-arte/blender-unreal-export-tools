bl_info = {
    "name": "Unreal Export Tools",
    "author": "Kall",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D Viewport > Sidebar (N) > Unreal",
    "description": "Asset checker, quick fixes and batch FBX export for Unreal Engine",
    "category": "Import-Export",
}

import os
import re

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       PointerProperty, StringProperty)
from bpy.types import Operator, Panel, PropertyGroup

DUP = re.compile(r"\.\d{3}$")


# ----------------------------------------------------------------- data
class UET_Issue(PropertyGroup):
    obj: StringProperty()
    msg: StringProperty()
    level: StringProperty()  # "ERROR" or "WARNING"


class UET_Settings(PropertyGroup):
    export_dir: StringProperty(name="Folder", subtype="DIR_PATH", default="//export/")
    mode: EnumProperty(
        name="Export",
        items=[("OBJECTS", "Each Object", "One FBX per selected mesh"),
               ("COLLECTIONS", "Each Collection", "One FBX per collection of selected meshes")],
        default="OBJECTS")
    prefix: StringProperty(name="Prefix", default="SM_",
                           description="Static mesh prefix expected by the checker and added by Fix Names")
    check_first: BoolProperty(name="Check before export", default=True)
    center: BoolProperty(name="Center at origin", default=True,
                         description="Export each object at 0,0,0 (Each Object mode only)")
    issues: CollectionProperty(type=UET_Issue)


# --------------------------------------------------------------- checks
def target_meshes(context):
    objs = [o for o in context.selected_objects if o.type == "MESH"]
    return objs or [o for o in context.scene.objects if o.type == "MESH"]


def check_object(o, prefix):
    out = []
    if " " in o.name:
        out.append(("WARNING", "Name contains spaces"))
    if DUP.search(o.name):
        out.append(("WARNING", "Duplicate suffix (.001)"))
    if not o.name.isascii():
        out.append(("ERROR", "Non-ASCII characters in name"))
    if prefix and not o.name.startswith(prefix):
        out.append(("WARNING", f"Missing '{prefix}' prefix"))
    if any(abs(s - 1.0) > 1e-4 for s in o.scale):
        out.append(("ERROR", "Scale not applied"))
    if any(s < 0 for s in o.scale):
        out.append(("ERROR", "Negative scale"))
    me = o.data
    if len(me.polygons) == 0:
        out.append(("ERROR", "Empty mesh"))
        return out
    if not me.uv_layers:
        out.append(("ERROR", "No UV map"))
    mats = [s.material for s in o.material_slots]
    if not any(mats):
        out.append(("ERROR", "No material"))
    elif not all(mats):
        out.append(("WARNING", "Empty material slot"))
    ngons = sum(1 for p in me.polygons if len(p.vertices) > 4)
    if ngons:
        out.append(("WARNING", f"{ngons} n-gon(s)"))
    return out


def run_checks(context):
    s = context.scene.uet
    s.issues.clear()
    objs = target_meshes(context)
    for o in objs:
        for level, msg in check_object(o, s.prefix):
            i = s.issues.add()
            i.obj, i.msg, i.level = o.name, msg, level
    errors = sum(1 for i in s.issues if i.level == "ERROR")
    return len(objs), errors, len(s.issues) - errors


def ensure_object_mode():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


# ------------------------------------------------------------ operators
class UET_OT_check(Operator):
    bl_idname = "uet.check"
    bl_label = "Run Checks"
    bl_description = "Check selected meshes (or every mesh if nothing is selected)"

    def execute(self, context):
        n, e, w = run_checks(context)
        self.report({"ERROR" if e else "INFO"}, f"{n} mesh(es): {e} error(s), {w} warning(s)")
        return {"FINISHED"}


class UET_OT_select(Operator):
    bl_idname = "uet.select"
    bl_label = "Select"
    name: StringProperty()

    def execute(self, context):
        o = bpy.data.objects.get(self.name)
        if o:
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            context.view_layer.objects.active = o
        return {"FINISHED"}


class UET_OT_fix_names(Operator):
    bl_idname = "uet.fix_names"
    bl_label = "Fix Names"
    bl_description = "Replace spaces, drop .001 suffixes and add the mesh prefix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        prefix = context.scene.uet.prefix
        count = 0
        for o in target_meshes(context):
            new = DUP.sub("", o.name).strip().replace(" ", "_")
            if prefix and not new.startswith(prefix):
                new = prefix + new
            if new != o.name:
                o.name = new
                count += 1
        run_checks(context)
        self.report({"INFO"}, f"Renamed {count} object(s)")
        return {"FINISHED"}


class UET_OT_apply(Operator):
    bl_idname = "uet.apply"
    bl_label = "Apply Rotation & Scale"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ensure_object_mode()
        skipped = []
        for o in target_meshes(context):
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            context.view_layer.objects.active = o
            try:
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            except RuntimeError:
                skipped.append(o.name)  # usually shared (multi-user) mesh data
        run_checks(context)
        if skipped:
            self.report({"WARNING"}, "Skipped (shared mesh data): " + ", ".join(skipped))
        return {"FINISHED"}


def export_fbx(context, objs, path, center):
    moved = {}
    if center:
        for o in objs:
            if o.parent is None:
                moved[o] = o.location.copy()
                o.location = (0, 0, 0)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    context.view_layer.objects.active = objs[0]
    try:
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True,
            object_types={"MESH", "ARMATURE"},
            apply_scale_options="FBX_SCALE_ALL",
            mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
    finally:
        for o, loc in moved.items():
            o.location = loc


class UET_OT_export(Operator):
    bl_idname = "uet.export"
    bl_label = "Batch Export FBX"
    bl_description = "Export selected meshes as Unreal-ready FBX files"

    def execute(self, context):
        s = context.scene.uet
        ensure_object_mode()
        folder = bpy.path.abspath(s.export_dir)
        if s.export_dir.startswith("//") and not bpy.data.filepath:
            self.report({"ERROR"}, "Save the .blend file first or choose an absolute folder")
            return {"CANCELLED"}
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        if not objs:
            self.report({"ERROR"}, "Select at least one mesh")
            return {"CANCELLED"}
        if s.check_first:
            _, errors, _ = run_checks(context)
            if errors:
                self.report({"ERROR"}, f"{errors} error(s) found - fix them or turn off 'Check before export'")
                return {"CANCELLED"}
        os.makedirs(folder, exist_ok=True)

        if s.mode == "OBJECTS":
            jobs = [(o.name, [o]) for o in objs]
        else:
            groups = {}
            for o in objs:
                groups.setdefault(o.users_collection[0].name, []).append(o)
            jobs = list(groups.items())

        for name, group in jobs:
            export_fbx(context, group, os.path.join(folder, name + ".fbx"),
                       s.center and s.mode == "OBJECTS")

        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        self.report({"INFO"}, f"Exported {len(jobs)} file(s) to {folder}")
        return {"FINISHED"}


# ---------------------------------------------------------------- panel
class UET_PT_panel(Panel):
    bl_label = "Unreal Export Tools"
    bl_idname = "UET_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Unreal"

    def draw(self, context):
        s = context.scene.uet
        col = self.layout.column(align=True)

        box = self.layout.box()
        box.label(text="Asset Checker", icon="CHECKMARK")
        box.prop(s, "prefix")
        row = box.row(align=True)
        row.operator("uet.check", icon="VIEWZOOM")
        row.operator("uet.fix_names", icon="SORTALPHA")
        box.operator("uet.apply", icon="ORIENTATION_GLOBAL")
        for i in list(s.issues)[:12]:
            r = box.row(align=True)
            r.alert = i.level == "ERROR"
            r.operator("uet.select", text=f"{i.obj}: {i.msg}",
                       icon="ERROR" if i.level == "ERROR" else "INFO").name = i.obj
        if len(s.issues) > 12:
            box.label(text=f"+ {len(s.issues) - 12} more...")

        box = self.layout.box()
        box.label(text="Batch Export", icon="EXPORT")
        box.prop(s, "export_dir")
        box.prop(s, "mode", text="")
        box.prop(s, "center")
        box.prop(s, "check_first")
        box.operator("uet.export", icon="EXPORT")


classes = (UET_Issue, UET_Settings, UET_OT_check, UET_OT_select, UET_OT_fix_names,
           UET_OT_apply, UET_OT_export, UET_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.uet = PointerProperty(type=UET_Settings)


def unregister():
    del bpy.types.Scene.uet
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
