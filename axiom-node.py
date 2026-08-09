import argparse
import sys
import uvicorn

ASCII_ART = r"""
    █████╗ ██╗  ██╗██╗ ██████╗ ███╗   ███╗
   ██╔══██╗╚██╗██╔╝██║██╔═══██╗████╗ ████║
   ███████║ ╚███╔╝ ██║██║   ██║██╔████╔██║
   ██╔══██║ ██╔██╗ ██║██║   ██║██║╚██╔╝██║
   ██║  ██║██╔╝ ██╗██║╚██████╔╝██║ ╚═╝ ██║
   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝     ╚═╝
             --- N O D E ---
"""

def main():
    parser = argparse.ArgumentParser(description="AXIOM Headless Swarm Node")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    print(ASCII_ART)
    print(f"[*] Headless Swarm Worker Online - Listening on port {args.port}")
    print("[*] Starting Uvicorn server...")
    
    uvicorn.run("axiom.server.node_api:app", host="0.0.0.0", port=args.port, ws="auto")

if __name__ == "__main__":
    main()
