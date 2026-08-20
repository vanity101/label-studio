"""合成一份最小 RLDS 数据集，供物化 eval 使用。不依赖真实 Bronze。

以顶层模块 `rlds_fixture` 加载（eval 会把本目录插入 sys.path），避免 TFDS
把 builder 的 code_path 解析坏。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import tensorflow_datasets as tfds


class MiniFridge(tfds.core.GeneratorBasedBuilder):
    VERSION = tfds.core.Version("1.0.0")

    def _info(self):
        return tfds.core.DatasetInfo(
            builder=self,
            features=tfds.features.FeaturesDict(
                {
                    "steps": tfds.features.Dataset(
                        {
                            "observation": tfds.features.FeaturesDict(
                                {"image": tfds.features.Image(shape=(64, 64, 3))}
                            ),
                            "action": tfds.features.Tensor(shape=(7,), dtype=np.float32),
                            "is_first": np.bool_,
                            "is_last": np.bool_,
                            "is_terminal": np.bool_,
                        }
                    ),
                }
            ),
        )

    def _split_generators(self, dl_manager):
        return {
            "train": self._generate_examples("train", 2),
        }

    def _generate_examples(self, split, count):
        for i in range(count):
            length = 5 + i
            steps = [
                {
                    "observation": {
                        "image": np.full((64, 64, 3), (j * 17) % 256, dtype=np.uint8)
                    },
                    "action": np.zeros((7,), np.float32),
                    "is_first": j == 0,
                    "is_last": j == length - 1,
                    "is_terminal": j == length - 1,
                }
                for j in range(length)
            ]
            yield f"{split}_{i}", {"steps": steps}


def build_mini_fridge(root: str) -> str:
    builder = MiniFridge(data_dir=root)
    builder.download_and_prepare()
    return str(Path(root) / "mini_fridge" / "1.0.0")
