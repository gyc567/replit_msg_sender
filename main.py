import subprocess
import sys
import time
import os

# 📝 你的脚本列表
# botsever.py 是 Flask 服务器，已修改为线程模式运行
SCRIPTS = [
    "arkm.py",  # Arkham 监控
    "bianjk.py",  # 币安监控
    # "zixun.py",       # Mlion 新闻 (临时注释掉)
    "botsever.py",  # Webhook 服务器
]

# 存储进程对象
running_processes = {}


def start_script(script_name):
    """启动单个脚本，带详细日志"""
    try:
        print(f"👉 [准备启动] {script_name} ...", flush=True)

        # botsever.py 特殊处理：在线程中运行，不创建子进程
        if script_name == "botsever.py":
            try:
                # 动态导入并启动
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import botsever

                port = botsever.run_server()
                if port:
                    running_processes[script_name] = {"type": "thread", "port": port}
                    print(f"✅ [启动成功] {script_name} (端口: {port})", flush=True)
                    return True
                else:
                    print(f"❌ [启动失败] {script_name} 无法获取端口", flush=True)
                    return False
            except Exception as e:
                print(f"❌ [启动报错] {script_name}: {str(e)}", flush=True)
                return False
        else:
            # 其他脚本用 Popen 启动
            process = subprocess.Popen(
                [sys.executable, "-u", script_name],
                stdout=sys.stdout,
                stderr=sys.stderr,
                bufsize=0,
            )

            running_processes[script_name] = {"type": "process", "obj": process}
            print(f"✅ [启动成功] {script_name} (PID: {process.pid})", flush=True)
            return True
    except Exception as e:
        print(f"❌ [启动报错] {script_name} 无法启动: {str(e)}", flush=True)
        return False


def stop_all():
    """停止所有进程"""
    print("\n🛑 正在关闭所有监控进程...", flush=True)
    for name, info in running_processes.items():
        if info.get("type") == "process":
            process = info.get("obj")
            if process and process.poll() is None:
                print(f"   - 正在终止 {name} (PID: {process.pid})...")
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
        # 线程类型的无法强制停止，只能靠程序自然退出
    print("👋 所有进程已清理完毕。")


def main():
    # 切换到当前目录，防止路径错误
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    print(f"🚀 主程序启动 | 工作目录: {current_dir}")
    print(f"📋 计划运行列表: {SCRIPTS}\n" + "=" * 40)

    # 1. 交错启动所有脚本（付费版资源充足，可以缩短间隔）
    for index, script in enumerate(SCRIPTS):
        print(f"\n--- 正在处理第 {index + 1}/{len(SCRIPTS)} 个任务 ---")
        start_script(script)

        if index < len(SCRIPTS) - 1:
            print(f"⏳ 等待 5 秒，让 {script} 初始化...", flush=True)
            time.sleep(5)

    print("\n" + "=" * 40)
    print("👀 所有脚本启动指令已发送，开始进入守护模式...")
    print("=" * 40 + "\n")

    # 2. 守护循环（只监控子进程，botsever是线程不监控）
    try:
        while True:
            time.sleep(10)  # 每10秒检查一次

            for script in SCRIPTS:
                info = running_processes.get(script)
                if not info:
                    continue

                # 只检查子进程类型的脚本
                if info.get("type") == "process":
                    process = info.get("obj")
                    return_code = process.poll()
                    if return_code is not None:
                        # 进程死了
                        print(
                            f"\n⚠️ [警告] {script} 已停止运行! (退出码: {return_code})"
                        )
                        print(f"🔄 正在尝试重启 {script} ...")
                        start_script(script)

    except KeyboardInterrupt:
        stop_all()


if __name__ == "__main__":
    main()
