from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import upload

app = FastAPI(title="VL_Flow API", description="Bank Transaction Identification Service")

# CORS Configuration
origins = [
    "http://localhost:5173", # Vue Default Port
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(upload.router, prefix="/api", tags=["upload"])

@app.get("/")
async def root():
    return {"message": "Welcome to VL_Flow API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
