# 按钮组件复刻计划（Sakai / PrimeVue Aura）

复刻对象：<https://sakai.primevue.org/uikit/button>
源码依据：`sakai-vue/src/views/uikit/ButtonDoc.vue` + `@primeuix/themes` 的 `presets/aura/button`、`presets/aura/base` 设计令牌。

目标：在 `GuiCore/CustomUI/button/` 下用 PySide6 复刻出**一套统一按钮组件**，覆盖 Sakai 按钮页的全部 84 个按钮实例，并新增一张「按钮预览」页面替代现有基座页面。

> **实现状态：已完成**（S1–S6）。落地文件：
>
> - `severity.py` —— Aura 深浅两套 severity 色板 + `colors_for()`；
> - `button.py` —— `CButton`（severity × variant × plain/rounded/raised/icon/loading/size）；
> - `button_group.py` / `split_button.py` —— `CButtonGroup` / `CSplitButton`；
> - `Apps/button_preview/` —— 按钮预览页（14 个分组，语言包 + 图标齐全）；
> - 旧页面已整体移到 `Apps_legacy/` 备查，基座只剩按钮预览应用；
> - 新增 6 个单色图标：`customgui/resource/customui/images/svg_icons/`（`icon_check` / `icon_star_fill` / `icon_bookmark` / `icon_bell` / `icon_refresh` / `icon_trash`）。
>
> 与初版计划的差异：`CPushButton` 已收敛为 `CButton` 的兼容壳（固定尺寸语义保留），
> `CStatusButton`（三态循环）与 `CMenuButton`（标题栏）暂时保留独立实现。

---

## 1. 源页面拆解

Sakai 按钮页是一个双栏布局（`md:w-1/2`），共 **14 个分组**。原文模板结构（节选，保留属性组合）：

```vue
<Button label="Submit" />
<Button label="Disabled" :disabled="true" />
<Button label="Link" class="p-button-link" />

<Button label="Primary" />
<Button label="Secondary" severity="secondary" />
...（success / info / warn / help / danger / contrast）

<Button label="Primary" text />
<Button label="Plain" plain text />
<Button label="Primary" outlined />

<ButtonGroup>
  <Button label="Save" icon="pi pi-check" />
  <Button label="Delete" icon="pi pi-trash" />
  <Button label="Cancel" icon="pi pi-times" />
</ButtonGroup>

<SplitButton label="Save" :model="items" severity="secondary" />  <!-- 8 个 severity -->

<Button type="button"><img src="/demo/images/logo-white.svg" /></Button>
<Button type="button" outlined severity="success"><img src="logo.svg" /><span>PrimeVue</span></Button>

<Button icon="pi pi-star-fill" />
<Button label="Bookmark" icon="pi pi-bookmark" />
<Button label="Bookmark" icon="pi pi-bookmark" iconPos="right" />

<Button label="Primary" raised />        <!-- 8 个 severity -->
<Button label="Primary" rounded />       <!-- 8 个 severity -->
<Button icon="pi pi-check" rounded />    <!-- 7 个，无 contrast -->
<Button icon="pi pi-check" text raised rounded />          <!-- 7 个 -->
<Button icon="pi pi-check" rounded outlined />             <!-- 7 个 -->

<Button label="Search" icon="pi pi-search" :loading="loading[0]" />
<Button label="Search" icon="pi pi-search" iconPos="right" :loading="loading[1]" />
<Button icon="pi pi-search" :loading="loading[2]" />
<Button label="Search" :loading="loading[3]" />
```

---

## 2. 复刻清单（共 84 个实例）

