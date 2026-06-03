#!/usr/bin/env python3
"""
发票识别压测脚本

用法：
  uv run python tests/stress_test_invoice.py \
    --url https://aisit.qdccb.cn:9900/vlagent/api \
    --token "Bearer eyJ..." \
    --file ./test.jpg \
    --concurrency 1 \
    --total 5
"""

import argparse
import asyncio
import ssl
import time
import statistics
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("需要 httpx: uv add --dev httpx")
    sys.exit(1)


def red(s):    return f"\033[91m{s}\033[0m"
def green(s):  return f"\033[92m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"


def make_ssl_context():
    """兼容旧式 SSL 重协商的 nginx"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT  # 允许旧式重协商
    return ctx


async def run_one(client, base_url, file_path, idx, poll, poll_interval):
    t0 = time.monotonic()
    result = {"idx": idx, "ok": False, "upload_ms": 0, "total_ms": 0,
              "status": "", "error": "", "file_id": None}

    try:
        with open(file_path, "rb") as f:
            fname = Path(file_path).name
            resp = await client.post(
                f"{base_url}/invoice_recognition/upload",
                files={"file": (fname, f)},
                timeout=120,
            )

        result["upload_ms"] = (time.monotonic() - t0) * 1000

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            result["total_ms"] = (time.monotonic() - t0) * 1000
            return result

        data = resp.json()
        file_id = data.get("file_id")
        if not file_id:
            result["error"] = f"无 file_id: {data}"
            result["total_ms"] = (time.monotonic() - t0) * 1000
            return result
        result["file_id"] = file_id

    except Exception as e:
        result["error"] = f"上传异常: {type(e).__name__}: {e}"
        result["total_ms"] = (time.monotonic() - t0) * 1000
        return result

    if not poll:
        result["ok"] = True
        result["status"] = "uploaded"
        result["total_ms"] = (time.monotonic() - t0) * 1000
        return result

    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)
        try:
            pr = await client.get(
                f"{base_url}/invoice_recognition/list/{file_id}", timeout=30)
            if pr.status_code != 200:
                continue
            d = pr.json()
            st = d.get("status", "")
            if st == "done":
                result["ok"] = True
                result["status"] = "done"
                result["total_ms"] = (time.monotonic() - t0) * 1000
                return result
            elif st == "failed":
                result["error"] = f"识别失败: {d.get('error_msg', '')[:200]}"
                result["status"] = "failed"
                result["total_ms"] = (time.monotonic() - t0) * 1000
                return result
        except Exception:
            continue

    result["error"] = "轮询超时 (300s)"
    result["status"] = "timeout"
    result["total_ms"] = (time.monotonic() - t0) * 1000
    return result


async def run_stress(base_url, token, file_path, concurrency, total, poll, poll_interval):
    sem = asyncio.Semaphore(concurrency)
    results = []
    done_count = 0
    lock = asyncio.Lock()
    headers = {"Authorization": token}

    print(bold(f"\n{'='*60}"))
    print(bold(f"  发票识别压测"))
    print(f"  URL:        {base_url}/invoice_recognition/...")
    print(f"  文件:       {file_path}")
    print(f"  并发:       {concurrency}")
    print(f"  总数:       {total}")
    print(f"  轮询结果:   {'是' if poll else '否'}")
    print(bold(f"{'='*60}\n"))

    ssl_ctx = make_ssl_context()
    async with httpx.AsyncClient(headers=headers, verify=ssl_ctx, timeout=120) as client:
        async def task(idx):
            nonlocal done_count
            async with sem:
                r = await run_one(client, base_url, file_path, idx, poll, poll_interval)
                async with lock:
                    results.append(r)
                    done_count += 1
                    mark = green("OK") if r["ok"] else red("FAIL")
                    fid = f"file_id={r['file_id']}" if r.get("file_id") else ""
                    print(f"  [{done_count}/{total}] {mark} #{idx:>3d}  "
                          f"upload={r['upload_ms']:.0f}ms  "
                          f"total={r['total_ms']:.0f}ms  "
                          f"{r.get('status', '')}  {fid}  "
                          f"{r.get('error', '')[:80]}")

        t_start = time.monotonic()
        await asyncio.gather(*[asyncio.create_task(task(i+1)) for i in range(total)])
        wall = time.monotonic() - t_start

    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]

    print(bold(f"\n{'='*60}"))
    print(bold(f"  压测报告"))
    print(bold(f"{'='*60}"))
    print(f"  总请求:     {total}")
    print(f"  成功:       {green(str(len(ok)))}")
    print(f"  失败:       {red(str(len(fail)))}")
    print(f"  耗时:       {wall:.1f}s")
    print(f"  QPS:        {total / wall:.2f} req/s")

    if ok:
        up = [r["upload_ms"] for r in ok]
        tot = [r["total_ms"] for r in ok]
        s_up = sorted(up)
        print(f"\n  上传耗时 (ms):")
        print(f"    min={min(up):.0f}  avg={statistics.mean(up):.0f}  "
              f"med={statistics.median(up):.0f}  max={max(up):.0f}  "
              f"p95={s_up[int(len(s_up)*0.95)]:.0f}")
        if poll:
            s_tot = sorted(tot)
            print(f"  端到端耗时 (ms):")
            print(f"    min={min(tot):.0f}  avg={statistics.mean(tot):.0f}  "
                  f"med={statistics.median(tot):.0f}  max={max(tot):.0f}  "
                  f"p95={s_tot[int(len(s_tot)*0.95)]:.0f}")

    if fail:
        print(f"\n  {red('失败详情:')}")
        from collections import Counter
        errors = Counter(r["error"][:120] for r in fail)
        for err, cnt in errors.most_common(10):
            print(f"    [{cnt}x] {err}")

    print(bold(f"{'='*60}\n"))


def main():
    p = argparse.ArgumentParser(description="发票识别压测")
    p.add_argument("--url", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--total", type=int, default=10)
    p.add_argument("--poll-interval", type=float, default=3)
    p.add_argument("--no-poll", action="store_true")
    args = p.parse_args()

    if not Path(args.file).exists():
        print(red(f"文件不存在: {args.file}"))
        sys.exit(1)

    asyncio.run(run_stress(
        base_url=args.url.rstrip("/"),
        token=args.token,
        file_path=args.file,
        concurrency=args.concurrency,
        total=args.total,
        poll=not args.no_poll,
        poll_interval=args.poll_interval,
    ))


if __name__ == "__main__":
    main()
