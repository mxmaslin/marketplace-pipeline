from marketplace_pipeline.interfaces.api.app import app, create_app


def run() -> None:
    import uvicorn

    uvicorn.run(
        "marketplace_pipeline.interfaces.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


__all__ = ["app", "create_app", "run"]

if __name__ == "__main__":
    run()
