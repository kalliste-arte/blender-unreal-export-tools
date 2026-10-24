# Unreal Export Tools

A small Blender add-on that checks your meshes for common Unreal Engine import problems, fixes the easy ones, and batch-exports clean FBX files.

## Features

- **Asset checker:** flags spaces and non-ASCII characters in names, `.001` duplicate suffixes, missing prefix (default `SM_`), unapplied or negative scale, missing UV maps, missing or empty materials, empty meshes and n-gons. Click an issue to select the object.
- **Quick fixes:** *Fix Names* (spaces to underscores, strips `.001`, adds the prefix) and *Apply Rotation & Scale*.
- **Batch export:** one FBX per selected object, or one per collection, with Unreal-friendly settings (face smoothing, no leaf bones, no animation baking). Optionally centers each object at the origin.
- **Safe exporting:** can refuse to export while checks still report errors.

## Install

1. Download `unreal_export_tools.py`.
2. In Blender: **Edit > Preferences > Add-ons > Install from Disk** (in some versions the small arrow menu in the top right), pick the file.
3. Enable **Unreal Export Tools**.
4. Open the 3D viewport sidebar (**N**) and use the **Unreal** tab.

## Usage

1. Select the meshes you want to check or export (with nothing selected, the checker looks at every mesh in the scene).
2. Press **Run Checks** and work through the list. **Fix Names** and **Apply Rotation & Scale** handle the common ones.
3. Choose an export folder (relative `//export/` needs a saved .blend), pick *Each Object* or *Each Collection*, and press **Batch Export FBX**.

## Notes

- Tested for Blender 3.6 and newer. Uses only the built-in FBX exporter, no extra dependencies.
- Objects that share mesh data can't have scale applied; they are listed as skipped.
- Checks run on mesh objects only. Armatures are exported with their meshes but aren't checked yet.

## License

MIT
