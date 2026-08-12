"""Start the GitPilot server:  python run.py  ->  http://localhost:8000/docs"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("gitpilot.main:app", host="0.0.0.0", port=8000, reload=True)
