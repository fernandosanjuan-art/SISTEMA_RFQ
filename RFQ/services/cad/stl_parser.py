def analyze_stl(file_path):
    try:
        import trimesh

        mesh = trimesh.load(file_path)

        volume_cm3 = mesh.volume / 1000

        return {
            "ok": True,
            "volume_cm3": round(volume_cm3, 2),
            "bodies": 1
        }

    except Exception as e:
        return {
            "ok": False,
            "volume_cm3": None,
            "error": str(e)
        }