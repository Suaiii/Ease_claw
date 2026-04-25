import argparse
import socket
import threading


def pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        for sock, how in ((dst, socket.SHUT_WR), (src, socket.SHUT_RD)):
            try:
                sock.shutdown(how)
            except Exception:
                pass


def handle(client: socket.socket, remote_host: str, remote_port: int) -> None:
    try:
        upstream = socket.create_connection((remote_host, remote_port), timeout=10)
    except Exception:
        client.close()
        return
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Loopback TCP relay for a remote OpenClaw gateway")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=31879)
    parser.add_argument("--remote-host", required=True)
    parser.add_argument("--remote-port", type=int, required=True)
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.listen_host, args.listen_port))
    server.listen(20)
    print(
        f"relay listening on {args.listen_host}:{args.listen_port} -> {args.remote_host}:{args.remote_port}",
        flush=True,
    )
    while True:
        client, _ = server.accept()
        threading.Thread(
            target=handle,
            args=(client, args.remote_host, args.remote_port),
            daemon=True,
        ).start()


if __name__ == "__main__":
    main()
