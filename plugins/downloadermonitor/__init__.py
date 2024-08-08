import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional

import pytz
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.modules.qbittorrent.qbittorrent import Qbittorrent
from app.plugins import _PluginBase
from app.plugins.zvideoassistant.DoubanHelper import *
from app.plugins.zvideoassistant.ScoreHelper import *
from app.schemas.types import EventType, NotificationType
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class DownloaderMonitor(_PluginBase):
    # 插件名称
    plugin_name = "下载器监控器"
    # 插件描述
    plugin_desc = "监控源文件删除后自动删除种子"
    # 插件图标
    plugin_icon = "torrent.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "fx786595833"
    # 作者主页
    author_url = "https://github.com/fx786595833"
    # 插件配置项ID前缀
    plugin_config_prefix = "downloadermonitor"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _cron = None
    _notify = False
    _onlyonce = False
    _map_path = ""
    _mark = False
    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None
    _qbittorrent = None

    def init_plugin(self, config: dict = None):
        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")
            self._map_path = config.get("map_path")
            self._qbittorrent = Qbittorrent()
            self._mark = config.get("mark")

        # 加载模块
        if self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info(f"下载器监控器服务启动，立即运行一次")
            self._scheduler.add_job(
                func=self.do_job,
                trigger="date",
                run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                name="下载器监控器",
            )
            # 关闭一次性开关
            self._onlyonce = False
            self._update_config()

            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    def _update_config(self):
        self.update_config(
            {
                "onlyonce": False,
                "cron": self._cron,
                "enabled": self._enabled,
                "notify": self._notify,
                "map_path": self._db_path,
                "mark": self._mark,
            }
        )

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    @eventmanager.register(EventType.PluginAction)
    def handle_command(self, event: Event):
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        if self._enabled and self._cron:
            return [
                {
                    "id": "DownloaderMonitor",
                    "name": "源文件已删除种子移除",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.do_job,
                    "kwargs": {},
                }
            ]

    def do_job(self):
        torrents, error = self._qbittorrent.get_torrents()
        message = ""

        if error:
            logger.error("无法连接qbittorrent下载器")
        if torrents:
            for torrent in torrents:
                save_path = torrent["save_path"]
                torrent_name = torrent["name"]

                previous_path = Path(save_path).joinpath(torrent_name)
                if self._map_path:
                    paths = self._map_path.split("\n")
                    for path in paths:
                        sub_paths = path.split(":")
                        save_path = save_path.replace(sub_paths[0], sub_paths[1]).replace('\\', '/')

                file_path = Path(save_path).joinpath(torrent_name)
                logger.debug(f"种子转换前路径:{previous_path}，转换后路径:{file_path}")
                # 获取种子name
                if not os.path.exists(file_path):
                    if self._mark:
                        logger.debug(f"标记种子为待删除，file={file_path}")
                        self._qbittorrent.set_torrents_tag(ids=torrent['hash'], tags=["待删除"])
                        message += f"种子{torrent_name}被标记为待删除\n"
                    else:
                        logger.debug(f"删除不存在目录的种子，file={file_path}")
                        success = self._qbittorrent.delete_torrents(delete_file=False, ids=torrent['hash'])
                        if success:
                            logger.debug(f"删除种子成功，name={torrent['name']}")
                            message += f"种子{torrent_name}删除成功\n"
                        else:
                            logger.debug(f"删除种子失败，name={torrent['name']}")
                            message += f"种子{torrent_name}删除失败\n"
        if self._notify and len(message) > 0:
            self.post_message(
                mtype=NotificationType.Plugin,
                title="【下载器监控器】",
                text=message,
            )

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "开启通知",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "mark",
                                            "label": "仅打上标记",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "cron", "label": "执行周期"},
                                    }
                                ],
                            },
                        ],
                    },

                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "map_path",
                                            "label": "目录映射",
                                            'rows': 5,
                                            "placeholder": "每一行一个目录，下载器保存目录:MoviePilot映射目录",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {
                                    "cols": 12,
                                },
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "error",
                                            "variant": "tonal",
                                            "text": "强烈建议第一次使用前选择仅标记模式，以免因路径配置不正确导致种子误删除。",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {
                                    "cols": 12,
                                },
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "建议配合【清理硬链接】插件配合使用，实现删除媒体库文件时，自动删除对应的种子",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "notify": False,
            "onlyonce": False,
            "cron": "0 0 * * *",
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))
