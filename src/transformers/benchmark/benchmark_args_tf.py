# coding=utf-8
# Copyright 2018 The HuggingFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from dataclasses import dataclass, field
from typing import Tuple

from ..file_utils import cached_property, is_tf_available, tf_required
from .benchmark_args_utils import BenchmarkArguments


if is_tf_available():
    import tensorflow as tf


logger = logging.getLogger(__name__)


@dataclass
class TensorflowBenchmarkArguments(BenchmarkArguments):
    tpu_name: str = field(
        default=None, metadata={"help": "Name of TPU"},
    )
    device_idx: int = field(
        default=0, metadata={"help": "CPU / GPU device index. Defaults to 0."},
    )
    tf_log_level: str = field(
        default="ERROR", metadata={"help": "Log level for tensorflow logger. Defaults to 'ERROR'"}
    )

    @cached_property
    @tf_required
    def _setup_strategy(self) -> Tuple["tf.distribute.Strategy", "tf.distribute.cluster_resolver.TPUClusterResolver"]:
        logger.info("Tensorflow: setting up strategy")
        tf.get_logger().setLevel(self.tf_log_level)

        if not self.no_tpu:
            try:
                if self.tpu_name:
                    tpu = tf.distribute.cluster_resolver.TPUClusterResolver(self.tpu_name)
                else:
                    tpu = tf.distribute.cluster_resolver.TPUClusterResolver()
            except ValueError:
                tpu = None
        else:
            tpu = None

        if tpu is not None:
            tf.config.experimental_connect_to_cluster(tpu)
            tf.tpu.experimental.initialize_tpu_system(tpu)

            strategy = tf.distribute.experimental.TPUStrategy(tpu)
        else:
            # currently no multi gpu is allowed
            gpus = tf.config.list_physical_devices("GPU")
            if self.is_gpu:
                try:
                    tf.config.experimental.set_visible_devices(gpus[self.device_idx], "GPU")
                    tf.config.experimental.set_memory_growth(gpus[self.device_idx], True)
                except:  # noqa: E722
                    logger.warn(f"Cannot enable gpu growth for GPU {self.device_idx}.")
                strategy = tf.distribute.OneDeviceStrategy(device=f"/gpu:{self.device_idx}")
            else:
                tf.config.experimental.set_visible_devices([], "GPU")  # disable GPU
                strategy = tf.distribute.OneDeviceStrategy(device=f"/cpu:{self.device_idx}")

        return strategy, tpu

    @property
    @tf_required
    def is_tpu(self) -> bool:
        tpu = self._setup_strategy[1]
        return tpu is not None and not self.args.no_tpu

    @property
    @tf_required
    def strategy(self) -> "tf.distribute.Strategy":
        return self._setup_strategy[0]

    @property
    @tf_required
    def n_gpu(self) -> int:
        if not self.no_cuda:
            gpus = tf.config.list_physical_devices("GPU")
            return len(gpus)
        return 0

    @property
    def is_gpu(self) -> bool:
        return self.n_gpu > 0
