import pdb
import torch
from typing import Any, Dict, List, Set
from detectron2.solver.build import maybe_add_gradient_clipping
from torch.nn.parallel import DistributedDataParallel

from mmcv.runner.optimizer import DefaultOptimizerConstructor

def build_optimizer(cfg, model):
    norm_module_types = (
        torch.nn.BatchNorm1d,
        torch.nn.BatchNorm2d,
        torch.nn.BatchNorm3d,
        torch.nn.SyncBatchNorm,
        torch.nn.GroupNorm,
        torch.nn.InstanceNorm1d,
        torch.nn.InstanceNorm2d,
        torch.nn.InstanceNorm3d,
        torch.nn.LayerNorm,
        torch.nn.LocalResponseNorm,
    )
    params: List[Dict[str, Any]] = []
    memo: Set[torch.nn.parameter.Parameter] = set()

    # For RCNN3D
    if cfg.SOLVER.TYPE == 'mmcv_AdamW':
        optimizer = dict(type='AdamW', lr=cfg.SOLVER.BASE_LR, weight_decay=0.01)
        paramwise_cfg = dict(custom_keys={'img_backbone': dict(lr_mult=0.1)})
        optimizer_constructor = DefaultOptimizerConstructor(optimizer, paramwise_cfg)
        optimizer = optimizer_constructor(model)

    elif cfg.SOLVER.TYPE == 'sgd':
        for module in model.modules():
            for key, value in module.named_parameters(recurse=False):
                if not value.requires_grad:
                    continue
                # Avoid duplicating parameters
                if value in memo:
                    continue
                memo.add(value)
                
                lr = cfg.SOLVER.BASE_LR
                weight_decay = cfg.SOLVER.WEIGHT_DECAY

                if isinstance(module, norm_module_types) and (cfg.SOLVER.WEIGHT_DECAY_NORM is not None):
                    weight_decay = cfg.SOLVER.WEIGHT_DECAY_NORM
                
                elif key == "bias":
                    if (cfg.SOLVER.BIAS_LR_FACTOR is not None):
                        lr = cfg.SOLVER.BASE_LR * cfg.SOLVER.BIAS_LR_FACTOR
                    if (cfg.SOLVER.WEIGHT_DECAY_BIAS is not None):
                        weight_decay = cfg.SOLVER.WEIGHT_DECAY_BIAS

                # these params do not need weight decay at all
                # TODO parameterize these in configs instead.
                if key in ['priors_dims_per_cat', 'priors_z_scales', 'priors_z_stats']:
                    weight_decay = 0.0

                params += [{"params": [value], "lr": lr, "weight_decay": weight_decay}]
    # For PETR
    elif cfg.SOLVER.TYPE == 'adamw':
        lr = cfg.SOLVER.BASE_LR
        lr_mult = 0.25
        if type(model) == DistributedDataParallel: model = model.module
        backbone_params_ids = list(map(id, model.detector.img_backbone.parameters()))
        normal_params = filter(lambda p: id(p) not in backbone_params_ids, model.parameters())
        params = [
            {"params": normal_params, "lr": lr},
            {"params": model.detector.img_backbone.parameters(), "lr": lr_mult * lr},
        ]

    elif cfg.SOLVER.TYPE == 'sgd':
        optimizer = torch.optim.SGD(
            params, 
            cfg.SOLVER.BASE_LR, 
            momentum=cfg.SOLVER.MOMENTUM, 
            nesterov=cfg.SOLVER.NESTEROV, 
            weight_decay=cfg.SOLVER.WEIGHT_DECAY
        )
    elif cfg.SOLVER.TYPE == 'adam':
        optimizer = torch.optim.Adam(params, cfg.SOLVER.BASE_LR, eps=1e-02)
    elif cfg.SOLVER.TYPE == 'adam+amsgrad':
        optimizer = torch.optim.Adam(params, cfg.SOLVER.BASE_LR, amsgrad=True, eps=1e-02)
    elif cfg.SOLVER.TYPE == 'adamw':
        optimizer = torch.optim.AdamW(params, cfg.SOLVER.BASE_LR, eps=1e-02)
    elif cfg.SOLVER.TYPE == 'adamw+amsgrad':
        optimizer = torch.optim.AdamW(params, cfg.SOLVER.BASE_LR, amsgrad=True, eps=1e-02)
    else:
        raise ValueError('{} is not supported as an optimizer.'.format(cfg.SOLVER.TYPE))

    optimizer = maybe_add_gradient_clipping(cfg, optimizer)
    return optimizer

def freeze_bn(network):

    for _, module in network.named_modules():
        if isinstance(module, torch.nn.BatchNorm2d):
            module.eval()
            module.track_running_stats = False
