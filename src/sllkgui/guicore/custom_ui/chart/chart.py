"""图表组件（Windows Fluent Design 数据可视化）。

支持 ``line`` / ``bar`` / ``pie`` / ``doughnut`` / ``polar`` / ``radar`` 六种类型，
底层使用 ``PySide6.QtCharts``。雷达图与极坐标图复用 ``QPolarChart``：类别刻度放在
角向轴上，数值放在径向轴上，雷达图把首值补到末尾形成闭合折线。

配色约定：

- 背景、标题、坐标轴、图例文字全部实时读取 :func:`~..display.palette.tokens`
  与 ``ColorPalette``，暗色/亮色主题下自动跟随；
- 系列颜色取设计令牌拼成一组调色板，不写死具体色值；
- ``refresh_theme()`` 会按当前主题重建一次图形，主题切换后调用即可。

QtCharts 缺失时模块仍可导入：``CChart`` 会退化为一个显示清晰错误说明的占位控件，
不会在导入阶段直接抛出异常。
"""

from __future__ import annotations

from PySide6.QtCore import QMargins, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from sllkgui.appcore import AppSettings, ColorPalette, get_theme_manager

from ..display.palette import tokens

try:  # pragma: no cover - 依赖 QtCharts，本机环境正常可用
    from PySide6.QtCharts import (
        QBarCategoryAxis,
        QBarSeries,
        QBarSet,
        QCategoryAxis,
        QChart,
        QChartView,
        QLineSeries,
        QPieSeries,
        QPolarChart,
        QValueAxis,
    )

    _CHARTS_AVAILABLE = True
    _CHARTS_ERROR = ""
except Exception as exc:  # pragma: no cover - 仅在缺少 QtCharts 的环境触发
    _CHARTS_AVAILABLE = False
    _CHARTS_ERROR = f"QtCharts 不可用：{exc}"

#: 支持的图表类型
CHART_TYPES = ("line", "bar", "pie", "doughnut", "polar", "radar")

#: 图表圆角
_RADIUS = 8


def _chart_config() -> int:
    """图表圆角，配置缺失时回落默认值。"""
    try:
        return int(AppSettings.chart.radius)
    except Exception:
        return _RADIUS


def charts_available() -> bool:
    """返回当前环境是否成功导入 QtCharts。"""
    return _CHARTS_AVAILABLE


def chart_palette() -> list[QColor]:
    """系列调色板：从设计令牌与 ``ColorPalette`` 现取，不写死色值。"""
    base = tokens()
    return [
        QColor(base["accent"]),
        QColor(ColorPalette.custom_context_hover),
        QColor(ColorPalette.custom_green),
        QColor(ColorPalette.custom_yellow),
        QColor(ColorPalette.custom_pink),
        QColor(ColorPalette.custom_red),
        QColor(ColorPalette.custom_icon_color),
        QColor(ColorPalette.custom_bg_active_one),
    ]


def _normalize_chart_type(chart_type: str) -> str:
    kind = str(chart_type).strip().lower()
    if kind not in CHART_TYPES:
        raise ValueError(f"不支持的图表类型：{chart_type}（可选：{', '.join(CHART_TYPES)}）")
    return kind


def _normalize_series(series) -> list[dict]:
    """把调用方传入的 series 统一成 ``{name, values, labels}``。"""
    result: list[dict] = []
    for item in list(series or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "Series")
        values = [float(value) for value in (item.get("values") or [])]
        labels = [str(label) for label in (item.get("labels") or [])]
        result.append({"name": name, "values": values, "labels": labels})
    return result


def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(AppSettings.family)
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