| # | 分组 | 数量 | 属性组合 | 说明 |
|---|------|------|----------|------|
| 1 | Default | 3 | 默认 / `disabled` / `link` | Submit、Disabled、Link |
| 2 | Severities | 8 | 实心 + 8 severity | primary…contrast |
| 3 | Text | 8 | `text` + 8 severity（含 `plain text`） | 「Plain」是 `plain + text` |
| 4 | Outlined | 8 | `outlined` + 8 severity | 含 contrast |
| 5 | Group | 3 | 同组内边框合并 | Save / Delete / Cancel，均带图标 |
| 6 | SplitButton | 8 | 主按钮 + 箭头 + 菜单，8 severity | 菜单项：Update / Delete / Home |
| 7 | Templating | 2 | 纯图片按钮 / 图片+文字（outlined success） | 自定义内容插槽 |
| 8 | Icons | 3 | 纯图标 / 图标左 / 图标右（`iconPos="right"`） | |
| 9 | Raised | 8 | `raised` + 8 severity | 阴影 |
| 10 | Rounded | 8 | `rounded` + 8 severity | 胶囊圆角，文字按钮 |
| 11 | Rounded Icons | 7 | `rounded` + 纯图标 | 无 contrast |
| 12 | Rounded Text | 7 | `text raised rounded` + 纯图标 | 无 contrast |
| 13 | Rounded Outlined | 7 | `outlined rounded` + 纯图标 | 无 contrast |
| 14 | Loading | 4 | 加载中（文字左 / 文字右 / 纯图标 / 仅文字） | 点击后 1s 恢复 |
| | **合计** | **84** | | |

### 2.1 按维度归并后，真正要实现的「能力」

| 维度 | 取值 | 数量 |
|------|------|------|
| severity | primary、secondary、success、info、warn、help、danger、contrast（+ plain） | 9 |
| variant | solid（默认）、outlined、text、link | 4 |
| shape | 默认圆角（6px）、`rounded`（胶囊） | 2 |
| elevation | flat、`raised`（阴影） | 2 |
| content | 文字、图标+文字（左）、图标+文字（右）、纯图标、自定义内容 | 5 |
| state | normal、hover、pressed、focus、disabled、loading | 6 |
| size | （Sakai 未展示）sm / md / lg，PrimeVue 支持 | 3（可选） |

结论：**不需要 84 个类**，只需要 3 个组件类 + 一张参数矩阵即可覆盖全部实例。

---

## 3. 组件设计

### 3.1 类划分

| 类 | 职责 | 对应用例 |
|----|------|----------|
| `CButton` | 单按钮，覆盖 severity × variant × shape × elevation × content × state | 分组 1/2/3/4/7/8/9/10/11/12/13/14（73 个） |
| `CButtonGroup` | 横向按钮组，首尾圆角、相邻边框合并 | 分组 5（3 个） |
| `CSplitButton` | 主按钮 + 分隔线 + 箭头按钮 + 弹出菜单 | 分组 6（8 个，依赖现有 `CMenu`） |

### 3.2 `CButton` 建议 API

```python
CButton(
    text: str = "",
    icon: str | QIcon | None = None,
    icon_pos: Literal["left", "right"] = "left",
    severity: Literal["primary", "secondary", "success", "info",
                      "warn", "help", "danger", "contrast"] = "primary",
    variant: Literal["solid", "outlined", "text", "link"] = "solid",
    plain: bool = False,          # 与 text/outlined 组合，走中性灰
    rounded: bool = False,        # 胶囊
    raised: bool = False,         # 阴影
    size: Literal["sm", "md", "lg"] = "md",
    loading: bool = False,
    disabled: bool = False,
    fixed_width: int | None = None,   # 纯图标按钮的方形宽度；None 走 iconOnlyWidth
    parent=None,
)
```

信号：`clicked`、`pressed`、`released`（与 Qt 习惯一致）。

状态机：

```
normal ──enter──> hover ──press──> pressed ──release──> hover ──leave──> normal
  │                                                            │
  └── setEnabled(False) ──> disabled（不响应鼠标/键盘）          │
  └── setLoading(True) ──> loading（锁交互、显示 spinner、保留宽度）─┘
```

### 3.3 交互与可访问性

- 键盘：`Tab` 聚焦、`Space`/`Enter` 触发（复用 `QPushButton` 默认行为）；
- 焦点环：Aura 为 `1px solid {primary}`、offset 2px（与 Sakai 一致，不做虚线框）；
- 状态过渡：hover/pressed 切换时背景、边框、文字在起点与目标状态色之间线性插值，
  时长 `button.hover_duration`（默认 160ms，Aura 为 0.2s；配置为 0 时瞬切），
  图标随文字色一起渐变；
