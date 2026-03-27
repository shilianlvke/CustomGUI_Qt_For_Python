from dataclasses import dataclass


@dataclass
class LanguageHandler:
	"""语言资源容器。

	职责:
	- 持有当前语言包中可访问的字段。
	- 支持运行时批量更新语言文案。
	"""

	def update(self, new_str: dict) -> None:
		"""批量更新语言字段。

		参数:
		- new_str: 语言键值映射，键为字段名，值为对应文案或结构。

		返回:
		- None
		"""

		for key, value in new_str.items():
			setattr(self, key, value)


Language = LanguageHandler()


__all__ = ["Language", "LanguageHandler"]
