#!/bin/bash
echo "last time running at: " > /HFIR/CG1D/shared/autoreduce/auto_reconstruction_cronjob_log.txt
date >> /HFIR/CG1D/shared/autoreduce/auto_reconstruction_cronjob_log.txt
source /opt/anaconda/etc/profile.d/conda.sh
conda activate imars3d
python /HFIR/CG1D/shared/autoreduce/reduce_cg1d.py
