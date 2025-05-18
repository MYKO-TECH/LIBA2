import yaml
from pathlib import Path

def get_knowledge():
    with open(Path(__file__).parent.parent/'knowledge'/'base.yaml') as f:
        return yaml.safe_load(f)

def save_knowledge(data):
    with open(Path(__file__).parent.parent/'knowledge'/'base.yaml', 'w') as f:
        yaml.safe_dump(data, f)

def deep_merge(target, source):
    for key in source:
        if isinstance(source[key], dict) and isinstance(target.get(key), dict):
            target[key] = deep_merge(target[key], source[key])
        else:
            target[key] = source[key]
    return target