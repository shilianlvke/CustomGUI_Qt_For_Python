from PySide6 import QtCore, QtGui, QtSvgWidgets, QtWidgets

"""统一导出常用 PySide6 模块的公开符号。

该模块作为兼容层，便于项目其他位置通过单一入口导入 Qt API。
"""

__all__ = []

# 收集选定 Qt 模块中的公开名称，并在当前模块中暴露。
for _module in (QtCore, QtGui, QtWidgets, QtSvgWidgets):
	for _name in dir(_module):
		# 跳过私有/内部属性。
		if _name.startswith("_"):
			continue
		globals()[_name] = getattr(_module, _name)
		__all__.append(_name)