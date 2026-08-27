import subprocess, time, socket, os
NO_WINDOW = 0x08000000
env = os.environ.copy()
env["HF_ENDPOINT"] = "https://hf-mirror.com"
p = subprocess.Popen([os.path.expanduser(r"~\.local\bin\headroom.exe"), "proxy", "--port", "8787"],
                     creationflags=NO_WINDOW, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
print("spawned pid", p.pid)
alive = False
for _ in range(30):
    try:
        with socket.create_connection(("127.0.0.1", 8787), timeout=1):
            alive = True
            break
    except Exception:
        time.sleep(0.5)
print("proxy alive:", alive)
# parent exits; proxy must survive
