#!/usr/bin/env python3
"""
发票识别压测脚本

支持两种模式：
  默认模式：  类似 JMeter — 快速发送所有请求，再轮询结果
  老模式：    --classic — 信号量模型，上一批完成才发下一批

用法：
  # JMeter 模式（推荐，匹配 JMeter 行为）
  uv run python tests/stress_test_invoice.py \
    --url https://aisit.qdccb.cn:9900/vlagent/api \
    --token "Bearer eyJ..." \
    --file ./test.jpg \
    --concurrency 10 \
    --total 1000

  # 老模式（信号量排队）
  uv run python tests/stress_test_invoice.py \
    --url https://aisit.qdccb.cn:9900/vlagent/api \
    --token "Bearer eyJ..." \
    --file ./test.jpg \
    --concurrency 10 \
    --total 1000 \
    --classic

  # 只发请求，不轮询结果（纯粹测接口吞吐）
  uv run python tests/stress_test_invoice.py \
    --url https://aisit.qdccb.cn:9900/vlagent/api \
    --token "Bearer eyJ..." \
    --file ./test.jpg \
    --concurrency 10 \
    --total 1000 \
    --no-poll
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


async def upload_one(client, base_url, file_path, idx):
    """只做上传（发送请求），不轮询。返回上传结果。"""
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
        result["ok"] = True
        result["status"] = "uploaded"

    except Exception as e:
        result["error"] = f"上传异常: {type(e).__name__}: {e}"
        result["total_ms"] = (time.monotonic() - t0) * 1000
        return result

    result["total_ms"] = (time.monotonic() - t0) * 1000
    return result


async def poll_one(client, base_url, file_id, idx, poll_interval=3):
    """轮询单个任务直到完成/失败/超时。就地修改传入的 result dict。"""
    deadline = time.monotonic() + 600
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
                return {"ok": True, "status": "done", "error": ""}
            elif st == "failed":
                return {"ok": False, "status": "failed",
                        "error": f"识别失败: {d.get('error_msg', '')[:200]}"}
        except Exception:
            continue

    return {"ok": False, "status": "timeout", "error": "轮询超时 (600s)"}


# ──────────────────────────────────────────────
# 模式一：JMeter 风格 — 快速发送所有请求，再轮询
# ──────────────────────────────────────────────
async def run_jmeter_mode(base_url, token, file_path, concurrency, total,
                          poll, poll_interval):
    headers = {"Authorization": token}
    ssl_ctx = make_ssl_context()

    print(bold(f"\n{'='*60}"))
    print(bold(f"  发票识别压测（JMeter 模式）"))
    print(f"  URL:        {base_url}/invoice_recognition/...")
    print(f"  文件:       {file_path}")
    print(f"  并发:       {concurrency}")
    print(f"  总数:       {total}")
    print(f"  轮询结果:   {'是' if poll else '否'}")
    print(bold(f"{'='*60}\n"))

    async with httpx.AsyncClient(headers=headers, verify=ssl_ctx, timeout=120) as client:

        # ── 阶段一：快速发送所有上传请求 ──
        print(cyan(f"▶ 阶段一：发送 {total} 个上传请求（并发={concurrency}）"))
        sem = asyncio.Semaphore(concurrency)
        upload_results = [None] * total

        async def send_task(idx):
            async with sem:
                r = await upload_one(client, base_url, file_path, idx)
                upload_results[idx] = r
                mark = green("OK") if r["ok"] else red("FAIL")
                fid = f"file_id={r['file_id']}" if r.get("file_id") else ""
                print(f"  [{idx+1}/{total}] {mark}  upload={r['upload_ms']:.0f}ms  "
                      f"{fid}  {r.get('error', '')[:80]}")

        t_send_start = time.monotonic()
        await asyncio.gather(*[asyncio.create_task(send_task(i)) for i in range(total)])
        send_wall = time.monotonic() - t_send_start

        upload_ok = [r for r in upload_results if r and r["ok"]]
        upload_fail = [r for r in upload_results if r and not r["ok"]]

        print(f"\n  发送完成: {len(upload_ok)} 成功, {len(upload_fail)} 失败, "
              f"耗时 {send_wall:.1f}s, "
              f"发送 QPS: {total / send_wall:.2f} req/s")

        if not poll or not upload_ok:
            print_report(upload_results, total, send_wall, poll)
            return

        # ── 阶段二：轮询所有已上传任务的结果 ──
        print(cyan(f"\n▶ 阶段二：轮询 {len(upload_ok)} 个任务的结果"))

        poll_results = {}

        async def poll_task(r):
            file_id = r["file_id"]
            t0 = time.monotonic()
            pr = await poll_one(client, base_url, file_id, r["idx"], poll_interval)
            elapsed = (time.monotonic() - t0) * 1000
            poll_results[file_id] = {**pr, "poll_ms": elapsed}
            mark = green("✓") if pr["ok"] else red("✗")
            print(f"  {mark} #{r['idx']:>3d} file_id={file_id}  "
                  f"poll={elapsed:.0f}ms  {pr['status']}  {pr.get('error', '')[:60]}")

        t_poll_start = time.monotonic()
        await asyncio.gather(*[asyncio.create_task(poll_task(r)) for r in upload_ok])
        poll_wall = time.monotonic() - t_poll_start

        # 合并结果
        for r in upload_ok:
            fid = r["file_id"]
            if fid in poll_results:
                pr = poll_results[fid]
                r["ok"] = pr["ok"]
                r["status"] = pr["status"]
                r["error"] = pr["error"]
                r["total_ms"] = r["upload_ms"] + pr["poll_ms"]

        all_ok = [r for r in upload_results if r and r["ok"]]
        all_fail = [r for r in upload_results if r and not r["ok"]]

        print(f"\n  轮询完成: {len(all_ok)} 成功, {len(all_fail)} 失败, "
              f"耗时 {poll_wall:.1f}s")

        total_wall = time.monotonic() - t_send_start
        print_report(upload_results, total, total_wall, poll)


# ──────────────────────────────────────────────
# 模式二：经典模式 — 信号量排队（老逻辑）
# ──────────────────────────────────────────────
async def run_classic_mode(base_url, token, file_path, concurrency, total,
                           poll, poll_interval):
    results = []
    done_count = 0
    lock = asyncio.Lock()
    headers = {"Authorization": token}

    print(bold(f"\n{'='*60}"))
    print(bold(f"  发票识别压测（经典模式）"))
    print(f"  URL:        {base_url}/invoice_recognition/...")
    print(f"  文件:       {file_path}")
    print(f"  并发:       {concurrency}")
    print(f"  总数:       {total}")
    print(f"  轮询结果:   {'是' if poll else '否'}")
    print(bold(f"{'='*60}\n"))

    ssl_ctx = make_ssl_context()
    async with httpx.AsyncClient(headers=headers, verify=ssl_ctx, timeout=120) as client:
        sem = asyncio.Semaphore(concurrency)

        async def task(idx):
            nonlocal done_count
            async with sem:
                r = await upload_one(client, base_url, file_path, idx)
                if poll and r["ok"] and r.get("file_id"):
                    pr = await poll_one(client, base_url, r["file_id"], idx, poll_interval)
                    r["ok"] = pr["ok"]
                    r["status"] = pr["status"]
                    r["error"] = pr["error"]
                    r["total_ms"] = r["upload_ms"] + pr.get("poll_ms", 0)

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

    print_report(results, total, wall, poll)


def print_report(results, total, wall, poll):
    ok = [r for r in results if r and r["ok"]]
    fail = [r for r in results if r and not r["ok"]]

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
        s_up = sorted(up)
        print(f"\n  上传耗时 (ms):")
        print(f"    min={min(up):.0f}  avg={statistics.mean(up):.0f}  "
              f"med={statistics.median(up):.0f}  max={max(up):.0f}  "
              f"p95={s_up[int(len(s_up)*0.95)]:.0f}")
        if poll:
            tot = [r["total_ms"] for r in ok]
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
    p.add_argument("--no-poll", action="store_true",
                   help="只发送上传请求，不轮询结果")
    p.add_argument("--classic", action="store_true",
                   help="使用经典信号量模式（等上一批完成才发下一批）")
    args = p.parse_args()

    if not Path(args.file).exists():
        print(red(f"文件不存在: {args.file}"))
        sys.exit(1)

    poll = not args.no_poll
    common = dict(
        base_url=args.url.rstrip("/"),
        token=args.token,
        file_path=args.file,
        concurrency=args.concurrency,
        total=args.total,
        poll=poll,
        poll_interval=args.poll_interval,
    )

    if args.classic:
        asyncio.run(run_classic_mode(**common))
    else:
        asyncio.run(run_jmeter_mode(**common))


if __name__ == "__main__":
    main()
