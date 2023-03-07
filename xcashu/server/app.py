from fastapi import FastAPI, HTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from xcashu.server.ledger import startup_cashu_mint
from xcashu.server.router import router
from xcashu.server.ledger import csat_router

from xcashu.server.middleware import EcashHeaderMiddleware


def create_app() -> FastAPI:
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        ),
        Middleware(EcashHeaderMiddleware),
    ]

    app = FastAPI(
        title="Cashu csat",
        description="API access with Cashu",
        license_info={
            "name": "MIT License",
            "url": "https://raw.githubusercontent.com/cashubtc/cashu/main/LICENSE",
        },
        middleware=middleware,
    )
    return app


app = create_app()

app.include_router(router=router)
app.include_router(router=csat_router)


@app.on_event("startup")
async def startup_mint():
    await startup_cashu_mint()
