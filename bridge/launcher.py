#!/usr/bin/env python3
"""
Dynamo MCP 自動啟動器
負責啟動 Python server.py，作為 Node.js Bridge 的後端
"""

import subprocess
import sys
import time
import os
import socket
import signal
from pathlib import Path

class ServerLauncher:
    def __init__(self):
        self.server_process = None
        self.project_root = Path(__file__).parent.parent
        self.server_py = self.project_root / "bridge" / "python" / "server.py"
    
    def is_port_available(self, port=65296):
        """檢查埠口是否已被佔用"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result != 0  # 0 表示已被佔用，非 0 表示可用
    
    def start_server(self):
        """啟動 Python server"""
        print("[Launcher] Checking server.py status...", file=sys.stderr)
        
        # 檢查 server.py 是否存在
        if not self.server_py.exists():
            print(f"[ERROR] 找不到 server.py: {self.server_py}", file=sys.stderr)
            sys.exit(1)
        
        # 檢查埠口
        if not self.is_port_available(65296):
            print("[OK] Port 65296 already in use, server.py is running", file=sys.stderr)
            return True
        
        print("[Launcher] Port 65296 available, starting server.py...", file=sys.stderr)
        
        try:
            # 啟動 Python server（將輸出重定向到 stderr，避免阻塞）
            self.server_process = subprocess.Popen(
                [sys.executable, str(self.server_py)],
                stdout=sys.stderr,
                stderr=sys.stderr,
                cwd=str(self.project_root)
            )
            
            print(f"[Launcher] Python server started (PID: {self.server_process.pid})", file=sys.stderr)
            
            # 等待 server 啟動
            time.sleep(2)
            
            # 驗證 server 是否成功啟動
            if self.server_process.poll() is None:
                print("[Launcher] server.py is running", file=sys.stderr)
                return True
            else:
                print("[ERROR] server.py exited immediately", file=sys.stderr)
                return False
        
        except Exception as e:
            print(f"[ERROR] Failed to start server.py: {e}", file=sys.stderr)
            return False
    
    def keep_alive(self):
        """保持 server 執行"""
        try:
            if self.server_process:
                self.server_process.wait()
        except KeyboardInterrupt:
            print("\n[Launcher] Stopping server...", file=sys.stderr)
            if self.server_process:
                self.server_process.terminate()
                self.server_process.wait()

if __name__ == "__main__":
    launcher = ServerLauncher()
    
    if launcher.start_server():
        print("[Launcher] server.py 已準備就緒，Node.js Bridge 可以連線")
        launcher.keep_alive()
    else:
        sys.exit(1)
