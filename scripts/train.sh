exp_id=TwoStage_base1_sun_bigcenterhead

CUDA_VISIBLE_DEVICES=0,1,2,3 python tools/train_net.py \
  --config-file configs/$exp_id.yaml \
  --num-gpus 4 \
  --dist-url tcp://127.0.0.1:12345 \
  OUTPUT_DIR output/$exp_id \
  #MODEL.WEIGHTS_PRETRAIN output/TwoStage_base1_omni3d_out_removepeople/model_recent.pth \
  #--resume \
