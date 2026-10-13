from pathlib import Path

from loadstructure import ConfigManager

# --- 需要合并的目录 ---
merged_dir = Path("configs/app")
yaml_files = sorted(merged_dir.glob("*.yaml"))
merged_cfg = ConfigManager.merge([str(f) for f in yaml_files])
print(merged_cfg.app.name)  # 合并后的配置

# --- 不能合并的目录：每个文件独立加载 ---
standalone_dir = Path("configs/secrets")
configs = {}
for yaml_file in standalone_dir.glob("*.yaml"):
    cfg = ConfigManager(str(yaml_file))
    cfg.load()
    configs[yaml_file.stem] = cfg

print(configs["key1"].api_token)  # 独立配置