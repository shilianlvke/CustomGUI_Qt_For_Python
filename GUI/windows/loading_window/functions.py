from PySide6.QtCore import QObject, QRunnable, QMutex, QWaitCondition, QMutexLocker, Signal
from AppCore import (
    AppError,
    DomainErrorBoundary,
    Logger,
    UIErrorBoundary,
    YamlHandler,
    record_event,
    to_user_message,
    track_timing,
)
from easydict import EasyDict


class LoadingSignalBus(QObject):
    """加载流程信号总线。"""

    progress_updated = Signal(int)  # 进度更新信号
    finished = Signal()  # 完成信号
    error_occurred = Signal(str)  # 错误信号


class ResourceLoader:
    """资源加载器。

    职责:
    - 按配置步骤加载启动资源。
    - 通过信号上报进度、完成与错误。
    """

    def __init__(self):
        """初始化资源加载器。"""

        Logger.tool(__class__)
        self.value = 0
        self._paused = False
        self._stopped = False
        self._lock = QMutex()
        self._cond = QWaitCondition()
        self.bus = LoadingSignalBus()
        self.sys_config = EasyDict()
        self.load_config()

    def load_config(self):
        """加载启动配置与基础路径。

        返回:
        - None
        """

        self.loading_config = YamlHandler("resource/loading_config.yml")
        self._base_paths = self.loading_config.base_path

    def stop(self):
        """停止加载流程。

        返回:
        - None
        """

        with QMutexLocker(self._lock):
            self._stopped = True
            self._paused = False
            self._cond.wakeOne()

    def resume(self):
        """恢复已暂停的加载流程。

        返回:
        - None
        """

        if self._paused:
            with QMutexLocker(self._lock):
                self._paused = False
                self._cond.wakeOne()

    def send_progress(self, value):
        """发送进度更新信号。

        参数:
        - value: 当前进度值。

        返回:
        - None
        """

        self.bus.progress_updated.emit(value)

    def perform_loading(self):
        """执行完整加载流程。

        返回:
        - None
        """

        try:
            with track_timing("loading.total", category="perf"):
                for category, steps in self.loading_config.loading_steps.items():
                    if self._stopped:
                        return
                    Logger.debug(f"加载{category}配置")
                    for step in steps:
                        if self._stopped:
                            return
                        self._load_step(step, category)
            Logger.info(f"{self.sys_config.app_lang.custom_ui.sys_name}-{self.sys_config.app_lang.custom_ui.sys_copyright}")
            record_event("loading.finished", category="loading")
            self.bus.finished.emit()
        except AppError as e:
            Logger.error(str(e))
            record_event(
                "loading.error",
                category="loading",
                level="error",
                payload={"code": e.code, "layer": e.layer},
            )
            self.bus.error_occurred.emit(to_user_message(e))
        except Exception as e:
            wrapped = UIErrorBoundary(
                code="LOADING_UNEXPECTED_ERROR",
                message="加载流程发生未预期错误",
                details=str(e),
            )
            Logger.error(str(wrapped))
            record_event(
                "loading.error",
                category="loading",
                level="error",
                payload={"code": wrapped.code, "layer": wrapped.layer},
            )
            self.bus.error_occurred.emit(to_user_message(wrapped))

    def _load_step(self, step_config, category):
        """执行单个加载步骤。

        参数:
        - step_config: 步骤配置对象。
        - category: 步骤所属分类。

        返回:
        - None
        """

        if self._stopped:
            return
        try:
            full_path = f"{self._base_paths[category]}{step_config['path']}"
            data = YamlHandler(full_path)
        except AppError:
            raise
        except Exception as exc:
            raise DomainErrorBoundary(
                code="LOADING_STEP_READ_FAILED",
                message="加载步骤读取失败",
                details=f"{category}:{step_config.get('path')}: {exc}",
            ) from exc
        if step_config.get("merge"):
            # 合并数据
            existing = self.sys_config[step_config["target"]]
            existing.merge(data)
            self.sys_config[step_config["target"]] = existing
        else:
            # 新增数据
            self.sys_config[step_config["target"]] = data
        self.send_progress(step_config["progress"])
        record_event(
            "loading.step",
            category="loading",
            payload={
                "category": category,
                "target": step_config.get("target", ""),
                "progress": step_config.get("progress", 0),
            },
        )
        self._paused = True
        with QMutexLocker(self._lock):
            while self._paused and not self._stopped:
                self._cond.wait(self._lock)


class LoadingTask(QRunnable):
    """线程池加载任务包装器。"""

    def __init__(self, loader: ResourceLoader):
        """初始化加载任务。

        参数:
        - loader: 资源加载器实例。

        返回:
        - None
        """

        super().__init__()
        self.loader = loader

    def run(self):
        """执行任务入口。

        返回:
        - None
        """

        self.loader.perform_loading()
