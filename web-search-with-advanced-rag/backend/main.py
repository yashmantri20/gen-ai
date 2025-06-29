from server import app
import uvicorn
from dotenv import load_dotenv

load_dotenv()

def main():
    uvicorn.run(
        "server:app",             # <- safer than passing imported app directly
        host="0.0.0.0",
        port=8000,
        reload=False,             # SSE can break under reload mode
        log_level="info",
        proxy_headers=True,       # optional, good for deployments behind a proxy
    )

if __name__ == "__main__":
    main()