class CChart(QWidget):
    """PrimeVue Chart 风格的图表控件。

    参数:
        chart_type: 图表类型，见 :data:`CHART_TYPES`。
        title: 标题。
        animation: 是否启用系列动画。
        legend: 是否显示图例。
        parent: 父控件。

    信号:
        pointClicked(str, float): 点击数据点时发出 ``(系列名, 数值)``。
            ``polar`` / ``radar`` 的数值为被点击点的 y 值，``bar`` 为对应柱的值，
            ``pie`` / ``doughnut`` 为扇区值。
    """

    pointClicked = Signal(str, float)

    def __init__(
        self,
        chart_type: str = "line",
        title: str = "",
        animation: bool = True,
        legend: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._radius = _chart_config()
        self.setObjectName("CChart_Widget")
        self._chart_type = _normalize_chart_type(chart_type)
        self._title = str(title)
        self._animation = bool(animation)
        self._legend_visible = bool(legend)
        self._series_data: list[dict] = []
        self._chart = None
        self._view = None
        self._error_label: QLabel | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        try:
            get_theme_manager().subscribe(self.refresh_theme)
        except Exception:  # pragma: no cover - 配置上下文未就绪时不影响图表构造
            pass

        if not _CHARTS_AVAILABLE:
            self._show_error()
            return

        self._build_view()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def chart_type(self) -> str:
        return self._chart_type

    def title(self) -> str:
        return self._title

    def chart(self):
        """底层 ``QChart``（QtCharts 不可用时返回 ``None``）。"""
        return self._chart

    def series_data(self) -> list[dict]:
        return [
            {"name": item["name"], "values": list(item["values"]), "labels": list(item["labels"])}
            for item in self._series_data
        ]

    def set_title(self, title: str) -> None:
        """设置图表标题。"""
        self._title = str(title)
        if self._chart is not None:
            self._chart.setTitle(self._title)
            self._apply_theme()

    def set_chart_type(self, chart_type: str) -> None:
        """切换图表类型；极坐标/雷达与笛卡尔图表之间会重建视图。"""
        kind = _normalize_chart_type(chart_type)
        if kind == self._chart_type:
            return
        self._chart_type = kind
        if not _CHARTS_AVAILABLE or self._chart is None:
            return
        polar_needed = kind in ("polar", "radar")
        if isinstance(self._chart, QPolarChart) != polar_needed:
            self._dispose_view()
            self._build_view()
        self._rebuild()
        self._apply_theme()

    def set_data(self, series: list[dict]) -> None:
        """设置数据。

        参数:
            series: 每个元素形如 ``{"name": "系列名", "values": [1, 2, 3],
                "labels": ["A", "B", "C"]}``。饼图/环形图只取第一组数据，
                其余类型按系列逐条绘制。
        """
        self._series_data = _normalize_series(series)
        if _CHARTS_AVAILABLE and self._chart is not None:
            self._rebuild()
            self._apply_theme()

    def set_animation(self, enabled: bool) -> None:
        """开关系列动画。"""
        self._animation = bool(enabled)
        if self._chart is not None:
            self._apply_animation()

    def set_legend_visible(self, visible: bool) -> None:
        """显示/隐藏图例。"""
        self._legend_visible = bool(visible)
        self._apply_theme()

    def refresh_theme(self) -> None:
        """主题切换后调用：按当前令牌重建图形与配色。"""
        if not _CHARTS_AVAILABLE:
            self._apply_error_theme()
            return
        if self._chart is None:
            return
        self._rebuild()
        self._apply_theme()

    # ------------------------------------------------------------------
    # 视图构建
    # ------------------------------------------------------------------
    def _show_error(self) -> None:
        self._error_label = QLabel(_CHARTS_ERROR, self)
        self._error_label.setObjectName("CChart_Error")
        self._error_label.setWordWrap(True)
        self._error_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._error_label)
        self._apply_error_theme()

    def _apply_error_theme(self) -> None:
        if self._error_label is None:
            return
        palette = tokens()
        self._error_label.setStyleSheet(
            f"color: {palette['muted']}; background: transparent;"
            " padding: 12px; border: 1px solid transparent;"
        )

    def _new_chart(self):
        chart = QPolarChart() if self._chart_type in ("polar", "radar") else QChart()
        chart.setBackgroundRoundness(self._radius)
        chart.setMargins(QMargins(8, 8, 8, 8))
        chart.setTitle(self._title)
        return chart

    def _build_view(self) -> None:
        self._chart = self._new_chart()
        self._view = QChartView(self._chart, self)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 图表不再自带底色：QChartView 的 viewport 默认会铺一层未填充背景，
        # 与表格同理，会让宿主卡片的玻璃表面被整块实色挡住。
        self._view.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._view.setAutoFillBackground(False)
        self._view.viewport().setAutoFillBackground(False)
        self._view.setStyleSheet("background: transparent; border: none;")
        self._layout.addWidget(self._view)
        self._apply_animation()
        self._apply_theme()

    def _dispose_view(self) -> None:
        if self._view is not None:
            self._layout.removeWidget(self._view)
            self._view.deleteLater()
            self._view = None
        self._chart = None

    def _apply_animation(self) -> None:
        if self._chart is None:
            return
        option = QChart.AnimationOption.SeriesAnimations if self._animation else QChart.AnimationOption.NoAnimation
        self._chart.setAnimationOptions(option)
        self._chart.setAnimationDuration(420)

    # ------------------------------------------------------------------
    # 绘制数据
    # ------------------------------------------------------------------
    def _labels(self) -> list[str]:
        for item in self._series_data:
            if item["labels"]:
                return list(item["labels"])
        if not self._series_data:
            return []
        return [str(index + 1) for index in range(len(self._series_data[0]["values"]))]

    @staticmethod
    def _value_range(values: list[float]) -> tuple[float, float]:
        if not values:
            return 0.0, 1.0
        low = min(0.0, min(values))
        high = max(0.0, max(values))
        if high == low:
            high = low + 1.0
        if high <= 0:
            high = 1.0
        return low, high

    def _series_color(self, index: int) -> QColor:
        palette = chart_palette()
        return palette[index % len(palette)]

    def _rebuild(self) -> None:
        if not _CHARTS_AVAILABLE or self._chart is None:
            return
        chart = self._chart
        for series in list(chart.series()):
            chart.removeSeries(series)
        for axis in list(chart.axes()):
            chart.removeAxis(axis)

        if not self._series_data:
            return
        kind = self._chart_type
        if kind in ("line", "polar", "radar"):
            self._build_lines()
        elif kind == "bar":
            self._build_bars()
        else:
            self._build_pie()

    def _build_lines(self) -> None:
        chart = self._chart
        labels = self._labels()
        series_objects = []
        kind = self._chart_type
        for index, item in enumerate(self._series_data):
            line = QLineSeries()
            line.setName(item["name"])
            pen = QPen(self._series_color(index))
            pen.setWidthF(2.2)
            line.setPen(pen)

            values = item["values"]
            points = [(float(position) + 0.5, value) for position, value in enumerate(values)]
            if kind == "radar" and len(points) > 1:
                points = points + [points[0]]

            for x_value, y_value in points:
                line.append(x_value, y_value)

            name = item["name"]
            line.clicked.connect(lambda point, series_name=name: self.pointClicked.emit(series_name, float(point.y())))
            chart.addSeries(line)
            series_objects.append(line)

        if kind in ("polar", "radar"):
            self._attach_polar_axes(labels, series_objects)
        else:
            self._attach_cartesian_axes(labels, series_objects)

    def _build_bars(self) -> None:
        chart = self._chart
        labels = self._labels()
        bar_series = QBarSeries()
        bar_series.setBarWidth(0.72)
        for index, item in enumerate(self._series_data):
            bar_set = QBarSet(item["name"])
            for value in item["values"]:
                bar_set.append(value)
            color = self._series_color(index)
            bar_set.setColor(color)
            bar_set.setBorderColor(color)
            name = item["name"]
            values = list(item["values"])
            bar_set.clicked.connect(
                lambda position, series_name=name, series_values=values: self._emit_indexed(
                    series_name, series_values, position
                )
            )
            bar_series.append(bar_set)

        chart.addSeries(bar_series)

        axis_x = QBarCategoryAxis()
        axis_x.append(labels)
        axis_y = QValueAxis()
        low, high = self._value_range([value for item in self._series_data for value in item["values"]])
        axis_y.setRange(low, high)

        chart.addAxis(axis_x, Qt.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignLeft)
        bar_series.attachAxis(axis_x)
        bar_series.attachAxis(axis_y)

    def _build_pie(self) -> None:
        chart = self._chart
        first = self._series_data[0]
        labels = self._labels()
        values = first["values"]
        pie = QPieSeries()
        pie.setName(first["name"])
        if self._chart_type == "doughnut":
            pie.setHoleSize(0.38)

        text_color = QColor(tokens()["text"])
        name = first["name"]
        for index, value in enumerate(values):
            label = labels[index] if index < len(labels) else str(index + 1)
            pie_slice = pie.append(label, value)
            color = self._series_color(index)
            pie_slice.setBrush(color)
            pie_slice.setPen(QPen(color))
            pie_slice.setLabelVisible(True)
            pie_slice.setLabelColor(text_color)
            pie_slice.clicked.connect(
                lambda _checked=False, series_name=name, slice_value=value: self.pointClicked.emit(
                    series_name, float(slice_value)
                )
            )
        chart.addSeries(pie)

    def _emit_indexed(self, name: str, values: list[float], position: int) -> None:
        if 0 <= position < len(values):
            self.pointClicked.emit(name, float(values[position]))

    def _attach_cartesian_axes(self, labels: list[str], series_objects: list) -> None:
        axis_x = QCategoryAxis()
        axis_x.setStartValue(0)
        axis_x.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionCenter)
        for index, label in enumerate(labels):
            axis_x.append(label, float(index + 1))
        axis_x.setRange(0, float(max(1, len(labels))))

        axis_y = QValueAxis()
        low, high = self._value_range([value for item in self._series_data for value in item["values"]])
        axis_y.setRange(low, high)

        self._chart.addAxis(axis_x, Qt.AlignBottom)
        self._chart.addAxis(axis_y, Qt.AlignLeft)
        for series in series_objects:
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

    def _attach_polar_axes(self, labels: list[str], series_objects: list) -> None:
        angular = QCategoryAxis()
        angular.setStartValue(0)
        angular.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionCenter)
        for index, label in enumerate(labels):
            angular.append(label, float(index + 1))
        angular.setRange(0, float(max(1, len(labels))))

        radial = QValueAxis()
        high = max(1.0, max((value for item in self._series_data for value in item["values"]), default=1.0))
        radial.setRange(0, high)

        orientation = QPolarChart.PolarOrientation
        self._chart.addAxis(angular, orientation.PolarOrientationAngular)
        self._chart.addAxis(radial, orientation.PolarOrientationRadial)
        for series in series_objects:
            series.attachAxis(angular)
            series.attachAxis(radial)

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        if self._chart is None:
            return
        palette = tokens()
        text = QColor(palette["text"])
        muted = QColor(palette["muted"])
        border = QColor(palette["border"])

        chart = self._chart
        # 透出卡片玻璃；图表只负责数据层，不再画自己的实色背景。
        chart.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
        chart.setBackgroundPen(QPen(Qt.PenStyle.NoPen))
        chart.setPlotAreaBackgroundVisible(False)
        chart.setTitleBrush(QBrush(text))
        chart.setTitleFont(_font(15, QFont.Weight.DemiBold))

        legend = chart.legend()
        legend.setVisible(self._legend_visible)
        legend.setAlignment(Qt.AlignBottom)
        legend.setLabelColor(text)
        legend.setBackgroundVisible(False)
        legend.setFont(_font(11))

        if self._view is not None:
            self._view.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))

        for axis in chart.axes():
            axis.setLabelsColor(muted)
            axis.setLabelsFont(_font(11))
            axis.setTitleBrush(QBrush(text))
            axis.setGridLineColor(border)
            axis.setLinePenColor(border)

        if _CHARTS_AVAILABLE:
            for series in chart.series():
                if isinstance(series, QPieSeries):
                    for pie_slice in series.slices():
                        pie_slice.setLabelColor(text)
        self.update()


__all__ = ["CChart", "CHART_TYPES", "chart_palette", "charts_available"]