- loading：文案与图标保持占位（避免按钮宽度跳动），右侧/左侧显示旋转指示器；
- disabled：不接收 hover/pressed，透明度与色阶按 Aura 规则处理。

---

## 4. 视觉规格（Aura 主题实测令牌）

### 4.1 尺寸

| Token | md（默认） | sm | lg |
|-------|-----------|----|----|
| 字号 | 1rem（16px，随 `form.field`） | 0.875rem（14px） | 1.125rem（18px） |
| 字重 | 500 | 500 | 500 |
| padding-x | 0.75rem（12px） | 0.625rem（10px） | 0.875rem（14px） |
| padding-y | 0.5rem（8px） | 0.375rem（6px） | 0.625rem（10px） |
| 纯图标宽 | 2.5rem（40px） | 2rem（32px） | 3rem（48px） |
| 圆角 | 6px | 6px | 6px |
| `rounded` 圆角 | 2rem（胶囊） | 2rem | 2rem |
| 图标与文字间距 | 0.5rem（8px） | 同左 | 同左 |
| 过渡时长 | 0.2s | 同左 | 同左 |

### 4.2 颜色矩阵（Aura）

#### 深色模式（本项目 `default` 主题方向，实心按钮）

| severity | 背景 | hover | active | 文字 |
|----------|------|-------|--------|------|
| primary | primary.color | primary.hover | primary.active | primary.contrast |
| secondary | surface.800 `#27272a` | surface.700 `#3f3f46` | surface.600 `#52525b` | surface.300 `#d4d4d8` |
| success | green.400 `#4ade80` | green.300 `#86efac` | green.200 `#bbf7d0` | green.950 `#052e16` |
| info | sky.400 `#38bdf8` | sky.300 `#7dd3fc` | sky.200 `#bae6fd` | sky.950 `#082f49` |
| warn | orange.400 `#fb923c` | orange.300 `#fdba74` | orange.200 `#fed7aa` | orange.950 `#431407` |
| help | purple.400 `#c084fc` | purple.300 `#d8b4fe` | purple.200 `#e9d5ff` | purple.950 `#3b0764` |
| danger | red.400 `#f87171` | red.300 `#fca5a5` | red.200 `#fecaca` | red.950 `#450a0a` |
| contrast | surface.0 `#ffffff` | surface.100 `#f4f4f5` | surface.200 `#e4e4e7` | surface.950 `#09090b` |

#### 浅色模式（本项目 `bright` / `eye` 主题方向，实心按钮）

| severity | 背景 | hover | active | 文字 |
|----------|------|-------|--------|------|
| secondary | surface.100 `#f1f5f9` | surface.200 `#e2e8f0` | surface.300 `#cbd5e1` | surface.600 `#475569` |
| success | green.500 `#22c55e` | green.600 `#16a34a` | green.700 `#15803d` | `#ffffff` |
| info | sky.500 `#0ea5e9` | sky.600 `#0284c7` | sky.700 `#0369a1` | `#ffffff` |
| warn | orange.500 `#f97316` | orange.600 `#ea580c` | orange.700 `#c2410c` | `#ffffff` |
| help | purple.500 `#a855f7` | purple.600 `#9333ea` | purple.700 `#7e22ce` | `#ffffff` |
| danger | red.500 `#ef4444` | red.600 `#dc2626` | red.700 `#b91c1c` | `#ffffff` |
| contrast | surface.950 `#020617` | surface.900 `#0f172a` | surface.800 `#1e293b` | `#ffffff` |

#### outlined / text

- outlined：透明底 + 1px 边框（彩色用 `{color}.200`/`{color}.700`，secondary 用 `surface.200`/`surface.700`），hover 背景用 `{color}.50`（深色模式用 `color-mix(…, transparent 96%)`），active 用 `100`/`84%`；
- text：无边框无底色，hover 背景同 outlined 的 hover 规则，文字用该 severity 的主色；
- link：无底色无边框，文字 `primary.color`，hover 加下划线。

#### raised

`0 3px 1px -2px rgba(0,0,0,.2), 0 2px 2px 0 rgba(0,0,0,.14), 0 1px 5px 0 rgba(0,0,0,.12)`

---

