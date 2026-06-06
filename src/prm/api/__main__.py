"""Run the REST API with: python -m prm.api"""

import uvicorn

from prm.api.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "prm.api.app:create_app",
        host=settings.api_host,
        port=settings.api_port,
        factory=True,
        reload=False,
    )


if __name__ == "__main__":
    main()
