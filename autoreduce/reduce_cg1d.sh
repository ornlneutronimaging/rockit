#!/bin/bash
source /SNS/users/j35/miniconda3/bin/activate /SNS/users/j35/miniconda3/envs/rockit
echo "last time running at: " > /HFIR/CG1D/shared/autoreduce/auto_reconstruction_cronjob_log.txt
date >> /HFIR/CG1D/shared/autoreduce/auto_reconstruction_cronjob_log.txt
which conda >> /HFIR/CG1D/shared/autoreduce/auto_reconstruction_cronjob_log.txt
python /HFIR/CG1D/shared/autoreduce/reduce_cg1d.py
