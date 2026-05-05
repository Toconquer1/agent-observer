"""
Core wrapper module for managing agent execution with proxy
"""
import os
import sys
import shutil
import subprocess
import signal
import time
from pathlib import Path
from typing import List, Optional


class AgentWrapper:
    """Wrapper for executing agent commands with mitmproxy observation"""

    def __init__(self, output_dir: str = ".agentob", proxy_port: int = 8080, auto_analysis: bool = True):
        self.output_dir = Path(output_dir).resolve()
        self.proxy_port = proxy_port
        self.auto_analysis = auto_analysis
        self.mitm_process: Optional[subprocess.Popen] = None
        self.mitm_flow_file = self.output_dir / "flows.mitm"

    def _ensure_mitmproxy_installed(self) -> bool:
        """Check if mitmproxy is installed, return True if available"""
        mitmdump_path = shutil.which("mitmdump")
        if mitmdump_path:
            print(f"[agentob] Found mitmproxy at: {mitmdump_path}")
            return True

        print("[agentob] mitmproxy not found, attempting to install via pip...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "mitmproxy"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("[agentob] mitmproxy installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[agentob] Failed to install mitmproxy: {e}")
            return False

    def _start_mitmproxy(self) -> bool:
        """Start mitmproxy in background"""
        if not self._ensure_mitmproxy_installed():
            return False

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Remove old flow file if exists
        if self.mitm_flow_file.exists():
            self.mitm_flow_file.unlink()

        mitmdump_path = shutil.which("mitmdump")
        if not mitmdump_path:
            print("[agentob] Error: mitmdump not found after installation")
            return False

        # Start mitmdump in background
        cmd = [
            mitmdump_path,
            "-p", str(self.proxy_port),
            "-w", str(self.mitm_flow_file),
            "--set", "stream_large_bodies=1",  # Stream large bodies to avoid memory issues
        ]

        try:
            # On Windows, use CREATE_NEW_PROCESS_GROUP to allow proper cleanup
            if sys.platform == "win32":
                self.mitm_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self.mitm_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )

            # Wait a bit for proxy to start
            time.sleep(2)

            # Check if process is still running
            if self.mitm_process.poll() is not None:
                print("[agentob] Error: mitmproxy failed to start")
                return False

            print(f"[agentob] mitmproxy started on port {self.proxy_port}")
            return True

        except Exception as e:
            print(f"[agentob] Failed to start mitmproxy: {e}")
            return False

    def _stop_mitmproxy(self):
        """Stop mitmproxy process"""
        if self.mitm_process is None:
            return

        try:
            if sys.platform == "win32":
                # On Windows, send CTRL_BREAK_EVENT
                self.mitm_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # On Unix, send SIGTERM to process group
                os.killpg(os.getpgid(self.mitm_process.pid), signal.SIGTERM)

            # Wait for process to terminate
            try:
                self.mitm_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't stop
                self.mitm_process.kill()
                self.mitm_process.wait()

            print("[agentob] mitmproxy stopped")

        except Exception as e:
            print(f"[agentob] Error stopping mitmproxy: {e}")

    def _build_env(self) -> dict:
        """Build environment variables with proxy settings"""
        env = os.environ.copy()

        proxy_url = f"http://127.0.0.1:{self.proxy_port}"

        # Get mitmproxy certificate path
        home = Path.home()
        mitm_cert = home / ".mitmproxy" / "mitmproxy-ca-cert.pem"

        env.update({
            "HTTP_PROXY": proxy_url,
            "HTTPS_PROXY": proxy_url,
            # For Node.js applications (like Claude Code)
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        })

        # For Python applications (like langchain)
        if mitm_cert.exists():
            env.update({
                "REQUESTS_CA_BUNDLE": str(mitm_cert),
                "SSL_CERT_FILE": str(mitm_cert),
            })

        return env

    def _resolve_command(self, cmd: List[str]) -> List[str]:
        """Resolve command executable to full path"""
        if not cmd:
            raise ValueError("No command specified")

        executable = cmd[0]
        args = cmd[1:]

        resolved = shutil.which(executable)
        if not resolved:
            raise FileNotFoundError(f"Command not found: {executable}")

        return [resolved, *args]

    def _run_target_command(self, target_cmd: List[str]) -> int:
        """Run the target agent command with proxy environment"""
        try:
            resolved_cmd = self._resolve_command(target_cmd)
        except Exception as e:
            print(f"[agentob] Error: {e}")
            return 127

        env = self._build_env()

        print("=" * 60)
        print("[agentob] Starting agent application")
        print(f"[agentob] Original command: {' '.join(target_cmd)}")
        print(f"[agentob] Resolved command: {' '.join(resolved_cmd)}")
        print("[agentob] Injected environment variables:")
        print(f"[agentob]   HTTP_PROXY={env.get('HTTP_PROXY')}")
        print(f"[agentob]   HTTPS_PROXY={env.get('HTTPS_PROXY')}")
        print(f"[agentob]   NODE_TLS_REJECT_UNAUTHORIZED={env.get('NODE_TLS_REJECT_UNAUTHORIZED')}")
        print()
        print("[agentob] Entering target application's native CLI")
        print("[agentob] After exiting, analysis will be performed")
        print("=" * 60)
        print()

        try:
            proc = subprocess.Popen(
                resolved_cmd,
                env=env,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            return_code = proc.wait()

        except KeyboardInterrupt:
            print()
            print("[agentob] Received Ctrl+C, exiting...")
            return 130

        return return_code

    def _analyze_flows(self):
        """Analyze captured flows"""
        if not self.mitm_flow_file.exists():
            print("[agentob] Warning: No flow file found, skipping analysis")
            return

        print()
        print("=" * 60)
        print("[agentob] Starting flow analysis...")
        print("=" * 60)

        try:
            from .decoder import MitmDecoder
            from .analyzer import RequestAnalyzer

            # Decode mitm file
            decoded_dir = self.output_dir / "decoded_flows"
            decoder = MitmDecoder(str(self.mitm_flow_file), str(decoded_dir))
            decoder.decode()

            # Analyze requests
            analyzer = RequestAnalyzer(str(decoded_dir))
            analyzer.analyze()

            print()
            print("=" * 60)
            print("[agentob] Analysis completed!")
            print(f"[agentob] Results saved in: {self.output_dir}")
            print("=" * 60)

        except Exception as e:
            print(f"[agentob] Error during analysis: {e}")
            import traceback
            traceback.print_exc()

    def run(self, target_command: List[str]) -> int:
        """Main execution flow"""
        # Start mitmproxy
        if not self._start_mitmproxy():
            print("[agentob] Failed to start proxy, aborting")
            return 1

        try:
            # Run target command
            return_code = self._run_target_command(target_command)

            print()
            print("=" * 60)
            print("[agentob] Target application exited")
            print(f"[agentob] Exit code: {return_code}")
            print("=" * 60)

            # Analyze flows if enabled
            if self.auto_analysis:
                self._analyze_flows()

            return return_code

        finally:
            # Always stop mitmproxy
            self._stop_mitmproxy()
