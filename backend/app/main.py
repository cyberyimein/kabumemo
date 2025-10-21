from pathlib import Path
import os

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Kabumemo API", version="0.1.0")
    app.include_router(api_router)

    env_dist = os.environ.get("KABUMEMO_DIST_DIR")
    if env_dist:
        dist_dir = Path(env_dist).expanduser().resolve()
    else:
        dist_dir = Path.cwd().parent / "frontend" / "dist"
        if not dist_dir.exists():
            dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist_dir.exists():
        print(f"[Startup] Serving frontend from {dist_dir}")

        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/")
        async def serve_root() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

            candidate = dist_dir / full_path
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)

            return FileResponse(dist_dir / "index.html")
    else:
        print(f"[Startup] Frontend dist directory not found: {dist_dir}")
    return app


app = create_app()