## 5. 与现有主题体系的衔接

现有 `ColorPalette` 只有 `custom_context_color`（蓝）、`custom_green`、`custom_red`、`custom_yellow` 等少量语义色，不足以支撑 8 个 severity。建议：

1. 在主题 YAML 中新增一组**语义色**（每个主题一份），例如：

```yaml
button:
  secondary: { base: "#27272a", hover: "#3f3f46", active: "#52525b", text: "#d4d4d8" }
  success:   { base: "#4ade80", hover: "#86efac", active: "#bbf7d0", text: "#052e16" }
  info:      { base: "#38bdf8", hover: "#7dd3fc", active: "#bae6fd", text: "#082f49" }
  warn:      { base: "#fb923c", hover: "#fdba74", active: "#fed7aa", text: "#431407" }
  help:      { base: "#c084fc", hover: "#d8b4fe", active: "#e9d5ff", text: "#3b0764" }
  danger:    { base: "#f87171", hover: "#fca5a5", active: "#fecaca", text: "#450a0a" }
  contrast:  { base: "#ffffff", hover: "#f4f4f5", active: "#e4e4e7", text: "#09090b" }
```

2. `primary` 直接复用 `ColorPalette.custom_context_color` 及其 hover/pressed 三个令牌，保证与现有按钮、选中态一致；
3. 组件**不缓存颜色**，绘制时实时读调色板（沿用 `CLeftMenuButton` 的做法），主题切换自动生效；
4. rounded / raised / size 等几何量走新增的设计令牌（`tokens.button.*`），不写死在组件里；
5. 现有 `CPushButton` / `CStatusButton` / `CMenuButton` **保留不动**（9 个应用页面在用）；`CButton` 独立新增，后续可让 `CPushButton` 变成 `CButton` 的薄封装。

---

## 6. 目录结构规划

```
GuiCore/CustomUI/button/
├── __init__.py            # 导出 CButton / CButtonGroup / CSplitButton（保留旧导出）
├── button.py              # CButton：绘制 + 状态机 + 参数解析
├── button_group.py        # CButtonGroup：边框合并、首尾圆角
├── split_button.py        # CSplitButton：主按钮 + 箭头 + CMenu
├── severity.py            # Severity 枚举与颜色解析（读调色板）
├── README.md              # 本文
├── push_btn.py            # 现有，保留
├── menu_btn.py            # 现有，保留
└── status_btn.py          # 现有，保留
```

绘制策略：与 `CLeftMenuButton` 一致——**自绘 `paintEvent`**（不用 QSS），因为需要按 severity × variant 组合动态取色、圆角合并、focus ring 与 loading 动画，QSS 难以表达状态矩阵。

---

## 7. 图标与资源

Sakai 用 PrimeIcons（`pi pi-*`）。本项目 `customgui/resource/customui/images/svg_icons/` 目前只有 43 个图标，可直接映射：

| PrimeIcons | 现有资源 | 状态 |
|------------|----------|------|
| `pi-times` | `icon_close.svg` | ✅ |
| `pi-search` | `icon_search.svg` | ✅ |
| `pi-home` | `icon_home.svg` | ✅ |
| `pi-heart` | `icon_heart.svg` | ✅ |
| `pi-check` | `icon_save.svg`（近似） | ⚠️ 建议补 `icon_check.svg` |
| `pi-user` | `icon_users.svg` | ✅ |
| `pi-chevron-down` | `icon_arrow_down.svg` | ✅ |
| `pi-star-fill` | — | ❌ 需新增 |
| `pi-bookmark` | — | ❌ 需新增 |
| `pi-bell` | — | ❌ 需新增 |
| `pi-refresh` | — | ❌ 需新增 |
| `pi-trash` | — | ❌ 需新增 |
| `pi-chevron-right` | `icon_arrow_right.svg` | ✅ |

方案：优先补齐 **6 个缺失 SVG**（`icon_star_fill`、`icon_bookmark`、`icon_bell`、`icon_refresh`、`icon_trash`、`icon_check`），风格统一为单色描边，配合 `icon_paint` 的 `SourceIn` 着色，天然支持主题变色。

