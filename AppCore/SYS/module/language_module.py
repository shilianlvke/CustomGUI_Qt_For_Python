from dataclasses import dataclass


@dataclass
class LanguageHandler:
	def update(self, new_str: dict) -> None:
		for key, value in new_str.items():
			setattr(self, key, value)


Language = LanguageHandler()


__all__ = ["Language", "LanguageHandler"]
