import uvicorn
from src import create_app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, port=5000)
