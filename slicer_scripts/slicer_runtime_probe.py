import pathlib

import slicer


def main():
    output_path = pathlib.Path(r"C:\entv1\slicer_runtime_probe.json")
    plugin_names = []
    dicom_plugins = getattr(slicer.modules, "dicomPlugins", None)
    if dicom_plugins:
        try:
            plugin_names = sorted(list(dicom_plugins.keys()))
        except Exception:
            plugin_names = []

    extensions_path = None
    try:
        extensions_manager = slicer.app.extensionsManagerModel()
        if extensions_manager:
            extensions_path = extensions_manager.extensionsInstallPath
    except Exception:
        extensions_path = None

    payload = {
        "dicomrtimportexport": hasattr(slicer.modules, "dicomrtimportexport"),
        "beams": hasattr(slicer.modules, "beams"),
        "dicomPlugins": plugin_names,
        "extensionsPath": extensions_path,
        "slicerVersion": slicer.app.applicationVersion,
        "revision": slicer.app.repositoryRevision,
    }
    output_path.write_text(__import__("json").dumps(payload, indent=2), encoding="utf-8")
    slicer.util.exit()


if __name__ == "__main__":
    main()
