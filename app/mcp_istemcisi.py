"""Agent → MCP HTTP bağlantısı. Agent'ın tüm veri ve politika erişimi MCP araçlarıyla yapılır.

Ders kodu `7. Gün Kodlar Tekrar/mcp_istemcisi.py`'den alındı (URL config'den okunur).
"""
from __future__ import annotations

import asyncio
import json
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import MCP_URL


def _parse(result):
    if result.isError:
        parcalar = [getattr(item, "text", str(item)) for item in result.content]
        raise RuntimeError("MCP araç hatası: " + " | ".join(parcalar))
    struct = getattr(result, "structuredContent", None)
    if isinstance(struct, dict):
        return struct.get("result", struct)
    for item in result.content:
        if hasattr(item, "text"):
            try:
                return json.loads(item.text)
            except ValueError:
                return {"text": item.text}
    return {}


async def call_async(tool_name: str, arguments: dict):
    async with streamablehttp_client(MCP_URL) as streams:
        read, write = streams[:2]
        async with ClientSession(read, write) as session:
            await session.initialize()
            return _parse(await session.call_tool(tool_name, arguments=arguments))


def call(tool_name: str, arguments: dict, attempts: int = 1):
    """Yalnızca okuma/idempotent araçlarda attempts > 1 kullanın (yazma araçları operation_key ile güvenlidir)."""
    for deneme in range(1, attempts + 1):
        print(f"[CLIENT] → MCP {tool_name} ({deneme}/{attempts})", flush=True)
        try:
            sonuc = asyncio.run(call_async(tool_name, arguments))
            print(f"[CLIENT] ← {json.dumps(sonuc, ensure_ascii=False, default=str)[:200]}", flush=True)
            return sonuc
        except Exception as exc:
            print(f"[CLIENT] ✗ {type(exc).__name__}: {exc}", flush=True)
            if deneme == attempts:
                raise
            time.sleep(0.35 * deneme)


async def list_tools():
    async with streamablehttp_client(MCP_URL) as streams:
        read, write = streams[:2]
        async with ClientSession(read, write) as session:
            await session.initialize()
            for t in (await session.list_tools()).tools:
                print(f" • {t.name}: {t.description or ''}")


if __name__ == "__main__":
    asyncio.run(list_tools())
    print(call("siparis_getir", {"siparis_no": "SP-2001"}))
