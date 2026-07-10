def analyze_step(file_path):
    try:
        from cadquery import importers

        model = importers.importStep(file_path)

        solid = model.val()

        volume_cm3 = solid.Volume() / 1000

        return {
            "ok": True,
            "volume_cm3": round(volume_cm3, 2)
        }

    except Exception as e:
        return {
            "ok": False,
            "volume_cm3": None,
            "error": str(e)
        }