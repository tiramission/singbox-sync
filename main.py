import httpx
import pathlib
import json
import datetime
import typing
import loguru
import tenacity
import sys
import os

subscribe_url: str = os.getenv("SUBSCRIBE_URL")
if not subscribe_url:
    loguru.logger.error("请提供 SUBSCRIBE_URL 环境变量")
    sys.exit(-1)

class utils:
    type Filter[T] = typing.Callable[[T], bool]

    @staticmethod
    def remove_item[T](items: list[T], *func: Filter[T]) -> list[T]:
        return [item for item in items if not any(f(item) for f in func)]

    @staticmethod
    def item_in[T](s: T) -> Filter[T]:
        return lambda x: s in x


@tenacity.retry(
    reraise=True,
    stop=tenacity.stop_after_attempt(3),
)
def update():
    resp = httpx.get(subscribe_url)
    config: dict = resp.json()
    config_inbounds(config)
    config_outbounds(config)
    config_route(config)
    data = json.dumps(config, indent=2, ensure_ascii=False)
    pathlib.Path("/etc/sing-box/config.json").write_text(data)
    loguru.logger.info("配置生成完成")


def config_route(config: dict):
    config["route"]["final"] = "自动选择"


def config_outbounds(config: dict):
    outbounds: list = config["outbounds"]
    for idx, outbound in enumerate(outbounds):
        match outbound["tag"]:
            case "自动选择":
                in_outbounds: list = outbound["outbounds"]
                in_outbounds = utils.remove_item(
                    in_outbounds,
                    utils.item_in("剩余流量"),
                    utils.item_in("距离下次重置剩余"),
                    utils.item_in("套餐到期"),
                )
                outbound["outbounds"] = in_outbounds
        outbounds[idx] = outbound
    config["outbounds"] = outbounds


def config_inbounds(config: dict):
    config["inbounds"] = [
        {
            "type": "mixed",
            "listen": "::",
            "listen_port": 7890,
            "tcp_fast_open": True,
            "sniff": True,
        },
        {
            "type": "tun",
            "tag": "tun-in",
            "inet4_address": "172.19.0.1/30",
            "inet6_address": "fdfe:dcba:9876::1/126",
            "auto_route": True,
            "strict_route": True,
            "stack": "mixed",
            "sniff": True,
        },
    ]
    config["inbounds"] = [ inbound for inbound in config["inbounds"] if inbound.get("type") != "tun" ]


if __name__ == "__main__":
    update()