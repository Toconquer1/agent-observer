"""
核心包装模块，用于通过代理管理 agent 执行
"""
import os
import sys
import shutil
import subprocess
import signal
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class AgentWrapper:
    """通过 mitmproxy 观测来执行 agent 命令的包装器"""

    def __init__(self, output_dir: str = ".agentob", proxy_port: int = 8080, auto_analysis: bool = True):
        self.output_dir = Path(output_dir).resolve()
        self.proxy_port = proxy_port
        self.auto_analysis = auto_analysis
        self.mitm_process: Optional[subprocess.Popen] = None

        # 生成会话 ID：时间戳（分钟级）+ 随机ID
        # 格式：YYYYMMDD_HHMM_<8位随机ID>
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        random_id = uuid.uuid4().hex[:8]
        self.session_id = f"{timestamp}_{random_id}"
        self.session_dir = self.output_dir / self.session_id
        self.mitm_flow_file = self.session_dir / "flows.mitm"

    def _ensure_mitmproxy_installed(self) -> bool:
        """检查 mitmproxy 是否已安装，可用则返回 True"""
        mitmdump_path = shutil.which("mitmdump")
        if mitmdump_path:
            print(f"[agentob] Found mitmproxy at: {mitmdump_path}")
            return True

        print("[agentob] 未找到 mitmproxy，尝试通过 pip 安装...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "mitmproxy"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("[agentob] mitmproxy 安装成功")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[agentob] mitmproxy 安装失败: {e}")
            return False

    def _start_mitmproxy(self) -> bool:
        """在后台启动 mitmproxy"""
        if not self._ensure_mitmproxy_installed():
            return False

        # 确保会话目录存在
        self.session_dir.mkdir(parents=True, exist_ok=True)

        mitmdump_path = shutil.which("mitmdump")
        if not mitmdump_path:
            print("[agentob] 错误：安装后未找到 mitmdump")
            return False

        # 在后台启动 mitmdump
        cmd = [
            mitmdump_path,
            "-p", str(self.proxy_port),
            "-w", str(self.mitm_flow_file)
        ]

        try:
            # 在 Windows 上，使用 CREATE_NEW_PROCESS_GROUP 以便正确清理
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

            # 等待代理启动
            time.sleep(2)

            # 检查进程是否仍在运行
            if self.mitm_process.poll() is not None:
                print("[agentob] 错误：mitmproxy 启动失败")
                return False

            print(f"[agentob] mitmproxy 已在端口 {self.proxy_port} 启动")
            return True

        except Exception as e:
            print(f"[agentob] 启动 mitmproxy 失败: {e}")
            return False

    def _stop_mitmproxy(self):
        """停止 mitmproxy 进程"""
        if self.mitm_process is None:
            return

        try:
            if sys.platform == "win32":
                # 在 Windows 上，发送 CTRL_BREAK_EVENT
                self.mitm_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # 在 Unix 上，向进程组发送 SIGTERM
                os.killpg(os.getpgid(self.mitm_process.pid), signal.SIGTERM)

            # 等待进程终止
            try:
                self.mitm_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 超时则强制终止
                self.mitm_process.kill()
                self.mitm_process.wait()

            print("[agentob] mitmproxy 已停止")

        except Exception as e:
            print(f"[agentob] 停止 mitmproxy 时出错: {e}")

    def _build_env(self) -> dict:
        """构建包含代理设置的环境变量"""
        env = os.environ.copy()

        proxy_url = f"http://127.0.0.1:{self.proxy_port}"

        # 获取 mitmproxy 证书路径
        home = Path.home()
        mitm_cert = home / ".mitmproxy" / "mitmproxy-ca-cert.pem"

        env.update({
            "HTTP_PROXY": proxy_url,
            "HTTPS_PROXY": proxy_url,
        })

        # 对于 Node.js 应用（如 Claude Code）
        # 使用正确的证书而不是禁用验证
        if mitm_cert.exists():
            env["NODE_EXTRA_CA_CERTS"] = str(mitm_cert)
        else:
            # 回退方案：找不到证书则禁用验证
            env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
            print("[agentob] 警告：未找到 mitmproxy 证书，已禁用 TLS 验证")

        # 对于 Python 应用（如 langchain）
        if mitm_cert.exists():
            env.update({
                "REQUESTS_CA_BUNDLE": str(mitm_cert),
                "SSL_CERT_FILE": str(mitm_cert),
            })

        return env

    def _resolve_command(self, cmd: List[str]) -> List[str]:
        """将命令可执行文件解析为完整路径"""
        if not cmd:
            raise ValueError("未指定命令")

        executable = cmd[0]
        args = cmd[1:]

        resolved = shutil.which(executable)
        if not resolved:
            raise FileNotFoundError(f"Command not found: {executable}")

        return [resolved, *args]

    def _run_target_command(self, target_cmd: List[str]) -> int:
        """使用代理环境运行目标 agent 命令"""
        try:
            resolved_cmd = self._resolve_command(target_cmd)
        except Exception as e:
            print(f"[agentob] 错误: {e}")
            return 127

        env = self._build_env()

        print("=" * 60)
        print("[agentob] 正在启动 agent 应用")
        print(f"[agentob] 会话 ID: {self.session_id}")
        print(f"[agentob] 原始命令: {' '.join(target_cmd)}")
        print(f"[agentob] 解析后命令: {' '.join(resolved_cmd)}")
        print("[agentob] 已注入的环境变量:")
        print(f"[agentob]   HTTP_PROXY={env.get('HTTP_PROXY')}")
        print(f"[agentob]   HTTPS_PROXY={env.get('HTTPS_PROXY')}")
        print(f"[agentob]   NODE_TLS_REJECT_UNAUTHORIZED={env.get('NODE_TLS_REJECT_UNAUTHORIZED')}")
        print()
        print("[agentob] 正在进入目标应用的原生 CLI")
        print("[agentob] 退出后将执行分析")
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
            print("[agentob] 收到 Ctrl+C，正在退出...")
            return 130

        return return_code

    def _analyze_flows(self):
        """分析捕获的流量"""
        if not self.mitm_flow_file.exists():
            print("[agentob] 警告：未找到流量文件，跳过分析")
            return

        print()
        print("=" * 60)
        print("[agentob] 开始流量分析...")
        print("=" * 60)

        try:
            from .decoder import MitmDecoder
            from .simplify import RequestSimplifier
            from .parser import CallTraceParser

            raw_dir = self.session_dir / "raw_requests"
            filtered_dir = self.session_dir / "filtered_requests"
            analyzed_dir = self.session_dir / "analyzed"

            # 1. 解码 mitm 文件 → raw_requests/
            decoder = MitmDecoder(str(self.mitm_flow_file), str(raw_dir))
            decoder.decode()

            # 2. 将原始请求复制到 filtered_requests/ 并过滤
            shutil.copytree(raw_dir, filtered_dir)
            self._filter_relevant_requests(filtered_dir)

            # 3. 简化请求（在 filtered_requests/ 上进行）
            simplifier = RequestSimplifier(str(filtered_dir), str(analyzed_dir))
            simplifier.simplify()

            # 4. 解析调用轨迹
            parser = CallTraceParser(str(filtered_dir), str(analyzed_dir))
            parser.parse()

            # 5. 基于 LLM 的分析（如果 API 密钥可用）
            if os.getenv("AGOB_API_KEY"):
                try:
                    print()
                    print("[agentob] 开始 LLM 分析...")
                    from .analyzer import AgentAnalyzer
                    analyzer = AgentAnalyzer(str(analyzed_dir))
                    analyzer.analyze()
                    print("[agentob] LLM 分析完成！")
                except Exception as e:
                    print(f"[agentob] LLM 分析失败: {e}")
                    print("[agentob] 继续进行无 LLM 的分析...")
            else:
                print()
                print("[agentob] 跳过 LLM 分析（未设置 AGOB_API_KEY）")
                print("[agentob] 要启用 LLM 分析，请在 .env 文件中设置 AGOB_API_KEY")

            # 生成可视化
            try:
                print()
                print("[agentob] 正在生成可视化...")
                from .visualizer import AgentVisualizer
                visualizer = AgentVisualizer(str(analyzed_dir))
                html_path = visualizer.generate()
                print(f"[agentob] 可视化已保存: {html_path}")
            except Exception as e:
                print(f"[agentob] 可视化生成失败: {e}")
                import traceback
                traceback.print_exc()

            print()
            print("=" * 60)
            print("[agentob] 分析完成！")
            print(f"[agentob] 会话 ID: {self.session_id}")
            print(f"[agentob] 结果保存在: {self.session_dir}")
            print("=" * 60)

        except Exception as e:
            print(f"[agentob] 分析过程中出错: {e}")
            import traceback
            traceback.print_exc()

    def _filter_relevant_requests(self, decoded_dir: Path):
        """过滤解码后的请求，仅保留 LLM API 相关流量"""
        import json

        total_count = 0
        kept_count = 0

        # 仅遍历请求文件
        for req_file in decoded_dir.glob("*_request_*.json"):
            total_count += 1
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                url = data.get('url', '')

                # 检查是否为 LLM API 请求（兼容 Anthropic 格式）
                # 匹配: /v1/messages, /v1/chat/completions 等
                is_llm = '/v1/messages' in url or '/v1/chat/completions' in url

                # 如果是 LLM 请求则保留
                if is_llm:
                    kept_count += 1
                else:
                    # 从文件名提取索引（如 "1_request_20260402_155849.json" -> "1"）
                    req_basename = req_file.stem  # 如 "1_request_20260402_155849"
                    index = req_basename.split('_')[0]

                    # 查找并删除对应的响应文件
                    for res_file in decoded_dir.glob(f"{index}_response_*.json"):
                        res_file.unlink()

                    # 删除请求文件
                    req_file.unlink()

            except Exception as e:
                print(f"[agentob] 警告：过滤 {req_file.name} 失败: {e}")

        removed_count = total_count - kept_count
        print(f"[agentob] 保留了 {kept_count}/{total_count} 个 LLM 请求对，移除了 {removed_count} 个")

    def run(self, target_command: List[str]) -> int:
        """主执行流程（前台模式）"""
        # 启动 mitmproxy
        if not self._start_mitmproxy():
            print("[agentob] 代理启动失败，中止")
            return 1

        try:
            # 运行目标命令
            return_code = self._run_target_command(target_command)

            print()
            print("=" * 60)
            print("[agentob] 目标应用已退出")
            print(f"[agentob] 退出码: {return_code}")
            print("=" * 60)

            # 如果启用，进行流量分析
            if self.auto_analysis:
                self._analyze_flows()

            return return_code

        finally:
            # 始终停止 mitmproxy
            self._stop_mitmproxy()

    def attach(self, duration: Optional[int] = None) -> int:
        """
        Attach 模式：启动代理并等待，用于观测已经在运行的后台 agent。

        使用场景：
        1. 先运行 agentob attach（或指定时长如 agentob attach 300）
        2. 设置环境变量指向代理（HTTP_PROXY=http://127.0.0.1:8080）
        3. 启动你的后台 agent（如 OpenClaw）
        4. agent 运行期间，所有流量会被捕获
        5. 按 Ctrl+C 或等待时长结束后，停止捕获并分析

        Args:
            duration: 可选的捕获时长（秒），None 表示无限期直到 Ctrl+C

        Returns:
            退出码
        """
        # 启动 mitmproxy
        if not self._start_mitmproxy():
            print("[agentob] 代理启动失败，中止")
            return 1

        try:
            print()
            print("=" * 60)
            print("[agentob] Attach 模式已启动")
            print(f"[agentob] 会话 ID: {self.session_id}")
            print(f"[agentob] 代理地址: http://127.0.0.1:{self.proxy_port}")
            print()
            print("[agentob] 请在你的 agent 应用中设置以下环境变量：")
            print(f"[agentob]   export HTTP_PROXY=http://127.0.0.1:{self.proxy_port}")
            print(f"[agentob]   export HTTPS_PROXY=http://127.0.0.1:{self.proxy_port}")
            print()

            # 获取证书路径
            home = Path.home()
            mitm_cert = home / ".mitmproxy" / "mitmproxy-ca-cert.pem"
            if mitm_cert.exists():
                print("[agentob] 对于 Node.js 应用，还需要：")
                print(f"[agentob]   export NODE_EXTRA_CA_CERTS={mitm_cert}")
                print()
                print("[agentob] 对于 Python 应用，还需要：")
                print(f"[agentob]   export REQUESTS_CA_BUNDLE={mitm_cert}")
                print(f"[agentob]   export SSL_CERT_FILE={mitm_cert}")
                print()
            else:
                print("[agentob] 警告：未找到 mitmproxy 证书")
                print("[agentob] 对于 Node.js 应用，可能需要：")
                print("[agentob]   export NODE_TLS_REJECT_UNAUTHORIZED=0")
                print()

            if duration:
                print(f"[agentob] 将捕获 {duration} 秒，或按 Ctrl+C 提前结束")
            else:
                print("[agentob] 按 Ctrl+C 停止捕获")

            print("=" * 60)
            print()

            # 等待指定时长或 Ctrl+C
            if duration:
                try:
                    time.sleep(duration)
                    print()
                    print(f"[agentob] 捕获时长 {duration} 秒已到，正在停止...")
                except KeyboardInterrupt:
                    print()
                    print("[agentob] 收到 Ctrl+C，正在停止...")
            else:
                try:
                    # 无限等待直到 Ctrl+C
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print()
                    print("[agentob] 收到 Ctrl+C，正在停止...")

            # 如果启用，进行流量分析
            if self.auto_analysis:
                self._analyze_flows()

            return 0

        finally:
            # 始终停止 mitmproxy
            self._stop_mitmproxy()