Templating 分组的 logo 按钮直接用现有图片资源（`PathFactory.set_svg_icon` / `set_jpg_image`），不需要额外素材。

---

## 8. 「按钮预览」页面规划

### 8.1 页面替换

- 移除 `Apps/` 下现有 9 个应用目录（`example`、`p2ptest_*`、`welcome`）；
- 新增 `Apps/button_preview/`：`config.yml`（`app_id: app.menu.left.button_preview`、`is_default: true`）+ `gui/main.py` + `language/zh_cn.yml` / `en_us.yml`；
- 左侧菜单只剩「按钮预览」一项，默认页指向它。

### 8.2 页面结构

单页滚动，`CScrollArea` 内放 14 张 `CCard`，卡片标题对应 Sakai 分组名，卡片内用 `QGridLayout` 排列按钮（每行 4–5 个，随宽度自适应）：

| 卡片 | 内容 |
|------|------|
| Default | Submit / Disabled / Link |
| Severities | 8 个实心按钮 |
| Text | 8 个 text（含 Plain） |
| Outlined | 8 个 outlined |
| Group | 1 个 `CButtonGroup`（3 按钮） |
| SplitButton | 8 个 `CSplitButton`（菜单项 Update/Delete/Home） |
| Templating | 2 个自定义内容按钮 |
| Icons | 纯图标 / 左图标 / 右图标 |
| Raised | 8 个 |
| Rounded | 8 个 |
| Rounded Icons | 7 个 |
| Rounded Text | 7 个 |
| Rounded Outlined | 7 个 |
| Loading | 4 个（点击触发 1s loading） |

所有可见文本走该应用语言包，语言切换时随页面重建刷新（与现有应用协议一致）。

---

## 9. 实施顺序与验收

| 阶段 | 内容 | 验收 |
|------|------|------|
| S1 | `severity.py` + `CButton` 基础绘制（solid/outlined/text/link × 8 severity） | 分组 2/3/4 与截图一致，hover/pressed 正确 |
| S2 | shape/elevation/content/state（rounded、raised、icon 左右、纯图标、disabled、focus） | 分组 1/8/9/10/11/12/13 一致 |
| S3 | loading（spinner + 宽度锁定） | 分组 14 点击表现一致 |
| S4 | `CButtonGroup` + `CSplitButton`（复用 `CMenu`） | 分组 5/6 一致，菜单可弹出/收起 |
| S5 | 主题令牌扩展（`tokens.button.*`、语义色）+ 四套主题校色 | 切换主题按钮颜色全部跟随 |
| S6 | 预览页 + 移除旧页面 + 语言包 | 启动即进入按钮预览，语言切换正常 |
| S7 | 测试与文档 | 新增 `tests/test_button_components.py`；`Docs/API.md` 重新生成 |

视觉验收基准：Sakai 页面截图（Aura / 深色 + 浅色各一份），逐组比对尺寸、圆角、色阶与间距。

---

## 10. 已确认决策

1. **统一收敛**：`CPushButton` / `CStatusButton` / `CMenuButton` 向 `CButton` 体系收敛；基座处于内测阶段，
   若影响下游项目，以下游跟随本基座为准。当前 `CPushButton` 已是 `CButton` 兼容壳，
   `CStatusButton` / `CMenuButton` 因带独立状态机暂未合并。
2. **size 变体**：已实现 `sm`(32) / `md`(40) / `lg`(48)，并提供 `set_size()` 运行时切换。
3. **Group / SplitButton**：均已实现（`CButtonGroup` 合并外框，`CSplitButton` 复用 `CMenu`）。
4. **美术资源**：新增图标统一放 `customgui/resource/customui/images/svg_icons/`，可随时按同名替换。
5. **旧页面**：`Apps/` 下 9 个应用已移到 `Apps_legacy/` 备查（不参与装配）。

## 11. 待补充

- `CStatusButton` 的多态视觉是否也迁到 `CButton` 的 severity 体系；
- 按钮 hover/pressed 的颜色过渡（Aura `transition: 0.2s`）目前是直接切换，后续可加 `QVariantAnimation`；
- 高 DPI 下图标缓存未按 `devicePixelRatio` 生成，4K 屏可再优化。
